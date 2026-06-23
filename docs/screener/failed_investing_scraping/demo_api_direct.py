#!/usr/bin/env python3
"""
Scraping directo vía API endpoint de Next.js
https://www.investing.com/_next/data/{BUILD_ID}/equities/{ticker}.json
"""

import requests
import json
from datetime import datetime

BUILD_ID = "dcd1b43"  # El que encontraste en Network
BASE_URL = "https://www.investing.com/_next/data/{}/equities/{}.json"

EMPRESAS = {
    "USA": ["aapl", "msft", "nvda", "tsla", "amzn"],
    "ARG": ["ypf-sa", "pampa", "edn"]
}

# Headers realistas
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Referer": "https://www.investing.com/equities/aapl",
    "Accept-Language": "es-419,es;q=0.9",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "DNT": "1",
    "Pragma": "no-cache",
    "Cache-Control": "no-cache",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
}

# Crear sesión para reutilizar conexiones y cookies
session = requests.Session()

# Cargar cookies guardadas
try:
    with open("investing_session.json") as f:
        session_data = json.load(f)
        cookies_list = session_data.get("cookies", [])
        for cookie in cookies_list:
            session.cookies.set(cookie['name'], cookie['value'])
        print(f"✅ {len(cookies_list)} cookies cargadas")
except FileNotFoundError:
    print("⚠️ Session file not found, intentando sin cookies...")

def obtener_datos_api(ticker):
    """Obtiene datos del API endpoint de Investing.com"""
    print(f"\n{'='*100}")
    print(f"OBTENIENDO {ticker.upper()}")
    print(f"{'='*100}")

    url = BASE_URL.format(BUILD_ID, ticker)
    print(f"  URL: {url}")

    try:
        response = session.get(url, headers=HEADERS, timeout=10)
        print(f"  Status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"  ✅ JSON recibido ({len(json.dumps(data))} bytes)")

            # Guardar JSON completo para inspeccionar
            with open(f"api_response_{ticker}.json", "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"  📄 Guardado en: api_response_{ticker}.json")

            # Mostrar estructura
            if 'pageProps' in data:
                print(f"  📊 pageProps encontrado")
                props = data['pageProps']

                # Mostrar claves principales
                if isinstance(props, dict):
                    print(f"     Claves: {list(props.keys())[:5]}")

                    # Buscar datos financieros
                    for key in props.keys():
                        if 'financial' in key.lower() or 'data' in key.lower():
                            print(f"     🎯 DATO FINANCIERO ENCONTRADO: {key}")

            return data
        else:
            print(f"  ❌ Error {response.status_code}: {response.text[:100]}")
            return None

    except Exception as e:
        print(f"  ❌ ERROR: {e}")
        return None

def main():
    print("=" * 100)
    print("📊 SCRAPING DIRECTO VÍA API - INVESTING.COM")
    print("=" * 100)
    print()

    print(f"Build ID: {BUILD_ID}")
    print(f"Base URL: {BASE_URL}")
    print()

    # Obtener datos para todas las empresas
    all_data = {}

    for ticker in EMPRESAS["USA"] + EMPRESAS["ARG"]:
        data = obtener_datos_api(ticker)
        if data:
            all_data[ticker] = data
        # Delay entre requests
        import time
        time.sleep(1)

    print()
    print("=" * 100)
    print(f"✅ RESUMEN")
    print("=" * 100)
    print(f"Datos obtenidos: {len(all_data)}/{len(EMPRESAS['USA']) + len(EMPRESAS['ARG'])}")
    print()
    print("Archivos generados:")
    for ticker in all_data.keys():
        print(f"  - api_response_{ticker}.json")
    print()
    print("=" * 100)
    print("⚠️ PRÓXIMO PASO")
    print("=" * 100)
    print()
    print("1. Abre uno de los archivos JSON (ej: api_response_aapl.json)")
    print("2. Inspecciona la estructura")
    print("3. Busca dónde están los datos financieros (Revenue, Net Income, P/E, etc.)")
    print("4. Pásame la estructura para que extraiga los datos específicos")
    print()

if __name__ == "__main__":
    main()
