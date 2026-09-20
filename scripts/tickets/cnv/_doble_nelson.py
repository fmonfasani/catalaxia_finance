import sqlite3
db = r'D:\Software Development\Porfolio\catalaxia-cedears-prod\data\screener.db'
con = sqlite3.connect(db)
cur = con.cursor()

# 1. EPS=None: existe el concepto con otro nombre?
print("=== EPS=None: conceptos disponibles ===")
for tk in ('INVJ', 'REGE', 'SAMI'):
    cur.execute("SELECT cuit FROM mapa_entidades WHERE ticker=? AND es_primario=1", (tk,))
    r = cur.fetchone()
    if not r: continue
    cuit = r[0]
    cur.execute("""
        SELECT DISTINCT concepto FROM cnv_estados_norm
        WHERE cuit=? AND (concepto LIKE '%EPS%' OR concepto LIKE '%por_acc%' OR concepto LIKE '%basico%')
        ORDER BY concepto
    """, (cuit,))
    conc = [r[0] for r in cur.fetchall()]
    print(f"  {tk}: conceptos= {conc}")
    # Try a broader search: any concept that has "resultado" or "ganancia" near "accion"
    cur.execute("""
        SELECT DISTINCT concepto FROM cnv_estados_norm
        WHERE cuit=? AND concepto IN ('NetIncome', 'Revenue', 'Equity', 'Assets')
        ORDER BY concepto
    """, (cuit,))
    basics = [r[0] for r in cur.fetchall()]
    print(f"         basics= {basics}")

# 2. EPS negativo: hay otro periodo con EPS positivo?
print("\n=== EPS negativos: periodos alternativos ===")
for tk in ('CELU', 'COME', 'DOME', 'FERR', 'GARO', 'HARG', 'LEDE', 'LONG', 'MOLI', 'RAGH', 'RIGO', 'ROSE'):
    cur.execute("SELECT cuit FROM mapa_entidades WHERE ticker=? AND es_primario=1", (tk,))
    r = cur.fetchone()
    if not r: continue
    cuit = r[0]
    cur.execute("""
        SELECT period_end, valor FROM cnv_estados_norm
        WHERE cuit=? AND concepto='EPS_basico'
        ORDER BY period_end DESC
        LIMIT 8
    """, (cuit,))
    eps_rows = cur.fetchall()
    # filter to positive values
    pos_eps = [(pe, v) for pe, v in eps_rows if v and v > 0]
    print(f"  {tk}: ultimo EPS={eps_rows[0][1] if eps_rows else 'N/A'}  |  positivos recientes={len(pos_eps)}: {pos_eps[:3]}")

# 3. Stale: hay periodos mas recientes que no pasaron el filtro Assets?
print("\n=== Desactualizados: todos los period_end disponibles ===")
for tk in ('BPAT', 'CECO2', 'CGPA2', 'PATA_2', 'TGNO4'):
    cur.execute("SELECT cuit FROM mapa_entidades WHERE ticker=? AND es_primario=1", (tk,))
    r = cur.fetchone()
    if not r: continue
    cuit = r[0]
    cur.execute("""
        SELECT DISTINCT period_end FROM cnv_estados_norm
        WHERE cuit=? AND concepto='Assets'
        ORDER BY period_end DESC
        LIMIT 10
    """, (cuit,))
    pes = [r[0] for r in cur.fetchall()]
    print(f"  {tk}: periodos_assets= {pes}")

# 4. no_significativo sin causa: DGCE, POLL
print("\n=== no_significativo: ROE, Equity, Revenue ===")
for tk in ('DGCE', 'POLL'):
    cur.execute("SELECT s.cuit, s.ROE, s.MargenNeto, s.PriceBook, s.PER, s.flag_no_significativo, s.dato_desactualizado FROM screener s JOIN mapa_entidades m ON m.cuit=s.cuit WHERE m.ticker=? AND m.es_primario=1", (tk,))
    r = cur.fetchone()
    if r:
        print(f"  {tk}: ROE={r[1]}  Margen={r[2]}  P/B={r[3]}  PER={r[4]}  no_sig={r[5]}  stale={r[6]}")
        # Check Equity and Revenue
        cur.execute("SELECT concepto, valor, period_end FROM cnv_estados_norm WHERE cuit=? AND concepto IN ('Equity', 'Revenue', 'NetIncome') AND period_end=(SELECT MAX(period_end) FROM cnv_estados_norm WHERE cuit=? AND concepto='Assets' AND valor>0) ORDER BY concepto", (r[0], r[0]))
        for cr in cur.fetchall():
            print(f"    {cr[0]:12s} = {cr[1]}  ({cr[2]})")

con.close()
