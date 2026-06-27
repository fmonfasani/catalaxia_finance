import requests
import pandas as pd
import time


from rapidfuzz import fuzz


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
    "PATA": "Importadora y Exportadora de la Patagonia",
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
    "GBAN": "Gas Natural Ban",
    "METR": "Metrogas",
    "TGNO4": "Transportadora de Gas del Norte",
    "BOLT": "Boldt",
    "COME": "Comercial del Plata",
    "GAMI": "GAMI",
    "GARO": "Garovaglio",
    "AGRO": "Agrometal",
    "DOME": "Domec",
    "FERR": "Ferrum",
    "INTR": "Introductora de Buenos Aires",
    "LONG": "Longvie",
    "MIRG": "Mirgor",
    "POLL": "Polledo",
    "REGE": "García Reguera",
    "AUSO": "Autopistas del Sol",
    "OEST": "Grupo Concesionario del Oeste",
    "ALUA": "Aluar",
    "CARC": "Carboclor",
    "CELU": "Celulosa Argentina",
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
    "RAGH": "RAGHSA",
    "RICH": "Richmond",
    "ROSE": "Rosenbusch"
}

def elegir_mejor(busqueda, resultados):

    mejor = None
    mejor_score = -1

    for r in resultados:

        score = fuzz.token_sort_ratio(
            busqueda.lower(),
            r["descripcion"].lower()
        )

        if score > mejor_score:
            mejor_score = score
            mejor = r

    return mejor

BASE = "https://www.cnv.gov.ar"

session = requests.Session()

session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/148.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "es-AR,es;q=0.9",
    "Referer": "https://www.cnv.gov.ar/SitioWeb/Empresas?seccion=buscador",
    "Origin": "https://www.cnv.gov.ar",
    "X-Requested-With": "XMLHttpRequest"
})

# Abre la página para obtener cookies
session.get(
    BASE + "/SitioWeb/Empresas?seccion=buscador",
    timeout=30
)

resultado = []

for ticker, busqueda in EMPRESAS.items():

    try:

        r = session.get(
            BASE + "/SitioWeb/Empresas/AutoComplete",
            params={"term": busqueda},
            timeout=30
        )

        r.raise_for_status()

        datos = r.json()

        if not datos:
            print(f"{ticker} -> NO ENCONTRADO")

            resultado.append({
                "Ticker": ticker,
                "Busqueda": busqueda,
                "Descripcion": "",
                "CUIT": "",
                "ID": "",
                "URL_AIF": ""
            })

            continue

        empresa = datos[0]

        url = f"{BASE}/SitioWeb/Empresas/Empresa/{empresa['cuit']}"

        print(f"{ticker} -> {empresa['descripcion']}")

        resultado.append({
            "Ticker": ticker,
            "Busqueda": busqueda,
            "Descripcion": empresa["descripcion"],
            "CUIT": empresa["cuit"],
            "ID": empresa["id"],
            "URL_AIF": url
        })

        time.sleep(0.3)

    except Exception as e:

        print(f"{ticker} -> ERROR -> {e}")

        resultado.append({
            "Ticker": ticker,
            "Busqueda": busqueda,
            "Descripcion": "",
            "CUIT": "",
            "ID": "",
            "URL_AIF": "",
            "ERROR": str(e)
        })

df = pd.DataFrame(resultado)

df.to_excel("cnv_empresas.xlsx", index=False)

print()
print(df)