#!/usr/bin/env python3
"""
Guarda la sesión logueada y la reutiliza para evitar que Cloudflare bloquee
"""

import asyncio
import json
from playwright.async_api import async_playwright

INVESTING_USER = "contacto@catalaxia.com.ar"
INVESTING_PASS = "Expl.Inv.25$"

SESSION_FILE = "investing_session.json"

async def login_and_save_session():
    """Loguea y guarda las cookies"""
    print("=" * 100)
    print("GUARDANDO SESIÓN DE INVESTING.COM")
    print("=" * 100)
    print()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        print("[1] Navegando a login...")
        await page.goto("https://es.investing.com/login/", wait_until="domcontentloaded")
        await asyncio.sleep(2)

        print("[2] Ingresando credenciales...")
        await page.fill('#loginFormUser_email', INVESTING_USER)
        await asyncio.sleep(1)
        await page.fill('#loginForm_password', INVESTING_PASS)
        await asyncio.sleep(1)

        print("[3] Haciendo click en login...")
        await page.click('a.newButton.orange')
        await asyncio.sleep(10)

        print("[4] Guardando cookies...")
        cookies = await context.cookies()

        session_data = {
            "cookies": cookies,
            "url": page.url
        }

        with open(SESSION_FILE, "w") as f:
            json.dump(session_data, f, indent=2)

        print(f"[5] ✅ Sesión guardada en: {SESSION_FILE}")
        print(f"    Cookies: {len(cookies)}")
        print(f"    URL actual: {page.url}")

        await context.close()
        await browser.close()

async def scrapear_con_sesion(ticker):
    """Scrapeá usando la sesión guardada"""
    print(f"\n{'='*100}")
    print(f"SCRAPEANDO {ticker} (con sesión guardada)")
    print(f"{'='*100}")

    try:
        # Cargar sesión
        with open(SESSION_FILE) as f:
            session_data = json.load(f)

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)

            # Crear contexto CON las cookies guardadas
            context = await browser.new_context()

            # Restaurar cookies
            await context.add_cookies(session_data["cookies"])

            page = await context.new_page()

            # Ir a financials
            url = f"https://es.investing.com/equities/{ticker.lower()}/financials"
            print(f"  [1] Navegando a {url}...")
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            print(f"  [2] Página cargada")

            await asyncio.sleep(3)

            # Ver qué se cargó
            page_text = await page.evaluate("() => document.body.innerText")
            lines = [l.strip() for l in page_text.split('\n') if l.strip()]

            print(f"  [3] Primeras líneas:")
            for line in lines[:10]:
                print(f"      {line}")

            # Guardar HTML
            html = await page.content()
            with open(f"{ticker}_con_sesion.html", "w", encoding="utf-8") as f:
                f.write(html)
            print(f"  [4] HTML guardado")

            # Buscar tablas
            tables = await page.query_selector_all("table")
            print(f"  [5] Tablas encontradas: {len(tables)}")

            # Extraer datos
            if len(tables) > 0:
                data = await page.evaluate("""
                    () => {
                        const result = {};
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

                        return result;
                    }
                """)

                print(f"  [6] Datos extraídos: {len(data)} campos")
                if data:
                    for key, value in list(data.items())[:5]:
                        print(f"       {key}: {value}")

                return data
            else:
                print(f"  ❌ No se encontraron tablas")
                return {}

            await context.close()
            await browser.close()

    except FileNotFoundError:
        print(f"  ❌ Archivo de sesión no encontrado: {SESSION_FILE}")
        print(f"     Primero ejecuta: python demo_session_persistence.py --save")
        return {}
    except Exception as e:
        print(f"  ❌ ERROR: {e}")
        import traceback
        print(traceback.format_exc())
        return {}

async def main():
    import sys

    if "--save" in sys.argv:
        # Guardar sesión
        await login_and_save_session()
    else:
        # Usar sesión para scrapear
        print("=" * 100)
        print("DEMO: Scrapeando con sesión persistente")
        print("=" * 100)
        print()

        empresas = ["AAPL", "MSFT", "NVDA"]

        for ticker in empresas:
            data = await scrapear_con_sesion(ticker)
            await asyncio.sleep(2)

        print()
        print("=" * 100)
        print("✅ Completado")
        print("=" * 100)

if __name__ == "__main__":
    asyncio.run(main())
