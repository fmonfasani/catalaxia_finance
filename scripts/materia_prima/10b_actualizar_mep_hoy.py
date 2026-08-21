# -*- coding: utf-8 -*-
"""
FASE 1.1b: Traer MEP HOY
Corre actualizar_dolares.py para traer MEP reciente.
Luego usa ese MEP como referencia para períodos cercanos.
"""
import sys
import os as _os
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'dolares'))

from _dolar import tres_dolares
import sqlite3
import datetime

PROD = os.path.join("data", _os.environ.get("SCREENER_DB", "screener.db"))

def actualizar_mep_hoy():
    """Trae MEP/CCL/A3500 de hoy, guarda en screener.db"""

    print("=" * 80)
    print("FASE 1.1b: ACTUALIZAR MEP HOY")
    print("=" * 80)

    # Traer tres dólares de referencia
    d = tres_dolares()

    print("\nTres dólares obtenidos:")
    for tipo, info in d.items():
        if info.get('valor'):
            cruce = f" (cruce {info.get('cruce', 'N/A')})" if info.get('cruce') else ""
            print(f"  {tipo.upper():<6} ${info['valor']:>8.2f}  [{info['fuente']}]{cruce}")
        else:
            print(f"  {tipo.upper():<6} SIN DATO")

    # Guardar en screener.db
    c = sqlite3.connect(PROD)
    hoy = datetime.date.today().isoformat()
    ts = datetime.datetime.now().isoformat(timespec='seconds')

    # Crear tabla si no existe
    c.execute("""CREATE TABLE IF NOT EXISTS dolares(
        fecha TEXT, tipo TEXT, valor REAL, cruce REAL, fuente TEXT, es_referencia INT, ts TEXT,
        UNIQUE(fecha, tipo))""")

    n = 0
    for tipo, info in d.items():
        if info.get('valor') is None:
            print(f"  ⚠️ {tipo}: sin dato, omitiendo")
            continue

        c.execute("""INSERT OR REPLACE INTO dolares(fecha,tipo,valor,cruce,fuente,es_referencia,ts)
                     VALUES(?,?,?,?,?,?,?)""",
                  (hoy, tipo, info['valor'], info.get('cruce'), info['fuente'],
                   1 if tipo == 'mep' else 0, ts))
        n += 1

    c.commit()
    c.close()

    print(f"\n✅ {n}/3 dólares guardados en screener.db para {hoy}")

    print("\n" + "=" * 80)
    print(f"MEP DE REFERENCIA HOY: ${d['mep']['valor']:.2f}")
    print("=" * 80)

    return d['mep']['valor'] if d['mep'].get('valor') else None

if __name__ == '__main__':
    mep = actualizar_mep_hoy()
