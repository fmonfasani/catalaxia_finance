"""
22_adr_links.py

Extracts ALL GUIDs from CNV public website for ADR companies,
determines formTypeId for each, and filters for EEFF (FT=147,154,142,487).
"""
import re
import sys
import time
from pathlib import Path

import pandas as pd
import requests

# ==========================================================
# PATHS
# ==========================================================

ROOT = Path(__file__).resolve().parent.parent
DATOS = ROOT / "datos"
DEBUG = ROOT / "debug"

LINKS_OUT = DEBUG / "adr_links_raw.csv"
FORMTYPES_OUT = DEBUG / "adr_formtypes.csv"
FILTERED_OUT = DEBUG / "adr_links_eeff.csv"
RESUMEN_OUT = DEBUG / "adr_formtypes_resumen.csv"

DEBUG.mkdir(exist_ok=True)

# ==========================================================
# CONFIG
# ==========================================================

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/137 Safari/537.36"
    )
}

BASE_CNV = "https://www.cnv.gov.ar/SitioWeb/Empresas/Empresa/"
BASE_AIF2 = "https://aif2.cnv.gov.ar/presentations/publicview/"

SLEEP = 0.25
SLEEP_FORMTYPE = 0.10

# ADR companies: ticker -> (nombre, cuit)
ADRS = {
    "GGAL": ("Grupo Financiero Galicia S.A.", "30704962807"),
    "BBAR": ("Banco Macro SA", "30500010084"),
    "CEPU": ("Central Puerto", "33650305499"),
    "CRESY": ("Cresud SACIF Y A", "30509300700"),
    "EDN": ("Edenor", "30655116202"),
    "LOMA": ("Loma Negra CIASA", "30500530851"),
    "PAM": ("Pampa Energía S.A.", "30526552659"),
    "SUPV": ("Banco Supervielle S.A.", "33500005179"),
    "TEO": ("Telecom Argentina S.A.", "30639453738"),
}

# ==========================================================
# REGEX
# ==========================================================

RX_GUID = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.I,
)

RX_PRESENTATION = re.compile(
    r"presentationIdGlobal\s*=\s*'([^']+)'",
    re.I,
)

RX_FORM_ID = re.compile(
    r"formTypeId\s*=\s*'([^']+)'",
    re.I,
)

RX_FORM_NAME = re.compile(
    r"formTypeName\s*=\s*'([^']+)'",
    re.I,
)

RX_PERIOD_YEAR = re.compile(
    r"periodoANIO\s*=\s*'(\d+)'",
    re.I,
)

RX_PERIOD_MONTH = re.compile(
    r"periodoMES\s*=\s*'(\d+)'",
    re.I,
)


# ==========================================================
# HELPERS
# ==========================================================

def extraer(regex, html):
    m = regex.search(html)
    return m.group(1).strip() if m else ""


def analizar_guid(guid):
    """Fetch a publicview page and extract metadata."""
    url = BASE_AIF2 + guid
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        r.raise_for_status()
        html = r.text
        return (
            r.status_code,
            extraer(RX_PRESENTATION, html),
            extraer(RX_FORM_ID, html),
            extraer(RX_FORM_NAME, html),
            extraer(RX_PERIOD_YEAR, html),
            extraer(RX_PERIOD_MONTH, html),
            "",
        )
    except Exception as e:
        return ("ERROR", "", "", "", "", "", str(e))


