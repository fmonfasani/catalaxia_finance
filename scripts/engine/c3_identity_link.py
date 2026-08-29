#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CNV -> Identity v1 · primer test de integracion transversal.

QUE PREGUNTA RESPONDE
---------------------
Dado lo que Identity v1 sabe HOY, ¿a que entidad certificada pertenece cada
presentacion de la CNV, y por que identificador?

POR QUE ESTE ES EL PRIMER CRUCE
-------------------------------
`fetch_raw.cnv_presentation.entity_key` guarda `'CIK:0001717161'`: una clave
DERIVADA del CIK. Es exactamente el acoplamiento que Identity v1 existe para
romper (D-I-B: la clave es opaca, no se deriva de ningun identificador). Si el
CIK de esa empresa resultara mal atribuido, hoy habria que reescribir cada fila
de CNV; con `entity_key` opaco, corregirlo es una assertion nueva.

QUE NO HACE
-----------
  * NO inventa ni ratifica CUIT. Si la cadena hacia el CUIT no esta demostrada,
    lo dice y sigue.
  * NO escribe nada autoritativo. Con `--vincular` registra el vinculo como
    CANDIDATE, con fuente y cita, y el `LEGACY_ENTITY_ID` correspondiente
    —que por CHECK jamas puede ser autoritativo.
  * NO modifica CNV. Solo lee `fetch_raw.cnv_presentation`.

Uso:
    python scripts/engine/c3_identity_link.py              # informe, no escribe
    python scripts/engine/c3_identity_link.py --vincular   # registra CANDIDATE
