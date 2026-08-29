#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Identity v1 — piloto de 4 emisores (ciclo 4).

Materializa YPF, CEPU, GGAL y TGSU2 en identity_v1 usando EVIDENCIA REAL de las
cuatro fuentes, y despues recorre la cadena completa para demostrar que se puede
responder, para cada emisor:

    CIK X, CUIT Y e instrumento Z son la misma entidad economica PORQUE ...

Reglas de operacion:
  - escribe SOLO en identity_v1 del engine-dev (5433);
  - lee 5432 (Market) en modo READ ONLY explicito;
  - no toca el parser SEC, el fetcher de Market ni el de CNV;
  - si una fuente no tiene el dato, deja REVIEW_REQUIRED. Nunca lo completa.

Es IDEMPOTENTE (F-023): resuelve cada entidad por su CIK autoritativo antes de
crearla, de modo que dos corridas seguidas dejan el mismo estado y los mismos
entity_key. No existe --reset: desde la migracion 009 el DELETE y el TRUNCATE
sobre la procedencia estan prohibidos. Para reiniciar en dev hay un unico
camino, deliberadamente ruidoso: DROP SCHEMA identity_v1 CASCADE + re-migrar.

Uso:
    python scripts/engine/identity_v1_pilot.py            # fetch GLEIF en vivo
    python scripts/engine/identity_v1_pilot.py --offline  # snapshot G4
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy import create_engine, text  # noqa: E402

from engine.config import load_settings  # noqa: E402
from engine.db import get_engine  # noqa: E402
from engine import identity_v1 as idv  # noqa: E402
from engine.identity_v1 import Evidence  # noqa: E402

UA = "Catalaxia-Identity/1.0 (fmonfasani@gmail.com)"
GLEIF_API = "https://api.gleif.org/api/v1/lei-records"

# Emisores del piloto. El LEI viene del ciclo G4 (busqueda por nombre =
# DISCOVERY); lo que se afirma aca es el registro GLEIF de ese LEI, no la
# coincidencia de nombre.
EMISORES = [
    {"slug": "YPF",   "nombre": "YPF SOCIEDAD ANONIMA",
     "cik": "0000904851", "lei": "5493003N7447U18U5U53", "market_entity": "72"},
    {"slug": "CEPU",  "nombre": "CENTRAL PUERTO S.A.",
     "cik": "0001717161", "lei": "2549005JLIWQ6B7VNR38", "market_entity": "70"},
    {"slug": "GGAL",  "nombre": "GRUPO FINANCIERO GALICIA S.A.",
     "cik": "0001114700", "lei": "5299008H3AXIXV5G3C23", "market_entity": "65"},
    {"slug": "TGSU2", "nombre": "TRANSPORTADORA DE GAS DEL SUR S.A.",
     "cik": "0000931427", "lei": "5299002TRC7IFQYSW596", "market_entity": "62"},
]

# Snapshot verificado en el ciclo G4 (2026-08-25), para correr sin red.
GLEIF_SNAPSHOT = {
    "5493003N7447U18U5U53": {"registeredAt": "RA000009", "registeredAs": "30-54668997-9"},
    "2549005JLIWQ6B7VNR38": {"registeredAt": "RA000009", "registeredAs": "33-65030549-9"},
    "5299008H3AXIXV5G3C23": {"registeredAt": "RA999999", "registeredAs": None},
    "5299002TRC7IFQYSW596": {"registeredAt": "RA000010", "registeredAs": "30-65786206-8"},
}


def gleif_record(lei: str, offline: bool) -> tuple[dict, str]:
    """Devuelve (registro, cita). En offline usa el snapshot, y lo declara."""
    if offline:
        s = GLEIF_SNAPSHOT[lei]
        rec = {"entity": {"registeredAt": {"id": s["registeredAt"]},
                          "registeredAs": s["registeredAs"]}}
        return rec, f"snapshot G4 2026-08-25: registeredAt={s['registeredAt']} registeredAs={s['registeredAs']!r}"
    req = urllib.request.Request(f"{GLEIF_API}/{lei}",
                                 headers={"User-Agent": UA,
                                          "Accept": "application/vnd.api+json"})
    with urllib.request.urlopen(req, timeout=45) as r:
        d = json.loads(r.read())
    a = d["data"]["attributes"]
    ent = a["entity"]
    cita = (f"GLEIF {GLEIF_API}/{lei} · legalName={ent['legalName']['name']!r} "
            f"registeredAt={(ent.get('registeredAt') or {}).get('id')} "
            f"registeredAs={ent.get('registeredAs')!r}")
    return a, cita


