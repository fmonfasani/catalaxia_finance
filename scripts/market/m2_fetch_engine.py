# -*- coding: utf-8 -*-
"""
M3-M12 -- Motor de fetch Market Data -> PostgreSQL
===================================================
Por cada instrumento MAPPED:

  FETCH     Source.fetch(ticker)  (yahoo en produccion, fixture en tests)
  RAW       payload exacto -> data/raw/market/<iid>/<run_id>/ (+sha256)  INMUTABLE
  PARSE     fecha de mercado en tz del exchange, tipos numericos, duplicados
  GATES     identity / symbol / source / currency / date / duplicates / nulls
  DIFF      business_hash(actual) vs business_hash(RECONSTRUIDO de la DB)
  UPSERT    solo filas NEW o CHANGED  (idempotencia real: 2da corrida = 0 writes)
  ACTIONS   dividendos/splits -> market_corporate_actions
  SNAPSHOT  fast_info -> market_snapshots (jamas historico)
  LOG       market_fetch_log + market_raw_runs + market_data_changes

Reglas duras
------------
* La rueda del dia (session=CURRENT en la tz del mercado) puede moverse: se
  clasifica INTRADAY_UPDATE, no corrupcion.
* Adj Close no entra al business_hash. Su ruido float se absorbe con
  tolerancia relativa y se reporta como ADJ_NOISE (no escribe).
* Si el payload trae MENOS del `umbral_cobertura` de las ruedas ya
  almacenadas, la corrida se CUARENTENA: se archiva el RAW y no se toca
  market_price_daily.
* Nunca se borran filas. Ruedas ausentes en el payload se auditan como
  MISSING.

Uso:
  python m2_fetch_engine.py --instruments YPFD.BA,YPF --stage golden
  python m2_fetch_engine.py --limit 5 --stage smoke --no-snapshot
"""
from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import psycopg2
import psycopg2.extras

import market_core as core
from market_source import DEFAULT_PARAMS, FetchResult, YahooSource

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "data").is_dir())
RAW_BASE = ROOT / "data" / "raw" / "market"

UMBRAL_COBERTURA = 0.90     # payload minimo aceptable vs filas ya almacenadas
SLEEP_BETWEEN = 1.0


import market_db


def pg_conn(dbname: str = None, *, write: bool = False):
    """Conexion a PostgreSQL a traves de la guarda F-001 (market_db).

    SOLO LECTURA por defecto. Escribir exige `write=True` en el call site y, si
    el destino es el puerto 5432, ademas `MARKET_ALLOW_PROD_WRITE=1`.
    """
    return market_db.connect(dbname, write=write)


@dataclass
class InstrumentSpec:
    instrument_id: str
    entity_id: str
    ticker_canonico: str
    ticker_yahoo: str
    currency: str
    exchange: Optional[str] = None


@dataclass
class RunReport:
    run_id: str
    instrument_id: str
    ticker_yahoo: str
    status: str                      # SUCCESS | SIN_CAMBIOS | FAILED | QUARANTINED
    rows: int = 0
    min_date: Optional[str] = None
    max_date: Optional[str] = None
    raw_sha256: Optional[str] = None
    batch_hash: Optional[str] = None
    resumen: dict = field(default_factory=dict)
    gates: list = field(default_factory=list)      # (code, severity, detail)
    faltantes: int = 0
    error: Optional[str] = None
    tz: Optional[str] = None


# ------------------------------------------------------------------ helpers

def _reconstruir_existentes(cur, iid):
    """Relee market_price_daily y RECONSTRUYE los hashes desde los valores
    persistidos. Esta es la unica forma valida de comparar: nunca se usa
    source_hash como si fuera business_hash."""
    cur.execute("""SELECT trading_date, open, high, low, close, adj_close,
                          volume, dividends, stock_splits, source_hash
                   FROM market_price_daily WHERE instrument_id=%s""", (iid,))
    out, mismatch = {}, []
    F = lambda x: None if x is None else float(x)
    for (d, o, h, l, c, ac, v, dv, sp, sh) in cur.fetchall():
        row = core.make_row(iid, d, F(o), F(h), F(l), F(c), F(ac),
                            None if v is None else int(v), F(dv), F(sp))
        if row.full_hash != sh:
            mismatch.append(d)
        out[d] = row
    return out, mismatch


