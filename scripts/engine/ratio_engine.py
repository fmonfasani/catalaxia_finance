#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Motor canonico de ratios (S1). Primer ratio: EV/Sales.

    python scripts/engine/ratio_engine.py            # calcula y muestra, NO escribe
    python scripts/engine/ratio_engine.py --persist  # calcula y persiste en derived.ratio

QUE IMPLEMENTA
Un solo ratio -- `ev_sales`, `formula_version = "ev_sales_v1"` -- sobre la
persistencia canonica `derived.ratio`. Se eligio EV/Sales porque sus cuatro
insumos ya se calculaban por separado en otras superficies y porque es el unico
multiplo de empresa que NO depende de resolver la cadena de D&A (decision D3,
todavia abierta). Ver RATIO_CONTRACT.md.

QUE NO IMPLEMENTA
Ningun otro ratio. No hay TTM: el motor no sabe sumar cuatro trimestres, asi que
`ev_sales` se emite con `period_window = 'FY'` de forma EXPLICITA. Emitirlo como
TTM seria mentir sobre el periodo, que es exactamente lo que el contrato viene a
cerrar (Regla 1).

GARANTIAS
  F-061  todo insumo pasa por `ratio_inputs.sql_insumos`, que exige que la
         provenance de cada hecho pertenezca al mismo emisor, filing y concepto.
  R2     precio y fundamentals DEBEN estar en la misma moneda. No se convierte.
  R6/R7  falta un insumo -> se persiste NOT_CALCULABLE con el motivo. El hueco
         se registra; no se omite la fila.
  R10    sin provenance completa no hay valor: `inputs` es NOT NULL y la fila
         guarda, por insumo, el tag elegido, la cadena evaluada, el fact_key,
         los source_fact_ids y el hash del archivo fuente.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
from decimal import Decimal
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from sqlalchemy import text  # noqa: E402

import engine.db as edb  # noqa: E402
from engine.config import load_settings  # noqa: E402
from engine.db import get_admin_engine  # noqa: E402

sys.path.insert(0, str(REPO / "scripts" / "engine"))
from ratio_defs import CONCEPTOS, elegir_concepto  # noqa: E402
from ratio_inputs import sql_insumos, violaciones_pertenencia  # noqa: E402

PIPELINE_VERSION = "ratio-engine-1.0"

# ── EL CONTRATO DE ESTE RATIO ────────────────────────────────────────────────
CANONICAL_ID = "ev_sales"
FORMULA_VERSION = "ev_sales_v1"

# Version de lo que la fila GUARDA como provenance, distinta de la version de
# formula. Cambiar la formula cambia el NUMERO; cambiar este esquema cambia la
# EVIDENCIA que lo acompana. Ambos casos deben producir una fila nueva y cerrar
# la anterior, nunca reescribirla, por eso participa de `ratio_key`.
#   prov_v1  un solo source_file/source_hash (el primero)
#   prov_v2  todos los origenes distintos: el 47% de derived.fact se apoya en
#            mas de una fila de parsed.facts y v1 dejaba fuera el resto
PROVENANCE_SCHEMA = "prov_v2"
FORMULA = "(market_cap + deuda_financiera - efectivo) / ingresos"
UNIT = "veces"
WINDOW = "FY"            # el motor no soporta TTM todavia; se declara, no se finge
DENOMINATOR_BASIS = "n/a"  # el denominador es de flujo

# Conceptos que consume, en el orden en que el contrato los declara. La cadena
# de fallback de cada uno vive en `ratio_defs.CONCEPTOS`: aca no se declara
# ningun tag.
CONCEPTOS_USADOS = ("ingresos", "deuda_financiera", "efectivo", "acciones_circulacion")

COLUMNAS = ("d.tag, d.report_period::text AS per, d.currency, d.value_numeric, "
            "d.accession_number, d.filing_date::text AS fdate, d.namespace, "
            "d.qname, d.unit_measure, d.source_fact_ids, d.fact_key")


def q(conn, sql, **kw):
    return conn.execute(text(sql), kw).mappings().all()


# ═══════════════════════════════════════════════════════════ identidad ══════

