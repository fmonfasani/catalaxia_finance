#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Backfill del universo CIK en Identity v1.

Contrato: docs/architecture/IDENTITY_BACKFILL_CIK_CONTRACT.md

LA REGLA CENTRAL
Un CIK autoritativo permite ANCLAR la entidad. Nada mas. No implica CUIT, no
implica LEI, y no autoriza a fusionar por nombre, ticker o domicilio.

El CIK que trae la fila legacy NO es evidencia: es un valor a verificar contra
un artefacto primario de SEC. F-024 mostro por que (dim_entity#572 traia el CIK
de Macro Bank en la columna `cuit`).

Modos:
    --inventario   clasifica el universo, no escribe        (fase C)
    --dry-run      simula el backfill completo, no escribe  (fase D)
    --aplicar      escribe                                  (fase F)
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from sqlalchemy import text  # noqa: E402

from engine import db as edb  # noqa: E402
from engine import identity_v1 as idv  # noqa: E402
from engine.config import load_settings  # noqa: E402
from engine.identity_v1 import Evidence  # noqa: E402

PIPELINE_VERSION = "identity-backfill-cik-v1"
OUT = REPO / "outputs" / "docs" / "fase_identity"

# Clases del inventario (fase C del enunciado)
CLASE_A = "A_CIK_AUTORITATIVO_ENTIDAD_EXISTENTE"
CLASE_B = "B_CIK_AUTORITATIVO_ENTIDAD_INEXISTENTE"
CLASE_C = "C_CIK_CONFLICTIVO"
CLASE_D = "D_CIK_INVALIDO"
CLASE_E = "E_CIK_AUSENTE"
CLASE_F = "F_ENTIDAD_PROVISIONAL_SIN_ANCLA"


# ---------------------------------------------------------------------------
# Fuentes primarias de SEC -- la unica autoridad sobre el CIK
# ---------------------------------------------------------------------------

def cargar_catalogo_sec() -> dict[str, dict]:
    """CIK -> fila del catalogo oficial. Sin esto no se ancla nada."""
    archivos = sorted((REPO / "data" / "raw" / "catalogo_edgar").glob("company_tickers*.json"))
    if not archivos:
        return {}
    d = json.load(open(archivos[-1], encoding="utf-8"))
    filas = d.values() if isinstance(d, dict) else d
    out = {}
    for e in filas:
        cik = str(e.get("cik_str", "")).zfill(10)
        if cik and cik != "0000000000":
            out.setdefault(cik, {"cik_str": e["cik_str"], "ticker": e.get("ticker"),
                                 "title": e.get("title"),
                                 "_archivo": archivos[-1].name})
    return out


def submissions_de(cik: str) -> dict | None:
    p = REPO / "data" / "raw" / "submissions" / f"CIK{cik}.json"
    if not p.exists():
        return None
    s = json.load(open(p, encoding="utf-8"))
    return {"name": s.get("name"), "sic": s.get("sic"), "tickers": s.get("tickers"),
            "sicDescription": s.get("sicDescription"),
            "exchanges": s.get("exchanges"), "_archivo": p.name}


def normalizar_cik(v) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    if not s or not s.isdigit():
        return None
    s = s.zfill(10)
    return s if len(s) == 10 else None


# ---------------------------------------------------------------------------
# Universo legacy
# ---------------------------------------------------------------------------

def universo_legacy() -> list[dict]:
    c = sqlite3.connect("file:" + str(REPO / "data" / "screener.db") + "?mode=ro", uri=True)
    filas = c.execute(
        "SELECT entity_id, ticker_canonico, grupo, cuit, cik, nombre FROM dim_entity"
    ).fetchall()          # materializado: reusar el cursor ya costo tres bugs
    c.close()
    return [dict(zip(("entity_id", "ticker", "grupo", "cuit", "cik", "nombre"), r))
            for r in filas]


# ---------------------------------------------------------------------------
# FASE C -- inventario
# ---------------------------------------------------------------------------

