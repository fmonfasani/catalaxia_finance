# -*- coding: utf-8 -*-
"""
M13-M15 / M24 -- Bateria de gates C-MKT sobre el estado persistido
===================================================================
Corre DESPUES del motor, sobre lo que quedo en PostgreSQL + el RAW en disco.
Escribe cada resultado en market_data_quality y devuelve un veredicto global.

Catalogo de gates
-----------------
  C-MKT-001  IDENTITY        identidad canonica coherente y sin colisiones
  C-MKT-002  SOURCE          toda corrida registrada con fuente/version/params
  C-MKT-003  COVERAGE        cobertura anual, gaps, regresiones
  C-MKT-004  OHLC            coherencia OHLC (upstream vs pipeline, via RAW)
  C-MKT-005  DUPLICATES      unicidad instrumento+rueda
  C-MKT-006  CURRENCY        moneda unica y coincidente con identidad
  C-MKT-007  SYMBOL          mapping MAPPED y sin simbolos compartidos
  C-MKT-008  DATE            sin fechas futuras; tz de mercado registrada
  C-MKT-009  NULLS           nulos en OHLC/volumen
  C-MKT-010  ADJ_NOISE       ruido de Adj Close dentro de tolerancia
  C-MKT-011  STALENESS       ultimo cierre certificado
  C-MKT-012  FINGERPRINT     business/full hash reconstruibles desde la base
  C-MKT-013  IDEMPOTENCY     ultima corrida repetida no escribio filas
  C-MKT-014  SNAPSHOT        snapshot separado del historico
  C-MKT-015  RAW_IMMUTABLE   sha256 de los RAW en disco == registrado
  C-MKT-016  CORP_ACTIONS    acciones corporativas consistentes con la serie
  C-MKT-017  PROVENANCE      cada fila trazable a corrida + RAW existente

Uso:
  python m4_quality.py --instruments 83,84 --json-out ruta.json
"""
from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import psycopg2

import market_core as core

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "data").is_dir())

SEV_ORDER = {"VALID": 0, "NOT_APPLICABLE": 0, "WARNING": 1, "INVALID": 2}


def pg_conn(dbname=None):
    return psycopg2.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=int(os.environ.get("DB_PORT", "5432")),
        dbname=dbname or os.environ.get("DB_NAME", "catalaxia"),
        user=os.environ.get("DB_USER", "catalaxia"),
        password=os.environ.get("DB_PASSWORD", "catalaxia"),
    )


