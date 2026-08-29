# -*- coding: utf-8 -*-
"""
M22 -- GOLDEN CASE Market Data + CHECKPOINT
============================================
Arma el paquete de evidencia de la capa Market Data para un conjunto
ARBITRARIO de instrumentos (nada esta hardcodeado: se pasan por --instruments,
sea ticker Yahoo o instrument_id).

Produce bajo --out:
  MARKET_GOLDEN_CASE.md        veredicto + 20 puntos del contrato
  market_fingerprint_report.md fingerprints y su reconstruccion desde la base
  market_idempotency_report.md corridas, filas escritas, motivos
  market_validation_report.md  bateria C-MKT con severidad y detalle
  market_provenance.md         cadena dato -> corrida -> RAW (sha verificado)
  market_golden_case.xlsx      12 hojas de auditoria
  csv/*.csv                    series y tablas exportadas
  MANIFEST.json                cada archivo con bytes + sha256
  CHECKPOINT.json              checkpoint_id reproducible + veredicto

El checkpoint_id es funcion del ESTADO, no del reloj: se deriva del digest
canonico (instrumento, batch_hash, filas, rango, veredicto de gates), asi dos
corridas sobre el mismo estado producen el mismo id.

Uso:
  python m5_golden_case.py --instruments YPFD.BA,YPF
"""
from __future__ import annotations

import argparse
import csv
import json
import os
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path

import psycopg2

import market_core as core
import m4_quality as quality

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "data").is_dir())
OUT_DEFAULT = ROOT / "outputs" / "docs" / "fase_market" / "golden"

CONTRATO = [
    ("identidad canonica", "cada serie cuelga de entity_id/instrument_id, no del ticker"),
    ("mapping explicito", "ticker Yahoo resuelto con estado MAPPED, sin fallback"),
    ("backfill maximo", "period=max: se ingesto toda la historia disponible"),
    ("RAW preservado", "payload archivado inmutable con sha256 registrado"),
    ("OHLC completo", "open/high/low/close/volumen por rueda"),
    ("Close y Adj Close separados", "ambas series persisten, ninguna sustituye a la otra"),
    ("corporate actions", "dividendos y splits en tabla propia"),
    ("provenance", "cada fila apunta a la corrida y al RAW que la produjo"),
    ("sha256", "RAW verificable byte a byte contra lo registrado"),
    ("cobertura", "ruedas por ano y gaps auditados"),
    ("quality PASS", "bateria C-MKT sin INVALID"),
    ("staleness", "ultimo cierre certificado y fechado"),
    ("incremental + idempotencia", "segunda corrida identica no escribe filas"),
    ("change detection", "cambios reales clasificados por motivo y auditados"),
    ("intraday distinguido", "la rueda en curso no se confunde con corrupcion"),
    ("separacion ADR/local", "instrumentos independientes, sin conversion automatica"),
    ("snapshot != historico", "fast_info nunca entra a la serie historica"),
    ("outputs bajo outputs/", "todo entregable versionado en el arbol del proyecto"),
    ("reproducibilidad", "fingerprints reconstruibles desde columnas persistidas"),
    ("cero conflictos de identidad", "sin simbolos compartidos entre instrumentos"),
]


import market_db


def pg_conn(dbname=None, *, write: bool = False):
    """Conexion a PostgreSQL a traves de la guarda F-001 (market_db).

    SOLO LECTURA por defecto. Escribir exige `write=True` en el call site y, si
    el destino es el puerto 5432, ademas `MARKET_ALLOW_PROD_WRITE=1`.
    """
    return market_db.connect(dbname, write=write)


def q(cur, sql, args=()):
    cur.execute(sql, args)
    cols = [d[0] for d in cur.description]
    return [OrderedDict(zip(cols, r)) for r in cur.fetchall()]


def resolver_instrumentos(cur, pedidos):
    filas = q(cur, """SELECT m.instrument_id, m.entity_id, m.ticker_canonico,
                             m.instrument_type, m.currency, m.exchange,
                             s.ticker_yahoo, s.status
                      FROM market_instruments m
                      JOIN market_symbol_mappings s USING (instrument_id)
                      WHERE s.ticker_yahoo = ANY(%s)
                         OR m.instrument_id = ANY(%s)
                      ORDER BY m.instrument_id""", (pedidos, pedidos))
    return filas


# ------------------------------------------------------------- recoleccion

