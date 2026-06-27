# -*- coding: utf-8 -*-
"""
Procesa un EEFF desde la CNV aif2 (plantilla estandarizada). Le das el ticker y
la URL publicview de la CNV, y extrae todo (line items por codigo universal +
ratios ya calculados por la CNV + RECPAM), valida por identidad y carga a la base.

Es la via ROBUSTA (codigos universales, estructurado, accesible, sin OCR).

Como obtener la URL de la CNV:
  buscar la empresa en la consulta publica de la CNV -> abrir su presentacion de
  estados contables -> copiar la URL (https://aif2.cnv.gov.ar/presentations/publicview/<UUID>)

Uso:
  python procesar_cnv.py LEDE "https://aif2.cnv.gov.ar/presentations/publicview/<UUID>"
  python procesar_cnv.py LEDE "https://...<UUID>" --cargar
"""
from __future__ import annotations
import sys, re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from parser_cnv_aif2 import extraer, validar, RATIOS_CNV

DB = next(p for p in Path(__file__).resolve().parents if (p / 'data').is_dir()) / "data" / "screener.db"


def ratios_propios(d):
    """ratios que calculamos nosotros (para comparar con los de la CNV)."""
    def div(a, b): return a / b if (a is not None and b not in (None, 0)) else None
    return {
        "margen_bruto": div(d.get("GrossProfit"), d.get("Revenue")),
        "margen_neto": div(d.get("NetIncome"), d.get("Revenue")),
        "roe": div(d.get("NetIncome"), d.get("Equity")),
        "roa": div(d.get("NetIncome"), d.get("Assets")),
        "current_ratio": div(d.get("AssetsCurrent"), d.get("LiabilitiesCurrent")),
        "deuda_ebitda": div((d.get("DebtCurrent", 0) + d.get("DebtNonCurrent", 0)), d.get("EBITDA")),
    }


def publicar(ticker, datos, ratios_cnv, periodo=None):
    import sqlite3
    con = sqlite3.connect(DB)
    con.execute("""CREATE TABLE IF NOT EXISTS cnv_estados (
        ticker TEXT, cik TEXT, concepto TEXT, period_end TEXT, tipo TEXT,
        valor REAL, valor_comparativo REAL, fecha_reexpresion TEXT,
        form TEXT, escala INTEGER, accn TEXT, fuente TEXT DEFAULT 'cnv-6k',
        PRIMARY KEY (cik, concepto, period_end, fecha_reexpresion))""")
    cik = (con.execute("SELECT cik FROM empresas WHERE ticker_ppal=?", (ticker,)).fetchone() or [f"BYMA-{ticker}"])[0]
    n = 0
    todo = {**datos, **{f"ratio_{k}": v for k, v in ratios_cnv.items()}}   # tambien los ratios CNV
    for concepto, valor in todo.items():
        con.execute("""INSERT OR REPLACE INTO cnv_estados
            (ticker,cik,concepto,period_end,tipo,valor,valor_comparativo,fecha_reexpresion,form,escala,accn,fuente)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (ticker, str(cik), concepto, periodo, "?", valor, None, periodo, "CNV-AIF2", 1000, None, "cnv-aif2"))
        n += 1
    con.commit(); con.close()
    return n


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    cargar = "--cargar" in sys.argv
    if len(args) < 2:
        print('uso: python procesar_cnv.py TICKER "URL_CNV_publicview" [--cargar]'); return
    ticker, url = args[0].upper(), args[1]
    r = extraer(url)
    print(f"Presentacion: {r['titulo']}")
    print(f"Codigos: {r['n_codigos']} | line items: {len(r['datos'])} | ratios CNV: {len(r['ratios_cnv'])}\n")
    for k, v in r["datos"].items():
        print(f"  {k:<18} {v:>18,.2f}")
    print("\nRatios de la CNV (oficiales) vs los nuestros:")
    prop = ratios_propios(r["datos"])
    print(f"  {'ratio':<16}{'CNV':>10}{'nuestro':>12}")
    for nombre, cnv_key in [("roe", "roe"), ("roa", "roa"), ("margen_neto", "margen_neto"),
                            ("current_ratio", "liquidez")]:
        cv = r["ratios_cnv"].get(cnv_key)
        nv = prop.get(nombre)
        print(f"  {nombre:<16}{(f'{cv:.3f}' if cv is not None else '-'):>10}{(f'{nv:.3f}' if nv is not None else '-'):>12}")
    chk = validar(r["datos"])
    for nombre, err in chk.items():
        if err is not None:
            print(f"\n  [{nombre}] error {err:.3f}%  [{'OK' if err < 1 else 'REVISAR'}]")
    ok = chk.get("Activo=Pas+PN") is not None and chk["Activo=Pas+PN"] < 1
    if cargar and ok:
        n = publicar(ticker, r["datos"], r["ratios_cnv"])
        print(f"\n  CARGADO: {n} datapoints (fuente=cnv-aif2)")
    elif cargar:
        print("\n  NO cargado: identidad no cierra.")


if __name__ == "__main__":
    main()
