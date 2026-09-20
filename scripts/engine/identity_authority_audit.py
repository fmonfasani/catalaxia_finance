#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Auditoría de autoridad Identity/CNV — SOLO LECTURA.

Diez controles sobre la coherencia entre `identifier.is_authoritative`,
`identifier.status`, `identifier.valid_to` y `assertion.status`.

NO escribe. NO ejecuta VALIDATE CONSTRAINT. NO modifica nada.

Uso:
    python scripts/engine/identity_authority_audit.py
"""
from __future__ import annotations

import io
import json
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "outputs" / "docs" / "fase_identity"
CONT = "catalaxia-engine-dev"


def psql(q: str, intentos: int = 15) -> list[list[str]]:
    ultimo = ""
    for _ in range(intentos):
        try:
            p = subprocess.run(
                ["docker", "exec", CONT, "psql", "-U", "catalaxia", "-d", "catalaxia",
                 "-t", "-A", "-F", "\x1f", "-c", q],
                capture_output=True, text=True, encoding="utf-8", timeout=45)
        except subprocess.TimeoutExpired:
            ultimo = "timeout (base bloqueada por otro agente)"
            time.sleep(12)
            continue
        if p.returncode == 0:
            return [ln.split("\x1f") for ln in p.stdout.splitlines() if ln.strip()]
        ultimo = (p.stderr or "")[:200]
        time.sleep(12)
    raise SystemExit(f"psql bloqueado tras {intentos} intentos: {ultimo}")


def uno(q: str):
    r = psql(q)
    return r[0][0] if r else None


def seccion(t: str) -> None:
    print(f"\n{'─' * 74}\n{t}\n{'─' * 74}")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    ev: dict = {}
    print("AUDITORIA DE AUTORIDAD IDENTITY / CNV — solo lectura\n")

    # ═══ 1 · VERIFIED sin autoridad ═══
    seccion("1 · assertion VERIFIED + identifier NO autoritativo")
    r1 = psql("""
        SELECT i.id_type, count(*), count(DISTINCT i.id_value), count(DISTINCT i.entity_key)
          FROM identity_v1.identifier i
          JOIN identity_v1.assertion a ON a.assertion_id = i.assertion_id
         WHERE a.status = 'VERIFIED' AND NOT i.is_authoritative
         GROUP BY 1 ORDER BY 2 DESC""")
    ev["c1_verified_sin_autoridad"] = [
        {"id_type": x[0], "filas": int(x[1]), "valores": int(x[2]), "entidades": int(x[3])}
        for x in r1]
    if not r1:
        print("  ninguno")
    for x in r1:
        print(f"  {x[0]:<10} filas={int(x[1]):>5}  valores distintos={int(x[2]):>5}  "
              f"entidades={int(x[3]):>5}")
    r1v = psql("""
        SELECT count(*) FROM identity_v1.identifier i
          JOIN identity_v1.assertion a ON a.assertion_id = i.assertion_id
         WHERE a.status='VERIFIED' AND NOT i.is_authoritative
           AND i.valid_to IS NULL AND i.id_type='CUIT'""")
    print(f"\n  de esos, CUIT vigentes: {r1v[0][0]}   <- los que podrian habilitar CNV")
    ev["c1_cuit_vigentes"] = int(r1v[0][0])

    # ═══ 2 · autoritativo sin VERIFIED ═══
    seccion("2 · identifier autoritativo + assertion != VERIFIED")
    r2 = psql("""
        SELECT i.id_type, a.status, count(*), bool_or(i.valid_to IS NULL)
          FROM identity_v1.identifier i
          JOIN identity_v1.assertion a ON a.assertion_id = i.assertion_id
         WHERE i.is_authoritative AND a.status <> 'VERIFIED'
         GROUP BY 1,2 ORDER BY 3 DESC""")
    ev["c2_autoritativo_sin_verified"] = [
        {"id_type": x[0], "assertion_status": x[1], "filas": int(x[2]),
         "alguno_vigente": x[3] == "t"} for x in r2]
    print("  ninguno" if not r2 else "")
    for x in r2:
        print(f"  {x[0]:<10} assertion={x[1]:<16} filas={int(x[2]):>4} "
              f"alguno_vigente={x[3]}")

    # ═══ 3 · autoritativo con status != ACTIVE ═══
    seccion("3 · identifier autoritativo + identifier.status != ACTIVE")
    r3 = psql("""
        SELECT i.id_type, i.status, count(*),
               count(*) FILTER (WHERE i.valid_to IS NULL) AS vigentes
          FROM identity_v1.identifier i
         WHERE i.is_authoritative AND i.status <> 'ACTIVE'
         GROUP BY 1,2 ORDER BY 3 DESC""")
    ev["c3_autoritativo_no_active"] = [
        {"id_type": x[0], "identifier_status": x[1], "filas": int(x[2]),
         "vigentes": int(x[3])} for x in r3]
    print("  ninguno" if not r3 else "")
    for x in r3:
        print(f"  {x[0]:<10} status={x[1]:<10} filas={int(x[2]):>4} vigentes={int(x[3]):>4}")

    # ═══ 4 · autoritativo con valid_to cerrado ═══
    seccion("4 · identifier autoritativo + valid_to IS NOT NULL (cerrado)")
    r4 = psql("""
        SELECT i.id_type, i.status, count(*), min(i.valid_to)::date::text,
               max(i.valid_to)::date::text
          FROM identity_v1.identifier i
         WHERE i.is_authoritative AND i.valid_to IS NOT NULL
         GROUP BY 1,2 ORDER BY 3 DESC""")
    ev["c4_autoritativo_cerrado"] = [
        {"id_type": x[0], "status": x[1], "filas": int(x[2]),
         "desde": x[3], "hasta": x[4]} for x in r4]
    print("  ninguno" if not r4 else "")
    for x in r4:
        print(f"  {x[0]:<10} status={x[1]:<10} filas={int(x[2]):>4}  "
              f"cerrados entre {x[3]} y {x[4]}")

    # ═══ 5 · mas de un CUIT autoritativo ACTIVE por entidad ═══
    seccion("5 · mas de un CUIT autoritativo ACTIVE vigente por entidad")
    r5 = psql("""
        SELECT entity_key, count(*), string_agg(id_value, ', ')
          FROM identity_v1.identifier
         WHERE id_type='CUIT' AND is_authoritative AND status='ACTIVE'
           AND valid_to IS NULL
         GROUP BY entity_key HAVING count(*) > 1""")
    ev["c5_multiples_autoritativos"] = [
        {"entity_key": x[0], "n": int(x[1]), "cuits": x[2]} for x in r5]
    print(f"  entidades con mas de uno: {len(r5)}")
    for x in r5:
        print(f"    {x[0]} -> {x[1]} CUIT: {x[2]}")

    # ═══ 6 · violaciones del CHECK NOT VALID ═══
    seccion("6 · ck_cuit_exige_evidencia_estructurada — violaciones sin VALIDATE")
    total_cuit_ver = uno("""
        SELECT count(*) FROM identity_v1.assertion
         WHERE left_ref LIKE 'CUIT:%' AND status='VERIFIED'""")
    viol = psql("""
        SELECT assertion_id::text, coalesce(source_id,'(null)'),
               coalesce(resolved_by,''), left(coalesce(source_facts::text,'(null)'), 90)
          FROM identity_v1.assertion
         WHERE left_ref LIKE 'CUIT:%' AND status='VERIFIED'
           AND NOT (CASE source_id
             WHEN 'GLEIF'   THEN coalesce(source_facts->>'registeredAt','') IN ('RA000009','RA000010')
                             AND coalesce(source_facts->>'registeredAs','') <> ''
             WHEN 'SEC_20F' THEN coalesce(source_facts->>'accession','') <> ''
                             AND coalesce(source_facts->>'seccion','') <> ''
             WHEN 'AFIP'    THEN coalesce(source_facts->>'constancia','') <> ''
             WHEN 'HUMAN'   THEN coalesce(source_facts->>'reviewer','') <> ''
                             AND coalesce(source_facts->>'decision_ref','') <> ''
             ELSE false END)""")
    print(f"  assertions CUIT VERIFIED en total : {total_cuit_ver}")
    print(f"  que VIOLARIAN el constraint       : {len(viol)}")
    for v in viol[:10]:
        print(f"    assertion {v[0]} source={v[1]} por={v[2]}")
        print(f"      source_facts: {v[3]}")
    ev["c6"] = {"cuit_verified_total": int(total_cuit_ver), "violaciones": len(viol),
                "detalle": [{"assertion_id": v[0], "source_id": v[1],
                             "resolved_by": v[2], "source_facts": v[3]} for v in viol]}

    # ═══ 7 · duplicados del importador ═══
    seccion("7 · los grupos duplicados, completos")
    r7 = psql("""
        SELECT i.entity_key, i.id_value, a.method, coalesce(a.resolved_by,''),
               count(*), string_agg(i.identifier_id::text, ',' ORDER BY i.identifier_id),
               string_agg(DISTINCT a.status, ','),
               count(DISTINCT coalesce(a.evidence::text,'')),
               count(DISTINCT coalesce(a.source_id,'')),
               count(DISTINCT coalesce(a.source_record,'')),
               count(DISTINCT a.confidence)
          FROM identity_v1.identifier i
          JOIN identity_v1.assertion a ON a.assertion_id = i.assertion_id
         WHERE i.id_type='CUIT' AND i.valid_to IS NULL AND NOT i.is_authoritative
         GROUP BY 1,2,3,4 HAVING count(*) > 1
         ORDER BY 5 DESC""")
    print(f"  grupos con mas de una fila vigente: {len(r7)}\n")
    print(f"  {'CUIT':<12} {'n':>3} {'estados':<12} {'ev':>3} {'src':>4} {'rec':>4} {'conf':>5}  entity_key")
    semanticos = 0
    for x in r7:
        distintos = int(x[7]) + int(x[8]) + int(x[9]) + int(x[10])
        idem = distintos == 4          # 1 valor distinto en cada uno de los 4 campos
        semanticos += 1 if idem else 0
        print(f"  {x[1]:<12} {int(x[4]):>3} {x[6]:<12} {int(x[7]):>3} {int(x[8]):>4} "
              f"{int(x[9]):>4} {int(x[10]):>5}  {x[0]}")
    print(f"\n  duplicados SEMANTICOS (evidencia/fuente/registro/confianza identicos): "
          f"{semanticos}/{len(r7)}")
    ev["c7_duplicados"] = [
        {"entity_key": x[0], "cuit": x[1], "method": x[2], "resolved_by": x[3],
         "filas": int(x[4]), "identifier_ids": x[5], "estados": x[6],
         "evidencias_distintas": int(x[7]), "sources_distintos": int(x[8]),
         "records_distintos": int(x[9]), "confianzas_distintas": int(x[10])}
        for x in r7]
    ev["c7_semanticos"] = semanticos

    # ═══ 8 · lo que la regla propuesta seleccionaria ═══
    seccion("8 · efecto de la regla propuesta sobre el universo actual")
    r8 = psql("""
        SELECT count(*) FILTER (WHERE i.is_authoritative AND i.status='ACTIVE'
                                 AND i.valid_to IS NULL),
               count(*) FILTER (WHERE i.valid_to IS NULL),
               count(DISTINCT i.id_value) FILTER (WHERE i.valid_to IS NULL)
          FROM identity_v1.identifier i WHERE i.id_type='CUIT'""")[0]
    print(f"  CUIT que habilita la regla propuesta  : {r8[0]}")
    print(f"  filas CUIT vigentes en total          : {r8[1]}")
    print(f"  CUIT distintos vigentes               : {r8[2]}")
    actual = uno("""
        SELECT count(DISTINCT e.entity_key) FROM identity_v1.entity e
         WHERE (SELECT max(a.status) FROM identity_v1.identifier i
                  JOIN identity_v1.assertion a ON a.assertion_id=i.assertion_id
                 WHERE i.entity_key=e.entity_key AND i.id_type='CUIT'
                   AND i.valid_to IS NULL) = 'VERIFIED'""")
    print(f"  entidades que habilita la regla ACTUAL (max) : {actual}")
    ev["c8"] = {"regla_propuesta": int(r8[0]), "filas_vigentes": int(r8[1]),
                "cuit_distintos": int(r8[2]), "regla_actual_max": int(actual)}

    (OUT / "identity_authority_audit.json").write_text(
        json.dumps(ev, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n  evidencia -> outputs/docs/fase_identity/identity_authority_audit.json")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    raise SystemExit(main())