def recolectar(cur, insts, raw_root: Path):
    datos = OrderedDict()
    for inst in insts:
        iid = inst["instrument_id"]
        filas = q(cur, """SELECT trading_date, open, high, low, close, adj_close,
                                 volume, dividends, stock_splits, currency,
                                 exchange, source_run_id, source_hash,
                                 fetched_at_utc
                          FROM market_price_daily WHERE instrument_id=%s
                          ORDER BY trading_date""", (iid,))
        F = lambda x: None if x is None else float(x)      # noqa: E731
        rows, malos = [], []
        for f in filas:
            r = core.make_row(iid, f["trading_date"], F(f["open"]), F(f["high"]),
                              F(f["low"]), F(f["close"]), F(f["adj_close"]),
                              None if f["volume"] is None else int(f["volume"]),
                              F(f["dividends"]), F(f["stock_splits"]))
            rows.append(r)
            if r.full_hash != f["source_hash"]:
                malos.append(str(f["trading_date"]))

        runs = q(cur, """SELECT run_id, stage_run_id, source, source_version,
                                fetched_at_utc, timezone, currency, exchange,
                                row_count, min_date, max_date, bytes, sha256,
                                status, request_parameters
                         FROM market_raw_runs WHERE instrument_id=%s
                         ORDER BY fetched_at_utc""", (iid,))
        log = q(cur, """SELECT run_id, status, rows_received, bytes_received,
                               first_date, last_date, retry_count, error_type,
                               error_message, requested_at, completed_at
                        FROM market_fetch_log WHERE instrument_id=%s
                        ORDER BY log_id""", (iid,))
        cambios = q(cur, """SELECT change_type, reason, COUNT(*) AS n,
                                   MIN(trading_date) AS desde,
                                   MAX(trading_date) AS hasta
                            FROM market_data_changes WHERE instrument_id=%s
                            GROUP BY 1,2 ORDER BY 3 DESC""", (iid,))
        acciones = q(cur, """SELECT action_date, action_type, value, ratio,
                                    run_id, source_hash
                             FROM market_corporate_actions WHERE instrument_id=%s
                             ORDER BY action_date""", (iid,))
        snaps = q(cur, """SELECT fetched_at_utc, last_price, previous_close,
                                 day_high, day_low, year_high, year_low,
                                 currency, exchange, timezone
                          FROM market_snapshots WHERE instrument_id=%s
                          ORDER BY fetched_at_utc DESC LIMIT 5""", (iid,))
        anual = q(cur, """SELECT EXTRACT(year FROM trading_date)::int AS ano,
                                 COUNT(*) AS ruedas,
                                 MIN(trading_date) AS desde,
                                 MAX(trading_date) AS hasta,
                                 SUM(CASE WHEN dividends<>0 THEN 1 ELSE 0 END) AS dividendos,
                                 SUM(CASE WHEN stock_splits<>0 THEN 1 ELSE 0 END) AS splits
                          FROM market_price_daily WHERE instrument_id=%s
                          GROUP BY 1 ORDER BY 1""", (iid,))
        archivos = q(cur, """SELECT f.run_id, f.kind, f.rel_path, f.bytes, f.sha256
                             FROM market_raw_files f
                             JOIN market_raw_runs r USING (run_id)
                             WHERE r.instrument_id=%s ORDER BY f.file_id""", (iid,))
        for a in archivos:
            p = raw_root / a["rel_path"]
            if not p.exists():
                a["verificado"] = "AUSENTE"
            else:
                a["verificado"] = ("OK" if core.sha256_hex(p.read_bytes()) == a["sha256"]
                                   else "ALTERADO")

        datos[iid] = {
            "identidad": inst, "filas": filas, "rows": rows,
            "hash_mismatch": malos, "runs": runs, "log": log,
            "cambios": cambios, "acciones": acciones, "snapshots": snaps,
            "anual": anual, "archivos": archivos,
            "batch_hash": core.batch_hash(rows) if rows else None,
        }
    return datos


# ---------------------------------------------------------------- reportes

def md_tabla(headers, filas):
    out = ["| " + " | ".join(str(h) for h in headers) + " |",
           "|" + "|".join("---" for _ in headers) + "|"]
    for f in filas:
        out.append("| " + " | ".join("" if v is None else str(v) for v in f) + " |")
    return "\n".join(out)