"""
from __future__ import annotations

import argparse
import io
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy import text  # noqa: E402

from engine.config import load_settings  # noqa: E402
from engine.db import get_engine  # noqa: E402
from engine import identity_v1 as idv  # noqa: E402
from engine.identity_v1 import Evidence  # noqa: E402

RE_CIK_EN_CLAVE_LEGACY = re.compile(r"CIK[:\-]?(\d{6,10})")


def poblacion_cnv(conn) -> list[dict]:
    return [dict(r) for r in conn.execute(text(
        """
        SELECT cuit,
               min(entity_key)            AS entity_key_legacy,
               count(*)                   AS presentaciones,
               min(fecha_publicacion)     AS desde,
               max(fecha_publicacion)     AS hasta,
               count(DISTINCT clase)      AS clases
          FROM fetch_raw.cnv_presentation
         GROUP BY cuit
         ORDER BY count(*) DESC
        """)).mappings()]


def resolver(conn, fila: dict) -> dict:
    """Intenta atribuir un CUIT de CNV a una entidad de Identity v1.

    Se prueban las vias en orden de fuerza decreciente y se registra CUAL
    funciono. Una via debil que resuelve no se disfraza de fuerte.
    """
    cuit = fila["cuit"]
    r = {"cuit": cuit, "via": None, "entity_key": None, "detalle": ""}

    # via 1 — el CUIT es un identificador AUTORITATIVO vigente en Identity v1
    ek = idv.entity_of(conn, "CUIT", "AFIP", cuit)
    if ek:
        r.update(via="CUIT_AUTORITATIVO", entity_key=ek,
                 detalle="el CUIT bajo el que CNV publica es autoritativo en Identity v1")
        return r

    # via 1b — el CUIT existe pero esta RETIRADO (cadena no demostrada)
    ret = conn.execute(text(
        "SELECT entity_key, status FROM identity_v1.identifier "
        " WHERE id_type='CUIT' AND id_value=:v AND valid_to IS NOT NULL "
        " ORDER BY valid_to DESC LIMIT 1"), {"v": cuit}).first()

    # via 2 — el CIK embebido en la clave legacy de CNV
    m = RE_CIK_EN_CLAVE_LEGACY.search(fila["entity_key_legacy"] or "")
    if m:
        cik = m.group(1).zfill(10)
        ek = idv.entity_of(conn, "CIK", "SEC", cik)
        if ek:
            r.update(via="CIK_EN_CLAVE_LEGACY", entity_key=ek,
                     detalle=(f"la clave legacy de CNV '{fila['entity_key_legacy']}' embebe "
                              f"el CIK {cik}, que Identity v1 resuelve autoritativamente"))
            if ret:
                r["detalle"] += (f" · el CUIT {cuit} figura RETIRADO ({ret[1]}): "
                                 "la cadena CIK->LEI->CUIT no esta ratificada")
            return r

    if ret:
        r.update(via="SIN_RESOLVER", detalle=(
            f"el CUIT {cuit} existe en Identity v1 pero esta retirado ({ret[1]}): "
            "requiere ratificacion humana del puente CIK<->LEI"))
    else:
        r.update(via="SIN_RESOLVER",
                 detalle=f"Identity v1 no conoce el CUIT {cuit} por ninguna via")
    return r


def vincular(conn, fila: dict, res: dict) -> str:
    """Registra el vinculo como CANDIDATE, con procedencia. Nunca autoritativo."""
    if not res["entity_key"]:
        return "no se registra: sin entidad resuelta"

    ya = conn.execute(text(
        "SELECT 1 FROM identity_v1.identifier "
        " WHERE entity_key=:e AND id_type='CNV_ENTITY_ID' AND id_value=:v "
        "   AND valid_to IS NULL"), {"e": res["entity_key"], "v": fila["cuit"]}).scalar()
    if ya:
        return "ya vinculado (idempotente)"

    cita = (f"fetch_raw.cnv_presentation: {fila['presentaciones']} presentaciones "
            f"publicadas bajo CUIT {fila['cuit']} entre {fila['desde']} y {fila['hasta']} "
            f"({fila['clases']} clases). Atribucion por {res['via']}: {res['detalle']}")
    out = idv.assert_identifier(
        conn, entity_key=res["entity_key"], id_type="CNV_ENTITY_ID", id_namespace="CNV",
        id_value=fila["cuit"], method="CROSS_REFERENCE",
        evidence=Evidence("CNV_PORTAL", f"cnv:emisor/{fila['cuit']}", cita,
                          "proc:c3_identity_link"))
    return f"{out.status} (assertion {out.assertion_id})"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vincular", action="store_true",
                    help="registrar el vinculo como CANDIDATE (por defecto solo informa)")
    args = ap.parse_args()

    s = load_settings()
    if s.is_prod:
        print("EXT-010: abortado.")
        return 2
    eng = get_engine(s)

    print(f"CNV -> Identity v1 · {s.describe()}")
    print(f"modo: {'VINCULAR (escribe CANDIDATE)' if args.vincular else 'INFORME (no escribe)'}\n")

    with eng.begin() as conn:
        filas = poblacion_cnv(conn)
        if not filas:
            print("No hay presentaciones CNV materializadas. Nada que cruzar.")
            return 0

        total = sum(f["presentaciones"] for f in filas)
        print("=" * 78)
        print(f"POBLACION CNV: {len(filas)} emisor(es), {total} presentaciones")
        print("=" * 78)

        resueltas = 0
        por_via: dict[str, int] = {}
        for f in filas:
            r = resolver(conn, f)
            por_via[r["via"]] = por_via.get(r["via"], 0) + 1
            marca = "OK " if r["entity_key"] else "-- "
            print(f"\n[{marca}] CUIT {f['cuit']} · {f['presentaciones']} presentaciones "
                  f"({f['desde']} → {f['hasta']})")
            print(f"       clave legacy CNV : {f['entity_key_legacy']}")
            print(f"       via              : {r['via']}")
            if r["entity_key"]:
                resueltas += f["presentaciones"]
                nombre = conn.execute(text(
                    "SELECT preferred_name FROM identity_v1.entity WHERE entity_key=:k"),
                    {"k": r["entity_key"]}).scalar()
                print(f"       entity_key       : {r['entity_key']}  ({nombre})")
            print(f"       {r['detalle']}")
            if args.vincular:
                print(f"       vinculo          : {vincular(conn, f, r)}")

        print("\n" + "=" * 78)
        print("COBERTURA")
        print("=" * 78)
        pct = 100.0 * resueltas / total if total else 0
        print(f"   presentaciones atribuidas a una entidad certificada: "
              f"{resueltas}/{total} ({pct:.1f} %)")
        for via, n in sorted(por_via.items()):
            print(f"   {via:<22} {n} emisor(es)")

        print("\nLO QUE ESTE CRUCE DEMUESTRA Y LO QUE NO")
        if por_via.get("CUIT_AUTORITATIVO"):
            print("   · hay emisores atribuidos por CUIT autoritativo: cadena completa")
        if por_via.get("CIK_EN_CLAVE_LEGACY"):
            print("   · hay emisores atribuidos por el CIK embebido en la clave legacy.")
            print("     Es una atribucion VALIDA y trazable, pero NO demuestra el CUIT:")
            print("     el CUIT sigue esperando ratificacion humana del puente CIK<->LEI.")
        if por_via.get("SIN_RESOLVER"):
            print("   · hay emisores que Identity v1 no puede atribuir. Quedan sin vincular;")
            print("     no se les inventa una entidad.")
    return 0


if __name__ == "__main__":
    # solo al ejecutarse como script: importar no debe tocar sys.stdout
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")
    raise SystemExit(main())
