#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Identity v1 — banco adversario sobre los 4 emisores ya materializados.

Intenta corromper la identidad de las entidades del piloto por las vias por las
que el sistema legacy SI se dejo corromper, y verifica que cada intento sea
rechazado o quede en revision. Todo corre dentro de una transaccion que se
REVIERTE: no modifica el estado del piloto.

    python scripts/engine/identity_v1_adversario.py
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy import text  # noqa: E402

from engine.config import load_settings  # noqa: E402
from engine.db import get_engine  # noqa: E402
from engine import identity_v1 as idv  # noqa: E402
from engine.identity_v1 import Evidence  # noqa: E402

ATAQUES: list[tuple[str, str]] = []


def registrar(nombre, esperado, obtenido, detalle=""):
    ok = obtenido == esperado
    ATAQUES.append((nombre, esperado, obtenido, ok, detalle))
    print(f"  [{'OK ' if ok else 'FALLA'}] {nombre:<52} esperado={esperado:<16} "
          f"obtenido={obtenido}")
    if detalle:
        print(f"          {detalle}")


def sql_falla(conn, q, **p) -> str:
    sp = conn.begin_nested()
    try:
        conn.execute(text(q), p)
    except Exception as e:  # noqa: BLE001
        sp.rollback()
        return type(e).__name__ + ": " + str(e).split("\n")[0][:150]
    sp.rollback()
    return ""