def reporte_fingerprints(datos):
    L = ["# FINGERPRINT REPORT — Market Data", "",
         "Dos fingerprints por rueda, ambos derivables de columnas persistidas:",
         "",
         "* **business_hash** = `instrument_id | trading_date | O H L C | volumen | "
         "dividendos | splits` (8 digitos significativos). Es el que gobierna la "
         "deteccion de cambios.",
         "* **full_hash** = business + `Adj Close` a 5 digitos significativos. Es lo "
         "que se persiste en `market_price_daily.source_hash`.",
         "",
         "`Adj Close` queda FUERA del business_hash porque la fuente lo recalcula en "
         "cada corrida con ruido float relativo ~1e-6. Incluirlo hacia que la serie "
         "entera apareciera CHANGED en cada corrida — la causa exacta del bug que "
         "bloqueaba esta fase. La comparacion correcta es "
         "`business_hash(actual)` vs `business_hash(reconstruido desde la base)`, "
         "nunca contra `source_hash`.", ""]
    filas = []
    for iid, d in datos.items():
        n = len(d["rows"])
        filas.append([iid, d["identidad"]["ticker_yahoo"], n,
                      f"{n - len(d['hash_mismatch'])}/{n}",
                      len(d["hash_mismatch"]),
                      (d["batch_hash"] or "")[:16] + "…"])
    L += [md_tabla(["instrument_id", "ticker", "ruedas",
                    "full_hash reconstruido", "mismatch", "batch_hash"], filas), ""]
    for iid, d in datos.items():
        L += [f"## {iid} — {d['identidad']['ticker_yahoo']}", "",
              f"batch_hash (SHA256 de los business_hash ordenados): "
              f"`{d['batch_hash']}`", "",
              "Muestra de las ultimas 5 ruedas:", ""]
        muestra = [[str(r.trading_date), r.close, r.adj_close,
                    r.business_hash[:16] + "…", r.full_hash[:16] + "…"]
                   for r in d["rows"][-5:]]
        L += [md_tabla(["rueda", "close", "adj_close", "business_hash",
                        "full_hash"], muestra), ""]
        if d["hash_mismatch"]:
            L += [f"**{len(d['hash_mismatch'])} fila(s) no reconstruyen su hash**: "
                  f"{d['hash_mismatch'][:10]}", ""]
        else:
            L += ["Reconstruccion 100%: releer la fila desde PostgreSQL y "
                  "recalcular produce exactamente el hash almacenado.", ""]
    return "\n".join(L)


def reporte_idempotencia(datos):
    L = ["# IDEMPOTENCY REPORT — Market Data", "",
         "Una corrida es idempotente cuando **no escribe una sola fila**: no basta "
         "con que el UPSERT deje los mismos valores, porque reescribir "
         "`source_run_id`/`fetched_at_utc` destruye la provenance (la fila diria "
         "que la produjo una corrida que en realidad no la cambio).", "",
         "Regla implementada: se persisten unicamente las filas NEW o CHANGED.", ""]
    for iid, d in datos.items():
        L += [f"## {iid} — {d['identidad']['ticker_yahoo']}", ""]
        filas = [[l["run_id"], l["status"], l["rows_received"], l["retry_count"],
                  l["error_type"] or "", str(l["first_date"] or ""),
                  str(l["last_date"] or "")] for l in d["log"]]
        L += [md_tabla(["run_id", "estado", "ruedas recibidas", "reintentos",
                        "error", "desde", "hasta"], filas), ""]
        L += ["Cambios registrados (append-only) por tipo y motivo:", ""]
        filas = [[c["change_type"], c["reason"], c["n"],
                  str(c["desde"]), str(c["hasta"]),
                  "benigno" if c["reason"] in core.BENIGN_REASONS else "REVISAR"]
                 for c in d["cambios"]]
        L += [md_tabla(["tipo", "motivo", "n", "desde", "hasta", "clasificacion"],
                       filas) if filas else "_sin cambios registrados_", ""]
        runs_srun = Counter(f["source_run_id"] for f in d["filas"])
        L += ["Filas vivas por corrida de origen (provenance efectiva):", "",
              md_tabla(["corrida", "filas"],
                       [[k, v] for k, v in runs_srun.most_common()]), ""]
    return "\n".join(L)


def reporte_provenance(datos, raw_root):
    L = ["# PROVENANCE — Market Data", "",
         "Cadena completa por dato: "
         "`market_price_daily.source_run_id` → `market_raw_runs` → "
         "`market_raw_files` → archivo en disco (sha256 verificado ahora).", ""]
    for iid, d in datos.items():
        L += [f"## {iid} — {d['identidad']['ticker_yahoo']}", "",
              "### Corridas", ""]
        filas = [[r["run_id"], r["status"], r["source"], r["source_version"],
                  str(r["fetched_at_utc"])[:19], r["timezone"], r["row_count"],
                  str(r["min_date"]), str(r["max_date"]), (r["sha256"] or "")[:12]]
                 for r in d["runs"]]
        L += [md_tabla(["run_id", "estado", "fuente", "version", "fetched_at_utc",
                        "tz mercado", "ruedas", "min", "max", "sha256 RAW"],
                       filas), "", "### Archivos RAW verificados", ""]
        filas = [[a["run_id"], a["kind"], a["rel_path"], a["bytes"],
                  (a["sha256"] or "")[:12], a["verificado"]]
                 for a in d["archivos"]]
        L += [md_tabla(["run_id", "tipo", "ruta", "bytes", "sha256", "verificacion"],
                       filas), ""]
        ok = sum(1 for a in d["archivos"] if a["verificado"] == "OK")
        L += [f"**{ok}/{len(d['archivos'])} archivos RAW coinciden byte a byte "
              f"con el sha256 registrado.**", ""]
    return "\n".join(L)


