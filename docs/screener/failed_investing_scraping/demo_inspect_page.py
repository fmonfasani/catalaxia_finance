#!/usr/bin/env python3
"""
Script para inspeccionar la página de login de Investing.com
y encontrar dónde están realmente los campos
"""

import asyncio
from playwright.async_api import async_playwright
from datetime import datetime

def log(msg):
    """Log a archivo y consola"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_msg = f"[{timestamp}] {msg}"
    print(log_msg)
    with open("inspect_debug.log", "a", encoding="utf-8") as f:
        f.write(log_msg + "\n")

async def main():
    log("="*100)
    log("INSPECCIONANDO PÁGINA DE LOGIN DE INVESTING.COM")
    log("="*100)
    log("")

    async with async_playwright() as p:
        log("[1] Abriendo navegador (VISIBLE)...")
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        log("[2] Navegando a login...")
        await page.goto("https://es.investing.com/login/", wait_until="domcontentloaded")
        log("[3] Página cargada")

        # Esperar un poco para que JavaScript cargue
        await asyncio.sleep(3)
        log("[4] Esperado 3 segundos para JavaScript")

        # Guardar HTML completo INMEDIATAMENTE
        html = await page.content()
        with open("login_page.html", "w", encoding="utf-8") as f:
            f.write(html)
        log("[5] HTML guardado en: login_page.html")
        log(f"    Tamaño: {len(html)} bytes")

        # Buscar iframes
        log("[6] Buscando iframes...")
        iframes = await page.query_selector_all("iframe")
        log(f"    Iframes encontrados: {len(iframes)}")
        for i, iframe in enumerate(iframes):
            src = await iframe.get_attribute("src")
            title = await iframe.get_attribute("title")
            name = await iframe.get_attribute("name")
            log(f"      [{i}] src={src}, title={title}, name={name}")

        # Buscar inputs de email
        log("[7] Buscando inputs de email...")
        email_inputs = await page.query_selector_all('input[type="email"]')
        log(f"    Inputs type=email: {len(email_inputs)}")

        # Buscar inputs con name email
        log("[8] Buscando inputs name=email...")
        email_name = await page.query_selector_all('input[name="email"]')
        log(f"    Inputs name=email: {len(email_name)}")

        # Buscar TODOS los inputs
        log("[9] Buscando TODOS los inputs...")
        all_inputs = await page.query_selector_all("input")
        log(f"    Total inputs: {len(all_inputs)}")
        for i, inp in enumerate(all_inputs[:20]):  # Mostrar primeros 20
            inp_type = await inp.get_attribute("type")
            inp_name = await inp.get_attribute("name")
            inp_id = await inp.get_attribute("id")
            inp_placeholder = await inp.get_attribute("placeholder")
            log(f"      [{i}] type={inp_type}, name={inp_name}, id={inp_id}, placeholder={inp_placeholder}")

        # Buscar formularios
        log("[10] Buscando formularios...")
        forms = await page.query_selector_all("form")
        log(f"     Formularios: {len(forms)}")
        for i, form in enumerate(forms):
            form_id = await form.get_attribute("id")
            form_class = await form.get_attribute("class")
            log(f"       [{i}] id={form_id}, class={form_class}")

        # Buscar botones submit
        log("[11] Buscando botones...")
        buttons = await page.query_selector_all("button")
        log(f"     Botones: {len(buttons)}")
        for i, btn in enumerate(buttons[:10]):
            btn_type = await btn.get_attribute("type")
            btn_text = await btn.text_content()
            btn_class = await btn.get_attribute("class")
            log(f"       [{i}] type={btn_type}, text='{btn_text.strip() if btn_text else ''}', class={btn_class}")

        # Buscar elementos con "email" en el texto
        log("[12] Buscando elementos con 'email' o 'password'...")
        labels = await page.query_selector_all("label")
        log(f"     Labels: {len(labels)}")
        for i, label in enumerate(labels[:10]):
            label_text = await label.text_content()
            label_for = await label.get_attribute("for")
            log(f"       [{i}] for={label_for}, text='{label_text.strip() if label_text else ''}'")

        # Extraer todo el texto
        log("[13] Extrayendo todo el texto visible...")
        all_text = await page.evaluate("() => document.body.innerText")
        with open("login_page_text.txt", "w", encoding="utf-8") as f:
            f.write(all_text)
        log(f"     Texto guardado en: login_page_text.txt ({len(all_text)} caracteres)")

        # Buscar shadow roots
        log("[14] Buscando Shadow DOM...")
        shadow_roots = await page.evaluate("""
            () => {
                const elements = document.querySelectorAll('*');
                let count = 0;
                elements.forEach(el => {
                    if (el.shadowRoot) {
                        count++;
                    }
                });
                return count;
            }
        """)
        log(f"     Shadow roots encontrados: {shadow_roots}")

        # Detectar si es un bot
        log("[15] Verificando si detectó bot...")
        error_text = await page.evaluate("() => document.body.innerText")
        if "bot" in error_text.lower() or "robot" in error_text.lower():
            log("     ⚠️ POSIBLE DETECCIÓN DE BOT")

        log("")
        log("="*100)
        log("✅ Inspección completada")
        log("   Archivos generados:")
        log("   - login_page.html (estructura completa)")
        log("   - login_page_text.txt (texto visible)")
        log("   - inspect_debug.log (este log)")
        log("="*100)
        log("")
        log("Mantén el navegador abierto para ver la página (presiona Enter en la consola para cerrar)")

        await context.close()
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
