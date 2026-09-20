"""Integridad EDGAR soberano (VALIDACIÓN): nada inventado, todo trazable. Sin red."""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ED = ROOT / "edgar_sovereign"
RAW = ED / "raw" / "filings"
T = ED / "tables"


def _rows(name):
    with open(T / name, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _raw_texts():
    return {p.name: open(p, encoding="utf-8", errors="replace").read()
            for p in RAW.glob("*.htm")} | \
           {p.name: open(p, encoding="utf-8", errors="replace").read()
            for p in RAW.glob("*.txt")}


def test_isin_solo_si_consta_en_filing():
    texts = _raw_texts()
    blob = "\n".join(texts.values())
    for r in _rows("TABLA1_instrument_master.csv"):
        if r["isin"]:
            assert r["isin"] in blob, f"ISIN {r['isin']} sin ocurrencia en RAW"
            assert r["identity_source"] not in ("", None)


def test_urls_apuntan_a_raw_descargado():
    have = {m["filing_url"] for m in
            (json.loads(open(p, encoding="utf-8").read())
             for p in RAW.glob("*.meta.json") if "index" not in p.name)}
    for tbl in ("TABLA1_instrument_master.csv", "TABLA2_price_value_evidence.csv",
                "TABLA3_fx_evidence.csv", "TABLA5_explicit_fx.csv"):
        for r in _rows(tbl):
            for col in ("filing_url", "source_filing_1"):
                url = r.get(col, "")
                if url.startswith("http"):
                    assert url in have, f"{tbl}: URL sin RAW {url}"


def test_qc_vocabulario_cerrado():
    ok = {"TRUE", "FALSE", "NO_DETERMINABLE"}
    for r in _rows("TABLA2_price_value_evidence.csv"):
        for c in ("IDENTITY_CONFIRMED", "DATE_CONFIRMED", "CURRENCY_CONFIRMED",
                  "VALUE_CONFIRMED", "MARKET_CONFIRMED", "PRICE_CONFIRMED"):
            assert r[c] in ok, (r["obs_id"], c, r[c])


def test_fx_con_formula_y_fuentes():
    for r in _rows("TABLA3_fx_evidence.csv"):
        assert r["FX_CALCULABLE"].startswith(("TRUE", "FALSE", "N/A"))
        if r["fx_implied"].startswith("NO_DETERMINABLE") or r["fx_implied"] == "N/A":
            continue
        assert r["formula"] not in ("", "N/A"), r["fx_id"]
        assert r["ars_value"] not in ("", "N/A") and r["usd_value"] not in ("", "N/A")


def test_cross_market_explicito():
    rows = _rows("TABLA4_cross_market.csv")
    assert len(rows) >= 1 and rows[0]["veredicto"].startswith("NO_EVIDENCE_FOUND")


def test_tipos_cerrados():
    tipos = {r["tipo_valor"] for r in _rows("TABLA2_price_value_evidence.csv")}
    assert tipos <= {"MARKET_PRICE", "DUAL_CURRENCY_VALUE", "CROSS_MARKET_TRANSACTION",
                     "EXPLICIT_FX", "FAIR_VALUE", "NOMINAL_ONLY", "CARRYING_VALUE"}
