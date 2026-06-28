import requests
import pandas as pd
import time

# ======================================================
# CONFIG
# ======================================================

EMPRESAS = {
    "LEDE": "Ledesma",
    "SAMI": "San Miguel",
    "MOLA": "Molinos Agro",
    "INVJ": "Inversora Juramento",
    "SEMI": "Semino",
    "BHIP": "Banco Hipotecario",
    "BPAT": "Banco Patagonia",
    "VALO": "Banco de Valores",
    "GRIM": "Grimoldi",
    "HAVA": "Havanna",
    "MOLI": "Molinos Río",
    "MORI": "Morixe",
    "PATA": "Patagonia",
    "CAPX": "Capex",
    "CECO2": "Central Costanera",
    "EDSH": "EDESA",
    "TRAN": "Transener",
    "A3": "A3 Mercados",
    "BYMA": "BYMA",
    "CGPA2": "Camuzzi",
    "DGCE": "Gas del Centro",
    "DGCU2": "Gas Cuyana",
    "ECOG": "Ecogas",
    "GBAN": "Naturgy Ban",
    "METR": "Metrogas",
    "TGNO4": "Transportadora de Gas del Norte",
    "BOLT": "Boldt",
    "COME": "Comercial del Plata",
    "GAMI": "GAMI",
    "GARO": "Garovaglio",
    "AGRO": "Agrometal",
    "DOME": "Domec",
    "FERR": "Ferrum",
    "INTR": "Introductora",
    "LONG": "Longvie",
    "MIRG": "Mirgor",
    "POLL": "Polledo",
    "REGE": "Garcia Reguera",
    "AUSO": "Autopistas del Sol",
    "OEST": "Grupo Concesionario del Oeste",
    "ALUA": "Aluar",
    "CARC": "Carboclor",
    "CELU": "Celulosa",
    "FIPL": "Fiplasto",
    "HARG": "Holcim",
    "RIGO": "Rigolleau",
    "TXAR": "Ternium Argentina",
    "CVH": "Cablevisión Holding",
    "GCLA": "Grupo Clarín",
    "CADO": "Carlos Casado",
    "COUR": "Continental Urbana",
    "CTIO": "Consultatio",
    "GCDI": "GCDI",
    "RAGH": "Raghsa",
    "RICH": "Richmond",
    "ROSE": "Rosenbusch"
}

BASE = "https://www.cnv.gov.ar"

# ======================================================
# SESSION
# ======================================================

session = requests.Session()

session.headers.update({
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://www.cnv.gov.ar/SitioWeb/Empresas?seccion=buscador",
    "X-Requested-With": "XMLHttpRequest"
})

# Obtiene cookies
session.get(
    BASE + "/SitioWeb/Empresas?seccion=buscador"
)

# ======================================================
# BUSQUEDA
# ======================================================

resultado = []

for ticker, termino in EMPRESAS.items():

    print(f"Buscando {ticker}...")

    r = session.get(
        BASE + "/SitioWeb/Empresas/AutoComplete",
        params={
            "term": termino
        }
    )

    datos = r.json()

    if len(datos) == 0:

        resultado.append({
            "ticker": ticker,
            "empresa": "",
            "id": "",
            "cuit": "",
            "url_empresa": ""
        })

        continue

    empresa = datos[0]

    resultado.append({

        "ticker": ticker,

        "empresa": empresa["descripcion"],

        "id": empresa["id"],

        "cuit": empresa["cuit"],

        "url_empresa":
            f"https://www.cnv.gov.ar/SitioWeb/Empresas/Empresa/{empresa['cuit']}"

    })

    time.sleep(.3)

# ======================================================
# EXPORT
# ======================================================

df = pd.DataFrame(resultado)

df.to_csv(
    "empresas.csv",
    index=False,
    encoding="utf-8-sig"
)

print()
print(df)

print()
print("OK -> empresas.csv generado")