def resolver_entidad(conn, cik: str) -> dict | None:
    """entity_key desde el CIK, exigiendo assertion VERIFIED.

    No se usa ticker ni nombre. Si el CIK no resuelve a exactamente una entidad
    con assertion VERIFIED, no hay entidad y el ratio no se calcula.
    """
    filas = q(conn, """
        SELECT e.entity_key, e.preferred_name, a.status::text AS st
          FROM identity_v1.identifier i
          JOIN identity_v1.entity e ON e.entity_key = i.entity_key
          JOIN identity_v1.assertion a ON a.assertion_id = i.assertion_id
         WHERE i.id_type = 'CIK' AND i.id_value = :c AND i.valid_to IS NULL""", c=cik)
    if len(filas) != 1 or filas[0]["st"] != "VERIFIED":
        return None
    return dict(filas[0])


def precios_de(conn, entity_key: str) -> list[dict]:
    """Ultimo cierre de cada instrumento LIGADO a la entidad.

    El enlace es `identity_v1.instrument.instrument_key = 'MKT:<id>'`. No se
    resuelve por ticker: un ticker puede corresponder al local y al ADR.
    """
    return [dict(p) for p in q(conn, """
        SELECT p.instrument_id, p.trading_date::text AS d, p.close, p.currency,
               p.exchange, COALESCE(ii.ratio_underlying, 1) AS ratio_adr
          FROM identity_v1.instrument ii
          JOIN market_price_daily p
            ON p.instrument_id = replace(ii.instrument_key, 'MKT:', '')
          JOIN (SELECT instrument_id, max(trading_date) md
                  FROM market_price_daily GROUP BY 1) u
            ON u.instrument_id = p.instrument_id AND u.md = p.trading_date
         WHERE ii.entity_key = :ek AND ii.valid_to IS NULL
           AND ii.instrument_key LIKE 'MKT:%'""", ek=entity_key)]


# ═══════════════════════════════════════════════════════════ provenance ═════

def evidencia(conn, fact: dict) -> dict:
    """Cadena fact -> parsed.facts -> archivo RAW, con su hash.

    A diferencia de la version anterior de `evidencia_de`, esta SI trae el `cik`
    y el `accession_number` de la fila apuntada: son los campos que dicen de
    quien es el hecho. Sin ellos la provenance no se puede verificar, solo
    mostrar (esa fue la causa raiz de F-061).
    """
    ids = [int(i) for i in (fact.get("source_fact_ids") or [])]
    if not ids:
        return {"estado": "SIN_CADENA"}
    filas = q(conn, """
        SELECT fact_id, cik, accession_number, qname, source_file, source_path,
               source_hash
          FROM parsed.facts WHERE fact_id = ANY(:ids)""", ids=ids)
    if len(filas) != len(ids):
        return {"estado": "ROTA", "esperados": len(ids), "hallados": len(filas)}
    # 47% de `derived.fact` se apoya en MAS DE UNA fila de `parsed.facts`: el
    # mismo hecho aparece repetido en varios estados del mismo filing. Guardar
    # solo el primer archivo dejaria fuera la mitad de la evidencia, asi que se
    # guardan todos los origenes distintos. `parsed_cik` y `parsed_accession`
    # son escalares porque la guarda de pertenencia ya garantiza que son unicos.
    p = dict(filas[0])
    return {"estado": "COMPLETA",
            "n_fuentes": len(filas),
            "source_fact_ids": ids,
            "parsed_cik": p["cik"],
            "parsed_accession": p["accession_number"],
            "source_files": sorted({f["source_file"] for f in filas}),
            "source_paths": sorted({f["source_path"] for f in filas if f["source_path"]}),
            "source_hashes": sorted({f["source_hash"] for f in filas if f["source_hash"]})}


def insumo(conn, rol: str, concepto: str, tag: str, f: dict) -> dict:
    return {"rol": rol,
            "concepto": concepto,
            "tag_elegido": tag,
            "cadena_evaluada": CONCEPTOS[concepto],
            "qname": f["qname"],
            "namespace": f["namespace"],
            "valor": float(f["value_numeric"]),
            "moneda": f["currency"],
            "unit_measure": f["unit_measure"],
            "fact_key": f["fact_key"],
            "accession_number": f["accession_number"],
            "filing_date": f["fdate"],
            "evidencia": evidencia(conn, f)}


# ═══════════════════════════════════════════════════════════════ calculo ════

