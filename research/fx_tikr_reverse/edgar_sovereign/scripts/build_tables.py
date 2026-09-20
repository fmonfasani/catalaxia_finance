#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Construye TABLAS 1-6 CSV desde el registro curado (TODO valor sale de un
fragmento exacto en raw/filings/*.htm + .meta.json; nada inventado).
Cada fila: capas Catalaxia §16, QC §14 (TRUE/FALSE/NO_DETERMINABLE) y
provenance §15 (source_value_1/2, fórmula, filings). Capas NO mezcladas:
identidad / valores / cálculo FX en tablas separadas.
Uso: python scripts/build_tables.py
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "engine"))
from common import assert_in_sandbox  # noqa: E402

T = ROOT / "edgar_sovereign" / "tables"
A = "https://www.sec.gov/Archives/edgar/data"
V = "build_tables@v1.0.0"

# ── TABLA 1 · INSTRUMENT MASTER (identidad canónica §7; NULL = no disponible) ──
T1_FIELDS = ["canonical_instrument_id", "instrument_name", "ticker", "species",
             "isin", "cusip", "figi", "issuer", "issuer_country", "legislation",
             "issue_date", "maturity_date", "coupon", "currency", "market",
             "settlement", "security_type", "identity_source", "filing_url"]
T1 = [
    ["AR-SOV-AL30", "Bonos de la Republica Argentina en dolares Step Up 2030",
     "AL30", "AL30", "ARARGE3209S6", None, None, "Republic of Argentina", "AR",
     "Argentine Law", None, "2030-07-09", "Step Up", "USD", "BYMA",
     "48hs (ver SOURCES.md)", "Sovereign bond",
     "GGAL 20-F exhibit4_4 (acc 0001114700-25-000049)",
     f"{A}/1114700/000111470025000049/exhibit4_4.htm"],
    ["AR-SOV-GD30", "Bonos de la Republica Argentina en dolares Step Up 2030",
     "GD30", "GD30", "US040114HS26", None, None, "Republic of Argentina", "AR",
     "New York Law", None, "2030-07-09", "Step Up", "USD", "BYMA/Exterior",
     "48hs (ver SOURCES.md)", "Sovereign bond",
     "GGAL exhibit4_4 + CEPU 6-K 2023-12-05 + Telecom 6-K 2024-11-12",
     f"{A}/1717161/000165495423015150/cepu_6k.htm"],
    ["AR-SOV-GD35", "Global Bonds 2035", "GD35", "GD35", "US040114HT09", None,
     None, "Republic of Argentina", "AR", "New York Law", None, "2035-07-09",
     None, "USD", None, None, "Sovereign bond",
     "GGAL exhibit4_4 + CEPU 6-K 2023-12-05",
     f"{A}/1717161/000165495423015150/cepu_6k.htm"],
    ["AR-SOV-GD38", "Global Bonds 2038", "GD38", "GD38", "US040114HU71", None,
     None, "Republic of Argentina", "AR", "New York Law", None, "2038-01-09",
     None, "USD", None, None, "Sovereign bond", "CEPU 6-K 2023-12-05",
     f"{A}/1717161/000165495423015150/cepu_6k.htm"],
    ["AR-SOV-GD41", "Global Bonds 2041", "GD41", "GD41", "US040114HV54", None,
     None, "Republic of Argentina", "AR", "New York Law", None, "2041-07-09",
     None, "USD", None, None, "Sovereign bond", "CEPU 6-K 2023-12-05",
     f"{A}/1717161/000165495423015150/cepu_6k.htm"],
    ["AR-SOV-BONCER", "National Treasury Bonds adjusted by CER (BONCER)",
     "BONCER", "BONCER", None, None, None, "Republic of Argentina", "AR",
     None, None, None, "CER-adjusted", "ARS", "BYMA", None, "Sovereign bond",
     "Macro 20-F 2024 (acc 0001193125-25-087225, FVTPL note)",
     f"{A}/1347426/000119312525087225/d865064d20f.htm"],
    ["AR-SOV-LECAP", "Capitalizable Bills (LECAPS)", "LECAP", "LECAP", None,
     None, None, "Republic of Argentina", "AR", None, None, None, "Zero-coupon",
     "ARS", None, None, "Treasury bill", "Macro 20-F 2024 (narrative)",
     f"{A}/1347426/000119312525087225/d865064d20f.htm"],
    ["AR-SOV-BODEN12", "Bonos del Gobierno Nacional due 2012-08-03 (BODEN)",
     "BODEN", "BODEN 2012", None, None, None, "Republic of Argentina", "AR",
     None, "2002", "2012-08-03", None, "USD", None, None, "Sovereign bond",
     "Banco Rio 6-K 2003-04-22 (acc 0000947871-03-001038, ex1.txt)",
     f"{A}/913140/000094787103001038/ex1.txt"],
    ["AR-SOV-BODEN07", "BODEN 2007", "BODEN", "BODEN 2007", None, None, None,
     "Republic of Argentina", "AR", None, "2002-02-03", "2007-02-03", "2.00%",
     "ARP", None, None, "Sovereign bond",
     "Argentina 18-K 2008-02-20 debt stock table",
     f"{A}/914021/000090342308000171/repargentina-18k_0220.htm"],
    ["AR-SOV-BODEN08", "BODEN 2008", "BODEN", "BODEN 2008", None, None, None,
     "Republic of Argentina", "AR", None, "2002-12-31", "2008-09-30", "2.00%",
     "ARP", None, None, "Sovereign bond", "Argentina 18-K 2008-02-20",
     f"{A}/914021/000090342308000171/repargentina-18k_0220.htm"],
    ["AR-SOV-BODEN11", "BODEN 2011", "BODEN", "BODEN 2011", None, None, None,
     "Republic of Argentina", "AR", None, "2003-04-30", "2011-04-30", "2.00%",
     "ARP", None, None, "Sovereign bond", "Argentina 18-K 2008-02-20",
     f"{A}/914021/000090342308000171/repargentina-18k_0220.htm"],
    ["AR-SOV-BODEN13", "Boden 2013", "BODEN", "BODEN 2013", None, None, None,
     "Republic of Argentina", "AR", None, "2003-04-01", "2013-10-01",
     "Floating", "ARP", None, None, "Sovereign bond", "Argentina 18-K 2008-02-20",
     f"{A}/914021/000090342308000171/repargentina-18k_0220.htm"],
    ["AR-SOV-PAR-PESOS", "PAR IN PESOS (2005 canje)", "PAR", "PAR pesos", None,
     None, None, "Republic of Argentina", "AR", None, "2003-12-31", "2038-12-31",
     "Step up", "ARP", None, None, "Sovereign bond", "Argentina 18-K 2008-02-20",
     f"{A}/914021/000090342308000171/repargentina-18k_0220.htm"],
    ["AR-SOV-DISC-PESOS", "DISCOUNT IN PESOS (2005 canje)", "DISCOUNT",
     "DISCOUNT pesos", None, None, None, "Republic of Argentina", "AR", None,
     "2003-12-31", "2033-12-31", "5.83%", "ARP", None, None, "Sovereign bond",
     "Argentina 18-K 2008-02-20",
     f"{A}/914021/000090342308000171/repargentina-18k_0220.htm"],
    ["AR-SOV-CUASIPAR", "CUASIPAR IN PESOS (2005 canje)", "CUASIPAR",
     "CUASIPAR pesos", None, None, None, "Republic of Argentina", "AR", None,
     "2003-12-31", "2045-12-31", "3.31%", "ARP", None, None, "Sovereign bond",
     "Argentina 18-K 2008-02-20",
     f"{A}/914021/000090342308000171/repargentina-18k_0220.htm"],
]

# ── TABLA 2 · PRICE/VALUE EVIDENCE ──
T2_FIELDS = ["obs_id", "fecha", "instrumento", "ticker", "isin", "mercado",
             "moneda", "tipo_valor", "valor", "unidades", "filer", "cik",
             "filing", "filing_date", "period_end", "filing_url",
             "source_page_or_section", "evidence_text",
             "IDENTITY_CONFIRMED", "DATE_CONFIRMED", "CURRENCY_CONFIRMED",
             "VALUE_CONFIRMED", "MARKET_CONFIRMED", "PRICE_CONFIRMED",
             "usable_fx", "caveats", "capa"]
T2 = [
    ["V01", "2023-11-30", "Global Bonds GD30", "GD30", "US040114HS26",
     "NO_DETERMINABLE (closing of operations, venue unnamed)", "ARS",
     "MARKET_PRICE", "328.50", "ARS per 1 NV (face USD 1)",
     "Central Puerto S.A.", "1717161", "6-K", "2023-12-05", "NO_DETERMINABLE",
     f"{A}/1717161/000165495423015150/cepu_6k.htm", "Dividend payment notice §3.1(c)",
     "Global Bonds GD30 valued at closing of operations on November 30, 2023 in $328.50 per 1 NV",
     "TRUE", "TRUE", "TRUE",
     "TRUE", "NO_DETERMINABLE", "TRUE", "ARS_LEG_ONLY", "Notice in pesos; bonds USD-amortizable", "NORMALIZED"],
    ["V02", "2023-11-30", "Global Bonds GD35", "GD35", "US040114HT09",
     "NO_DETERMINABLE", "ARS", "MARKET_PRICE", "295.01", "ARS per 1 NV",
     "Central Puerto S.A.", "1717161", "6-K", "2023-12-05", "NO_DETERMINABLE",
     f"{A}/1717161/000165495423015150/cepu_6k.htm", "Dividend notice §3.1(a)",
     "Global Bonds GD35 valued at closing of operations on November 30, 2023 in $295.01 per 1 NV",
     "TRUE", "TRUE", "TRUE", "TRUE", "NO_DETERMINABLE", "TRUE", "ARS_LEG_ONLY", "", "NORMALIZED"],
    ["V03", "2023-11-30", "Global Bonds GD41", "GD41", "US040114HV54",
     "NO_DETERMINABLE", "ARS", "MARKET_PRICE", "297.80", "ARS per 1 NV",
     "Central Puerto S.A.", "1717161", "6-K", "2023-12-05", "NO_DETERMINABLE",
     f"{A}/1717161/000165495423015150/cepu_6k.htm", "Dividend notice §3.1(b)",
     "Global Bonds GD41 valued at closing of operations on November 30, 2023 in $297.80 per 1 NV",
     "TRUE", "TRUE", "TRUE", "TRUE", "NO_DETERMINABLE", "TRUE", "ARS_LEG_ONLY", "", "NORMALIZED"],
    ["V04", "2023-11-30", "Global Bonds GD38", "GD38", "US040114HU71",
     "NO_DETERMINABLE", "ARS", "MARKET_PRICE", "358.99", "ARS per 1 NV",
     "Central Puerto S.A.", "1717161", "6-K", "2023-12-05", "NO_DETERMINABLE",
     f"{A}/1717161/000165495423015150/cepu_6k.htm", "Dividend notice §3.1(d)",
     "Global Bonds GD38 valued at closing of operations on November 30, 2023 in $358.99 per 1 NV",
     "TRUE", "TRUE", "TRUE", "TRUE", "NO_DETERMINABLE", "TRUE", "ARS_LEG_ONLY", "", "NORMALIZED"],
    ["V05", "2024-11-11", "Global Bonds 2030", "GD30", "US040114HS26",
     "Company portfolio (distribution in kind)", "USD+ARS", "DUAL_CURRENCY_VALUE",
     "NV US$145,602,795 | Reserve AR$115,725,101,466",
     "USD nominal vs ARS reserve (carrying)",
     "Telecom Argentina S.A.", "932470", "6-K", "2024-11-12", "NO_DETERMINABLE",
     f"{A}/932470/000110465924116432/tm2428055d1_6k.htm", "Dividend distribution letter",
     "distribution to shareholders of Global Bonds maturing 2030 (Code GD30 - ISIN US040114HS26) with nominal value US$145,602,795, partially withdrawing from the Voluntary reserve an amount of AR$115,725,101,466",
     "TRUE", "TRUE", "TRUE", "TRUE", "FALSE",
     "FALSE", "CARRYING_BASED_ONLY", "AR$ is reserve carrying amount, not market price", "NORMALIZED"],
    ["V06", "2024-12-31", "Foreign currency net position (Banco Galicia)",
     "N/A (position)", None, "Bank balance sheet", "ARS+USD",
     "DUAL_CURRENCY_VALUE", "Ps.37,157M = US$36M; on-balance Ps.-129,433M = US$-125.4M; forwards Ps.166,590M = US$161.3M",
     "millions, position-level", "Grupo Financiero Galicia S.A.", "1114700",
     "20-F", "2025-04-28", "2024-12-31",
     f"{A}/1114700/000111470025000049/ggal-20241231.htm", "Risk management / FX position",
     "As of December 31, 2024, Banco Galicia had a net assets foreign currency position of Ps.37,157 million (US$36 million) after adjusting its on-balance sheet net assets position of Ps.-129,433 million (US$-125.4 million) by net forward purchases of foreign currency without delivery of the underlying liability, for Ps.166,590 million (US$161.3 million)",
     "TRUE", "TRUE", "TRUE", "TRUE",
     "TRUE", "FALSE",
     "POSITION_BASED_ONLY", "Rounded to millions; translation, not instrument price", "NORMALIZED"],
    ["V07", "2026-03-31", "Bono Rep. Argentina USD Step Up 2030 – AL30", "AL30",
     None, "Company portfolio (Schedule A)", "ARS", "CARRYING_VALUE",
     "10,431 (03/31/2026); 13,087 (12/31/2025)", "thousands of pesos, homogeneous",
     "Grupo Supervielle S.A.", "1517399", "6-K", "2026-05-27", "2026-03-31",
     f"{A}/1517399/000151739926000025/supv-20260331x6k.htm", "SCHEDULE A – public/private securities",
     "Bono Rep. Argentina Usd Step Up 2030 – AL30 10,431 13,087 (Book value 03/31/2026, 12/31/2025; thousands of pesos)",
     "TRUE", "TRUE", "TRUE", "TRUE", "FALSE", "FALSE", "NO (single currency)",
     "", "NORMALIZED"],
    ["V08", "2024-12-31", "National Treasury Bonds CER-adjusted (BONCER)",
     "BONCER", None, "Bank portfolio", "ARS", "FAIR_VALUE",
     "FVTPL gain Ps.319,676M (+17%, mainly BONCER); no instrument price stated",
     "aggregate P&L", "Macro Bank Inc.", "1347426", "20-F", "2025-04-21",
     "2024-12-31", f"{A}/1347426/000119312525087225/d865064d20f.htm",
     "MD&A – Net gain from FVTPL",
     "Public securities with a 17% or Ps.319,676 million rise (mainly in National Treasury Bonds adjusted by CER - BONCER)",
     "TRUE", "TRUE", "TRUE", "TRUE", "FALSE", "FALSE",
     "NO (aggregate, no price)", "Aggregate P&L, no instrument price", "NORMALIZED"],
    ["V09", "2006-12-31", "BODEN/BOCON/PAR/DISCOUNT/CUASIPAR (debt stock)",
     "various", None, "Sovereign debt stock", "ARP face; USD millions outstanding",
     "NOMINAL_ONLY", "Face/outstanding table (e.g. BODEN 2011 face ARP 2,099M, outstanding USD 1,703M)",
     "millions", "Republic of Argentina", "914021", "18-K", "2008-02-20",
     "2006-12-31 (table date)",
     f"{A}/914021/000090342308000171/repargentina-18k_0220.htm",
     "Debt stock table (Interest Rate/Issue/Final Maturity/Currencies/Face/Outstanding)",
     "BODEN 2011 2.00% 04/30/03 04/30/11 ARP 2,099 1,703 (Face Value / Outstanding, Millions of dollars)",
     "TRUE", "TRUE", "TRUE", "TRUE", "FALSE", "FALSE",
     "NO (face≠price)", "Face values, not prices", "NORMALIZED"],
]

# ── TABLA 3 · FX EVIDENCE (sólo lo capaz de aportar FX) ──
T3_FIELDS = ["fx_id", "fecha", "tipo", "ars_value", "usd_value", "fx_implied",
             "fx_direction", "fx_explicito", "formula", "source_filing_1",
             "source_filing_2", "calculation", "evidence_text", "caveats",
             "FX_CALCULABLE", "PRIMARY_SOURCE", "capa"]
T3 = [
    ["FX01", "2024-12-31", "DUAL_POSITION", "37157 (Ps.M)", "36 (US$M)",
     "1032.14", "ARS per USD",
     "1032.50 (same filing, reference rate)",
     "37157/36 = 1032.14",
     f"{A}/1114700/000111470025000049/ggal-20241231.htm", "N/A (single filing)",
     "37157/36=1032.138…; on-balance 129433/125.4=1032.16; forwards 166590/161.3=1032.76",
     "net assets foreign currency position of Ps.37,157 million (US$36 million) [...] translated at the reference exchange rate (Ps. 1,032.50 [...])",
     "Position-level, rounded to millions (±~15 band); translation uses stated 1032.50, not the quotient",
     "TRUE (position-based)", "VERIFICADO POR FUENTE SEC", "FINANCIAL MODEL"],
    ["FX02", "2024-11-11", "DUAL_CARRYING", "115725101466 (AR$ reserve)",
     "145602795 (US$ nominal)", "794.79", "ARS per USD-1-nominal", "N/A",
     "115725101466/145602795 = 794.79",
     f"{A}/932470/000110465924116432/tm2428055d1_6k.htm", "N/A",
     "115725101466/145602795=794.793…",
     "nominal value US$145,602,795 [...] withdrawing from the Voluntary reserve an amount of AR$115,725,101,466",
     "AR$ is reserve carrying amount, NOT market price; ratio is ARS-per-unit-nominal, not a market FX",
     "TRUE (carrying-based)", "VERIFICADO POR FUENTE SEC", "FINANCIAL MODEL"],
    ["FX03", "2024-12-31", "IMPLICIT_METHOD", "VWAP ARS (GD30/AL30 most liquid)",
     "VWAP USD", "NO_DETERMINABLE (formula, no print)", "ARS per USD", "N/A",
     "mean5d(VWAP_ARS/VWAP_USD)", f"{A}/1114700/000111470025000049/exhibit4_4.htm",
     "N/A", "contractual definition, no numeric print in filing",
     "Implicit Exchange Rate means the average of the last five Business Days of the implied exchange rate resulting from the ratio of (a) the daily volume-weighted average of the price in ARS of the most liquid security between GD30 and AL30 over (b) the daily volume-weighted average of the price in US Dollars",
     "Methodology using both species; needs market VWAPs (secondary) to produce a print",
     "FALSE (no print)", "VERIFICADO POR FUENTE SEC", "FINANCIAL MODEL"],
    ["FX04", "2023-11-30", "ARS_LEG_ONLY", "328.50 (GD30 ARS per 1 NV)", "N/A",
     "NO_DETERMINABLE (EDGAR-only)", "ARS per USD-1-nominal", "N/A", "N/A",
     f"{A}/1717161/000165495423015150/cepu_6k.htm",
     "USD leg requires secondary GD30 USD price 2023-11-30 (NOT used here)",
     "N/A — not computed (missing component per §18)",
     "GD30 valued at closing of operations on November 30, 2023 in $328.50 per 1 NV",
     "ARS market price certain; USD leg absent in EDGAR → FX needs secondary (marked if ever used)",
     "FALSE", "VERIFICADO POR FUENTE SEC (ARS leg)", "FINANCIAL MODEL"],
    ["FX05", "2002-01/02", "HISTORICAL_EXPLICIT", "N/A", "N/A", "N/A", "ARS per USD",
     "Ps.1.40 (official, export/selected, Jan 6–Feb 11 2002); 1:1 until 2002-01-06",
     "N/A (stated, not computed)",
     f"{A}/914021/000090342308000171/repargentina-18k_0220.htm", "N/A",
     "quoted: official rate Ps.1.40 per USD; prior 1:1 convertibility",
     "From January 6, 2002, through February 11, 2002 [...] the official rate, set at Ps.1.40 per U.S. dollar",
     "Historical regime evidence, not a tradeable print", "N/A (explicit)",
     "VERIFICADO POR FUENTE SEC", "FINANCIAL MODEL"],
]

# ── TABLA 4 · CROSS-MARKET (USD↔ARS). Ningún caso hallado → fila explícita ──
T4_FIELDS = ["case_id", "fecha", "instrumento", "buy_leg", "sell_leg",
             "filer", "filing_url", "evidence_text", "veredicto", "capa"]
T4 = [["CX00", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A",
       "Búsqueda 2001–2026 en 11 documentos: ninguna operación compra-en-USD/venta-en-ARS (ni inversa) documentada a nivel instrumento",
       "NO_EVIDENCE_FOUND (cercano: GGAL-HSBC translation Ps.82,436,043 = US$81,158 — mismo activo, no cross-market)",
       "FINANCIAL MODEL"]]

# ── TABLA 5 · EXPLICIT FX ──
T5_FIELDS = ["fx_id", "fecha", "rate", "direccion", "fuente_tasa", "filer",
             "filing", "filing_date", "filing_url", "evidence_text", "capa"]
T5 = [
    ["X01", "2024-12-31", "1032.5000", "Ps. per US$1.00", "BCRA Reference Exchange Rate",
     "Grupo Financiero Galicia", "20-F", "2025-04-28",
     f"{A}/1114700/000111470025000049/ggal-20241231.htm",
     "Reference Exchange Rate published by the BCRA [...] Ps.1,032.5000, Ps.808.4833 and Ps.177.1283 per US$1.00 as of December 31, 2024, 2023 and 2022", "NORMALIZED"],
    ["X02", "2023-12-31", "808.4833", "Ps. per US$1.00", "BCRA Reference Exchange Rate",
     "Grupo Financiero Galicia", "20-F", "2025-04-28",
     f"{A}/1114700/000111470025000049/ggal-20241231.htm", "idem X01 (serie 2022–2024)", "NORMALIZED"],
    ["X03", "2022-12-31", "177.1283", "Ps. per US$1.00", "BCRA Reference Exchange Rate",
     "Grupo Financiero Galicia", "20-F", "2025-04-28",
     f"{A}/1114700/000111470025000049/ggal-20241231.htm", "idem X01 (serie 2022–2024)", "NORMALIZED"],
    ["X04", "2024-12-31", "1032.50", "Ps. per US$1.00", "BCRA reference (convenience)",
     "Macro Bank", "20-F", "2025-04-21",
     f"{A}/1347426/000119312525087225/d865064d20f.htm",
     "the reference exchange rate for U.S. dollars as of December 31, 2024, as reported by the Central Bank was Ps. 1,032.50 to U.S.$1.00", "NORMALIZED"],
    ["X05", "2025-04-11", "1078.38", "Ps. per USD", "BCRA Reference (A 3500)",
     "Macro Bank", "20-F", "2025-04-21",
     f"{A}/1347426/000119312525087225/d865064d20f.htm",
     "exchange rate standing at Ps. 1,078.38 per U.S. dollars as of April 11, 2025 (Reference Exchange Rate as reported by the Central Bank, pursuant to Communication A 3500)", "NORMALIZED"],
    ["X06", "2023-12-31", "808 (from 366)", "Ps. per USD", "Official (devaluation Dec 2023)",
     "Macro Bank", "20-F", "2025-04-21",
     f"{A}/1347426/000119312525087225/d865064d20f.htm",
     "devalued the official exchange rate from Ps. 366 to Ps. 800 per U.S. dollar [...] the exchange rate rose from Ps. 808 to Ps. 1,032 per U.S. dollar throughout 2024", "NORMALIZED"],
    ["X07", "2022-01-01", "102.75", "Ps. per USD", "BCRA Communication A 3500",
     "Macro Bank", "20-F", "2025-04-21",
     f"{A}/1347426/000119312525087225/d865064d20f.htm",
     "the exchange rate regulated by the Central Bank through Communication A 3500 was quoted at Ps. 102.75", "NORMALIZED"],
    ["X08", "2025-04-16", "1172.80", "Ps./US$", "Market (post-band regime)",
     "Grupo Financiero Galicia", "20-F", "2025-04-28",
     f"{A}/1114700/000111470025000049/ggal-20241231.htm",
     "As of April 16, 2025, the exchange rate stood at Ps.1,172.80/US$ (bands Ps./US$1,000–1,400)", "NORMALIZED"],
    ["X09", "2023-11-30", "BNA seller rate (value NOT in filing)",
     "Ps. per USD", "Banco de la Nación Argentina, seller, closing",
     "Central Puerto", "6-K", "2023-12-05",
     f"{A}/1717161/000165495423015150/cepu_6k.htm",
     "USD 0.001190 per share. Valued at the seller exchange rate of Banco de la Nación Argentina at closing on November 30, 2023",
     "NORMALIZED"],
    ["X10", "2002-01-06/02-11", "1.40", "Ps. per USD",
     "Official rate (exports/selected)", "Republic of Argentina", "18-K", "2008-02-20",
     f"{A}/914021/000090342308000171/repargentina-18k_0220.htm",
     "the official rate, set at Ps.1.40 per U.S. dollar (prior: one-to-one dollar/peso through January 6, 2002)", "NORMALIZED"],
]

# ── TABLA 6 · NO USABLE (con motivo) ──
T6_FIELDS = ["item_id", "instrumento", "motivo", "filing_o_query", "filing_url",
             "evidence_text", "capa"]
T6 = [
    ["N01", "AL30 (trust species)", "Mención sin valores (composición de fideicomiso)",
     "BBVA 6-K 2026-08-10 (acc 0001292814-26-004154)",
     f"{A}/913059/000129281426004154/ex99-1.htm",
     "the trust is composed of Treasury Bonds (Species AL30) [...] and dollars in cash",
     "NORMALIZED"],
    ["N02", "Canje 2020 (indentures)", "Sólo contexto de canje, sin precios ni ISIN en el doc",
     "Argentina 18-K/A 2020-09-14 (acc 0001193125-20-244916)",
     f"{A}/914021/000119312520244916/d84152d18ka.htm",
     "Second 2005 Supplemental Indenture [...] First 2016 Supplemental Indenture, dated September 4, 2020",
     "NORMALIZED"],
    ["N03", "BODEN 2012 (términos)", "Términos (dollar-for-dollar) sin precio",
     "Banco Rio 6-K 2003-04-22", f"{A}/913140/000094787103001038/ex1.txt",
     "exchange of the entire amount [...] for Bonos del Gobierno Nacional due August 3, 2012 (BODEN) [...] on a dollar-for-dollar basis",
     "NORMALIZED"],
    ["N04", "Agregados FVTPL / quoted-price P&L", "Agregados contables, no precio de instrumento",
     "Macro/GGAL 20-F 2024", f"{A}/1347426/000119312525087225/d865064d20f.htm",
     "Differences in quoted prices of gold and foreign currency 163,216,922 [...] (P&L line, not an instrument print)",
     "NORMALIZED"],
    ["N05", "LETES/LEBAC/LECAP/BONCER/BONTES (queries)", "Hits FTS existen pero sin documento revisado a nivel precio",
     "FTS: letes 16+82, lebac 214+121, lecap 1+33, boncer 0+57, bontes 3+12",
     "raw/fts/*.json (queries, no filings)",
     "Cobertura pendiente: revisar filings top-hit por query (ver recomendaciones)",
     "FUENTES"],
    ["N06", "GLOBAL bonds genéricos", "Query demasiado amplia (7117+8064 hits); sin muestreo vertreten",
     "FTS global_bond_arg", "raw/fts/global_bond_arg__*.json",
     "Pendiente: acotar a 424B2/F-3 del soberano (prospectos con CUSIP/ISIN/cupón)",
     "FUENTES"],
]


def write_csv(path: Path, fields: list[str], rows: list[list]) -> None:
    assert_in_sandbox(path)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(fields)
        for r in rows:
            w.writerow(["" if v is None else v for v in r])


def main() -> None:
    T.mkdir(parents=True, exist_ok=True)
    write_csv(T / "TABLA1_instrument_master.csv", T1_FIELDS, T1)
    write_csv(T / "TABLA2_price_value_evidence.csv", T2_FIELDS, T2)
    write_csv(T / "TABLA3_fx_evidence.csv", T3_FIELDS, T3)
    write_csv(T / "TABLA4_cross_market.csv", T4_FIELDS, T4)
    write_csv(T / "TABLA5_explicit_fx.csv", T5_FIELDS, T5)
    write_csv(T / "TABLA6_no_usable.csv", T6_FIELDS, T6)
    print(f"[{V}] T1={len(T1)} T2={len(T2)} T3={len(T3)} T4={len(T4)} T5={len(T5)} T6={len(T6)} -> tables/")


if __name__ == "__main__":
    main()
