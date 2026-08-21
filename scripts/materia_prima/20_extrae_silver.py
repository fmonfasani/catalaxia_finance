# -*- coding: utf-8 -*-
"""
FASE 2: Extracción + Normalización
Lee demo.db:silver (TXAR 30 períodos) → screener.db:silver_norm
Con metadatos:
  · Moneda explícita (ARS)
  · Escala guardada (×1e6 millones)
  · RECPAM double variant (con/sin)
  · Vintage de reexpresión (inflación AR)
"""
import sqlite3
import os as _os
import os
import datetime

def extraer_silver():
    print("=" * 80)
    print("FASE 2: EXTRACCIÓN + NORMALIZACIÓN SILVER")
    print("=" * 80)

    demo = sqlite3.connect('data/demo.db')
    prod = sqlite3.connect(_os.path.join("data", _os.environ.get("SCREENER_DB", "screener.db")))

    ticker = 'TXAR'
    moneda = 'ARS'

    print(f"\nLeyendo {ticker} desde demo.db...")

    # Leer todos los conceptos + períodos
    # (demo.db silver no tiene ticker, solo TXAR por defecto)
    rows = demo.execute("""
        SELECT period_end, concepto, valor
        FROM silver
        ORDER BY period_end, concepto
    """).fetchall()

    print(f"  Encontrados: {len(rows)} registros")

    # Contabilidad Argentina:
    # - CNV siempre reporte en ARS
    # - Escala: millones (×1e6)
    # - RECPAM: aplicado en CNV (es parte del resultado reportado)

    n = 0
    for period_end, concepto, valor in rows:
        if valor is None:
            continue

        valor_original = valor
        escala = 1e6  # CNV siempre en millones
        factor_aplicado = 0
        incluye_recpam = 1  # CNV ya incluye RECPAM en el resultado
        vintage_reexpresion = period_end  # Para ahora, asumimos no hay reexpresión
        # TODO: leer fecha_reexpresion de tabla cierre si existe

        # Valores por defecto (se rellenan en Fase 3)
        cierre_ok = None
        continuidad_ok = None
        ancla_ok = None
        nivel_certificacion = 'PENDIENTE'
        detalle_falla = None

        prod.execute("""
            INSERT OR REPLACE INTO silver_norm
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            ticker, period_end, concepto,
            valor,  # valor normalizado (×1e6 ya aplicado en demo.db)
            valor_original,
            moneda,
            escala,
            factor_aplicado,
            incluye_recpam,
            vintage_reexpresion,
            cierre_ok,
            continuidad_ok,
            ancla_ok,
            nivel_certificacion,
            detalle_falla,
            datetime.datetime.now().isoformat()
        ))

        n += 1

    prod.commit()

    # Estadísticas
    periodos = set([r[0] for r in rows])
    conceptos = set([r[1] for r in rows])

    print(f"\n✅ Normalizados: {n} registros")
    print(f"   Períodos: {len(periodos)} (desde {min(periodos)} a {max(periodos)})")
    print(f"   Conceptos: {len(conceptos)}")
    print(f"   Moneda: {moneda}")
    print(f"   Escala: ×1e6 (millones)")

    demo.close()
    prod.close()

    print("\n" + "=" * 80)
    print("✅ FASE 2 COMPLETADA: Datos normalizados en silver_norm")
    print("=" * 80)

    return n

if __name__ == '__main__':
    extraer_silver()
