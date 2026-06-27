"""
20.5_inspeccionar.py

Inspecciona un publicview de la CNV para descubrir cómo identificar
automáticamente los Estados Financieros (EEFF).

Uso:

python 20.5_inspeccionar.py GUID

o

python 20.5_inspeccionar.py
"""

from pathlib import Path
import json
import re
import sys

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://aif2.cnv.gov.ar/presentations/publicview/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/137.0 Safari/537.36"
    )
}


def obtener_html(guid: str) -> str:
    url = BASE_URL + guid

    r = requests.get(
        url,
        headers=HEADERS,
        timeout=30,
    )

    r.raise_for_status()

    return r.text


def imprimir_encabezados(soup):

    print("\n================ TITULO ================")

    if soup.title:
        print(soup.title.get_text(strip=True))

    print("\n================ H1 ================")

    for h in soup.find_all("h1"):
        print(h.get_text(" ", strip=True))

    print("\n================ H2 ================")

    for h in soup.find_all("h2"):
        print(h.get_text(" ", strip=True))

    print("\n================ H3 ================")

    for h in soup.find_all("h3"):
        print(h.get_text(" ", strip=True))


def imprimir_tablas(soup):

    tablas = soup.find_all("table")

    print(f"\nTablas encontradas: {len(tablas)}")

    for i, tabla in enumerate(tablas[:5], start=1):

        print(f"\n========== TABLA {i} ==========")

        texto = tabla.get_text("\n", strip=True)

        print(texto[:3000])


def buscar_palabras(html):

    palabras = [
        "estado",
        "estados",
        "financiero",
        "financieros",
        "contable",
        "contables",
        "balance",
        "situacion",
        "situación",
        "resultado",
        "patrimonio",
        "cash",
        "flujo",
        "memoria",
        "hecho relevante",
        "prospecto",
        "asamblea",
        "trimestre",
        "ejercicio",
    ]

    print("\n================ PALABRAS CLAVE ================\n")

    html_lower = html.lower()

    for palabra in palabras:

        if palabra in html_lower:
            print("✓", palabra)


def buscar_json(html):

    print("\n================ JSON EMBEBIDO ================\n")

    scripts = re.findall(
        r"<script.*?>(.*?)</script>",
        html,
        flags=re.S | re.I,
    )

    encontrados = False

    for script in scripts:

        if any(
            x in script.lower()
            for x in [
                "presentation",
                "document",
                "json",
                "model",
                "initial",
                "state",
            ]
        ):
            encontrados = True

            print("=" * 80)
            print(script[:4000])
            print()

    if not encontrados:
        print("No se detectó JSON embebido evidente.")


def buscar_urls(html):

    print("\n================ URLS =================\n")

    urls = sorted(set(re.findall(r"https?://[^\"]+", html)))

    for url in urls[:100]:
        print(url)

    print(f"\nTotal URLs: {len(urls)}")


def buscar_guid(html):

    print("\n================ GUID =================\n")

    guids = sorted(set(re.findall(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        html,
        re.I,
    )))

    print(f"GUID encontrados: {len(guids)}")

    for g in guids[:20]:
        print(g)


def guardar_html(guid, html):

    carpeta = Path("debug")

    carpeta.mkdir(exist_ok=True)

    archivo = carpeta / f"{guid}.html"

    archivo.write_text(
        html,
        encoding="utf-8",
    )

    print(f"\nHTML guardado en:\n{archivo.resolve()}")


def main():

    if len(sys.argv) > 1:

        guid = sys.argv[1]

    else:

        guid = input("GUID: ").strip()

    print("\nDescargando...\n")

    html = obtener_html(guid)

    guardar_html(guid, html)

    soup = BeautifulSoup(html, "lxml")

    imprimir_encabezados(soup)

    buscar_palabras(html)

    imprimir_tablas(soup)

    buscar_json(html)

    buscar_urls(html)

    buscar_guid(html)

    print("\n================ FIN =================")


if __name__ == "__main__":
    main()