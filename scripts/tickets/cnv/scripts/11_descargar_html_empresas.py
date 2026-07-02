from pathlib import Path
import sys
import time
import requests
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATOS_DIR = ROOT / "datos"
OUTPUT_DIR = DATOS_DIR / "html_descargados"
EMPRESAS_CSV = DATOS_DIR / "empresas.csv"
MANIFEST_CSV = OUTPUT_DIR / "manifest.csv"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cnv_ir.catalogo_ir import CATALOGO

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/137.0 Safari/537.36"
    )
}

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

empresas_df = pd.read_csv(EMPRESAS_CSV)
empresas_map = {str(row["ticker"]): row for _, row in empresas_df.iterrows()}

rows = []

for ticker in sorted(CATALOGO.keys()):
    row = empresas_map.get(ticker)
    if row is None:
        rows.append({
            "ticker": ticker,
            "empresa": "",
            "status": "missing_in_empresas_csv",
            "output_file": "",
            "url": "",
        })
        continue

    url = str(row["url_empresa"])
    output_file = OUTPUT_DIR / f"{ticker}.html"
    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        output_file.write_text(response.text, encoding="utf-8", errors="ignore")
        rows.append({
            "ticker": ticker,
            "empresa": str(row.get("empresa", "")),
            "status": "ok",
            "output_file": output_file.name,
            "url": url,
        })
        print(f"OK {ticker}: {output_file.name}")
    except Exception as exc:
        rows.append({
            "ticker": ticker,
            "empresa": str(row.get("empresa", "")),
            "status": f"error:{exc}",
            "output_file": "",
            "url": url,
        })
        print(f"ERR {ticker}: {exc}")

    time.sleep(0.5)

manifest_df = pd.DataFrame(rows)
manifest_df.to_csv(MANIFEST_CSV, index=False, encoding="utf-8-sig")
print(f"\nManifest guardado en {MANIFEST_CSV}")
print(f"Archivos descargados: {(manifest_df['status'] == 'ok').sum()} de {len(manifest_df)}")
