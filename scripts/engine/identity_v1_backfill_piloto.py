#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Backfill PILOTO de Identity v1 — 12 emisores, por clase de dificultad.

Contrato: docs/architecture/IDENTITY_BACKFILL_CONTRACT.md

No es una carga: es una MEDICION. Responde cuanto del universo real puede
Identity v1 resolver con evidencia, y cuanto queda honestamente en manos de una
persona. NO son las ~8.000 entidades.

Escribe SOLO en identity_v1. No toca SEC, CNV ni Market (los lee).
Idempotente y reversible por run_id.

Uso:
    python scripts/engine/identity_v1_backfill_piloto.py --offline
    python scripts/engine/identity_v1_backfill_piloto.py --offline --aplicar
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sqlite3
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy import create_engine, text  # noqa: E402

from engine import db as edb  # noqa: E402
from engine import identity_v1 as idv  # noqa: E402
from engine.config import load_settings  # noqa: E402
from engine.identity_v1 import Evidence  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
UA = "Catalaxia-Identity/1.0 (fmonfasani@gmail.com)"
GLEIF = "https://api.gleif.org/api/v1/lei-records"

# Piloto por CLASE DE DIFICULTAD (contrato seccion 9). Los LEI vienen del ciclo
# G4 (busqueda por nombre = DISCOVERY); lo que se afirma es el registro GLEIF de
# ese LEI, nunca la coincidencia de nombre.
PILOTO = [
    {"slug": "YPF", "clase": "CIK+CUIT+LEI", "cik": "0000904851",
     "lei": "5493003N7447U18U5U53", "legacy": "YPFD"},
    {"slug": "CEPU", "clase": "CIK+CUIT+LEI", "cik": "0001717161",
     "lei": "2549005JLIWQ6B7VNR38", "legacy": "CEPU"},
    {"slug": "TGSU2", "clase": "CIK+CUIT+LEI", "cik": "0000931427",
     "lei": "5299002TRC7IFQYSW596", "legacy": "TGSU2"},
    {"slug": "GGAL", "clase": "CIK+LEI_sin_CUIT", "cik": "0001114700",
     "lei": "5299008H3AXIXV5G3C23", "legacy": "GGAL"},
    {"slug": "CAAP", "clase": "CUIT_sin_CIK", "cik": None, "lei": None, "legacy": "CAAP"},
    {"slug": "GGALB", "clase": "CUIT_sin_CIK", "cik": None, "lei": None, "legacy": "GGALB"},
    {"slug": "SUPVB", "clase": "CUIT_sin_CIK", "cik": None, "lei": None, "legacy": "SUPVB"},
    {"slug": "YPFLUZ", "clase": "CUIT_sin_CIK", "cik": None, "lei": None, "legacy": "YPFLUZ"},
    {"slug": "BMA", "clase": "dato_corrupto_F024", "cik": None, "lei": None, "legacy": "BMA"},
    {"slug": "AAPL", "clase": "solo_CIK_US", "cik": "0000320193", "lei": None, "legacy": "AAPL"},
    {"slug": "MSFT", "clase": "solo_CIK_US", "cik": "0000789019", "lei": None, "legacy": "MSFT"},
    {"slug": "NVDA", "clase": "solo_CIK_US", "cik": "0001045810", "lei": None, "legacy": "NVDA"},
]

SNAPSHOT_G4 = {
    "5493003N7447U18U5U53": {"registeredAt": "RA000009", "registeredAs": "30-54668997-9",
                             "legalName": "YPF Sociedad Anonima"},
    "2549005JLIWQ6B7VNR38": {"registeredAt": "RA000009", "registeredAs": "33-65030549-9",
                             "legalName": "CENTRAL PUERTO S A"},
    "5299008H3AXIXV5G3C23": {"registeredAt": "RA999999", "registeredAs": None,
                             "legalName": "Grupo Financiero Galicia S.A."},
    "5299002TRC7IFQYSW596": {"registeredAt": "RA000010", "registeredAs": "30-65786206-8",
                             "legalName": "Transportadora de Gas del Sur S.A."},
}


def gleif(lei: str, offline: bool):
    if offline or lei in SNAPSHOT_G4:
        s = SNAPSHOT_G4[lei]
        return ({"entity": {"registeredAt": {"id": s["registeredAt"]},
                            "registeredAs": s["registeredAs"]}},
                "snapshot G4 2026-08-25: legalName={!r} registeredAt={} registeredAs={!r}".format(
                    s["legalName"], s["registeredAt"], s["registeredAs"]))
    req = urllib.request.Request(GLEIF + "/" + lei, headers={
        "User-Agent": UA, "Accept": "application/vnd.api+json"})
    with urllib.request.urlopen(req, timeout=45) as r:
        a = json.loads(r.read())["data"]["attributes"]
    e = a["entity"]
    cita = "GLEIF {}/{} · legalName={!r} registeredAt={} registeredAs={!r}".format(
        GLEIF, lei, e["legalName"]["name"], (e.get("registeredAt") or {}).get("id"),
        e.get("registeredAs"))
    return a, cita


