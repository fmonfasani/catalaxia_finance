# -*- coding: utf-8 -*-
"""
Diagnostico de una URL de IR: dice si responde, cuantos links/PDFs tiene, cuales
matchean EEFF, y si linkea a subpaginas de inversores. Sirve para encontrar la
URL correcta del EEFF de una empresa y arreglar el catalogo.

Uso:
  python probar_url.py https://www.ledesma.com.ar/inversores
  python probar_url.py https://www.ledesma.com.ar/        # probar la home
"""
import sys, re, requests, warnings
warnings.filterwarnings("ignore")
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120", "Accept-Language": "es-AR"}


def probar(url):
    try:
        r = requests.get(url, headers=H, timeout=20, verify=False)
    except Exception as e:
        print(f"NO RESPONDE: {type(e).__name__}: {str(e)[:60]}")
        print("  -> URL mal escrita, o el sitio bloquea/no existe esa ruta.")
        return
    print(f"HTTP {r.status_code} | {len(r.text)//1024} KB de HTML\n")
    links = re.findall(r'href=[\"\']([^\"\']+)', r.text)
    pdfs = [l for l in links if l.lower().endswith(".pdf")]
    eeff = [l for l in pdfs if re.search(r"eeff|estado|contab|balance|trimestr|financ", l, re.I)]
    inv = [l for l in links if re.search(r"invers|estado|contab|financ|balance|accionis", l, re.I) and not l.lower().endswith(".pdf")]
    print(f"Links totales: {len(links)} | PDFs: {len(pdfs)} | PDFs tipo EEFF: {len(eeff)}")
    if eeff:
        print("\n>>> EEFF ENCONTRADOS (esta URL sirve para el catalogo):")
        for l in eeff[:8]:
            print(f"    {l}")
    elif pdfs:
        print("\nHay PDFs pero ninguno parece EEFF. Algunos:")
        for l in pdfs[:6]:
            print(f"    {l.rsplit('/',1)[-1][:60]}")
    if not pdfs and inv:
        print("\nSin PDFs aca, pero hay sub-paginas de inversores (proba estas):")
        for l in sorted(set(inv))[:8]:
            print(f"    {l}")
    if not links:
        print("\n(0 links en el HTML -> la pagina probablemente carga el contenido por")
        print(" JavaScript. requests no lo ve. Hay que abrir el sitio en el navegador,")
        print(" entrar a la seccion de estados contables, y copiar la URL del PDF directo.)")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("uso: python probar_url.py <URL>")
    else:
        probar(sys.argv[1])