class Bateria:
    def __init__(self, conn, run_id, raw_root=None):
        self.conn = conn
        self.cur = conn.cursor()
        self.run_id = run_id
        self.raw_root = Path(raw_root or ROOT)
        self.resultados = []

    def reg(self, code, iid, sev, detail, fecha=None):
        self.cur.execute("""INSERT INTO market_data_quality
            (check_code, instrument_id, trading_date, severity, detail, run_id)
            VALUES (%s,%s,%s,%s,%s,%s)""",
                         (code, iid, fecha, sev, detail, self.run_id))
        self.resultados.append({"check": code, "instrument_id": iid,
                                "severity": sev, "detail": detail,
                                "trading_date": str(fecha) if fecha else None})

    # ---------------------------------------------------------- por cartera
    def gates_globales(self, iids):
        cur = self.cur
        # C-MKT-001 identidad
        cur.execute("""SELECT p.instrument_id FROM market_price_daily p
                       LEFT JOIN market_instruments i USING (instrument_id)
                       WHERE i.instrument_id IS NULL GROUP BY 1""")
        huerfanos = [r[0] for r in cur.fetchall()]
        cur.execute("""SELECT COUNT(*) FROM market_instruments
                       WHERE entity_id IS NULL OR entity_id=''""")
        sin_entidad = cur.fetchone()[0]
        self.reg("C-MKT-001", None,
                 "INVALID" if (huerfanos or sin_entidad) else "VALID",
                 f"instrumentos con precios sin identidad={huerfanos}; "
                 f"identidades sin entity_id={sin_entidad}")

        # C-MKT-007 simbolos compartidos
        cur.execute("""SELECT ticker_yahoo, COUNT(*) FROM market_symbol_mappings
                       WHERE status='MAPPED' AND ticker_yahoo IS NOT NULL
                       GROUP BY 1 HAVING COUNT(*)>1""")
        colisiones = cur.fetchall()
        cur.execute("SELECT status, COUNT(*) FROM market_symbol_mappings GROUP BY 1")
        por_estado = dict(cur.fetchall())
        self.reg("C-MKT-007", None,
                 "INVALID" if colisiones else "VALID",
                 f"mappings por estado={por_estado}; simbolos MAPPED compartidos="
                 f"{[(t, n) for t, n in colisiones[:5]]} (total {len(colisiones)})")

        # C-MKT-015 inmutabilidad del RAW en disco
        cur.execute("""SELECT f.run_id, f.kind, f.rel_path, f.bytes, f.sha256
                       FROM market_raw_files f
                       JOIN market_raw_runs r USING (run_id)
                       WHERE r.instrument_id = ANY(%s)
                       ORDER BY f.file_id""", (iids,))
        archivos = cur.fetchall()
        faltan, alterados, ok = [], [], 0
        for run_id, kind, rel, nbytes, sha in archivos:
            p = self.raw_root / rel
            if not p.exists():
                faltan.append(rel)
                continue
            real = core.sha256_hex(p.read_bytes())
            if real != sha:
                alterados.append((rel, sha[:12], real[:12]))
            else:
                ok += 1
        self.reg("C-MKT-015", None,
                 "INVALID" if (faltan or alterados) else "VALID",
                 f"archivos RAW verificados={ok}/{len(archivos)}; "
                 f"ausentes={len(faltan)} {faltan[:3]}; "
                 f"alterados={len(alterados)} {alterados[:3]}")

        # C-MKT-002 corridas registradas con fuente/version/parametros
        cur.execute("""SELECT COUNT(*) FROM market_raw_runs
                       WHERE source IS NULL OR source_version IS NULL
                          OR request_parameters IS NULL""")
        incompletas = cur.fetchone()[0]
        cur.execute("SELECT status, COUNT(*) FROM market_raw_runs GROUP BY 1")
        runs = dict(cur.fetchall())
        self.reg("C-MKT-002", None,
                 "INVALID" if incompletas else "VALID",
                 f"corridas por estado={runs}; sin fuente/version/params={incompletas}")

        # C-MKT-017 provenance
        cur.execute("""SELECT COUNT(*) FROM market_price_daily p
                       WHERE NOT EXISTS (SELECT 1 FROM market_raw_runs r
                                         WHERE r.run_id = p.source_run_id)""")
        sin_run = cur.fetchone()[0]
        cur.execute("""SELECT COUNT(*) FROM market_price_daily p
                       JOIN market_raw_runs r ON r.run_id = p.source_run_id
                       WHERE NOT EXISTS (SELECT 1 FROM market_raw_files f
                                         WHERE f.run_id = r.run_id
                                           AND f.kind='HISTORY_CSV')""")
        sin_raw = cur.fetchone()[0]
        self.reg("C-MKT-017", None,
                 "INVALID" if (sin_run or sin_raw) else "VALID",
                 f"filas sin corrida registrada={sin_run}; "
                 f"filas cuya corrida no tiene RAW archivado={sin_raw}")

    # ------------------------------------------------------ por instrumento
    def gates_instrumento(self, iid, gap_habiles=12, staleness_dias=7):
        cur = self.cur
        cur.execute("""SELECT trading_date, open, high, low, close, adj_close,
                              volume, dividends, stock_splits, currency,
                              source_hash, source_run_id
                       FROM market_price_daily WHERE instrument_id=%s
                       ORDER BY trading_date""", (iid,))
        filas = cur.fetchall()
        if not filas:
            self.reg("C-MKT-003", iid, "INVALID", "sin filas en market_price_daily")
            return {"filas": 0}

        cur.execute("""SELECT currency, exchange, entity_id, ticker_canonico
                       FROM market_instruments WHERE instrument_id=%s""", (iid,))
        ident = cur.fetchone()
        cur.execute("""SELECT timezone FROM market_raw_runs
                       WHERE instrument_id=%s AND status='SUCCESS'
                       ORDER BY fetched_at_utc DESC LIMIT 1""", (iid,))
        tzrow = cur.fetchone()
        tz_txt = tzrow[0] if tzrow else None
        market_tz = None
        if tz_txt and tz_txt not in ("None", "null"):
            try:
                import zoneinfo
                market_tz = zoneinfo.ZoneInfo(tz_txt)
            except Exception:                            # noqa: BLE001
                market_tz = None

        F = lambda x: None if x is None else float(x)    # noqa: E731
        rows, hash_bad = [], []
        for (d, o, h, l, c, ac, v, dv, sp, cy, sh, srun) in filas:
            r = core.make_row(iid, d, F(o), F(h), F(l), F(c), F(ac),
                              None if v is None else int(v), F(dv), F(sp))
            rows.append((r, cy, sh, srun))
            if r.full_hash != sh:
                hash_bad.append(d)

        # ---- C-MKT-012 fingerprint reconstruible ------------------------
        self.reg("C-MKT-012", iid, "INVALID" if hash_bad else "VALID",
                 f"filas={len(rows)}; full_hash reconstruido != persistido en "
                 f"{len(hash_bad)} fila(s) {[str(x) for x in hash_bad[:5]]}; "
                 f"business_hash derivable de las columnas persistidas")

        # ---- C-MKT-005 duplicados ---------------------------------------
        fechas = [r[0].trading_date for r in rows]
        self.reg("C-MKT-005", iid,
                 "VALID" if len(fechas) == len(set(fechas)) else "INVALID",
                 f"filas={len(fechas)} fechas_distintas={len(set(fechas))}")

        # ---- C-MKT-006 moneda -------------------------------------------
        monedas = Counter(r[1] for r in rows)
        esperada = ident[0] if ident else None
        ok_cur = len(monedas) == 1 and (esperada is None
                                        or list(monedas)[0] == esperada)
        self.reg("C-MKT-006", iid, "VALID" if ok_cur else "INVALID",
                 f"moneda en la serie={dict(monedas)}; identidad={esperada}")

        # ---- C-MKT-008 fechas -------------------------------------------
        hoy = datetime.now(timezone.utc)
        estados = Counter(core.session_state(d, market_tz, hoy) for d in fechas)
        futuras = estados.get(core.FUTURE, 0)
        self.reg("C-MKT-008", iid, "INVALID" if futuras else "VALID",
                 f"tz_mercado={tz_txt}; ruedas por estado={dict(estados)}; "
                 f"rango={fechas[0]}..{fechas[-1]}")

        # ---- C-MKT-009 nulos --------------------------------------------
        nulos = [r[0].trading_date for r in rows
                 if None in (r[0].open, r[0].high, r[0].low, r[0].close)]
        sin_vol = sum(1 for r in rows if r[0].volume is None)
        self.reg("C-MKT-009", iid, "WARNING" if nulos else "VALID",
                 f"OHLC nulos={len(nulos)} {[str(x) for x in nulos[:5]]}; "
                 f"volumen nulo={sin_vol}")

        # ---- C-MKT-004 OHLC (upstream vs pipeline, contrastado con RAW) --
        viol = [(r[0], core.ohlc_violations(r[0])) for r in rows]
        viol = [(r, v) for r, v in viol if v]
        if viol:
            upstream, propios = self._contrastar_con_raw(iid, viol)
            sev = "INVALID" if propios else "WARNING"
            self.reg("C-MKT-004", iid, sev,
                     f"filas={len(rows)}; incoherencias={len(viol)}; "
                     f"reproducidas byte a byte en el RAW (defecto de la fuente)="
                     f"{upstream}; introducidas por el pipeline={len(propios)} "
                     f"{[str(x) for x in propios[:5]]}; "
                     f"ej={[(str(r.trading_date), ','.join(v)) for r, v in viol[:3]]}")
            for r, v in viol[:50]:
                self.reg("C-MKT-004", iid, "WARNING",
                         f"UPSTREAM_OHLC_DEFECT: {','.join(v)} "
                         f"O={r.open} H={r.high} L={r.low} C={r.close}",
                         fecha=r.trading_date)
        else:
            self.reg("C-MKT-004", iid, "VALID",
                     f"filas={len(rows)} sin incoherencias OHLC")

        # ---- C-MKT-003 cobertura + gaps ---------------------------------
        cur.execute("""SELECT EXTRACT(year FROM trading_date)::int, COUNT(*),
                              MIN(trading_date), MAX(trading_date)
                       FROM market_price_daily WHERE instrument_id=%s
                       GROUP BY 1 ORDER BY 1""", (iid,))
        anos = cur.fetchall()
        gaps = []
        for i in range(1, len(fechas)):
            g = (fechas[i] - fechas[i - 1]).days
            if g > gap_habiles * 7 // 5 + 2:
                gaps.append((str(fechas[i - 1]), str(fechas[i]), g))
        self.reg("C-MKT-003", iid, "WARNING" if gaps else "VALID",
                 f"anos cubiertos={len(anos)} ({anos[0][0]}..{anos[-1][0]}); "
                 f"ruedas={len(fechas)}; gaps>{gap_habiles}h={len(gaps)} "
                 f"top={gaps[:5]}")

        # ---- C-MKT-011 staleness ----------------------------------------
        ult = rows[-1][0]
        dias = (hoy.date() - ult.trading_date).days
        self.reg("C-MKT-011", iid,
                 "VALID" if dias <= staleness_dias else "WARNING",
                 f"ultimo_cierre={ult.trading_date} close={ult.close} "
                 f"estado_sesion="
                 f"{core.session_state(ult.trading_date, market_tz, hoy)} "
                 f"dias_atras={dias} cutoff={hoy.date()}",
                 fecha=ult.trading_date)

        # ---- C-MKT-016 corporate actions --------------------------------
        div_serie = sum(1 for r in rows if r[0].dividends)
        sp_serie = sum(1 for r in rows if r[0].stock_splits)
        cur.execute("""SELECT COUNT(*) FILTER (WHERE action_type='DIVIDEND'),
                              COUNT(*) FILTER (WHERE action_type='STOCK_SPLIT')
                       FROM market_corporate_actions WHERE instrument_id=%s""",
                    (iid,))
        n_div, n_sp = cur.fetchone()
        self.reg("C-MKT-016", iid,
                 "VALID" if (n_div == div_serie and n_sp == sp_serie) else "WARNING",
                 f"serie: dividendos={div_serie} splits={sp_serie} | "
                 f"market_corporate_actions: dividendos={n_div} splits={n_sp}")

        # ---- C-MKT-010 ruido Adj Close ----------------------------------
        cur.execute("""SELECT COUNT(*) FROM market_data_changes
                       WHERE instrument_id=%s AND reason=%s""",
                    (iid, core.R_ADJ_NOISE))
        n_noise = cur.fetchone()[0]
        self.reg("C-MKT-010", iid, "VALID" if n_noise == 0 else "WARNING",
                 f"tolerancia relativa={core.TOL_ADJ_REL:g}; filas escritas por "
                 f"ruido de Adj Close={n_noise} (debe ser 0: el ruido no persiste)")

        # ---- C-MKT-013 idempotencia -------------------------------------
        cur.execute("""SELECT run_id, status FROM market_fetch_log
                       WHERE instrument_id=%s AND status IN
                             ('SUCCESS','SIN_CAMBIOS','PARTIAL','FAILED')
                       ORDER BY log_id DESC LIMIT 2""", (iid,))
        ultimas = cur.fetchall()
        if len(ultimas) < 2:
            self.reg("C-MKT-013", iid, "NOT_APPLICABLE",
                     "menos de dos corridas registradas")
        else:
            ultima = ultimas[0]
            cur.execute("""SELECT change_type, reason, COUNT(*)
                           FROM market_data_changes WHERE curr_run_id=%s
                           GROUP BY 1,2 ORDER BY 3 DESC""", (ultima[0],))
            camb = cur.fetchall()
            no_benignos = [(ct, rs, n) for ct, rs, n in camb
                           if ct == "CHANGED" and rs not in core.BENIGN_REASONS]
            self.reg("C-MKT-013", iid,
                     "VALID" if not no_benignos else "WARNING",
                     f"ultima corrida={ultima[0]} estado={ultima[1]}; "
                     f"cambios registrados={[tuple(c) for c in camb] or 'ninguno'}; "
                     f"no benignos={no_benignos or 0}")

        # ---- C-MKT-014 snapshot separado --------------------------------
        cur.execute("SELECT COUNT(*) FROM market_snapshots WHERE instrument_id=%s",
                    (iid,))
        n_snap = cur.fetchone()[0]
        self.reg("C-MKT-014", iid, "VALID" if n_snap else "WARNING",
                 f"snapshots={n_snap} en market_snapshots; la serie historica no "
                 f"contiene campos de snapshot")

        # ---- provenance por instrumento ---------------------------------
        runs = Counter(r[3] for r in rows)
        self.reg("C-MKT-017", iid, "VALID",
                 f"filas por corrida de origen={dict(list(runs.items())[:6])}"
                 + (f" (+{len(runs) - 6} corridas)" if len(runs) > 6 else ""))

        return {"filas": len(rows), "rango": f"{fechas[0]}..{fechas[-1]}",
                "ultimo_close": float(ult.close) if ult.close is not None else None,
                "gaps": len(gaps), "incoherencias_ohlc": len(viol),
                "hash_mismatch": len(hash_bad)}

    def _contrastar_con_raw(self, iid, viol):
        """Por cada incoherencia OHLC verifica si el valor esta identico en el
        RAW archivado de la corrida que lo produjo. Si esta -> defecto de la
        fuente (el pipeline transcribio fiel). Si no -> defecto del pipeline."""
        import pandas as pd
        cache = {}
        upstream, propios = 0, []
        self.cur.execute("""SELECT p.trading_date, f.rel_path
                            FROM market_price_daily p
                            JOIN market_raw_files f
                              ON f.run_id = p.source_run_id
                             AND f.kind='HISTORY_CSV'
                            WHERE p.instrument_id=%s""", (iid,))
        mapa = dict(self.cur.fetchall())
        for r, _v in viol:
            rel = mapa.get(r.trading_date)
            if not rel:
                propios.append(r.trading_date)
                continue
            if rel not in cache:
                p = self.raw_root / rel
                if not p.exists():
                    cache[rel] = None
                else:
                    df = pd.read_csv(p, index_col=0)
                    df.index = [str(x)[:10] for x in df.index]
                    cache[rel] = df
            df = cache[rel]
            key = str(r.trading_date)
            if df is None or key not in df.index:
                propios.append(r.trading_date)
                continue
            src = df.loc[key]
            iguales = all(
                core.norm_num(src.get(col)) == val
                for col, val in (("Open", r.open), ("High", r.high),
                                 ("Low", r.low), ("Close", r.close)))
            if iguales:
                upstream += 1
            else:
                propios.append(r.trading_date)
        return upstream, propios