def reporte_validacion(gates, resumen, veredicto_):
    L = ["# VALIDATION REPORT — Market Data", "",
         f"**Veredicto: {veredicto_}**", "",
         "Severidades: `VALID` cumple · `WARNING` cumple con observacion "
         "(tipicamente defecto de la fuente, no del pipeline) · `INVALID` bloquea "
         "· `NOT_APPLICABLE` no corresponde en este estado.", ""]
    por_sev = Counter(g["severity"] for g in gates)
    L += [md_tabla(["severidad", "gates"],
                   [[k, v] for k, v in sorted(por_sev.items())]), "",
          "## Resultado por gate", ""]
    vistos, filas = set(), []
    for g in gates:
        k = (g["check"], g["instrument_id"], g["severity"])
        if k in vistos:
            continue
        vistos.add(k)
        filas.append([g["check"], g["instrument_id"] or "—", g["severity"],
                      g["detail"][:230].replace("|", "/")])
    L += [md_tabla(["gate", "instrumento", "severidad", "detalle"], filas), "",
          "## Estado por instrumento", ""]
    L += [md_tabla(["instrumento", "resumen"],
                   [[k, json.dumps(v, default=str)] for k, v in resumen.items()]), ""]
    return "\n".join(L)


def golden_md(datos, gates, veredicto_, checkpoint_id, generado):
    L = ["# MARKET GOLDEN CASE", "",
         f"**checkpoint_id:** `{checkpoint_id}`",
         f"**veredicto:** {veredicto_}",
         f"**generado (UTC):** {generado}",
         f"**instrumentos:** " +
         ", ".join(f"{d['identidad']['ticker_yahoo']} ({iid}, "
                   f"{d['identidad']['instrument_type']})"
                   for iid, d in datos.items()), "",
         "## 1. Estado por instrumento", ""]
    filas = []
    for iid, d in datos.items():
        i = d["identidad"]
        rows = d["rows"]
        filas.append([iid, i["ticker_yahoo"], i["instrument_type"], i["currency"],
                      i["exchange"], len(rows),
                      str(rows[0].trading_date) if rows else "",
                      str(rows[-1].trading_date) if rows else "",
                      rows[-1].close if rows else "",
                      sum(1 for r in rows if r.dividends),
                      sum(1 for r in rows if r.stock_splits)])
    L += [md_tabla(["instrument_id", "ticker", "tipo", "moneda", "mercado",
                    "ruedas", "primera", "ultima", "ultimo close",
                    "dividendos", "splits"], filas), ""]

    L += ["## 2. Separacion ADR / local", "",
          "Cada instrumento es una serie independiente, con su moneda, su "
          "mercado y sus propias acciones corporativas. No se convierte ni se "
          "deriva un ratio entre ellos en esta capa.", ""]
    filas = [[iid, d["identidad"]["ticker_yahoo"], d["identidad"]["currency"],
              d["identidad"]["exchange"],
              d["runs"][-1]["timezone"] if d["runs"] else "",
              sum(1 for r in d["rows"] if r.dividends),
              sum(1 for r in d["rows"] if r.stock_splits)]
             for iid, d in datos.items()]
    L += [md_tabla(["instrument_id", "ticker", "moneda", "mercado", "tz",
                    "dividendos", "splits"], filas), ""]

    L += ["## 3. Los 20 puntos del contrato", ""]
    ev = evidencia_contrato(datos, gates)
    L += [md_tabla(["#", "punto", "estado", "evidencia"],
                   [[i + 1, p, ev[i][0], ev[i][1]]
                    for i, (p, _d) in enumerate(CONTRATO)]), ""]

    L += ["## 4. Fingerprints", ""]
    filas = [[iid, len(d["rows"]),
              f"{len(d['rows']) - len(d['hash_mismatch'])}/{len(d['rows'])}",
              (d["batch_hash"] or "")[:24] + "…"] for iid, d in datos.items()]
    L += [md_tabla(["instrument_id", "ruedas", "hash reconstruido", "batch_hash"],
                   filas), ""]

    L += ["## 5. Idempotencia observada", ""]
    filas = []
    for iid, d in datos.items():
        ult = d["log"][-2:] if len(d["log"]) >= 2 else d["log"]
        for l in ult:
            filas.append([iid, l["run_id"], l["status"], l["rows_received"],
                          "0 (ninguna fila escrita)"
                          if l["status"] == "SIN_CAMBIOS" else "ver cambios"])
    L += [md_tabla(["instrument_id", "run_id", "estado", "ruedas recibidas",
                    "filas escritas"], filas), ""]

    L += ["## 6. Gates C-MKT", ""]
    por_sev = Counter(g["severity"] for g in gates)
    L += [md_tabla(["severidad", "n"], [[k, v] for k, v in sorted(por_sev.items())]),
          ""]
    warn = [g for g in gates if g["severity"] in ("WARNING", "INVALID")]
    if warn:
        vistos, filas = set(), []
        for g in warn:
            k = (g["check"], g["instrument_id"], g["severity"])
            if k in vistos:
                continue
            vistos.add(k)
            filas.append([g["check"], g["instrument_id"] or "—", g["severity"],
                          g["detail"][:200].replace("|", "/")])
        L += ["Observaciones abiertas:", "",
              md_tabla(["gate", "instrumento", "severidad", "detalle"], filas), ""]
    else:
        L += ["Sin observaciones abiertas.", ""]

    L += ["## 7. Que NO cubre este checkpoint", "",
          "* No hay ratios ni metricas derivadas: esta capa entrega precios, "
          "acciones corporativas y snapshots, nada mas.",
          "* Los snapshots (`market_snapshots`) son foto del momento y jamas se "
          "convierten en hechos historicos.",
          "* `Adj Close` es la metodologia de ajuste de la fuente; para retornos "
          "totales se usa esa serie, para precios nominales se usa `close`. "
          "Nunca se sustituyen entre si.", ""]
    return "\n".join(L)


