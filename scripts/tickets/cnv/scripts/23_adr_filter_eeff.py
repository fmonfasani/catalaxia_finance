"""
23_adr_filter_eeff.py

Filter ADR formTypes for EEFF (FT=147, 154, 142, 487, 339) and save.
"""
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEBUG = ROOT / "debug"

FORMTYPES = DEBUG / "adr_formtypes.csv"
EEFF_OUT = DEBUG / "adr_links_eeff.csv"
DIV_OUT = DEBUG / "adr_links_dividendos.csv"
RESUMEN_OUT = DEBUG / "adr_eeff_resumen.csv"

EEFF_FTS = {"147", "154", "142", "487"}
DIV_FTS = {"339"}

df = pd.read_csv(FORMTYPES)
df["formTypeId_str"] = df.formTypeId.astype(str).str.replace(r"\.0$", "", regex=True)

# Filter EEFF
mask_eeff = df.formTypeId_str.isin(EEFF_FTS)
df_eeff = df[mask_eeff].copy()
df_eeff.to_csv(EEFF_OUT, index=False, encoding="utf-8-sig")
print(f"EEFF filtered: {len(df_eeff):,}")

# Cross-tab
xtab = pd.crosstab(df_eeff.ticker, df_eeff.formTypeId_str)
print("\nBy ticker and formType:")
print(xtab.to_string())

xtab.to_csv(RESUMEN_OUT, encoding="utf-8-sig")

# Filter dividends
mask_div = df.formTypeId_str.isin(DIV_FTS)
df_div = df[mask_div].copy()
df_div.to_csv(DIV_OUT, index=False, encoding="utf-8-sig")
print(f"\nDividendos filtered: {len(df_div):,}")
for t in df_div.ticker.unique():
    print(f"  {t}: {(df_div.ticker==t).sum()}")

print(f"\nSaved to:\n  {EEFF_OUT}\n  {DIV_OUT}")
