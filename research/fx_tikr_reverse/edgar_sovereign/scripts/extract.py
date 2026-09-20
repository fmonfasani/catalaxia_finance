#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extractor de evidencia (PARSED). Reglas léxicas documentadas; clasifica
candidatos, NO veredictos: la clasificación final Tipos A-G la hace el
investigador sobre estos registros (ver evidence.jsonl + informe).

Ventanas de 500 caracteres alrededor de cada match de términos §3. Por cada
ventana: filing meta (del .meta.json), términos matched, heurística sugerida.
Dedup por (filing, offset). Salida: parsed/evidence.jsonl (UTF-8).
Heurísticas (sugerencia, revisable):
  EXPLICIT_FX_CAND : /Ps\.\s?[\d.,]+\s+to\s+U\.S\.\$|translated at|exchange rate (of|was)/i
  INSTR_CAND       : AL30|GD30|BONAR|BODEN|GLOBAL \d|LETES|LEBAC|LECAP|BONCER|BONTES|TESORO
  FAIR_CAND        : fair value|Level [123]|carrying|quoted price|market price|CUSIP|ISIN
"""
from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "engine"))
from common import assert_in_sandbox  # noqa: E402

RAW = ROOT / "edgar_sovereign" / "raw" / "filings"
OUT = ROOT / "edgar_sovereign" / "parsed" / "evidence.jsonl"
EXTRACTOR = "edgar_extract@v1.0.0"
WIN = 500

INSTR = re.compile(r"AL30D?C?|GD30D?C?|BONAR(?:\s+\S+)?|BODEN(?:\s+\d+)?|GLOBAL\s+\d{4}|"
                   r"LETES|LEBACs?|LECAPs?|BONCER|BONTEs?|Tesoro Argentino|"
                   r"Argentine (?:government )?(?:bonds|securities|treasury)|"
                   r"Republic of Argentina|National Treasury Bonds?", re.I)
FX = re.compile(r"Ps\.\s?[\d.,]+\s+to\s+U\.S\.\$\s?\d|exchange rate|translated at|"
                r"convenience of the reader|repo exchange rate", re.I)
VAL = re.compile(r"fair value|Level [123]|carrying value|quoted price|market price|"
                 r"closing price|CUSIP|ISIN|face value|nominal|amortized cost", re.I)


def text_of(p: Path) -> str:
    t = open(p, encoding="utf-8", errors="replace").read()
    t = html.unescape(re.sub(r"<[^>]+>", " ", t))
    return re.sub(r"\s+", " ", t)


def main() -> None:
    assert_in_sandbox(OUT)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    recs: list[dict] = []
    for doc in sorted(RAW.glob("*.htm")):
        meta = json.loads((str(doc) + ".meta.json") and open(str(doc) + ".meta.json", encoding="utf-8").read())
        t = text_of(doc)
        seen: set[int] = set()
        for m in list(INSTR.finditer(t)) + list(FX.finditer(t)):
            start = max(0, m.start() - WIN)
            if any(abs(start - s) < WIN for s in seen):
                continue
            seen.add(start)
            window = t[start:m.end() + WIN]
            recs.append({
                "filing_url": meta["filing_url"], "accession_number": meta["accession_number"],
                "company_cik": meta["company_cik"], "document": meta["document"],
                "filing_date": meta.get("filing_date_hint"),
                "match": m.group(0)[:80], "instr_hit": bool(INSTR.search(window)),
                "fx_hit": bool(FX.search(window)), "val_hit": bool(VAL.search(window)),
                "heuristic": ("EXPLICIT_FX_CAND" if FX.search(window) and re.search(r"Ps\.", window)
                              else "INSTR_FX_CAND" if INSTR.search(window) and FX.search(window)
                              else "INSTR_VAL_CAND" if INSTR.search(window) and VAL.search(window)
                              else "INSTR_CAND" if INSTR.search(window)
                              else "FX_CAND" if FX.search(window) else "VAL_CAND"),
                "evidence_text": window.strip()[:1100],
                "raw_ref": str(doc), "raw_sha256": meta["sha256"],
                "extractor": EXTRACTOR})
    with open(OUT, "w", encoding="utf-8") as f:
        for r in recs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    from collections import Counter
    print(f"[{EXTRACTOR}] docs={len(list(RAW.glob('*.htm')))} ventanas={len(recs)} "
          f"{dict(Counter(r['heuristic'] for r in recs))} -> parsed/evidence.jsonl")


if __name__ == "__main__":
    main()
