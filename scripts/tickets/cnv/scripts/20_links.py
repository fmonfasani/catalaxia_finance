import pandas as pd
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import time

BASE = "https://www.cnv.gov.ar"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/137.0 Safari/537.36"
    )
}

# ----------------------------
# Lee empresas.csv
# ----------------------------

empresas = pd.read_csv("empresas.csv")

resultado = []

# ----------------------------
# Recorre todas las empresas
# ----------------------------

for _, empresa in empresas.iterrows():

    ticker = empresa["ticker"]
    nombre = empresa["empresa"]
    cuit = str(empresa["cuit"])
    url_empresa = empresa["url_empresa"]

    print(f"\n[{ticker}] {nombre}")

    try:

        # La página pública de la CNV NO es la AIF
        url_empresa = empresa["url_empresa"]

        r = requests.get(url_empresa, headers=HEADERS, timeout=30)

        if r.status_code != 200:
            print("Error", r.status_code)
            continue

        soup = BeautifulSoup(r.text, "html.parser")

        links = soup.find_all("a", href=True)

        encontrados = 0

        for a in links:

            href = a["href"]

            if "/presentations/publicview/" not in href:
                continue

            href = urljoin(BASE, href)

            guid = href.split("/")[-1]

            fila = a.find_parent("tr")

            if fila is None:
                continue

            columnas = fila.find_all("td")

            if len(columnas) < 4:
                continue

            fecha = columnas[0].get_text(strip=True)
            hora = columnas[1].get_text(strip=True)
            descripcion = columnas[2].get_text(" ", strip=True)
            id_cnv = columnas[3].get_text(strip=True)

            resultado.append({

                "Ticker": ticker,
                "Empresa": nombre,
                "CUIT": cuit,

                "Fecha": fecha,
                "Hora": hora,

                "Descripcion": descripcion,

                "ID_CNV": id_cnv,

                "GUID": guid,

                "URL_PRESENTACION": href

            })

            encontrados += 1

        print(f"   {encontrados} presentaciones")

        time.sleep(1)

    except Exception as e:
        print(e)

# ----------------------------
# Guarda CSV
# ----------------------------

df = pd.DataFrame(resultado)

df.to_csv("links.csv", index=False, encoding="utf-8-sig")

print()
print("=" * 60)
print("TOTAL:", len(df))
print("Archivo generado: links.csv")
print("=" * 60)