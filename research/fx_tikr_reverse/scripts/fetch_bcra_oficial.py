#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""STUB — descarga Oficial primario BCRA. REQ-FX-003. Mismo contrato que fetch_bcra_a3500."""
from __future__ import annotations

import argparse
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.resolve()
SCRIPT_VERSION = "fetch_bcra_oficial@v0-stub"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="from_", required=True)
    ap.add_argument("--to", required=True)
    ap.add_argument("--out", default=str(ROOT / "01_raw" / "bcra_oficial"))
    a = ap.parse_args()
    out = Path(a.out)
    if ROOT.resolve() not in out.resolve().parents and out.resolve() != ROOT.resolve():
        raise SystemExit(f"REFUSADO: --out fuera del sandbox ({out})")
    raise SystemExit(
        f"[{SCRIPT_VERSION}] NO IMPLEMENTADO: serie oficial BCRA pendiente de "
        f"verificación (REQ-FX-003). Rango {a.from_}..{a.to}. NO DETERMINABLE."
    )


if __name__ == "__main__":
    main()
