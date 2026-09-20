#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Collector BCRA OFICIAL minorista — PRIORIDAD 1 (fuente primaria, sin auth).

Fuente primaria: BCRA Tipo de cambio minorista, serie histórica de cierre
(VERIFICADO POR EJECUCIÓN 2026-09-15: POST a
https://www.bcra.gob.ar/cierre-de-cotizaciones-resultado/ con moneda=2
[Dólar estadounidense] responde 200 con tabla HTML:
<tr data-fecha="YYYY-MM-DD"><td>DD-MM-YYYY</td><td>compra</td><td>venta</td></tr>,
miles con '.' y decimales con ','. Una sola descarga trae TODA la serie
2010-06-01 -> hoy; por eso el RAW es un snapshot fechado, no un archivo por día.

Metodología BCRA (Comunicación B 9791, citada en la página): promedio ponderado
de entidades informantes, plaza CABA. Compra y venta se persisten ambas; el
canónico para fx_value es VENTA (dólar vendedor), declarado en normalize.py.

RAW:
  raw/bcra/oficial/snapshot_<retrieved-date>.html       (HTML íntegro, inmutable)
  raw/bcra/oficial/snapshot_<retrieved-date>.meta.json  (source_url, retrieved_at,
     source_date=snapshot, sha256 del HTML, http_status, collector, git_commit)
PARSED: parsed/bcra_oficial.csv (source_date, compra, venta, provenance_id).

Si el POST falla o el HTML no trae filas -> status NOT_AVAILABLE con motivo;
jamás se inventa un valor (REQ-FX-006).

Uso:
  python engine/bcra_oficial.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from html import unescape

import requests

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (assert_in_sandbox, git_commit, utcnow_iso,
                    write_raw_noreplace, ENGINE_VERSION)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RAW_DIR = ROOT / "raw" / "bcra" / "oficial"
PARSED = ROOT / "parsed" / "bcra_oficial.csv"
URL = "https://www.bcra.gob.ar/cierre-de-cotizaciones-resultado/"
COLLECTOR_VERSION = "bcra_oficial@v1.0.0"
TIMEOUT = 60

ROW_RE = re.compile(
    r'<tr\s+data-fecha="(\d{4}-\d{2}-\d{2})">\s*<td>([^<]+)</td>\s*'
    r'<td>([^<]+)</td>\s*<td>([^<]+)</td>', re.IGNORECASE)


def to_float(es: str) -> float | None:
    try:
        return float(es.strip().replace(".", "").replace(",", "."))
    except (ValueError, AttributeError):
        return None


def fetch_snapshot() -> tuple[int, bytes, str]:
    retrieved = utcnow_iso()
    r = requests.post(URL, data={"moneda": "2"}, timeout=TIMEOUT,
                      headers={"User-Agent": "catalaxia-fx-engine/1.0",
                               "Content-Type": "application/x-www-form-urlencoded"})
    r.raise_for_status()
    return r.status_code, r.content, retrieved


def parse_snapshot(html: str) -> list[dict]:
    rows = []
    for m in ROW_RE.finditer(html):
        iso, shown, compra, venta = m.groups()
        rows.append({"source_date": iso, "display_date": shown.strip(),
                     "compra": to_float(unescape(compra)),
                     "venta": to_float(unescape(venta))})
    # dedup por fecha (el servidor no debería duplicar; si lo hace, se registra)
    seen, out, dups = set(), [], 0
    for row in rows:
        if row["source_date"] in seen:
            dups += 1
            continue
        seen.add(row["source_date"])
        out.append(row)
    return out


def main() -> None:
    assert_in_sandbox(RAW_DIR)
    assert_in_sandbox(PARSED)
    try:
        http_status, content, retrieved = fetch_snapshot()
    except Exception as e:
        status = {"status": "NOT_AVAILABLE", "source": "BCRA-minorista",
                  "source_url": URL, "retrieved_at": utcnow_iso(),
                  "reason": f"{type(e).__name__}: {e}",
                  "collector": COLLECTOR_VERSION, "git_commit": git_commit()}
        p = RAW_DIR / "STATUS.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(status, ensure_ascii=False, indent=1), encoding="utf-8")
        raise SystemExit(f"[{COLLECTOR_VERSION}] NOT_AVAILABLE: {status['reason']}")
    import hashlib
    sha = hashlib.sha256(content).hexdigest()
    day = retrieved[:10]
    html_res = write_raw_noreplace(RAW_DIR / f"snapshot_{day}.html", content)
    meta = {"source": "BCRA-minorista-serie-cierre", "fx_type": "OFICIAL",
            "source_url": URL + " [POST moneda=2]",
            "retrieved_at": retrieved, "source_date": f"snapshot-{day}",
            "sha256": sha, "http_status": http_status,
            "collector": COLLECTOR_VERSION, "engine": ENGINE_VERSION,
            "git_commit": git_commit(), "raw_ref": html_res["path"],
            "note": "venta = dólar vendedor minorista (canónico); compra se conserva"}
    write_raw_noreplace(RAW_DIR / f"snapshot_{day}.meta.json",
                        json.dumps(meta, ensure_ascii=False, indent=1).encode("utf-8"))
    rows = parse_snapshot(content.decode("utf-8", errors="replace"))
    if not rows:
        raise SystemExit(f"[{COLLECTOR_VERSION}] NOT_AVAILABLE: HTML sin filas parseables "
                         f"(sha256={sha}); serie no inventada.")
    PARSED.parent.mkdir(parents=True, exist_ok=True)
    import csv
    with open(PARSED, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["source_date", "compra", "venta", "provenance_id"])
        w.writeheader()
        for row in sorted(rows, key=lambda r: r["source_date"]):
            w.writerow({"source_date": row["source_date"], "compra": row["compra"],
                        "venta": row["venta"],
                        "provenance_id": f"bcra-oficial:{row['source_date']}:{sha[:12]}"})
    print(f"[{COLLECTOR_VERSION}] filas={len(rows)} rango={rows and min(r['source_date'] for r in rows)}"
          f"->{max(r['source_date'] for r in rows)} sha256={sha[:16]}... -> {PARSED.name}")


if __name__ == "__main__":
    main()
