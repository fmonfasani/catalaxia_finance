# -*- coding: utf-8 -*-
"""
PILOTO de extraccion de estados contables argentinos (formato CNV/FACPCE).

La CNV esta geo-bloqueada, PERO los ADR argentinos adjuntan sus estados contables
INTERINOS (trimestrales) como exhibit en los 6-K de EDGAR (que SI es accesible).
Esos estados son el dato que el XBRL no tiene (trimestral), en formato CNV, y
NIC 29 coherente dentro del filing.

Este parser:
  1. baja el exhibit de estados financieros del 6-K (HTML).
  2. parsea el estado de resultados y el balance -> line items canonicos.
  3. valida con identidades contables (gross = rev - cogs; activo = pasivo + PN).

El mismo parser sirve para PDFs de la CNV cuando se acceda desde una IP argentina
(solo cambia la capa de descarga; la de parseo es la misma logica).
"""
from __future__ import annotations
import re, html as ihtml, requests
from pathlib import Path

UA = {"User-Agent": "catalaxia research fmonfasani@gmail.com"}

# etiqueta (regex, en ingles del 6-K) -> concepto canonico. Etiquetas especificas
# para no matchear el indice de notas. Orden importa (las mas largas primero).
PATRONES = [
    (r"Net revenue", "Revenue"),
    (r"Cost of sales", "COGS"),
    (r"Gross profit", "GrossProfit"),
    (r"NET PROFIT FOR THE PERIOD", "NetIncome"),
    (r"Total current assets", "AssetsCurrent"),
    (r"Total assets", "Assets"),
    (r"Total current liabilities", "LiabilitiesCurrent"),
    (r"Total liabilities", "Liabilities"),
    (r"Equity attributable to the owners of the Company", "Equity"),
    (r"Cash and cash equivalents at the end", "Cash"),
]


def num(s):
    s = s.strip().replace(",", "")
    neg = s.startswith("(") or s.startswith("-")
    s = s.strip("()").lstrip("-")
    try:
        return -float(s) if neg else float(s)
    except ValueError:
        return None


def descargar_exhibit(cik, accn, doc):
    """baja el HTML del exhibit de estados. accn sin guiones."""
    url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accn}/{doc}"
    r = requests.get(url, headers=UA, timeout=30)
    r.raise_for_status()
    return r.text


def a_texto(html):
    t = ihtml.unescape(re.sub("<[^>]+>", " ", html))
    return re.sub(r"[ \t]+", " ", t)


def extraer(texto):
    """Por cada concepto, toma la PRIMER aparicion de la etiqueta seguida de
    1-2 numeros (periodo actual | comparativo)."""
    out = {}
    NUMRE = r"\(?-?\d{1,3}(?:,\d{3})+\)?(?:\.\d+)?"
    for patron, concepto in PATRONES:
        if concepto in out:
            continue
        # etiqueta + gap no-greedy (salta refs de nota tipo "6 ") + 1-2 numeros
        m = re.search(patron + r".{0,20}?(" + NUMRE + r")\s+(" + NUMRE + r")", texto)
        if m:
            out[concepto] = (num(m.group(1)), num(m.group(2)))
    return out


def validar(d):
    """identidades contables (sobre el periodo actual)."""
    chk = []
    if all(k in d for k in ("Revenue", "COGS", "GrossProfit")):
        calc = d["Revenue"][0] + d["COGS"][0]   # COGS viene negativo
        err = abs(calc - d["GrossProfit"][0]) / abs(d["GrossProfit"][0]) * 100
        chk.append(("Gross = Revenue + COGS", err))
    if all(k in d for k in ("Assets", "Liabilities", "Equity")):
        calc = d["Liabilities"][0] + d["Equity"][0]
        err = abs(calc - d["Assets"][0]) / abs(d["Assets"][0]) * 100
        chk.append(("Activo = Pasivo + PN", err))
    return chk


if __name__ == "__main__":
    import json, sqlite3, glob
    con = sqlite3.connect(Path(__file__).resolve().parents[2] / "data" / "screener.db")
    cik = con.execute("SELECT cik FROM empresas WHERE ticker_ppal='LOMA' AND grupo='adr_arg'").fetchone()[0]
    con.close()
    html = descargar_exhibit(cik, "000171137526000038", "financialstatements1q26e.htm")
    d = extraer(a_texto(html))
    print("=== LOMA — estados Q1 2026 extraidos del 6-K (formato CNV) ===")
    print(f"{'concepto':<16}{'actual (Q1-26)':>18}{'comparativo':>18}")
    for c, (v1, v2) in d.items():
        print(f"  {c:<14}{(f'{v1:,.0f}' if v1 is not None else '-'):>18}{(f'{v2:,.0f}' if v2 is not None else '-'):>18}")
    print("\n=== Validacion por identidades contables ===")
    for nombre, err in validar(d):
        ok = "OK" if err < 1 else "REVISAR"
        print(f"  {nombre:<26} error {err:.2f}%  [{ok}]")
