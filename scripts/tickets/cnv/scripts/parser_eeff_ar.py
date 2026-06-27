# -*- coding: utf-8 -*-
"""
Parser de EEFF argentinos (PDF en espanol, formato CNV/FACPCE) bajados del IR de
la empresa. La CNV portal esta geo-bloqueada, pero las empresas publican los
MISMOS estados contables en su sitio de inversores (accesible).

Usa extract_tables de pdfplumber (preserva columnas -> evita la ambiguedad de
numeros concatenados del texto plano). Mapea etiquetas en espanol a conceptos
canonicos y valida por identidades contables.

Numeros argentinos: punto=miles, coma=decimal. 4 columnas tipicas:
[acum. periodo actual | acum. anterior | trimestre actual | trimestre anterior].
Tomamos la 1ra (acumulado del periodo) para flujos.
"""
from __future__ import annotations
import re

# etiqueta espanol -> concepto canonico. CASE-SENSITIVE: los totales en MAYUSCULA
# matchean solo el gran total (no los subtotales "Total del activo corriente").
ETIQUETAS_AR = [
    (r"Ventas netas", "Revenue"),
    (r"Costo de ventas", "COGS"),
    (r"Resultado Bruto", "GrossProfit"),
    (r"RESULTADO INTEGRAL TOTAL", "ResultadoIntegral"),
    (r"TOTAL DEL ACTIVO", "Assets"),
    (r"Total del activo corriente", "AssetsCurrent"),
    (r"TOTAL DEL PASIVO", "Liabilities"),
    (r"Total del pasivo corriente", "LiabilitiesCurrent"),
    (r"TOTAL DEL PATRIMONIO", "Equity"),
    (r"Efectivo y equivalentes", "Cash"),
]
NUM_AR = r"\(?\d{1,3}(?:\.\d{3})+\)?"


def num_ar(s):
    """'(1.498.010.431.426)' -> -1498010431426.0"""
    if s is None:
        return None
    s = str(s).strip()
    neg = s.startswith("(") or s.startswith("-")
    s = re.sub(r"[^\d,]", "", s.strip("()"))   # saca puntos de miles y simbolos
    s = s.replace(",", ".")                      # coma decimal -> punto
    if not s or s == ".":
        return None
    try:
        v = float(s)
        return -v if neg else v
    except ValueError:
        return None


def primer_valor(celdas):
    """De las celdas de una fila (label, val1, val2,...) devuelve el 1er numero."""
    for c in celdas[1:]:
        v = num_ar(c)
        if v is not None:
            return v
    return None


def parsear_pdf(path):
    """Extrae texto, junta numeros partidos por el PDF, y por cada etiqueta toma
    el 1er numero (columna 'acumulado del periodo'). Case-sensitive."""
    import pdfplumber, warnings
    warnings.filterwarnings("ignore")
    with pdfplumber.open(path) as pdf:
        txt = " ".join((p.extract_text() or "") for p in pdf.pages)
    txt = re.sub(r"\s+", " ", txt)
    txt = re.sub(r"(?<=\d)\s+(?=[\d.])", "", txt)     # une "1 .526" -> "1.526"
    out = {}
    for patron, concepto in ETIQUETAS_AR:
        if concepto in out:
            continue
        m = re.search(patron + r"[^\d(]{0,40}?(" + NUM_AR + r")", txt)   # SIN re.I
        if m:
            out[concepto] = num_ar(m.group(1))
    # NetIncome <- Resultado Integral (la linea limpia; resultado neto se concatena mal)
    if "NetIncome" not in out and "ResultadoIntegral" in out:
        out["NetIncome"] = out["ResultadoIntegral"]
    return out


def validar(d):
    chk = {}
    if all(k in d for k in ("Assets", "Liabilities", "Equity")):
        c = d["Liabilities"] + d["Equity"]
        chk["Activo=Pas+PN"] = abs(c - d["Assets"]) / abs(d["Assets"]) * 100
    if all(k in d for k in ("Revenue", "COGS", "GrossProfit")):
        c = d["Revenue"] + d["COGS"] if d["COGS"] < 0 else d["Revenue"] - d["COGS"]
        chk["Gross=Rev-COGS"] = abs(c - d["GrossProfit"]) / abs(d["GrossProfit"]) * 100
    return chk


def ratios(d):
    def div(a, b): return a / b if (a is not None and b not in (None, 0)) else None
    r = {}
    r["margen_bruto"] = div(d.get("GrossProfit"), d.get("Revenue"))
    r["margen_neto"] = div(d.get("NetIncome"), d.get("Revenue"))
    r["roe"] = div(d.get("NetIncome"), d.get("Equity"))
    r["roa"] = div(d.get("NetIncome"), d.get("Assets"))
    r["current_ratio"] = div(d.get("AssetsCurrent"), d.get("LiabilitiesCurrent"))
    r["pasivo_equity"] = div(d.get("Liabilities"), d.get("Equity"))
    return r


if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "data/raw/cnv_ir/ALUA_2025_2026_3T.pdf"
    print(f"Parseando: {path}")
    d = parsear_pdf(path)
    print("\nLine items extraidos (ARS):")
    for k, v in d.items():
        print(f"  {k:<18} {v:>22,.0f}")
    print("\nValidacion por identidades:")
    for nombre, err in validar(d).items():
        print(f"  {nombre:<16} error {err:.2f}%  [{'OK' if err < 1 else 'REVISAR'}]")
    print("\nRatios reconstruidos:")
    for k, v in ratios(d).items():
        if v is None: continue
        es_pct = k.startswith("margen") or k in ("roe", "roa")
        print(f"  {k:<16} {(f'{v*100:.1f}%' if es_pct else f'{v:.2f}x')}")