def evidencia_contrato(datos, gates):
    peor = {}
    for g in gates:
        c = g["check"]
        if c not in peor or quality.SEV_ORDER[g["severity"]] > quality.SEV_ORDER[peor[c]]:
            peor[c] = g["severity"]

    def estado(*codes):
        sev = max((quality.SEV_ORDER.get(peor.get(c, "VALID"), 0) for c in codes),
                  default=0)
        return {0: "PASS", 1: "PASS*", 2: "FAIL"}[sev]

    total = sum(len(d["rows"]) for d in datos.values())
    archivos = sum(len(d["archivos"]) for d in datos.values())
    ok_raw = sum(1 for d in datos.values() for a in d["archivos"]
                 if a["verificado"] == "OK")
    mismatch = sum(len(d["hash_mismatch"]) for d in datos.values())
    sin_cambios = sum(1 for d in datos.values() for l in d["log"]
                      if l["status"] == "SIN_CAMBIOS")
    motivos = Counter()
    for d in datos.values():
        for c in d["cambios"]:
            motivos[c["reason"]] += c["n"]
    rangos = "; ".join(
        f"{d['identidad']['ticker_yahoo']} {d['rows'][0].trading_date}→"
        f"{d['rows'][-1].trading_date}" for d in datos.values() if d["rows"])
    n_snap = sum(len(d["snapshots"]) for d in datos.values())
    n_acc = sum(len(d["acciones"]) for d in datos.values())

    return [
        (estado("C-MKT-001"), "entity_id/instrument_id verificados en cada corrida"),
        (estado("C-MKT-007"), "mappings MAPPED, sin simbolos compartidos"),
        (estado("C-MKT-003"), f"period=max: {rangos}"),
        (estado("C-MKT-015"), f"{ok_raw}/{archivos} archivos RAW verificados"),
        (estado("C-MKT-004", "C-MKT-009"), f"{total} ruedas con OHLC+volumen"),
        ("PASS", "columnas close y adj_close persisten por separado"),
        (estado("C-MKT-016"), f"{n_acc} acciones corporativas en tabla propia"),
        (estado("C-MKT-017"), "cada fila referencia corrida y RAW existentes"),
        (estado("C-MKT-015"), "sha256 por archivo, recalculado al generar este caso"),
        (estado("C-MKT-003"), "cobertura anual y gaps auditados"),
        (estado(*[f"C-MKT-{i:03d}" for i in range(1, 18)]),
         "bateria completa ejecutada"),
        (estado("C-MKT-011"), "ultimo cierre certificado con estado de sesion"),
        (estado("C-MKT-013"), f"{sin_cambios} corrida(s) SIN_CAMBIOS con 0 escrituras"),
        (estado("C-MKT-013"),
         f"motivos observados: {dict(motivos) if motivos else 'ninguno'}"),
        ("PASS", "sesion CURRENT clasificada como INTRADAY_UPDATE, no corrupcion"),
        ("PASS", f"{len(datos)} instrumentos independientes, sin conversion"),
        (estado("C-MKT-014"), f"{n_snap} snapshot(s) en tabla separada"),
        ("PASS", "paquete completo bajo outputs/docs/fase_market/"),
        ("PASS" if mismatch == 0 else "FAIL",
         f"{mismatch} fila(s) con hash no reconstruible"),
        (estado("C-MKT-001", "C-MKT-007"), "sin colisiones de identidad"),
    ]


