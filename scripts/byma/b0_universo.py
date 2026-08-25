"""
E2a — b0_universo: matriz del universo BYMA.

Lee:  snapshot (data/backups/snapshot_byma_*.db mas reciente)
Escribe: data/byma_pipeline.db -> tabla byma_universo
NO toca screener.db.
"""
import glob
import os
import sqlite3
from datetime import datetime

BASE = r'D:\Software Development\Porfolio\catalaxia-cedears-prod'
PIPE = os.path.join(BASE, 'data', 'byma_pipeline.db')

SNAPS = sorted(glob.glob(os.path.join(BASE, 'data', 'backups', 'snapshot_byma_2*.db')))
SNAPS = [s for s in SNAPS if '_baseline_' not in s]
if not SNAPS:
    raise SystemExit('FALLO: no hay snapshot. Correr snapshot_byma.py')
SNAP = SNAPS[-1]
print(f'snapshot fuente: {os.path.basename(SNAP)}')

LIMITE_STALE = '2025-06-30'

src = sqlite3.connect(SNAP)
sc = src.cursor()
if os.path.exists(PIPE):
    os.remove(PIPE)
dst = sqlite3.connect(PIPE)
dc = dst.cursor()

dc.execute("""CREATE TABLE byma_universo (
    cuit TEXT PRIMARY KEY,
    ticker TEXT,
    nombre TEXT,
    grupo TEXT,
    fy_end_month INTEGER,
    fiscal_inconsistent INTEGER,
    n_periodos_eeff INTEGER,
    primer_eeff TEXT,
    ultimo_eeff TEXT,
    tiene_ttm INTEGER,
    cnv_ok INTEGER,
    estado TEXT,
    motivo_estado TEXT,
    built_at TEXT)""")

# Universo = cuits con EEFF en CNV (norm) UNION mapa_entidades
cuits_norm = {r[0] for r in sc.execute(
    "SELECT DISTINCT cuit FROM cnv_estados_norm WHERE cuit IS NOT NULL")}
mapa = {}
for cuit, tk, nom, grp, prim in sc.execute(
        "SELECT cuit, ticker, nombre, grupo, es_primario FROM mapa_entidades"):
    prev = mapa.get(cuit)
    if prev is None or (prim == 1 and prev[4] != 1):
        mapa[cuit] = (cuit, tk, nom, grp, prim)
fiscal = {r[0]: (r[1], r[2]) for r in sc.execute(
    """SELECT cuit, fy_end_month, inconsistent FROM fiscal_calendar""")}
ttm_cuits = {r[0] for r in sc.execute(
    "SELECT DISTINCT cuit FROM ratios_ttm WHERE cuit IS NOT NULL")}

universo = set(cuits_norm) | set(mapa)
rows = []
for cuit in sorted(universo):
    m = mapa.get(cuit)
    ticker = (m[1] if m else None) or ''
    nombre = (m[2] if m else None) or ''
    grupo = (m[3] if m else None) or ''
    f = fiscal.get(cuit, (None, None))
    stats = sc.execute(
        """SELECT COUNT(DISTINCT period_end), MIN(period_end), MAX(period_end)
           FROM cnv_estados_norm WHERE cuit=?""", (cuit,)).fetchone()
    n_per, primer, ultimo = int(stats[0]), stats[1], stats[2]
    tiene_ttm = 1 if cuit in ttm_cuits else 0
    if n_per == 0:
        estado, motivo = 'SIN_CNV', 'sin estados contables en cnv_estados_norm'
        cnv_ok = 0
    elif ultimo and ultimo >= LIMITE_STALE:
        estado, motivo = 'FRESCO', f'ultimo cierre {ultimo} >= {LIMITE_STALE}'
        cnv_ok = 1
    else:
        estado, motivo = 'STALE', f'ultimo cierre {ultimo} < {LIMITE_STALE}'
        cnv_ok = 1
    rows.append((cuit, ticker, nombre, grupo, f[0], f[1], n_per, primer, ultimo,
                 tiene_ttm, cnv_ok, estado, motivo, datetime.now().isoformat()))

dc.executemany('INSERT INTO byma_universo VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)', rows)
dst.commit()

n_total = dc.execute('SELECT COUNT(*) FROM byma_universo').fetchone()[0]
print()
print('RESUMEN b0_universo:')
for est, n in dc.execute('SELECT estado, COUNT(*) FROM byma_universo GROUP BY 1'):
    print(f'  {est:<10} {n}')
print(f'  total universo: {n_total}')
print(f'  con TTM previo: {dc.execute("SELECT SUM(tiene_ttm) FROM byma_universo").fetchone()[0]}')
print()
stale = dc.execute(
    "SELECT ticker, nombre, ultimo_eeff FROM byma_universo WHERE estado='STALE' ORDER BY ultimo_eeff").fetchall()
print(f'STALE ({len(stale)}):')
for s in stale[:15]:
    print(f'  {s[0] or "?":<8} {str(s[1])[:35]:<35} ultimo={s[2]}')
src.close()
dst.close()
