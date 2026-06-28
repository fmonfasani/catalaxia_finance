from bs4 import BeautifulSoup
import re

with open("ledesma.html", encoding="utf8") as f:
    html = f.read()

print("Tamaño:", len(html))

print("\nCantidad de publicview:")
print(html.lower().count("publicview"))

print("\nCantidad de presentations:")
print(html.lower().count("presentations"))

print("\nCantidad de aif2:")
print(html.lower().count("aif2.cnv.gov.ar"))

print("\nGUID encontrados:")

guids = re.findall(
    r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
    html,
    re.I
)

print(len(guids))

for g in guids[:20]:
    print(g)