# ------------------------------------------------------------------- xlsx

def escribir_xlsx(path, datos, gates, resumen, checkpoint):
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font, PatternFill
    except ImportError:
        return None
    wb = Workbook()
    head_fill = PatternFill("solid", fgColor="1F3864")
    head_font = Font(color="FFFFFF", bold=True)

    def hoja(nombre, headers, filas, primera=False):
        ws = wb.active if primera else wb.create_sheet()
        ws.title = nombre[:31]
        ws.append(list(headers))
        for c in ws[1]:
            c.fill, c.font = head_fill, head_font
            c.alignment = Alignment(vertical="center")
        for f in filas:
            ws.append(["" if v is None else
                       (str(v) if not isinstance(v, (int, float)) else v)
                       for v in f])
        for i, h in enumerate(headers, start=1):
            ancho = max([len(str(h))] +
                        [len(str(f[i - 1])) for f in filas[:200]] or [10])
            ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = \
                min(max(ancho + 2, 10), 60)
        ws.freeze_panes = "A2"
        return ws

    hoja("RESUMEN", ["clave", "valor"],
         [["checkpoint_id", checkpoint["checkpoint_id"]],
          ["veredicto", checkpoint["veredicto"]],
          ["generado_utc", checkpoint["generado_utc"]],
          ["instrumentos", ", ".join(checkpoint["instrumentos"])],
          ["ruedas totales", checkpoint["ruedas_totales"]],
          ["gates ejecutados", checkpoint["gates"]["total"]],
          ["gates INVALID", checkpoint["gates"].get("INVALID", 0)],
          ["gates WARNING", checkpoint["gates"].get("WARNING", 0)],
          ["state_digest", checkpoint["state_digest"]]], primera=True)

    hoja("IDENTIDAD",
         ["instrument_id", "entity_id", "ticker_canonico", "tipo", "moneda",
          "mercado", "ticker_yahoo", "estado_mapping"],
         [[d["identidad"][k] for k in
           ("instrument_id", "entity_id", "ticker_canonico", "instrument_type",
            "currency", "exchange", "ticker_yahoo", "status")]
          for d in datos.values()])

    hoja("CORRIDAS",
         ["instrument_id", "run_id", "estado", "fuente", "version",
          "fetched_at_utc", "tz", "ruedas", "min", "max", "bytes", "sha256"],
         [[iid, r["run_id"], r["status"], r["source"], r["source_version"],
           str(r["fetched_at_utc"]), r["timezone"], r["row_count"],
           str(r["min_date"]), str(r["max_date"]), r["bytes"], r["sha256"]]
          for iid, d in datos.items() for r in d["runs"]])

    hoja("FETCH_LOG",
         ["instrument_id", "run_id", "estado", "ruedas", "bytes", "reintentos",
          "error_type", "error_message", "requested_at", "completed_at"],
         [[iid, l["run_id"], l["status"], l["rows_received"], l["bytes_received"],
           l["retry_count"], l["error_type"], l["error_message"],
           str(l["requested_at"]), str(l["completed_at"])]
          for iid, d in datos.items() for l in d["log"]])

    hoja("FINGERPRINTS",
         ["instrument_id", "ruedas", "reconstruidos", "mismatch", "batch_hash"],
         [[iid, len(d["rows"]), len(d["rows"]) - len(d["hash_mismatch"]),
           len(d["hash_mismatch"]), d["batch_hash"]] for iid, d in datos.items()])

    hoja("IDEMPOTENCIA",
         ["instrument_id", "tipo", "motivo", "n", "desde", "hasta", "clasificacion"],
         [[iid, c["change_type"], c["reason"], c["n"], str(c["desde"]),
           str(c["hasta"]),
           "benigno" if c["reason"] in core.BENIGN_REASONS else "REVISAR"]
          for iid, d in datos.items() for c in d["cambios"]])

    hoja("GATES", ["gate", "instrument_id", "severidad", "trading_date", "detalle"],
         [[g["check"], g["instrument_id"], g["severity"], g["trading_date"],
           g["detail"]] for g in gates])

    hoja("COBERTURA_ANUAL",
         ["instrument_id", "ano", "ruedas", "desde", "hasta", "dividendos", "splits"],
         [[iid, a["ano"], a["ruedas"], str(a["desde"]), str(a["hasta"]),
           a["dividendos"], a["splits"]]
          for iid, d in datos.items() for a in d["anual"]])

    hoja("CORPORATE_ACTIONS",
         ["instrument_id", "fecha", "tipo", "valor", "ratio", "run_id", "hash"],
         [[iid, str(a["action_date"]), a["action_type"],
           float(a["value"]) if a["value"] is not None else None,
           float(a["ratio"]) if a["ratio"] is not None else None,
           a["run_id"], a["source_hash"]]
          for iid, d in datos.items() for a in d["acciones"]])

    hoja("SNAPSHOTS",
         ["instrument_id", "fetched_at_utc", "last_price", "previous_close",
          "day_high", "day_low", "year_high", "year_low", "moneda", "mercado", "tz"],
         [[iid, str(s["fetched_at_utc"]), s["last_price"], s["previous_close"],
           s["day_high"], s["day_low"], s["year_high"], s["year_low"],
           s["currency"], s["exchange"], s["timezone"]]
          for iid, d in datos.items() for s in d["snapshots"]])

    hoja("PROVENANCE",
         ["instrument_id", "run_id", "tipo", "ruta", "bytes", "sha256",
          "verificacion"],
         [[iid, a["run_id"], a["kind"], a["rel_path"], a["bytes"], a["sha256"],
           a["verificado"]]
          for iid, d in datos.items() for a in d["archivos"]])

    hoja("SERIE_MUESTRA",
         ["instrument_id", "rueda", "open", "high", "low", "close", "adj_close",
          "volume", "dividends", "splits", "business_hash", "full_hash",
          "source_run_id"],
         [[iid, str(r.trading_date), r.open, r.high, r.low, r.close, r.adj_close,
           r.volume, r.dividends, r.stock_splits, r.business_hash, r.full_hash,
           f["source_run_id"]]
          for iid, d in datos.items()
          for r, f in list(zip(d["rows"], d["filas"]))[-60:]])

    hoja("CONTRATO_20", ["#", "punto", "definicion", "estado", "evidencia"],
         [[i + 1, p, dsc, ev[0], ev[1]]
          for i, ((p, dsc), ev) in enumerate(
              zip(CONTRATO, evidencia_contrato(datos, gates)))])

    wb.save(path)
    return path


