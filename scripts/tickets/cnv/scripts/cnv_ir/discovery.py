# -*- coding: utf-8 -*-
"""
Discovery robusto del PDF de EEFF por empresa. NO adivina URLs sueltas: parte del
catalogo curado, baja la pagina de IR y busca el link al EEFF mas reciente.

Estrategia (en orden):
  1. URLs del catalogo -> buscar links .pdf que matcheen patrones de EEFF.
  2. Si la pagina de IR linkea a una sub-pagina de "inversores/estados", seguirla.
  3. Fallback: bolsar (BYMA) por ticker.

Devuelve [(url_pdf, score)] ordenado por recencia estimada (fecha en el nombre).
"""
from __future__ import annotations
import re, requests, warnings
warnings.filterwarnings("ignore")

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120",
      "Accept-Language": "es-AR,es"}

PAT_EEFF = re.compile(r"eeff|estado.?contab|estados?.?financ|estado.?de.?situaci|"
                      r"balance|trimestr|memoria.?y.?estados|informaci[oó]n.?contable", re.I)
PAT_FECHA = re.compile(r"(20\d{2})[^\d]?([01]?\d)?")


def _abs(url, base):
    if url.startswith("http"):
        return url
    if url.startswith("//"):
        return "https:" + url
    m = re.match(r"(https?://[^/]+)", base)
    raiz = m.group(1) if m else base
    return raiz + (url if url.startswith("/") else "/" + url)


def _get(url, timeout=12):
    try:
        r = requests.get(url, headers=UA, timeout=timeout, verify=False)
        if r.status_code == 200:
            return r.text
    except Exception:
        return None
    return None


def _score(url):
    """recencia estimada por la fecha en el nombre (mayor = mas nuevo)."""
    nombre = url.rsplit("/", 1)[-1]
    años = [int(a) for a, _ in PAT_FECHA.findall(nombre) if a]
    return max(años) if años else 0


def descubrir_eeff(ticker, catalogo=None, seguir_subpaginas=True):
    """Devuelve lista de URLs de PDF de EEFF (mas reciente primero) o []."""
    if catalogo is None:
        from catalogo_ir import CATALOGO as catalogo
    info = catalogo.get(ticker)
    urls_ir = info[3] if info else []      # (nombre, sector, cierre, urls)
    pdfs = set()
    subpaginas = []
    for ir in urls_ir:
        html = _get(ir)
        if not html:
            continue
        for href in re.findall(r'href=[\"\']([^\"\']+)', html):
            if href.lower().endswith(".pdf") and PAT_EEFF.search(href):
                pdfs.add(_abs(href, ir))
            elif seguir_subpaginas and re.search(r"estado|contab|financ|balance|invers", href, re.I) and not href.lower().endswith(".pdf"):
                subpaginas.append(_abs(href, ir))
    # seguir 1 nivel de subpaginas de estados
    for sp in subpaginas[:4]:
        html = _get(sp)
        if not html:
            continue
        for href in re.findall(r'href=[\"\']([^\"\']+\.pdf)', html, re.I):
            if PAT_EEFF.search(href):
                pdfs.add(_abs(href, sp))
    # ordenar por recencia
    return sorted(pdfs, key=_score, reverse=True)


def descubrir_todos(catalogo=None, solo=None):
    if catalogo is None:
        from catalogo_ir import CATALOGO as catalogo
    res = {}
    for tk in (solo or catalogo):
        res[tk] = descubrir_eeff(tk, catalogo)
    return res


if __name__ == "__main__":
    import sys
    from catalogo_ir import CATALOGO
    tickers = sys.argv[1:] or list(CATALOGO)
    print(f"{'Ticker':<8}{'EEFF encontrados':<18}{'ultimo'}")
    print("-" * 60)
    ok = 0
    for tk in tickers:
        pdfs = descubrir_eeff(tk, CATALOGO)
        if pdfs:
            ok += 1
            print(f"{tk:<8}{len(pdfs):<18}{pdfs[0].rsplit('/', 1)[-1][:38]}")
        else:
            print(f"{tk:<8}{'0':<18}(sin EEFF / IR bloqueado)")
    print(f"\nCon EEFF encontrado: {ok}/{len(tickers)}")
