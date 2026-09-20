#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Descarga filings EDGAR a RAW inmutable (1 archivo por documento + .meta.json).

Origen de cada target: hit FTS en raw/fts/*.json (query_name + _id). Nada se
inventa: accession/CIK/doc salen del hit. Rate <= 10 req/s (aquí ~1s).
Fuente: https://www.sec.gov/Archives/edgar/data/<cik>/<acc_sin_guiones>/<doc>
Lista curada inicial (12 docs, priorización §10 del encargo):
  mercado explícito > transacción USD/ARS > dual USD+ARS > FX explícito >
  fair value L1 > holdings. Se cubren AL30/GD30 (menciones directas) + 20-F
  bancarios (BODEN/BONAR + fair value + FX) + 18-K soberano (identidad).
Uso: python scripts/dl_filings.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "engine"))
from common import git_commit, utcnow_iso, write_raw_noreplace  # noqa: E402

RAW = ROOT / "edgar_sovereign" / "raw" / "filings"
COLLECTOR = "edgar_dl@v1.0.0"
UA = "Catalaxia research contact@catalaxia.example"

# (fts_query, hit_id_prefijo, cik, accession_sin_guiones, doc, motivo)
TARGETS: list[tuple[str, str, str, str, str, str]] = [
    ("al30", "0001292814-26-004154", "913059", "000129281426004154", "ex99-1.htm",
     "BBVA 6-K 2026-08-10 menciona AL30 (earnings: valores + FX?)"),
    ("al30", "0001517399-26-000025", "1517399", "000151739926000025", "supv-20260331x6k.htm",
     "Supervielle 6-K 2026-05-27 menciona AL30"),
    ("gd30", "0001654954-23-015150", "1717161", "000165495423015150", "cepu_6k.htm",
     "CEPU 6-K 2023-12-05 menciona GD30"),
    ("gd30", "0001104659-24-116432", "932470", "000110465924116432", "tm2428055d1_6k.htm",
     "Telecom 6-K 2024-11-12 menciona GD30"),
    ("gd30", "0001114700-25-000049", "1114700", "000111470025000049", "exhibit4_4.htm",
     "GGAL 20-F exhibit (términos instrumento?)"),
    ("republic_argentina", "0001193125-25-087225", "1347426", "000119312525087225", "d865064dex81.htm",
     "Macro Bank 20-F 2025 (EX-8.1; contexto Republic of Argentina)"),
]


def dl_index(cik: str, acc: str) -> dict:
    """Baja el índice del filing (descubre documento principal). También es RAW."""
    url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/index.json"
    r = requests.get(url, headers={"User-Agent": UA, "Accept": "application/json"},
                     timeout=60)
    r.raise_for_status()
    stem = f"{cik}_{acc}_index.json"
    if f"{stem}.meta.json" not in _seen():
        res = write_raw_noreplace(RAW / stem, r.content)
        import hashlib
        meta = {"source": "SEC_EDGAR", "filing_url": url, "accession_number": acc,
                "company_cik": cik, "document": "index.json",
                "fts_query": "filing-index", "motivo": "descubrir documento principal",
                "retrieved_at": utcnow_iso(),
                "sha256": hashlib.sha256(r.content).hexdigest(),
                "http_status": r.status_code, "collector": COLLECTOR,
                "git_commit": git_commit(), "raw_ref": res["path"]}
        write_raw_noreplace(RAW / f"{stem}.meta.json",
                            json.dumps(meta, ensure_ascii=False, indent=1).encode("utf-8"))
    return r.json()
    url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/index.json"


def _seen() -> set[str]:
    return {p.name.replace(".meta.json", "") for p in RAW.glob("*.meta.json")}


def dl(cik: str, acc: str, doc: str, fts_query: str, motivo: str) -> dict:
    url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{doc}"
    r = requests.get(url, headers={"User-Agent": UA, "Accept": "*/*"}, timeout=90)
    r.raise_for_status()
    retrieved = utcnow_iso()
    import hashlib
    sha = hashlib.sha256(r.content).hexdigest()
    stem = f"{cik}_{acc}_{doc.replace('/', '_')}"
    res = write_raw_noreplace(RAW / stem, r.content)
    meta = {"source": "SEC_EDGAR", "filing_url": url, "accession_number": acc,
            "company_cik": cik, "document": doc, "fts_query": fts_query,
            "motivo": motivo, "retrieved_at": retrieved, "sha256": sha,
            "http_status": r.status_code, "bytes": len(r.content),
            "collector": COLLECTOR, "git_commit": git_commit(),
            "raw_ref": res["path"]}
    write_raw_noreplace(RAW / f"{stem}.meta.json",
                        json.dumps(meta, ensure_ascii=False, indent=1).encode("utf-8"))
    res.update({"url": url, "bytes": len(r.content)})
    return res


def main() -> None:
    seen = _seen()
    # dedup: mismo (cik,acc,doc) una sola vez aunque venga de 2 queries
    done: set[str] = set()
    for fts_query, _hit, cik, acc, doc, motivo in TARGETS:
        key = f"{cik}_{acc}_{doc}"
        if key in done or f"{key}" in seen or f"{key}.htm" in seen:
            print(f"[{COLLECTOR}] SKIP duplicado {key}")
            continue
        done.add(key)
        try:
            res = dl(cik, acc, doc, fts_query, motivo)
            idx = dl_index(cik, acc)
            items = (idx.get("directory") or {}).get("item", [])
            mains = [i["name"] for i in items
                     if i["name"].endswith(".htm") and "ex" not in i["name"].lower()
                     and "exhibit" not in i["name"].lower()]
            print(f"[{COLLECTOR}] {key}: {res['action']} bytes={res['bytes']} mains={mains[:4]}")
        except Exception as e:
            print(f"[{COLLECTOR}] {key}: ERROR {type(e).__name__}: {e}")
        time.sleep(1.0)


if __name__ == "__main__":
    main()
