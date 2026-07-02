# -*- coding: utf-8 -*-
"""
build_subset.py — Arma el SUBSET PRIORITARIO (offline, 0 requests)
==================================================================
Genera datos/empresas_subset.csv = (56 BYMA-only) + (ADR argentinos), cruzando
por CUIT y por nombre contra datos/empresas_556.csv (salida del JOB 1).

Ese CSV se usa como palanca de scope:
    job2_download.py --empresas empresas_subset.csv    (baja solo el subset)
    job5_extract_eeff.py --cuits empresas_subset.csv   (extrae solo el subset)
    job6_extract_div.py  --cuits empresas_subset.csv

Uso:
    python build_subset.py

IMPORTANTE: el match de ADR es por palabra clave sobre el nombre -> REVISÁ el
reporte que imprime. Ajustá ADR_PATRONES si algún ADR no matcheó o entró de más.
"""
from __future__ import annotations
import csv, unicodedata
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DATOS = BASE / "datos"
UNIVERSO = DATOS / "empresas_556.csv"     # JOB 1
BYMA56 = DATOS / "empresas.csv"           # las 56 BYMA-only (ticker,empresa,id,cuit,url_empresa)
OUT = DATOS / "empresas_subset.csv"

# ADR argentinos que presentan en CNV. Un row matchea si TODOS los tokens estan en
# el nombre normalizado. Revisar el reporte: algunos tokens pueden traer al grupo
# entero (ej. "galicia" -> holding + banco), lo cual es aceptable.
ADR_PATRONES = [
    ("YPF", ["ypf"]),
    ("Grupo Financiero Galicia", ["galicia"]),
    ("Banco Macro", ["macro"]),
    ("BBVA Argentina", ["bbva"]),
    ("Grupo Supervielle", ["supervielle"]),
    ("Pampa Energia", ["pampa", "energia"]),               # ["pampa"] solo traia bancos (ruido)
    ("Transportadora Gas del Sur (TGS)", ["transportadora", "gas", "sur"]),
    ("Central Puerto", ["central", "puerto"]),
    ("Cresud", ["cresud"]),
    ("IRSA", ["irsa"]),
    ("Loma Negra", ["loma", "negra"]),
    ("Telecom Argentina", ["telecom"]),
    ("Ternium Argentina (ex-Siderar)", ["ternium"]),       # CNV: "TERNIUM ARGENTINA S.A."
    ("Vista Energy", ["vista"]),                           # revisar candidatos en el reporte
    ("Corp. America (Aeropuertos Arg 2000)", ["aeropuertos", "2000"]),  # CNV: "Aeropuertos Argentina 2000 S.A."
    # EDN (Edenor) y TRAN (Transener): ya entran por BYMA-only via CUIT -> no se listan aca
    #   Edenor  -> CNV: "Empresa Distribuidora y Comercializadora Norte SA"
    #   Transener -> CNV: "Cia. de Transporte de Energia Electrica"
    # Bioceres: NO existe en el registro CNV -> se omite
]


def norm(s):
    s = unicodedata.normalize("NFKD", (s or "").lower())
    return " ".join("".join(c for c in s if not unicodedata.combining(c)).replace(".", " ").split())


def main():
    universo = list(csv.DictReader(open(UNIVERSO, encoding="utf-8-sig")))
    by_cuit = {r["cuit"].strip(): r for r in universo if r.get("cuit")}
    print(f"build_subset — universo (JOB1): {len(universo)} empresas")

    subset = {}   # cuit -> row(+grupo)

    # --- 1) 56 BYMA-only por CUIT ---
    byma_ok = byma_miss = 0
    if BYMA56.exists():
        for r in csv.DictReader(open(BYMA56, encoding="utf-8-sig")):
            cuit = (r.get("cuit") or "").strip()
            if cuit in by_cuit:
                row = dict(by_cuit[cuit]); row["grupo"] = "byma_only"; row["ticker"] = r.get("ticker", "")
                subset[cuit] = row; byma_ok += 1
            else:
                print(f"  [BYMA sin match por CUIT] {r.get('ticker'):<6} {r.get('empresa','')[:40]} cuit={cuit}")
                byma_miss += 1
        print(f"  BYMA-only: {byma_ok} matcheadas, {byma_miss} sin match (revisar CUIT en empresas.csv)")
    else:
        print(f"  ! No existe {BYMA56.name}: se omite el grupo BYMA-only")

    # --- 2) ADR por nombre ---
    print("\n  ADR (match por nombre — REVISAR):")
    for label, tokens in ADR_PATRONES:
        hits = [r for r in universo if all(t in norm(r.get("empresa")) for t in tokens)]
        if not hits:
            print(f"    [SIN MATCH] {label}  (tokens={tokens})")
            continue
        for r in hits:
            cuit = r["cuit"].strip()
            if cuit in subset:
                continue  # ya estaba (BYMA o ADR previo)
            row = dict(r); row["grupo"] = "adr"; subset[cuit] = row
            print(f"    + {label:<32} -> {r.get('empresa','')[:45]} (cuit {cuit})")

    # --- salida ---
    campos = ["ticker", "empresa", "id", "cuit", "url_empresa", "grupo"]
    with open(OUT, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=campos, extrasaction="ignore")
        w.writeheader()
        for r in subset.values():
            w.writerow({k: r.get(k, "") for k in campos})
    n_byma = sum(1 for r in subset.values() if r["grupo"] == "byma_only")
    n_adr = sum(1 for r in subset.values() if r["grupo"] == "adr")
    print(f"\n  -> {OUT.name}: {len(subset)} empresas ({n_byma} byma_only + {n_adr} adr)")
    print("     Revisá el reporte de arriba antes de usarlo como scope.")


if __name__ == "__main__":
    main()
