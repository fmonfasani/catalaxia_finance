"""
fase1_re_codes.py — Reverse engineering of ADR CNV financial codes.

Downloads representative filings for FT=487, FT=147, FT=154, FT=339
and dumps ALL accounts with their NRO codes and RUBRO names to CSV.
"""
import re
import requests
import pandas as pd
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
DEBUG = ROOT / "debug"
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/137 Safari/537.36'}

# Representative filings
SAMPLES = {
    "FT487_BANK": {
        "label": "GGAL FT=487 (Bancos NIIF)",
        "ticker": "GGAL",
        "guid": "00b2561d-2c21-48b9-89a8-373f74aafe8b",
    },
    "FT147_NONBANK": {
        "label": "CEPU FT=147 (NIIF no-bancos)",
        "ticker": "CEPU",
        "guid": "ef29a051-d818-4463-b214-0faa9d328d97",
    },
    "FT154_BANK": {
        "label": "GGAL FT=154 (Bancos legacy)",
        "ticker": "GGAL",
        "guid": "0984996c-c3f1-4b89-902d-fa6e76c79c18",
    },
    "FT339_DIV": {
        "label": "GGAL FT=339 (Dividendos)",
        "ticker": "GGAL",
        "guid": "13280c13-2796-470b-9734-0753478b9604",
    },
}

def fetch_and_parse(label, ticker, guid):
    url = f"https://aif2.cnv.gov.ar/presentations/publicview/{guid}"
    r = requests.get(url, headers=HEADERS, timeout=30)
    html = r.text
    
    meta = {}
    for rx_name, rx in [
        ("formTypeId", r'formTypeId\s*=\s*["\']([^"\']+)["\']'),
        ("formTypeName", r'formTypeName\s*=\s*["\']([^"\']+)["\']'),
        ("presentationId", r'presentationIdGlobal\s*=\s*["\']([^"\']+)["\']'),
        ("periodoAnio", r'periodoANIO\s*=\s*["\']([^"\']+)["\']'),
        ("periodoMes", r'periodoMES\s*=\s*["\']([^"\']+)["\']'),
    ]:
        m = re.search(rx, html, re.I)
        meta[rx_name] = m.group(1) if m else ""
    
    print(f"\n{'='*80}")
    print(f"{label}")
    print(f"  GUID: {guid}")
    for k, v in meta.items():
        print(f"  {k}: {v}")
    
    # Find entities
    entities = re.findall(r'<entidad[^>]*>.*?</entidad>', html, re.IGNORECASE | re.DOTALL)
    print(f"  Entities: {len(entities)}")
    
    all_accounts = []
    all_entities = []
    
    for i, ent in enumerate(entities):
        ent_tag = re.search(r'<entidad\s+([^>]*)>', ent, re.IGNORECASE)
        if not ent_tag:
            continue
        attrs = ent_tag.group(1)
        eid = re.search(r'id=["\']([^"\']+)["\']', attrs)
        clave = re.search(r'clave=["\']([^"\']+)["\']', attrs)
        nelem = re.search(r'numeroelementos=["\']([^"\']+)["\']', attrs)
        eid_val = eid.group(1) if eid else "?"
        clave_val = clave.group(1) if clave else "?"
        nelem_val = nelem.group(1) if nelem else "?"
        
        filas = re.findall(r'<fila[^>]*>.*?</fila>', ent, re.IGNORECASE | re.DOTALL)
        nf = len(filas)
        
        all_entities.append({
            "entity_id": eid_val,
            "clave": clave_val,
            "num_elementos": nelem_val,
            "num_filas": nf,
        })
        
        for j, fila in enumerate(filas):
            props = re.findall(r'<propiedad\s+id=["\']([^"\']+)["\'][^>]*>([^<]*)</propiedad>', fila, re.IGNORECASE)
            row = {"ticker": ticker, "entity_id": eid_val, "entity_clave": clave_val, "fila_idx": j+1}
            for k, v in props:
                row[k] = v.strip()
            all_accounts.append(row)
    
    return meta, all_entities, all_accounts

def safe_print(text):
    """Print with cp1252 fallback."""
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode('cp1252', errors='replace').decode('cp1252'))

def main():
    all_rows = []
    
    for key, sample in SAMPLES.items():
        meta, entities, accounts = fetch_and_parse(**sample)
        
        # Print entity summary
        print(f"\n  Entities detail:")
        for ent in entities:
            print(f"    id={ent['entity_id']} clave='{ent['clave']}' filas={ent['num_filas']}")
        
        # Print accounts for the main entity (Estados Contables Cuentas)
        main_accounts = [a for a in accounts if a["entity_clave"] == "Estados Contables Cuentas"]
        if main_accounts:
            print(f"\n  Accounts (Estados Contables Cuentas): {len(main_accounts)}")
            for a in main_accounts:
                nro = a.get("Nro", "?")
                rubro = a.get("Rubro", "?")
                monto = a.get("Monto", "?")
        safe_print(f"    Nro={nro:>8s}  Monto={monto:>15s}  {rubro[:60]}")

    # Print ALL accounts regardless of entity
    print(f"\n  ALL entities with filas:")
    for a in accounts:
        ec = a.get("entity_clave", "?")
        if ec != "Estados Contables Cuentas":
            props_str = ", ".join([f"{k}={v}" for k, v in a.items() if k not in ("ticker", "entity_id", "entity_clave", "fila_idx")])
            safe_print(f"    [{a['fila_idx']}] {ec}: {props_str[:120]}")

        # Print dividend accounts
        div_accounts = [a for a in accounts if a["entity_clave"] in ("Dividendos", "DatosGenerales")]
        if div_accounts:
            print(f"\n  Dividend data:")
            for a in div_accounts:
                print(f"    {a}")
        
        # Collect all accounts with NRO for CSV
        for a in accounts:
            if "Nro" in a:
                all_rows.append({
                    "fuente": key,
                    "ticker": sample["ticker"],
                    "entity_id": a["entity_id"],
                    "entity_clave": a["entity_clave"],
                    "nro": a.get("Nro", ""),
                    "rubro": a.get("Rubro", ""),
                    "monto": a.get("Monto", ""),
                })
        
        print()
    
    # Save full dump
    df = pd.DataFrame(all_rows)
    out_path = DEBUG / "adr_re_codes_dump.csv"
    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"\nSaved full dump to {out_path}")
    print(f"Total rows: {len(df)}")
    
    # Summary of all unique NRO codes
    print(f"\n{'='*80}")
    print(f"UNIQUE NRO codes across all formTypes:")
    print(f"{'='*80}")
    for nro in sorted(df.nro.unique()):
        labeled = df[df.nro == nro]
        rubros = labeled.rubro.unique()
        fuentes = labeled.fuente.unique()
        print(f"  Nro={nro:>8s}  Rubro={rubros[0][:60] if len(rubros) > 0 else '?'}  ({', '.join(fuentes)})")

if __name__ == "__main__":
    main()
