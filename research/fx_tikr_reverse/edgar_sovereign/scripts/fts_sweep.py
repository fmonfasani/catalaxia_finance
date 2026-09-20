#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Barrido universo EDGAR FTS — guarda RAW inmutable por query (1 JSON por query).

Fuente: https://efts.sec.gov/LATEST/search-index (VERIFICADO POR EJECUCIÓN
2026-09-15: responde 200 sin auth; exige User-Agent; <=10 req/s, aquí ~0.5s).
Cada archivo: {meta:{query, forms, startdt, enddt, source_url, retrieved_at,
sha256, http_status, collector, git_commit}, payload:{...hits íntegros...}}.
RAW inmutable: write_raw_noreplace (engine/common.py). Sin imputación.
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
COLLECTOR = "edgar_fts@v1.0.0"
UA = "Catalaxia research contact@catalaxia.example"
BASE = "https://efts.sec.gov/LATEST/search-index"

# Universo §2+§3 del encargo: (nombre, q, forms). Período 2001-2026 en 2 ventanas
# (FTS limita tamaño; ventana partida = cobertura, no cherry-picking).
WINDOWS = [("2001-01-01", "2015-12-31"), ("2016-01-01", "2026-09-15")]
QUERIES: list[tuple[str, str, str]] = [
    ("republic_argentina", '"Republic of Argentina"', "20-F,6-K,18-K,424B2,424B5,F-3"),
    ("argentine_republic", '"Argentine Republic"', "20-F,6-K,18-K"),
    ("argentine_sovereign", '"Argentine sovereign"', "20-F,6-K,18-K,424B2"),
    ("argentine_govt_bonds", '"Argentine government bonds"', "20-F,6-K"),
    ("argentine_govt_securities", '"Argentine government securities"', "20-F,6-K"),
    ("al30", "AL30", "20-F,6-K"),
    ("gd30", "GD30", "20-F,6-K"),
    ("bonar", "BONAR", "20-F,6-K,18-K"),
    ("boden", "BODEN", "20-F,6-K,18-K"),
    ("global_bond_arg", '"Global" AND Argentina AND bond', "20-F,6-K,18-K,424B2,F-3"),
    ("letes", "LETES", "20-F,6-K"),
    ("lebac", "LEBAC", "20-F,6-K"),
    ("lecap", "LECAP", "20-F,6-K"),
    ("boncer", "BONCER", "20-F,6-K"),
    ("bontes", "BONTES", "20-F,6-K"),
    ("tesoro_argentino", '"Tesoro Argentino"', "20-F,6-K"),
    ("exchange_rate_used", '"exchange rate" AND Argentina', "20-F,6-K"),
    ("translated_rate", '"translated at" AND pesos', "20-F,6-K"),
    ("treasury_arg", '"ARGENTINE TREASURY" OR "TESORO ARGENTINO"', "20-F,6-K"),
]


def run_query(name: str, q: str, forms: str, startdt: str, enddt: str) -> dict:
    params = {"q": q, "dateRange": "custom", "startdt": startdt,
              "enddt": enddt, "forms": forms}
    url = BASE + "?" + urllib.parse.urlencode(params)
    r = requests.get(url, headers={"User-Agent": UA, "Accept": "application/json"},
                     timeout=60)
    r.raise_for_status()
    payload = r.json()
    retrieved = utcnow_iso()
    canon = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    import hashlib
    envelope = {"meta": {"query": q, "query_name": name, "forms": forms,
                         "startdt": startdt, "enddt": enddt, "source_url": url,
                         "retrieved_at": retrieved,
                         "sha256": hashlib.sha256(canon).hexdigest(),
                         "http_status": r.status_code, "collector": COLLECTOR,
                         "git_commit": git_commit()},
                "payload": payload}
    out = RAW_FTS / f"{name}__{startdt}_{enddt}.json"
    res = write_raw_noreplace(out, json.dumps(envelope, ensure_ascii=False).encode("utf-8"))
    total = payload.get("hits", {}).get("total", {}).get("value", "?")
    res.update({"query": name, "window": f"{startdt}..{enddt}", "hits": total})
    return res


def main() -> None:
    only = sys.argv[1:] or None
    results = []
    for name, q, forms in QUERIES:
        if only and name not in only:
            continue
        for startdt, enddt in WINDOWS:
            try:
                res = run_query(name, q, forms, startdt, enddt)
                print(f"[{COLLECTOR}] {name} {startdt}..{enddt}: hits={res['hits']} ({res['action']})")
                results.append(res)
            except Exception as e:
                print(f"[{COLLECTOR}] {name} {startdt}..{enddt}: ERROR {type(e).__name__}: {e}")
                results.append({"query": name, "error": str(e)})
            time.sleep(0.6)
    n_hits = sum(r.get("hits", 0) for r in results if isinstance(r.get("hits"), int))
    print(f"[{COLLECTOR}] queries={len(results)} hits_totales(sum)={n_hits}")


if __name__ == "__main__":
    main()
