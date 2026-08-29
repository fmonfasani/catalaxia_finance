#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Auditoria independiente del smoke SEC -> Identity v1 -> CNV.

No confia en el reporte del smoke. Reconstruye todo desde la base y el RAW.

Un resultado de 0 documentos se CLASIFICA, nunca se reporta como "sin datos":

  A  LA EMPRESA NO ESTA EN LA CNV
     el perfil respondio y no declara presentaciones. Ausencia real.
  B  ESTA PERO NUNCA SE FETCHEO
     no hay RAW para ese CUIT. Ausencia de ejecucion, no de dato.
  C  SE FETCHEO Y EL FETCH FALLO
     hay RAW y hay presentaciones en el, pero no llegaron a la base.
     Es un defecto del cargador -- el caso de F-039.
  D  EL CUIT NO PUDO RESOLVERSE
     Identity v1 bloqueo antes de consultar. Es el comportamiento correcto.

Uso:
    python scripts/engine/audit_cross_cnv.py
"""
from __future__ import annotations

import io
import json
import re
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from sqlalchemy import text  # noqa: E402

from engine import db as edb  # noqa: E402
from engine.config import load_settings  # noqa: E402

RAW = REPO / "data" / "raw" / "engine" / "cnv"

EMISORES = {"YPF": "0000904851", "TGSU2": "0000931427",
            "CEPU": "0001717161", "GGAL": "0001071371"}


def cuit_de_identity(conn, cik: str):
    """Reimplementado, no importado del smoke: es una auditoria."""
    r = conn.execute(text("""
        SELECT i.entity_key, v.lei, v.cuit,
               (SELECT a.resolved_by FROM identity_v1.assertion a
                 WHERE a.subject_type='IDENTIFIER_BRIDGE' AND a.status='VERIFIED'
                   AND a.method='HUMAN_DECISION' AND a.valid_to IS NULL
                   AND a.left_ref='CIK:SEC:'||i.id_value
                   AND a.right_ref='LEI:GLEIF:'||v.lei) AS ratificado_por
          FROM identity_v1.identifier i
          JOIN identity_v1.v_entity_resolution v USING (entity_key)
         WHERE i.id_type='CIK' AND i.id_namespace='SEC' AND i.id_value=:c
           AND i.is_authoritative AND i.valid_to IS NULL"""),
        {"c": cik}).mappings().first()
    return dict(r) if r else None


def raw_de(cuit: str) -> list[Path]:
    d = RAW / f"CUIT{cuit}" / "empresa"
    return sorted(d.glob("*.html")) if d.exists() else []


def presentaciones_en_raw(paths: list[Path]) -> int:
    """Cuenta GUIDs unicos en el RAW, sin usar el parser del pipeline."""
    guids = set()
    for p in paths:
        guids |= set(re.findall(
            r"publicview/([0-9a-fA-F-]{36})", p.read_text(encoding="utf-8", errors="replace")))
    return len(guids)


def clasificar(ident, raws, n_raw, n_db) -> tuple[str, str]:
    if ident is None or not ident.get("cuit"):
        return "D", "Identity v1 no pudo resolver el CUIT; bloqueo antes de consultar"
    if n_db > 0:
        return "-", f"{n_db} presentaciones (GUIDs unicos) cargadas"
    if not raws:
        return "B", "el CUIT resuelve pero nunca se fetcheo: no hay RAW"
    if n_raw == 0:
        return "A", "el perfil respondio y no declara presentaciones: ausencia real"
    return "C", (f"el RAW declara {n_raw} presentaciones y la base tiene 0: "
                 f"defecto del cargador")


def main() -> int:
    s = load_settings()
    if s.is_prod:
        print("EXT-010: abortado.")
        return 2
    eng = edb.get_engine(s)
    salida = {}

    print(f"AUDITORIA CROSS-WORKSTREAM  ·  {s.describe()}\n")
    print(f"  {'ticker':<8} {'CUIT':<13} {'ratificado':<12} {'RAW':>7} {'DB':>7}  clase")
    print("  " + "-" * 76)

    with eng.connect() as conn:
        for tk, cik in EMISORES.items():
            ident = cuit_de_identity(conn, cik)
            cuit = (ident or {}).get("cuit")
            raws = raw_de(cuit) if cuit else []
            n_raw = presentaciones_en_raw(raws) if raws else 0
            # OJO CON EL GRANO: la UNIQUE es (run_id, guid). `cnv_presentation`
            # es raw inmutable VERSIONADO POR CORRIDA -- N corridas dejan N
            # copias de cada GUID, y eso es correcto, no duplicacion. Contar
            # filas da un multiplo del universo real. Se cuentan GUIDs unicos.
            fila_db = conn.execute(text(
                "SELECT count(DISTINCT guid), count(DISTINCT run_id), count(*) "
                "  FROM fetch_raw.cnv_presentation WHERE cuit=:c"),
                {"c": cuit}).one() if cuit else (0, 0, 0)
            n_db, n_corridas, n_filas = fila_db

            clase, motivo = clasificar(ident, raws, n_raw, n_db)
            print(f"  {tk:<8} {str(cuit or '-'):<13} "
                  f"{str((ident or {}).get('ratificado_por') or '-'):<12} "
                  f"{n_raw:>7} {n_db:>7}  {clase}  {motivo}")
            if n_db and n_raw != n_db:
                print(f"           RAW y DB no coinciden: {n_raw} vs {n_db} GUIDs")

            det = {"cik": cik, "cuit": cuit,
                   "entity_key": (ident or {}).get("entity_key"),
                   "bridge_ratificado_por": (ident or {}).get("ratificado_por"),
                   "raw_archivos": [p.name for p in raws],
                   "presentaciones_en_raw": n_raw,
                   "guids_en_db": n_db, "corridas": n_corridas if cuit else 0,
                   "filas_db_todas_las_corridas": n_filas if cuit else 0,
                   "clase": clase, "motivo": motivo}
            if n_db:
                det["relaciones"] = {k or "AUSENTE": v for k, v in Counter(
                    dict(conn.execute(text(
                        "SELECT relacion, count(DISTINCT guid) FROM fetch_raw.cnv_presentation "
                        " WHERE cuit=:c GROUP BY 1"), {"c": cuit}).all())).items()}
                det["autorreferencias"] = conn.execute(text(
                    "SELECT count(DISTINCT guid) FROM fetch_raw.cnv_presentation "
                    " WHERE cuit=:c AND es_autorreferencia"), {"c": cuit}).scalar()
            salida[tk] = det

        # --- controles que no dependen de ningun emisor -------------------
        print("\n  controles transversales")
        ctrl = {}
        ctrl["cuits_en_cnv_sin_identidad"] = [r[0] for r in conn.execute(text(
            "SELECT DISTINCT p.cuit FROM fetch_raw.cnv_presentation p "
            " WHERE NOT EXISTS (SELECT 1 FROM identity_v1.identifier i "
            "                    WHERE i.id_type='CUIT' AND i.id_value=p.cuit "
            "                      AND i.is_authoritative AND i.valid_to IS NULL)"))]
        ctrl["relaciones_fuera_del_dominio"] = [r[0] for r in conn.execute(text(
            "SELECT DISTINCT relacion FROM fetch_raw.cnv_presentation "
            " WHERE relacion IS NOT NULL "
            "   AND relacion NOT IN ('CONTROLADA','VINCULADA','CONTROLANTE')"))]
        ctrl["autorreferencias_sin_marcar"] = conn.execute(text(
            "SELECT count(*) FROM fetch_raw.cnv_presentation "
            " WHERE cuit_relacionado = cuit AND NOT es_autorreferencia")).scalar()
        ctrl["cuit_no_autoritativo_usado"] = conn.execute(text(
            "SELECT count(*) FROM identity_v1.identifier "
            " WHERE id_type='CUIT' AND is_authoritative AND valid_to IS NULL "
            "   AND assertion_id IN (SELECT assertion_id FROM identity_v1.assertion "
            "                         WHERE status <> 'VERIFIED')")).scalar()
        for k, v in ctrl.items():
            estado = "OK" if (v == 0 or v == []) else "REVISAR"
            print(f"    {estado:<8} {k:<36} {v}")
        salida["_controles"] = ctrl

    f = REPO / "outputs" / "docs" / "fase_identity" / "audit_cross_cnv.json"
    f.write_text(json.dumps(salida, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n  evidencia -> {f.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    raise SystemExit(main())
