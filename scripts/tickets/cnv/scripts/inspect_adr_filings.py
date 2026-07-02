"""
Inspect the data tables of ADR filings (FT=487, FT=339, FT=154)
to understand the financial codes used.
"""
import re
import requests
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DEBUG = ROOT / "debug"

EEFF = DEBUG / "adr_formtypes.csv"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/137 Safari/537.36"}
BASE = "https://aif2.cnv.gov.ar/presentations/publicview/"

df = pd.read_csv(EEFF)

# Find one FT=487 and one FT=339 for GGAL
for ft_label, ft in [("FT=487 (Bancos NIIF)", 487), ("FT=339 (Dividendos)", 339), ("FT=154 (Bancos)", 154), ("FT=147 (NIIF)", 147)]:
    candidates = df[df.formTypeId == float(ft)]
    if len(candidates) == 0:
        print(f"\n{ft_label}: no candidates")
        continue
    
    row = candidates.iloc[0]
    guid = row.guid
    ticker = row.ticker
    url = BASE + guid
    
    print(f"\n{'='*80}")
    print(f"{ft_label} | {ticker} | GUID={guid}")
    print(f"{'='*80}")
    
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        html = r.text
        
        # Find datatable_html (the key data table)
        m = re.search(r"datatable_html\s*=\s*'([^']+)'", html)
        if m:
            dt = m.group(1)
            # Unescape HTML entities
            dt = dt.replace("\\'", "'").replace('\\"', '"').replace("\\n", "\n").replace("\\t", "\t")
            print(f"\nDataTable HTML length: {len(dt)}")
            
            # Extract all fila codes and their codigoCuenta values
            fila_codes = set(re.findall(r'codigoCuenta["\']\s*value=["\']([^"\']+)["\']', dt, re.I))
            codigo_balance = set(re.findall(r'codigoBalance["\']\s*value=["\']([^"\']+)["\']', dt, re.I))
            conceptos = set(re.findall(r'descripcion["\']\s*value=["\']([^"\']+)["\']', dt, re.I))
            
            print(f"Unique codigoCuenta values: {len(fila_codes)}")
            if len(fila_codes) > 0:
                sample = sorted(fila_codes)[:20]
                print(f"  Sample: {sample}")
            
            print(f"Unique codigoBalance values: {len(codigo_balance)}")
            if len(codigo_balance) > 0:
                sample = sorted(codigo_balance)[:20]
                print(f"  Sample: {sample}")
            
            print(f"Unique conceptos: {len(conceptos)}")
            if len(conceptos) > 0:
                sample = sorted(conceptos)[:20]
                print(f"  Sample: {sample}")
            
            # Show actual fila structure
            filas = re.findall(r'<fila[^>]*>.*?</fila>', dt, re.I | re.S)
            print(f"\nNumber of fila elements: {len(filas)}")
            if len(filas) > 0:
                print(f"First fila:")
                print(filas[0][:300])
        else:
            print("No datatable_html found")
            # Try to find the data key
            m2 = re.search(r"(data|data_table|tableData)\s*[:=]\s*['\"]([^'\"]+)['\"]", html, re.I)
            if m2:
                print(f"Found data key: {m2.group(1)} = {m2.group(2)[:200]}")
            
    except Exception as e:
        print(f"ERROR: {e}")
