#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Superficie de consulta del motor canonico. CLI que devuelve JSON.

    python scripts/engine/ratio_api.py --ticker AAPL
    python scripts/engine/ratio_api.py --cik 0000904851 --ratio pe
    python scripts/engine/ratio_api.py --ticker YPFD --ratio pe --provenance
    python scripts/engine/ratio_api.py --ticker AAPL --fundamental ingresos
    python scripts/engine/ratio_api.py --universo

SOLO LECTURA. No calcula, no escribe: sirve lo que `ratio_engine.py` persistio.

EL CONTRATO DE SALIDA
Ningun valor viaja solo. Toda celda lleva, sin excepcion:

    canonical_id · value · unit · status · period_end · window
    · denominator_basis · currency · formula_version · formula
    · provenance_status · motivo

`value: null` con `status: NOT_CALCULABLE` NO es cero y NO es un error: es una
respuesta con motivo. Ver CATALAXIA_RATIO_PRODUCT.md.

`provenance_status` se recalcula al servir, no se guarda: se recorre cada
insumo y se verifica que su evidencia este completa y que el `parsed_cik`
coincida con el emisor de la fila.
    COMPLETA    todos los insumos contables citan RAW con hash, del mismo emisor
    PARCIAL     hay insumos citados pero alguno sin cadena
    AUSENTE     la fila no cita ningun insumo contable