def main() -> int:
    s = load_settings()
    if s.is_prod:
        print("EXT-010: abortado.")
        return 2
    eng = get_engine(s)

    with eng.connect() as conn:
        tx = conn.begin()
        try:
            ent = {r["preferred_name"].split()[0]: dict(r) for r in conn.execute(text(
                "SELECT * FROM identity_v1.v_entity_resolution")).mappings()}
            if len(ent) < 4:
                print("El piloto no esta sembrado. Correr identity_v1_pilot.py primero.")
                return 2
            ypf, cepu = ent["YPF"], ent["CENTRAL"]
            ggal, tgs = ent["GRUPO"], ent["TRANSPORTADORA"]
            print(f"piloto: {len(ent)} entidades en {s.describe()}\n")

            # ---------------------------------------------------------------
            print("A) El error historico: el CUIT de Central Puerto atribuido a YPF")
            r = idv.assert_identifier(
                conn, entity_key=ypf["entity_key"], id_type="CUIT", id_namespace="AFIP",
                id_value=cepu["cuit"], method="REGULATORY_DOCUMENT",
                evidence=Evidence("SEC_20F", "20-F/0000904851",
                                  "supuesta mencion de CUIT en el 20-F", "proc:s03"))
            registrar("CUIT de CEPU -> YPF", "REJECTED", r.status,
                      f"conflict #{r.conflict_id}; el CUIT sigue en {r.detalle.get('entidad_actual')}")

            # ---------------------------------------------------------------
            print("\nB) Un CIK contradictorio desde una fuente autoritativa")
            # B1: el CIK ya pertenece a otra entidad -> rechazo duro
            r = idv.assert_identifier(
                conn, entity_key=ypf["entity_key"], id_type="CIK", id_namespace="SEC",
                id_value=tgs["cik"], method="REGISTRY",
                evidence=Evidence("SEC_REGISTRY", "submissions/otro.json",
                                  "otra fila del catalogo", "proc:sec"))
            registrar("CIK de TGSU2 (ya asignado) -> YPF", "REJECTED", r.status,
                      f"conflict #{r.conflict_id}; pertenece a {r.detalle.get('entidad_actual')}")
            # B2: un CIK que nadie reclama, pero YPF ya tiene otro -> revision
            r = idv.assert_identifier(
                conn, entity_key=ypf["entity_key"], id_type="CIK", id_namespace="SEC",
                id_value="0000320193", method="REGISTRY",
                evidence=Evidence("SEC_REGISTRY", "submissions/CIK0000320193.json",
                                  "CIK de Apple Inc., no reclamado en el piloto", "proc:sec"))
            registrar("CIK libre pero contradictorio -> YPF", "REVIEW_REQUIRED", r.status,
                      f"vigente={r.detalle.get('vigente')} propuesto={r.detalle.get('propuesto')}")

            # ---------------------------------------------------------------
            print("\nC) El legacy (dim_entity) intentando imponer su version")
            r = idv.assert_identifier(
                conn, entity_key=ggal["entity_key"], id_type="CUIT", id_namespace="AFIP",
                id_value="30704962807", method="REGISTRY",
                evidence=Evidence("LEGACY_DIM_ENTITY", "sqlite:dim_entity",
                                  "fila legacy sin autor ni documento de respaldo",
                                  "proc:legacy_import"))
            registrar("legacy completa el CUIT de GGAL", "CANDIDATE", r.status,
                      "CORROBORATING no establece identidad; la review sigue abierta")
            rep = idv.resolution_report(conn, ggal["entity_key"])
            registrar("  y el CUIT autoritativo de GGAL sigue vacio", "None", str(rep["cuit"]))

            # ---------------------------------------------------------------
            print("\nD) Un CUIT con digito verificador invalido")
            r = idv.assert_identifier(
                conn, entity_key=ggal["entity_key"], id_type="CUIT", id_namespace="AFIP",
                id_value="30704962801", method="REGULATORY_DOCUMENT",
                evidence=Evidence("SEC_20F", "20-F/0001114700", "cita cualquiera", "proc:s03"))
            registrar("CUIT con checksum roto", "REJECTED", r.status, r.motivo)

            # ---------------------------------------------------------------
            print("\nE) Colision de ticker entre mercados (el caso COUR)")
            k = idv.create_entity(conn, "Emisora extranjera homonima", "US")
            r = idv.assert_identifier(
                conn, entity_key=k, id_type="TICKER", id_namespace="US", id_value="TGS",
                method="REGISTRY", evidence=Evidence("SEC_REGISTRY", "company_tickers",
                                                     "ticker TGS", "proc:sec"))
            registrar("ticker homonimo no crea identidad", "CANDIDATE", r.status,
                      f"is_authoritative={r.is_authoritative}")
            # el mismo simbolo YAHOO vigente no puede colgar de dos instrumentos
            msg = sql_falla(conn,
                "INSERT INTO identity_v1.instrument_symbol (instrument_key, id_namespace, symbol) "
                "VALUES ('MKT:65','YAHOO','TGS')")
            registrar("simbolo YAHOO 'TGS' en dos instrumentos", "rechazado",
                      "rechazado" if "ux_symbol_vigente" in msg else msg or "ACEPTADO", msg[:120])
            # pero el mismo texto en otro namespace SI convive (BYMA vs YAHOO)
            sp = conn.begin_nested()
            idv.link_symbol(conn, instrument_key="MKT:66", id_namespace="US", symbol="TGS")
            registrar("mismo texto en namespace distinto", "aceptado", "aceptado",
                      "US/TGS y YAHOO/TGS son identificadores distintos")
            sp.rollback()

            # ---------------------------------------------------------------
            print("\nF) Reescritura del pasado y borrado de provenance")
            aid = conn.execute(text(
                "SELECT assertion_id FROM identity_v1.assertion "
                " WHERE entity_key=:k AND left_ref LIKE 'CIK%' LIMIT 1"),
                {"k": ypf["entity_key"]}).scalar()
            msg = sql_falla(conn, "DELETE FROM identity_v1.assertion WHERE assertion_id=:a", a=aid)
            registrar("borrar assertion vigente de YPF", "rechazado",
                      "rechazado" if "vigente" in msg else msg or "ACEPTADO", msg[:120])
            nueva = idv._insert_assertion(
                conn, subject_type="ENTITY_IDENTIFIER", entity_key=ypf["entity_key"],
                left_ref=idv.ref("CIK", "SEC", ypf["cik"]), right_ref=None,
                relationship="BELONGS_TO", method="REGISTRY", confidence="AUTHORITATIVE",
                status="VERIFIED", ev=Evidence("SEC_REGISTRY", "submissions/nuevo",
                                               "re-confirmacion", "proc:sec"))
            idv.supersede_assertion(conn, aid, nueva=nueva)
            msg = sql_falla(conn, "UPDATE identity_v1.assertion SET evidence='inventado' "
                                  " WHERE assertion_id=:a", a=aid)
            registrar("editar assertion historica", "rechazado",
                      "rechazado" if "inmutable" in msg else msg or "ACEPTADO", msg[:120])

            # ---------------------------------------------------------------
            print("\nG) Publicar identidad sin evidencia")
            msg = sql_falla(conn,
                "INSERT INTO identity_v1.assertion (subject_type, entity_key, method, "
                "confidence, status) VALUES ('ENTITY_IDENTIFIER', :k, 'REGISTRY', "
                "'AUTHORITATIVE', 'VERIFIED')", k=cepu["entity_key"])
            registrar("assertion VERIFIED sin cita", "rechazado",
                      "rechazado" if "ck_verified_exige_evidencia" in msg else msg or "ACEPTADO",
                      msg[:120])
            msg = sql_falla(conn,
                "INSERT INTO identity_v1.assertion (subject_type, entity_key, method, "
                "confidence, status, source_id, source_record, evidence, resolved_by) "
                "VALUES ('ENTITY_IDENTIFIER', :k, 'DERIVED_RULE', 'AUTHORITATIVE', "
                "'VERIFIED', 'DERIVED_RULE', 'x', 'y', 'z')", k=cepu["entity_key"])
            registrar("regla derivada declarada AUTHORITATIVE", "rechazado",
                      "rechazado" if "ck_authoritative_metodo" in msg else msg or "ACEPTADO",
                      msg[:120])

            print("\n" + "=" * 78)
            fallas = [a for a in ATAQUES if not a[3]]
            print(f"ATAQUES: {len(ATAQUES)}   RECHAZADOS COMO CORRESPONDE: "
                  f"{len(ATAQUES) - len(fallas)}   FALLAS: {len(fallas)}")
            for f in fallas:
                print(f"   FALLA -> {f[0]}: esperado {f[1]}, obtenido {f[2]}")
            return 1 if fallas else 0
        finally:
            tx.rollback()
            print("\n(transaccion revertida: el piloto quedo intacto)")


if __name__ == "__main__":
    # solo al ejecutarse como script: importar no debe tocar sys.stdout
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")
    raise SystemExit(main())