def calcular_ev_sales(conn, cik: str) -> dict:
    """EV/Sales del ultimo ejercicio del emisor. Nunca levanta: devuelve estado."""
    base = {"cik": cik, "canonical_id": CANONICAL_ID, "period_window": WINDOW,
            "denominator_basis": DENOMINATOR_BASIS, "unit": UNIT,
            "formula_version": FORMULA_VERSION, "formula": FORMULA}

    def no(motivo, **kw):
        return {**base, "status": "NOT_CALCULABLE", "value": None,
                "motivo": motivo, "inputs": kw.get("inputs", []),
                "period_end": kw.get("period_end"),
                "entity_key": kw.get("entity_key"), "currency": None}

    ent = resolver_entidad(conn, cik)
    if ent is None:
        return {**base, "status": "REVIEW_REQUIRED", "value": None,
                "motivo": f"el CIK {cik} no resuelve a una entidad con assertion VERIFIED",
                "inputs": [], "period_end": None, "entity_key": None, "currency": None}
    base["entity_key"] = ent["entity_key"]
    base["preferred_name"] = ent["preferred_name"]

    filas = q(conn, sql_insumos(COLUMNAS), c=cik)
    if not filas:
        return no("sin facts vigentes que pasen la guarda de pertenencia (F-061)",
                  entity_key=ent["entity_key"])

    porper: dict[str, dict] = {}
    for f in filas:
        porper.setdefault(f["per"], {})[f["tag"]] = dict(f)
    per = max(porper)
    disp = porper[per]
    base["period_end"] = per

    # --- los cuatro conceptos, por cadena de fallback ----------------------
    # Cuando falta uno, la fila NOT_CALCULABLE se queda con los que SI se
    # resolvieron: asi dice en que eslabon se corto, no solo que se corto.
    elegidos: dict[str, tuple[str, dict]] = {}
    for c in CONCEPTOS_USADOS:
        tag, f = elegir_concepto(disp, c)
        if f is None:
            parciales = [insumo(conn, k, k, *v) for k, v in elegidos.items()]
            return no(f"sin fact para el concepto '{c}' en {per}; "
                      f"candidatos consultados: {CONCEPTOS[c]}",
                      period_end=per, entity_key=ent["entity_key"],
                      inputs=parciales)
        elegidos[c] = (tag, f)

    # --- R2 · una sola moneda en los fundamentals -------------------------
    monedas = {f["currency"] for c, (_t, f) in elegidos.items()
               if c != "acciones_circulacion"}
    if len(monedas) != 1:
        return no(f"los fundamentals mezclan monedas {sorted(monedas)}; "
                  f"un ratio no mezcla monedas y no se convierte",
                  period_end=per, entity_key=ent["entity_key"])
    moneda = monedas.pop()
    base["currency"] = moneda

    # --- precio en ESA moneda ---------------------------------------------
    precios = precios_de(conn, ent["entity_key"])
    if not precios:
        return no("la entidad no tiene instrumento ligado en identity_v1.instrument: "
                  "atribuirle un precio seria un join por ticker",
                  period_end=per, entity_key=ent["entity_key"])
    p = next((x for x in precios if x["currency"] == moneda), None)
    if p is None:
        return no(f"fundamentals en {moneda} y no hay precio en esa moneda "
                  f"(disponibles: {sorted({x['currency'] for x in precios})})",
                  period_end=per, entity_key=ent["entity_key"])

    # --- las cuentas -------------------------------------------------------
    acciones = Decimal(str(elegidos["acciones_circulacion"][1]["value_numeric"]))
    if acciones <= 0:
        return no(f"acciones en circulacion = {acciones}",
                  period_end=per, entity_key=ent["entity_key"])
    ingresos = Decimal(str(elegidos["ingresos"][1]["value_numeric"]))
    if ingresos <= 0:
        return no(f"denominador ingresos = {ingresos}: no positivo",
                  period_end=per, entity_key=ent["entity_key"])

    deuda = Decimal(str(elegidos["deuda_financiera"][1]["value_numeric"]))
    caja = Decimal(str(elegidos["efectivo"][1]["value_numeric"]))
    ratio_adr = Decimal(str(p["ratio_adr"] or 1))
    market_cap = (Decimal(str(p["close"])) / ratio_adr) * acciones
    ev = market_cap + deuda - caja
    valor = ev / ingresos

    inputs = [insumo(conn, rol, c, *elegidos[c]) for rol, c in (
        ("ingresos", "ingresos"), ("deuda", "deuda_financiera"),
        ("efectivo", "efectivo"), ("acciones", "acciones_circulacion"))]
    inputs.append({"rol": "precio", "concepto": "precio_cierre",
                   "instrument_id": p["instrument_id"], "exchange": p["exchange"],
                   "trading_date": p["d"], "valor": float(p["close"]),
                   "moneda": p["currency"], "ratio_adr": float(ratio_adr),
                   "evidencia": {"estado": "COMPLETA", "fuente": "market_price_daily"}})
    inputs.append({"rol": "derivado", "concepto": "market_cap",
                   "valor": float(market_cap), "moneda": moneda,
                   "formula": "close / ratio_adr * acciones_circulacion"})
    inputs.append({"rol": "derivado", "concepto": "enterprise_value",
                   "valor": float(ev), "moneda": moneda,
                   "formula": "market_cap + deuda_financiera - efectivo"})

    return {**base, "status": "CALCULADO", "value": float(round(valor, 6)),
            "motivo": None, "inputs": inputs, "publicable": True,
            "market_cap": float(market_cap), "enterprise_value": float(ev)}