"""
from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from sqlalchemy import text  # noqa: E402

from engine.config import load_settings  # noqa: E402
from engine.db import get_admin_engine  # noqa: E402

sys.path.insert(0, str(REPO / "scripts" / "engine"))
from ratio_defs import CONCEPTOS, elegir_concepto  # noqa: E402
from ratio_inputs import sql_insumos  # noqa: E402

# Roles que NO provienen de un filing y por lo tanto no tienen cadena XBRL.
ROLES_SIN_XBRL = {"precio", "derivado"}


class Filtros:
    """Las dimensiones por las que un cliente puede consultar."""

    def __init__(self, a):
        self.ratio = a.ratio
        self.window = a.window
        self.status = a.status
        self.period = a.period
        self.currency = a.currency


def q(conn, sql, **kw):
    return conn.execute(text(sql), kw).mappings().all()


# ═══════════════════════════════════════════════════════════ resolucion ═════

def resolver(conn, ticker: str | None, cik: str | None) -> dict:
    """ticker -> entidad -> CIK, por el enlace de instrumento. Nunca por nombre."""
    if cik:
        f = q(conn, """
            SELECT e.entity_key, e.preferred_name, i.id_value AS cik
              FROM identity_v1.identifier i
              JOIN identity_v1.entity e ON e.entity_key = i.entity_key
              JOIN identity_v1.assertion a ON a.assertion_id = i.assertion_id
             WHERE i.id_type='CIK' AND i.id_value=:c AND i.valid_to IS NULL
               AND a.status='VERIFIED'""", c=cik)
        if len(f) != 1:
            return {"error": "IDENTIDAD_NO_RESUELTA",
                    "detalle": f"el CIK {cik} no resuelve a una unica entidad "
                               f"con assertion VERIFIED ({len(f)} candidatas)"}
        return dict(f[0])
    f = q(conn, """
        SELECT DISTINCT e.entity_key, e.preferred_name,
               (SELECT i.id_value FROM identity_v1.identifier i
                 WHERE i.entity_key=e.entity_key AND i.id_type='CIK'
                   AND i.valid_to IS NULL LIMIT 1) AS cik
          FROM market_instruments mi
          JOIN identity_v1.instrument ii
            ON ii.instrument_key = 'MKT:' || mi.instrument_id AND ii.valid_to IS NULL
          JOIN identity_v1.entity e ON e.entity_key = ii.entity_key
         WHERE mi.ticker_canonico = :t""", t=ticker)
    if len(f) != 1:
        return {"error": "IDENTIDAD_NO_RESUELTA",
                "detalle": f"el ticker {ticker} resuelve a {len(f)} entidades por "
                           f"enlace de instrumento; el ticker no es identidad"}
    return dict(f[0])


# ═══════════════════════════════════════════════════════════ provenance ═════

def provenance_status(fila: dict) -> str:
    contables = [i for i in fila["inputs"] if i.get("rol") not in ROLES_SIN_XBRL]
    if not contables:
        return "AUSENTE"
    for i in contables:
        ev = i.get("evidencia") or {}
        if ev.get("estado") != "COMPLETA":
            return "PARCIAL"
        if not ev.get("source_hashes") or not ev.get("source_fact_ids"):
            return "PARCIAL"
        if ev.get("parsed_cik") != fila["cik"]:
            return "PARCIAL"
    return "COMPLETA"


def celda(fila: dict, con_provenance: bool = False) -> dict:
    out = {
        "canonical_id": fila["canonical_id"],
        "value": float(fila["value"]) if fila["value"] is not None else None,
        "unit": fila["unit"],
        "status": fila["status"],
        "period_end": fila["period_end"].isoformat(),
        "window": fila["period_window"],
        "denominator_basis": fila["denominator_basis"],
        "currency": fila["currency"],
        "formula_version": fila["formula_version"],
        "formula": fila["formula"],
        "provenance_status": provenance_status(fila),
        "motivo": fila["motivo"],
        "publicable": fila["publicable"],
    }
    if con_provenance:
        out["provenance"] = {
            "run_id": fila["run_id"],
            "input_checkpoint_id": fila["input_checkpoint_id"],
            "calculated_at": fila["calculated_at"].isoformat(),
            "valid_from": fila["valid_from"].isoformat(),
            "valid_to": fila["valid_to"].isoformat() if fila["valid_to"] else None,
            "inputs": fila["inputs"],
        }
    return out


# ═══════════════════════════════════════════════════════════════ consultas ══

def ratios_de(conn, ent: dict, f: "Filtros", con_prov: bool) -> list[dict]:
    """Las seis dimensiones de consulta del contrato, todas opcionales."""
    filas = q(conn, """
        SELECT * FROM derived.ratio
         WHERE valid_to IS NULL AND entity_key = :ek
           AND (:r   IS NULL OR canonical_id  = :r)
           AND (:w   IS NULL OR period_window = :w)
           AND (:st  IS NULL OR status        = :st)
           AND (:pe  IS NULL OR period_end    = CAST(:pe AS date))
           AND (:cur IS NULL OR currency      = :cur)
         ORDER BY canonical_id, period_end DESC""",
        ek=ent["entity_key"], r=f.ratio, w=f.window, st=f.status,
        pe=f.period, cur=f.currency)
    return [celda(dict(x), con_prov) for x in filas]


def fundamental_de(conn, ent: dict, concepto: str) -> dict:
    """Un concepto contable del ultimo ejercicio, con su cadena de fallback.

    Pasa por la MISMA seleccion que los ratios: la guarda de pertenencia de
    F-061 aplica igual a una consulta de fundamental.
    """
    if concepto not in CONCEPTOS:
        return {"error": "CONCEPTO_DESCONOCIDO",
                "detalle": f"'{concepto}' no esta declarado",
                "disponibles": sorted(CONCEPTOS)}
    filas = q(conn, sql_insumos(
        "d.tag, d.report_period::text AS per, d.currency, d.value_numeric, "
        "d.accession_number, d.qname, d.namespace, d.unit_measure, "
        "d.source_fact_ids, d.fact_key, d.filing_date::text AS fdate"),
        c=ent["cik"])
    if not filas:
        return {"concepto": concepto, "status": "NOT_CALCULABLE", "value": None,
                "motivo": "el emisor no tiene facts que pasen la guarda de pertenencia"}
    porper: dict[str, dict] = {}
    for f in filas:
        porper.setdefault(f["per"], {})[f["tag"]] = dict(f)
    per = max(porper)
    tag, f = elegir_concepto(porper[per], concepto)
    if f is None:
        return {"concepto": concepto, "status": "NOT_CALCULABLE", "value": None,
                "period_end": per, "window": "FY",
                "cadena_evaluada": CONCEPTOS[concepto],
                "motivo": f"ningun tag de la cadena esta presente en {per}"}
    fuentes = q(conn, """
        SELECT fact_id, cik, accession_number, source_file, source_hash
          FROM parsed.facts WHERE fact_id = ANY(:ids)""",
        ids=[int(i) for i in f["source_fact_ids"]])
    return {"concepto": concepto, "status": "DISPONIBLE",
            "value": float(f["value_numeric"]), "currency": f["currency"],
            "period_end": per, "window": "FY",
            "tag_elegido": tag, "cadena_evaluada": CONCEPTOS[concepto],
            "qname": f["qname"], "unit_measure": f["unit_measure"],
            "accession_number": f["accession_number"],
            "provenance_status": ("COMPLETA"
                                  if all(x["cik"] == ent["cik"] for x in fuentes)
                                  and len(fuentes) == len(f["source_fact_ids"])
                                  else "PARCIAL"),
            "source_fact_ids": [int(i) for i in f["source_fact_ids"]],
            "source_files": sorted({x["source_file"] for x in fuentes}),
            "source_hashes": sorted({x["source_hash"] for x in fuentes})}


# ═══════════════════════════════════════════════════════════════ main ═══════

def main() -> int:
    ap = argparse.ArgumentParser(description="Consulta del motor canonico de ratios")
    ap.add_argument("--ticker")
    ap.add_argument("--cik")
    ap.add_argument("--ratio", help="ev_sales | eps | pb | pe")
    ap.add_argument("--fundamental", help="concepto contable, p.ej. ingresos")
    ap.add_argument("--window", help="FY | TTM | Q | YTD | PIT")
    ap.add_argument("--status", help="CALCULADO | NOT_CALCULABLE | REVIEW_REQUIRED")
    ap.add_argument("--period", help="period_end exacto, p.ej. 2025-09-27")
    ap.add_argument("--currency", help="USD | ARS")
    ap.add_argument("--provenance", action="store_true",
                    help="incluye la cadena completa de insumos")
    ap.add_argument("--universo", action="store_true",
                    help="todas las entidades con ratios persistidos")
    a = ap.parse_args()

    s = load_settings()
    if s.is_prod:
        print(json.dumps({"error": "EXT-010: no se consulta produccion"}))
        return 2
    eng = get_admin_engine(s)

    with eng.connect() as c:
        if a.universo:
            ents = q(c, """
                SELECT DISTINCT r.entity_key, e.preferred_name, r.cik
                  FROM derived.ratio r
                  JOIN identity_v1.entity e ON e.entity_key = r.entity_key
                 WHERE r.valid_to IS NULL ORDER BY 2""")
            salida = {"universo": [
                {"entity_key": e["entity_key"], "nombre": e["preferred_name"],
                 "cik": e["cik"],
                 "ratios": ratios_de(c, dict(e), Filtros(a), a.provenance)}
                for e in ents]}
        else:
            if not (a.ticker or a.cik):
                print(json.dumps({"error": "falta --ticker, --cik o --universo"}))
                return 2
            ent = resolver(c, a.ticker, a.cik)
            if "error" in ent:
                print(json.dumps(ent, ensure_ascii=False, indent=2))
                return 1
            salida = {"entity_key": ent["entity_key"],
                      "nombre": ent["preferred_name"], "cik": ent["cik"]}
            if a.fundamental:
                salida["fundamental"] = fundamental_de(c, ent, a.fundamental)
            else:
                salida["ratios"] = ratios_de(c, ent, Filtros(a), a.provenance)

    print(json.dumps(salida, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    raise SystemExit(main())
