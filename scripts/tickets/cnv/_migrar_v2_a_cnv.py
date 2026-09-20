"""
Migrate v2 data into cnv_estados, replacing old cnv-aif2 rows.
Maps v2.cuit → cnv_estados.cik (same convention as v1).
Only processes CUITs specified in --cuits (or all if --all).
"""
import sqlite3, csv, sys
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "data").is_dir())
DB = ROOT / "data" / "screener.db"
SUBSET = ROOT / "scripts" / "tickets" / "cnv" / "datos" / "empresas_subset.csv"

args = sys.argv[1:]
cuits_ok = None
if "--cuits" in args:
    cp = Path(args[args.index("--cuits") + 1])
    cp = cp if cp.exists() else Path(args[args.index("--cuits") + 1])
    cuits_ok = {r["cuit"].strip() for r in csv.DictReader(open(cp, encoding="utf-8-sig")) if r.get("cuit")}
elif "--all" in args:
    pass  # all CUITs in v2

con = sqlite3.connect(DB)
cur = con.cursor()

# Get v2 CUITs
if cuits_ok:
    placeholders = ",".join("?" for _ in cuits_ok)
    cur.execute(f"SELECT DISTINCT cuit FROM cnv_estados_v2 WHERE cuit IN ({placeholders})", list(cuits_ok))
else:
    cur.execute("SELECT DISTINCT cuit FROM cnv_estados_v2")
v2_cuits = [r[0] for r in cur.fetchall()]
print(f"CUITs to migrate: {len(v2_cuits)}")

# Build ticker → cuit mapping from SUBSET
cuit_a_ticker = {}
with open(SUBSET, encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        cu = r["cuit"].strip()
        tk = r["ticker"].strip().upper()
        if cu and tk:
            cuit_a_ticker[cu] = tk

total_deleted = 0
total_inserted = 0

for cuit in v2_cuits:
    # Delete existing cnv-aif2 rows for this CUIT
    cur.execute("DELETE FROM cnv_estados WHERE cik = ? AND fuente = 'cnv-aif2'", (cuit,))
    del_count = cur.rowcount
    total_deleted += del_count

    # Insert v2 rows mapped to cnv_estados schema
    cur.execute("""
        SELECT ticker, cuit, concepto, period_end, tipo, valor,
               valor_comparativo, fecha_reexpresion, form,
               unidad_factor, accn
        FROM cnv_estados_v2
        WHERE cuit = ?
    """, (cuit,))

    rows = []
    for r in cur.fetchall():
        ticker_r, _, concepto, pe, tp, valor, vc, frexp, form, escala, accn = r
        # Use ticker from mapping if available (cnv_estados might have ticker)
        ticker = cuit_a_ticker.get(cuit, ticker_r or "")
        rows.append((ticker, cuit, concepto, pe, tp, valor,
                    vc if vc is not None else None,
                    frexp or "", form, escala or 1, accn, "cnv-aif2"))

    for row in rows:
        try:
            cur.execute("""INSERT OR IGNORE INTO cnv_estados
                (ticker, cik, concepto, period_end, tipo, valor,
                 valor_comparativo, fecha_reexpresion, form, escala, accn, fuente)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""", row)
            total_inserted += 1
        except Exception as e:
            print(f"  ERROR inserting {row[1]} {row[2]} {row[3]}: {e}")

    con.commit()
    ticker = cuit_a_ticker.get(cuit, cuit[-4:])
    print(f"  {ticker:<8} {cuit}  del={del_count} ins={len(rows)}")

print(f"\nTotal: deleted {total_deleted} rows, inserted {total_inserted} rows in cnv_estados")
con.close()
