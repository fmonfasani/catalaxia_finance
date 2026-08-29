#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F-024 — tratamiento de BMA (Banco Macro) en Identity v1.

Contrato: docs/architecture/F024_CONTRATO.md

QUE RESUELVE
`dim_entity` fila 572 declara `cuit='0001347426'` y `cik=NULL`. Ese valor NO es
un CUIT (10 digitos, no pasa el modulo 11): es el **CIK de Macro Bank Inc.**,
verificado contra dos artefactos primarios de SEC ya materializados.

EL VINCULO NO ES POR NOMBRE NI POR TICKER
La fila legacy CONTIENE el valor 0001347426. SEC lo declara como CIK. El
identificador correcto ya estaba en la fila, en la columna equivocada. No se
infiere nada de la razon social: se lee el dato que la fila trae y se lo tipa
bien.

QUE NO HACE
  * NO toca `dim_entity`: es el registro historico del error y su evidencia.
  * NO establece el CUIT: GLEIF devuelve DOS LEI vigentes para la misma razon
    social, y elegir uno por domicilio seria inferencia.
  * NO establece el LEI, por la misma ambiguedad.
  * NO ratifica ningun bridge.

Idempotente y reversible. Escribe solo en identity_v1.

Uso:
    python scripts/engine/f024_bma.py            # informe, no escribe
    python scripts/engine/f024_bma.py --aplicar
