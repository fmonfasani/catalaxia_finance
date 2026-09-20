#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""STUB — FX implícito TIKR (ARS ÷ USD) + comparación y veredicto. REQ-FX-006/007/008/009.

extract_tikr_fx: lee benchmark curado a RAW (01_raw/tikr/<hash>.xlsx, inmutable),
  calcula FX_implicito por métrica Cf. stats_spec §1 (excluye EBITDA y acciones),
  conserva (periodo, metrica, ars, usd, fx_implicito, raw_ref, raw_hash).
compare_stats: aplica OBS-V1 + decision-v1.0.0 y emite CERTIFICATION.md.
  SIN series FX verificadas debe emitir UNKNOWN (fail-closed).

Estado: NO IMPLEMENTADO hasta disponer de benchmarks quarterly con provenance.
"""
from __future__ import annotations

import argparse

SCRIPT_VERSION = "tikr_fx_compare@v0-stub"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--benchmark", default="")
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    raise SystemExit(
        f"[{SCRIPT_VERSION}] NO IMPLEMENTADO (benchmark={a.benchmark!r} out={a.out!r}). "
        f"Sin benchmarks quarterly + 6 series FX con OBS-V1, el veredicto es UNKNOWN "
        f"por construcción. Clasificación: NO DETERMINABLE."
    )


if __name__ == "__main__":
    main()
