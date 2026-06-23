#!/usr/bin/env python3
"""
DEMO COMPARATIVA: SEC EDGAR vs Investing.com
Scraping con Playwright + DEBUG DETALLADO
"""

import json
import os
import asyncio
from playwright.async_api import async_playwright
from datetime import datetime

# Credenciales (uso local únicamente)
INVESTING_USER = "contacto@catalaxia.com.ar"
INVESTING_PASS = "Expl.Inv.25$"

EMPRESAS = {
    "USA": ["AAPL", "MSFT", "NVDA", "TSLA", "AMZN"],
    "ARG": ["YPF", "PAMPA", "EDN"]
}

LOG_FILE = "scraping_debug.log"

def log(msg):
    """Log a archivo y consola"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_msg = f"[{timestamp}] {msg}"
    print(log_msg)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(log_msg + "\n")

async def scrapear_investing_debug(ticker):
    """
    Scrapeá Investing.com con mucho logging
    """
    log(f"\n{'='*100}")
    log(f"INICIANDO SCRAPING DE {ticker}")
    log(f"{'='*100}")

    try:
        async with async_playwright() as p:
            log(f"  [1] Iniciando navegador Chromium...")
            browser = await p.chromium.launch(headless=False)  # headless=False para ver qué pasa
            context = await browser.new_context()
            page = await context.new_page()

            log(f"  [2] Navegador abierto")

            # LOGIN
            log(f"  [3] Navigando a login...")
            await page.goto("https://es.investing.com/login/", wait_until="domcontentloaded")
            log(f"  [4] Página de login cargada")

            # ESPERAR 15 SEGUNDOS PARA QUE INGRESE CREDENCIALES MANUALMENTE
            log(f"")
            log(f"  ╔════════════════════════════════════════════════════════════════════════════════════════════════════╗")
            log(f"  ║ *** INGRESA LAS CREDENCIALES MANUALMENTE EN EL NAVEGADOR ***                                      ║")
            log(f"  ║                                                                                                    ║")
            log(f"  ║ Usuario: contacto@catalaxia.com.ar                                                                ║")
            log(f"  ║ Password: Expl.Inv.25$                                                                             ║")
            log(f"  ║                                                                                                    ║")
            log(f"  ║ Tienes 15 segundos...                                                                             ║")
            log(f"  ╚════════════════════════════════════════════════════════════════════════════════════════════════════╝")
            log(f"")

            for i in range(15, 0, -1):
                log(f"  [5] {i:2d} segundos restantes...")
                await asyncio.sleep(1)

            log(f"  [6] 15 segundos completados, esperando a que se complete el login automáticamente...")
            log(f"")

            # Esperar a que se redirija (después del login manual)
            try:
                await asyncio.sleep(3)  # Esperar 3 segundos más para que se redirija
                current_url = page.url
                log(f"  [7] URL actual después del login: {current_url}")
            except Exception as e:
                log(f"  [7] ⚠️ Error obteniendo URL: {e}")

            # Navegar a financials
            url = f"https://es.investing.com/equities/{ticker.lower()}/financials"
            log(f"  [17] Navegando a {url}...")
            await page.goto(url, wait_until="domcontentloaded")
            log(f"  [18] Página de financials cargada")

            # Guardar HTML para inspeccionar
            html = await page.content()
            html_file = f"investing_{ticker}_debug.html"
            with open(html_file, "w", encoding="utf-8") as f:
                f.write(html)
            log(f"  [19] HTML guardado en: {html_file}")

            # Esperar tablas
            log(f"  [20] Buscando tablas...")
            tables = await page.query_selector_all("table")
            log(f"  [21] Tablas encontradas: {len(tables)}")

            # Buscar divs con datos
            log(f"  [22] Buscando divs de datos...")
            divs = await page.query_selector_all("div[data-field]")
            log(f"  [23] Divs con data-field: {len(divs)}")

            # Buscar spans
            log(f"  [24] Buscando spans...")
            spans = await page.query_selector_all("span")
            log(f"  [25] Spans encontrados: {len(spans)}")

            # Extraer todos los textos visibles
            log(f"  [26] Extrayendo textos visibles...")
            all_text = await page.evaluate("""
                () => {
                    return document.body.innerText;
                }
            """)
            text_file = f"investing_{ticker}_text.txt"
            with open(text_file, "w", encoding="utf-8") as f:
                f.write(all_text)
            log(f"  [27] Texto guardado en: {text_file}")

            # Extraer estructura JSON
            log(f"  [28] Buscando JSON en página...")
            scripts = await page.query_selector_all("script")
            log(f"  [29] Scripts encontrados: {len(scripts)}")

            # Intentar extraer datos de cualquier tabla
            log(f"  [30] Extrayendo datos de tablas...")
            data = await page.evaluate("""
                () => {
                    const result = {};
                    const tables = document.querySelectorAll('table');
                    let table_count = 0;

                    tables.forEach(table => {
                        table_count++;
                        const rows = table.querySelectorAll('tr');
                        rows.forEach(row => {
                            const cells = row.querySelectorAll('td');
                            if (cells.length >= 2) {
                                const label = cells[0].textContent.trim();
                                const value = cells[1].textContent.trim();
                                if (label && value && label.length > 0) {
                                    result[label] = value;
                                }
                            }
                        });
                    });

                    return {
                        data: result,
                        table_count: table_count,
                        total_rows: document.querySelectorAll('tr').length
                    };
                }
            """)

            log(f"  [31] Tablas procesadas: {data.get('table_count', 0)}")
            log(f"  [32] Filas totales: {data.get('total_rows', 0)}")
            log(f"  [33] Datos extraídos: {len(data.get('data', {}))} campos")

            if data.get('data'):
                log(f"  [34] Campos encontrados:")
                for key, value in list(data['data'].items())[:10]:
                    log(f"       - {key}: {value}")

            log(f"  [35] *** EL NAVEGADOR PERMANECERÁ ABIERTO POR 30 SEGUNDOS PARA QUE VEAS LOS DATOS ***")
            await asyncio.sleep(30)

            await context.close()
            await browser.close()

            log(f"  [36] Navegador cerrado")
            log(f"✅ {ticker} completado")

            return data.get('data', {})

    except Exception as e:
        log(f"❌ ERROR: {str(e)}")
        import traceback
        log(f"TRACEBACK:\n{traceback.format_exc()}")
        return None


async def main():
    log("=" * 100)
    log("📊 DEMO COMPARATIVA: SEC EDGAR vs Investing.com (DEBUG MODE)")
    log("=" * 100)
    log("")

    log("🔐 Autenticando en Investing.com...")
    log(f"   Usuario: {INVESTING_USER}")
    log("")

    investing_data = {}

    log("📥 SCRAPEANDO INVESTING.COM (CON LOGGING)")
    log("-" * 100)

    # Solo hacer AAPL primero para debug
    ticker = "AAPL"
    log(f"\nProcesando {ticker}...")
    data = await scrapear_investing_debug(ticker)
    if data:
        investing_data[ticker] = data

    log("")
    log("=" * 100)
    log("📊 RESULTADOS")
    log("=" * 100)
    log("")

    log("Investing.com data scraped:")
    log(json.dumps(investing_data, indent=2, ensure_ascii=False))

    # Guardar datos
    with open("investing_data_debug.json", "w", encoding="utf-8") as f:
        json.dump(investing_data, f, indent=2, ensure_ascii=False)

    log("")
    log("=" * 100)
    log(f"✅ Log guardado en: {LOG_FILE}")
    log(f"✅ Datos guardados en: investing_data_debug.json")
    log(f"✅ HTML de AAPL guardado en: investing_aapl_debug.html")
    log(f"✅ Texto de AAPL guardado en: investing_aapl_text.txt")
    log("=" * 100)


if __name__ == "__main__":
    asyncio.run(main())
