#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""El recorrido de demostracion, de la fila del screener a la evidencia fuente.

    seleccionar empresa -> ver datos financieros -> ver precio -> ver ratios
    -> seleccionar un ratio -> como fue calculado -> datos de entrada
    -> de que filing/fact/proveedor viene -> evidencia fuente

Cada paso sale de la base o del artefacto en disco. Nada se reconstruye de
memoria ni se reescribe: si un eslabon falta, se dice.

Uso:
    python scripts/engine/demo_drilldown.py                    # el screener
    python scripts/engine/demo_drilldown.py --empresa AAPL     # una empresa
    python scripts/engine/demo_drilldown.py --empresa AAPL --ratio roe
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import zipfile
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

FASE = REPO / "outputs" / "docs" / "fase_producto"
RAW_ROOT = REPO / "data" / "raw" / "engine"


def leer_fuente(ruta_raw: str | None) -> tuple[bytes | None, str]:
    """Lee el artefacto fuente, este suelto o dentro del paquete XBRL.

    S03 registra los miembros del paquete como `...-xbrl.zip!miembro.htm`: el
    documento inline vive DENTRO del zip que publica SEC. Sin resolver esa
    sintaxis, la cadena de evidencia se corta justo en el ultimo paso.
    """
    if not ruta_raw:
        return None, ""
    if "!" in ruta_raw:
        zip_rel, miembro = ruta_raw.split("!", 1)
        zpath = RAW_ROOT / zip_rel
        if not zpath.exists():
            return None, ""
        try:
            with zipfile.ZipFile(zpath) as z:
                return z.read(miembro), f"{zpath.relative_to(REPO)} :: {miembro}"
        except (KeyError, zipfile.BadZipFile):
            return None, ""
    p = RAW_ROOT / ruta_raw
    if not p.exists():
        return None, ""
    return p.read_bytes(), str(p.relative_to(REPO))


def barra(t: str) -> None:
    print(f"\n{'─' * 78}\n{t}\n{'─' * 78}")


def mostrar_empresa(f: dict) -> None:
    barra(f"1-2. EMPRESA · {f['ticker']}")
    if f["estado"] != "OK":
        print(f"  estado: {f['estado']}")
        print(f"  motivo: {f.get('motivo')}")
        return
    e = f["entidad"]
    print(f"  razon social      {e['preferred_name']}")
    print(f"  entity_key        {e['entity_key']}   (clave opaca de identity_v1)")
    print(f"  CIK               {e['cik']}")
    print(f"  identidad         {f.get('origen_identidad')}")
    print(f"  enlace instrumento{'':<1} {f.get('enlace_instrumento')}")
    if f.get("enlace_instrumento") != "OK":
        print(f"     -> {f.get('enlace_instrumento_motivo','')[:150]}")
    print(f"  ejercicio         {f['ejercicio']}   moneda de reporte {f['moneda_reporte']}")
    print(f"  taxonomia         {f['taxonomia']}")

    barra(f"3. PRECIO · {f['ticker']}")
    for p in f["precios"]:
        ru = p.get("ratio_underlying")
        print(f"  instrumento {p['instrument_id']:<4} {str(p['exchange']):<6} "
              f"cierre {float(p['close']):>12,.2f} {p['currency']}   {p['d']}"
              + (f"   ratio ADR {float(ru):g}:1" if ru else ""))


def mostrar_ratios(f: dict) -> None:
    barra(f"4. RATIOS · {f['ticker']} · ejercicio {f['ejercicio']}")
    orden = sorted(f["metricas"].items(),
                   key=lambda kv: (kv[1]["estado"] != "CALCULADO", kv[0]))
    for rid, m in orden:
        if m["estado"] == "CALCULADO":
            v = m["valor"]
            txt = f"{v:>16,.2f}" if abs(v) > 1e6 else f"{v:>16.4f}"
            print(f"  {rid:<22}{txt}  {m.get('unidad','')}")
        elif m["estado"] == "REVIEW_REQUIRED":
            print(f"  {rid:<22}{m['valor']:>16.4f}  REVIEW_REQUIRED "
                  f"(no publicable sin banda de sanidad)")
        else:
            print(f"  {rid:<22}{'NULL':>16}  {m.get('motivo','')[:60]}")