def legacy_row(slug: str):
    c = sqlite3.connect(str(REPO / "data" / "screener.db"))
    r = c.execute("SELECT entity_id, grupo, cik, cuit, ticker_canonico, nombre "
                  "  FROM dim_entity WHERE ticker_canonico = ?", (slug,)).fetchone()
    c.close()
    if not r:
        return None
    return dict(zip(("entity_id", "grupo", "cik", "cuit", "ticker", "nombre"), r))


def market_instrumentos(url: str, entity_id: str):
    """Lee Market (5432) en modo READ ONLY. No escribe."""
    eng = create_engine(url, future=True,
                        connect_args={"application_name": "identity_backfill_readonly"})
    with eng.connect() as c:
        c.execute(text("SET TRANSACTION READ ONLY"))
        rows = c.execute(text(
            "SELECT i.instrument_id, i.ticker_canonico, i.instrument_type, i.exchange, "
            "       i.currency, i.ratio_adr, "
            "       (SELECT m.ticker_yahoo FROM market_symbol_mappings m "
            "         WHERE m.instrument_id=i.instrument_id "
            "         ORDER BY (m.status='MAPPED') DESC LIMIT 1) AS yahoo "
            "  FROM market_instruments i WHERE i.entity_id=:e ORDER BY i.instrument_id"),
            {"e": str(entity_id)}).mappings().all()
    eng.dispose()
    return [dict(r) for r in rows]


