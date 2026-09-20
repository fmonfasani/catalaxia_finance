#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Descargas fase-2 (prospectos soberanos + CEPU adicionales + Ternium control).

Targets con provenance de query FTS (nombre archivo p2_* o consulta ad-hoc
persistida aquí como RAW). Reutiliza dl/dl_index de dl_filings (no duplica).
Uso: python sovereign_matrix/scripts/dl_phase2.py
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
import urllib.parse
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE.parent.parent / "edgar_sovereign" / "scripts"))
from dl_filings import dl, dl_index  # noqa: E402
sys.path.insert(0, str(ROOT / "engine"))
from common import git_commit, utcnow_iso, write_raw_noreplace  # noqa: E402

RAW_FTS = ROOT / "edgar_sovereign" / "raw" / "fts"
UA = "Catalaxia research contact@catalaxia.example"
COLLECTOR = "edgar_dl_p2@v1.0.0"

PROSPECTUS_Q = {"q": "bond", "dateRange": "custom", "startdt": "2001-01-01",
                "enddt": "2026-09-15", "forms": "424B2,424B5,F-3,424B3",
                "ciks": "0000914021"}


def save_prospectus_query() -> None:
    url = ("https://efts.sec.gov/LATEST/search-index?"
           + urllib.parse.urlencode(PROSPECTUS_Q))
    r = requests.get(url, headers={"User-Agent": UA, "Accept": "application/json"},
                     timeout=60)
    r.raise_for_status()
    payload = r.json()
    canon = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
    env = {"meta": {"query": "bond (CIK 0000914021)", "query_name": "sov_prospectus_cik",
                    "forms": PROSPECTUS_Q["forms"], "startdt": "2001-01-01",
                    "enddt": "2026-09-15", "source_url": url,
                    "retrieved_at": utcnow_iso(),
                    "sha256": hashlib.sha256(canon).hexdigest(),
                    "http_status": r.status_code, "collector": COLLECTOR,
                    "git_commit": git_commit()}, "payload": payload}
    res = write_raw_noreplace(
        RAW_FTS / "p2_sov_prospectus_cik__2001-01-01_2026-09-15.json",
        json.dumps(env, ensure_ascii=False).encode())
    print(f"[{COLLECTOR}] prospectus-query: hits={payload['hits']['total']['value']} ({res['action']})")


JOBS = [
    ("914021", "000119312520221606", "d68512d424b5.htm",
     "Argentina 424B5 2020-08-17 (canje 2020: Step-Up 2030/35/38/41/46?)"),
    ("914021", "000119312518005905", "d519997d424b5.htm",
     "Argentina 424B5 2018-01-08 (emisión GLOBAL pre-canje)"),
    ("1717161", "000165495423013780", "cepu_6k.htm",
     "CEPU 6-K 2023-11-03 (serie dividendos, AL35/GD35?)"),
    ("1717161", "000129281424004083", "cepu20241107_6k.htm",
     "CEPU 6-K 2024-11-07 (serie dividendos, posible 2da fecha de valuación)"),
    ("1342874", "000134287421000031", "tx-20201231.htm",
     "Ternium 20-F 2020 (control negativo frase cross-market)"),
]


def main() -> None:
    save_prospectus_query()
    time.sleep(1)
    for cik, acc, doc, motivo in JOBS:
        try:
            res = dl(cik, acc, doc, "phase2", motivo)
            idx = dl_index(cik, acc)
            items = (idx.get("directory") or {}).get("item", [])
            mains = [i["name"] for i in items if i["name"].endswith((".htm", ".txt"))
                     and "ex" not in i["name"].lower()][:4]
            print(f"[{COLLECTOR}] {doc}: {res['action']} bytes={res['bytes']} mains={mains}", flush=True)
        except Exception as e:
            print(f"[{COLLECTOR}] {doc}: ERROR {type(e).__name__}: {e}", flush=True)
        time.sleep(1)


if __name__ == "__main__":
    main()