# --------------------------------------------------------------------------
# Lectura de las fuentes ya materializadas
# --------------------------------------------------------------------------

def sec_evidence(conn, cik: str) -> tuple[str, str] | None:
    row = conn.execute(text(
        "SELECT accession_number, form, filing_date FROM parsed.pre_xbrl_filings "
        " WHERE cik=:c ORDER BY filing_date DESC LIMIT 1"), {"c": cik}).first()
    if not row:
        return None
    return row[0], f"parsed.pre_xbrl_filings: {row[1]} {row[2]} accession {row[0]} (CIK {cik})"


def cnv_evidence(conn, cuit: str) -> tuple[int, str] | None:
    row = conn.execute(text(
        "SELECT count(*), min(fecha_publicacion), max(fecha_publicacion) "
        "  FROM fetch_raw.cnv_presentation WHERE cuit=:c"), {"c": cuit}).first()
    if not row or not row[0]:
        return None
    return row[0], (f"fetch_raw.cnv_presentation: {row[0]} presentaciones publicadas "
                    f"bajo CUIT {cuit} entre {row[1]} y {row[2]}")


def market_instrumentos(market_url: str, entity_id: str) -> list[dict]:
    """Lee Market en 5432 en modo READ ONLY. No escribe nada."""
    eng = create_engine(market_url, future=True,
                        connect_args={"application_name": "identity_v1_pilot_readonly"})
    with eng.connect() as c:
        c.execute(text("SET TRANSACTION READ ONLY"))
        # subselect y no JOIN: un instrumento con 2 mappings duplicaria la fila
        # y el INSERT de instrument reventaria por PK. Se toma el mapeo MAPPED.
        rows = c.execute(text(
            "SELECT i.instrument_id, i.ticker_canonico, i.instrument_type, i.exchange, "
            "       i.currency, i.ratio_adr, "
            "       (SELECT m.ticker_yahoo FROM market_symbol_mappings m "
            "         WHERE m.instrument_id = i.instrument_id "
            "         ORDER BY (m.status='MAPPED') DESC, m.ticker_yahoo LIMIT 1) AS ticker_yahoo "
            "  FROM market_instruments i "
            " WHERE i.entity_id = :e ORDER BY i.instrument_id"), {"e": entity_id}).mappings().all()
    eng.dispose()
    return [dict(r) for r in rows]


# --------------------------------------------------------------------------