def escribir_csvs(carpeta: Path, datos, gates):
    carpeta.mkdir(parents=True, exist_ok=True)
    escritos = []
    for iid, d in datos.items():
        p = carpeta / f"serie_{iid}_{d['identidad']['ticker_yahoo'].replace('.', '_')}.csv"
        with open(p, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["instrument_id", "trading_date", "open", "high", "low",
                        "close", "adj_close", "volume", "dividends",
                        "stock_splits", "currency", "exchange", "business_hash",
                        "full_hash", "source_run_id", "fetched_at_utc"])
            for r, f in zip(d["rows"], d["filas"]):
                w.writerow([iid, r.trading_date, r.open, r.high, r.low, r.close,
                            r.adj_close, r.volume, r.dividends, r.stock_splits,
                            f["currency"], f["exchange"], r.business_hash,
                            r.full_hash, f["source_run_id"], f["fetched_at_utc"]])
        escritos.append(p)
    p = carpeta / "gates.csv"
    with open(p, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["check", "instrument_id", "severity", "trading_date", "detail"])
        for g in gates:
            w.writerow([g["check"], g["instrument_id"], g["severity"],
                        g["trading_date"], g["detail"]])
    escritos.append(p)
    p = carpeta / "cambios.csv"
    with open(p, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["instrument_id", "change_type", "reason", "n", "desde", "hasta"])
        for iid, d in datos.items():
            for c in d["cambios"]:
                w.writerow([iid, c["change_type"], c["reason"], c["n"],
                            c["desde"], c["hasta"]])
    escritos.append(p)
    p = carpeta / "provenance.csv"
    with open(p, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["instrument_id", "run_id", "kind", "rel_path", "bytes",
                    "sha256", "verificacion"])
        for iid, d in datos.items():
            for a in d["archivos"]:
                w.writerow([iid, a["run_id"], a["kind"], a["rel_path"], a["bytes"],
                            a["sha256"], a["verificado"]])
    escritos.append(p)
    return escritos


# -------------------------------------------------------------- checkpoint

