#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F-041 — evidencia estructurada para assertions historicas.

Contrato: docs/architecture/F041_CONTRACT.md

REGLA FUNDAMENTAL
No se reescribe el pasado. `source_facts` NO se edita en el lugar (aunque la
base hoy lo permita -- ver F-042): se afirma de nuevo y se supersede.

Modos:
    --clasificar   fase D: clasifica las 7, no escribe
    --aplicar      fase E: re-afirma las de clase B
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from sqlalchemy import text  # noqa: E402

from engine import db as edb  # noqa: E402
from engine.config import load_settings  # noqa: E402

PIPELINE_VERSION = "f041-reafirmacion-v1"
OUT = REPO / "outputs" / "docs" / "fase_identity"

CLASE_A = "A_ESTRUCTURABLE"          # vacia por contrato (§9)
CLASE_B = "B_REAFIRMABLE"
CLASE_C = "C_NO_ESTRUCTURABLE"
CLASE_D = "D_CONFLICTO"


def pendientes(conn) -> list[dict]:
    """Las assertions historicas sin evidencia estructurada. Se mide, no se asume."""
    return [dict(r) for r in conn.execute(text("""
        SELECT i.identifier_id, i.entity_key, i.id_value AS cik, i.status AS id_status,
               a.assertion_id, a.source_id, a.source_record, a.method, a.confidence,
               a.status AS a_status, a.resolved_by, a.created_at, a.evidence,
               (SELECT preferred_name FROM identity_v1.entity e
                 WHERE e.entity_key = i.entity_key) AS nombre
          FROM identity_v1.identifier i
          JOIN identity_v1.assertion a ON a.assertion_id = i.assertion_id
         WHERE i.id_type='CIK' AND i.is_authoritative AND i.valid_to IS NULL
           AND a.source_facts IS NULL
         ORDER BY a.assertion_id""")).mappings()]


