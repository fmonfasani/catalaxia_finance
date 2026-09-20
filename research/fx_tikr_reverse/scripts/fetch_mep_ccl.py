#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""STUB — MEP/CCL directos (etiqueta DIRECTA) + reconstrucción instrumental. REQ-FX-004/005.

Dos modos excluyentes para impedir mezcla silenciosa de series:
  --mode directa       -> vendors (dolarito/dolarapi/Rava) con etiqueta DIRECTA
  --mode reconstruida  -> ADR/bonos con fórmula + settlement (instrumental_spec.md)

Estado: NO IMPLEMENTADO. Contrato fijado; ejecución pendiente de precios auditables.
"""
from __future__ import annotations

import argparse
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.resolve()
SCRIPT_VERSION = "fetch_direct_reconstruct@v0-stub"
ADR_UNIVERSE = {"GGAL": ("GGAL.BA", "GGAL", 10), "YPFD": ("YPFD.BA", "YPF", 1),
                "PAMP": ("PAMP.BA", "PAM", 25)}
BONDS = ("AL30", "GD30")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["directa", "reconstruida"], required=True)
    ap.add_argument("--from", dest="from_", required=True)
    ap.add_argument("--to", required=True)
    a = ap.parse_args()
    raise SystemExit(
        f"[{SCRIPT_VERSION}] NO IMPLEMENTADO (mode={a.mode}, {a.from_}..{a.to}). "
        f"Directa exige vendors con timestamp; reconstruida exige {sorted(ADR_UNIVERSE)} "
        f"+ {list(BONDS)} con settlement declarado. Ver instrumental_spec.md. "
        f"Clasificación: NO DETERMINABLE."
    )


if __name__ == "__main__":
    main()