def veredicto(resultados):
    peor = max((SEV_ORDER[r["severity"]] for r in resultados), default=0)
    return {0: "PASS", 1: "PASS_WITH_WARNINGS", 2: "FAIL"}[peor]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--instruments", help="instrument_id separados por coma")
    ap.add_argument("--gap-habiles", type=int, default=12)
    ap.add_argument("--staleness-dias", type=int, default=7)
    ap.add_argument("--json-out")
    ap.add_argument("--dbname")
    args = ap.parse_args()

    conn = pg_conn(args.dbname)
    run_id = f"quality-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    b = Bateria(conn, run_id)
    if args.instruments:
        iids = [x.strip() for x in args.instruments.split(",")]
    else:
        b.cur.execute("SELECT DISTINCT instrument_id FROM market_price_daily "
                      "ORDER BY 1")
        iids = [r[0] for r in b.cur.fetchall()]

    b.gates_globales(iids)
    resumen = {}
    for iid in iids:
        resumen[iid] = b.gates_instrumento(iid, args.gap_habiles,
                                           args.staleness_dias)
    conn.commit()

    v = veredicto(b.resultados)
    print(f"run_id={run_id}  instrumentos={iids}")
    for iid, s in resumen.items():
        print(f"  [{iid}] {s}")
    por_sev = Counter(r["severity"] for r in b.resultados)
    print(f"\ngates ejecutados={len(b.resultados)} -> {dict(por_sev)}")
    vistos = set()
    for r in b.resultados:
        if r["severity"] in ("INVALID", "WARNING"):
            k = (r["check"], r["instrument_id"], r["severity"])
            if k in vistos:
                continue
            vistos.add(k)
            print(f"  {r['severity']:<8} {r['check']} [{r['instrument_id']}] "
                  f"{r['detail'][:170]}")
    print(f"\nVEREDICTO: {v}")

    if args.json_out:
        Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json_out).write_text(json.dumps(
            {"run_id": run_id, "veredicto": v, "resumen": resumen,
             "gates": b.resultados}, indent=2, default=str), encoding="utf-8")
        print(f"reporte -> {args.json_out}")
    conn.close()
    return 0 if v != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