# ═══════════════════════════ los otros tres del vertical slice ═════════════
# Se agregan EPS, P/B y P/E porque el slice los exige. NINGUNO inventa periodo:
# los tres declaran su ventana real. P/E en particular es FY -- el EPS que usa
# es el del ultimo ejercicio anual, no una suma de cuatro trimestres -- y se
# publica diciendolo. Ver CATALAXIA_RATIO_PRODUCT.md.

SPECS = {
    "ev_sales": {"fv": "ev_sales_v1", "unit": "veces", "window": "FY",
                 "basis": "n/a", "formula": FORMULA},
    "eps":      {"fv": "eps_v1", "unit": "moneda_por_accion", "window": "FY",
                 "basis": "AVERAGE",
                 "formula": "EPS basico reportado por el emisor"},
    "pb":       {"fv": "pb_v1", "unit": "veces", "window": "PIT",
                 "basis": "CLOSING",
                 "formula": "(close / ratio_adr) / (patrimonio_controladora / acciones_circulacion)"},
    "pe":       {"fv": "pe_v1", "unit": "veces", "window": "FY",
                 "basis": "n/a",
                 "formula": "(close / ratio_adr) / eps_basico"},
}


def _base(cik: str, cid: str) -> dict:
    s = SPECS[cid]
    return {"cik": cik, "canonical_id": cid, "period_window": s["window"],
            "denominator_basis": s["basis"], "unit": s["unit"],
            "formula_version": s["fv"], "formula": s["formula"]}


def _contexto(conn, cik: str, cid: str):
    """(entidad, periodo, facts) o un estado terminal. Comun a los tres."""
    b = _base(cik, cid)
    ent = resolver_entidad(conn, cik)
    if ent is None:
        return None, {**b, "status": "REVIEW_REQUIRED", "value": None, "inputs": [],
                      "motivo": f"el CIK {cik} no resuelve a una entidad con "
                                f"assertion VERIFIED",
                      "period_end": None, "entity_key": None, "currency": None}
    b["entity_key"] = ent["entity_key"]
    b["preferred_name"] = ent["preferred_name"]
    filas = q(conn, sql_insumos(COLUMNAS), c=cik)
    if not filas:
        return None, {**b, "status": "NOT_CALCULABLE", "value": None, "inputs": [],
                      "motivo": "sin facts vigentes que pasen la guarda de "
                                "pertenencia (F-061)",
                      "period_end": None, "currency": None}
    porper: dict[str, dict] = {}
    for f in filas:
        porper.setdefault(f["per"], {})[f["tag"]] = dict(f)
    per = max(porper)
    b["period_end"] = per
    return (ent, per, porper[per]), b


def _no(b: dict, motivo: str, inputs=None) -> dict:
    return {**b, "status": "NOT_CALCULABLE", "value": None, "motivo": motivo,
            "inputs": inputs or [], "currency": b.get("currency")}


