#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Normalización — PRIORIDAD 6. Construye normalized/fx_reference.parquet.

Entradas: parsed/universe.csv + raw/bcra/a3500/*.json + parsed/bcra_oficial.csv.
Cada fila: date | period | source | instrument | fx_type | fx_value | volume |
settlement | provenance_id  (schema exacto P6; tipos en DATA_DICTIONARY.md).

- date = target_date del quarter (no la efectiva: la efectiva va en provenance
  y en universe.csv; así no hay reemplazo silencioso).
- fx_type ∈ {A3500, OFICIAL} (referencias BCRA con dato). Filas MEP/CCL
  (directas o reconstruidas) se agregan sólo con quotes validados; hoy ausentes
  -> se documentan en RUN_REPORT.md, no se inventan.
- fx_value NULL + provenance con null_reason si status != OK.
- instrument = "N/A" (referencia no operable), volume = NULL, settlement = "N/A".
- Salidas: normalized/fx_reference.parquet (canónico, pyarrow) +
  normalized/fx_reference.csv (espejo auditable sin dependencias).

Uso:
  python engine/normalize.py
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import assert_in_sandbox, sha256_bytes  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
UNIVERSE = ROOT / "parsed" / "universe.csv"
RAW_A3500 = ROOT / "raw" / "bcra" / "a3500"
PARSED_OFICIAL = ROOT / "parsed" / "bcra_oficial.csv"
OUT_PQ = ROOT / "normalized" / "fx_reference.parquet"
OUT_CSV = ROOT / "normalized" / "fx_reference.csv"
NORMALIZE_VERSION = "normalize@v1.0.0"

COLUMNS = ["date", "period", "source", "instrument", "fx_type", "fx_value",
           "volume", "settlement", "provenance_id"]


def load_raw_meta() -> dict[str, dict]:
    """source_date -> meta (para provenance_id con sha)."""
    out = {}
    for p in RAW_A3500.glob("*.json"):
        try:
            out[p.stem] = json.loads(p.read_text(encoding="utf-8"))["meta"]
        except (ValueError, KeyError, OSError):
            continue
    return out


def main() -> None:
    assert_in_sandbox(OUT_PQ)
    assert_in_sandbox(OUT_CSV)
    import pandas as pd
    uni = pd.read_csv(UNIVERSE, dtype=str).fillna("")
    metas = load_raw_meta()
    ofi: dict[str, str] = {}
    if PARSED_OFICIAL.exists():
        with open(PARSED_OFICIAL, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                ofi[r["source_date"]] = r["provenance_id"]
    rows = []
    for _, u in uni.iterrows():
        period, tgt = u["period"], u["target_date"]
        # A3500
        if u["status_a3500"] == "OK" and u["eff_a3500"]:
            m = metas.get(u["eff_a3500"], {})
            v = (json.loads((RAW_A3500 / f"{u['eff_a3500']}.json").read_text(encoding="utf-8"))
                 ["parsed_hint"]["usd_tipoCotizacion"])
            rows.append({"date": tgt, "period": period, "source": "BCRA-estadisticas-cambiarias-v1.0",
                         "instrument": "N/A", "fx_type": "A3500", "fx_value": float(v),
                         "volume": None, "settlement": "N/A",
                         "provenance_id": f"bcra-a3500:{u['eff_a3500']}:lag{u['lag_a3500']}:"
                                          f"{str(m.get('sha256',''))[:12]}"})
        else:
            rows.append({"date": tgt, "period": period, "source": "BCRA-estadisticas-cambiarias-v1.0",
                         "instrument": "N/A", "fx_type": "A3500", "fx_value": None,
                         "volume": None, "settlement": "N/A",
                         "provenance_id": f"bcra-a3500:{period}:NULL:NO_PUBLICATION_IN_WINDOW"})
        # OFICIAL
        if u["status_oficial"] == "OK" and u["eff_oficial"]:
            with open(PARSED_OFICIAL, encoding="utf-8") as f:
                venta = next(float(r["venta"]) for r in csv.DictReader(f)
                             if r["source_date"] == u["eff_oficial"])
            rows.append({"date": tgt, "period": period, "source": "BCRA-minorista-serie-cierre",
                         "instrument": "N/A", "fx_type": "OFICIAL", "fx_value": float(venta),
                         "volume": None, "settlement": "N/A",
                         "provenance_id": f"{ofi.get(u['eff_oficial'], 'bcra-oficial:' + u['eff_oficial'])}"
                                          f":lag{u['lag_oficial']}"})
        else:
            rows.append({"date": tgt, "period": period, "source": "BCRA-minorista-serie-cierre",
                         "instrument": "N/A", "fx_type": "OFICIAL", "fx_value": None,
                         "volume": None, "settlement": "N/A",
                         "provenance_id": f"bcra-oficial:{period}:NULL:NO_PUBLICATION_IN_WINDOW"})
    df = pd.DataFrame(rows, columns=COLUMNS)
    OUT_PQ.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT_PQ, index=False)
    df.to_csv(OUT_CSV, index=False)
    digest = sha256_bytes(OUT_PQ.read_bytes())
    ok = int(df["fx_value"].notna().sum())
    print(f"[{NORMALIZE_VERSION}] filas={len(df)} con_valor={ok} "
          f"sha256(parquet)={digest[:16]}... -> normalized/fx_reference.parquet")


if __name__ == "__main__":
    main()
