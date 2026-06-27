# -*- coding: utf-8 -*-
"""
Loader de empresas argentinas SOLO-BYMA (no están en EDGAR), desde la CNV.

Idea: las argentinas reportan en IFRS (NIIF), igual que los ADRs que ya
procesamos. Entonces alcanza con extraer los ~20 line-items core del estado
contable (PDF de la CNV / AIF) y meterlos en la tabla `facts` con el MISMO
nombre de concepto canónico que usamos para GAAP/IFRS. A partir de ahí, el motor
`calcular_ratios_base.py` calcula TODOS los ratios igual que para una ADR.

Las 3 capas del sistema:
  1) DESCUBRIMIENTO  scrapear el índice de la CNV/AIF -> URL del PDF del balance.
  2) EXTRACCIÓN      parsear el PDF (pdfplumber/camelot) -> ~20 números.
  3) CÁLCULO         este loader inserta en `facts` -> motor de ratios existente.

La capa 2 (parseo de PDF) es la difícil. Para un MVP: cargar los ~20 números a
mano (o semi-auto) en un dict/CSV por empresa, y este loader hace el resto.

NOTA: los estados argentinos vienen RE-EXPRESADOS por inflación (NIC 29), o sea
ya en "moneda homogénea" al cierre -> son comparables entre períodos.
"""
from __future__ import annotations
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path

DB = next(p for p in Path(__file__).resolve().parents if (p / 'data').is_dir()) / "data" / "screener.db"

# concepto canónico -> el motor de ratios ya conoce estos nombres
CONCEPTOS_CORE = [
    "Revenue", "GrossProfit", "OperatingIncome", "NetIncome", "DA",
    "Assets", "AssetsCurrent", "Liabilities", "LiabilitiesCurrent",
    "Cash", "Inventory", "Receivables", "Debt", "Equity",
    "CFO", "CapEx", "Dividends", "EPS_diluted", "Shares_diluted", "SharesOutstanding",
]


def cargar(con, ticker, nombre, anios):
    """anios = { period_end_ISO : { concepto: valor, ... }, ... }
    Inserta cada valor como datapoint ANUAL en `facts`, con period_start un año
    antes (para que el motor lo trate como anual ~365d). Moneda ARS."""
    cik = f"CNV-{ticker}"     # id sintético (no es CIK real de SEC)
    filas = []
    for end, datos in anios.items():
        start = (datetime.fromisoformat(end) - timedelta(days=364)).date().isoformat()
        fy = int(end[:4])
        for concepto, val in datos.items():
            if val is None:
                continue
            unit = "ARS" if concepto not in ("EPS_diluted",) else "ARS/shares"
            if concepto in ("Shares_diluted", "SharesOutstanding"):
                unit = "shares"
            filas.append((cik, "cnv-ifrs", f"CNV_{concepto}", concepto, unit,
                          start, end, val, fy, "FY", "ANUAL-CNV", end))
    con.execute("DELETE FROM facts WHERE cik=?", (cik,))
    con.executemany("INSERT INTO facts VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", filas)
    con.execute("INSERT OR IGNORE INTO empresas (cik) VALUES (?)", (cik,))
    con.execute("""UPDATE empresas SET nombre=?, ticker_ppal=?, grupo='byma_cnv',
        esquema='ifrs-full', moneda='ARS', pais='Argentina', fecha_facts=? WHERE cik=?""",
        (nombre, ticker, datetime.now(timezone.utc).isoformat(), cik))
    con.commit()
    return cik, len(filas)


# ──────────────────────────────────────────────────────────────────────────
# DEMO: prueba el mecanismo end-to-end con números de EJEMPLO (a completar del
# PDF real de la CNV). Calcula los ratios inline para no tocar la tabla `ratios`.
# ──────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # ⚠️ NÚMEROS DE EJEMPLO (millones de ARS) — reemplazar por los del balance CNV.
    EJEMPLO_ALUAR = {
        "2024-06-30": dict(Revenue=1_400_000, GrossProfit=420_000, OperatingIncome=280_000,
            NetIncome=180_000, DA=95_000, Assets=2_100_000, AssetsCurrent=900_000,
            Liabilities=800_000, LiabilitiesCurrent=450_000, Cash=120_000, Inventory=310_000,
            Receivables=180_000, Debt=350_000, Equity=1_300_000, CFO=240_000, CapEx=90_000,
            Dividends=60_000, Shares_diluted=2_800, SharesOutstanding=2_800),
        "2023-06-30": dict(Revenue=1_150_000, NetIncome=150_000, Equity=1_150_000,
            Assets=1_900_000, OperatingIncome=230_000, DA=88_000),
    }

    def div(a, b): return a / b if (a is not None and b not in (None, 0)) else None
    d = EJEMPLO_ALUAR["2024-06-30"]
    ebitda = d["OperatingIncome"] + d["DA"]
    fcf = d["CFO"] - d["CapEx"]
    cogs = d["Revenue"] - d["GrossProfit"]
    print("PROOF OF CONCEPT — ratios de una empresa SOLO-BYMA (Aluar, ejemplo CNV)")
    print("="*60)
    print(f"  (los números son de EJEMPLO; los reales salen del PDF de la CNV)\n")
    ratios = {
        "Margen bruto":      div(d["GrossProfit"], d["Revenue"]),
        "Margen operativo":  div(d["OperatingIncome"], d["Revenue"]),
        "Margen EBITDA":     div(ebitda, d["Revenue"]),
        "Margen neto":       div(d["NetIncome"], d["Revenue"]),
        "ROE":               div(d["NetIncome"], d["Equity"]),
        "ROA":               div(d["NetIncome"], d["Assets"]),
        "Deuda/EBITDA":      div(d["Debt"], ebitda),
        "Deuda/Equity":      div(d["Debt"], d["Equity"]),
        "Current ratio":     div(d["AssetsCurrent"], d["LiabilitiesCurrent"]),
        "FCF margin":        div(fcf, d["Revenue"]),
        "Payout":            div(d["Dividends"], d["NetIncome"]),
        "Asset turnover":    div(d["Revenue"], d["Assets"]),
        "Inventory turnover": div(cogs, d["Inventory"]),
    }
    for k, v in ratios.items():
        if v is None: continue
        es_veces = k in ("Deuda/EBITDA", "Deuda/Equity", "Current ratio", "Asset turnover", "Inventory turnover")
        print(f"  {k:<20} {v:.2f}x" if es_veces else f"  {k:<20} {v*100:.1f}%")
    print(f"\n  EPS = NetIncome/Shares = {div(d['NetIncome'], d['Shares_diluted']):.1f} ARS/acción")
    print("\n  -> MISMOS ratios que para un ADR. El motor no distingue el origen.")