def calcular_eps(conn, cik: str) -> dict:
    """EPS basico REPORTADO. No se deriva: si el emisor no lo publica, no hay.

    El control NI/acciones existe y coincide (9/9 periodos, dif < 0,72%), pero
    la version canonica es la reportada: derivarlo cuando el emisor lo publica
    seria sustituir su cifra por una propia.
    """
    ctx, b = _contexto(conn, cik, "eps")
    if ctx is None:
        return b
    _ent, per, disp = ctx
    tag, f = elegir_concepto(disp, "eps_basico")
    if f is None:
        return _no(b, f"sin fact para el concepto 'eps_basico' en {per}; "
                      f"candidatos consultados: {CONCEPTOS['eps_basico']}")
    b["currency"] = f["currency"]
    return {**b, "status": "CALCULADO", "value": float(f["value_numeric"]),
            "motivo": None, "publicable": True,
            "inputs": [insumo(conn, "eps", "eps_basico", tag, f)]}


def _precio_en(conn, ent, moneda: str, b: dict):
    """El precio del instrumento LIGADO, en la moneda pedida. R2: no convierte."""
    precios = precios_de(conn, ent["entity_key"])
    if not precios:
        return None, _no(b, "la entidad no tiene instrumento ligado en "
                            "identity_v1.instrument: atribuirle un precio seria "
                            "un join por ticker")
    p = next((x for x in precios if x["currency"] == moneda), None)
    if p is None:
        return None, _no(b, f"el insumo contable esta en {moneda} y no hay precio "
                            f"en esa moneda (disponibles: "
                            f"{sorted({x['currency'] for x in precios})})")
    return p, None


def _insumo_precio(p) -> dict:
    return {"rol": "precio", "concepto": "precio_cierre",
            "instrument_id": p["instrument_id"], "exchange": p["exchange"],
            "trading_date": p["d"], "valor": float(p["close"]),
            "moneda": p["currency"], "ratio_adr": float(p["ratio_adr"] or 1),
            "evidencia": {"estado": "COMPLETA", "fuente": "market_price_daily"}}


def calcular_pb(conn, cik: str) -> dict:
    """P/B sobre el patrimonio de la CONTROLADORA.

    DECISION D9, tomada para el slice: el denominador es
    `patrimonio_controladora`, no el patrimonio total. El accionista compra la
    participacion de la controladora; incluir minoritarios abarata el multiplo
    de holdings y bancos sin que el comprador tenga derecho sobre esa parte.
    Queda en la provenance de cada celda cual tag se uso.
    """
    ctx, b = _contexto(conn, cik, "pb")
    if ctx is None:
        return b
    ent, per, disp = ctx
    tb, fb = elegir_concepto(disp, "patrimonio_controladora")
    ts, fs = elegir_concepto(disp, "acciones_circulacion")
    if fb is None or fs is None:
        falta = "patrimonio_controladora" if fb is None else "acciones_circulacion"
        return _no(b, f"sin fact para el concepto '{falta}' en {per}; "
                      f"candidatos consultados: {CONCEPTOS[falta]}")
    b["currency"] = fb["currency"]
    p, err = _precio_en(conn, ent, fb["currency"], b)
    if err:
        return err
    acciones = Decimal(str(fs["value_numeric"]))
    if acciones <= 0:
        return _no(b, f"acciones en circulacion = {acciones}")
    bvps = Decimal(str(fb["value_numeric"])) / acciones
    ins = [insumo(conn, "patrimonio", "patrimonio_controladora", tb, fb),
           insumo(conn, "acciones", "acciones_circulacion", ts, fs),
           _insumo_precio(p),
           {"rol": "derivado", "concepto": "bvps", "valor": float(bvps),
            "moneda": fb["currency"],
            "formula": "patrimonio_controladora / acciones_circulacion"}]
    if bvps <= 0:
        return _no(b, f"valor libro por accion = {bvps:.4f} <= 0: el multiplo "
                      f"invierte su lectura y no se publica", inputs=ins)
    valor = (Decimal(str(p["close"])) / Decimal(str(p["ratio_adr"] or 1))) / bvps
    return {**b, "status": "CALCULADO", "value": float(round(valor, 6)),
            "motivo": None, "publicable": True, "inputs": ins}


