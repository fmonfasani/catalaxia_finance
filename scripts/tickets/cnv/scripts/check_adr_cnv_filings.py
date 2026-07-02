"""Check what CNV filings exist for ADR companies"""
import csv
from collections import defaultdict, Counter

with open('scripts/tickets/cnv/datos/links_eeff_refined.csv', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    rows = list(reader)

# ADR tickers
adr_tickers = ['BBAR', 'BMA', 'CEPU', 'CRESY', 'EDN', 'GGAL', 'LOMA', 'PAM', 'SUPV', 'TEO']
all_tickers = set(r['ticker'] for r in rows)

# Which ADR tickers exist in the CSV?
print("=== ADR tickers in links_eeff_refined ===")
for tk in adr_tickers:
    present = tk in all_tickers
    count = sum(1 for r in rows if r['ticker'] == tk)
    print(f"  {tk:<6}: {'YES' if present else 'NO':<4} ({count} filings total)")

# Also check if there are FILING entries for BYMA tickers that are ALSO ADRs
print("\n=== Checking BYMA tickers that might be the same companies ===")
byma_alt = {'PAM': 'PAMP', 'CRESY': 'CRES', 'TEO': 'TECO2'}
for adr_tk, byma_tk in byma_alt.items():
    in_csv = byma_tk in all_tickers
    cnt_by = sum(1 for r in rows if r['ticker'] == byma_tk)
    print(f"  ADR={adr_tk} -> BYMA={byma_tk}: {'YES' if in_csv else 'NO':<4} (BYMA has {cnt_by} filings)")

# For each ADR, show breakdown by formTypeId
print("\n=== ADR filings by formTypeId ===")
for tk in adr_tickers:
    ft_counts = Counter(r['formTypeId'] for r in rows if r['ticker'] == tk)
    total = sum(ft_counts.values())
    if total > 0:
        details = ', '.join(f"FT={k}:{v}" for k, v in sorted(ft_counts.items()))
        print(f"  {tk:<6}: {total:>5} filings  [{details}]")

# Also check the BYMA alternatives
print("\n=== BYMA equivalents for ADRs ===")
for tk in ['PAMP', 'CRES', 'TECO2', 'BBAR', 'BMA', 'CEPU', 'EDN', 'GGAL', 'LOMA', 'SUPV']:
    ft_counts = Counter(r['formTypeId'] for r in rows if r['ticker'] == tk)
    total = sum(ft_counts.values())
    if total > 0:
        details = ', '.join(f"FT={k}:{v}" for k, v in sorted(ft_counts.items()))
        print(f"  {tk:<6}: {total:>5} filings  [{details}]")

# Also check the CNV ticker name approach - maybe they use CUIT
print("\n=== CUIT mapping for ADRs ===")
cuits = {}
for r in rows:
    if r['ticker'] in adr_tickers:
        cuits[r['ticker']] = r['cuit']
for tk, c in cuits.items():
    print(f"  {tk}: CUIT={c}")

# Check how many unique tickers have FT=147 filings at all
ft147_tickers = set(r['ticker'] for r in rows if r['formTypeId'] == '147')
print(f"\nTotal unique tickers with FT=147: {len(ft147_tickers)}")
for tk in sorted(adr_tickers):
    has_147 = tk in ft147_tickers
    alt = byma_alt.get(tk)
    has_147_alt = alt in ft147_tickers if alt else False
    print(f"  {tk:<6}: FT=147={'YES' if has_147 else 'NO':<4}  alt={alt or '':<6} FT=147={'YES' if has_147_alt else 'NO':<4}")

# What are ALL the tickers in the CSV? (to see the full set)
print(f"\nAll tickers in CSV ({len(all_tickers)}):")
csv_tickers = sorted(all_tickers)
print(f"  {', '.join(csv_tickers)}")
