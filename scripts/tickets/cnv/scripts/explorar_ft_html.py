"""Check if FT=349 and FT=488 pages contain structured data tables in HTML"""
import csv, re, requests

H = {'User-Agent': 'Mozilla/5.0', 'Accept-Language': 'es-AR'}

with open(r'scripts/tickets/cnv/datos/links_eeff_refined.csv', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))

# Get samples for 349 and 488 - pick ones with actual financial companies
samples = []
seen = {}
for r in rows:
    ft = r['formTypeId']
    if ft in ('349', '488') and r['ticker'] not in seen.get(ft, set()):
        seen.setdefault(ft, set()).add(r['ticker'])
        samples.append(r)
        if len([s for s in samples if s['formTypeId'] == ft]) >= 3:
            continue

for s in samples:
    ft = s['formTypeId']
    ticker = s['ticker']
    pid = int(float(s['presentationId']))
    url = s['url']
    
    resp = requests.get(url, headers=H, timeout=20, verify=False)
    html = resp.text
    
    # Check for patterns that indicate financial data tables
    has_table = bool(re.search(r'<table[^>]*class=["\'].*?(?:grid|tabla|data)', html, re.I | re.DOTALL))
    has_codes = bool(re.findall(r'[1-8]\d{6}', html))
    has_financial_amounts = bool(re.findall(r'(?:\d{1,3}(?:\.\d{3})+,\d{2})', html))
    
    print(f"\n{ft:<5} {ticker:<6} PID={pid:<8} ({len(html)} bytes)")
    print(f"  HTML table: {has_table} | CNV codes: {has_codes} | Financial amounts: {has_financial_amounts}")
    
    # Look for any CNV codes in the HTML
    codes = set(re.findall(r'[1-8]\d{6}', html))
    if codes:
        print(f"  CNV codes found ({len(codes)}): {sorted(codes)[:10]}...")
    
    # Look for financial numbers
    amounts = re.findall(r'(\d{1,3}(?:\.\d{3})+,\d{2})', html)
    if amounts:
        print(f"  Financial amounts found: {len(amounts)} (first 3: {amounts[:3]})")
    
    # Check for JSON data in other parts of the page
    json_blocks = re.findall(r'\{.*"propiedades".*\}', html, re.DOTALL)
    if json_blocks:
        # Try a more targeted search for data tables
        pass
    
    # Check the sections structure more deeply
    m = re.search(r'var formFile\s*=\s*(\{.*?\});', html, re.DOTALL)
    if not m:
        m = re.search(r'var formFile\s*=\s*(\{.*\});', html, re.DOTALL)
    if m:
        import json
        data = json.loads(m.group(1))
        md_count = len(data.get('modeloDatos', []))
        nav = data.get('navegacion', {})
        ag_count = len(nav.get('agrupador', []))
        print(f"  modeloDatos: {md_count} | agrupadores: {ag_count}")
        
        # Show form type from metadata
        md = data.get('metadata', {})
        ft_real = md.get('FormType', '?')
        desc = md.get('DescripcionFormulario', '')
        print(f"  FormType: {ft_real} | Desc: {desc}")
