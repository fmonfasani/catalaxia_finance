import requests

CIK = "0000021344"
URL = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{CIK}.json"

headers = {
    "User-Agent": "BYMAStocks contacto@example.com"
}

data = requests.get(URL, headers=headers, timeout=30)
data.raise_for_status()
facts = data.json()

revenue = facts["facts"]["us-gaap"]["Revenues"]

# Buscar el último valor anual disponible
annual = [
    x for x in revenue["units"]["USD"]
    if x.get("fp") == "FY"
    and x.get("form") == "10-K"
]

last = sorted(annual, key=lambda x: x["end"])[-1]

print("KO Revenue")
print("Periodo:", last["end"])
print("Valor:", last["val"])
print("Moneda: USD")
print("Fuente: SEC EDGAR")