def calcular_pe(conn, cik: str) -> dict:
    """P/E con EPS del ULTIMO EJERCICIO ANUAL. window = FY, dicho asi.

    El motor no sabe hacer TTM. El canonico del contrato es TTM; mientras no
    exista, esto se publica como FY y NUNCA como TTM.

    Regla IAMC: con EPS <= 0 el multiplo no se muestra. No es un dato que
    falte -- es una regla financiera, y el motivo lo dice.
    """
    ctx, b = _contexto(conn, cik, "pe")
    if ctx is None:
        return b
    ent, per, disp = ctx
    tag, f = elegir_concepto(disp, "eps_basico")
    if f is None:
        return _no(b, f"sin fact para el concepto 'eps_basico' en {per}; "
                      f"candidatos consultados: {CONCEPTOS['eps_basico']}")
    b["currency"] = f["currency"]
    p, err = _precio_en(conn, ent, f["currency"], b)
    if err:
        return err
    eps = Decimal(str(f["value_numeric"]))
    ins = [insumo(conn, "eps", "eps_basico", tag, f), _insumo_precio(p)]
    if eps <= 0:
        return _no(b, f"REGLA: EPS = {eps} <= 0 (ejercicio con perdida). El P/E "
                      f"queda sin valor por decision financiera, no por falta de "
                      f"dato: el EPS esta y su provenance tambien", inputs=ins)
    valor = (Decimal(str(p["close"])) / Decimal(str(p["ratio_adr"] or 1))) / eps
    return {**b, "status": "CALCULADO", "value": float(round(valor, 6)),
            "motivo": None, "publicable": True, "inputs": ins}


CALCULADORES = {"ev_sales": calcular_ev_sales, "eps": calcular_eps,
                "pb": calcular_pb, "pe": calcular_pe}


def calcular_todos(conn, cik: str) -> list[dict]:
    """Los cuatro ratios soportados para un emisor, en orden estable."""
    return [CALCULADORES[cid](conn, cik) for cid in ("eps", "pb", "pe", "ev_sales")]


# ═══════════════════════════════════════════════════════════ persistencia ═══

def ratio_key(r: dict) -> str:
    """Huella determinista de identidad + insumos.

    Identidad: quien, que ratio, que periodo, que ventana, que base, que moneda.
    Insumos: el fact_key y el valor de cada uno, ordenados -- si un insumo
    cambia, la huella cambia y el motor cierra la fila anterior y abre una nueva.
    La version de formula participa: cambiar la formula NO puede reescribir el
    historico en silencio.
    """
    ident = "|".join(str(x) for x in (
        r["canonical_id"], r["entity_key"], r["period_end"], r["period_window"],
        r["denominator_basis"], r.get("currency") or "-", r["formula_version"],
        PROVENANCE_SCHEMA))
    huella_insumos = sorted(
        f"{i.get('rol')}={i.get('fact_key') or i.get('instrument_id') or i.get('concepto')}"
        f":{i.get('valor')}" for i in r.get("inputs", []))
    crudo = ident + "||" + "|".join(huella_insumos) + "||" + str(r["status"])
    return hashlib.sha256(crudo.encode("utf-8")).hexdigest()


SQL_VIGENTE = """
SELECT ratio_key FROM derived.ratio
 WHERE valid_to IS NULL AND entity_key = :ek AND canonical_id = :cid
   AND period_end = :pe AND period_window = :w AND denominator_basis = :b
   AND coalesce(currency, '-') = :cur
"""

SQL_INSERT = """
INSERT INTO derived.ratio (
  ratio_key, entity_key, cik, canonical_id, period_end, period_window,
  denominator_basis, currency, value, unit, status, motivo, publicable,
  formula_version, formula, inputs, input_checkpoint_id, run_id)
VALUES (
  :rk, :ek, :cik, :cid, :pe, :w, :b, :cur, :val, :unit, :st, :mot, :pub,
  :fv, :f, CAST(:inp AS jsonb), :chk, :run)
"""


def persistir(conn, r: dict, run_id: str, checkpoint: str) -> str:
    """Devuelve 'INSERTADO', 'SIN_CAMBIO' o 'REEMPLAZADO'.

    Idempotencia: misma identidad + mismos insumos = misma `ratio_key` = no se
    escribe. Insumo distinto = clave distinta: se cierra la vigente con
    `valid_to` y se inserta la nueva. Nunca se hace UPDATE de un valor.
    """
    if r["period_end"] is None or r["entity_key"] is None:
        return "OMITIDO_SIN_IDENTIDAD"
    rk = ratio_key(r)
    args = {"ek": r["entity_key"], "cid": r["canonical_id"], "pe": r["period_end"],
            "w": r["period_window"], "b": r["denominator_basis"],
            "cur": r.get("currency") or "-"}
    prev = conn.execute(text(SQL_VIGENTE), args).scalar()
    if prev == rk:
        return "SIN_CAMBIO"
    accion = "INSERTADO"
    if prev is not None:
        conn.execute(text("UPDATE derived.ratio SET valid_to = now() "
                          "WHERE ratio_key = :rk"), {"rk": prev})
        accion = "REEMPLAZADO"
    conn.execute(text(SQL_INSERT), {
        "rk": rk, "ek": r["entity_key"], "cik": r["cik"], "cid": r["canonical_id"],
        "pe": r["period_end"], "w": r["period_window"], "b": r["denominator_basis"],
        "cur": r.get("currency"), "val": r["value"], "unit": r["unit"],
        "st": r["status"], "mot": r["motivo"], "pub": bool(r.get("publicable")),
        "fv": r["formula_version"], "f": r["formula"],
        "inp": json.dumps(r["inputs"], ensure_ascii=False, default=str),
        "chk": checkpoint, "run": run_id})
    return accion


