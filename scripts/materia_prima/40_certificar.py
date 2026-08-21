# -*- coding: utf-8 -*-
"""
FASE 4: CERTIFICACIÓN
Resume los 9 cruces → nivel CERTIFICADO / cierre-interno / REVISAR

Regla:
  CERTIFICADO = Capa 1 (identidades) + Capa 2 (continuidad) + al menos una de (3 o 4)
  cierre-interno = Capa 1 + Capa 2, pero falla Capa 3 y 4
  REVISAR = falla Capa 1 o 2
"""
import sqlite3
import os as _os
import os
import datetime

PROD = os.path.join("data", _os.environ.get("SCREENER_DB", "screener.db"))

def certificar():
    """Calcula nivel de certificación por período"""

    print("=" * 80)
    print("FASE 4: CERTIFICACIÓN")
    print("=" * 80)

    c = sqlite3.connect(PROD)

    ticker = 'TXAR'
    periodos = sorted(set([r[0] for r in c.execute(
        "SELECT DISTINCT period_end FROM validaciones WHERE ticker=?", (ticker,))]))

    print(f"\nCertificando {len(periodos)} períodos...")

    certificados = 0
    cierre_interno = 0
    revisar = 0

    for period in periodos:
        # Contar OK por capa
        capa1_ok = c.execute("""
            SELECT COUNT(*) FROM validaciones
            WHERE ticker=? AND period_end=? AND cruce_id IN (1,9) AND resultado='OK'
        """, (ticker, period)).fetchone()[0]

        capa2_ok = c.execute("""
            SELECT COUNT(*) FROM validaciones
            WHERE ticker=? AND period_end=? AND cruce_id=2 AND resultado='OK'
        """, (ticker, period)).fetchone()[0]

        capa3_ok = c.execute("""
            SELECT COUNT(*) FROM validaciones
            WHERE ticker=? AND period_end=? AND cruce_id=3 AND resultado='OK'
        """, (ticker, period)).fetchone()[0]

        capa4_ok = c.execute("""
            SELECT COUNT(*) FROM validaciones
            WHERE ticker=? AND period_end=? AND cruce_id=4 AND resultado='OK'
        """, (ticker, period)).fetchone()[0]

        # Lógica de certificación
        identidades_ok = 1 if capa1_ok >= 1 else 0
        continuidad_ok = 1 if capa2_ok >= 1 else 0
        ancla_ok = 1 if (capa3_ok or capa4_ok) else 0

        if identidades_ok and continuidad_ok and ancla_ok:
            nivel = 'CERTIFICADO'
            causa = None
            certificados += 1
        elif identidades_ok and continuidad_ok:
            nivel = 'cierre-interno'
            causa = 'faltan anclas externas (investing/mercado)'
            cierre_interno += 1
        else:
            nivel = 'REVISAR'
            causa = 'fallan identidades o continuidad'
            revisar += 1

        # Guardar certificación
        c.execute("""
            INSERT OR REPLACE INTO certificacion_nueva
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            ticker, period,
            identidades_ok,
            f'Capa1 (A=P+PN, P&L): {capa1_ok} OK',
            continuidad_ok,
            f'Capa2 (YTD continuidad): {capa2_ok} OK',
            capa3_ok,
            1.0 if capa3_ok else None,  # ratio
            capa4_ok,
            0,  # ps_ok (no calculado aún)
            None, None,  # P/B, P/S ratios
            nivel,
            causa,
            datetime.datetime.now().isoformat()
        ))

    c.commit()

    # Resumen
    total = certificados + cierre_interno + revisar

    print(f"\n{'RESULTADO FINAL':^80}")
    print("=" * 80)
    print(f"  ✅ CERTIFICADO:     {certificados}/{total} ({certificados*100//total if total else 0}%)")
    print(f"  🟡 cierre-interno:  {cierre_interno}/{total}")
    print(f"  ⚠️  REVISAR:         {revisar}/{total}")
    print("=" * 80)

    # Mostrar cuál es cuál
    if revisar > 0:
        print(f"\nPeríodos REVISAR:")
        rows = c.execute("""
            SELECT period_end, causa_falla FROM certificacion_nueva
            WHERE ticker=? AND nivel_certificacion='REVISAR'
            ORDER BY period_end
        """, (ticker,)).fetchall()
        for period, causa in rows:
            print(f"  · {period}: {causa}")

    c.close()

    print("\n" + "=" * 80)
    print("✅ FASE 4 COMPLETADA: Certificación asignada")
    print("=" * 80)

if __name__ == '__main__':
    certificar()
