#!/usr/bin/env python3
"""
DEMO INTERACTIVA: Loguea y abre página para inspeccionar con F11
"""

import asyncio
from playwright.async_api import async_playwright

INVESTING_USER = "contacto@catalaxia.com.ar"
INVESTING_PASS = "Expl.Inv.25$"

async def main():
    async with async_playwright() as p:
        print("=" * 100)
        print("DEMO INTERACTIVA: Inspeccionando Investing.com")
        print("=" * 100)
        print()
        print("Voy a:")
        print("1. Abrir navegador VISIBLE")
        print("2. Loguear automáticamente")
        print("3. Ir a AAPL Financials")
        print("4. Mantener navegador abierto para que vos inspecciones con F11")
        print()

        browser = await p.chromium.launch(
            headless=False,  # ← VISIBLE
            args=['--disable-dev-shm-usage', '--no-sandbox']
        )

        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
        )

        page = await context.new_page()

        print("[1] Navegando a login...")
        await page.goto("https://es.investing.com/login/", wait_until="domcontentloaded")
        await asyncio.sleep(2)

        print("[2] Ingresando email...")
        await page.fill('#loginFormUser_email', INVESTING_USER)
        await asyncio.sleep(1)

        print("[3] Ingresando password...")
        await page.fill('#loginForm_password', INVESTING_PASS)
        await asyncio.sleep(1)

        print("[4] Haciendo click en login...")
        await page.click('a.newButton.orange')
        await asyncio.sleep(5)

        print("[5] Navegando a AAPL Financials...")
        await page.goto("https://es.investing.com/equities/aapl/financials", wait_until="domcontentloaded")
        await asyncio.sleep(3)

        print()
        print("=" * 100)
        print("✅ PÁGINA CARGADA")
        print("=" * 100)
        print()
        print("AHORA:")
        print()
        print("1️⃣  Presiona F11 para abrir Developer Tools")
        print("2️⃣  Selecciona el Inspector (Elements/HTML)")
        print("3️⃣  Busca dónde están los datos financieros")
        print("4️⃣  Copia la estructura HTML completa")
        print()
        print("BUSCA:")
        print("  - ¿Están en <table>?")
        print("  - ¿Están en <div class='...'>?")
        print("  - ¿Qué clase tiene el contenedor?")
        print("  - ¿Cómo se estructura cada fila?")
        print()
        print("TOMA SCREENSHOT o COPIA el HTML del contenedor de datos")
        print()
        print("=" * 100)
        print()
        print("Presiona Enter cuando hayas terminado de inspeccionar...")
        input()

        await context.close()
        await browser.close()

        print()
        print("✅ Navegador cerrado")
        print()
        print("Ahora pega aquí la estructura HTML que encontraste")

if __name__ == "__main__":
    asyncio.run(main())
