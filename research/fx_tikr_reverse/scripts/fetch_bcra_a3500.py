#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""STUB — descarga A3500 primario BCRA. REQ-FX-002.

Estado: NO IMPLEMENTADO (NO DETERMINABLE hasta verificar endpoint BCRA vivo).
Este stub existe para fijar el CONTRATO (provenance + idempotencia + sandbox)
antes de tocar la red. Debe fallar cerrado hasta implementar.

Contrato de salida por celda: (fecha, tipo=A3500, compra/venta o valor,
observation_date, lag_days, endpoint, params, downloaded_at, http_status,
raw_ref, raw_hash, parser_version, etiqueta=REFERENCIA_BCRA).
"""
from __future__ import annotations

import argparse
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.resolve()
SCRIPT_VERSION = "fetch_bcra_a3500@v0-stub"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="from_", required=True)
    ap.add_argument("--to", required=True)
    ap.add_argument("--out", default=str(ROOT / "01_raw" / "bcra_a3500"))
    a = ap.parse_args()
    out = Path(a.out)
    if ROOT.resolve() not in out.resolve().parents and out.resolve() != ROOT.resolve():
        raise SystemExit(f"REFUSADO: --out fuera del sandbox ({out})")
    raise SystemExit(
        f"[{SCRIPT_VERSION}] NO IMPLEMENTADO: endpoint BCRA A3500 pendiente de "
        f"verificación contra fuente viva (fuente primaria exigida por REQ-FX-002). "
        f"Rango pedido {a.from_}..{a.to}. Ver 00_DEFINIR/source_registry.yaml. "
        f"Clasificación: NO DETERMINABLE."
    )


if __name__ == "__main__":
    main()
