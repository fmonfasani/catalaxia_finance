#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fases I y J del ciclo 8. NO ejecuta CNV ni Market: solo mide.

FASE I  elegibilidad Identity -> Market  e  Identity -> CNV
FASE J  dossier de los 56 BYMA bloqueados, sin resolverlos
"""
from __future__ import annotations

import io
import json
import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from sqlalchemy import text  # noqa: E402

from engine import db as edb  # noqa: E402
from engine.config import load_settings  # noqa: E402

OUT = REPO / "outputs" / "docs" / "fase_identity"


def legacy():
    c = sqlite3.connect("file:" + str(REPO / "data" / "screener.db") + "?mode=ro", uri=True)
    filas = c.execute("SELECT entity_id, ticker_canonico, grupo, cuit, cik, nombre "
                      "FROM dim_entity").fetchall()
    c.close()
    return [dict(zip(("entity_id", "ticker", "grupo", "cuit", "cik", "nombre"), r))
            for r in filas]


def modulo11_cuit(v: str) -> bool:
    if not v or not v.isdigit() or len(v) != 11:
        return False
    pesos = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2]
    tot = sum(int(d) * p for d, p in zip(v[:10], pesos))
    resto = 11 - (tot % 11)
    dv = 0 if resto == 11 else (9 if resto == 10 else resto)
    return dv == int(v[10])


def main() -> int:
    s = load_settings()
    if s.is_prod:
        print("EXT-010: abortado.")
        return 2
    eng = edb.get_engine(s)
    OUT.mkdir(parents=True, exist_ok=True)

    with eng.connect() as conn:
        # ================= FASE I — elegibilidad ==========================
        print(f"FASE I · ELEGIBILIDAD CROSS-WORKSTREAM · {s.describe()}\n")

        con_cik = conn.execute(text(
            "SELECT count(DISTINCT entity_key) FROM identity_v1.identifier "
            " WHERE id_type='CIK' AND is_authoritative AND valid_to IS NULL")).scalar()

        # Identity -> CNV: exige CUIT autoritativo, y si la entidad esta anclada
        # en CIK, exige ademas el bridge CIK<->LEI ratificado por una PERSONA.
        cnv = conn.execute(text("""
            SELECT count(*) FROM identity_v1.v_entity_resolution v
             WHERE v.cuit IS NOT NULL
               AND (v.cik IS NULL OR EXISTS (
                     SELECT 1 FROM identity_v1.assertion a
                      WHERE a.subject_type='IDENTIFIER_BRIDGE' AND a.status='VERIFIED'
                        AND a.method='HUMAN_DECISION' AND a.valid_to IS NULL
                        AND a.resolved_by NOT LIKE 'proc:%'
                        AND a.left_ref='CIK:SEC:'||v.cik
                        AND a.right_ref='LEI:GLEIF:'||v.lei))""")).scalar()

        # Identity -> Market: Market opera por instrumento. La elegibilidad es
        # que la entidad tenga ancla autoritativa y que el legacy la asocie a un
        # ticker. NO se crea ningun vinculo aca: se cuenta.
        leg = legacy()
        ciks_db = {r[0] for r in conn.execute(text(
            "SELECT id_value FROM identity_v1.identifier "
            " WHERE id_type='CIK' AND is_authoritative AND valid_to IS NULL"))}
        market_ok = [f for f in leg
                     if str(f["cik"] or "").strip().isdigit()
                     and str(f["cik"]).strip().zfill(10) in ciks_db
                     and f["ticker"]]

        print(f"  entidades con CIK autoritativo          {con_cik}")
        print(f"  elegibles Identity -> Market            {len(market_ok)}"
              f"   (tienen ancla + ticker en el legacy)")
        print(f"  elegibles Identity -> CNV               {cnv}"
              f"   (CUIT autoritativo con bridge ratificado)")
        print(f"\n  La brecha entre {len(market_ok)} y {cnv} es G5: el CUIT exige una")
        print( "  decision humana por empresa, y hay 3 firmadas.")

        por_grupo = {}
        for f in market_ok:
            por_grupo[f["grupo"]] = por_grupo.get(f["grupo"], 0) + 1
        print(f"\n  elegibles Market por grupo: {por_grupo}")

        fase_i = {"entidades_con_cik": con_cik,
                  "elegibles_market": len(market_ok),
                  "elegibles_market_por_grupo": por_grupo,
                  "elegibles_cnv": cnv,
                  "nota": ("No se ejecuto CNV ni Market. Solo se midio elegibilidad. "
                           "La brecha Market/CNV es G5: ninguna fuente publica el "
                           "puente CIK<->LEI, asi que el CUIT exige ratificacion "
                           "humana por empresa.")}
        (OUT / "impacto_cross_workstream.json").write_text(
            json.dumps(fase_i, indent=2, ensure_ascii=False), encoding="utf-8")

        # ================= FASE J — dossier BYMA ==========================
        print(f"\n\nFASE J · DOSSIER BYMA BLOQUEADOS  (no se resuelve ninguno)\n")
        byma = [f for f in leg if f["grupo"] == "byma_only"]
        dossier = []
        for f in byma:
            cuit = str(f["cuit"] or "").strip()
            valido = modulo11_cuit(cuit)
            en_identity = conn.execute(text(
                "SELECT entity_key, is_authoritative, status FROM identity_v1.identifier "
                " WHERE id_type='CUIT' AND id_value=:c AND valid_to IS NULL"),
                {"c": cuit}).mappings().first()
            dossier.append({
                "entity_id": f["entity_id"],
                "ticker": f["ticker"],
                "nombre_legacy": f["nombre"],
                "cuit_legacy": cuit or None,
                "cuit_modulo11_valido": valido,
                "cik": None,
                "en_identity_v1": (dict(en_identity) if en_identity else None),
                "por_que_el_cuit_no_es_autoritativo": (
                    "La unica fuente que lo declara es LEGACY_DIM_ENTITY, cuyo "
                    "authority_level es CORROBORATING: puede proponer, nunca "
                    "establecer. La fila no tiene autor ni cita, y ya fallo antes "
                    "(el CIK de YPF)."),
                "por_que_no_hay_cik": (
                    "El emisor no cotiza en EEUU: SEC no le asigna CIK. No es un "
                    "dato faltante, es un identificador que no existe para el."),
                "consecuencia": (
                    "Sin CIK no hay ancla autoritativa desde la cual tender un "
                    "puente a GLEIF. Buscar su LEI por razon social es inferencia "
                    "(F-024: GLEIF devuelve DOS LEI para 'Banco Macro')."),
                "fuentes_posibles": [
                    {"fuente": "AFIP", "autoritativa_para": "CUIT",
                     "disponible": False,
                     "obstaculo": "captcha; no automatizable (ciclo 3D)"},
                    {"fuente": "GLEIF", "autoritativa_para": "LEI, CUIT",
                     "disponible": "parcial",
                     "obstaculo": ("requiere identificar el LEI correcto sin ancla; "
                                   "buscar por nombre es inferencia prohibida")},
                    {"fuente": "CNV_PORTAL", "autoritativa_para": "-",
                     "disponible": False,
                     "obstaculo": ("DISCOVERY_ONLY: no declara el CUIT del emisor "
                                   "(solo el del auditor). Y su perfil se consulta "
                                   "POR CUIT: es circular")},
                    {"fuente": "HUMAN", "autoritativa_para": "cualquiera",
                     "disponible": True,
                     "obstaculo": "requiere evidencia primaria que hoy no esta reunida"},
                ],
                "que_evidencia_faltaria": (
                    "Un documento de una fuente AUTHORITATIVE que ligue esta razon "
                    "social a ese CUIT: constancia de AFIP, o un registro de GLEIF "
                    "con registeredAt RA000009/RA000010 al que se llegue por un "
                    "identificador demostrado, no por el nombre."),
                "requiere_afip": True,
                "requiere_decision_humana": True,
                "estado": "BLOQUEADO_SIN_ANCLA_AUTORITATIVA",
            })

        n_val = sum(1 for d in dossier if d["cuit_modulo11_valido"])
        print(f"  emisores BYMA sin CIK                   {len(dossier)}")
        print(f"  con CUIT legacy que pasa modulo 11      {n_val}")
        print(f"  con CUIT legacy invalido o ausente      {len(dossier) - n_val}")
        print(f"  con CUIT autoritativo en identity_v1    "
              f"{sum(1 for d in dossier if (d['en_identity_v1'] or {}).get('is_authoritative'))}")
        print(f"  ratificados por este ciclo              0  (ninguno: es el punto)")
        malos = [d for d in dossier if not d["cuit_modulo11_valido"]]
        if malos:
            print(f"\n  CUIT legacy que NO pasa modulo 11:")
            for d in malos[:8]:
                print(f"    #{d['entity_id']:<5} {str(d['ticker']):<10} {d['cuit_legacy']!r}")

        (OUT / "BYMA_BLOCKED_DOSSIER.json").write_text(
            json.dumps({"total": len(dossier),
                        "cuit_modulo11_valido": n_val,
                        "ratificados_en_este_ciclo": 0,
                        "emisores": dossier}, indent=2, ensure_ascii=False),
            encoding="utf-8")
        print(f"\n  -> outputs/docs/fase_identity/BYMA_BLOCKED_DOSSIER.json")
        print(f"  -> outputs/docs/fase_identity/impacto_cross_workstream.json")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    raise SystemExit(main())
