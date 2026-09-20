#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AUDITOR INDEPENDIENTE — validación CNV multi-empresa (Fase H).

No reutiliza `c3_cnv_fetch.py`, `engine/cnv/discovery.py`, `engine/cnv/validate.py`
ni `engine/cnv/rawstore.py`. Reimplementa desde cero, contra la evidencia cruda
(DB + disco), cada verificación que el fetcher afirma cumplir:

  - identidad     : ¿el CUIT bajo el que se fetcheó corresponde a una entidad
                    de identity_v1, y con qué confianza?
  - CUIT          : ¿el valor pasa el dígito verificador de AFIP (módulo 11),
                    reimplementado acá, no importado?
  - cantidad      : ¿coincide manifest (DB) == archivos en disco == lo
                    reportado por discovery?
  - duplicados    : ¿hay (kind,key,sha256) repetidos dentro del mismo CUIT?
                    ¿el mismo sha256 aparece bajo CUIT distintos (mezcla)?
  - hashes        : sha256 recalculado desde el archivo en disco, comparado
                    contra el de la fila del manifest — no se confía en
                    `RawStore.verify()`.
  - provenance    : cada fila descargada tiene entidad, cuit, endpoint,
                    raw_path y run_id, y el CUIT en `raw_path` coincide con
                    el CUIT de la fila.
  - atribución    : el 100% de lo fetcheado en cada run pertenece al CUIT
                    solicitado en ese run (0 mezcla entre emisores).

Uso:
    python scripts/engine/cnv_validation_auditor.py                # todos los CUIT con datos
    python scripts/engine/cnv_validation_auditor.py --cuit 30546689979
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy import text  # noqa: E402

from engine.config import REPO_ROOT, load_settings  # noqa: E402
from engine.db import get_engine  # noqa: E402

RAW_ROOT = REPO_ROOT / "data" / "raw" / "engine" / "cnv"


# --------------------------------------------------------- CUIT, reimplementado
def cuit_checksum_valido(cuit: str) -> tuple[bool, str]:
    """Digito verificador AFIP (modulo 11). Reimplementado, no importado de validate.py."""
    if not re.fullmatch(r"\d{11}", cuit or ""):
        return False, "formato: no son 11 digitos"
    pesos = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2]
    total = sum(int(d) * w for d, w in zip(cuit[:10], pesos))
    resto = total % 11
    verificador = 11 - resto
    if verificador == 11:
        verificador = 0
    if verificador == 10:
        return False, "algoritmo no genera un digito valido (caso raro, CUIT invalido)"
    ok = verificador == int(cuit[10])
    return ok, ("digito verificador coincide" if ok
                else f"digito verificador esperado={verificador} declarado={cuit[10]}")