def _archivar_raw(iid, run_id, res: FetchResult, meta_extra: dict):
    raw_dir = RAW_BASE / str(iid) / run_id
    raw_dir.mkdir(parents=True, exist_ok=True)
    csv_bytes = res.raw_bytes if res.raw_bytes is not None else b""
    (raw_dir / "history.csv").write_bytes(csv_bytes)
    raw_sha = core.sha256_hex(csv_bytes)
    meta = {**meta_extra, "sha256_history_csv": raw_sha,
            "bytes_history_csv": len(csv_bytes)}
    meta_bytes = json.dumps(meta, indent=2, default=str).encode("utf-8")
    (raw_dir / "meta.json").write_bytes(meta_bytes)
    return raw_dir, csv_bytes, raw_sha, meta_bytes, core.sha256_hex(meta_bytes)


def _rel(p: Path) -> str:
    return str(p).replace(str(ROOT) + os.sep, "").replace(os.sep, "/")


# --------------------------------------------------------------- motor

def run_instrument(conn, spec: InstrumentSpec, source, stage: str,
                   now_utc: datetime = None, con_snapshot: bool = True,
                   params: dict = None) -> RunReport:
    cur = conn.cursor()
    ts = now_utc or datetime.now(timezone.utc)
    iid = str(spec.instrument_id)
    run_id = f"{stage}-{iid}-{ts.strftime('%Y%m%dT%H%M%S%fZ')}"
    params = dict(params or DEFAULT_PARAMS)
    config_hash = core.sha256_hex(json.dumps(
        {"ticker": spec.ticker_yahoo, **params, "source": source.name,
         "version": source.version}, sort_keys=True).encode())

    rep = RunReport(run_id=run_id, instrument_id=iid,
                    ticker_yahoo=spec.ticker_yahoo, status="FAILED")
    gates = rep.gates

    def gate(code, sev, detail, fecha=None):
        gates.append((code, sev, detail))
        cur.execute("""INSERT INTO market_data_quality
            (check_code, instrument_id, trading_date, severity, detail, run_id)
            VALUES (%s,%s,%s,%s,%s,%s)""", (code, iid, fecha, sev, detail, run_id))

    cur.execute("""INSERT INTO market_fetch_log
        (run_id, instrument_id, ticker_yahoo, source, requested_at, started_at, status)
        VALUES (%s,%s,%s,%s,%s,%s,'REQUESTED')""",
                (run_id, iid, spec.ticker_yahoo, source.name, ts, ts))
    conn.commit()

    # ---- C-MKT-001 identidad --------------------------------------------
    cur.execute("""SELECT entity_id, currency, exchange FROM market_instruments
                   WHERE instrument_id=%s""", (iid,))
    ident = cur.fetchone()
    if not ident:
        gate("C-MKT-001", "INVALID", f"instrument_id {iid} inexistente en market_instruments")
        _cerrar_log(cur, run_id, "FAILED", 0, error=("IDENTITY", "instrumento inexistente"))
        conn.commit()
        rep.error = "identidad inexistente"
        return rep
    if ident[0] != spec.entity_id:
        gate("C-MKT-001", "INVALID",
             f"entity_id divergente: spec={spec.entity_id} db={ident[0]}")
    else:
        gate("C-MKT-001", "VALID",
             f"entity_id={ident[0]} instrument_id={iid} canonico={spec.ticker_canonico}")

    # ---- C-MKT-007 simbolo ----------------------------------------------
    cur.execute("""SELECT ticker_yahoo, status FROM market_symbol_mappings
                   WHERE instrument_id=%s""", (iid,))
    m = cur.fetchone()
    if not m or m[1] != "MAPPED":
        gate("C-MKT-007", "INVALID",
             f"mapping no MAPPED: {m[1] if m else 'ausente'}")
    elif m[0] != spec.ticker_yahoo:
        gate("C-MKT-007", "INVALID",
             f"ticker divergente: mapping={m[0]} pedido={spec.ticker_yahoo}")
    else:
        gate("C-MKT-007", "VALID", f"MAPPED {iid} -> {spec.ticker_yahoo}")

    # ---- FETCH ------------------------------------------------------------
    res = source.fetch(spec.ticker_yahoo, params)
    if not res.ok:
        gate("C-MKT-002", "INVALID",
             f"fuente {source.name} fallo tras {res.attempts} intento(s): "
             f"{res.error_type}: {res.error_message}")
        cur.execute("""INSERT INTO market_raw_runs
            (run_id, stage_run_id, entity_id, instrument_id, ticker_canonico,
             ticker_yahoo, source, source_version, request_parameters,
             interval, auto_adjust, actions, fetched_at_utc, currency, exchange,
             row_count, status)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'1d',FALSE,TRUE,%s,%s,%s,0,'FAILED')
            ON CONFLICT (run_id) DO NOTHING""",
                    (run_id, stage, spec.entity_id, iid, spec.ticker_canonico,
                     spec.ticker_yahoo, source.name, source.version,
                     psycopg2.extras.Json({**params, "config_hash": config_hash,
                                           "error_type": res.error_type}),
                     ts, spec.currency, spec.exchange))
        _cerrar_log(cur, run_id, "FAILED", res.rows,
                    retry=max(res.attempts - 1, 0),
                    error=(res.error_type, res.error_message))
        conn.commit()
        rep.error = f"{res.error_type}: {res.error_message}"
        return rep

    gate("C-MKT-002", "VALID",
         f"{source.name} {source.version} params={json.dumps(params, sort_keys=True)} "
         f"intentos={res.attempts} filas={res.rows}"
         + (f" [recuperado tras {res.attempts - 1} fallo(s)]" if res.attempts > 1 else ""))

    # ---- NORMALIZE --------------------------------------------------------
    norm = core.normalize_history(res.df, iid)
    recs = norm.rows
    rep.tz = norm.tz
    if not recs:
        gate("C-MKT-002", "INVALID", "payload sin filas utilizables")
        _cerrar_log(cur, run_id, "FAILED", 0, error=("EMPTY", "sin filas"))
        conn.commit()
        rep.error = "payload vacio"
        return rep

    market_tz = getattr(res.df.index, "tz", None)
    fechas = [r.trading_date for r in recs]
    min_d, max_d = min(fechas), max(fechas)
    bhash = core.batch_hash(recs)
    rep.rows, rep.min_date, rep.max_date = len(recs), str(min_d), str(max_d)
    rep.batch_hash = bhash

    # ---- C-MKT-005 duplicados de input ------------------------------------
    if norm.duplicates_dropped:
        sev = "INVALID" if norm.duplicates_conflicting else "WARNING"
        gate("C-MKT-005", sev,
             f"input con {norm.duplicates_dropped} fecha(s) duplicada(s), "
             f"{norm.duplicates_conflicting} con valores divergentes; "
             f"se conserva la ultima aparicion; ej={norm.duplicate_dates[:5]}")
    else:
        gate("C-MKT-005", "VALID", f"input sin fechas duplicadas ({len(recs)} ruedas)")

    # ---- C-MKT-006 moneda / mercado ---------------------------------------
    meta = res.metadata or {}
    cur_src = (meta.get("currency") or "").upper() or None
    exch_src = meta.get("exchangeName") or meta.get("fullExchangeName")
    if cur_src and spec.currency and cur_src != spec.currency.upper():
        gate("C-MKT-006", "INVALID",
             f"moneda divergente: esperada={spec.currency} fuente={cur_src} "
             f"(exchange fuente={exch_src})")
    elif cur_src:
        gate("C-MKT-006", "VALID",
             f"moneda={cur_src} coincide con market_instruments; exchange fuente={exch_src}")
    else:
        gate("C-MKT-006", "WARNING",
             f"la fuente no reporto moneda; se asume {spec.currency} de identidad")

    sym_src = meta.get("symbol")
    if sym_src and sym_src != spec.ticker_yahoo:
        gate("C-MKT-007", "INVALID",
             f"la fuente respondio simbolo {sym_src} para pedido {spec.ticker_yahoo}")

    # ---- C-MKT-008 fechas --------------------------------------------------
    sesiones = {r.trading_date: core.session_state(r.trading_date, market_tz, ts)
                for r in recs}
    futuras = [d for d, s in sesiones.items() if s == core.FUTURE]
    n_current = sum(1 for s in sesiones.values() if s == core.CURRENT)
    if futuras:
        gate("C-MKT-008", "INVALID",
             f"{len(futuras)} rueda(s) con fecha futura en tz {norm.tz}: {futuras[:5]}")
    else:
        gate("C-MKT-008", "VALID",
             f"tz_mercado={norm.tz} rango={min_d}..{max_d} "
             f"ruedas_finalizadas={len(recs) - n_current} rueda_en_curso={n_current}")

    # ---- C-MKT-009 nulos ---------------------------------------------------
    nulos = [r.trading_date for r in recs if None in (r.open, r.high, r.low, r.close)]
    sin_vol = sum(1 for r in recs if r.volume is None)
    if nulos:
        gate("C-MKT-009", "WARNING",
             f"{len(nulos)} rueda(s) con OHLC nulo; ej={nulos[:5]}; "
             f"volumen_nulo={sin_vol}")
    else:
        gate("C-MKT-009", "VALID", f"cero OHLC nulos; volumen_nulo={sin_vol}")

    # ---- C-MKT-004 coherencia OHLC ----------------------------------------
    viol = [(r.trading_date, core.ohlc_violations(r)) for r in recs]
    viol = [(d, v) for d, v in viol if v]
    if viol:
        # el payload viene asi de la fuente: se registra por fecha y se marca
        # WARNING (defecto upstream), no INVALID (no lo produjo el pipeline).
        gate("C-MKT-004", "WARNING",
             f"{len(viol)} rueda(s) con OHLC incoherente EN ORIGEN "
             f"(sha RAW {res.raw_bytes and core.sha256_hex(res.raw_bytes)[:12]}); "
             f"ej={[(str(d), ','.join(v)) for d, v in viol[:3]]}")
        for d, v in viol[:50]:
            cur.execute("""INSERT INTO market_data_quality
                (check_code, instrument_id, trading_date, severity, detail, run_id)
                VALUES ('C-MKT-004',%s,%s,'WARNING',%s,%s)""",
                        (iid, d, f"UPSTREAM_OHLC_DEFECT: {','.join(v)}", run_id))
    else:
        gate("C-MKT-004", "VALID", f"{len(recs)} ruedas con OHLC coherente")

    # ---- estado previo + fingerprints reconstruidos ------------------------
    existentes, mismatch = _reconstruir_existentes(cur, iid)
    if mismatch:
        gate("C-MKT-012", "INVALID",
             f"{len(mismatch)} fila(s) almacenadas cuyo full_hash NO se "
             f"reconstruye desde los valores persistidos; ej={mismatch[:5]}")
    else:
        gate("C-MKT-012", "VALID",
             f"{len(existentes)} fila(s) almacenadas: business_hash y full_hash "
             f"reconstruibles al 100% desde market_price_daily")

    # ---- cuarentena por regresion de cobertura -----------------------------
    if existentes and len(recs) < UMBRAL_COBERTURA * len(existentes):
        raw_dir, csv_bytes, raw_sha, _mb, meta_sha = _archivar_raw(
            iid, run_id, res,
            {"run_id": run_id, "ticker_yahoo": spec.ticker_yahoo, "params": params,
             "config_hash": config_hash, "batch_hash": bhash, "rows": len(recs),
             "min_date": str(min_d), "max_date": str(max_d),
             "source": source.name, "source_version": source.version,
             "fetched_at_utc": ts.isoformat(), "timezone_index": norm.tz,
             "history_metadata": meta, "quarantine": True})
        gate("C-MKT-003", "INVALID",
             f"CUARENTENA: payload {len(recs)} ruedas < {UMBRAL_COBERTURA:.0%} "
             f"de las {len(existentes)} almacenadas. RAW archivado en "
             f"{_rel(raw_dir)}; market_price_daily NO fue modificada")
        _registrar_run(cur, run_id, stage, spec, source, params, config_hash,
                       bhash, ts, norm.tz, len(recs), min_d, max_d,
                       len(csv_bytes), raw_sha, "PARTIAL", meta)
        _registrar_files(cur, run_id, raw_dir, csv_bytes, raw_sha, meta_sha)
        _cerrar_log(cur, run_id, "PARTIAL", len(recs), bytes_=len(csv_bytes),
                    first=min_d, last=max_d, sha=raw_sha,
                    error=("COVERAGE_REGRESSION",
                           f"{len(recs)} < {len(existentes)}"))
        conn.commit()
        rep.status = "QUARANTINED"
        rep.raw_sha256 = raw_sha
        rep.error = "regresion de cobertura"
        return rep

    # ---- RAW inmutable ------------------------------------------------------
    raw_dir, csv_bytes, raw_sha, _mb, meta_sha = _archivar_raw(
        iid, run_id, res,
        {"run_id": run_id, "ticker_yahoo": spec.ticker_yahoo, "params": params,
         "config_hash": config_hash, "batch_hash": bhash, "rows": len(recs),
         "min_date": str(min_d), "max_date": str(max_d),
         "source": source.name, "source_version": source.version,
         "fetched_at_utc": ts.isoformat(), "timezone_index": norm.tz,
         "history_metadata": meta})
    rep.raw_sha256 = raw_sha

    _registrar_run(cur, run_id, stage, spec, source, params, config_hash, bhash,
                   ts, norm.tz, len(recs), min_d, max_d, len(csv_bytes),
                   raw_sha, "SUCCESS", meta)
    _registrar_files(cur, run_id, raw_dir, csv_bytes, raw_sha, meta_sha)

    cur.execute("""SELECT run_id FROM market_raw_runs
        WHERE instrument_id=%s AND run_id<>%s AND status='SUCCESS'
        ORDER BY fetched_at_utc DESC, run_id DESC LIMIT 1""", (iid, run_id))
    pr = cur.fetchone()
    prev_run = pr[0] if pr else None

    # ---- DIFF: business_hash actual vs reconstruido -------------------------
    decisiones = core.classify_batch(recs, existentes, market_tz, ts)
    resumen = core.summarize(decisiones)
    rep.resumen = resumen

    por_fecha = {r.trading_date: r for r in recs}
    a_escribir = [por_fecha[d.trading_date] for d in decisiones if d.persist]

    if a_escribir:
        psycopg2.extras.execute_values(cur, """
            INSERT INTO market_price_daily
             (instrument_id, trading_date, open, high, low, close, adj_close,
              volume, dividends, stock_splits, currency, exchange,
              source_run_id, source_hash, fetched_at_utc)
            VALUES %s
            ON CONFLICT (instrument_id, trading_date) DO UPDATE SET
              open=EXCLUDED.open, high=EXCLUDED.high, low=EXCLUDED.low,
              close=EXCLUDED.close, adj_close=EXCLUDED.adj_close,
              volume=EXCLUDED.volume, dividends=EXCLUDED.dividends,
              stock_splits=EXCLUDED.stock_splits,
              currency=EXCLUDED.currency, exchange=EXCLUDED.exchange,
              source_run_id=EXCLUDED.source_run_id,
              source_hash=EXCLUDED.source_hash,
              fetched_at_utc=EXCLUDED.fetched_at_utc
        """, [(iid, r.trading_date, r.open, r.high, r.low, r.close, r.adj_close,
               r.volume, r.dividends, r.stock_splits, spec.currency,
               spec.exchange, run_id, r.full_hash, ts) for r in a_escribir],
            page_size=1000)

    # auditoria append-only: solo hechos (NEW/CHANGED). UNCHANGED se resume.
    audit = [d for d in decisiones if d.change_type in ("NEW", "CHANGED")]
    if audit:
        psycopg2.extras.execute_values(cur, """
            INSERT INTO market_data_changes
             (instrument_id, trading_date, change_type, old_hash, new_hash,
              old_value, new_value, reason, curr_run_id, prev_run_id)
            VALUES %s
        """, [(iid, d.trading_date, d.change_type, d.old_hash, d.new_hash,
               psycopg2.extras.Json(d.old_value) if d.old_value else None,
               psycopg2.extras.Json(d.new_value) if d.new_value else None,
               d.reason, run_id, prev_run) for d in audit], page_size=1000)

    # ruedas presentes en la base y ausentes en el payload -> MISSING (no borra)
    faltantes = sorted(set(existentes) - set(por_fecha))
    rep.faltantes = len(faltantes)
    if faltantes:
        psycopg2.extras.execute_values(cur, """
            INSERT INTO market_data_changes
             (instrument_id, trading_date, change_type, old_hash, reason,
              curr_run_id, prev_run_id)
            VALUES %s
        """, [(iid, d, "MISSING", existentes[d].full_hash,
               "AUSENTE_EN_PAYLOAD", run_id, prev_run)
              for d in faltantes[:500]], page_size=500)
        gate("C-MKT-003", "WARNING",
             f"{len(faltantes)} rueda(s) almacenadas ausentes en el payload "
             f"(no se borran); ej={[str(d) for d in faltantes[:5]]}")

    # ---- C-MKT-010 ruido de Adj Close --------------------------------------
    n_noise = resumen["por_motivo"].get(core.R_ADJ_NOISE, 0)
    if n_noise:
        gate("C-MKT-010", "VALID",
             f"{n_noise} rueda(s) con Adj Close dentro de tolerancia "
             f"{core.TOL_ADJ_REL:g} (recalculo float de la fuente): no se persisten")
    else:
        gate("C-MKT-010", "VALID", "sin ruido de Adj Close en esta corrida")

    # ---- C-MKT-013 idempotencia --------------------------------------------
    if not existentes:
        gate("C-MKT-013", "NOT_APPLICABLE",
             f"carga inicial: {len(recs)} ruedas NEW")
    elif resumen["idempotente"]:
        gate("C-MKT-013", "VALID",
             f"corrida idempotente: 0 filas escritas sobre {len(recs)} ruedas "
             f"(UNCHANGED={resumen['por_tipo'].get('UNCHANGED', 0)})")
    else:
        det = ", ".join(f"{k}={v}" for k, v in sorted(resumen["por_motivo"].items())
                        if k != "IDENTICAL")
        sev = "INVALID" if resumen["cambios_no_benignos"] else "VALID"
        gate("C-MKT-013", sev,
             f"{resumen['filas_escritas']} fila(s) escritas; motivos: {det}"
             + (f"; NO BENIGNOS en {resumen['fechas_no_benignas']}"
                if resumen["cambios_no_benignos"] else ""))

    # ---- C-MKT-016 corporate actions ---------------------------------------
    if norm.actions:
        psycopg2.extras.execute_values(cur, """
            INSERT INTO market_corporate_actions
             (instrument_id, action_date, action_type, value, ratio,
              source_hash, run_id)
            VALUES %s
            ON CONFLICT DO NOTHING
        """, [(iid, d, at, val, ratio, rh, run_id)
              for d, at, val, ratio, rh in norm.actions], page_size=500)
    cur.execute("""SELECT COUNT(*) FILTER (WHERE action_type='DIVIDEND'),
                          COUNT(*) FILTER (WHERE action_type='STOCK_SPLIT')
                   FROM market_corporate_actions WHERE instrument_id=%s""", (iid,))
    n_div, n_sp = cur.fetchone()
    div_serie = sum(1 for r in recs if r.dividends)
    sp_serie = sum(1 for r in recs if r.stock_splits)
    gate("C-MKT-016",
         "VALID" if (n_div == div_serie and n_sp == sp_serie) else "WARNING",
         f"acciones corporativas: serie div={div_serie} split={sp_serie} | "
         f"tabla div={n_div} split={n_sp}")

    # ---- snapshot (M8) ------------------------------------------------------
    if con_snapshot:
        try:
            snap = source.snapshot(spec.ticker_yahoo)
            num = {k: core.norm_num(snap.get(k)) for k in
                   ("last_price", "previous_close", "open", "day_high", "day_low",
                    "year_high", "year_low", "fifty_day_average",
                    "two_hundred_day_average")}
            cur.execute("""
                INSERT INTO market_snapshots
                 (instrument_id, ticker_yahoo, fetched_at_utc, last_price,
                  previous_close, open, day_high, day_low, volume, year_high,
                  year_low, fifty_day_average, two_hundred_day_average,
                  currency, exchange, timezone, payload_json)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (iid, spec.ticker_yahoo, ts, num["last_price"],
                  num["previous_close"], num["open"], num["day_high"],
                  num["day_low"], core.norm_vol(snap.get("volume")),
                  num["year_high"], num["year_low"], num["fifty_day_average"],
                  num["two_hundred_day_average"],
                  snap.get("currency") or spec.currency, spec.exchange, norm.tz,
                  psycopg2.extras.Json({k: (v if isinstance(v, (int, float, str, bool)) or v is None else str(v))
                                        for k, v in snap.items()})))
            gate("C-MKT-014", "VALID",
                 "snapshot persistido en market_snapshots (jamas en la serie historica)")
        except Exception as e:                          # noqa: BLE001
            gate("C-MKT-014", "WARNING", f"snapshot fallo: {str(e)[:150]}")
    else:
        gate("C-MKT-014", "NOT_APPLICABLE", "snapshot deshabilitado en esta corrida")

    # ---- C-MKT-017 provenance ----------------------------------------------
    cur.execute("""SELECT COUNT(*) FROM market_price_daily p
                   WHERE p.instrument_id=%s
                     AND NOT EXISTS (SELECT 1 FROM market_raw_runs r
                                     WHERE r.run_id=p.source_run_id)""", (iid,))
    huerfanas = cur.fetchone()[0]
    gate("C-MKT-017", "VALID" if huerfanas == 0 else "INVALID",
         f"filas sin corrida de origen registrada: {huerfanas}")

    sin_cambios = resumen["idempotente"]
    rep.status = "SIN_CAMBIOS" if sin_cambios else "SUCCESS"
    _cerrar_log(cur, run_id, rep.status, len(recs), bytes_=len(csv_bytes),
                first=min_d, last=max_d, sha=raw_sha,
                retry=max(res.attempts - 1, 0))
    conn.commit()
    return rep


def _registrar_run(cur, run_id, stage, spec, source, params, config_hash,
                   bhash, ts, tz, rows, min_d, max_d, nbytes, sha, status, meta):
    cur.execute("""
        INSERT INTO market_raw_runs
         (run_id, stage_run_id, entity_id, instrument_id, ticker_canonico,
          ticker_yahoo, source, source_version, request_parameters,
          query_start, query_end, interval, auto_adjust, actions,
          fetched_at_utc, timezone, currency, exchange,
          row_count, min_date, max_date, bytes, sha256, status)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (run_id) DO NOTHING
    """, (run_id, stage, spec.entity_id, str(spec.instrument_id),
          spec.ticker_canonico, spec.ticker_yahoo, source.name, source.version,
          psycopg2.extras.Json({**params, "config_hash": config_hash,
                                "batch_hash": bhash,
                                "history_metadata": meta}),
          str(min_d), str(max_d), params.get("interval", "1d"),
          bool(params.get("auto_adjust", False)), bool(params.get("actions", True)),
          ts, tz, spec.currency, spec.exchange, rows, min_d, max_d, nbytes,
          sha, status))


def _registrar_files(cur, run_id, raw_dir, csv_bytes, raw_sha, meta_sha):
    cur.execute("""INSERT INTO market_raw_files (run_id, kind, rel_path, bytes, sha256)
        VALUES (%s,'HISTORY_CSV',%s,%s,%s) ON CONFLICT (run_id, kind) DO NOTHING""",
                (run_id, _rel(raw_dir / "history.csv"), len(csv_bytes), raw_sha))
    mp = raw_dir / "meta.json"
    cur.execute("""INSERT INTO market_raw_files (run_id, kind, rel_path, bytes, sha256)
        VALUES (%s,'META_JSON',%s,%s,%s) ON CONFLICT (run_id, kind) DO NOTHING""",
                (run_id, _rel(mp), mp.stat().st_size, meta_sha))


def _cerrar_log(cur, run_id, status, rows, bytes_=None, first=None, last=None,
                sha=None, retry=0, error=(None, None)):
    cur.execute("""UPDATE market_fetch_log SET completed_at=now(), status=%s,
        rows_received=%s, bytes_received=%s, first_date=%s, last_date=%s,
        sha256=%s, retry_count=%s, error_type=%s, error_message=%s
        WHERE run_id=%s""",
                (status, rows, bytes_, first, last, sha, retry,
                 error[0], error[1], run_id))


# ------------------------------------------------------------------ batch

def cargar_specs(cur, instruments=None, limit=None):
    q = """SELECT m.instrument_id, m.entity_id, m.ticker_canonico,
                  s.ticker_yahoo, m.currency, m.exchange
           FROM market_instruments m
           JOIN market_symbol_mappings s USING (instrument_id)
           WHERE s.status='MAPPED'"""
    if instruments:
        want = [t.strip() for t in instruments]
        cur.execute(q + " AND s.ticker_yahoo = ANY(%s) ORDER BY m.instrument_id",
                    (want,))
    else:
        cur.execute(q + " ORDER BY m.instrument_id"
                    + ((" LIMIT %s" % int(limit)) if limit else ""))
    return [InstrumentSpec(*r) for r in cur.fetchall()]


def main():
    import time
    ap = argparse.ArgumentParser()
    ap.add_argument("--instruments", help="lista separada por comas de ticker_yahoo")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--stage", default="batch")
    ap.add_argument("--no-snapshot", action="store_true")
    ap.add_argument("--json-out", help="ruta donde volcar el reporte de la corrida")
    args = ap.parse_args()

    conn = pg_conn(write=True)          # escribe market_price_daily y raw runs
    cur = conn.cursor()
    specs = cargar_specs(cur, args.instruments.split(",") if args.instruments else None,
                         args.limit)
    cur.close()
    print(f"instrumentos a procesar: {len(specs)}")

    source = YahooSource()
    reportes = []
    for i, spec in enumerate(specs):
        rep = run_instrument(conn, spec, source, args.stage,
                             con_snapshot=not args.no_snapshot)
        reportes.append(rep)
        estado = rep.status
        det = ""
        if rep.resumen:
            det = (f" new={rep.resumen['por_tipo'].get('NEW', 0)}"
                   f" changed={rep.resumen['por_tipo'].get('CHANGED', 0)}"
                   f" unchanged={rep.resumen['por_tipo'].get('UNCHANGED', 0)}"
                   f" escritas={rep.resumen['filas_escritas']}")
        print(f"  [{spec.instrument_id}] {spec.ticker_yahoo:<10} {estado:<12} "
              f"{rep.rows} ruedas {rep.min_date}..{rep.max_date} "
              f"sha={(rep.raw_sha256 or '')[:10]}{det}"
              + (f"  ERROR {rep.error}" if rep.error else ""))
        malos = [g for g in rep.gates if g[1] == "INVALID"]
        for g in malos:
            print(f"      GATE {g[0]} INVALID: {g[2]}")
        if i < len(specs) - 1:
            time.sleep(SLEEP_BETWEEN)

    conn.close()
    if args.json_out:
        from dataclasses import asdict
        Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json_out).write_text(json.dumps(
            [asdict(r) for r in reportes], indent=2, default=str), encoding="utf-8")
        print(f"reporte -> {args.json_out}")
    fallidos = [r for r in reportes if r.status in ("FAILED", "QUARANTINED")]
    print(f"listo: {len(reportes) - len(fallidos)} ok / {len(fallidos)} con problema")
    return 1 if fallidos else 0


if __name__ == "__main__":
    raise SystemExit(main())
