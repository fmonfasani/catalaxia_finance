import requests

url = "https://www.cnv.gov.ar/SitioWeb/Empresas/Empresa/30501250305"

headers = {
    "User-Agent": "Mozilla/5.0"
}

print("Consultando...")

r = requests.get(
    url,
    headers=headers,
    timeout=120
)

print(r.status_code)
print(len(r.text))

with open("ledesma.html", "w", encoding="utf8") as f:
    f.write(r.text)

print("HTML guardado")