def sha256_de(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def clasificar(fila: dict) -> dict:
    """Clasifica contra el ARTEFACTO, nunca contra el texto de `evidence`."""
    out = {**{k: (str(v) if k == "created_at" else v) for k, v in fila.items()},
           "clase": None, "motivo": None, "artefacto": None, "facts": None}
    cik = fila["cik"]

    if fila["source_id"] == "SEC_REGISTRY":
        p = REPO / "data" / "raw" / "submissions" / f"CIK{cik}.json"
        if not p.exists():
            out["clase"] = CLASE_C
            out["motivo"] = f"el artefacto declarado no esta en disco: {p.name}"
            return out
        s = json.load(open(p, encoding="utf-8"))
        declarado = str(s.get("cik", "")).zfill(10)
        if declarado != cik:
            out["clase"] = CLASE_D
            out["motivo"] = (f"el artefacto declara CIK {declarado}, la assertion "
                             f"afirma {cik}")
            return out
        out["clase"] = CLASE_B
        out["motivo"] = "el artefacto declarado existe y declara el mismo CIK"
        out["artefacto"] = f"data/raw/submissions/{p.name}"
        out["facts"] = {"cik": declarado, "sec_name": s.get("name"),
                        "tickers": s.get("tickers"), "exchanges": s.get("exchanges"),
                        "sic": s.get("sic"), "sic_description": s.get("sicDescription"),
                        "artefacto": f"data/raw/submissions/{p.name}",
                        "sha256": sha256_de(p)}
        return out

    if fila["source_id"] == "SEC_20F":
        # La assertion declara un DOCUMENTO (el 20-F del accession). Se busca
        # ese documento, no un sustituto.
        acc = (fila["source_record"] or "").replace("-", "")
        d = REPO / "data" / "raw" / "engine" / f"CIK{cik}" / "filings" / acc
        docs = sorted(d.glob("*.htm")) + sorted(d.glob("*.txt")) if d.exists() else []
        if docs:
            out["clase"] = CLASE_B
            out["motivo"] = "el documento del accession esta en disco"
            out["artefacto"] = str(docs[0].relative_to(REPO))
            out["facts"] = {"accession": fila["source_record"], "cik": cik,
                            "artefacto": str(docs[0].relative_to(REPO)),
                            "sha256": sha256_de(docs[0])}
            return out
        idx = d / "index.json"
        out["clase"] = CLASE_C
        out["motivo"] = (
            "el documento 20-F nunca se archivo. "
            + (f"Solo existe {idx.relative_to(REPO)}, que lista los archivos del "
               "directorio pero NO declara el CIK ni el form: el CIK vive en la "
               "ruta de SEC, no en el contenido. Estructurar desde ahi seria "
               "inferir." if idx.exists() else
               f"No hay nada bajo {d.relative_to(REPO)}."))
        # Se REGISTRA que el hecho esta corroborado por otra via, sin usarla
        # para estructurar esta assertion (eso cambiaria su fuente declarada).
        sub = REPO / "data" / "raw" / "submissions" / f"CIK{cik}.json"
        if sub.exists():
            s = json.load(open(sub, encoding="utf-8"))
            rec = (s.get("filings") or {}).get("recent") or {}
            accs = rec.get("accessionNumber") or []
            if fila["source_record"] in accs:
                i = accs.index(fila["source_record"])
                out["corroboracion_independiente"] = {
                    "fuente": "SEC_REGISTRY",
                    "artefacto": f"data/raw/submissions/{sub.name}",
                    "declara": {"accession": fila["source_record"],
                                "form": (rec.get("form") or [None])[i],
                                "filingDate": (rec.get("filingDate") or [None])[i],
                                "cik": str(s.get("cik", "")).zfill(10)},
                    "nota": ("El hecho es cierto y verificable, pero por una fuente "
                             "DISTINTA de la que esta assertion declara. Usarla aca "
                             "cambiaria que la sostiene.")}
        return out

    out["clase"] = CLASE_C
    out["motivo"] = f"no hay regla de estructuracion para la fuente {fila['source_id']}"
    return out


def reafirmar(conn, item: dict, run_id: str) -> dict:
    """Contrato §6. Cuatro pasos, una transaccion. No edita nada historico."""
    vieja = item["assertion_id"]
    cita = ("Re-afirmacion de la assertion #{} ({} {}) con evidencia estructurada. "
            "El hecho no cambia: {} declara el CIK {}. Verificado contra {} "
            "(sha256 {}). F-041.").format(
        vieja, item["source_id"], item["source_record"], item["source_id"],
        item["cik"], item["facts"]["artefacto"], item["facts"]["sha256"][:16])

    # 1 -- assertion nueva
    nueva = conn.execute(text("""
        INSERT INTO identity_v1.assertion
          (subject_type, entity_key, method, confidence, status, source_id,
           source_record, evidence, resolved_by, source_facts)
        VALUES ('ENTITY_IDENTIFIER', :k, :m, :c, 'VERIFIED', :src, :rec, :ev, :by,
                CAST(:f AS jsonb))
        RETURNING assertion_id"""),
        {"k": item["entity_key"], "m": item["method"], "c": item["confidence"],
         "src": item["source_id"], "rec": item["source_record"], "ev": cita,
         "by": f"proc:f041_reafirmacion@{run_id[:12]}",
         "f": json.dumps(item["facts"], ensure_ascii=False)}).scalar_one()

    # 2 -- retirar el identifier viejo ANTES de insertar el nuevo:
    #      ux_identifier_autoritativo_unico es parcial sobre valid_to IS NULL
    conn.execute(text(
        "UPDATE identity_v1.identifier SET valid_to = now(), status='RETIRED' "
        " WHERE identifier_id = :i"), {"i": item["identifier_id"]})

    # 3 -- identifier nuevo, mismo valor, misma entidad, apuntando a la nueva
    nuevo_id = conn.execute(text("""
        INSERT INTO identity_v1.identifier
          (entity_key, id_type, id_namespace, id_value, is_authoritative, status,
           assertion_id)
        VALUES (:k, 'CIK', 'SEC', :v, TRUE, 'ACTIVE', :a)
        RETURNING identifier_id"""),
        {"k": item["entity_key"], "v": item["cik"], "a": nueva}).scalar_one()

    # 4 -- encadenar: la vieja queda, cerrada y enlazada
    conn.execute(text(
        "UPDATE identity_v1.assertion SET valid_to = now(), superseded_by = :n "
        " WHERE assertion_id = :v"), {"n": nueva, "v": vieja})

    return {"cik": item["cik"], "nombre": item["nombre"],
            "assertion_vieja": vieja, "assertion_nueva": nueva,
            "identifier_viejo": item["identifier_id"], "identifier_nuevo": nuevo_id,
            "artefacto": item["facts"]["artefacto"]}


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--clasificar", action="store_true")
    g.add_argument("--aplicar", action="store_true")
    args = ap.parse_args()

    s = load_settings()
    if s.is_prod:
        print("EXT-010: abortado.")
        return 2
    eng = edb.get_engine(s)
    OUT.mkdir(parents=True, exist_ok=True)

    print(f"F-041 · {s.describe()}\n")
    with eng.connect() as conn:
        filas = pendientes(conn)
    items = [clasificar(f) for f in filas]

    print(f"  assertions sin evidencia estructurada: {len(items)}\n")
    print(f"  {'assert':>7} {'CIK':<12} {'fuente':<13} {'clase':<20} entidad")
    print("  " + "-" * 84)
    for it in items:
        print(f"  {it['assertion_id']:>7} {it['cik']:<12} {it['source_id']:<13} "
              f"{it['clase']:<20} {str(it['nombre'])[:28]}")
        if it["clase"] != CLASE_B:
            print(f"          -> {it['motivo'][:110]}")

    from collections import Counter
    resumen = Counter(it["clase"] for it in items)
    print(f"\n  {dict(resumen)}")

    doc = {"ts_utc": datetime.now(timezone.utc).isoformat(),
           "total": len(items), "resumen": dict(resumen), "items": items}
    (OUT / "f041_clasificacion.json").write_text(
        json.dumps(doc, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"  -> outputs/docs/fase_identity/f041_clasificacion.json")

    if args.clasificar:
        return 0

    objetivo = [it for it in items if it["clase"] == CLASE_B]
    if not objetivo:
        print("\n  nada que re-afirmar.")
        return 0

    print(f"\n  re-afirmando {len(objetivo)} (clase B) ...")
    with edb.run_scope(eng, s, PIPELINE_VERSION) as run:
        print(f"  run_id={run.run_id}")
        with eng.begin() as conn:
            hechos = [reafirmar(conn, it, run.run_id) for it in objetivo]
        run.status = "OK"
    for h in hechos:
        print(f"    {h['cik']}  assertion {h['assertion_vieja']} -> {h['assertion_nueva']}"
              f"   identifier {h['identifier_viejo']} -> {h['identifier_nuevo']}"
              f"   {str(h['nombre'])[:24]}")
    (OUT / "f041_reafirmacion.json").write_text(
        json.dumps({"run": PIPELINE_VERSION, "reafirmadas": hechos,
                    "deuda": [{"assertion_id": it["assertion_id"], "cik": it["cik"],
                               "clase": it["clase"], "motivo": it["motivo"],
                               "corroboracion_independiente":
                                   it.get("corroboracion_independiente")}
                              for it in items if it["clase"] != CLASE_B]},
                   indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n  -> outputs/docs/fase_identity/f041_reafirmacion.json")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    raise SystemExit(main())
