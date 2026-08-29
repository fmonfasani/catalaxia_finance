#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Smoke cross-workstream SEC -> Identity v1 -> CNV.

LA REGLA DEL SMOKE
El CUIT con el que se consulta a la CNV sale **exclusivamente** de identity_v1,
y solo si la cadena que lo sostiene esta completa:

    CIK (SEC, autoritativo)
      -> bridge CIK<->LEI  VERIFIED, HUMAN_DECISION, firmado por una persona
      -> LEI (GLEIF, autoritativo)
      -> CUIT (GLEIF registeredAs, RA000009/RA000010) autoritativo y vigente

Si falta cualquier eslabon, el emisor se BLOQUEA. No se lee el CUIT de
`dim_entity`, ni de un CSV, ni del argumento de linea de comandos. Ese es todo
el punto del ejercicio: probar que la identidad puede *gobernar* el fetch.

Uso:
    python scripts/engine/smoke_cross_cnv.py --ticker YPF
    python scripts/engine/smoke_cross_cnv.py --ticker YPF --fetch
"""
from __future__ import annotations

import argparse
import io
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from sqlalchemy import text  # noqa: E402

from engine import db as edb  # noqa: E402
from engine.config import load_settings  # noqa: E402

# Que emisor es cual, por su CIK -- el unico identificador que SEC establece.
# No se resuelve por nombre ni por ticker (eso seria inferencia, F-024).
EMISORES = {
    "YPF":   "0000904851",
    "TGSU2": "0000931427",
    "CEPU":  "0001717161",
    "GGAL":  "0001071371",
}


def resolver_cuit(conn, cik: str) -> dict:
    """Devuelve el CUIT SOLO si toda la cadena esta demostrada."""
    out = {"cik": cik, "entity_key": None, "lei": None, "cuit": None,
           "bridge": None, "bloqueo": None}

    ek = conn.execute(text(
        "SELECT entity_key FROM identity_v1.identifier "
        " WHERE id_type='CIK' AND id_namespace='SEC' AND id_value=:c "
        "   AND is_authoritative AND valid_to IS NULL"), {"c": cik}).scalar()
    if not ek:
        out["bloqueo"] = "no hay entidad anclada en ese CIK autoritativo"
        return out
    out["entity_key"] = ek

    fila = conn.execute(text(
        "SELECT r.lei, r.cuit FROM identity_v1.v_entity_resolution r "
        " WHERE r.entity_key = :k"), {"k": ek}).mappings().first()
    out["lei"] = fila["lei"] if fila else None
    cuit = fila["cuit"] if fila else None

    if not out["lei"]:
        out["bloqueo"] = "la entidad no tiene LEI autoritativo vigente"
        return out

    br = conn.execute(text(
        "SELECT assertion_id, resolved_by, resolution_reason, confidence "
        "  FROM identity_v1.assertion "
        " WHERE subject_type='IDENTIFIER_BRIDGE' AND status='VERIFIED' "
        "   AND method='HUMAN_DECISION' AND valid_to IS NULL "
        "   AND left_ref='CIK:SEC:'||:c AND right_ref='LEI:GLEIF:'||:l"),
        {"c": cik, "l": out["lei"]}).mappings().first()
    if not br:
        out["bloqueo"] = ("el bridge CIK<->LEI no esta ratificado por una persona "
                          "(G5: no existe fuente primaria que lo publique)")
        return out
    if not br["resolved_by"] or br["resolved_by"].startswith("proc:"):
        out["bloqueo"] = f"el bridge lo firmo un proceso: {br['resolved_by']}"
        return out
    out["bridge"] = {"assertion_id": br["assertion_id"],
                     "ratificado_por": br["resolved_by"],
                     "confidence": br["confidence"]}

    if not cuit:
        out["bloqueo"] = "GLEIF no publica un CUIT utilizable para este LEI"
        return out
    out["cuit"] = cuit
    return out


def cnv_ya_tiene(conn, cuit: str, entity_key: str) -> dict:
    """Que hay HOY en CNV para esta entidad. No fetchea."""
    n_cuit = conn.execute(text(
        "SELECT count(*) FROM fetch_raw.cnv_presentation WHERE cuit = :c"),
        {"c": cuit}).scalar()
    n_ek = conn.execute(text(
        "SELECT count(*) FROM fetch_raw.cnv_presentation WHERE entity_key = :k"),
        {"k": entity_key}).scalar()
    return {"presentaciones_por_cuit": n_cuit, "presentaciones_por_entity_key": n_ek}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticker", required=True, choices=sorted(EMISORES))
    ap.add_argument("--fetch", action="store_true",
                    help="ejecuta c3_cnv_fetch.py con el CUIT resuelto")
    ap.add_argument("--scope", default="FINANCIERO")
    args = ap.parse_args()

    s = load_settings()
    if s.is_prod:
        print("EXT-010: abortado.")
        return 2
    eng = edb.get_engine(s)

    cik = EMISORES[args.ticker]
    print(f"SMOKE CROSS-WORKSTREAM · {args.ticker} · CIK {cik}")
    print(f"  {s.describe()}\n")

    with eng.connect() as conn:
        r = resolver_cuit(conn, cik)
        print("  identity_v1")
        print(f"    entity_key  {r['entity_key']}")
        print(f"    LEI         {r['lei']}")
        if r["bridge"]:
            print(f"    bridge      assertion #{r['bridge']['assertion_id']} "
                  f"ratificado por {r['bridge']['ratificado_por']} "
                  f"({r['bridge']['confidence']})")
        print(f"    CUIT        {r['cuit'] or '-'}")

        if r["bloqueo"]:
            print(f"\n  BLOQUEADO: {r['bloqueo']}")
            print("  No se consulta la CNV. El CUIT no se inventa.")
            _guardar(args.ticker, r, None)
            return 1

        antes = cnv_ya_tiene(conn, r["cuit"], r["entity_key"])
        print(f"\n  CNV antes   {antes}")

    if not args.fetch:
        print("\n  (ensayo: no se fetcheo. Usar --fetch para consultar la CNV)")
        _guardar(args.ticker, r, {"antes": antes})
        return 0

    print(f"\n  fetch CNV con CUIT {r['cuit']} (scope {args.scope}) ...")
    p = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "engine" / "c3_cnv_fetch.py"),
         "--cuit", r["cuit"], "--scope", args.scope],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(REPO))
    cola = (p.stdout or "").strip().splitlines()[-12:]
    for ln in cola:
        print("    " + ln)
    if p.returncode != 0:
        print(f"    STDERR: {(p.stderr or '')[-400:]}")

    with eng.connect() as conn:
        despues = cnv_ya_tiene(conn, r["cuit"], r["entity_key"])
    print(f"\n  CNV despues {despues}")
    _guardar(args.ticker, r, {"antes": antes, "despues": despues,
                              "returncode": p.returncode, "cola_stdout": cola})
    return 0


def _guardar(ticker, resolucion, cnv):
    d = REPO / "outputs" / "docs" / "fase_identity"
    d.mkdir(parents=True, exist_ok=True)
    f = d / f"smoke_cross_cnv_{ticker}.json"
    f.write_text(json.dumps(
        {"ticker": ticker, "ts_utc": datetime.now(timezone.utc).isoformat(),
         "resolucion_identity": resolucion, "cnv": cnv},
        indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n  evidencia -> {f.relative_to(REPO)}")


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    raise SystemExit(main())
