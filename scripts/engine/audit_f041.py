#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Auditoria INDEPENDIENTE de F-041 (ciclo 9, fase H).

No importa `f041_reafirmacion`. Reconstruye desde PostgreSQL y desde los
artefactos primarios, y responde para CADA assertion:

    "¿Por que esta assertion tiene estos source_facts?"

recalculando el sha256 del artefacto y cotejando cada campo declarado.
"""
from __future__ import annotations

import hashlib
import io
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from sqlalchemy import text  # noqa: E402

from engine import db as edb  # noqa: E402
from engine.config import load_settings  # noqa: E402

OUT = REPO / "outputs" / "docs" / "fase_identity"

# entity_key que cada CIK designaba ANTES de la re-afirmacion, tomado del
# reporte de reproduccion de la fase A. Si alguno cambio, el ancla se movio.
ANCLA_ANTES = {
    "0000904851": "E01M0X99C8F87H9TH9N39H2D1NW",
    "0001717161": "E01M0X99DQ7P5TQ4Z6Z58RC5PB3",
    "0001114700": "E01M0X99EXSQTYKWZMDEMMBX8QY",
    "0000931427": "E01M0X99G29RBSSFSGAM5S1QZMT",
    "0000320193": "E01M13XBSM8ZWPXACZAG2H149JX",
}


def main() -> int:
    s = load_settings()
    if s.is_prod:
        print("EXT-010: abortado.")
        return 2
    eng = edb.get_engine(s)
    hallazgos, ctrl = [], {}

    def check(nombre, ok, detalle=""):
        ctrl[nombre] = {"ok": bool(ok), "detalle": str(detalle)}
        print(f"    {'OK     ' if ok else 'FALLA  '} {nombre:<46} {detalle}")
        if not ok:
            hallazgos.append(f"{nombre}: {detalle}")

    print(f"AUDITORIA INDEPENDIENTE · F-041 · {s.describe()}\n")

    with eng.connect() as conn:
        # ---- las 6 re-afirmadas, una por una -------------------------------
        print("  ¿por que esta assertion tiene estos source_facts?\n")
        nuevas = conn.execute(text("""
            SELECT a.assertion_id, a.source_id, a.source_record, a.resolved_by,
                   a.source_facts, a.evidence, i.id_value AS cik, i.entity_key,
                   i.identifier_id,
                   (SELECT v.assertion_id FROM identity_v1.assertion v
                     WHERE v.superseded_by = a.assertion_id) AS supersede_a
              FROM identity_v1.assertion a
              JOIN identity_v1.identifier i ON i.assertion_id = a.assertion_id
             WHERE a.resolved_by LIKE 'proc:f041_reafirmacion%'
               AND i.is_authoritative AND i.valid_to IS NULL
             ORDER BY a.assertion_id""")).mappings().all()

        verificadas = 0
        for f in nuevas:
            facts = f["source_facts"] or {}
            art = REPO / (facts.get("artefacto") or "")
            lineas = []
            ok = True
            if not art.exists():
                lineas.append("el artefacto declarado NO existe"); ok = False
            else:
                real = hashlib.sha256(art.read_bytes()).hexdigest()
                if real != facts.get("sha256"):
                    lineas.append(f"sha256 no coincide ({real[:12]} vs "
                                  f"{str(facts.get('sha256'))[:12]})"); ok = False
                else:
                    lineas.append(f"sha256 recalculado coincide: {real[:16]}")
                d = json.load(open(art, encoding="utf-8"))
                if str(d.get("cik", "")).zfill(10) != f["cik"]:
                    lineas.append("el artefacto declara OTRO CIK"); ok = False
                else:
                    lineas.append(f"el artefacto declara cik={f['cik']}")
                if facts.get("sec_name") != d.get("name"):
                    lineas.append("sec_name no sale del artefacto"); ok = False
            if f["supersede_a"] is None:
                lineas.append("no supersede ninguna assertion"); ok = False
            verificadas += ok
            print(f"    #{f['assertion_id']}  CIK {f['cik']}  "
                  f"(supersede #{f['supersede_a']})")
            for ln in lineas:
                print(f"        {'OK ' if ok else '?? '} {ln}")

        check("las 6 re-afirmadas verifican contra su artefacto",
              verificadas == len(nuevas) == 6, f"{verificadas}/{len(nuevas)}")

        # ---- el pasado sigue ahi -------------------------------------------
        viejas = conn.execute(text("""
            SELECT a.assertion_id, a.source_id, a.source_record, a.evidence,
                   a.resolved_by, a.created_at, a.valid_to, a.superseded_by
              FROM identity_v1.assertion a
             WHERE a.superseded_by IS NOT NULL ORDER BY a.assertion_id""")).mappings().all()
        check("las 6 assertions historicas siguen existiendo", len(viejas) == 6,
              f"{len(viejas)}")
        check("cada historica conserva su provenance original",
              all(v["source_id"] and v["source_record"] and v["evidence"]
                  and v["resolved_by"] and v["created_at"] for v in viejas))
        check("cada historica quedo cerrada y encadenada",
              all(v["valid_to"] and v["superseded_by"] for v in viejas))
        check("ninguna historica fue firmada por f041",
              not any("f041" in (v["resolved_by"] or "") for v in viejas))

        retirados = conn.execute(text(
            "SELECT count(*) FROM identity_v1.identifier "
            " WHERE status='RETIRED' AND valid_to IS NOT NULL")).scalar()
        check("los 6 identifiers viejos quedaron RETIRED con fecha", retirados == 6,
              f"{retirados}")

        # ---- EL ANCLA NO SE MOVIO -------------------------------------------
        movidas = []
        for cik, esperada in ANCLA_ANTES.items():
            actual = conn.execute(text(
                "SELECT entity_key FROM identity_v1.identifier "
                " WHERE id_type='CIK' AND id_value=:c AND is_authoritative "
                "   AND valid_to IS NULL"), {"c": cik}).scalar()
            if actual != esperada:
                movidas.append((cik, esperada, actual))
        check("cada CIK designa la MISMA entidad que antes", not movidas, movidas)

        # ---- no se invento nada ---------------------------------------------
        inventados = conn.execute(text("""
            SELECT count(*) FROM identity_v1.assertion
             WHERE resolved_by LIKE 'proc:f041%'
               AND (source_facts->>'artefacto' IS NULL
                    OR source_facts->>'sha256' IS NULL)""")).scalar()
        check("ninguna re-afirmacion sin artefacto y sha256", inventados == 0,
              f"{inventados}")

        cambio_fuente = conn.execute(text("""
            SELECT count(*) FROM identity_v1.assertion n
              JOIN identity_v1.assertion v ON v.superseded_by = n.assertion_id
             WHERE n.source_id <> v.source_id OR n.source_record <> v.source_record
                OR n.entity_key <> v.entity_key OR n.method <> v.method""")).scalar()
        check("la re-afirmacion no cambio fuente, registro, entidad ni metodo",
              cambio_fuente == 0, f"{cambio_fuente}")

        # ---- la deuda esta declarada ----------------------------------------
        deuda = conn.execute(text("""
            SELECT a.assertion_id, a.source_id, i.id_value
              FROM identity_v1.identifier i
              JOIN identity_v1.assertion a ON a.assertion_id = i.assertion_id
             WHERE i.id_type='CIK' AND i.is_authoritative AND i.valid_to IS NULL
               AND a.source_facts IS NULL""")).all()
        print(f"\n  deuda declarada: {len(deuda)}")
        for d in deuda:
            doc = REPO / "data" / "raw" / "engine" / f"CIK{d[2]}" / "filings"
            print(f"    assertion #{d[0]}  {d[1]}  CIK {d[2]}  "
                  f"-> el documento no esta bajo {doc.relative_to(REPO)}")
        check("la deuda es exactamente 1 y es la de SEC_20F",
              len(deuda) == 1 and deuda[0][1] == "SEC_20F", f"{deuda}")

        # ---- nada colateral --------------------------------------------------
        check("CUIT autoritativos siguen siendo 3",
              conn.execute(text("SELECT count(*) FROM identity_v1.identifier "
                                " WHERE id_type='CUIT' AND is_authoritative "
                                "   AND valid_to IS NULL")).scalar() == 3)
        check("entidades sin cambio (525)",
              conn.execute(text("SELECT count(*) FROM identity_v1.entity")).scalar() == 525)
        check("CIK autoritativos sin cambio (513)",
              conn.execute(text("SELECT count(*) FROM identity_v1.identifier "
                                " WHERE id_type='CIK' AND is_authoritative "
                                "   AND valid_to IS NULL")).scalar() == 513)
        check("cero corridas RUNNING",
              conn.execute(text("SELECT count(*) FROM engine.runs "
                                "WHERE status='RUNNING'")).scalar() == 0)

        # ---- el hueco de F-042 esta tapado ------------------------------------
        cubre = conn.execute(text(
            "SELECT prosrc LIKE '%source_facts%' FROM pg_proc "
            " WHERE proname='fn_assertion_inmutable'")).scalar()
        check("el trigger de inmutabilidad cubre source_facts (F-042)", cubre)

    veredicto = ("CLOSED_WITH_NOTES" if not hallazgos else "BLOCKED")
    print(f"\n  VEREDICTO F-041: {veredicto}")
    for h in hallazgos:
        print(f"    - {h}")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "audit_f041.json").write_text(
        json.dumps({"veredicto": veredicto, "controles": ctrl,
                    "hallazgos": hallazgos}, indent=2, ensure_ascii=False),
        encoding="utf-8")
    print("  evidencia -> outputs/docs/fase_identity/audit_f041.json")
    return 0 if not hallazgos else 1


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    raise SystemExit(main())