"""
from __future__ import annotations

import argparse
import io
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy import text  # noqa: E402

from engine import db as edb  # noqa: E402
from engine import identity_v1 as idv  # noqa: E402
from engine.config import load_settings  # noqa: E402
from engine.identity_v1 import Evidence  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
CIK_BMA = "0001347426"
LEGACY_ID = 572

# Los dos LEI que GLEIF devuelve para la misma razon social. Se registran como
# candidatos en la review; NINGUNO se establece.
LEI_CANDIDATOS = [
    {"lei": "579100KKDKKIFEBKK040", "status": "ACTIVE", "registeredAs": "30-50001008-4",
     "domicilio": "MADERO EDUARDO AV. 1182, BUENOS AIRES, AR"},
    {"lei": "579100KKDKKIFEBKK058", "status": None, "registeredAs": "30500010084",
     "domicilio": "447 SARMIENTO, CAPITAL FEDERAL, AR"},
]


def evidencia_sec() -> tuple[str, dict] | tuple[None, None]:
    """Lee los DOS artefactos primarios de SEC. Sin ellos no se hace nada."""
    ct = sorted((REPO / "data" / "raw" / "catalogo_edgar").glob("company_tickers*.json"))
    sub = REPO / "data" / "raw" / "submissions" / f"CIK{CIK_BMA}.json"
    if not ct or not sub.exists():
        return None, None
    d = json.load(open(ct[-1], encoding="utf-8"))
    fila = next((e for e in (d.values() if isinstance(d, dict) else d)
                 if str(e.get("cik_str", "")).zfill(10) == CIK_BMA), None)
    if fila is None:
        return None, None
    s = json.load(open(sub, encoding="utf-8"))
    cita = ("SEC company_tickers {}: cik_str={} ticker={} title={!r}. "
            "SEC submissions CIK{}.json: name={!r} sic={} ({}) exchanges={} "
            "domicilio={!r}").format(
        ct[-1].name, fila["cik_str"], fila.get("ticker"), fila.get("title"),
        CIK_BMA, s.get("name"), s.get("sic"), s.get("sicDescription"),
        s.get("exchanges"), ((s.get("addresses") or {}).get("business") or {}).get("street1"))
    return cita, {"cik_str": fila["cik_str"], "ticker": fila.get("ticker"),
                  "title": fila.get("title"), "sec_name": s.get("name")}


def fila_legacy() -> dict | None:
    c = sqlite3.connect("file:" + str(REPO / "data" / "screener.db") + "?mode=ro", uri=True)
    r = c.execute("SELECT entity_id, ticker_canonico, grupo, cuit, cik, nombre "
                  "  FROM dim_entity WHERE entity_id = ?", (LEGACY_ID,)).fetchone()
    c.close()
    return dict(zip(("entity_id", "ticker", "grupo", "cuit", "cik", "nombre"), r)) if r else None


def tratar(conn, cita_sec: str, facts_sec: dict, leg: dict) -> dict:
    out = {"eventos": [], "entity_key": None}

    # --- 1. la entidad se ancla en su CIK, que SI es demostrable -----------
    key, creada = idv.resolve_or_create_entity(
        conn, preferred_name=facts_sec["sec_name"] or "Macro Bank Inc.",
        id_type="CIK", id_namespace="SEC", id_value=CIK_BMA, country="AR")
    out["entity_key"] = key
    out["eventos"].append(("entidad", "CREADA" if creada else "REUTILIZADA", key))

    r = idv.assert_identifier(
        conn, entity_key=key, id_type="CIK", id_namespace="SEC", id_value=CIK_BMA,
        method="REGISTRY",
        evidence=Evidence("SEC_REGISTRY", "company_tickers + submissions/CIK{}.json".format(CIK_BMA),
                          cita_sec, "proc:f024_bma", facts=facts_sec))
    out["eventos"].append(("CIK", r.status, CIK_BMA))

    # --- 2. el error del legacy queda REGISTRADO, no borrado --------------
    ya = conn.execute(text(
        "SELECT conflict_id FROM identity_v1.conflict "
        " WHERE id_value = :v AND reason LIKE 'F-024%' LIMIT 1"), {"v": CIK_BMA}).scalar()
    if ya:
        out["eventos"].append(("conflicto", "YA REGISTRADO", "conflict #{}".format(ya)))
    else:
        cid = idv.open_conflict(
            conn, id_type="CUIT", id_namespace="AFIP", id_value=CIK_BMA,
            candidatos=[key], detected_by="proc:f024_bma",
            reason=("F-024: dim_entity#{} declara cuit={!r} para el ticker {}, pero ese valor "
                    "es el CIK de {!r} segun SEC (company_tickers + submissions). No es un "
                    "CUIT: 10 digitos, no pasa el modulo 11. El legacy NO se modifica: es el "
                    "registro historico del error.").format(
                        leg["entity_id"], leg["cuit"], leg["ticker"], facts_sec["title"]))
        out["eventos"].append(("conflicto", "ABIERTO", "conflict #{}".format(cid)))

    # --- 3. el LEI es AMBIGUO: se registra la ambiguedad, no se elige ------
    ya_r = conn.execute(text(
        "SELECT review_id FROM identity_v1.review "
        " WHERE entity_key = :k AND status='OPEN' AND reason LIKE 'F-024%' LIMIT 1"),
        {"k": key}).scalar()
    if ya_r:
        out["eventos"].append(("review LEI", "YA ABIERTA", "review #{}".format(ya_r)))
    else:
        rid = idv.open_review(
            conn, entity_key=key,
            candidatos={"cik": CIK_BMA, "lei_candidatos": LEI_CANDIDATOS,
                        "domicilio_sec": "AV. EDUARDO MADERO 1182, BUENOS AIRES"},
            reason=("F-024: GLEIF devuelve DOS LEI vigentes para 'BANCO MACRO SOCIEDAD "
                    "ANONIMA'. El domicilio de 579100KKDKKIFEBKK040 coincide con el que SEC "
                    "declara, pero eso es corroboracion, no autoridad: ninguno menciona el "
                    "CIK. Elegir por domicilio seria inferencia. Decide una persona."),
            evidence="GLEIF filter[entity.legalName]=Banco Macro -> 2 resultados")
        out["eventos"].append(("review LEI", "ABIERTA", "review #{}".format(rid)))

    # --- 4. el CUIT NO se establece ---------------------------------------
    out["eventos"].append(("CUIT", "AUSENTE",
                           "depende del LEI ambiguo y del bridge CIK<->LEI (G5)"))
    rep = idv.resolution_report(conn, key)
    out["resolucion"] = {k: rep.get(k) for k in ("cik", "cuit", "lei", "n_autoritativos")}
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--aplicar", action="store_true")
    args = ap.parse_args()

    s = load_settings()
    if s.is_prod:
        print("EXT-010: abortado.")
        return 2
    eng = edb.get_engine(s)

    cita, facts = evidencia_sec()
    if not cita:
        print("BLOCK: faltan los artefactos primarios de SEC. No se hace nada.")
        return 1
    leg = fila_legacy()
    if not leg:
        print("BLOCK: no existe dim_entity#{}.".format(LEGACY_ID))
        return 1

    print("F-024 · BMA · {}".format(s.describe()))
    print("modo: {}\n".format("APLICAR" if args.aplicar else "ENSAYO (se revierte)"))
    print("  legacy   dim_entity#{}: ticker={} cuit={!r} cik={!r}".format(
        leg["entity_id"], leg["ticker"], leg["cuit"], leg["cik"]))
    print("  SEC      {}\n".format(cita[:150]))

    with edb.run_scope(eng, s, "f024-bma-v1") as run:
        conn = eng.connect()
        tx = conn.begin()
        try:
            out = tratar(conn, cita, facts, leg)
            for etapa, estado, det in out["eventos"]:
                print("   {:<12} {:<16} {}".format(etapa, estado, det))
            print("\n  resolucion: {}".format(out["resolucion"]))
            tx.commit() if args.aplicar else tx.rollback()
            run.status = "OK"
            print("\nrun_id={}  ({})".format(
                run.run_id, "APLICADO" if args.aplicar else "REVERTIDO"))
        finally:
            conn.close()
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    raise SystemExit(main())
