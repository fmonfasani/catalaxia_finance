# -*- coding: utf-8 -*-
"""
SCRIPT 2 · ACTUALIZAR — baja los tres dólares (CCL, MEP, A3500) y los guarda en la tabla `dolares`
de screener.db, con fecha y fuente. Idempotente (INSERT OR REPLACE por fecha+tipo). Se corre
periódicamente (cron/diario) para mantener la serie al día.
   python scripts/dolares/actualizar_dolares.py
El CCL queda como el de referencia (es el que usa el proyecto para ARS→USD).
"""
import os, sys, sqlite3, datetime
import os as _os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _dolar import tres_dolares

PROD = os.path.join("data", _os.environ.get("SCREENER_DB", "screener.db"))
hoy = datetime.date.today().isoformat()
ts = datetime.datetime.now().isoformat(timespec='seconds')

REFERENCIA = 'mep'                      # el MEP es el dólar de referencia del proyecto
d = tres_dolares()
c = sqlite3.connect(PROD)
cols = [r[1] for r in c.execute("PRAGMA table_info(dolares)")]
if cols and 'cruce' not in cols:
    c.execute("DROP TABLE dolares")            # migración: esquema viejo (compra/venta) → recrear
c.execute("""CREATE TABLE IF NOT EXISTS dolares(
    fecha TEXT, tipo TEXT, valor REAL, cruce REAL, fuente TEXT, es_referencia INT, ts TEXT,
    UNIQUE(fecha, tipo))""")
n = 0
for tipo, info in d.items():
    if info.get('valor') is None:
        print(f'  ⚠ {tipo}: sin dato (fuente no respondió) — no se guarda (flag > inventar)'); continue
    c.execute("INSERT OR REPLACE INTO dolares(fecha,tipo,valor,cruce,fuente,es_referencia,ts) VALUES(?,?,?,?,?,?,?)",
              (hoy, tipo, info['valor'], info.get('cruce'), info['fuente'], 1 if tipo == REFERENCIA else 0, ts))
    n += 1
c.commit()

print(f'[dolares] {hoy}: guardados {n}/3 en tabla `dolares` (referencia = {REFERENCIA.upper()})')
for tipo, valor, cruce, fuente, ref in c.execute(
        "SELECT tipo,valor,cruce,fuente,es_referencia FROM dolares WHERE fecha=? ORDER BY es_referencia DESC, tipo", (hoy,)):
    cr = f' · cruce {cruce:,.1f}' if cruce else ''
    print(f'   {tipo.upper():<6} {valor:>10,.2f}   [{fuente}]{cr}{"  ← REFERENCIA" if ref else ""}')
# aviso si la referencia (MEP) se aleja de su cruce
mv, mc = d[REFERENCIA]['valor'], d[REFERENCIA].get('cruce')
if mv and mc and abs(mv - mc) / mc > 0.02:
    print(f'   ⚠ MEP primario ({mv:,.1f}) vs cruce ({mc:,.1f}) difieren >2% — revisar antes de usar')
c.close()