def mostrar_ratio(f: dict, rid: str) -> None:
    m = f["metricas"].get(rid)
    if m is None:
        print(f"  no existe la metrica {rid!r}. Disponibles: "
              f"{sorted(f['metricas'])}")
        return
    barra(f"5-6. COMO SE CALCULO · {f['ticker']} · {rid}")
    print(f"  estado     {m['estado']}")
    if m["estado"] == "NO_CALCULABLE":
        print(f"  valor      NULL")
        print(f"  motivo     {m['motivo']}")
        return
    print(f"  valor      {m['valor']}  {m.get('unidad','')}")
    print(f"  periodo    {m['periodo']}")
    print(f"  formula    {m.get('formula')}")
    if not m.get("publicable", True):
        print(f"  aviso      REVIEW_REQUIRED: aritmeticamente correcto, no publicable")

    barra(f"7. DATOS DE ENTRADA · {rid}")
    for i in m.get("insumos", []):
        val = i["valor"]
        print(f"  {i['rol']:<12} {val:>22,.4f} {i.get('moneda') or ''}")
        if i.get("concepto"):
            print(f"     concepto  {i['concepto']}")
        if i.get("tag"):
            print(f"     tag XBRL  {i['tag']}   ({i.get('namespace','')})")
        if i.get("instrumento"):
            print(f"     instrumento MKT:{i['instrumento']} {i.get('mercado','')} "
                  f"fecha {i.get('fecha')} ratio ADR {i.get('ratio_adr')}")

    barra(f"8-9. DE DONDE VIENE · {rid}")
    for i in m.get("insumos", []):
        ev = i.get("evidencia") or {}
        print(f"\n  ── {i['rol']} ──")
        if ev.get("fuente") == "market_price_daily":
            print(f"     proveedor   Market · tabla market_price_daily")
            print(f"     instrumento {ev.get('instrument_key')}")
            print(f"     fecha       {i.get('fecha')}")
            continue
        print(f"     filing      {i.get('form')} {i.get('accession')} "
              f"presentado {i.get('filing_date')}")
        print(f"     en SEC      {i.get('url_filing')}")
        if ev.get("estado") != "COMPLETA":
            print(f"     cadena      {ev.get('estado')}: {ev.get('motivo')}")
            continue
        print(f"     parsed.fact {ev['parsed_fact_id']}  qname {ev['qname']}")
        print(f"     contexto    {ev['contexto']}  unidad {ev.get('medida')} "
              f"decimales {ev.get('decimales')}")
        print(f"     archivo     {ev['archivo_fuente']}")
        print(f"     sha256      {ev['sha256_fuente']}")
        datos, ubic = leer_fuente(ev.get("ruta_raw"))
        if datos is None:
            print(f"     en disco    NO ESTA ({ev.get('ruta_raw')})")
            continue
        real = hashlib.sha256(datos).hexdigest()
        coincide = "COINCIDE" if real == ev["sha256_fuente"] else "DIFIERE"
        print(f"     en disco    {ubic}")
        print(f"     verificado  {coincide}  ({len(datos):,} bytes)")
        if coincide == "DIFIERE":
            print(f"     recalculado {real}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--empresa", default=None)
    ap.add_argument("--ratio", default=None)
    a = ap.parse_args()

    filas = json.loads((FASE / "screener.json").read_text(encoding="utf-8"))
    if not a.empresa:
        barra("SCREENER — universo de demostracion")
        cols = ["pe", "market_cap", "roe", "debt_to_equity", "current_ratio", "net_margin"]
        print(f"  {'ticker':<7} {'ejercicio':<12} {'tax':<14} " +
              " ".join(f"{c[:11]:>13}" for c in cols))
        for f in filas:
            if f["estado"] != "OK":
                print(f"  {f['ticker']:<7} {f['estado']:<12} {'-':<14} " +
                      " ".join(f"{'NULL':>13}" for _ in cols))
                continue
            l = f"  {f['ticker']:<7} {f['ejercicio'][:10]:<12} {f['taxonomia'][:13]:<14} "
            for c in cols:
                m = f["metricas"].get(c, {})
                if m.get("estado") == "CALCULADO":
                    v = m["valor"]
                    l += (f"{v/1e9:>12,.2f}B " if c == "market_cap" else f"{v:>13.4f} ")
                else:
                    l += f"{'NULL':>13} "
            print(l)
        print("\n  para el recorrido completo:")
        print("    python scripts/engine/demo_drilldown.py --empresa AAPL --ratio roe")
        return 0

    f = next((x for x in filas if x["ticker"] == a.empresa.upper()), None)
    if f is None:
        print(f"empresa {a.empresa!r} fuera del universo: "
              f"{[x['ticker'] for x in filas]}")
        return 1
    mostrar_empresa(f)
    if f["estado"] != "OK":
        return 0
    mostrar_ratios(f)
    if a.ratio:
        mostrar_ratio(f, a.ratio)
    else:
        print("\n  para ver como se calculo uno: --ratio <nombre>")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    raise SystemExit(main())
