#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fase A — ingesta SEC del universo de demostracion.

Conduce S02 -> S03 -> S04 por emisor, con el mecanismo oficial y sin tocar
ninguna de las tres etapas mas alla de su parametrizacion por CIK.

El formulario NO se asume: un emisor privado extranjero presenta 20-F y uno
domestico 10-K. Cada empresa declara el suyo. Si se equivocara, S02 encontraria
0 filings y la corrida quedaria registrada como tal, no inventaria nada.

Uso:
    python scripts/engine/fundamentals_universo.py                 # las 7 pendientes
    python scripts/engine/fundamentals_universo.py --solo AAPL
"""
from __future__ import annotations

import argparse
import io
import json
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

OUT = REPO / "outputs" / "docs" / "fase_producto"

# ticker -> (CIK, formularios anuales, filings a traer)
# El formulario sale del tipo de emisor, no de una suposicion:
#   20-F  emisor privado extranjero (los cuatro argentinos)
#   10-K  emisor domestico de EE.UU.
UNIVERSO = {
    "YPF":   ("0000904851", "20-F,20-F/A", None),   # ya ingerido: 9 filings
    "CEPU":  ("0001717161", "20-F,20-F/A", 2),
    "TGSU2": ("0000931427", "20-F,20-F/A", 2),
    "GGAL":  ("0001114700", "20-F,20-F/A", 2),
    "BMA":   ("0001347426", "20-F,20-F/A", 2),
    "AAPL":  ("0000320193", "10-K,10-K/A", 2),
    "MSFT":  ("0000789019", "10-K,10-K/A", 2),
    "NVDA":  ("0001045810", "10-K,10-K/A", 2),
}


def correr(cmd: list[str], etiqueta: str) -> tuple[bool, str]:
    t0 = time.time()
    p = subprocess.run([sys.executable] + cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", cwd=str(REPO))
    salida = (p.stdout or "") + (p.stderr or "")
    ok = p.returncode == 0 and "gate          = PASS" not in salida.replace("gate    ", "gate  ") \
        or p.returncode == 0
    cola = [ln for ln in salida.splitlines() if ln.strip()][-1:] or [""]
    print(f"      {etiqueta:<6} rc={p.returncode} {time.time()-t0:5.1f}s  {cola[0][:96]}")
    return p.returncode == 0, salida


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--solo", default=None, help="un solo ticker del universo")
    ap.add_argument("--incluir-ypf", action="store_true",
                    help="reingerir YPF (por defecto se saltea: ya tiene 9 filings)")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    objetivo = {args.solo: UNIVERSO[args.solo]} if args.solo else dict(UNIVERSO)
    if not args.solo and not args.incluir_ypf:
        objetivo.pop("YPF", None)

    resultados = []
    for tk, (cik, forms, maxf) in objetivo.items():
        print(f"\n=== {tk} · CIK {cik} · {forms} ===")
        r = {"ticker": tk, "cik": cik, "forms": forms, "max_filings": maxf}

        cmd = ["scripts/engine/s02_fetch_ypf.py", "--cik", cik, "--forms", forms]
        if maxf:
            cmd += ["--max-filings", str(maxf)]
        ok2, out2 = correr(cmd, "S02")
        r["s02"] = "OK" if ok2 else "FALLO"
        if not ok2:
            r["s02_detalle"] = out2[-400:]
            resultados.append(r)
            continue

        ok3, out3 = correr(["scripts/engine/s03_parse_ypf.py", "--cik", cik,
                            "--min-xbrl", "1"], "S03")
        r["s03"] = "OK" if ok3 else "FALLO"
        if not ok3:
            r["s03_detalle"] = out3[-400:]
            resultados.append(r)
            continue

        ok4, out4 = correr(["scripts/engine/s04_normalize.py"], "S04")
        r["s04"] = "OK" if ok4 else "FALLO"
        if not ok4:
            r["s04_detalle"] = out4[-400:]
        resultados.append(r)

    print("\n--- resumen ---")
    for r in resultados:
        print(f"  {r['ticker']:<6} S02={r.get('s02','-'):<6} S03={r.get('s03','-'):<6} "
              f"S04={r.get('s04','-')}")
    (OUT / "ingesta_universo.json").write_text(
        json.dumps(resultados, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n  -> {OUT.name}/ingesta_universo.json")
    return 0 if all(r.get("s04") == "OK" for r in resultados) else 1


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    raise SystemExit(main())
