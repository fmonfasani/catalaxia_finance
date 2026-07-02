"""
22_adr_links_fast.py

Parallel version - checks formTypeId for ADR GUIDs using ThreadPoolExecutor.
"""
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
DEBUG = ROOT / "debug"

LINKS_RAW = DEBUG / "adr_links_raw.csv"
FORMTYPES_OUT = DEBUG / "adr_formtypes.csv"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/137 Safari/537.36"
}
BASE_AIF2 = "https://aif2.cnv.gov.ar/presentations/publicview/"

RX_PRESENTATION = re.compile(r"presentationIdGlobal\s*=\s*'([^']+)'", re.I)
RX_FORM_ID = re.compile(r"formTypeId\s*=\s*'([^']+)'", re.I)
RX_FORM_NAME = re.compile(r"formTypeName\s*=\s*'([^']+)'", re.I)
RX_PERIOD_YEAR = re.compile(r"periodoANIO\s*=\s*'(\d+)'", re.I)
RX_PERIOD_MONTH = re.compile(r"periodoMES\s*=\s*'(\d+)'", re.I)

MAX_WORKERS = 10
SAVE_EVERY = 200

def extraer(regex, html):
    m = regex.search(html)
    return m.group(1).strip() if m else ""

def fetch_one(row):
    guid = row["guid"]
    url = BASE_AIF2 + guid
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        r.raise_for_status()
        html = r.text
        return {
            "ticker": row["ticker"],
            "empresa": row["empresa"],
            "cuit": row["cuit"],
            "guid": guid,
            "presentationId": extraer(RX_PRESENTATION, html),
            "formTypeId": extraer(RX_FORM_ID, html),
            "formTypeName": extraer(RX_FORM_NAME, html),
            "periodoAnio": extraer(RX_PERIOD_YEAR, html),
            "periodoMes": extraer(RX_PERIOD_MONTH, html),
            "status": r.status_code,
            "error": "",
        }
    except Exception as e:
        return {
            "ticker": row["ticker"],
            "empresa": row["empresa"],
            "cuit": row["cuit"],
            "guid": guid,
            "presentationId": "",
            "formTypeId": "",
            "formTypeName": "",
            "periodoAnio": "",
            "periodoMes": "",
            "status": "ERROR",
            "error": str(e),
        }

def main():
    print("=" * 80)
    print("ADR FORM TYPES (PARALLEL)")
    print("=" * 80)

    df = pd.read_csv(LINKS_RAW)
    total = len(df)
    print(f"Total GUIDs: {total:,}")

    # Load already processed
    guids_ok = set()
    if FORMTYPES_OUT.exists():
        done = pd.read_csv(FORMTYPES_OUT)
        guids_ok = set(done.guid)
        print(f"Already processed: {len(guids_ok):,}")

    pending = df[~df.guid.isin(guids_ok)].copy()
    print(f"Pending: {len(pending):,}")

    if len(pending) == 0:
        print("Nothing to do!")
        return

    all_done = list(guids_ok)
    pending_records = pending.to_dict("records")
    completed = 0
    errors = 0
    start = time.time()
    batch = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = {ex.submit(fetch_one, r): r for r in pending_records}
        for f in as_completed(futures):
            result = f.result()
            completed += 1
            if result["status"] == "ERROR":
                errors += 1
            all_done.append(result["guid"])
            batch.append(result)

            elapsed = time.time() - start
            rate = completed / elapsed if elapsed > 0 else 0
            eta = (len(pending_records) - completed) / rate if rate > 0 else 0
            sys.stdout.write(
                f"\r[{completed}/{len(pending_records)}] "
                f"errors={errors} "
                f"rate={rate:.1f}/s "
                f"ETA={eta:.0f}s    "
            )
            sys.stdout.flush()

            if len(batch) >= SAVE_EVERY:
                bloque = pd.DataFrame(batch)
                mode = "a" if FORMTYPES_OUT.exists() else "w"
                header = mode == "w"
                bloque.to_csv(
                    FORMTYPES_OUT, mode=mode, header=header,
                    index=False, encoding="utf-8-sig",
                )
                batch = []

    if batch:
        bloque = pd.DataFrame(batch)
        mode = "a" if FORMTYPES_OUT.exists() else "w"
        header = mode == "w"
        bloque.to_csv(
            FORMTYPES_OUT, mode=mode, header=header,
            index=False, encoding="utf-8-sig",
        )

    print()
    elapsed = time.time() - start
    print(f"\nDone! {completed:,} processed in {elapsed:.0f}s ({completed/elapsed:.1f}/s)")
    print(f"Errors: {errors}")

if __name__ == "__main__":
    main()
