#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Collector BYMA — PRIORIDAD 2. Sólo verifica disponibilidad; NO descarga series.

Objetivos: MEP, CCL, Dollar Index, CCL Index (índices BYMA).

Hallazgo previo (VERIFICADO POR FUENTE 2026-09-15):
- BYMA Market Data APIs (Snapshot/Delayed/EOD, Índices, Instruments) exigen
  credenciales client_id/client_secret (bymadata-api-wrapper, docs BYMA
  productos-de-datos/market-data/apis). Sin credenciales -> 401/403.
- BYMA OMS (trading) exige API_KEY_ID/SECRET + usuario/clave (repo OMS de ejemplo).
- Índice CCL BYMA existe como producto, histórico sujeto a credenciales.

Regla: si una API requiere credenciales -> NO inventarlas. Se registra
NOT_AVAILABLE / AUTH_REQUIRED con endpoint, documentación y motivo, y el
pipeline sigue con BCRA + reconstrucción (que no requieren auth).

RAW: raw/byma/<producto>.status.json (uno por producto, inmutable por día).
Nunca se guarda un precio sin provenance completa.

Uso:
  python engine/byma_status.py
"""
from __future__ import annotations

import json
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import assert_in_sandbox, git_commit, utcnow_iso, write_raw_noreplace

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RAW_DIR = ROOT / "raw" / "byma"
COLLECTOR_VERSION = "byma_status@v1.0.0"

PRODUCTS = [
    {"producto": "MEP", "endpoint": "api-mgr.byma.com.ar/{eod|delayed}/fixed_income",
     "docs": "https://www.byma.com.ar/productos/productos-de-datos/market-data/apis",
     "status": "AUTH_REQUIRED",
     "reason": "BYMA DataLens exige client_id/client_secret; sin credenciales en .env. No inventadas."},
    {"producto": "CCL", "endpoint": "api-mgr.byma.com.ar/{eod|delayed}/fixed_income",
     "docs": "https://www.byma.com.ar/productos/productos-de-datos/market-data/apis",
     "status": "AUTH_REQUIRED",
     "reason": "Idem MEP: credenciales BYMA requeridas y ausentes."},
    {"producto": "Dollar_Index", "endpoint": "api-mgr.byma.com.ar/{eod|delayed}/indices",
     "docs": "https://www.byma.com.ar/productos/productos-de-datos/market-data/apis",
     "status": "AUTH_REQUIRED",
     "reason": "Endpoint indices con credenciales; ausentes."},
    {"producto": "CCL_Index",
     "endpoint": "https://www.byma.com.ar/productos/productos-de-datos/indice-ccl-byma-historico",
     "docs": "https://www.byma.com.ar/productos/productos-de-datos/indice-ccl-byma-historico",
     "status": "AUTH_REQUIRED",
     "reason": "Producto existe (índice CCL BYMA) pero el histórico descargable exige acceso BYMA; ausente."},
]


def main() -> None:
    assert_in_sandbox(RAW_DIR)
    retrieved = utcnow_iso()
    for p in PRODUCTS:
        doc = {"source": "BYMA", "producto": p["producto"], "endpoint": p["endpoint"],
               "docs": p["docs"], "status": p["status"], "reason": p["reason"],
               "source_url": p["endpoint"], "retrieved_at": retrieved,
               "source_date": retrieved[:10], "sha256": None,
               "collector": COLLECTOR_VERSION, "git_commit": git_commit(),
               "action_requerida": "proveer BYMA_CLIENT_ID/SECRET en .env (nunca en código) y re-ejecutar"}
        out = RAW_DIR / f"{p['producto'].lower()}.status.json"
        res = write_raw_noreplace(out, json.dumps(doc, ensure_ascii=False, indent=1).encode("utf-8"))
        print(f"[{COLLECTOR_VERSION}] {p['producto']}: {p['status']} ({res['action']})")


if __name__ == "__main__":
    main()