def procesar(conn, em: dict, offline: bool, market_url: str) -> dict:
    out = {"slug": em["slug"], "clase": em["clase"], "fuentes": [], "eventos": [],
           "cik": None, "lei": None, "cuit": None, "conflicto": None,
           "identificadores": 0, "entity_key": None}
    leg = legacy_row(em["legacy"])
    if not leg:
        out["eventos"].append(("legacy", "SIN_DATO", em["legacy"] + " no esta en dim_entity"))
        return out

    # ---- ancla de la entidad -------------------------------------------
    # F-032: se resuelve por TODOS los identificadores autoritativos conocidos,
    # no solo por el primero. Si el orden de las fuentes cambia entre corridas,
    # la entidad se encuentra igual. Si dos identificadores apuntan a entidades
    # distintas es un CONFLICTO: no se fusiona nada.
    candidatos = [("CIK", "SEC", em["cik"]), ("LEI", "GLEIF", em["lei"])]
    if leg["cuit"]:
        candidatos.append(("CUIT", "AFIP", re.sub(r"\D", "", leg["cuit"])))
    hallada, choque = idv.resolver_por_candidatos(conn, candidatos)
    if choque:
        out["eventos"].append(("ancla", "CONFLICTO",
            "identificadores apuntan a entidades distintas: " + " | ".join(choque)))
        out["conflicto"] = "; ".join(choque)[:90]
        return out

    if em["cik"]:
        key = hallada or idv.create_entity(
            conn, leg["nombre"] or em["slug"],
            "US" if em["clase"] == "solo_CIK_US" else "AR")
    else:
        cu = re.sub(r"\D", "", leg["cuit"] or "")
        if not idv.cuit_valido(cu):
            out["eventos"].append(("ancla", "REJECTED",
                "CUIT legacy '{}' no pasa el modulo 11; no se crea entidad".format(leg["cuit"])))
            out["conflicto"] = "dato de origen invalido (F-024)"
            return out
        # F-032. La primera version anclaba la entidad en el CUIT legacy y la
        # creaba. Pero `LEGACY_DIM_ENTITY` es CORROBORATING y por contrato ese
        # CUIT nunca llega a autoritativo, asi que `resolve_or_create_entity`
        # —que resuelve por identificador AUTORITATIVO— no la encontraba en la
        # corrida siguiente y creaba OTRA. Tres corridas dejaron tres copias de
        # cada emisora argentina sin CIK.
        #
        # El contrato ya lo decia (seccion 7): "entidad sin ningun identificador
        # autoritativo posible queda UNRESOLVED, no se crea". La implementacion
        # lo violaba. Anclar una entidad en un identificador que la propia
        # politica no deja hacer autoritativo produce duplicacion silenciosa.
        if not hallada:
            out["eventos"].append(("ancla", "UNRESOLVED",
                "unica fuente de CUIT es LEGACY (CORROBORATING): no alcanza para "
                "anclar la entidad. No se crea; requiere GLEIF o AFIP"))
            out["cuit_candidato"] = cu
            return out
        key = hallada
    out["entity_key"] = key

    # ---- SEC: el CIK ----------------------------------------------------
    if em["cik"]:
        sec = conn.execute(text(
            "SELECT accession_number, form, filing_date FROM parsed.pre_xbrl_filings "
            " WHERE cik=:c ORDER BY filing_date DESC LIMIT 1"), {"c": em["cik"]}).first()
        if sec:
            ev = Evidence("SEC_20F", sec[0],
                          "parsed.pre_xbrl_filings: {} {} accession {} (CIK {})".format(
                              sec[1], sec[2], sec[0], em["cik"]),
                          "proc:s03_parse")
            met = "REGULATORY_DOCUMENT"
            out["fuentes"].append("SEC:20F")
        else:
            ev = Evidence("SEC_REGISTRY", "submissions/CIK{}.json".format(em["cik"]),
                          "SEC submissions declara el CIK {} para el registrante".format(em["cik"]),
                          "proc:sec_registry")
            met = "REGISTRY"
            out["fuentes"].append("SEC:registry")
        r = idv.assert_identifier(conn, entity_key=key, id_type="CIK", id_namespace="SEC",
                                  id_value=em["cik"], method=met, evidence=ev)
        out["eventos"].append(("CIK", r.status, ev.source_record))

    # ---- CUIT del legacy: CORROBORATING, nunca establece ----------------
    if leg["cuit"]:
        cu = re.sub(r"\D", "", leg["cuit"])
        r = idv.assert_identifier(
            conn, entity_key=key, id_type="CUIT", id_namespace="AFIP", id_value=cu,
            method="REGISTRY",
            evidence=Evidence("LEGACY_DIM_ENTITY", "sqlite:dim_entity#" + str(leg["entity_id"]),
                              "dim_entity fila {} ({}) declara cuit={!r} sin autor "
                              "ni documento de respaldo".format(
                                  leg["entity_id"], leg["grupo"], leg["cuit"]),
                              "proc:legacy_import"))
        out["fuentes"].append("LEGACY")
        out["eventos"].append(("CUIT legacy", r.status, r.motivo[:70]))
        if r.status == "REJECTED":
            out["conflicto"] = r.motivo[:90]

    # ---- GLEIF: LEI y, si corresponde, CUIT -----------------------------
    if em["lei"]:
        rec, cita = gleif(em["lei"], offline)
        r = idv.assert_identifier(conn, entity_key=key, id_type="LEI", id_namespace="GLEIF",
                                  id_value=em["lei"], method="REGISTRY",
                                  evidence=Evidence("GLEIF", "lei-records/" + em["lei"],
                                                    cita, "proc:gleif_fetch"))
        out["fuentes"].append("GLEIF")
        out["eventos"].append(("LEI", r.status, em["lei"]))
        r2 = idv.link_cuit_desde_gleif(
            conn, entity_key=key, lei=em["lei"], gleif_record=rec,
            source_record="gleif:lei-records/" + em["lei"], resolved_by="proc:gleif_fetch")
        out["eventos"].append(("CUIT via GLEIF", r2.status, r2.motivo[:80]))

    # ---- CNV: presentaciones bajo el CUIT autoritativo -------------------
    rep = idv.resolution_report(conn, key)
    cuit_aut = rep.get("cuit")
    if cuit_aut:
        n = conn.execute(text("SELECT count(*), min(fecha_publicacion), max(fecha_publicacion) "
                              "  FROM fetch_raw.cnv_presentation WHERE cuit=:c"),
                         {"c": cuit_aut}).first()
        if n and n[0]:
            idv.assert_identifier(
                conn, entity_key=key, id_type="CNV_ENTITY_ID", id_namespace="CNV",
                id_value=cuit_aut, method="CROSS_REFERENCE",
                evidence=Evidence("CNV_PORTAL", "cnv:emisor/" + cuit_aut,
                                  "fetch_raw.cnv_presentation: {} presentaciones bajo CUIT {} "
                                  "entre {} y {}".format(n[0], cuit_aut, n[1], n[2]),
                                  "proc:c3_cnv_fetch"))
            out["fuentes"].append("CNV")
            out["eventos"].append(("CNV", "CANDIDATE", "{} presentaciones".format(n[0])))

    # ---- Market: instrumentos --------------------------------------------
    for ins in market_instrumentos(market_url, leg["entity_id"]):
        ikey = "MKT:" + str(ins["instrument_id"])
        if conn.execute(text("SELECT 1 FROM identity_v1.instrument WHERE instrument_key=:k"),
                        {"k": ikey}).scalar():
            continue
        tipo = {"LOCAL": "EQUITY", "ADR": "ADR", "US": "EQUITY"}.get(
            ins["instrument_type"], "EQUITY")
        if tipo == "ADR" and ins["ratio_adr"] is None:
            out["eventos"].append(("MKT", "OMITIDO", ikey + " ADR sin ratio_adr"))
            continue
        aid = idv._insert_assertion(
            conn, subject_type="ENTITY_INSTRUMENT", entity_key=key,
            left_ref="INSTRUMENT:" + ikey, right_ref=None, relationship="BELONGS_TO",
            method="LEGACY_IMPORT", confidence="WEAK", status="CANDIDATE",
            ev=Evidence("MARKET_CATALOG",
                        "market_instruments.instrument_id=" + str(ins["instrument_id"]),
                        "market_instruments asocia {} ({} {}) a entity_id={}".format(
                            ikey, ins["exchange"], ins["currency"], leg["entity_id"]),
                        "proc:identity_backfill"))
        idv.register_instrument(conn, entity_key=key, instrument_key=ikey,
                                instrument_type=tipo, exchange=ins["exchange"] or "?",
                                currency=ins["currency"],
                                ratio_underlying=ins["ratio_adr"] if tipo == "ADR" else None,
                                assertion_id=aid)
        # F-014: ticker_canonico repite el ticker LOCAL en la fila del ADR.
        # Solo se escribe el simbolo que la fuente respalda.
        if ins["exchange"] == "BUE":
            idv.link_symbol(conn, instrument_key=ikey, id_namespace="BYMA",
                            symbol=ins["ticker_canonico"])
        if ins["yahoo"]:
            idv.link_symbol(conn, instrument_key=ikey, id_namespace="YAHOO",
                            symbol=ins["yahoo"])
        out["fuentes"].append("MARKET")
        out["eventos"].append(("MKT", "CANDIDATE", "{} {}".format(ikey, ins["instrument_type"])))

    rep = idv.resolution_report(conn, key)
    out["cik"] = rep.get("cik")
    out["cuit"] = rep.get("cuit")
    out["lei"] = rep.get("lei")
    out["identificadores"] = rep.get("n_autoritativos") or 0
    out["reviews"] = rep.get("reviews_abiertas") or 0
    out["fuentes"] = sorted(set(out["fuentes"]))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--aplicar", action="store_true", help="escribe; por defecto revierte")
    ap.add_argument("--offline", action="store_true", help="snapshot GLEIF del ciclo G4")
    ap.add_argument("--solo", help="lista de slugs separados por coma (piloto acotado)")
    args = ap.parse_args()

    s = load_settings()
    if s.is_prod:
        print("EXT-010: abortado.")
        return 2
    eng = edb.get_engine(s)
    # F-001: Market (5432) se lee con el rol de SOLO LECTURA de la migracion 012.
    # `catalaxia_engine` ni siquiera existe en esa base; el rol correcto es el
    # que tiene SELECT y `default_transaction_read_only = on`.
    market_url = ("postgresql+psycopg2://{}:{}@{}:5432/{}".format(
        "catalaxia_market_ro", s.db_password, s.db_host, s.db_name))

    huerfanas = edb.corridas_huerfanas(eng)
    if huerfanas:
        print("BLOCK · F-009: {} corrida(s) huerfana(s).".format(len(huerfanas)))
        return 1

    print("BACKFILL PILOTO · {}".format(s.describe()))
    print("modo: {}\n".format("APLICAR" if args.aplicar else "ENSAYO (se revierte)"))

    with edb.run_scope(eng, s, "identity-backfill-piloto-v1") as run:
        conn = eng.connect()
        tx = conn.begin()
        try:
            seleccion = PILOTO
            if args.solo:
                pedidos = [x.strip().upper() for x in args.solo.split(",")]
                seleccion = [e for e in PILOTO if e["slug"] in pedidos]
            res = [procesar(conn, em, args.offline, market_url) for em in seleccion]
            for r in res:
                print("=" * 78)
                print("{:<8} [{}]  entity_key={}".format(
                    r["slug"], r["clase"], r["entity_key"] or "—"))
                for etapa, estado, det in r["eventos"]:
                    print("   {:<16} {:<18} {}".format(etapa, estado, det))
            if args.aplicar:
                tx.commit()
            else:
                tx.rollback()
            run.status = "OK"
            d = REPO / "outputs" / "docs" / "fase_identity"
            d.mkdir(parents=True, exist_ok=True)
            (d / "backfill_piloto_{}.json".format(run.run_id[:12])).write_text(
                json.dumps(res, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
            print("\nrun_id={}  ({})".format(
                run.run_id, "APLICADO" if args.aplicar else "REVERTIDO"))
        finally:
            conn.close()
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    raise SystemExit(main())
