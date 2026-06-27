import re
import requests
from bs4 import BeautifulSoup

URL = "https://www.cnv.gov.ar/SitioWeb/Empresas/Empresa/30501250305"

headers = {
    "User-Agent": "Mozilla/5.0"
}

html = requests.get(URL, headers=headers).text

print("HTML:", len(html))

soup = BeautifulSoup(html, "html.parser")

guids = set()

# Buscar links
for a in soup.find_all("a", href=True):

    href = a["href"]

    if "presentations/publicview" in href:
        guids.add(href)

# Buscar GUID dentro del HTML
regex = r'presentations/publicview/([a-f0-9\-]{36})'

for guid in re.findall(regex, html, re.I):

    guids.add(
        f"https://aif2.cnv.gov.ar/presentations/publicview/{guid}"
    )

print()

print("GUIDS ENCONTRADOS")

for g in sorted(guids):

    print(g)

print()

print("TOTAL:", len(guids))