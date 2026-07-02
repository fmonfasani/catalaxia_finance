import sqlite3
db = sqlite3.connect('data/screener.db')
cur = db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
for r in cur:
    print(r[0])
print()
# Check cnv_estados columns
cur = db.execute("PRAGMA table_info(cnv_estados)")
cols = cur.fetchall()
for c in cols:
    print(c)
print()
# Check all tables with columns
for t in ['cnv_estados', 'links_eeff', 'empresas']:
    try:
        cur = db.execute(f"PRAGMA table_info({t})")
        print(f"\n{t}:")
        for c in cur.fetchall():
            print(f"  {c[1]} ({c[2]})")
    except:
        pass
db.close()
