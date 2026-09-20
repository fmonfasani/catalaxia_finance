#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Discovery fase-2: universo congelado faltante + prospectos + frases cross-market.

Reutiliza el store RAW edgar_sovereign/raw/fts (no duplica) y el protocolo
fts_sweep (User-Agent, <=10 req/s, envelope con sha256). Cubre §1: AL29/GD29,
AL35/GD35, AL38/AE38/GD38, AL41/GD41, GD46, AL25/GD25, PAR/DISCOUNT/CUASIPAR/
BOCON/LEFIS, CUSIP/ISIN, frases cross-market §4/§10 y formas de prospecto
(424B2/424B5/F-3/S-B) del soberano. Ventanas 2001-2015 / 2016-2026.
Uso: python sovereign_matrix/scripts/discovery_p2.py [solo_nombres...]
"""
from __future__ import annotations

import json
import sys
import time
import urllib.parse
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "engine"))
from common import git_commit, utcnow_iso, write_raw_noreplace  # noqa: E402

RAW_FTS = ROOT / "edgar_sovereign" / "raw" / "fts"
COLLECTOR = "edgar_fts_p2@v1.0.0"
UA = "Catalaxia research contact@catalaxia.example"
BASE = "https://efts.sec.gov/LATEST/search-index"
WINDOWS = [("2001-01-01", "2015-12-31"), ("2016-01-01", "2026-09-15")]
FORMS_EQ = "20-F,6-K,18-K"
FORMS_PROSP = "424B2,424B5,F-3,F-3/A,S-B"

QUERIES: list[tuple[str, str, str]] = [
    ("al29_gd29", "AL29 OR GD29", FORMS_EQ),
    ("al35_gd35", "AL35 OR GD35", FORMS_EQ),
    ("al38_ae38_gd38", "AL38 OR AE38 OR GD38", FORMS_EQ),
    ("al41_gd41", "AL41 OR GD41", FORMS_EQ),
    ("gd46", "GD46", FORMS_EQ),
    ("al25_gd25", "AL25 OR GD25", FORMS_EQ),
    ("par_discount_cuasi", "CUASIPAR OR (PAR AND Argentina AND bond)", FORMS_EQ),
    ("bocon", "BOCON", FORMS_EQ),
    ("lefis", "LEFIS", FORMS_EQ),
    ("cusip_arg", "CUSIP AND Argentina AND bond", FORMS_EQ),
    ("isin_arg", "ISIN AND Argentina AND (bond OR BONAR OR GLOBAL)", FORMS_EQ),
    ("xmarket_buy_us", '"purchased in the United States" AND Argentina', "20-F,6-K"),
    ("xmarket_sell_ar", '"sold in Argentina" AND securities', "20-F,6-K"),
    ("xmarket_buy_ar", '"purchased in Argentina" AND securities', "20-F,6-K"),
    ("xmarket_sell_us", '"sold in the United States" AND Argentina', "20-F,6-K"),
    ("dual_listing", '"dual listing" AND Argentina', "20-F,6-K"),
    ("quoted_usd", '"quoted in U.S. dollars" AND Argentina', "20-F,6-K"),
    ("quoted_ars", '"quoted in Argentine pesos"', "20-F,6-K"),
    ("sov_prospectus", "Argentina AND (prospectus OR offering) AND (2030 OR 2035 OR 2038 OR 2041 OR 2046)",
     FORMS_PROSP),
    ("sov_debt_exchange", "Argentina AND (exchange offer OR invitation) AND bond", "6-K,18-K"),
]


def run(name, q, forms, startdt, enddt):
    params = {"q": q, "dateRange": "custom", "startdt": startdt,
              "enddt": enddt, "forms": forms}
    url = BASE + "?" + urllib.parse.urlencode(params)
    r = requests.get(url, headers={"User-Agent": UA, "Accept": "application/json"},
                     timeout=60)
    r.raise_for_status()
    payload = r.json()
    import hashlib
    canon = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
    env = {"meta": {"query": q, "query_name": name, "forms": forms,
                    "startdt": startdt, "enddt": enddt, "source_url": url,
                    "retrieved_at": utcnow_iso(),
                    "sha256": hashlib.sha256(canon).hexdigest(),
                    "http_status": r.status_code, "collector": COLLECTOR,
                    "git_commit": git_commit()}, "payload": payload}
    res = write_raw_noreplace(RAW_FTS / f"p2_{name}__{startdt}_{enddt}.json",
                              json.dumps(env, ensure_ascii=False).encode())
    res["hits"] = payload.get("hits", {}).get("total", {}).get("value", "?")
    return res


def main():
    only = sys.argv[1:] or None
    tot = 0
    for name, q, forms in QUERIES:
        if only and name not in only:
            continue
        for a, b in WINDOWS:
            try:
                r = run(name, q, forms, a, b)
                print(f"[{COLLECTOR}] {name} {a}..{b}: hits={r['hits']} ({r['action']})", flush=True)
                tot += 1
            except Exception as e:
                print(f"[{COLLECTOR}] {name} {a}..{b}: ERROR {type(e).__name__}: {e}", flush=True)
            time.sleep(0.6)
    print(f"[{COLLECTOR}] ventanas={tot}")


if __name__ == "__main__":
    main()