def sembrar(conn, em: dict, offline: bool, market_url: str) -> dict:
    slug = em["slug"]
    out = {"slug": slug, "pasos": []}

    key, creada = idv.resolve_or_create_entity(
        conn, preferred_name=em["nombre"], id_type="CIK", id_namespace="SEC",
        id_value=em["cik"], country="AR")
    out["entity_key"] = key
    out["creada"] = creada

    # --- 1. SEC: el CIK -------------------------------------------------
    sec = sec_evidence(conn, em["cik"])
    if sec:
        ev = Evidence("SEC_20F", sec[0], sec[1], "proc:s03_parse")
        met = "REGULATORY_DOCUMENT"
    else:
        ev = Evidence("SEC_REGISTRY", f"submissions/CIK{em['cik']}.json",
                      f"SEC submissions declara el CIK {em['cik']} para el registrante",
                      "proc:sec_registry")
        met = "REGISTRY"
    r = idv.assert_identifier(conn, entity_key=key, id_type="CIK", id_namespace="SEC",
                              id_value=em["cik"], method=met, evidence=ev)
    out["pasos"].append(("SEC  CIK", r.status, ev.source_record))

    # --- 2. GLEIF: el LEI ------------------------------------------------
    rec, cita = gleif_record(em["lei"], offline)
    ev_g = Evidence("GLEIF", f"lei-records/{em['lei']}", cita, "proc:gleif_fetch")
    r = idv.assert_identifier(conn, entity_key=key, id_type="LEI", id_namespace="GLEIF",
                              id_value=em["lei"], method="REGISTRY", evidence=ev_g)
    out["pasos"].append(("GLEIF LEI", r.status, em["lei"]))

    # --- 3. el puente CIK <-> LEI (G5: no hay fuente primaria) -----------
    # F-016: este script NO firma el puente. Ninguna fuente primaria publica el
    # par CIK<->LEI, y un proceso no puede ratificar lo que no puede demostrar.
    # Se registra la PROPUESTA; la ratificacion la hace una persona con
    # scripts/engine/identity_v1_ratificar.py, con evidencia de ambos lados.
    if idv.bridge_verificado(conn, idv.ref("CIK", "SEC", em["cik"]),
                             idv.ref("LEI", "GLEIF", em["lei"])):
        out["pasos"].append(("BRIDGE CIK<->LEI", "VERIFIED (ratificado)",
                             "una persona lo ratifico"))
    else:
        idv.assert_bridge(
            conn, left_ref_=idv.ref("CIK", "SEC", em["cik"]),
            right_ref_=idv.ref("LEI", "GLEIF", em["lei"]), method="CROSS_REFERENCE",
            evidence=Evidence(
                "GLEIF", f"lei-records/{em['lei']}",
                f"{cita} — propuesto por coincidencia de denominacion social con el "
                f"registrante del CIK {em['cik']}. NO demostrado: ninguna fuente "
                "primaria publica este par (G5).",
                "proc:identity_v1_pilot"))
        out["pasos"].append(("BRIDGE CIK<->LEI", "CANDIDATE (sin ratificar)",
                             "requiere identity_v1_ratificar.py"))

    # --- 4. el CUIT por la via GLEIF -------------------------------------
    r = idv.link_cuit_desde_gleif(conn, entity_key=key, lei=em["lei"],
                                  gleif_record=rec,
                                  source_record=f"gleif:lei-records/{em['lei']}",
                                  resolved_by="proc:gleif_fetch")
    out["pasos"].append(("AFIP CUIT", r.status, r.motivo[:96]))
    out["cuit"] = idv.resolution_report(conn, key).get("cuit")

    # --- 5. CNV: presentaciones bajo ese CUIT ----------------------------
    if out["cuit"]:
        cnv = cnv_evidence(conn, out["cuit"])
        if cnv:
            idv.assert_identifier(
                conn, entity_key=key, id_type="CNV_ENTITY_ID", id_namespace="CNV",
                id_value=out["cuit"], method="REGISTRY",
                evidence=Evidence("CNV_PORTAL", f"cnv:emisor/{out['cuit']}", cnv[1],
                                  "proc:c3_cnv_fetch"))
            out["pasos"].append(("CNV  emisor", "CANDIDATE", f"{cnv[0]} presentaciones"))
        else:
            out["pasos"].append(("CNV  emisor", "SIN DATO", "no hay fetch CNV para este CUIT"))
    else:
        out["pasos"].append(("CNV  emisor", "BLOQUEADO", "sin CUIT no se puede consultar CNV"))

    # --- 6. Market: instrumentos ------------------------------------------
    for ins in market_instrumentos(market_url, em["market_entity"]):
        tipo = {"LOCAL": "EQUITY", "ADR": "ADR", "US": "EQUITY"}.get(ins["instrument_type"], "EQUITY")
        ikey = f"MKT:{ins['instrument_id']}"
        if conn.execute(text("SELECT 1 FROM identity_v1.instrument WHERE instrument_key=:k"),
                        {"k": ikey}).scalar():
            out["pasos"].append((f"MKT  {ins['instrument_type']:<5}",
                                 f"{ikey} {ins['ticker_canonico']}", "ya registrado"))
            continue
        aid = idv._insert_assertion(
            conn, subject_type="ENTITY_INSTRUMENT", entity_key=key,
            left_ref=f"INSTRUMENT:{ikey}", right_ref=None, relationship="BELONGS_TO",
            method="LEGACY_IMPORT", confidence="WEAK", status="CANDIDATE",
            ev=Evidence("MARKET_CATALOG",
                        f"market_instruments.instrument_id={ins['instrument_id']}",
                        f"market_instruments asocia {ikey} ({ins['exchange']} "
                        f"{ins['currency']}) a esta entidad", "proc:identity_v1_pilot"))
        idv.register_instrument(
            conn, entity_key=key, instrument_key=ikey, instrument_type=tipo,
            exchange=ins["exchange"] or "?", currency=ins["currency"],
            ratio_underlying=ins["ratio_adr"] if tipo == "ADR" else None,
            assertion_id=aid)
        # market_instruments.ticker_canonico es el ticker LOCAL y viene repetido
        # en la fila del ADR: para MKT:84 (NYSE) dice 'YPFD', que es el simbolo
        # de BYMA, no el de NYSE. Solo se escribe el simbolo en el namespace que
        # la fuente REALMENTE respalda; el resto queda en review.
        nota = ""
        if ins["exchange"] == "BUE":
            idv.link_symbol(conn, instrument_key=ikey, id_namespace="BYMA",
                            symbol=ins["ticker_canonico"])
        else:
            rid = idv.open_review(
                conn, entity_key=key,
                candidatos={"instrument_key": ikey, "exchange": ins["exchange"],
                            "ticker_canonico_market": ins["ticker_canonico"],
                            "ticker_yahoo": ins["ticker_yahoo"]},
                reason=("Market no publica el simbolo de "
                        f"{ins['exchange']}: ticker_canonico='{ins['ticker_canonico']}' "
                        "es el ticker local repetido en la fila del ADR"),
                evidence=f"market_instruments.instrument_id={ins['instrument_id']} (5432)")
            nota = f"review #{rid}: sin simbolo {ins['exchange']} respaldado"
        if ins["ticker_yahoo"]:
            idv.link_symbol(conn, instrument_key=ikey, id_namespace="YAHOO",
                            symbol=ins["ticker_yahoo"])
        out["pasos"].append((f"MKT  {ins['instrument_type']:<5}",
                             f"{ikey} {ins['ticker_canonico']}",
                             f"{ins['exchange']} {ins['currency']} "
                             f"yahoo={ins['ticker_yahoo']} {nota}"))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true", help="usar snapshot GLEIF del ciclo G4")
    args = ap.parse_args()

    s = load_settings()
    if s.is_prod:
        print("EXT-010: el piloto no corre contra 5432. Abortado.")
        return 2
    eng = get_engine(s)

    market_url = (f"postgresql+psycopg2://{s.db_user}:{s.db_password}"
                  f"@{s.db_host}:5432/{s.db_name}")

    print(f"identity_v1 pilot · escritura: {s.describe()}")
    print(f"                    lectura Market (READ ONLY): {s.db_host}:5432\n")

    with eng.begin() as conn:
        resultados = [sembrar(conn, em, args.offline, market_url) for em in EMISORES]

        for r in resultados:
            print("=" * 78)
            print(f"{r['slug']}   entity_key = {r['entity_key']}")
            for etapa, estado, detalle in r["pasos"]:
                print(f"   {etapa:<18} {estado:<28} {detalle}")

        print("\n" + "=" * 78)
        print("RESOLUCION (identity_v1.v_entity_resolution)")
        print("=" * 78)
        for row in conn.execute(text(
            "SELECT preferred_name, cik, cuit, lei, n_autoritativos, "
            "       reviews_abiertas, conflictos_abiertos "
            "  FROM identity_v1.v_entity_resolution ORDER BY preferred_name")).mappings():
            print(f"   {row['preferred_name'][:34]:<36} CIK={row['cik']} "
                  f"CUIT={row['cuit'] or '—':<12} LEI={row['lei']} "
                  f"aut={row['n_autoritativos']} rev={row['reviews_abiertas']} "
                  f"conf={row['conflictos_abiertos']}")

        print("\nREVIEWS ABIERTAS (lo que el sistema admite NO saber):")
        n = 0
        for row in conn.execute(text(
            "SELECT r.review_id, e.preferred_name, r.reason "
            "  FROM identity_v1.review r LEFT JOIN identity_v1.entity e USING (entity_key) "
            " WHERE r.status='OPEN' ORDER BY r.review_id")).mappings():
            print(f"   #{row['review_id']} {row['preferred_name'][:30]:<32} {row['reason']}")
            n += 1
        if not n:
            print("   (ninguna)")
    return 0


if __name__ == "__main__":
    # solo al ejecutarse como script: importar no debe tocar sys.stdout
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")
    raise SystemExit(main())
