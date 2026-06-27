"""
PASO 4 — Generar el reporte final en Excel.

Consolida ratios_tickets.csv + tickets_sin_cik.csv en un unico .xlsx con
tabs separados, siguiendo el mismo patron que scripts/screener/08_generar_screener.py
(pandas.ExcelWriter + openpyxl).

La idea del tab "Calidad de datos" es que el usuario pueda confiar en el
Excel sin tener que abrir los JSON crudos de financials_sec/.

Input : datos/ratios_tickets.csv, datos/tickets_sin_cik.csv
Output: datos/reporte_tickets.xlsx
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

DATOS_DIR = Path(__file__).resolve().parent.parent / "datos"
RATIOS_CSV = DATOS_DIR / "ratios_tickets.csv"
SIN_CIK_CSV = DATOS_DIR / "tickets_sin_cik.csv"
OUT_XLSX = DATOS_DIR / "reporte_tickets.xlsx"

COLUMNAS_RATIOS = [
    "ticker", "cik", "nombre", "_esquema", "exchange", "currency",
    "precio_usd", "per_ttm", "eps_ttm_diluted", "cagr_eps_5y",
    "margen_neto_ttm", "roe_cagr_5y",
    "deuda_lp_sobre_ebitda", "deuda_total_sobre_ebitda",
    "fcfonce_equity_lp", "fcfonce_neto_caja", "payout_ttm",
    "dif_max_52w", "dif_min_52w", "year_high", "year_low",
]

COLUMNAS_CALIDAD = [
    "ticker", "cik", "nombre", "_esquema", "_error",
    "_revenue_ttm", "_netincome_ttm", "_ebitda_ttm", "_fcf_ttm",
    "_diluted_shares", "_equity", "_lt_debt", "_deuda_total",
    "_metric_revenue", "_metric_da",
]


def main() -> None:
    print("=" * 60)
    print("  PASO 4 -- Generar reporte final (Excel)")
    print("=" * 60)

    ratios_df = pd.read_csv(RATIOS_CSV)
    sin_cik_df = pd.read_csv(SIN_CIK_CSV)

    print(f"\n  Tickers con CIK (en ratios_tickets.csv): {len(ratios_df)}")
    print(f"  Tickers sin CIK (revision manual)      : {len(sin_cik_df)}")

    tiene_ratio_per = ratios_df["per_ttm"].notna().sum() if "per_ttm" in ratios_df else 0
    tiene_financials = (~ratios_df.get("_error", pd.Series(dtype=object)).notna()).sum()

    resumen = pd.DataFrame([
        {"metrica": "Total tickers en Tickets.xlsx", "valor": len(ratios_df) + len(sin_cik_df)},
        {"metrica": "Con CIK resuelto", "valor": len(ratios_df)},
        {"metrica": "Sin CIK (revision manual)", "valor": len(sin_cik_df)},
        {"metrica": "Con financials descargados", "valor": int(tiene_financials)},
        {"metrica": "Con PER calculado (precio + EPS TTM)", "valor": int(tiene_ratio_per)},
    ])

    cols_ratios = [c for c in COLUMNAS_RATIOS if c in ratios_df.columns]
    cols_calidad = [c for c in COLUMNAS_CALIDAD if c in ratios_df.columns]

    with pd.ExcelWriter(OUT_XLSX, engine="openpyxl") as writer:
        print("  - Tab: Resumen")
        resumen.to_excel(writer, sheet_name="Resumen", index=False)

        print("  - Tab: Ratios")
        ratios_df[cols_ratios].sort_values("ticker").to_excel(
            writer, sheet_name="Ratios", index=False
        )

        print("  - Tab: Calidad de datos")
        ratios_df[cols_calidad].sort_values("ticker").to_excel(
            writer, sheet_name="Calidad de datos", index=False
        )

        print("  - Tab: Sin CIK - revision manual")
        sin_cik_df.to_excel(writer, sheet_name="Sin CIK - revision manual", index=False)

        # Autofit simple de columnas en cada hoja
        for sheet in writer.sheets.values():
            for col_cells in sheet.columns:
                largo = max((len(str(c.value)) for c in col_cells if c.value is not None), default=10)
                sheet.column_dimensions[col_cells[0].column_letter].width = min(largo + 2, 45)

    print(f"\n  OK {OUT_XLSX}")
    print("\nPaso 4 completo. Reporte listo para revision manual.")


if __name__ == "__main__":
    main()
