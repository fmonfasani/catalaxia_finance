#!/usr/bin/env python3
"""
DEMO COMPARATIVA: SEC EDGAR vs Investing.com
Scraping con Playwright + Stealth (para evadir Cloudflare)
"""

import json
import asyncio
from playwright.async_api import async_playwright
from datetime import datetime

INVESTING_USER = "contacto@catalaxia.com.ar"
INVESTING_PASS = "Expl.Inv.25$"

EMPRESAS = ["AAPL", "MSFT", "NVDA", "TSLA", "AMZN"]

LOG_FILE = "scraping_stealth.log"

def log(msg):
    """Log a archivo y consola"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_msg = f"[{timestamp}] {msg}"
    print(log_msg)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(log_msg + "\n")

async def bypass_cloudflare(page):
    """Bypass Cloudflare con stealth techniques"""
    log("  [*] Aplicando stealth techniques...")

    # Agregar User-Agent realista
    await page.set_extra_http_headers({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
        'Accept-Language': 'es-ES,es;q=0.9',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Referer': 'https://google.com/'
    })

    # Inyectar JavaScript para ocultar que es automatizado
    await page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {
            get: () => false,
        });

        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5],
        });

        Object.defineProperty(navigator, 'languages', {
            get: () => ['es-ES', 'es'],
        });

        window.chrome = {
            runtime: {}
        };
    """)

    log("  [*] Stealth techniques aplicadas")

