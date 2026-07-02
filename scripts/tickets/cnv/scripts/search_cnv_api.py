"""Search CNV AIF2 portal for ADR company filings"""
import requests
import json

# Try to find CNV API search endpoint
# Based on the URL pattern, CNV portal might have an API

# Try common search endpoints
base = "https://aif2.cnv.gov.ar"
endpoints = [
    "/api/search",
    "/api/presentations",
    "/api/companies",
    "/presentations/search",
]

# First, let's try to access the main page and find the API
print("=== Trying to find CNV search API ===")
for ep in endpoints:
    try:
        r = requests.get(f"{base}{ep}", timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        print(f"  {ep}: status={r.status_code}, len={len(r.text)}")
        if r.status_code == 200 and len(r.text) < 5000:
            print(f"    Content: {r.text[:500]}")
    except Exception as e:
        print(f"  {ep}: ERROR {e}")

# Try to find company filings by querying the presentation page
# The URL contains GUID - maybe there's a listing page
print("\n=== Trying CNV presentation listing ===")
try:
    r = requests.get(f"{base}/presentations", timeout=10, 
                     headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
    print(f"  /presentations: status={r.status_code}, len={len(r.text)}")
    if r.status_code == 200:
        print(f"    Content: {r.text[:1000]}")
except Exception as e:
    print(f"  ERROR: {e}")

# Also try with .json extension
try:
    r = requests.get(f"{base}/presentations/publicview", timeout=10,
                     headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
    print(f"  /presentations/publicview: status={r.status_code}")
except Exception as e:
    print(f"  ERROR: {e}")

# Try to access a known filing to understand headers
print("\n=== Known filing headers ===")
known_url = "https://aif2.cnv.gov.ar/presentations/publicview/fdde9998-f965-4ee7-9c7e-2a2b55620b7a"
try:
    r = requests.head(known_url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
    print(f"  Status: {r.status_code}")
    print(f"  Headers: {dict(r.headers)}")
except Exception as e:
    print(f"  ERROR: {e}")
