#!/usr/bin/env python3
"""
Abre Investing.com login para inspeccionar con F11
"""

import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        print("=" * 100)
        print("INSPECCIONANDO INVESTING.COM LOGIN")
        print("=" * 100)
        print()
        print("1. Se abrirá el navegador VISIBLE")
        print("2. VOS presionas F11 para inspeccionar")
        print("3. Buscas los campos de email y password")
        print("4. Copias los selectores exactos (id, name, class, etc.)")
        print("5. Me los pasas en el chat")
        print()
        print("Abriendo navegador en 3 segundos...")
        print()

        browser = await p.chromium.launch(
            headless=False,  # ← VISIBLE
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
            ]
        )

        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
            locale='es-ES',
        )

        page = await context.new_page()

        print("🌐 Navegando a https://es.investing.com/login/")
        await page.goto("https://es.investing.com/login/", wait_until="domcontentloaded")

        print()
        print("=" * 100)
        print("✅ PÁGINA CARGADA")
        print("=" * 100)
        print()
        print("📍 QUÉ HACER AHORA:")
        print()
        print("1. Presiona F11 (Developer Tools)")
        print("2. Selecciona el Inspector (HTML)")
        print("3. Usa Ctrl+Shift+C para seleccionar elemento")
        print("4. Haz click en el campo de EMAIL")
        print("5. Copia el HTML que ves, especialmente:")
        print("   - El atributo ID")
        print("   - El atributo NAME")
        print("   - El atributo CLASS")
        print("   Ejemplo: <input id='user-email' name='email' class='form-control'/>")
        print()
        print("6. Haz lo mismo con el campo de PASSWORD")
        print("7. Y con el botón de SUBMIT")
        print()
        print("8. Pega la info en el chat")
        print()
        print("Presiona Enter en la consola cuando termines (o cierra el navegador)...")
        input()

        await context.close()
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