async def scrapear_investing_stealth(ticker):
    """Scrapeá con stealth"""
    log(f"\n{'='*100}")
    log(f"SCRAPEANDO {ticker}")
    log(f"{'='*100}")

    try:
        async with async_playwright() as p:
            log(f"  [1] Abriendo navegador con opciones stealth...")

            browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                ]
            )

            context = await browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
                locale='es-ES',
                timezone_id='America/Argentina/Buenos_Aires',
            )

            page = await context.new_page()

            # Aplicar stealth
            await bypass_cloudflare(page)

            log(f"  [2] Navegador abierto")

            # LOGIN
            log(f"  [3] Navegando a login...")
            await page.goto("https://es.investing.com/login/", wait_until="domcontentloaded", timeout=30000)
            log(f"  [4] Página cargada")

            # Detectar si Cloudflare está bloqueando
            page_text = await page.evaluate("() => document.body.innerText")
            if "Cloudflare" in page_text or "security" in page_text.lower():
                log(f"  ⚠️ CLOUDFLARE DETECTADO - Esperando 10 segundos...")
                await asyncio.sleep(10)

            # Intentar llenar email
            log(f"  [5] Intentando rellenar formulario...")
            try:
                await page.fill('input[name="email"]', INVESTING_USER, timeout=5000)
                log(f"  [6] Email ingresado")
            except:
                log(f"  [6] No se encontró campo email, intentando otros selectores...")
                try:
                    await page.fill('input[type="email"]', INVESTING_USER)
                    log(f"  [6b] Email ingresado (type=email)")
                except:
                    log(f"  [6c] ❌ No se pudo ingresar email")
                    # Guardar HTML para inspeccionar
                    html = await page.content()
                    with open(f"cloudflare_{ticker}.html", "w", encoding="utf-8") as f:
                        f.write(html)
                    log(f"  [*] HTML guardado en: cloudflare_{ticker}.html")
                    return {}

            # Password
            try:
                await page.fill('input[name="password"]', INVESTING_PASS)
                log(f"  [7] Password ingresado")
            except:
                log(f"  [7] ❌ No se pudo ingresar password")
                return {}

            # Submit
            try:
                await page.click('button[type="submit"]')
                log(f"  [8] Submit presionado")
            except:
                log(f"  [8] ❌ No se pudo hacer click en submit")
                return {}

            # Esperar redirección
            log(f"  [9] Esperando redirección...")
            try:
                await page.wait_for_url("**/dashboard**", timeout=10000)
                log(f"  [10] ✅ Login exitoso")
            except:
                log(f"  [10] ⚠️ No se redirijo a dashboard, continuando...")

            # Navegar a financials
            url = f"https://es.investing.com/equities/{ticker.lower()}/financials"
            log(f"  [11] Navegando a {url}...")
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            log(f"  [12] Página cargada")

            # Esperar a que cargue contenido
            await asyncio.sleep(3)

            # Guardar HTML
            html = await page.content()
            with open(f"investing_{ticker}_stealth.html", "w", encoding="utf-8") as f:
                f.write(html)
            log(f"  [13] HTML guardado")

            # Extraer texto
            page_text = await page.evaluate("() => document.body.innerText")
            with open(f"investing_{ticker}_stealth.txt", "w", encoding="utf-8") as f:
                f.write(page_text)
            log(f"  [14] Texto guardado")
            log(f"  [*] Primeras líneas:")
            for line in page_text.split('\n')[:15]:
                if line.strip():
                    log(f"      {line.strip()}")

            # Buscar tablas
            tables = await page.query_selector_all("table")
            log(f"  [15] Tablas encontradas: {len(tables)}")

            # Buscar divs con datos
            divs = await page.query_selector_all("div[class*='financial'], div[class*='row'], div[class*='data']")
            log(f"  [16] Divs de datos encontrados: {len(divs)}")

            # Extraer datos
            data = await page.evaluate("""
                () => {
                    const result = {};

                    // Buscar en tablas
                    const tables = document.querySelectorAll('table');
                    tables.forEach(table => {
                        const rows = table.querySelectorAll('tr');
                        rows.forEach(row => {
                            const cells = row.querySelectorAll('td');
                            if (cells.length >= 2) {
                                const label = cells[0].textContent.trim();
                                const value = cells[1].textContent.trim();
                                if (label && value) {
                                    result[label] = value;
                                }
                            }
                        });
                    });

                    // Si no hay tablas, buscar en divs
                    if (Object.keys(result).length === 0) {
                        const rows = document.querySelectorAll('div[class*="row"]');
                        rows.forEach(row => {
                            const label = row.querySelector('[class*="label"], [class*="key"]')?.textContent.trim();
                            const value = row.querySelector('[class*="value"]')?.textContent.trim();
                            if (label && value) {
                                result[label] = value;
                            }
                        });
                    }

                    return result;
                }
            """)

            log(f"  [17] Datos extraídos: {len(data)} campos")
            if data:
                for key, value in list(data.items())[:10]:
                    log(f"       - {key}: {value}")

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
    log("📊 DEMO COMPARATIVA: SEC EDGAR vs Investing.com (STEALTH MODE)")
    log("=" * 100)
    log("")

    log("🔐 Autenticando en Investing.com...")
    log(f"   Usuario: {INVESTING_USER}")
    log("")

    investing_data = {}

    log("📥 SCRAPEANDO INVESTING.COM")
    log("-" * 100)

    for ticker in EMPRESAS:
        log(f"\nProcesando {ticker}...")
        data = await scrapear_investing_stealth(ticker)
        if data:
            investing_data[ticker] = data
        await asyncio.sleep(2)  # Delay entre requests

    log("")
    log("=" * 100)
    log("📊 RESULTADOS")
    log("=" * 100)
    log("")

    log("Investing.com data scraped:")
    log(json.dumps(investing_data, indent=2, ensure_ascii=False))

    # Guardar datos
    with open("investing_data_stealth.json", "w", encoding="utf-8") as f:
        json.dump(investing_data, f, indent=2, ensure_ascii=False)

    log("")
    log("=" * 100)
    log(f"✅ Log guardado en: {LOG_FILE}")
    log(f"✅ Datos guardados en: investing_data_stealth.json")
    log("=" * 100)


if __name__ == "__main__":
    asyncio.run(main())
