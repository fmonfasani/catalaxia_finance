# -*- coding: utf-8 -*-
"""
Parser de EEFF argentinos (PDF en espanol, formato CNV/FACPCE) con LIBRERIA DE
ETIQUETAS (variantes por tipo de empresa: industrial, utility, agro, banco) +
fallback a OCR para PDFs escaneados.

Auto-validacion por identidades contables: Activo = Pasivo + PN ; Gross = Rev-COGS.
Si la identidad cierra (~0%), la extraccion es correcta (checksum del estado).

Numeros argentinos: punto=miles, coma=decimal. Toma la 1ra columna (acumulado).
"""
from __future__ import annotations
import re

# ---- LIBRERIA DE ETIQUETAS: concepto -> variantes (regex, case-insensitive) ----
# Las de "gran total" usan lookahead negativo para no agarrar subtotales.
LIB = {
    "Revenue": [
        r"Ventas netas", r"Ingresos de actividades ordinarias", r"Ingresos por ventas",
        r"Ingresos por servicios", r"Ingresos operativos", r"Ventas y prestaci[oó]n de servicios",
        r"Ingresos por intereses",            # bancos
    ],
    "COGS": [r"Costo de ventas y servicios", r"Costo de ventas", r"Costo de los servicios",
             r"Costos operativos"],
    "GrossProfit": [r"Resultado bruto", r"Ganancia bruta", r"Resultado Bruto"],
    "NetIncome": [r"Resultado neto del per[ií]odo", r"Resultado del per[ií]odo(?!\s+atribuible)",
                  r"Ganancia neta del per[ií]odo", r"Ganancia\s*\(p[eé]rdida\) del per[ií]odo",
                  r"Resultado del ejercicio"],
    "ResultadoIntegral": [r"Resultado integral total del per[ií]odo", r"Resultado integral total"],
    "Assets": [r"Total del activo(?!\s*(?:no\s+)?corriente)", r"Total activo(?!\s*(?:no\s+)?corriente)",
               r"TOTAL ACTIVO(?!\s*(?:NO\s+)?CORRIENTE)"],
    "AssetsCurrent": [r"Total del activo corriente", r"Total activo corriente"],
    "Liabilities": [r"Total del pasivo(?!\s*(?:no\s+)?corriente)(?!\s+y)", r"Total pasivo(?!\s*(?:no\s+)?corriente)(?!\s+y)"],
    "LiabilitiesCurrent": [r"Total del pasivo corriente", r"Total pasivo corriente"],
    "Equity": [r"Total del patrimonio(?:\s+neto)?", r"Total patrimonio(?:\s+neto)?",
               r"Patrimonio neto total", r"Total del patrimonio"],
    "Cash": [r"Efectivo y equivalentes de efectivo", r"Efectivo y equivalentes",
             r"Caja y bancos"],
}
NUM_AR = r"\(?-?\d{1,3}(?:\.\d{3})+\)?"


def num_ar(s):
    if s is None:
        return None
    s = str(s).strip()
    neg = s.startswith("(") or s.startswith("-")
    s = re.sub(r"[^\d,]", "", s.strip("()"))
    s = s.replace(",", ".")
    if not s or s == ".":
        return None
    try:
        v = float(s)
        return -v if neg else v
    except ValueError:
        return None


def normalizar(txt):
    txt = re.sub(r"\s+", " ", txt)
    txt = re.sub(r"(?<=\d)\s+(?=[\d.])", "", txt)   # une numeros partidos por el PDF
    return txt


def parsear_texto(txt):
    """Extrae line items canonicos desde el texto del EEFF (ya normalizado)."""
    txt = normalizar(txt)
    out = {}
    for concepto, variantes in LIB.items():
        if concepto in out:
            continue
        for patron in variantes:
            m = re.search(patron + r"[^\d(]{0,40}?(" + NUM_AR + r")", txt, re.I)
            if m:
                v = num_ar(m.group(1))
                if v is not None:
                    out[concepto] = v
                    break
    # Reconciliar NetIncome con ResultadoIntegral: la linea "Resultado neto" a veces
    # se trunca por numeros concatenados en el PDF. Si difieren >5x, el Integral
    # (que suele parsear limpio) es mas confiable.
    ni, ri = out.get("NetIncome"), out.get("ResultadoIntegral")
    if ri is not None and (ni is None or (ni != 0 and abs(ri / ni) > 5)):
        out["NetIncome"] = ri
    return out


def texto_de_pdf(path, ocr_si_escaneado=True):
    """Devuelve (texto, metodo). metodo in {'texto','ocr','vacio'}."""
    import pdfplumber
    import warnings
    warnings.filterwarnings("ignore")
    with pdfplumber.open(path) as pdf:
        txt = " ".join((p.extract_text() or "") for p in pdf.pages)
    if len(txt.strip()) >= 3000:
        return txt, "texto"
    if ocr_si_escaneado:
        from ocr import ocr_pdf      # import diferido (solo si hace falta)
        t = ocr_pdf(path)
        if t and len(t.strip()) >= 1000:
            return t, "ocr"
    return txt, "vacio"


def validar(d):
    chk = {}
    if all(k in d for k in ("Assets", "Liabilities", "Equity")):
        c = d["Liabilities"] + d["Equity"]
        chk["Activo=Pas+PN"] = abs(c - d["Assets"]) / abs(d["Assets"]) * 100 if d["Assets"] else None
    if all(k in d for k in ("Revenue", "COGS", "GrossProfit")):
        c = d["Revenue"] + d["COGS"] if d["COGS"] < 0 else d["Revenue"] - d["COGS"]
        chk["Gross=Rev-COGS"] = abs(c - d["GrossProfit"]) / abs(d["GrossProfit"]) * 100 if d["GrossProfit"] else None
    return chk


def ratios(d):
    def div(a, b): return a / b if (a is not None and b not in (None, 0)) else None
    return {
        "margen_bruto": div(d.get("GrossProfit"), d.get("Revenue")),
        "margen_neto": div(d.get("NetIncome"), d.get("Revenue")),
        "roe": div(d.get("NetIncome"), d.get("Equity")),
        "roa": div(d.get("NetIncome"), d.get("Assets")),
        "current_ratio": div(d.get("AssetsCurrent"), d.get("LiabilitiesCurrent")),
        "pasivo_equity": div(d.get("Liabilities"), d.get("Equity")),
    }


def procesar_pdf(path):
    """Pipeline de un PDF: texto/ocr -> parse -> validar -> ratios."""
    txt, metodo = texto_de_pdf(path)
    if metodo == "vacio":
        return {"metodo": metodo, "datos": {}, "checks": {}, "ratios": {}, "ok": False}
    d = parsear_texto(txt)
    chk = validar(d)
    id_ok = chk.get("Activo=Pas+PN")
    ok = id_ok is not None and id_ok < 1
    return {"metodo": metodo, "datos": d, "checks": chk, "ratios": ratios(d), "ok": ok}


if __name__ == "__main__":
    import sys
    path = sys.argv[1]
    r = procesar_pdf(path)
    print(f"metodo: {r['metodo']} | items: {len(r['datos'])} | identidad OK: {r['ok']}")
    for k, v in r["datos"].items():
        print(f"  {k:<18} {v:>22,.0f}")
    for nombre, err in r["checks"].items():
        if err is not None:
            print(f"  [{nombre}] error {err:.2f}%")
    for k, v in r["ratios"].items():
        if v is not None:
            print(f"  ratio {k:<16} {v*100:.1f}%" if k.startswith('m') or k in ('roe','roa') else f"  ratio {k:<16} {v:.2f}x")
