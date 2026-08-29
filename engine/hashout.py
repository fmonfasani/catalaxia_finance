"""`hash_out` v2 — digest determinista basado en CONTENIDO.

Contrato: docs/architecture/HASH_OUT_CONTRACT.md

POR QUE EXISTE (F-029)
----------------------
`hashout-v1` era `sha256(json({facts, contexts, units, concepts, relations}))`:
cinco CANTIDADES DE FILAS. Tres corridas de S03 con contenido distinto —una de
ellas la que corrigio el parser de unidades y cambio 44 unidades y 436 facts—
declararon el MISMO hash_out. Un checkpoint que no distingue contenido no sirve
para detectar regresiones del parser, que es justo para lo que se lo usa.

LAS TRES PROPIEDADES, y como se obtienen
----------------------------------------
  P1 sensible al contenido   los campos semanticos entran al digest de fila
  P2 insensible al orden     los hashes de fila se ORDENAN antes de agregar
  P3 reconstruible           todo sale de la base; un tercero lo recalcula

P2 no es comodidad: Postgres no garantiza orden sin ORDER BY, y un digest
sensible al orden daria falsos positivos en cada corrida hasta volverse ruido.
"""
from __future__ import annotations

import hashlib
import json
from decimal import Decimal

from sqlalchemy import text

HASH_SPEC = "hashout-v2"

NULO = chr(0) + "NULL"   # centinela imposible en texto: distingue NULL de cadena vacia


def _campo(v) -> str:
    """Serializa un valor para el digest de fila.

    Los NUMERIC se serializan con su TEXTO, no como float: `0.30` y `0.3000`
    son declaraciones distintas y deben producir hashes distintos (misma razon
    que el desempate por precision de S04).
    """
    if v is None:
        return NULO
    if isinstance(v, Decimal):
        return str(v)
    if isinstance(v, bool):
        return "t" if v else "f"
    if isinstance(v, (dict, list)):
        return json.dumps(v, sort_keys=True, ensure_ascii=False, default=str)
    return str(v)


def hash_fila(valores) -> str:
    return hashlib.sha256("|".join(_campo(v) for v in valores).encode()).hexdigest()


def hash_conjunto(filas) -> str:
    """Agrega un conjunto de filas de forma CONMUTATIVA (P2).

    El sort de los hashes de fila es lo que hace que el resultado no dependa
    del orden en que la base devolvio las filas.
    """
    hs = sorted(hash_fila(f) for f in filas)
    return hashlib.sha256("".join(hs).encode()).hexdigest()


# ---------------------------------------------------------------------
# Campos semanticos por tabla. NO entran: run_id, created_at, updated_at,
# claves seriales (dependen del orden de insercion) ni rutas de archivo.
# ---------------------------------------------------------------------
CAMPOS = {
    "parsed.facts": (
        "accession_number, qname, context_id, unit_ref, value_text, value_numeric, "
        "is_numeric, is_nil, decimals, unit_type, measure, numerator, denominator, "
        "period_kind, start_date, end_date, instant_date"),
    "parsed.contexts": (
        "accession_number, context_id, period_kind, start_date, end_date, instant_date, "
        "dimensions, typed_dimensions, dim_count"),
    "parsed.units": (
        "accession_number, unit_ref, unit_type, measures, numerator, denominator"),
    "parsed.concepts": (
        "qname, namespace, tag, period_type, balance, abstract, is_custom, taxonomy"),
    "derived.fact": (
        "fact_key, entity_key, qname, context_id, unit_measure, currency, unidad_resuelta, "
        "value_text, value_numeric, is_nil, is_dimensional, period_kind, start_date, "
        "end_date, instant_date, desempate, n_fuentes"),
}

# voluminosa (146k) y su contenido no se publica hacia S04: entra solo por conteo
SOLO_CONTEO = ("parsed.link_relations",)


def digest_tabla(conn, tabla: str, filtro: str = "", params: dict | None = None) -> str:
    cols = CAMPOS[tabla]
    q = f"SELECT {cols} FROM {tabla}" + (f" WHERE {filtro}" if filtro else "")
    return hash_conjunto(conn.execute(text(q), params or {}).all())


def hash_out(conn, tablas: list[str], filtro: str = "", params: dict | None = None) -> dict:
    """Devuelve {'hash_out', 'hash_spec', 'por_tabla', 'conteos'}.

    Todo se lee de la base: un auditor recalcula esto sin correr el pipeline.
    """
    por_tabla, conteos = {}, {}
    for t in tablas:
        n = conn.execute(
            text(f"SELECT count(*) FROM {t}" + (f" WHERE {filtro}" if filtro else "")),
            params or {}).scalar()
        conteos[t] = n
        if t not in SOLO_CONTEO:
            por_tabla[t] = digest_tabla(conn, t, filtro, params)
    cuerpo = {"por_tabla": por_tabla, "_conteos": conteos}
    return {
        "hash_out": hashlib.sha256(
            json.dumps(cuerpo, sort_keys=True).encode()).hexdigest(),
        "hash_spec": HASH_SPEC,
        "por_tabla": por_tabla,
        "conteos": conteos,
    }
