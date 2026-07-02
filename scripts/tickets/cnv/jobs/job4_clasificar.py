# -*- coding: utf-8 -*-
"""
JOB 4 · D4 — CLASIFICAR + SEGMENTAR (offline)
=============================================
Toma guid_formtype.csv (JOB 3) y produce las WHITELISTS que consumen los jobs de
extraccion (5 y 6). Clasifica cada GUID por el NOMBRE del formulario del acordeon
(la company page muestra nombres, no IDs) usando palabras clave.

Salidas (en datos/):
    whitelist_eeff.csv   -> GUIDs de estados contables/financieros  (para JOB 5)
    whitelist_div.csv    -> GUIDs de dividendos / hechos rel. / actas (para JOB 6)
    tabla_maestra.csv    -> 1 fila por empresa: #eeff, #div, cotiza?, formularios

Uso:
    python job4_clasificar.py

0 requests. Reusable.
"""
from __future__ import annotations
import csv, re, unicodedata
from pathlib import Path
from collections import defaultdict, Counter

BASE = Path(__file__).resolve().parent.parent
DATOS = BASE / "datos"
IN = DATOS / "guid_formtype.csv"

# Clasificacion por palabras clave sobre el NOMBRE del formulario (normalizado sin acentos)
KW_EEFF = ["estados contables", "estados financieros", "balance", "eeff", "estado de situacion"]
KW_DIV = ["dividendo", "pago de dividendos", "aviso de pago"]
KW_HR = ["hecho relevante", "hechos relevantes"]
KW_ACTA = ["acta", "asamblea"]


def norm(s):
    s = unicodedata.normalize("NFKD", (s or "").lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def clasificar(formulario):
    f = norm(formulario)
    if any(k in f for k in KW_EEFF):
        return "eeff"
    if any(k in f for k in KW_DIV):
        return "dividendo"
    if any(k in f for k in KW_HR):
        return "hecho_relevante"
    if any(k in f for k in KW_ACTA):
        return "acta"
    return "otro"


def main():
    filas = list(csv.DictReader(open(IN, encoding="utf-8-sig")))
    print(f"JOB4 · D4 — Clasificar+segmentar | {len(filas)} GUIDs de guid_formtype.csv")

    eeff, div = [], []
    por_empresa = defaultdict(lambda: Counter())
    tickers = {}
    for r in filas:
        clase = clasificar(r["formulario"])
        r = {**r, "clase": clase}
        por_empresa[r["cuit"]][clase] += 1
        tickers[r["cuit"]] = r["empresa"]
        if clase == "eeff":
            eeff.append(r)
        elif clase in ("dividendo", "hecho_relevante", "acta"):
            div.append(r)

    def escribir(path, rows):
        with open(path, "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.DictWriter(fh, fieldnames=["cuit", "empresa", "guid", "formulario", "clase", "url"])
            w.writeheader(); w.writerows(rows)

    escribir(DATOS / "whitelist_eeff.csv", eeff)
    escribir(DATOS / "whitelist_div.csv", div)

    # tabla maestra
    with open(DATOS / "tabla_maestra.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["cuit", "empresa", "n_eeff", "n_dividendo", "n_hecho_rel", "n_acta", "cotiza_probable"])
        for cuit, c in sorted(por_empresa.items(), key=lambda x: -x[1]["eeff"]):
            cotiza = "si" if c["dividendo"] or c["eeff"] else "?"
            w.writerow([cuit, tickers[cuit], c["eeff"], c["dividendo"], c["hecho_relevante"], c["acta"], cotiza])

    print(f"  -> whitelist_eeff.csv: {len(eeff)} GUIDs  ({len(set(r['cuit'] for r in eeff))} empresas)")
    print(f"  -> whitelist_div.csv : {len(div)} GUIDs  ({len(set(r['cuit'] for r in div))} empresas)")
    print(f"  -> tabla_maestra.csv : {len(por_empresa)} empresas")
    globi = Counter()
    for c in por_empresa.values():
        globi.update(c)
    print(f"  Distribucion clases: {dict(globi)}")


if __name__ == "__main__":
    main()
