# -*- coding: utf-8 -*-
"""
JOB 1 · D1 — UNIVERSO
=====================
Baja TODAS las empresas registradas en la CNV (endpoint AutoComplete) y las deja
en datos/empresas_556.csv. Es un discovery barato: 1 request.

Salida: datos/empresas_556.csv  (ticker, empresa, cuit, id, url_empresa)

Uso:
    python job1_universo.py

Fuente: https://www.cnv.gov.ar/SitioWeb/Empresas/AutoComplete  (devuelve JSON)
Rate limit: 1 sola request. Sin problema.
"""
from __future__ import annotations
import csv, json
from pathlib import Path
import requests

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "data").is_dir())
DATOS = Path(__file__).resolve().parent.parent / "datos"
DEBUG = Path(__file__).resolve().parent.parent / "debug"
URL = "https://www.cnv.gov.ar/SitioWeb/Empresas/AutoComplete"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120"}


def campo(reg, *nombres):
    """Devuelve el primer campo presente (los nombres del JSON pueden variar)."""
    for n in nombres:
        for k in reg:
            if k.lower() == n.lower() and str(reg[k]).strip():
                return str(reg[k]).strip()
    return ""


def main():
    DATOS.mkdir(parents=True, exist_ok=True); DEBUG.mkdir(parents=True, exist_ok=True)
    print("JOB1 · D1 — Universo CNV (AutoComplete)")
    r = requests.get(URL, headers=HEADERS, timeout=30)
    r.raise_for_status()
    data = r.json()
    (DEBUG / "autocomplete.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  registros: {len(data)}  (raw -> debug/autocomplete.json)")

    filas = []
    for reg in data:
        cuit = campo(reg, "cuit", "CUIT")
        if not cuit:
            continue
        filas.append({
            "ticker": campo(reg, "ticker", "simbolo", "abreviatura"),
            "empresa": campo(reg, "denominacion", "nombre", "razonSocial", "descripcion", "label"),
            "id": campo(reg, "id", "entidadId", "idEntidad"),
            "cuit": cuit,
            "url_empresa": f"https://www.cnv.gov.ar/SitioWeb/Empresas/Empresa/{cuit}",
        })
    # dedup por cuit
    vistos, unicas = set(), []
    for f in filas:
        if f["cuit"] not in vistos:
            vistos.add(f["cuit"]); unicas.append(f)

    out = DATOS / "empresas_556.csv"
    with open(out, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=["ticker", "empresa", "id", "cuit", "url_empresa"])
        w.writeheader(); w.writerows(unicas)
    print(f"  -> {out.name}: {len(unicas)} empresas (dedup por cuit)")
    con_ticker = sum(1 for f in unicas if f["ticker"])
    print(f"     con ticker (cotizan?): {con_ticker} | sin ticker (solo ON?): {len(unicas)-con_ticker}")


if __name__ == "__main__":
    main()