def clasificar(conn, fila: dict, catalogo: dict) -> dict:
    """Clasifica SIN escribir. El CIK legacy es un candidato, no una verdad."""
    out = {"entity_id": fila["entity_id"], "ticker": fila["ticker"],
           "grupo": fila["grupo"], "nombre_legacy": fila["nombre"],
           "cik_legacy": fila["cik"], "cuit_legacy": fila["cuit"],
           "cik": None, "clase": None, "motivo": None, "entity_key": None}

    cik = normalizar_cik(fila["cik"])
    if cik is None:
        out["clase"] = CLASE_E
        out["motivo"] = ("el legacy no declara un CIK utilizable"
                         if not fila["cik"] else
                         f"CIK con formato invalido: {fila['cik']!r}")
        return out

    # El contrato acepta CUALQUIERA de los dos artefactos primarios de SEC.
    # La primera version exigia solo `company_tickers` y clasificaba a EXXON
    # (CIK 34088) y a ELECTRONIC ARTS (712515) como CIK invalidos. No lo son:
    # `submissions/CIK<n>.json` los declara con su razon social y su ticker. Lo
    # que pasa es que el catalogo hoy mapea XOM al CIK 2115436 ("ExxonMobil
    # Holdings Corp") -- una sucesion societaria. El CIK viejo sigue siendo un
    # CIK real de SEC; lo que cambio es a quien apunta el TICKER.
    #
    # Corregir eso por ticker seria la inferencia prohibida (es el caso
    # COUR/Coursera). Aca solo se ancla la entidad en su CIK.
    out["cik"] = cik
    sub = submissions_de(cik)
    if cik not in catalogo and sub is None:
        out["clase"] = CLASE_D
        out["motivo"] = ("SEC no reconoce ese CIK ni en company_tickers ni en "
                         "submissions: el valor del legacy no es evidencia y no hay "
                         "artefacto primario que lo respalde")
        return out

    if cik in catalogo:
        out["sec"] = catalogo[cik]
        out["fuente_cik"] = "company_tickers"
    else:
        out["sec"] = {"cik_str": int(cik), "ticker": (sub.get("tickers") or [None])[0],
                      "title": sub.get("name"), "_archivo": sub["_archivo"]}
        out["fuente_cik"] = "submissions"
        out["nota"] = ("el catalogo actual no lista este CIK; SEC lo declara en "
                       "submissions. Puede ser sucesion societaria: el ticker del "
                       "legacy hoy apunta a otro CIK. NO se resuelve por ticker.")

    duenio = conn.execute(text(
        "SELECT entity_key FROM identity_v1.identifier "
        " WHERE id_type='CIK' AND id_namespace='SEC' AND id_value=:c "
        "   AND is_authoritative AND valid_to IS NULL"), {"c": cik}).scalar()
    if duenio:
        out["entity_key"] = duenio
        out["clase"] = CLASE_A
        out["motivo"] = "el CIK ya ancla una entidad existente"
        # ¿lo reclama tambien OTRA fila legacy? eso es conflicto de universo
        return out

    out["clase"] = CLASE_B
    out["motivo"] = "CIK verificado contra SEC, sin entidad todavia"
    return out


def marcar_conflictos(inventario: list[dict]) -> None:
    """Dos filas legacy que reclaman el MISMO CIK son un conflicto, no un duplicado."""
    por_cik = Counter(r["cik"] for r in inventario if r["cik"] and r["clase"] in (CLASE_A, CLASE_B))
    for r in inventario:
        if r["cik"] and por_cik.get(r["cik"], 0) > 1:
            r["clase"] = CLASE_C
            r["motivo"] = (f"{por_cik[r['cik']]} filas del legacy reclaman el CIK {r['cik']}: "
                           f"no se elige una por nombre ni por ticker")


def provisionales_sin_ancla(conn) -> list[dict]:
    filas = conn.execute(text(
        "SELECT e.entity_key, e.preferred_name, e.entity_status FROM identity_v1.entity e "
        " WHERE NOT EXISTS (SELECT 1 FROM identity_v1.identifier i "
        "                    WHERE i.entity_key=e.entity_key AND i.is_authoritative "
        "                      AND i.valid_to IS NULL)")).mappings().all()
    return [{"entity_key": f["entity_key"], "nombre": f["preferred_name"],
             "entity_status": f["entity_status"], "clase": CLASE_F,
             "motivo": "entidad sin ningun identificador autoritativo vigente"}
            for f in filas]


# ---------------------------------------------------------------------------
# FASES D / F -- backfill
# ---------------------------------------------------------------------------