def main():
    print("=" * 80)
    print("ADR LINKS - Extraer GUIDs y formTypeIds del portal CNV")
    print("=" * 80)

    # ====================================
    # STEP 1: Get all GUIDs from CNV site
    # ====================================
    print("\n" + "=" * 80)
    print("STEP 1: Fetching GUIDs from CNV public website")
    print("=" * 80)

    all_links = []
    seen_guids = set()
    guids_by_ticker = {}

    for ticker, (nombre, cuit) in ADRS.items():
        url = BASE_CNV + cuit
        print(f"\n[{ticker}] {nombre} ({cuit})...", end=" ", flush=True)
        try:
            r = requests.get(url, headers=HEADERS, timeout=120)
            r.raise_for_status()
            guids = sorted(set(RX_GUID.findall(r.text)))
            print(f"{len(guids):,} GUIDs")
            guids_by_ticker[ticker] = guids
            for g in guids:
                if g not in seen_guids:
                    seen_guids.add(g)
                    all_links.append({
                        "ticker": ticker,
                        "empresa": nombre,
                        "cuit": cuit,
                        "guid": g,
                        "url": BASE_AIF2 + g,
                    })
            time.sleep(SLEEP)
        except Exception as e:
            print(f"ERROR: {e}")

    df_links = pd.DataFrame(all_links)
    df_links.to_csv(LINKS_OUT, index=False, encoding="utf-8-sig")
    print(f"\nTotal GUIDs (unique): {len(df_links):,}")
    print(f"Saved to {LINKS_OUT}")

    # ====================================
    # STEP 2: Check formTypeId for each GUID
    # ====================================
    print("\n" + "=" * 80)
    print("STEP 2: Checking formTypeId for each GUID")
    print("=" * 80)

    if FORMTYPES_OUT.exists():
        procesados = pd.read_csv(FORMTYPES_OUT)
        guids_ok = set(procesados.guid)
        print(f"Already processed: {len(guids_ok):,}")
    else:
        procesados = pd.DataFrame()
        guids_ok = set()

    pendientes = df_links[~df_links.guid.isin(guids_ok)].copy()
    print(f"Pending: {len(pendientes):,}")

    total = len(df_links)
    nuevos = []

    for i, row in enumerate(pendientes.itertuples(index=False), start=1):
        sys.stdout.write(
            f"\r[{len(guids_ok) + i:06}/{total}] "
            f"{row.ticker} {row.guid[:8]}...  "
        )
        sys.stdout.flush()

        status, pid, fid, fname, anio, mes, error = analizar_guid(row.guid)

        nuevos.append({
            "ticker": row.ticker,
            "empresa": row.empresa,
            "cuit": row.cuit,
            "guid": row.guid,
            "presentationId": pid,
            "formTypeId": fid,
            "formTypeName": fname,
            "periodoAnio": anio,
            "periodoMes": mes,
            "status": status,
            "error": error,
        })

        if len(nuevos) >= 50:
            bloque = pd.DataFrame(nuevos)
            mode = "a" if FORMTYPES_OUT.exists() else "w"
            header = mode == "w"
            bloque.to_csv(
                FORMTYPES_OUT, mode=mode, header=header,
                index=False, encoding="utf-8-sig",
            )
            nuevos = []

        time.sleep(SLEEP_FORMTYPE)

    if nuevos:
        bloque = pd.DataFrame(nuevos)
        mode = "a" if FORMTYPES_OUT.exists() else "w"
        header = mode == "w"
        bloque.to_csv(
            FORMTYPES_OUT, mode=mode, header=header,
            index=False, encoding="utf-8-sig",
        )

    print("\n")

    # ====================================
    # STEP 3: Summary + Filter EEFF
    # ====================================
    print("=" * 80)
    print("STEP 3: Summary and filtering")
    print("=" * 80)

    df_ft = pd.read_csv(FORMTYPES_OUT)

    # Resumen by formType
    resumen = (
        df_ft.groupby(["formTypeId", "formTypeName"], dropna=False)
        .size()
        .reset_index(name="cantidad")
        .sort_values("cantidad", ascending=False)
    )
    print("\nFormType summary:")
    print(resumen.to_string(index=False))
    resumen.to_csv(RESUMEN_OUT, index=False, encoding="utf-8-sig")

    # Filter for EEFF formTypes
    EEFF_FTS = {"147", "154", "142", "487"}
    df_eeff = df_ft[df_ft.formTypeId.isin(EEFF_FTS)].copy()
    print(f"\nEEFF filtered: {len(df_eeff):,} (FT=147,154,142,487)")

    # Cross-tab by ticker and formTypeId
    xtab = pd.crosstab(df_eeff.ticker, df_eeff.formTypeId)
    print("\nBy ticker:")
    print(xtab.to_string())

    df_eeff.to_csv(FILTERED_OUT, index=False, encoding="utf-8-sig")
    print(f"\nSaved to {FILTERED_OUT}")

    print("\n" + "=" * 80)
    print("DONE")
    print("=" * 80)


if __name__ == "__main__":
    main()
