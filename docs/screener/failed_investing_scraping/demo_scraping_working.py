#!/usr/bin/env python3
"""
DEMO COMPARATIVA: SEC EDGAR vs Investing.com
Scraping con selectores CORRECTOS
"""

import json
import asyncio
from playwright.async_api import async_playwright
from datetime import datetime

INVESTING_USER = "contacto@catalaxia.com.ar"
INVESTING_PASS = "Expl.Inv.25$"

EMPRESAS = ["AAPL", "MSFT", "NVDA", "TSLA", "AMZN"]

LOG_FILE = "scraping_working.log"

def log(msg):
    """Log a archivo y consola"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_msg = f"[{timestamp}] {msg}"
    print(log_msg)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(log_msg + "\n")

async def scrapear_investing(ticker):
    """Scrapeá con selectores correctos"""
    log(f"\n{'='*100}")
    log(f"SCRAPEANDO {ticker}")
    log(f"{'='*100}")

    try:
        async with async_playwright() as p:
            log(f"  [1] Abriendo navegador...")
            browser = await p.chromium.launch(
                headless=True,
                args=['--disable-dev-shm-usage', '--no-sandbox']
            )

            context = await browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
            )

            page = await context.new_page()
            log(f"  [2] Navegador abierto")

            # LOGIN
            log(f"  [3] Navegando a login...")
            await page.goto("https://es.investing.com/login/", wait_until="domcontentloaded", timeout=30000)
            log(f"  [4] Página cargada")

            # Esperar a que cargue el formulario
            await asyncio.sleep(2)

            # Rellenar EMAIL con selector correcto
            log(f"  [5] Rellenando email en #loginFormUser_email...")
            try:
                await page.fill('#loginFormUser_email', INVESTING_USER)
                log(f"  [6] ✅ Email ingresado")
            except Exception as e:
                log(f"  [6] ❌ Error en email: {e}")
                return {}

            # Rellenar PASSWORD
            log(f"  [7] Rellenando password en #loginForm_password...")
            try:
                await page.fill('#loginForm_password', INVESTING_PASS)
                log(f"  [8] ✅ Password ingresado")
            except Exception as e:
                log(f"  [8] ❌ Error en password: {e}")
                return {}

            # Click en botón (es un <a> con class newButton orange)
            log(f"  [9] Haciendo click en botón login (a.newButton.orange)...")
            try:
                await page.click('a.newButton.orange')
                log(f"  [10] ✅ Click realizado")
            except Exception as e:
                log(f"  [10] ❌ Error en click: {e}")
                return {}

            # Esperar a que se redirija
            log(f"  [11] Esperando redirección...")
            try:
                await page.wait_for_url("**/dashboard**", timeout=15000)
                log(f"  [12] ✅ Login exitoso, redirección completada")
            except:
                log(f"  [12] ⚠️ No se redirijo a dashboard, continuando de todas formas...")

            # Navegar a financials
            url = f"https://es.investing.com/equities/{ticker.lower()}/financials"
            log(f"  [13] Navegando a {url}...")
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            log(f"  [14] Página cargada")

            # Esperar a que carguen datos
            await asyncio.sleep(3)

            # Guardar HTML y texto
            html = await page.content()
            with open(f"investing_{ticker}.html", "w", encoding="utf-8") as f:
                f.write(html)

            page_text = await page.evaluate("() => document.body.innerText")
            with open(f"investing_{ticker}.txt", "w", encoding="utf-8") as f:
                f.write(page_text)

            log(f"  [15] HTML y texto guardados")

            # Mostrar primeras líneas de texto
            lines = [l.strip() for l in page_text.split('\n') if l.strip()]
            log(f"  [*] Primeras líneas de la página:")
            for line in lines[:20]:
                log(f"      {line}")

            # Buscar tablas
            tables = await page.query_selector_all("table")
            log(f"  [16] Tablas encontradas: {len(tables)}")

            # Extraer datos de tablas
            data = await page.evaluate("""
                () => {
                    const result = {};
                    const tables = document.querySelectorAll('table');

                    tables.forEach(table => {
                        const rows = table.querySelectorAll('tr');
                        rows.forEach(row => {
                            const cells = row.querySelectorAll('td, th');
                            if (cells.length >= 2) {
                                const label = cells[0].textContent.trim();
                                const value = cells[1].textContent.trim();
                                if (label && value && label.length > 3) {
                                    result[label] = value;
                                }
                            }
                        });
                    });

                    return result;
                }
            """)

            log(f"  [17] Datos extraídos: {len(data)} campos")
            if data:
                for key, value in list(data.items())[:15]:
                    log(f"       {key}: {value}")

            await context.close()
            await browser.close()

            log(f"✅ {ticker} completado")
            return data

    except Exception as e:
        log(f"❌ ERROR: {str(e)}")
        import traceback
        log(f"TRACEBACK:\n{traceback.format_exc()}")
        return None


async def main():
    log("=" * 100)
    log("📊 DEMO COMPARATIVA: SEC EDGAR vs Investing.com")
    log("=" * 100)
    log("")

    log("🔐 Credenciales:")
    log(f"   Usuario: {INVESTING_USER}")
    log("")

    log("Selectores encontrados:")
    log("   Email: #loginFormUser_email")
    log("   Password: #loginForm_password")
    log("   Submit: a.newButton.orange")
    log("")

    investing_data = {}

    log("📥 SCRAPEANDO INVESTING.COM")
    log("-" * 100)

    for ticker in EMPRESAS:
        log(f"\nProcesando {ticker}...")
        data = await scrapear_investing(ticker)
        if data:
            investing_data[ticker] = data
        await asyncio.sleep(3)  # Delay entre requests

    log("")
    log("=" * 100)
    log("📊 RESULTADOS")
    log("=" * 100)
    log("")

    log("Investing.com data:")
    for ticker, data in investing_data.items():
        log(f"\n{ticker}:")
        log(f"  Campos: {len(data)}")
        for key, value in list(data.items())[:5]:
            log(f"    {key}: {value}")

    # Guardar JSON
    with open("investing_data_final.json", "w", encoding="utf-8") as f:
        json.dump(investing_data, f, indent=2, ensure_ascii=False)

    log("")
    log("=" * 100)
    log(f"✅ Log: {LOG_FILE}")
    log(f"✅ Datos: investing_data_final.json")
    log(f"✅ HTML: investing_*.html")
    log(f"✅ Texto: investing_*.txt")
    log("=" * 100)


if __name__ == "__main__":
    asyncio.run(main())
