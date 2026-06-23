#!/usr/bin/env python3
"""
Abre navegador para inspeccionar Network y encontrar API endpoints
"""

import asyncio
from playwright.async_api import async_playwright

INVESTING_USER = "contacto@catalaxia.com.ar"
INVESTING_PASS = "Expl.Inv.25$"

async def main():
    async with async_playwright() as p:
        print("=" * 100)
        print("INSPECCIONANDO NETWORK - FINDING API ENDPOINTS")
        print("=" * 100)
        print()

        browser = await p.chromium.launch(
            headless=False,  # VISIBLE
            args=['--disable-dev-shm-usage', '--no-sandbox']
        )

        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
        )

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

        print("[4] Navegando a AAPL Financials...")

        # Capturar todas las requests
        requests_list = []

        def handle_response(response):
            requests_list.append({
                "url": response.url,
                "status": response.status,
                "method": response.request.method,
            })

        page.on("response", handle_response)

        await page.goto("https://es.investing.com/equities/aapl/financials", wait_until="domcontentloaded")
        await asyncio.sleep(5)

        print()
        print("=" * 100)
        print("✅ PÁGINA CARGADA - REQUESTS CAPTURADAS")
        print("=" * 100)
        print()

        print("📊 REQUESTS DE INTERÉS (API/XHR/Fetch):")
        print()

        # Filtrar requests interesantes
        json_requests = [r for r in requests_list if 'json' in r['url'].lower() or 'api' in r['url'].lower() or 'financials' in r['url'].lower()]

        print(f"Total requests capturadas: {len(requests_list)}")
        print(f"Requests JSON/API: {len(json_requests)}")
        print()

        for i, req in enumerate(json_requests, 1):
            print(f"{i}. {req['status']} {req['method']}")
            print(f"   {req['url']}")
            print()

        print()
        print("=" * 100)
        print("🔍 QUÉ HACER AHORA:")
        print("=" * 100)
        print()
        print("1. Presiona F12 para abrir Developer Tools")
        print("2. Ve a la pestaña NETWORK")
        print("3. Recarga la página (Ctrl+R)")
        print("4. Busca requests a:")
        print("   - /api/*")
        print("   - /financials*")
        print("   - /data*")
        print("   - Cualquier request que devuelva JSON")
        print()
        print("5. Haz click en una request interesante")
        print("6. Ve a la pestaña RESPONSE")
        print("7. Busca la estructura de datos (números, métricas, etc.)")
        print()
        print("8. Copia la URL de la request y pégala aquí")
        print()
        print("=" * 100)
        print()

        print("Presiona Enter cuando hayas encontrado el API endpoint...")
        input()

        await context.close()
        await browser.close()

        print()
        print("✅ Navegador cerrado")

if __name__ == "__main__":
    asyncio.run(main())
