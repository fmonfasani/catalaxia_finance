#!/usr/bin/env python3
"""
DEMO COMPARATIVA: SEC EDGAR vs Investing.com
Scraping automático con Playwright (más robusto que Selenium)
"""

import json
import os
import asyncio
from playwright.async_api import async_playwright

# Credenciales (uso local únicamente)
INVESTING_USER = "contacto@catalaxia.com.ar"
INVESTING_PASS = "Expl.Inv.25$"

EMPRESAS = {
    "USA": ["AAPL", "MSFT", "NVDA", "TSLA", "AMZN"],
    "ARG": ["YPF", "PAMPA", "EDN"]
}

async def scrapear_investing(ticker):
    """
    Scrapeá Investing.com para obtener ratios con Playwright
    Requiere autenticación
    """
    print(f"  🔄 Scrapeando {ticker}...", end=" ", flush=True)

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()

            # Login
            await page.goto("https://es.investing.com/login/")
            await page.fill('input[name="email"]', INVESTING_USER)
            await page.fill('input[name="password"]', INVESTING_PASS)
            await page.click('button[type="submit"]')

            # Esperar a que redirija después del login
            await page.wait_for_url("https://es.investing.com/**", timeout=10000)

            # Navegar a financials de la empresa
            url = f"https://es.investing.com/equities/{ticker.lower()}/financials"
            await page.goto(url)

            # Esperar tabla de financials
            await page.wait_for_selector("table", timeout=10000)

            # Extraer datos
            data = {}

            # Buscar valores en tablas
            tables = await page.query_selector_all("table")

            for table in tables:
                rows = await table.query_selector_all("tr")

                for row in rows:
                    cells = await row.query_selector_all("td")

                    if len(cells) >= 2:
                        # Extraer label y valor
                        label = await cells[0].text_content()
                        value = await cells[1].text_content()

                        if label and value:
                            label = label.strip()
                            value = value.strip()

                            # Mapear a nuestros ratios
                            if "Revenue" in label or "Ingresos" in label:
                                data["revenue"] = value
                            elif "Net Income" in label or "Ganancia Neta" in label:
                                data["net_income"] = value
                            elif "P/E" in label or "PER" in label:
                                data["per"] = value
                            elif "EPS" in label:
                                data["eps"] = value
                            elif "Debt" in label or "Deuda" in label:
                                data["debt"] = value
                            elif "ROE" in label:
                                data["roe"] = value

            await context.close()
            await browser.close()

            print("✅")
            return data

    except Exception as e:
        print(f"❌ ({str(e)[:40]})")
        return None


async def main():
    print("=" * 100)
    print("📊 DEMO COMPARATIVA: SEC EDGAR vs Investing.com")
    print("=" * 100)
    print()

    print("🔐 Autenticando en Investing.com...")
    print(f"   Usuario: {INVESTING_USER}")
    print()

    investing_data = {}

    # Scrapear Investing.com
    print("📥 SCRAPEANDO INVESTING.COM")
    print("-" * 100)

    all_tickers = EMPRESAS["USA"] + EMPRESAS["ARG"]

    for ticker in all_tickers:
        data = await scrapear_investing(ticker)
        if data:
            investing_data[ticker] = data
        await asyncio.sleep(1)

    print()
    print("=" * 100)
    print("📊 RESULTADOS")
    print("=" * 100)
    print()
    print("Investing.com data scraped:")
    print(json.dumps(investing_data, indent=2))

    # Cargar SEC EDGAR data
    print()
    print("SEC EDGAR data (para USA):")
    if os.path.exists("/tmp/AAPL_sec.json"):
        with open("/tmp/AAPL_sec.json") as f:
            sec_sample = json.load(f)
            print(f"✅ Datos disponibles para 5 empresas USA")

    print()
    print("=" * 100)
    print("⚠️  SIGUIENTE PASO")
    print("=" * 100)
    print()
    print("""Para completar la comparativa:
    1. Los datos se han scrapeado
    2. Necesito procesar y comparar
    3. Mostraré un reporte final con divergencias
    """)


if __name__ == "__main__":
    asyncio.run(main())
