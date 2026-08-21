# -*- coding: utf-8 -*-
"""
Precondiciones entre etapas del pipeline
=========================================
El pipeline es una secuencia: `s4` crea `screener` con sus columnas base y cada
etapa posterior añade las suyas con `ALTER TABLE ADD COLUMN`. Eso está bien -- el
orden es información sobre cómo se construyen los datos, no deuda técnica.

El problema es que ese orden estaba **implícito**. Si alguien corre `s8` sobre una
base donde `s6` no pasó, el fallo es `IndexError: No item with that key` al leer
`row["fuente_fund"]`: un error que no dice qué falta ni qué hacer.

Estas funciones lo convierten en una instrucción. No cambian ningún dato.
"""
from __future__ import annotations
import sys


def requiere_columnas(cur, tabla, columnas, etapa_previa):
    """Aborta con un mensaje util si a `tabla` le faltan columnas.

    Uso:
        requiere_columnas(cur, "screener", ["fuente_fund", "sector"], "s6_ajustes")
    """
    cur.execute(f"PRAGMA table_info({tabla})")
    presentes = {r[1] for r in cur.fetchall()}
    if not presentes:
        sys.exit(f"\n  ERROR: la tabla `{tabla}` no existe.\n"
                 f"  Corré {etapa_previa} primero.\n")
    faltan = [c for c in columnas if c not in presentes]
    if faltan:
        sys.exit(f"\n  ERROR: a `{tabla}` le faltan columnas: {', '.join(faltan)}\n"
                 f"  Las crea {etapa_previa}. Corré esa etapa primero.\n"
                 f"  (el pipeline completo: python scripts/tickets/screener/run_all.py)\n")


def requiere_filas(cur, tabla, minimo, etapa_previa):
    """Aborta si `tabla` esta vacia o por debajo de un minimo esperado."""
    try:
        cur.execute(f"SELECT COUNT(*) FROM {tabla}")
        n = cur.fetchone()[0]
    except Exception:
        sys.exit(f"\n  ERROR: no se pudo leer `{tabla}`. Corré {etapa_previa} primero.\n")
    if n < minimo:
        sys.exit(f"\n  ERROR: `{tabla}` tiene {n} filas, se esperaban al menos {minimo}.\n"
                 f"  Corré {etapa_previa} primero.\n")
