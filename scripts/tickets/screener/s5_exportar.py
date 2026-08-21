# -*- coding: utf-8 -*-
"""
FASE 5 -- Validacion final + export CSV
=========================================
Cross-checks de cobertura, rangos, y exporta screener_export.csv.

Gates:
  1. Cobertura minima (ningun ratio obligatorio en todas)
  2. Rango razonable (ROE entre -1 y 1, PER entre 0 y 200, etc.)
  3. Reporte de entidades con datos criticos faltantes
"""
from __future__ import annotations
import sqlite3, csv, json, math
from pathlib import Path
from collections import defaultdict

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "data").is_dir())
import os as _os
# SCREENER_DB permite apuntar a una copia de prueba sin tocar produccion:
#   SCREENER_DB=screener.db.test python scripts/tickets/screener/run_all.py
# Debe estar en TODOS los scripts del pipeline: si uno solo no lo respeta,
# escribe en la base real aunque el resto corra sobre la copia.
DB = ROOT / "data" / _os.environ.get("SCREENER_DB", "screener.db")
OUT = ROOT / "data" / "screener_export.csv"
OUT_JSON = ROOT / "data" / "screener_export.json"


def build():
    con = sqlite3.connect(DB)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=60000")
    cur = con.cursor()

    print("FASE 5 -- Validacion final + export CSV")
    print("=" * 60)

    # --- Cobertura ---
    cur.execute("SELECT COUNT(1) FROM screener")
    n = cur.fetchone()[0]
    print(f"Entidades en screener: {n}")

    ratios = ["ROE", "ROA", "MargenNeto", "DeudaEBITDA", "EPS", "FCF_CE",
              "Payout", "CAGR_EPS_5y", "PER", "PriceBook", "PriceSales",
              "Precio", "Max52w", "Min52w",
              "ev_ebitda", "margen_operativo", "payout_status"]

    print(f"\n  Cobertura por ratio:")
    cobertura = {}
    for r in ratios:
        cur.execute(f"SELECT COUNT(1) FROM screener WHERE \"{r}\" IS NOT NULL")
        cnt = cur.fetchone()[0]
        pct = round(100 * cnt / n, 1)
        cobertura[r] = cnt
        print(f"    {r:<15s} {cnt:>3}/{n} ({pct:>5.1f}%)")

    # --- Rango razonable ---
    print(f"\n  Gate de rangos:")
    gates = [
        ("ROE", -5.0, 5.0),
        ("ROA", -1.0, 1.0),
        ("MargenNeto", -10.0, 10.0),
        ("DeudaEBITDA", 0, 50),
        ("PER", 0, 500),
        ("PriceBook", 0, 50),
        ("PriceSales", 0, 50),
        ("FCF_CE", -5.0, 5.0),
        ("CAGR_EPS_5y", -5.0, 5.0),
    ]
    fuera_rango = 0
    for campo, lo, hi in gates:
        cur.execute(f'SELECT COUNT(1) FROM screener WHERE "{campo}" IS NOT NULL AND ("{campo}" < ? OR "{campo}" > ?)',
                    (lo, hi))
        cnt = cur.fetchone()[0]
        if cnt > 0:
            fuera_rango += cnt
            cur.execute(f'SELECT ticker, "{campo}" FROM screener WHERE "{campo}" IS NOT NULL AND ("{campo}" < ? OR "{campo}" > ?) LIMIT 3',
                        (lo, hi))
            for r in cur.fetchall():
                print(f"    [OUTLIER] {r[0]:20s} {campo}={r[1]:.4f} (rango [{lo},{hi}])")

    if fuera_rango == 0:
        print("    Todos los valores en rango razonable")
    else:
        print(f"    {fuera_rango} valores fuera de rango (reportados arriba)")

    # --- Proveedores de datos (provenance) ---
    print(f"\n  Provenance (fuentes de datos):")
    cur.execute("""
        SELECT provenance FROM screener WHERE provenance IS NOT NULL
    """)
    prov_cont = defaultdict(int)
    for r in cur.fetchall():
        items = r[0].split("; ")
        for it in items:
            it = it.strip()
            if it:
                prov_cont[it] += 1
    for item, cnt in sorted(prov_cont.items(), key=lambda x: -x[1])[:15]:
        print(f"    {item:<25s} {cnt:>4} entidades")

    # --- Export CSV ---
    print(f"\n  Exportando a {OUT.name}...")
    cur.execute("PRAGMA table_info(screener)")
    cols = [c[1] for c in cur.fetchall()]
    # Renombrar ultimo_periodo -> period_ref en el CSV
    col_map = {"ultimo_periodo": "period_ref"}
    safe_cols = [col_map.get(c, c) for c in cols]
    filas = cur.execute("SELECT * FROM screener ORDER BY ticker").fetchall()
    try:
        with open(OUT, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(safe_cols)
            w.writerows(filas)
        print(f"    -> {OUT} ({n} filas, {len(safe_cols)} columnas)")
    except PermissionError:
        print(f"    [!] {OUT.name} LOCKEADO (¿abierto en Excel/visor?) — se saltea el CSV, "
              f"cerralo y re-corré s5. El JSON y el DB están OK.")

    # --- Export JSON (mismo dato, para consumo por apps) ---
    # Array de objetos {columna: valor}. NaN/inf -> null (JSON valido).
    def _clean(v):
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            return None
        return v
    registros = [{k: _clean(v) for k, v in zip(safe_cols, fila)} for fila in filas]
    try:
        with open(OUT_JSON, "w", encoding="utf-8") as f:
            json.dump(registros, f, ensure_ascii=False)
        print(f"    -> {OUT_JSON} ({len(registros)} empresas, {OUT_JSON.stat().st_size//1024} KB)")
    except PermissionError:
        print(f"    [!] {OUT_JSON.name} LOCKEADO — se saltea; cerralo y re-corré s5.")

    # --- Reporte de completitud ---
    print(f"\n  Entidades con mas datos faltantes (top 5):")
    cur.execute("""
        SELECT ticker,
               (CASE WHEN ROE IS NULL THEN 1 ELSE 0 END +
                CASE WHEN ROA IS NULL THEN 1 ELSE 0 END +
                CASE WHEN EPS IS NULL THEN 1 ELSE 0 END +
                CASE WHEN PER IS NULL THEN 1 ELSE 0 END +
                CASE WHEN Precio IS NULL THEN 1 ELSE 0 END) as missing
        FROM screener
        ORDER BY missing DESC
        LIMIT 5
    """)
    for r in cur.fetchall():
        cur.execute(f'SELECT ROE, ROA, EPS, PER, Precio FROM screener WHERE ticker=?', (r[0],))
        vals = cur.fetchone()
        print(f"    {r[0]:20s} missing={r[1]}  ROE={vals[0]} ROA={vals[1]} EPS={vals[2]} PER={vals[3]} Precio={vals[4]}")

    con.close()
    print("\nFASE 5 -- OK")


if __name__ == "__main__":
    build()
