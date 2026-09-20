"""Registro de emisores Golden Case (SOLO DATOS, sin logica de parsing).

Cada entrada describe UN emisor para parametrizar el pipeline SEC generico
(S01 --cik, S02 --cik/--forms, S03 --cik/--min-xbrl, e2e --cik). La logica de
fetch/parse/normalize vive en los stages; este modulo solo declara datos del
emisor. YPF permanece como Golden Case (golden=True), no como techo.
"""
from __future__ import annotations

ISSUERS = {
    "YPF": {
        "issuer_key": "YPF",
        "legal_name": "YPF SOCIEDAD ANONIMA",
        "cik": "0000904851",
        "jurisdiction": "AR/US-ADR",
        "identifiers": [
            ("TICKER", "YPF", "US"),
            ("YF_SYMBOL", "YPF", "yahoo"),
            ("TICKER", "YPFD", "BYMA"),
            ("YF_SYMBOL", "YPFD.BA", "yahoo"),
        ],
        "forms": ["20-F", "20-F/A"],
        "min_xbrl": 9,
        "golden": True,
    },
    "KO": {
        "issuer_key": "KO",
        "legal_name": "COCA COLA CO",
        "cik": "0000021344",
        "jurisdiction": "US",
        "identifiers": [
            ("TICKER", "KO", "US"),
            ("YF_SYMBOL", "KO", "yahoo"),
        ],
        "forms": ["10-K", "10-K/A"],
        "min_xbrl": 5,
        "golden": True,
    },
}


def _norm_cik(cik: str) -> str:
    return (cik or "").strip().zfill(10)


def get_by_cik(cik: str) -> dict | None:
    """Devuelve la ficha del emisor por CIK, o None si no esta registrado."""
    want = _norm_cik(cik)
    for spec in ISSUERS.values():
        if spec["cik"] == want:
            return spec
    return None


def get_by_key(key: str) -> dict | None:
    """Devuelve la ficha del emisor por issuer_key, o None."""
    return ISSUERS.get((key or "").strip().upper())
