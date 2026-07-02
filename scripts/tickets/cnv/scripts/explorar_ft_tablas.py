"""Examine the HTML table structure for FT=349 and FT=488"""
import csv, re, requests, html as htmlmod

H = {'User-Agent': 'Mozilla/5.0', 'Accept-Language': 'es-AR'}

with open(r'scripts/tickets/cnv/datos/links_eeff_refined.csv', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))

# Pick one 488 and one 349
for ft, ticker in [('488', 'A3'), ('349', 'BPAT'), ('349', 'GCLA')]:
    for r in rows:
        if r['formTypeId'] == ft and r['ticker'] == ticker:
            url = r['url']
            break
    pid = int(float(r['presentationId']))
    
    resp = requests.get(url, headers=H, timeout=20, verify=False)
    html = resp.text
    
    # Find all tables
    tables = re.findall(r'<table[^>]*>(.*?)</table>', html, re.DOTALL | re.I)
    
    print(f"\n{'='*60}")
    print(f"{ft:<5} {ticker:<6} PID={pid:<8} - {len(tables)} table(s) found")
    print(f"{'='*60}")
    
    for i, tbl in enumerate(tables):
        # Show table rows
        rows_html = re.findall(r'<tr[^>]*>(.*?)</tr>', tbl, re.DOTALL | re.I)
        print(f"\n  Table {i+1}: {len(rows_html)} rows")
        
        for j, row in enumerate(rows_html[:15]):
            # Extract cell text
            cells = re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', row, re.DOTALL | re.I)
            clean = []
            for cell in cells:
                txt = re.sub(r'<[^>]+>', ' ', cell)
                txt = htmlmod.unescape(txt).strip()
                txt = re.sub(r'\s+', ' ', txt)
                clean.append(txt)
            
            # Only show non-empty rows
            if any(c.strip() for c in clean):
                print(f"    Row {j+1}: {' | '.join(c[:40] for c in clean)}")
    
    # Also look for any table-like grid structures
    grids = re.findall(r'class=["\']([^"\']*grid[^"\']*)["\']', html)
    if grids:
        print(f"\n  Grid classes: {grids[:5]}")
