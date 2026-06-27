# -*- coding: utf-8 -*-
"""
Parser de la plantilla ESTANDARIZADA de la CNV (aif2.cnv.gov.ar). Es el camino
ROBUSTO: codigos universales (iguales para TODAS las empresas), estructurado en
HTML (sin PDF/OCR), accesible (no geo-bloqueado), y trae ratios YA CALCULADOS
mas el RECPAM (resultado por inflacion) explicito.

Estructura en la pagina:  CODIGO  RUBRO  MONTO   (ej: 1999999 TOTAL DEL ACTIVO 761018910.00)

Uso:
  python parser_cnv_aif2.py https://aif2.cnv.gov.ar/presentations/publicview/<UUID>
"""
from __future__ import annotations
import re, html as ihtml, requests, warnings
warnings.filterwarnings("ignore")
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120", "Accept-Language": "es-AR"}

# codigo CNV -> concepto canonico (line items)
CODIGOS = {
    # balance - activo
    "1122500": "Cash", "1121999": "Receivables", "1120100": "Inventory",
    "1139999": "AssetsCurrent", "1110100": "PPE", "1110200": "Intangibles",
    "1119999": "AssetsNonCurrent", "1999999": "Assets",
    # patrimonio
    "2210999": "Capital", "2211999": "Reservas", "2212999": "ResultadosNoAsignados",
    "2299999": "Equity",
    # pasivo
    "2322200": "DebtCurrent", "2321999": "Payables", "2339999": "LiabilitiesCurrent",
    "2312300": "DebtNonCurrent", "2319999": "LiabilitiesNonCurrent", "2399999": "Liabilities",
    # resultados
    "3000100": "Revenue", "3000200": "COGS", "3009999": "GrossProfit",
    "3011600": "DA", "3019999": "OperatingIncome", "3021400": "IngresosFinancieros",
    "3021500": "InterestExpense", "3021800": "RECPAM", "3029999": "PretaxIncome",
    "3031100": "IncomeTax", "3049999": "NetIncome", "3099999": "ResultadoIntegral",
    "3240000": "CashFlowNeto",
    # metricas
    "8000000": "EPS_basico", "8000001": "EPS_diluido", "8000003": "EBIT",
    "8000004": "EBITDA", "8000005": "WorkingCapital",
}
# codigo CNV -> ratio ya calculado por la CNV
RATIOS_CNV = {
    "8000006": "liquidez", "8000007": "solvencia", "8000009": "roe", "8000010": "roa",
    "8000011": "endeudamiento", "8000013": "apalancamiento", "8000014": "margen_neto",
    "8000015": "deuda_fin_ebitda", "8000016": "ebitda_costos_fin", "8000027": "prueba_acida",
    "8000028": "cobertura_intereses", "8000029": "rotacion_activos",
}


def fetch(url):
    return requests.get(url, headers=H, timeout=25, verify=False).text


def parsear_html(html):
    """Extrae {codigo: monto} de la plantilla. Numeros planos (decimal con punto)."""
    txt = ihtml.unescape(re.sub("<[^>]+>", " ", html))
    txt = re.sub(r"\s+", " ", txt)
    pares = {}
    for m in re.finditer(r"([1-8]\d{6})\s+[A-ZÁÉÍÓÚÑ()/.,\s]+?\s+(-?\d+\.\d{2})", txt):
        pares.setdefault(m.group(1), float(m.group(2)))
    return pares


def extraer(url):
    """Devuelve dict con line items canonicos + ratios CNV + meta."""
    html = fetch(url)
    titulo = re.search(r"<title>([^<]+)", html)
    pares = parsear_html(html)
    datos = {c: pares[cod] for cod, c in CODIGOS.items() if cod in pares}
    ratios = {r: pares[cod] for cod, r in RATIOS_CNV.items() if cod in pares}
    return {"titulo": titulo.group(1).strip() if titulo else None,
            "datos": datos, "ratios_cnv": ratios, "n_codigos": len(pares)}


def validar(datos):
    chk = {}
    if all(k in datos for k in ("Assets", "Liabilities", "Equity")):
        c = datos["Liabilities"] + datos["Equity"]
        chk["Activo=Pas+PN"] = abs(c - datos["Assets"]) / abs(datos["Assets"]) * 100 if datos["Assets"] else None
    if all(k in datos for k in ("Revenue", "COGS", "GrossProfit")):
        c = datos["Revenue"] + datos["COGS"]
        chk["Gross=Rev+COGS"] = abs(c - datos["GrossProfit"]) / abs(datos["GrossProfit"]) * 100 if datos["GrossProfit"] else None
    return chk


if __name__ == "__main__":
    import sys
    url = sys.argv[1] if len(sys.argv) > 1 else "https://aif2.cnv.gov.ar/presentations/publicview/5ffe093a-06ec-4c63-a0fa-c1e0ee4106a1"
    r = extraer(url)
    print(f"Presentacion: {r['titulo']}")
    print(f"Codigos con valor: {r['n_codigos']} | line items mapeados: {len(r['datos'])}\n")
    for k, v in r["datos"].items():
        print(f"  {k:<18} {v:>18,.2f}")
    print("\nRatios CNV (ya calculados):")
    for k, v in r["ratios_cnv"].items():
        print(f"  {k:<20} {v:>10,.4f}")
    print()
    for nombre, err in validar(r["datos"]).items():
        if err is not None:
            print(f"  [{nombre}] error {err:.3f}%  [{'OK' if err < 1 else 'REVISAR'}]")
