from playwright.sync_api import sync_playwright
import pandas as pd
import time

EMPRESA = "https://www.cnv.gov.ar/SitioWeb/Empresas/Empresa/30501250305"


def esperar(page):
    page.wait_for_load_state("networkidle")
    time.sleep(2)


with sync_playwright() as p:

    browser = p.chromium.launch(headless=False)

    page = browser.new_page()

    page.goto(EMPRESA)

    esperar(page)

    print("Página cargada")

    # ------------------------------
    # BUSCAR TODOS LOS LINKS publicview
    # ------------------------------

    enlaces = []

    for a in page.locator("a").all():

        href = a.get_attribute("href")

        if href and "publicview" in href:
            enlaces.append(href)

    enlaces = list(set(enlaces))

    print(f"Encontrados {len(enlaces)} balances")

    for url in enlaces:

        print(url)

    # ------------------------------
    # EXTRAER TABLA
    # ------------------------------

    for url in enlaces:

        print("Procesando", url)

        page.goto(url)

        esperar(page)

        filas = []

        # ESTA PARTE HAY QUE AJUSTAR CON LOS
        # SELECTORES REALES DE LA TABLA

        tabla = page.locator("table")

        trs = tabla.locator("tr").all()

        for tr in trs:

            tds = tr.locator("td").all_inner_texts()

            if len(tds) >= 3:

                filas.append({
                    "codigo": tds[0],
                    "descripcion": tds[1],
                    "importe": tds[2]
                })

        if filas:

            df = pd.DataFrame(filas)

            guid = url.split("/")[-1]

            df.to_csv(
                f"{guid}.csv",
                index=False,
                encoding="utf-8-sig"
            )

            print("OK", guid)

    browser.close()