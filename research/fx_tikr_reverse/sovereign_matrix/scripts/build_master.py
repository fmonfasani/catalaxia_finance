#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Master soberano: identidad extendida + matriz §2 + FX observations + provenance.

Reutiliza edgar_sovereign/tables (NO duplica: lee y extiende). Nuevas filas
sólo con fragmento exacto en RAW fase-2. Equivalencias §5 como CANDIDATE salvo
evidencia (AL30↔GD30: EQUIVALENT_ECONOMIC por Implicit Exchange Rate, §4 GGAL).
CAMBIO DE ALCANCE registrados: BOPREAL BPOC7/BPOD7, TV24 (fuera del universo §1).
Uso: python sovereign_matrix/scripts/build_master.py
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "engine"))
from common import assert_in_sandbox  # noqa: E402

SM = ROOT / "sovereign_matrix"
EDT = ROOT / "edgar_sovereign" / "tables"
A = "https://www.sec.gov/Archives/edgar/data"
V = "build_master@v1.0.0"

MASTER_FIELDS = ["INSTRUMENTO", "FECHA", "SERIE", "ISIN", "CUSIP", "FIGI",
                 "TICKER", "TIPO", "JURISDICCION", "LEY", "MONEDA",
                 "VALOR_NOMINAL", "PRECIO_ARS", "PRECIO_USD", "MERCADO_ARS",
                 "MERCADO_USD", "TIPO_DE_PRECIO", "UNIDAD_DEL_PRECIO",
                 "FX_EXPLICITO", "FUENTE_FX", "FX_IMPLICITO", "FORMULA_FX",
                 "OPERACION", "COMPRADOR", "VENDEDOR", "FECHA_OPERACION",
                 "ACCESSION", "DOCUMENTO", "URL", "FRAGMENTO", "PROVENANCE",
                 "STATUS", "CONFIDENCE", "NOTES"]


