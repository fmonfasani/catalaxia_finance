"""Find source of existing ADR data in cnv_estados"""
import sqlite3
import os
db = sqlite3.connect(os.path.join("data", os.environ.get("SCREENER_DB", "screener.db")))

for tk in ['BBAR', 'BMA', 'CEPU', 'CRESY', 'EDN', 'GGAL', 'LOMA', 'PAM', 'SUPV', 'TEO']:
    cur = db.execute("""
        SELECT fuente, concepto, period_end, valor, form, accn 
        FROM cnv_estados WHERE ticker=?
        ORDER BY period_end
    """, (tk,))
    rows = cur.fetchall()
    if rows:
        print(f"\n{tk}:")
        for r in rows:
            print(f"  fuente={r[0]:<15} concepto={r[1]:<20} period={r[2]} valor={r[3]} form={r[4]} accn={r[5][:20] if r[5] else 'None'}")
    else:
        print(f"\n{tk}: NO DATA")

db.close()
