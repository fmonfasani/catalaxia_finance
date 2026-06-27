# -*- coding: utf-8 -*-
"""
INVENTARIO — antes de descargar, te dice QUE hay en cada IR: cuantos EEFF,
que años, cuantos anuales vs trimestrales, el ultimo. NO baja PDFs (solo lista
los links del sitio de IR). Sirve para saber que vas a obtener antes de tirar
el pipeline.

Uso:
  python inventario.py                 # todas las del catalogo
  python inventario.py --sector gas    # un sector
  python inventario.py ALUA BOLT CTIO  # papeles puntuales
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from catalogo_ir import CATALOGO, SECTORES, por_sector
from discovery import descubrir_eeff
from paso1_descarga import clasificar_eeff


def inventariar(tickers):
    print(f"{'Ticker':<7}{'Sector':<13}{'EEFF':>5}{'Años':>14}{'Anual':>7}{'Trim':>6}  ultimo")
    print("-" * 78)
    total_eeff = 0
    con_eeff = 0
    resumen = []
    for tk in tickers:
        info = CATALOGO.get(tk)
        if not info:
            continue
        nombre, sector, cierre, urls = info
        if not urls:
            print(f"{tk:<7}{sector:<13}{'-':>5}{'(sin URL en catalogo)':>14}")
            resumen.append((tk, 0, "sin_url"))
            continue
        pdfs = descubrir_eeff(tk, CATALOGO)
        if not pdfs:
            print(f"{tk:<7}{sector:<13}{'0':>5}{'(IR no responde)':>14}")
            resumen.append((tk, 0, "no_responde"))
            continue
        clas = [clasificar_eeff(u.rsplit('/', 1)[-1], cierre) for u in pdfs]
        años = sorted({a for a, _, _ in clas if a})
        nA = sum(1 for _, _, t in clas if t == "anual")
        nQ = sum(1 for _, _, t in clas if t == "trimestral")
        rango = f"{años[0]}-{años[-1]}" if años else "?"
        ult = pdfs[0].rsplit('/', 1)[-1][:30]
        print(f"{tk:<7}{sector:<13}{len(pdfs):>5}{rango:>14}{nA:>7}{nQ:>6}  {ult}")
        total_eeff += len(pdfs); con_eeff += 1
        resumen.append((tk, len(pdfs), "ok"))
    print("-" * 78)
    print(f"Empresas con EEFF accesible: {con_eeff}/{len(tickers)} | total EEFF listados: {total_eeff}")
    sinurl = sum(1 for _, _, e in resumen if e == "sin_url")
    nores = sum(1 for _, _, e in resumen if e == "no_responde")
    if sinurl or nores:
        print(f"(sin URL en catalogo: {sinurl} | IR no respondio: {nores} -> desde Argentina deberian responder)")
    return resumen


def main():
    args = sys.argv[1:]
    if "--sector" in args:
        i = args.index("--sector")
        sec = args[i + 1] if i + 1 < len(args) else ""
        tickers = por_sector(sec.lower())
        if not tickers:
            print(f"Sector '{sec}' invalido. Opciones: {', '.join(SECTORES)}"); return
    elif args and not args[0].startswith("--"):
        tickers = [a.upper() for a in args]
    else:
        tickers = list(CATALOGO)
    inventariar(tickers)


if __name__ == "__main__":
    main()