def checkpoint_de_insumos(conn) -> str:
    """Huella del estado de `derived.fact` que se leyo.

    Sin esto no se puede afirmar que dos corridas leyeron lo mismo, y la
    idempotencia no seria demostrable sino declarada.
    """
    fila = conn.execute(text(
        "SELECT count(*)::text || ':' || coalesce(max(updated_at)::text,'-') "
        "  FROM derived.fact WHERE valid_to IS NULL")).scalar_one()
    return hashlib.sha256(fila.encode()).hexdigest()[:32]


# ═══════════════════════════════════════════════════════════════ main ═══════

def ciks_del_universo(conn) -> list[str]:
    """Emisores con fundamentals. No hay lista hardcodeada de empresas."""
    return [r[0] for r in conn.execute(text(
        "SELECT DISTINCT cik FROM derived.fact WHERE valid_to IS NULL ORDER BY 1")).all()]


def main() -> int:
    ap = argparse.ArgumentParser(description="Motor canonico de ratios — EV/Sales")
    ap.add_argument("--persist", action="store_true",
                    help="escribe en derived.ratio (sin esto, solo calcula)")
    ap.add_argument("--cik", help="un solo emisor; por defecto, todos")
    a = ap.parse_args()

    s = load_settings()
    print(f"  {s.describe()}")
    if s.is_prod:
        print("  EXT-010: no se ejecuta contra produccion")
        return 2
    eng = get_admin_engine(s)

    with eng.connect() as c:
        v = violaciones_pertenencia(c)
        print(f"  F-061 · punteros de provenance ajenos: {v}")
        if v:
            print("  BLOQUEADO: hay hechos cuya provenance no pertenece a su emisor")
            return 1
        ciks = [a.cik] if a.cik else ciks_del_universo(c)
        checkpoint = checkpoint_de_insumos(c)
        resultados = [r for cik in ciks for r in calcular_todos(c, cik)]

    print(f"\n  {len(SPECS)} ratios soportados · checkpoint={checkpoint}\n")
    print(f"  {'CIK':<12}{'entidad':<30}{'ratio':<10}{'win':<5}{'periodo':<12}"
          f"{'estado':<16}{'valor':>13}  moneda")
    for r in resultados:
        nom = (r.get("preferred_name") or "-")[:28]
        val = f"{r['value']:.6g}" if r["value"] is not None else "-"
        print(f"  {r['cik']:<12}{nom:<30}{r['canonical_id']:<10}"
              f"{r['period_window']:<5}{str(r['period_end'] or '-'):<12}"
              f"{r['status']:<16}{val:>13}  {r.get('currency') or '-'}")
        if r["status"] != "CALCULADO":
            print(f"              motivo: {(r['motivo'] or '')[:110]}")

    if not a.persist:
        print("\n  (sin --persist: no se escribio nada)")
        return 0

    with edb.run_scope(eng, s, PIPELINE_VERSION) as run:
        with eng.begin() as c:
            acciones = {}
            for r in resultados:
                acciones[(r["cik"], r["canonical_id"])] = persistir(
                    c, r, run.run_id, checkpoint)
        run.status = "OK"
    print(f"\n  persistido en derived.ratio · run {run.run_id}")
    resumen: dict[str, int] = {}
    for acc in acciones.values():
        resumen[acc] = resumen.get(acc, 0) + 1
    for acc, n in sorted(resumen.items()):
        print(f"    {acc:<22} {n}")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    raise SystemExit(main())