def read_tbl(name):
    with open(EDT / name, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def wcsv(path, fields, rows):
    assert_in_sandbox(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    return len(rows)


# ── 02_IDENTITY: master extendido (T1 + fase-2; CUSIP/FIGI NULL salvo evidencia)
ID_FIELDS = ["canonical_instrument_id", "instrument_name", "ticker", "species",
             "isin", "cusip", "figi", "issuer", "issuer_country", "legislation",
             "issue_date", "maturity_date", "coupon", "currency", "market",
             "settlement", "security_type", "identity_source", "filing_url",
             "scope"]
NEW_IDENTITY = [
    ["AR-SOV-BPOC7", "Bopreal Series 1 – C", "BPOC7", "BPOC7", "AR0763285209",
     None, None, "BCRA/Republic of Argentina", "AR", "Argentine Law", None,
     "2027-10-31", None, "USD", "BYMA", None, "Bopreal (CAMBIO DE ALCANCE)",
     "CEPU 6-K 2024-11-07 (acc 0001292814-24-004083)",
     f"{A}/1717161/000129281424004083/cepu20241107_6k.htm", "CANDIDATE_SCOPE"],
    ["AR-SOV-BPOD7", "Bopreal Series 1 – D", "BPOD7", "BPOD7", "AR0314171247",
     None, None, "BCRA/Republic of Argentina", "AR", "Argentine Law", None,
     "2027-10-31", None, "USD", "BYMA", None, "Bopreal (CAMBIO DE ALCANCE)",
     "CEPU 6-K 2024-11-07",
     f"{A}/1717161/000129281424004083/cepu20241107_6k.htm", "CANDIDATE_SCOPE"],
    ["AR-SOV-TV24", "U.S. dollar-linked National Treasury bond TV24", "TV24",
     "TV24", "ARARGE320C18", None, None, "Republic of Argentina", "AR",
     "Argentine Law", None, "2024-04-30", "Zero (dollar-linked)", "USD-linked",
     "BYMA", None, "Treasury bond (CAMBIO DE ALCANCE)",
     "CEPU 6-K 2023-11-03 (acc 0001654954-23-013780)",
     f"{A}/1717161/000165495423013780/cepu_6k.htm", "CANDIDATE_SCOPE"],
    ["AR-SOV-NEW30", "New USD 2030 Bonds (2020 canje)", None, "New USD 2030",
     None, None, None, "Republic of Argentina", "AR", "New York Law", "2020-09-04",
     "2030-07", "Step-Up", "USD", None, None, "Sovereign bond",
     "Argentina 424B5 2020-08-17 (acc 0001193125-20-221606, amort. from Jul-2024)",
     f"{A}/914021/000119312520221606/d68512d424b5.htm", "IN_SCOPE"],
    ["AR-SOV-NEW35", "New USD 2035 Bonds (2020 canje)", "GD35?", "New USD 2035",
     None, None, None, "Republic of Argentina", "AR", "New York Law", "2020-09-04",
     "2035-07", "Step-Up", "USD", None, None, "Sovereign bond",
     "Argentina 424B5 2020-08-17 (ticker unconfirmed → GD35 CANDIDATE link)",
     f"{A}/914021/000119312520221606/d68512d424b5.htm", "IN_SCOPE"],
    ["AR-SOV-NEW38", "New USD 2038 Bonds (2020 canje)", None, "New USD 2038",
     None, None, None, "Republic of Argentina", "AR", "New York Law", "2020-09-04",
     "2038-01", "Step-Up", "USD", None, None, "Sovereign bond",
     "Argentina 424B5 2020-08-17 (amort. from Jul-2027)",
     f"{A}/914021/000119312520221606/d68512d424b5.htm", "IN_SCOPE"],
    ["AR-SOV-NEW41", "New USD 2041 Bonds (2020 canje)", "GD41?", "New USD 2041",
     None, None, None, "Republic of Argentina", "AR", "New York Law", "2020-09-04",
     "2041-07", "Step-Up", "USD", None, None, "Sovereign bond",
     "Argentina 424B5 2020-08-17 (consideration tables; ticker link CANDIDATE)",
     f"{A}/914021/000119312520221606/d68512d424b5.htm", "IN_SCOPE"],
    ["AR-SOV-NEW46", "New USD 2046 Bonds (2020 canje)", "GD46?", "New USD 2046",
     None, None, None, "Republic of Argentina", "AR", "New York Law", "2020-09-04",
     "2046-07", "Step-Up", "USD", None, None, "Sovereign bond",
     "Argentina 424B5 2020-08-17 (consideration U.S.$135.99769–163.13709)",
     f"{A}/914021/000119312520221606/d68512d424b5.htm", "IN_SCOPE"],
    ["AR-SOV-USD21", "USD 2021 Bonds 6.875% (2016 indenture)", None, "USD 2021",
     "US040114GW47", None, None, "Republic of Argentina", "AR", "New York Law",
     None, "2021", "6.875%", "USD", None, None, "Sovereign bond",
     "Argentina 424B5 2020-08-17 ANNEX B (eligible bonds table)",
     f"{A}/914021/000119312520221606/d68512d424b5.htm", "IN_SCOPE"],
    ["AR-SOV-USD22", "USD 2022 Bonds 5.625%", None, "USD 2022", "US040114HK99",
     None, None, "Republic of Argentina", "AR", "New York Law", None, "2022",
     "5.625%", "USD", None, None, "Sovereign bond", "idem ANNEX B",
     f"{A}/914021/000119312520221606/d68512d424b5.htm", "IN_SCOPE"],
    ["AR-SOV-DISC33", "USD 2033 Discount Bonds I", None, "USD 2033 Discount",
     "US040114GL81", None, None, "Republic of Argentina", "AR", "New York Law",
     "2005", "2033", "Discount", "USD", None, None, "Sovereign bond",
     "Argentina 424B5 2020-08-17 ANNEX A",
     f"{A}/914021/000119312520221606/d68512d424b5.htm", "IN_SCOPE"],
]

EQUIV = [  # §5: equivalencias con evidencia exigida
    ["AL30", "GD30", "EQUIVALENT_ECONOMIC (same bond, different law/species)",
     "GGAL Implicit Exchange Rate usa indistintamente el más líquido GD30/AL30; "
     "misma maturity 2030-07-09 y Step-Up; ISIN distintos (ARARGE3209S6 vs US040114HS26)"],
    ["AL35", "GD35", "CANDIDATE (sin evidencia directa)"],
    ["AL38", "GD38", "CANDIDATE (sin evidencia directa)"],
    ["AL41", "GD41", "CANDIDATE (sin evidencia directa)"],
    ["New USD 2035", "GD35", "CANDIDATE (ticker link no confirmado en prospecto)"],
    ["New USD 2041", "GD41", "CANDIDATE (idem)"],
    ["New USD 2046", "GD46", "CANDIDATE (GD46 sin hits EDGAR 2016+; FTS-gap pre-2016)"],
]


def main():
    # 02_IDENTITY merged
    with open(EDT / "TABLA1_instrument_master.csv", encoding="utf-8") as f:
        r = csv.DictReader(f)
        old_fields, old_rows = r.fieldnames, list(r)
    id_fields = old_fields + ["scope"]
    merged = [{**row, "scope": "IN_SCOPE"} for row in old_rows]
    merged += [dict(zip(id_fields, row)) for row in NEW_IDENTITY]
    n_id = wcsv(SM / "02_IDENTITY" / "instrument_master.csv", id_fields, merged)
    wcsv(SM / "02_IDENTITY" / "equivalences.csv",
         ["local", "international", "veredicto", "evidencia"], [dict(zip(
             ["local", "international", "veredicto", "evidencia"], e)) for e in EQUIV])

    # Matriz §2 desde TABLA2 + filas fase-2 (identidad/face nuevas → STATUS PARTIAL)
    t2 = read_tbl("TABLA2_price_value_evidence.csv")
    M = []
    for r in t2:
        status = ("SUPPORTED" if r["tipo_valor"] in ("MARKET_PRICE", "DUAL_CURRENCY_VALUE")
                  else "PARTIAL")
        M.append({"INSTRUMENTO": r["instrumento"], "FECHA": r["fecha"], "SERIE": r["ticker"],
                  "ISIN": r["isin"], "CUSIP": "", "FIGI": "", "TICKER": r["ticker"],
                  "TIPO": r["tipo_valor"], "JURISDICCION": "AR",
                  "LEY": "", "MONEDA": r["moneda"], "VALOR_NOMINAL": "",
                  "PRECIO_ARS": r["valor"] if "ARS" in r["moneda"] else "",
                  "PRECIO_USD": "", "MERCADO_ARS": r["mercado"], "MERCADO_USD": "",
                  "TIPO_DE_PRECIO": r["tipo_valor"], "UNIDAD_DEL_PRECIO": r["unidades"],
                  "FX_EXPLICITO": "", "FUENTE_FX": "", "FX_IMPLICITO": "",
                  "FORMULA_FX": "", "OPERACION": "", "COMPRADOR": "", "VENDEDOR": "",
                  "FECHA_OPERACION": "", "ACCESSION": "", "DOCUMENTO": r["filing"],
                  "URL": r["filing_url"], "FRAGMENTO": r["evidence_text"],
                  "PROVENANCE": "A", "STATUS": status,
                  "CONFIDENCE": "", "NOTES": r["caveats"]})
    # V05 dual completa USD+nominal
    for m in M:
        if m["FRAGMENTO"].startswith("distribution to shareholders of Global Bonds maturing 2030"):
            m["VALOR_NOMINAL"] = "US$145,602,795"
            m["PRECIO_ARS"] = "AR$115,725,101,466 (reserva carrying)"
    # V06 dual posición
    for m in M:
        if m["FRAGMENTO"].startswith("As of December 31, 2024, Banco Galicia had a net"):
            m["PRECIO_USD"] = "US$36M (netos; componentes -125.4/+161.3)"
    n_m = wcsv(SM / "sovereign_debt_master.csv", MASTER_FIELDS, M)

    # FX observations (AGENTE 06 checklist por cálculo)
    t3 = read_tbl("TABLA3_fx_evidence.csv")
    FXF = ["fx_id", "fecha", "mismo_instrumento", "fecha_alineada",
           "mismo_concepto", "misma_unidad", "mismo_nominal", "mismo_mercado",
           "mismo_tipo_precio", "veredicto_comparabilidad", "fx_implicito",
           "formula", "fuente_1", "fuente_2"]
    FXR = [
        {"fx_id": "FX01", "fecha": "2024-12-31", "mismo_instrumento": "N/A (posición)",
         "fecha_alineada": "TRUE", "mismo_concepto": "TRUE (posición neta)",
         "misma_unidad": "TRUE (millones)", "mismo_nominal": "N/A",
         "mismo_mercado": "TRUE (balance)", "mismo_tipo_precio": "TRUE (traslación)",
         "veredicto_comparabilidad": "COMPARABLE (posición, banda ±~15)",
         "fx_implicito": "1032.14", "formula": "37157/36",
         "fuente_1": "GGAL 20-F", "fuente_2": "N/A"},
        {"fx_id": "FX02", "fecha": "2024-11-11", "mismo_instrumento": "TRUE (GD30)",
         "fecha_alineada": "PARTIAL (carta 11-11; reserva sin fecha propia)",
         "mismo_concepto": "FALSE (nominal vs carrying)",
         "misma_unidad": "TRUE", "mismo_nominal": "TRUE",
         "mismo_mercado": "FALSE (cartera vs reserva)",
         "mismo_tipo_precio": "FALSE (nominal vs carrying)",
         "veredicto_comparabilidad": "NO_COMPARABLE_COMO_FX (sólo ratio carrying)",
         "fx_implicito": "794.79 (carrying)", "formula": "115725101466/145602795",
         "fuente_1": "Telecom 6-K", "fuente_2": "N/A"},
        {"fx_id": "FX04", "fecha": "2023-11-30", "mismo_instrumento": "TRUE (GD30)",
         "fecha_alineada": "TRUE", "mismo_concepto": "NO_DETERMINABLE (falta pata USD)",
         "misma_unidad": "NO_DETERMINABLE", "mismo_nominal": "NO_DETERMINABLE",
         "mismo_mercado": "NO_DETERMINABLE", "mismo_tipo_precio": "NO_DETERMINABLE",
         "veredicto_comparabilidad": "NO_DETERMINABLE (falta componente §18)",
         "fx_implicito": "NO_DETERMINABLE", "formula": "ARS/ USD? (pata USD ausente)",
         "fuente_1": "CEPU 6-K (ARS 328.50)", "fuente_2": "NO_EVIDENCE_FOUND"},
    ]
    n_fx = wcsv(SM / "fx_observations.csv", FXF, FXR)

    # Cross-market forensics (AGENTE 07): Ternium negativo + estado
    n_cx = wcsv(SM / "cross_market_cases.csv",
                ["case_id", "fecha", "instrumento", "buy_leg", "sell_leg",
                 "evidencia", "clasificacion", "capa"],
                [{"case_id": "CX00", "fecha": "N/A", "instrumento": "N/A",
                  "buy_leg": "N/A", "sell_leg": "N/A",
                  "evidencia": "Revisión 2001–2026 (15 docs + frases xmarket_*): 0 operaciones instrumento-USD↔ARS",
                  "clasificacion": "NO_EVIDENCE_FOUND", "capa": "FINANCIAL MODEL"},
                 {"case_id": "CX01-neg", "fecha": "2021-03-31",
                  "instrumento": "N/A (acero/chatarra)", "buy_leg": "chatarra EEUU (39%)",
                  "sell_leg": "N/A",
                  "evidencia": "Ternium 20-F 2020: '39% was purchased in the United States. Scrap is purchased at market prices' — commodity, no bono",
                  "clasificacion": "FALSE_POSITIVE_REMOVED", "capa": "FINANCIAL MODEL"},
                 {"case_id": "CX02-near", "fecha": "2024-12-06",
                  "instrumento": "N/A (adquisición HSBC)",
                  "buy_leg": "Ps.82,436,043", "sell_leg": "US$81,158 (mismo activo)",
                  "evidencia": "GGAL exhibit4_4: ON Ps.82,436,043 (US$81,158 at exchange rate in effect) — traslación mismo activo",
                  "clasificacion": "ACCOUNTING_TRANSLATION (no cross-market)", "capa": "FINANCIAL MODEL"}])
    print(f"[{V}] identity={n_id} master={n_m} fxobs={n_fx} xmarket={n_cx}")


if __name__ == "__main__":
    main()