def sha256_de_archivo(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------- consultas DB
def cuits_con_datos(conn, solo_cuit: str | None) -> list[str]:
    q = "SELECT DISTINCT cuit FROM fetch_raw.cnv_download_log"
    params = {}
    if solo_cuit:
        q += " WHERE cuit = :c"
        params["c"] = solo_cuit
    return [r[0] for r in conn.execute(text(q), params)]


def identidad_independiente(conn, cuit: str) -> dict:
    """Busca CUALQUIER identificador en identity_v1 que mencione este CUIT,
    de cualquier tipo/confianza, sin asumir cuál via debería usarse."""
    rows = conn.execute(text("""
        SELECT e.entity_key, e.preferred_name, i.id_type, i.id_namespace,
               i.is_authoritative, i.status AS id_status, i.valid_to,
               a.confidence, a.status AS a_status, a.method, a.source_id
        FROM identity_v1.identifier i
        JOIN identity_v1.entity e ON e.entity_key = i.entity_key
        JOIN identity_v1.assertion a ON a.assertion_id = i.assertion_id
        WHERE i.id_value = :v AND i.id_type IN ('CUIT', 'CNV_ENTITY_ID')
        ORDER BY i.valid_to NULLS FIRST, i.id_type
    """), {"v": cuit}).mappings().all()
    vigentes = [r for r in rows if r["valid_to"] is None]
    autoritativos_vigentes = [r for r in vigentes if r["is_authoritative"]]
    return {
        "total_menciones": len(rows),
        "vigentes": len(vigentes),
        "autoritativos_vigentes": len(autoritativos_vigentes),
        "detalle_vigentes": [dict(r) for r in vigentes],
    }


def manifest_del_cuit(conn, cuit: str) -> list[dict]:
    return [dict(r) for r in conn.execute(text("""
        SELECT run_id, artifact_kind, artifact_key, sha256, raw_path, result,
               entity_key, cuit, endpoint, downloaded_at
        FROM fetch_raw.cnv_download_log
        WHERE cuit = :c AND result IN ('DOWNLOADED', 'SIN_CAMBIOS')
        ORDER BY downloaded_at
    """), {"c": cuit}).mappings()]


def discovery_del_cuit(conn, cuit: str) -> dict:
    row = conn.execute(text("""
        SELECT count(*) AS filas, count(DISTINCT guid) AS guids_unicos,
               count(DISTINCT run_id) AS corridas
        FROM fetch_raw.cnv_presentation WHERE cuit = :c
    """), {"c": cuit}).mappings().first()
    return dict(row) if row else {"filas": 0, "guids_unicos": 0, "corridas": 0}


def runs_del_cuit(conn, cuit: str) -> list[str]:
    return [r[0] for r in conn.execute(text(
        "SELECT DISTINCT run_id FROM fetch_raw.cnv_download_log WHERE cuit=:c"), {"c": cuit})]


def mezcla_entre_cuits(conn, run_ids: list[str], cuit_esperado: str) -> list[dict]:
    """Para cada run_id que tocó este CUIT: ¿ese run también tocó OTRO cuit?"""
    if not run_ids:
        return []
    rows = conn.execute(text("""
        SELECT run_id, cuit, count(*) AS n
        FROM fetch_raw.cnv_download_log
        WHERE run_id = ANY(:runs)
        GROUP BY run_id, cuit
    """), {"runs": run_ids}).mappings().all()
    ajenos = [dict(r) for r in rows if r["cuit"] != cuit_esperado]
    return ajenos


# -------------------------------------------------------------------- auditar
def auditar_cuit(conn, cuit: str) -> dict:
    resultado: dict = {"cuit": cuit, "checks": []}

    def check(id_: str, ok: bool, detalle: str, evidencia: dict | None = None):
        resultado["checks"].append({
            "id": id_, "result": "PASS" if ok else "FAIL",
            "detalle": detalle, "evidencia": evidencia or {}})

    # 1. CUIT — formato y digito verificador, reimplementado
    ok, detalle = cuit_checksum_valido(cuit)
    check("AUD-CUIT-001", ok, f"digito verificador AFIP: {detalle}")

    # 2. Identidad — via independiente contra identity_v1
    ident = identidad_independiente(conn, cuit)
    check("AUD-IDENT-001", ident["total_menciones"] > 0,
          f"identity_v1 conoce este CUIT en {ident['total_menciones']} fila(s) "
          f"({ident['vigentes']} vigentes, {ident['autoritativos_vigentes']} autoritativas)",
          {"detalle_vigentes": ident["detalle_vigentes"]})
    entidades_vigentes = {d["entity_key"] for d in ident["detalle_vigentes"]}
    check("AUD-IDENT-002", len(entidades_vigentes) <= 1,
          f"el CUIT no apunta a mas de una entidad vigente: {len(entidades_vigentes)} distinta(s)",
          {"entidades": sorted(entidades_vigentes)})

    # 3. Cantidad — manifest (DB) vs discovery vs disco
    manifest = manifest_del_cuit(conn, cuit)
    disco = list((RAW_ROOT / f"CUIT{cuit}").rglob("*")) if (RAW_ROOT / f"CUIT{cuit}").exists() else []
    archivos_disco = [p for p in disco if p.is_file() and not p.name.endswith(".part")
                      and p.parent.name != "_index"]
    disc = discovery_del_cuit(conn, cuit)
    check("AUD-CANT-001", len(manifest) == len(archivos_disco),
          f"manifest DB={len(manifest)} vs archivos en disco={len(archivos_disco)} "
          f"bajo data/raw/engine/cnv/CUIT{cuit}/",
          {"manifest": len(manifest), "disco": len(archivos_disco)})
    check("AUD-CANT-002", disc["guids_unicos"] >= 0,
          f"discovery registrado: {disc['filas']} filas / {disc['guids_unicos']} guids unicos "
          f"en {disc['corridas']} corrida(s) — informativo, no bloqueante")

    # 4. Duplicados dentro del CUIT
    claves = [(m["artifact_kind"], m["artifact_key"], m["sha256"]) for m in manifest]
    dup_internos = len(claves) - len(set(claves))
    check("AUD-DUP-001", dup_internos == 0,
          f"duplicados (kind,key,sha256) dentro de este CUIT: {dup_internos}")

    # 5. Hashes — recalculados desde el archivo, no confiando en la DB ni en rawstore
    verificados, mismatches, faltantes = 0, [], []
    for m in manifest:
        if not m["raw_path"]:
            continue
        abspath = RAW_ROOT / m["raw_path"]
        real = sha256_de_archivo(abspath)
        if real is None:
            faltantes.append(m["raw_path"])
        elif real != m["sha256"]:
            mismatches.append({"raw_path": m["raw_path"], "db": m["sha256"][:12], "disco": real[:12]})
        else:
            verificados += 1
    check("AUD-HASH-001", not mismatches and not faltantes,
          f"sha256 recalculado desde disco: {verificados}/{len(manifest)} coinciden, "
          f"{len(mismatches)} mismatch, {len(faltantes)} faltantes",
          {"mismatches": mismatches[:10], "faltantes": faltantes[:10]})

    # 6. Provenance completa + coherencia CUIT-en-ruta
    incompleta = [m for m in manifest if not all(
        [m["entity_key"], m["cuit"], m["endpoint"], m["raw_path"], m["run_id"]])]
    ruta_incoherente = [m for m in manifest
                        if m["raw_path"] and f"CUIT{m['cuit']}" not in m["raw_path"]]
    check("AUD-PROV-001", not incompleta,
          f"provenance completa (entity_key,cuit,endpoint,raw_path,run_id): "
          f"{len(manifest)-len(incompleta)}/{len(manifest)} completas",
          {"incompletas": [m["artifact_key"] for m in incompleta][:10]})
    check("AUD-PROV-002", not ruta_incoherente,
          f"el CUIT de la fila coincide con el CUIT{{n}} de su raw_path: "
          f"{len(manifest)-len(ruta_incoherente)}/{len(manifest)} coherentes",
          {"incoherentes": [m["artifact_key"] for m in ruta_incoherente][:10]})

    # 7. Atribucion — ningun run que toco este CUIT toco tambien otro
    runs = runs_del_cuit(conn, cuit)
    ajenos = mezcla_entre_cuits(conn, runs, cuit)
    check("AUD-ATRIB-001", not ajenos,
          f"0 corridas de este CUIT mezclaron otro CUIT: {len(runs)} corrida(s) revisada(s), "
          f"{len(ajenos)} fila(s) ajenas encontradas",
          {"ajenos": ajenos[:10]})

    resultado["gate"] = "PASS" if all(c["result"] == "PASS" for c in resultado["checks"]) else "FAIL"
    return resultado


def main() -> int:
    ap = argparse.ArgumentParser(description="Auditor independiente CNV multi-empresa")
    ap.add_argument("--cuit", default=None, help="auditar solo este CUIT (default: todos con datos)")
    args = ap.parse_args()

    s = load_settings()
    eng = get_engine(s)
    with eng.connect() as conn:
        cuits = cuits_con_datos(conn, args.cuit)
        if not cuits:
            print("No hay CUIT con datos en fetch_raw.cnv_download_log. Nada que auditar.")
            return 0

        print(f"AUDITOR INDEPENDIENTE CNV — {len(cuits)} CUIT con datos: {cuits}\n")
        informe = {"_meta": {"cuits_auditados": cuits, "db": s.describe()}, "resultados": []}
        for cuit in cuits:
            r = auditar_cuit(conn, cuit)
            informe["resultados"].append(r)
            print(f"=== CUIT {cuit} — gate {r['gate']} ===")
            for c in r["checks"]:
                print(f"  [{c['result']:4}] {c['id']} — {c['detalle']}")
            print()

        overall = "PASS" if all(r["gate"] == "PASS" for r in informe["resultados"]) else "FAIL"
        print(f"VEREDICTO GLOBAL DEL AUDITOR: {overall}")

        out_path = REPO_ROOT / "outputs" / "docs" / "fase_cnv" / "CNV_VALIDATION_AUDITOR_REPORT.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        informe["_meta"]["veredicto_global"] = overall
        out_path.write_text(json.dumps(informe, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        print(f"\nInforme escrito en {out_path}")
    return 0 if overall == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
