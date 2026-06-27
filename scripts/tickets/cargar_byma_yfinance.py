# -*- coding: utf-8 -*-
"""
Loader de papeles SOLO-BYMA (no estan en EDGAR) desde yfinance -> misma base.

ARQUITECTURA (pensada para la "super base" futura):
  - UN solo `facts` unificado. La procedencia va en `taxonomia`='yfinance'
    (+ columna `fuente` en `empresas`). El motor de ratios lee por `concepto`
    canonico, asi que US (EDGAR) + ADR (EDGAR) + BYMA (yfinance) conviven y se
    calculan con el MISMO motor, sin cambiarlo.
  - Se guardan LOS ~160 TAGS por papel: los ~25 mapeables con su `concepto`
    canonico (los lee el motor), el resto crudo (concepto=NULL) para el futuro.
  - Raw cache en data/raw/yfinance/{ticker}.json = fuente de verdad re-parseable.

Descarga con cuidado: delay + retry ante 429 (yfinance no tiene limite oficial).
"""
from __future__ import annotations
import sqlite3, json, time, math
from datetime import datetime, timezone, timedelta
from pathlib import Path
import yfinance as yf

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "data" / "screener.db"
RAW = ROOT / "data" / "raw" / "yfinance"

# yfinance tag -> concepto canonico (los que el motor usa). El resto se guarda crudo.
# CapEx/Dividends vienen NEGATIVOS en yfinance (egresos) -> el loader toma abs().
YF_CANONICO = {
    "Total Revenue": "Revenue", "Cost Of Revenue": "COGS", "Gross Profit": "GrossProfit",
    "Operating Income": "OperatingIncome", "Net Income": "NetIncome",
    "Reconciled Depreciation": "DA", "Interest Expense": "InterestExpense",
    "Tax Provision": "IncomeTax", "Pretax Income": "PretaxIncome",
    "Diluted EPS": "EPS_diluted", "Diluted Average Shares": "Shares_diluted",
    "Total Assets": "Assets", "Current Assets": "AssetsCurrent",
    "Total Liabilities Net Minority Interest": "Liabilities", "Current Liabilities": "LiabilitiesCurrent",
    "Stockholders Equity": "Equity", "Total Debt": "Debt",
    "Cash And Cash Equivalents": "Cash", "Inventory": "Inventory",
    "Accounts Receivable": "Receivables", "Ordinary Shares Number": "SharesOutstanding",
    "Retained Earnings": "RetainedEarnings", "Net PPE": "PPE",
    "Operating Cash Flow": "CFO", "Capital Expenditure": "CapEx",
    "Cash Dividends Paid": "Dividends", "Free Cash Flow": "FCF_reported",
    "EBITDA": "EBITDA_reported", "Invested Capital": "InvestedCapital",
}
ABS = {"CapEx", "Dividends"}                       # egresos: guardar positivo
SHARES = {"Shares_diluted", "SharesOutstanding"}   # unit shares
PER_SHARE = {"EPS_diluted"}


def descargar(ticker, reintentos=3):
    """Baja income/balance/cashflow (todos los tags) con delay + retry. Cachea raw."""
    bursatil = f"{ticker}.BA"
    for intento in range(reintentos):
        try:
            t = yf.Ticker(bursatil)
            dfs = {"income": t.income_stmt, "balance": t.balance_sheet, "cashflow": t.cashflow}
            time.sleep(1.0)
            if all(d is None or d.empty for d in dfs.values()):
                return None
            RAW.mkdir(parents=True, exist_ok=True)
            cache = {sec: ({str(c)[:10]: {k: (None if (v is None or (isinstance(v, float) and math.isnan(v))) else v)
                       for k, v in df[c].items()} for c in df.columns} if df is not None and not df.empty else {})
                     for sec, df in dfs.items()}
            (RAW / f"{ticker}.json").write_text(json.dumps(cache, default=str), encoding="utf-8")
            return dfs
        except Exception as e:
            print(f"    ! {bursatil} intento {intento+1}: {str(e)[:45]} (retry 3s)")
            time.sleep(3)
    return None


def cargar(con, ticker, nombre, dfs):
    cik = f"BYMA-{ticker}"
    filas = []
    for sec, df in dfs.items():
        if df is None or df.empty:
            continue
        for col in df.columns:
            end = str(col)[:10]
            start = (datetime.fromisoformat(end) - timedelta(days=364)).date().isoformat()
            fy = int(end[:4])
            for tag in df.index:
                v = df.loc[tag, col]
                if v is None or (isinstance(v, float) and math.isnan(v)):
                    continue
                v = float(v)
                concepto = YF_CANONICO.get(tag)         # None si no mapeado -> se guarda crudo
                if concepto in ABS:
                    v = abs(v)
                unit = "shares" if concepto in SHARES else ("ARS/sh" if concepto in PER_SHARE else "ARS")
                filas.append((cik, "yfinance", tag, concepto, unit, start, end, v, fy, "FY", "ANUAL-YF", end))
    con.execute("DELETE FROM facts WHERE cik=?", (cik,))
    con.executemany("INSERT INTO facts VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", filas)
    con.execute("INSERT OR IGNORE INTO empresas (cik) VALUES (?)", (cik,))
    con.execute("""UPDATE empresas SET nombre=?, ticker_ppal=?, grupo='byma_yf', esquema='yfinance',
        moneda='ARS', pais='Argentina', fuente='yfinance', fecha_facts=? WHERE cik=?""",
        (nombre, ticker, datetime.now(timezone.utc).isoformat(), cik))
    con.commit()
    n_map = sum(1 for f in filas if f[3] is not None)
    return cik, len(filas), n_map


def asegurar_columna_fuente(con):
    cols = {r[1] for r in con.execute("PRAGMA table_info(empresas)")}
    if "fuente" not in cols:
        con.execute("ALTER TABLE empresas ADD COLUMN fuente TEXT")
        con.execute("UPDATE empresas SET fuente='edgar' WHERE fecha_facts IS NOT NULL AND fuente IS NULL")
        con.commit()


def cargar_lista(tickers, nombres=None):
    """tickers: lista de symbols BYMA (sin .BA). nombres: dict opcional ticker->nombre."""
    nombres = nombres or {}
    con = sqlite3.connect(DB, timeout=60); con.execute("PRAGMA busy_timeout=60000")
    asegurar_columna_fuente(con)
    ok, fail = [], []
    for i, tk in enumerate(tickers, 1):
        print(f"  [{i}/{len(tickers)}] {tk}.BA ...", end=" ", flush=True)
        dfs = descargar(tk)
        if dfs is None:
            print("SIN DATOS"); fail.append(tk); continue
        cik, n, n_map = cargar(con, tk, nombres.get(tk, tk), dfs)
        print(f"OK  {n} tags ({n_map} mapeados)")
        ok.append(tk)
    con.close()
    print(f"\n  Resumen: {len(ok)} cargados, {len(fail)} sin datos. {('Fallaron: '+', '.join(fail)) if fail else ''}")
    return ok, fail


if __name__ == "__main__":
    import sys
    args = sys.argv[1:]
    if args:
        cargar_lista([a.upper() for a in args])
    else:
        print("uso: python cargar_byma_yfinance.py GRIM ALUA MIRG ...")
