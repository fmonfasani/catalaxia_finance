#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F-061 — el unico punto por el que un ratio consigue sus insumos.

POR QUE EXISTE ESTE MODULO
`screener_demo.py`, `matriz_producto.py`, `e2e_producto.py` y
`ratios_inventario.py` traian sus insumos cada uno con su propio
`SELECT ... FROM derived.fact WHERE cik = :c`. Cuatro copias de la misma
consulta y, por lo tanto, cuatro copias del mismo agujero: la identidad, que
llegaba como `entity_key` respaldado por una assertion, degradaba a una
igualdad de texto sobre una columna que cualquier escritura puede fijar.

Ahora la clausula vive UNA vez, aca. Los cuatro modulos arman su lista de
columnas y el WHERE lo pone `sql_insumos()`. Quitar la guarda exige editar este
archivo, y hay un test de mutacion que lo detecta.

LA GARANTIA
Todo `fact_id` de `derived.fact.source_fact_ids` debe resolver a una fila de
`parsed.facts` del MISMO emisor, del MISMO filing y del MISMO concepto.

No usa ticker, ni nombre, ni empresa hardcodeada, ni heuristica, ni desempate
arbitrario: usa la relacion de provenance que la ingesta ya deja escrita.

Ver `outputs/docs/fase_ratios/F061_ROOT_CAUSE.md`.
"""
from __future__ import annotations

# ── EL INVARIANTE ────────────────────────────────────────────────────────────
# Cuenta punteros ajenos. La migracion 032 declara la vista equivalente
# `derived.v_fact_pertenencia`; esta version parametrizada existe para que los
# tests puedan correrla sobre un schema temporal.
INVARIANTE_PERTENENCIA = """
SELECT count(*)
  FROM {derived} d
  CROSS JOIN LATERAL unnest(d.source_fact_ids) AS s(fid)
  LEFT JOIN {parsed} p ON p.fact_id = s.fid
 WHERE d.valid_to IS NULL
   AND (p.fact_id IS NULL
     OR p.cik <> d.cik
     OR p.accession_number <> d.accession_number
     OR p.qname <> d.qname)
"""

# ── LA GUARDA ────────────────────────────────────────────────────────────────
# `NOT EXISTS` sobre el unnest dice, literalmente: ningun puntero de esta fila
# es ajeno. Una fila sin punteros no puede existir -- `source_fact_ids` es NOT
# NULL en el schema -- y si existiera, un array vacio hace que el NOT EXISTS sea
# verdadero; por eso la condicion de no-vacio va aparte y explicita.
GUARDA_PERTENENCIA = """
   AND array_length({alias}.source_fact_ids, 1) > 0
   AND NOT EXISTS (
         SELECT 1
           FROM unnest({alias}.source_fact_ids) AS gs(fid)
           LEFT JOIN {parsed} gp ON gp.fact_id = gs.fid
          WHERE gp.fact_id IS NULL
             OR gp.cik <> {alias}.cik
             OR gp.accession_number <> {alias}.accession_number
             OR gp.qname <> {alias}.qname)
"""

# Filtros que definen "el hecho principal del periodo": numerico, no
# dimensional, con valor, y cuya fecha es la del cierre que declara. El ultimo
# es el que excluye los comparativos de ejercicios anteriores que vienen en el
# mismo filing.
FILTROS_BASE = """
     {alias}.valid_to IS NULL
   AND {alias}.cik = :c
   AND {alias}.is_numeric
   AND NOT {alias}.is_dimensional
   AND {alias}.value_numeric IS NOT NULL
   AND COALESCE({alias}.instant_date::text, {alias}.end_date::text)
       = {alias}.report_period::text
"""


def sql_insumos(columnas: str, *, alias: str = "d",
                derived: str = "derived.fact",
                parsed: str = "parsed.facts",
                extra: str = "") -> str:
    """La consulta canonica de insumos. Nadie mas arma este WHERE.

    `columnas` se pasa ya calificada con el alias (por ejemplo ``d.tag``).
    `derived` y `parsed` son parametrizables SOLO para los tests, que corren
    sobre un schema temporal; en produccion se usan los valores por defecto.
    """
    return (f"SELECT {columnas}\n"
            f"  FROM {derived} {alias}\n"
            f" WHERE {FILTROS_BASE.format(alias=alias)}"
            f"{GUARDA_PERTENENCIA.format(alias=alias, parsed=parsed)}"
            f"{extra}")


def violaciones_pertenencia(conn, derived: str = "derived.fact",
                            parsed: str = "parsed.facts") -> int:
    """Cuantos punteros de provenance son ajenos. Debe ser 0 siempre."""
    from sqlalchemy import text
    return conn.execute(text(INVARIANTE_PERTENENCIA.format(
        derived=derived, parsed=parsed))).scalar_one()
