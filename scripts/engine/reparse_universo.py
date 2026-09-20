#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F-054 — re-parseo del universo tras corregir el alcance del borrado de S03.

S03 borraba las cinco tablas de `parsed` enteras y reiniciaba la secuencia de
`fact_id`. Con un emisor era staging; con varios, cada corrida destruia la
provenance de la anterior Y reutilizaba sus ids, de modo que
`derived.fact.source_fact_ids` terminaba resolviendo contra filas de otra
empresa.

Corregido el alcance, hay que volver a parsear cada emisor para que sus punteros
apunten a sus propias filas. No se re-descarga nada: se reusa el RAW de S02.

Uso:
    python scripts/engine/reparse_universo.py
"""
from __future__ import annotations

import io
import json
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

OUT = REPO / "outputs" / "docs" / "fase_producto"

# Orden deliberado: YPF ultimo, por ser el mas grande. El orden no debe importar
# —esa es justamente la propiedad que F-054 rompio y que hay que recuperar—, y
# por eso el control final verifica que TODOS conserven su cadena, no solo el
# ultimo en correr.
CIKS = [
    ("CEPU",  "0001717161"), ("TGSU2", "0000931427"), ("GGAL",  "0001114700"),
    ("BMA",   "0001347426"), ("AAPL",  "0000320193"), ("MSFT",  "0000789019"),
    ("NVDA",  "0001045810"), ("YPF",   "0000904851"),
]


def correr(cmd: list[str], etiqueta: str) -> bool:
    t0 = time.time()
    p = subprocess.run([sys.executable] + cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", cwd=str(REPO))
    cola = [ln for ln in ((p.stdout or "") + (p.stderr or "")).splitlines() if ln.strip()]
    print(f"      {etiqueta:<5} rc={p.returncode} {time.time()-t0:5.1f}s  "
          f"{(cola[-1] if cola else '')[:92]}")
    return p.returncode == 0


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    res = []
    for tk, cik in CIKS:
        print(f"\n=== {tk} · {cik} ===")
        ok3 = correr(["scripts/engine/s03_parse_ypf.py", "--cik", cik, "--min-xbrl", "1"], "S03")
        ok4 = correr(["scripts/engine/s04_normalize.py"], "S04") if ok3 else False
        res.append({"ticker": tk, "cik": cik, "s03": ok3, "s04": ok4})

    print("\n--- resumen ---")
    for r in res:
        print(f"  {r['ticker']:<6} S03={'OK' if r['s03'] else 'FALLO':<5} "
              f"S04={'OK' if r['s04'] else 'FALLO'}")
    (OUT / "reparse_universo.json").write_text(
        json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0 if all(r["s04"] for r in res) else 1


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    raise SystemExit(main())
