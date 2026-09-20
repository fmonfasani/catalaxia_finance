"""Ejes 5-7: settlement + currency + división por cero. Puro."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine"))
from reconstruct import reconstruct_day  # noqa: E402

BASE_ARS = {"instrument": "BONAR 2030", "ticker": "AL30", "isin": None,
            "date": "2024-12-30", "market": "BYMA", "settlement": "48hs",
            "currency": "ARS", "price": 65000.0, "volume": 1000.0,
            "source": "TEST", "source_url": "test://al30",
            "retrieved_at": "2024-12-30T20:00:00+00:00", "sha256": "abc"}
BASE_USD = dict(BASE_ARS, ticker="AL30D", currency="USD", price=62.0,
                source_url="test://al30d")


def test_mep_ok_mismo_settlement():
    out = reconstruct_day("2024-12-30", [{"ars": BASE_ARS, "usd": BASE_USD,
                                          "ratio": 1.0, "instrument": "AL30"}], "MEP")
    assert out["fx_value"] == 65000.0 / 62.0 and out["n"] == 1
    assert out["null_reason"] is None


def test_settlement_mismatch_no_imputa():
    usd = dict(BASE_USD, settlement="CI")
    out = reconstruct_day("2024-12-30", [{"ars": BASE_ARS, "usd": usd,
                                          "ratio": 1.0, "instrument": "AL30"}], "MEP")
    assert out["fx_value"] is None and out["null_reason"] == "SETTLEMENT_MISMATCH"


def test_settlement_undeclared_flag_no_decide():
    ars = dict(BASE_ARS, settlement="UNDECLARED")
    usd = dict(BASE_USD, settlement="UNDECLARED")
    out = reconstruct_day("2024-12-30", [{"ars": ars, "usd": usd,
                                          "ratio": 1.0, "instrument": "AL30"}], "MEP")
    assert out["fx_value"] is not None  # se reporta…
    assert "UNDECLARED_SETTLEMENT" in out["flags"]  # …pero flaggeada NO_DECIDE


def test_currency_mismatch():
    usd = dict(BASE_USD, currency="ARS")
    out = reconstruct_day("2024-12-30", [{"ars": BASE_ARS, "usd": usd,
                                          "ratio": 1.0, "instrument": "AL30"}], "MEP")
    assert out["fx_value"] is None and "CURRENCY_MISMATCH" in out["null_reason"]


def test_division_por_cero_y_precio_faltante():
    usd0 = dict(BASE_USD, price=0.0)
    # price=0 invalida el quote -> ZERO_OR_NEGATIVE_PRICE (capa quote, antes de dividir)
    out = reconstruct_day("2024-12-30", [{"ars": BASE_ARS, "usd": usd0,
                                          "ratio": 1.0, "instrument": "AL30"}], "MEP")
    assert out["fx_value"] is None
    assert out["null_reason"] in ("ZERO_OR_NEGATIVE_PRICE", "DIVISION_BY_ZERO")
    out2 = reconstruct_day("2024-12-30", [{"ars": None, "usd": BASE_USD,
                                           "ratio": 1.0, "instrument": "AL30"}], "MEP")
    assert out2["fx_value"] is None and out2["null_reason"] == "MISSING_LEG"


def test_ccl_adr_ratio():
    ars = dict(BASE_ARS, instrument="GGAL ADR", ticker="GGAL.BA", price=1000.0)
    usd = dict(BASE_USD, instrument="GGAL ADR", ticker="GGAL", market="NASDAQ",
               currency="USD", price=50.0)
    out = reconstruct_day("2024-12-30", [{"ars": ars, "usd": usd, "ratio": 10,
                                          "instrument": "GGAL ADR"}], "CCL")
    assert out["fx_value"] == 1000.0 * 10 / 50.0
