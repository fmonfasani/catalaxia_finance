import re
import pandas as pd
import requests
import time

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

empresas = pd.read_csv("empresas.csv")

resultado = []

for _, e in empresas.iterrows():

    ticker = e["ticker"]
    empresa = e["empresa"]
    cuit = str(e["cuit"])

    print(f"\n{ticker}")

    url = f"https://www.cnv.gov.ar/SitioWeb/Empresas/Empresa/{cuit}"

    html = requests.get(
        url,
        headers=HEADERS,
        timeout=120
    ).text

    guids = sorted(set(re.findall(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        html,
        re.I
    )))

    print("GUID:", len(guids))

    for guid in guids:

        resultado.append({

            "ticker": ticker,

            "empresa": empresa,

            "cuit": cuit,

            "guid": guid,

            "url":

            f"https://aif2.cnv.gov.ar/presentations/publicview/{guid}"

        })

    time.sleep(1)

df = pd.DataFrame(resultado)

df.to_csv(
    "links.csv",
    index=False,
    encoding="utf-8-sig"
)

print()
print(df.head())
print()
print("TOTAL:", len(df))