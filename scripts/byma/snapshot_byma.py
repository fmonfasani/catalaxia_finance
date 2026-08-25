"""
E1 — Snapshot verificable del estado BYMA en screener.db.

Hace:
  1. Copia física consistente (sqlite3 backup API) de data/screener.db
     a data/backups/snapshot_byma_<fecha>.db
  2. Calcula SHA256 de origen y destino y los verifica.
  3. Ejecuta queries baseline del estado BYMA y las guarda en JSON.
  4. Registra la operación en tabla _snap_log (única escritura en producción).

NO modifica datos de producción.
"""
import hashlib
import json
import os
import sqlite3
from datetime import datetime

BASE = r'D:\Software Development\Porfolio\catalaxia-cedears-prod'
SRC = os.path.join(BASE, 'data', 'screener.db')
BACKUP_DIR = os.path.join(BASE, 'data', 'backups')
STAMP = datetime.now().strftime('%Y%m%d_%H%M%S')
DST = os.path.join(BACKUP_DIR, f'snapshot_byma_{STAMP}.db')
JSON_OUT = os.path.join(BACKUP_DIR, f'snapshot_byma_baseline_{STAMP}.json')


def sha256(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def backup_consistente(src, dst):
    src_con = sqlite3.connect(src)
    dst_con = sqlite3.connect(dst)
    with dst_con:
        src_con.backup(dst_con)
    n_pages_ok = dst_con.execute('PRAGMA integrity_check').fetchone()[0]
    dst_con.close()
    src_con.close()
    return n_pages_ok


def verificacion_logica(src, dst):
    """La copia no es byte-identica (el header de SQLite cambia el contador de
    transacciones al escribir). La equivalencia correcta es LOGICA:
    integridad ok en ambas + mismos conteos por tabla + mismo esquema."""
    a, b = sqlite3.connect(src), sqlite3.connect(dst)
    res = {}
    res['integridad_src'] = a.execute('PRAGMA integrity_check').fetchone()[0]
    res['integridad_dst'] = b.execute('PRAGMA integrity_check').fetchone()[0]
    tablas_a = [r[0] for r in a.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    tablas_b = [r[0] for r in b.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    res['mismo_esquema_tablas'] = tablas_a == tablas_b
    schema_a = hashlib.sha256(str(a.execute(
        "SELECT type,name,sql FROM sqlite_master ORDER BY type,name").fetchall()).encode()).hexdigest()
    schema_b = hashlib.sha256(str(b.execute(
        "SELECT type,name,sql FROM sqlite_master ORDER BY type,name").fetchall()).encode()).hexdigest()
    res['schema_hash_match'] = schema_a == schema_b
    diffs = []
    for t in tablas_a:
        na = a.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
        nb = b.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
        if na != nb:
            diffs.append(f'{t}: {na} vs {nb}')
    res['conteos_difieren'] = diffs
    res['tablas_verificadas'] = len(tablas_a)
    a.close()
    b.close()
    res['ok'] = (res['integridad_src'] == 'ok'
                 and res['integridad_dst'] == 'ok'
                 and res['mismo_esquema_tablas']
                 and res['schema_hash_match']
                 and not diffs)
    return res


def baseline(cur):
    out = {}
    out['universo'] = {
        'empresas_byma_yf': cur.execute(
            "SELECT COUNT(*) FROM empresas WHERE grupo='byma_yf'").fetchone()[0],
        'screener_byma_only': cur.execute(
            "SELECT COUNT(*) FROM screener WHERE grupo='byma_only'").fetchone()[0],
        'cnv_norm_cuits': cur.execute(
            "SELECT COUNT(DISTINCT cuit) FROM cnv_estados_norm WHERE cuit IS NOT NULL").fetchone()[0],
        'ratios_cnv_cuits': cur.execute(
            "SELECT COUNT(DISTINCT cuit) FROM ratios_cnv WHERE cuit IS NOT NULL").fetchone()[0],
        'mapa_entidades': cur.execute('SELECT COUNT(*) FROM mapa_entidades').fetchone()[0],
    }
    out['cnv_frescura'] = {
        str(mx): n for mx, n in cur.execute("""
            SELECT mx, COUNT(*) FROM (
              SELECT cuit, MAX(period_end) AS mx FROM cnv_estados_norm GROUP BY cuit)
            GROUP BY mx ORDER BY mx DESC""")}
    cols = [c[1] for c in cur.execute('PRAGMA table_info(ratios_cnv)').fetchall()]
    skip = ('cuit', 'ticker', 'ultimo_periodo')
    out['ratios_cnv_cobertura'] = {
        c: cur.execute(f'SELECT COUNT({c}) FROM ratios_cnv').fetchone()[0]
        for c in cols if c not in skip}
    scols = [c[1] for c in cur.execute('PRAGMA table_info(screener)').fetchall()]
    sskip = ('cuit', 'ticker', 'ultimo_periodo', 'grupo')
    out['screener_byma_fillrate'] = {}
    for c in scols:
        if c in sskip:
            continue
        nn = cur.execute(
            "SELECT COUNT(%s) FROM screener WHERE grupo='byma_only' AND %s IS NOT NULL" % (c, c)).fetchone()[0]
        if nn:
            out['screener_byma_fillrate'][c] = nn
    out['precios_byma'] = [
        {'moneda': r[0], 'filas': r[1], 'max_fecha': r[2]}
        for r in cur.execute("""
            SELECT p.currency, COUNT(*), MAX(p.fecha)
            FROM precios p JOIN empresas e ON e.cik=p.cik
            WHERE e.grupo='byma_yf' GROUP BY p.currency""")]
    out['dolares'] = [
        {'tipo': r[0], 'hasta': r[1]} for r in
        cur.execute('SELECT tipo, MAX(fecha) FROM dolares GROUP BY tipo')]
    out['ratios_ttm'] = {
        'filas': cur.execute('SELECT COUNT(*) FROM ratios_ttm').fetchone()[0],
        'interinos': cur.execute('SELECT COUNT(*) FROM ratios_ttm WHERE interino=1').fetchone()[0],
        'built_at_max': cur.execute('SELECT MAX(built_at) FROM ratios_ttm').fetchone()[0],
    }
    return out


def main():
    t0 = datetime.now()
    print(f'[1/5] Copia consistente -> {os.path.basename(DST)}')
    integridad = backup_consistente(SRC, DST)

    print('[2/5] SHA256 del snapshot (evidencia antimanipulacion futura)')
    sha_dst = sha256(DST)
    print(f'      snapshot={sha_dst[:16]}...')
    print('      (nota: SHA del origen NO se compara por bytes; el header de SQLite')
    print('       cambia el contador de transacciones al copiar)')

    print('[3/5] Verificacion logica src vs dst')
    ver = verificacion_logica(SRC, DST)
    ok = ver['ok']
    print(f'      integridad src/dst: {ver["integridad_src"]}/{ver["integridad_dst"]}')
    print(f'      esquema match={ver["mismo_esquema_tablas"]} hash={ver["schema_hash_match"]}')
    print(f'      tablas verificadas={ver["tablas_verificadas"]} diferencias={ver["conteos_difieren"] or "ninguna"}')

    print('[4/5] Queries baseline')
    con = sqlite3.connect(SRC)
    cur = con.cursor()
    bl = baseline(cur)

    print('[5/5] Registro en _snap_log')
    cur.execute("""CREATE TABLE IF NOT EXISTS _snap_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT, snapshot_path TEXT, sha256_snapshot TEXT,
        verificado INTEGER, detalle_verificacion TEXT, baseline_json TEXT)""")
    cols_existentes = {c[1] for c in cur.execute('PRAGMA table_info(_snap_log)').fetchall()}
    for col_def in ('sha256_snapshot TEXT', 'verificado INTEGER',
                    'detalle_verificacion TEXT'):
        col = col_def.split()[0]
        if col not in cols_existentes:
            cur.execute(f'ALTER TABLE _snap_log ADD COLUMN {col_def}')
    cur.execute(
        'INSERT INTO _snap_log (ts, snapshot_path, sha256_snapshot, verificado, detalle_verificacion, baseline_json) '
        'VALUES (?,?,?,?,?,?)',
        (t0.isoformat(), DST, sha_dst, int(ok), json.dumps(ver), JSON_OUT))
    con.commit()

    payload = {
        'generado': t0.isoformat(),
        'snapshot_path': DST,
        'sha256_snapshot': sha_dst,
        'verificacion_logica': ver,
        'integridad_sqlite': integridad,
        'baseline': bl,
    }
    with open(JSON_OUT, 'w', encoding='utf-8') as f:
        json.dump(payload, f, indent=2, ensure_ascii=False, default=str)
    con.close()

    print()
    print('RESUMEN E1:')
    print(f'  snapshot: {DST} ({os.path.getsize(DST)/1e6:.1f} MB)')
    print(f'  baseline: {JSON_OUT}')
    print(f'  verificado={ok}')
    print(f'  universo byma: {bl["universo"]}')
    if not ok:
        raise SystemExit('FALLO: snapshot no verificado logicamente')
    print('E1 OK - snapshot certificado')


if __name__ == '__main__':
    main()