def procesar(conn, item: dict, run_id: str) -> dict:
    """Ancla UNA entidad en su CIK. No hace nada mas.

    Devuelve el plan de lo ocurrido. En DRY-RUN el llamador revierte.
    """
    ev_out = {"entity_id": item["entity_id"], "cik": item["cik"],
              "accion": None, "entity_key": None, "identifier": None,
              "review": None, "conflict": None}
    sec = item["sec"]
    sub = submissions_de(item["cik"])

    cita = ("SEC company_tickers {}: cik_str={} ticker={} title={!r}".format(
        sec["_archivo"], sec["cik_str"], sec.get("ticker"), sec.get("title")))
    facts = {"cik_str": sec["cik_str"], "ticker_sec": sec.get("ticker"),
             "title": sec.get("title"), "fuente": sec["_archivo"]}
    if sub:
        cita += "; SEC {}: name={!r} sic={} ({}) exchanges={}".format(
            sub["_archivo"], sub["name"], sub["sic"], sub["sicDescription"], sub["exchanges"])
        facts.update({"sec_name": sub["name"], "sic": sub["sic"],
                      "exchanges": sub["exchanges"]})

    nombre = (sub or {}).get("name") or sec.get("title") or item["nombre_legacy"]
    key, creada = idv.resolve_or_create_entity(
        conn, preferred_name=nombre, id_type="CIK", id_namespace="SEC",
        id_value=item["cik"], country=None)
    ev_out["entity_key"] = key
    ev_out["accion"] = "CREADA" if creada else "REUTILIZADA"

    r = idv.assert_identifier(
        conn, entity_key=key, id_type="CIK", id_namespace="SEC", id_value=item["cik"],
        method="REGISTRY",
        evidence=Evidence("SEC_REGISTRY", sec["_archivo"], cita,
                          f"proc:backfill_cik@{run_id[:12]}", facts=facts))
    ev_out["identifier"] = r.status

    # El CUIT legacy se PROPONE como candidato debil y jamas se ancla en el.
    # Es explicitamente la causa raiz de F-032: LEGACY_DIM_ENTITY es
    # CORROBORATING y nunca llega a autoritativo.
    cuit = (item.get("cuit_legacy") or "").strip()
    if cuit and cuit.isdigit() and len(cuit) == 11:
        rc = idv.assert_identifier(
            conn, entity_key=key, id_type="CUIT", id_namespace="AFIP", id_value=cuit,
            method="REGISTRY",
            evidence=Evidence("LEGACY_DIM_ENTITY", f"sqlite:dim_entity#{item['entity_id']}",
                              f"fila legacy sin autor declarado; CUIT propuesto: {cuit}",
                              f"proc:backfill_cik@{run_id[:12]}"))
        ev_out["cuit_legacy_status"] = rc.status
    return ev_out


def hash_identidad(conn) -> str:
    """Huella del estado de identidad. Para comparar contenido, no conteos."""
    filas = conn.execute(text(
        "SELECT e.entity_key, e.preferred_name, e.entity_status, "
        "       i.id_type, i.id_namespace, i.id_value, i.is_authoritative, i.status "
        "  FROM identity_v1.entity e "
        "  LEFT JOIN identity_v1.identifier i "
        "         ON i.entity_key=e.entity_key AND i.valid_to IS NULL "
        " ORDER BY 1,4,5,6")).all()
    h = hashlib.sha256()
    for f in filas:
        h.update(("|".join("" if x is None else str(x) for x in f) + "\n").encode())
    return h.hexdigest()


def contar(conn) -> dict:
    q = lambda s: conn.execute(text(s)).scalar()
    return {
        "entidades": q("SELECT count(*) FROM identity_v1.entity"),
        "identifiers_vigentes": q("SELECT count(*) FROM identity_v1.identifier WHERE valid_to IS NULL"),
        "identifiers_autoritativos": q("SELECT count(*) FROM identity_v1.identifier "
                                       " WHERE is_authoritative AND valid_to IS NULL"),
        "cik_autoritativos": q("SELECT count(*) FROM identity_v1.identifier "
                               " WHERE id_type='CIK' AND is_authoritative AND valid_to IS NULL"),
        "cuit_autoritativos": q("SELECT count(*) FROM identity_v1.identifier "
                                " WHERE id_type='CUIT' AND is_authoritative AND valid_to IS NULL"),
        "assertions": q("SELECT count(*) FROM identity_v1.assertion"),
        "reviews_open": q("SELECT count(*) FROM identity_v1.review WHERE status='OPEN'"),
        "conflicts": q("SELECT count(*) FROM identity_v1.conflict"),
    }


# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--inventario", action="store_true")
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--aplicar", action="store_true")
    ap.add_argument("--limite", type=int, default=None)
    args = ap.parse_args()

    s = load_settings()
    if s.is_prod:
        print("EXT-010: abortado.")
        return 2
    eng = edb.get_engine(s)
    OUT.mkdir(parents=True, exist_ok=True)

    catalogo = cargar_catalogo_sec()
    if not catalogo:
        print("BLOCK: no hay catalogo de SEC en data/raw/catalogo_edgar/. "
              "Sin fuente primaria no se ancla nada.")
        return 1
    legacy = universo_legacy()
    print(f"BACKFILL CIK  ·  {s.describe()}")
    print(f"  catalogo SEC: {len(catalogo)} CIK   ·   legacy: {len(legacy)} filas\n")

    with eng.connect() as conn:
        inventario = [clasificar(conn, f, catalogo) for f in legacy]
        marcar_conflictos(inventario)
        huerfanas = provisionales_sin_ancla(conn)

    resumen = Counter(r["clase"] for r in inventario)
    print("  inventario del universo legacy")
    for cl in (CLASE_A, CLASE_B, CLASE_C, CLASE_D, CLASE_E):
        print(f"    {cl:<44} {resumen.get(cl, 0)}")
    print(f"    {CLASE_F:<44} {len(huerfanas)}  (ya en identity_v1)")
    print("\n  por grupo legacy")
    for grp, n in Counter(r["grupo"] for r in inventario).most_common():
        sin_cik = sum(1 for r in inventario if r["grupo"] == grp and r["clase"] == CLASE_E)
        print(f"    {str(grp):<12} total={n:<5} sin CIK={sin_cik}")

    elegibles = [r for r in inventario if r["clase"] in (CLASE_A, CLASE_B)]
    print(f"\n  ELEGIBLES para backfill (A + B): {len(elegibles)}")

    doc = {"ts_utc": datetime.now(timezone.utc).isoformat(),
           "catalogo_sec": len(catalogo), "legacy": len(legacy),
           "resumen": dict(resumen), "provisionales_sin_ancla": len(huerfanas),
           "elegibles": len(elegibles),
           "por_grupo": {str(k): v for k, v in Counter(r["grupo"] for r in inventario).items()},
           "inventario": inventario, "sin_ancla": huerfanas}
    f = OUT / "backfill_cik_inventory.json"
    f.write_text(json.dumps(doc, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"  inventario -> {f.relative_to(REPO)}")

    if args.inventario:
        return 0

    # -------- DRY-RUN / APLICAR ------------------------------------------
    objetivo = elegibles[:args.limite] if args.limite else elegibles
    modo = "APLICAR" if args.aplicar else "DRY-RUN (se revierte)"
    print(f"\n  modo: {modo}   ·   a procesar: {len(objetivo)}")

    with edb.run_scope(eng, s, PIPELINE_VERSION) as run:
        print(f"  run_id={run.run_id}")
        conn = eng.connect()
        try:
            # `contar` y `hash_identidad` hacen autobegin: la transaccion se abre
            # ANTES de leer, o `conn.begin()` explota con "already initialized".
            tx = conn.begin()
            antes, h_antes = contar(conn), hash_identidad(conn)
            eventos, errores = [], []
            for i, item in enumerate(objetivo, 1):
                sp = conn.begin_nested()
                try:
                    eventos.append(procesar(conn, item, run.run_id))
                    sp.commit()
                except Exception as e:
                    sp.rollback()
                    errores.append({"entity_id": item["entity_id"], "cik": item["cik"],
                                    "error": f"{type(e).__name__}: {str(e)[:200]}"})
                if i % 100 == 0:
                    print(f"    {i}/{len(objetivo)}")
            despues, h_despues = contar(conn), hash_identidad(conn)
            tx.commit() if args.aplicar else tx.rollback()
            run.status = "OK"

            acc = Counter(e["accion"] for e in eventos)
            ids = Counter(e["identifier"] for e in eventos)
            print(f"\n  entidades   CREADAS={acc.get('CREADA', 0)}  "
                  f"REUTILIZADAS={acc.get('REUTILIZADA', 0)}")
            print(f"  CIK         {dict(ids)}")
            print(f"  CUIT legacy {dict(Counter(e.get('cuit_legacy_status') for e in eventos if e.get('cuit_legacy_status')))}")
            print(f"  errores     {len(errores)}")
            for e in errores[:5]:
                print(f"     {e['entity_id']} {e['cik']}: {e['error'][:110]}")
            print("\n  delta")
            for k in antes:
                d = despues[k] - antes[k]
                print(f"    {k:<28} {antes[k]:>6} -> {despues[k]:>6}  ({d:+d})")
            print(f"    hash identidad  {h_antes[:16]} -> {h_despues[:16]}")

            rep = {"modo": modo, "run_id": run.run_id, "procesados": len(objetivo),
                   "acciones": dict(acc), "identifier_status": dict(ids),
                   "errores": errores, "antes": antes, "despues": despues,
                   "hash_antes": h_antes, "hash_despues": h_despues,
                   "eventos": eventos}
            nombre = "backfill_cik_apply.json" if args.aplicar else "backfill_cik_dryrun.json"
            (OUT / nombre).write_text(json.dumps(rep, indent=2, ensure_ascii=False),
                                      encoding="utf-8")
            print(f"\n  reporte -> outputs/docs/fase_identity/{nombre}")
        finally:
            conn.close()
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    raise SystemExit(main())
