import pandas as pd

df = pd.read_csv('scripts/tickets/cnv/debug/adr_formtypes.csv')
total = len(df)
errors = (df.status == "ERROR").sum()
print(f"Total: {total:,}")
print(f"Errors: {errors}")
print()

# FormType summary (top 30)
vc = df.formTypeId.value_counts(dropna=False).head(30)
print("=== Top FormTypes ===")
for ft, n in vc.items():
    if pd.notna(ft):
        names = df[df.formTypeId == ft].formTypeName.dropna().unique()
        name_str = names[0] if len(names) > 0 else "?"
    else:
        name_str = "NaN"
    print(f"  FT={str(ft):>6s}: {n:5d}  {name_str}")

print()

# Focus on EEFF + Dividend formTypes
targets = [147, 154, 142, 487, 339]
print("=== EEFF & Dividend FormTypes ===")
for ft in targets:
    sub = df[df.formTypeId == float(ft)]
    if len(sub) > 0:
        print(f"\nFT={ft} ({sub.formTypeName.iloc[0]}): {len(sub)} total")
        xtab = pd.crosstab(sub.ticker, sub.formTypeId)
        print(xtab.to_string())
        # Show period years
        if "periodoAnio" in sub.columns:
            years = sub.periodoAnio.dropna().unique()
            if len(years) > 0:
                print(f"  Years: {sorted(years)}")
    else:
        print(f"\nFT={ft}: 0")

print()

# Check what FT=142, FT=339 have
for ft in [142, 339, 143]:
    sub = df[df.formTypeId == float(ft)]
    if len(sub) > 0:
        print(f"\nFT={ft}: {len(sub)} filings")
        for t in sub.ticker.unique():
            cnt = (sub.ticker == t).sum()
            print(f"  {t}: {cnt}")
        if "periodoAnio" in sub.columns:
            print(f"  Years: {sorted(sub.periodoAnio.dropna().unique())}")