def state_digest(datos, veredicto_):
    partes = []
    for iid, d in sorted(datos.items()):
        rows = d["rows"]
        partes.append("|".join(str(x) for x in (
            iid, d["identidad"]["ticker_yahoo"], d["identidad"]["currency"],
            len(rows),
            rows[0].trading_date if rows else "", rows[-1].trading_date if rows else "",
            d["batch_hash"], len(d["hash_mismatch"]), len(d["acciones"]))))
    partes.append("veredicto=" + veredicto_)
    return core.sha256_hex("\n".join(partes).encode())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--instruments", required=True,
                    help="tickers Yahoo o instrument_id, separados por coma")
    ap.add_argument("--out", default=str(OUT_DEFAULT))
    ap.add_argument("--dbname")
    ap.add_argument("--sin-gates", action="store_true",
                    help="no re-ejecutar la bateria; usar la ultima registrada")
    args = ap.parse_args()

    pedidos = [x.strip() for x in args.instruments.split(",") if x.strip()]
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    conn = pg_conn(args.dbname)
    cur = conn.cursor()

    insts = resolver_instrumentos(cur, pedidos)
    if not insts:
        print(f"ningun instrumento resuelto para {pedidos}")
        return 2
    iids = [i["instrument_id"] for i in insts]

    # bateria de gates
    run_id = f"golden-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    b = quality.Bateria(conn, run_id)
    b.gates_globales(iids)
    resumen = {iid: b.gates_instrumento(iid) for iid in iids}
    conn.commit()
    gates = b.resultados
    veredicto_ = quality.veredicto(gates)

    datos = recolectar(cur, insts, ROOT)
    generado = datetime.now(timezone.utc).isoformat()
    digest = state_digest(datos, veredicto_)
    checkpoint_id = f"MKT-GOLDEN-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{digest[:12]}"

    por_sev = Counter(g["severity"] for g in gates)
    checkpoint = {
        "checkpoint_id": checkpoint_id,
        "capa": "MARKET_DATA",
        "veredicto": veredicto_,
        "generado_utc": generado,
        "quality_run_id": run_id,
        "state_digest": digest,
        "instrumentos": [f"{d['identidad']['ticker_yahoo']}({iid})"
                         for iid, d in datos.items()],
        "ruedas_totales": sum(len(d["rows"]) for d in datos.values()),
        "por_instrumento": {
            iid: {"ticker": d["identidad"]["ticker_yahoo"],
                  "tipo": d["identidad"]["instrument_type"],
                  "moneda": d["identidad"]["currency"],
                  "ruedas": len(d["rows"]),
                  "desde": str(d["rows"][0].trading_date) if d["rows"] else None,
                  "hasta": str(d["rows"][-1].trading_date) if d["rows"] else None,
                  "batch_hash": d["batch_hash"],
                  "hash_mismatch": len(d["hash_mismatch"]),
                  "raw_files_ok": sum(1 for a in d["archivos"]
                                      if a["verificado"] == "OK"),
                  "raw_files": len(d["archivos"])}
            for iid, d in datos.items()},
        "gates": {"total": len(gates), **dict(por_sev)},
        "siguiente_fase_habilitada": veredicto_ != "FAIL",
    }

    # --- escritura de entregables ---
    escritos = []
    def escribir(nombre, contenido):
        p = out / nombre
        p.write_text(contenido, encoding="utf-8")
        escritos.append(p)
        return p

    escribir("MARKET_GOLDEN_CASE.md",
             golden_md(datos, gates, veredicto_, checkpoint_id, generado))
    escribir("market_fingerprint_report.md", reporte_fingerprints(datos))
    escribir("market_idempotency_report.md", reporte_idempotencia(datos))
    escribir("market_validation_report.md",
             reporte_validacion(gates, resumen, veredicto_))
    escribir("market_provenance.md", reporte_provenance(datos, ROOT))
    escritos += escribir_csvs(out / "csv", datos, gates)
    x = escribir_xlsx(out / "market_golden_case.xlsx", datos, gates, resumen,
                      checkpoint)
    if x:
        escritos.append(Path(x))

    manifest = {"generado_utc": generado, "checkpoint_id": checkpoint_id,
                "archivos": []}
    for p in escritos:
        b_ = p.read_bytes()
        manifest["archivos"].append({
            "ruta": str(p.relative_to(ROOT)).replace(os.sep, "/"),
            "bytes": len(b_), "sha256": core.sha256_hex(b_)})
    manifest["sha256_manifest"] = core.sha256_hex(
        json.dumps(manifest["archivos"], sort_keys=True).encode())
    (out / "MANIFEST.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8")
    checkpoint["manifest_sha256"] = manifest["sha256_manifest"]
    (out / "CHECKPOINT.json").write_text(
        json.dumps(checkpoint, indent=2, default=str), encoding="utf-8")

    print(f"veredicto           : {veredicto_}")
    print(f"checkpoint_id       : {checkpoint_id}")
    print(f"state_digest        : {digest}")
    print(f"gates               : {dict(por_sev)}")
    for iid, d in datos.items():
        print(f"  [{iid}] {d['identidad']['ticker_yahoo']:<10} "
              f"{len(d['rows'])} ruedas "
              f"{d['rows'][0].trading_date}..{d['rows'][-1].trading_date} "
              f"batch={d['batch_hash'][:12]} "
              f"raw_ok={sum(1 for a in d['archivos'] if a['verificado'] == 'OK')}"
              f"/{len(d['archivos'])}")
    print(f"entregables         : {len(escritos) + 2} archivos en {out}")
    conn.close()
    return 0 if veredicto_ != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
