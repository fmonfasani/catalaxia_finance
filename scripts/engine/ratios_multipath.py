#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fase C — analisis MULTI-CAMINO de los ratios, sobre datos reales.

Pregunta que responde: de cuantas formas INDEPENDIENTES puede obtenerse cada
ratio, y cuando esas formas NO son equivalentes.

Dos caminos NO se cuentan como independientes si comparten el dato subyacente.
Cada camino declara explicitamente sus insumos para poder auditarlo.

SOLO LECTURA. No escribe en la base.
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from sqlalchemy import text  # noqa: E402

from engine.config import load_settings  # noqa: E402
from engine.db import get_admin_engine  # noqa: E402

OUT = REPO / "outputs" / "docs" / "fase_ratios"
CIK_YPF = "0000904851"

# El tag de EPS CAMBIA DE NOMBRE entre ejercicios. La semantica no se deduce del
# nombre: se declara aca, y la unidad (moneda/accion) se usa como control.
EPS_TAGS = [
    "BasicEarningsLossPerShare",            # 2023-2025, USD/shares
    "BasicAndDilutedEarningsPerShare",      # 2021-2022, ARS y USD
    "BasicAndDilutedEarningsLossPerShare",  # 2017-2020, ARS/shares
]
NI_TAGS = ["ProfitLossAttributableToOwnersOfParent", "ProfitLoss"]

# Tres conteos de acciones con SEMANTICA DISTINTA. No son intercambiables.
SHARE_TAGS = {
    "WeightedAverageShares": "promedio ponderado del ejercicio (denominador del EPS)",
    "EntityCommonStockSharesOutstanding": "en circulacion a fecha de caratula (dei)",
    "NumberOfSharesOutstanding": "en circulacion al cierre",
}


def facts(conn, cik):
    """Facts del anio principal de cada filing (no los comparativos)."""
    filas = conn.execute(text("""
        SELECT tag, report_period, currency, value_numeric, accession_number,
               unit_measure, filing_date
          FROM derived.fact
         WHERE valid_to IS NULL AND cik=:c AND is_numeric AND NOT is_dimensional
           AND value_numeric IS NOT NULL
           AND COALESCE(instant_date::text, end_date::text) = report_period::text
         ORDER BY report_period DESC"""), {"c": cik}).mappings().all()
    out = {}
    for f in filas:
        out.setdefault(str(f["report_period"]), {})[f["tag"]] = dict(f)
    return out


def shares_por_periodo(conn, cik):
    """Conteos de acciones por report_period.

    No se exige que el instant coincida con el cierre: el tag `dei` lleva la
    fecha de CARATULA del filing, no la del ejercicio.
    """
    filas = conn.execute(text("""
        SELECT DISTINCT ON (tag, report_period)
               tag, report_period, value_numeric, accession_number,
               COALESCE(instant_date::text, end_date::text) AS fecha
          FROM derived.fact
         WHERE valid_to IS NULL AND cik=:c AND NOT is_dimensional
           AND tag = ANY(:t) AND value_numeric IS NOT NULL
         ORDER BY tag, report_period DESC, filing_date DESC"""),
        {"c": cik, "t": list(SHARE_TAGS)}).mappings().all()
    out = {}
    for f in filas:
        out.setdefault(str(f["report_period"]), {})[f["tag"]] = dict(f)
    return out


def elegir(disp, cands):
    """Primer candidato presente. El ORDEN de la lista es la regla de fallback."""
    for t in cands:
        if t in disp:
            return t, disp[t]
    return None, None


def precio(conn, iid):
    r = conn.execute(text("""
        SELECT trading_date::text AS d, close, currency, exchange
          FROM market_price_daily WHERE instrument_id=:i
         ORDER BY trading_date DESC LIMIT 1"""), {"i": iid}).mappings().first()
    return dict(r) if r else None


def main() -> int:
    s = load_settings()
    if s.is_prod:
        print("EXT-010: abortado.")
        return 2
    eng = get_admin_engine(s)
    OUT.mkdir(parents=True, exist_ok=True)
    ev = {"equivalencia_eps": [], "pe": [], "acciones": {}}

    with eng.connect() as conn:
        F = facts(conn, CIK_YPF)
        SH = shares_por_periodo(conn, CIK_YPF)

        print("ANALISIS MULTI-CAMINO - YPF (unico emisor con fundamentals)\n")

        # ---- 1. EPS: cobertura real con la cadena de fallback --------------
        print("1. EPS - el tag cambia de nombre entre ejercicios")
        print(f"   {'periodo':<12} {'tag usado':<38} {'valor':>10} {'moneda':<6}")
        eps = {}
        for per in sorted(F, reverse=True):
            t, f = elegir(F[per], EPS_TAGS)
            if f is None:
                print(f"   {per:<12} {'(ninguno de los 3 tags)':<38} {'-':>10}")
                continue
            eps[per] = f
            print(f"   {per:<12} {t:<38} {float(f['value_numeric']):>10.2f} "
                  f"{f['currency']:<6}")
        print(f"   -> cobertura EPS: {len(eps)}/{len(F)} periodos "
              f"(con un solo tag serian 3)")

        # ---- 2. equivalencia: EPS reportado vs EPS derivado ----------------
        print("\n2. EQUIVALENCIA - EPS reportado  vs  ProfitLoss/WeightedAverageShares")
        print("   dos caminos al MISMO numero. Si no coinciden, algun tag no")
        print("   significa lo que su nombre sugiere.")
        print(f"   {'periodo':<12} {'reportado':>11} {'derivado':>12} {'dif %':>8}  veredicto")
        for per in sorted(eps, reverse=True):
            tn, fn = elegir(F[per], NI_TAGS)
            was = SH.get(per, {}).get("WeightedAverageShares")
            r = float(eps[per]["value_numeric"])
            if fn is None or was is None or float(was["value_numeric"]) == 0:
                falta = "ProfitLoss" if fn is None else "WeightedAverageShares"
                print(f"   {per:<12} {r:>11.2f} {'n/d':>12} {'-':>8}  "
                      f"NO_VERIFICABLE (falta {falta})")
                ev["equivalencia_eps"].append(
                    {"periodo": per, "estado": "NO_VERIFICABLE", "falta": falta})
                continue
            if fn["currency"] != eps[per]["currency"]:
                print(f"   {per:<12} {r:>11.2f} {'-':>12} {'-':>8}  "
                      f"NO_COMPARABLE ({fn['currency']} vs {eps[per]['currency']})")
                ev["equivalencia_eps"].append(
                    {"periodo": per, "estado": "NO_COMPARABLE",
                     "monedas": [fn["currency"], eps[per]["currency"]]})
                continue
            d = float(fn["value_numeric"]) / float(was["value_numeric"])
            dif = abs(d - r) / abs(r) * 100 if r else float("inf")
            vd = "COINCIDE" if dif < 2 else ("APROXIMA" if dif < 10 else "DIVERGE")
            print(f"   {per:<12} {r:>11.2f} {d:>12.4f} {dif:>7.2f}%  {vd}")
            ev["equivalencia_eps"].append(
                {"periodo": per, "reportado": r, "derivado": round(d, 6),
                 "dif_pct": round(dif, 3), "veredicto": vd, "tag_ni": tn,
                 "moneda": fn["currency"], "accession": eps[per]["accession_number"]})

        # ---- 3. los tres conteos de acciones ------------------------------
        print("\n3. ACCIONES - tres tags, tres semanticas. NO son intercambiables")
        cols = list(SHARE_TAGS)
        print(f"   {'periodo':<12} " + " ".join(f"{c[:21]:>22}" for c in cols))
        for per in sorted(SH, reverse=True)[:9]:
            fila = f"   {per:<12} "
            reg = {}
            for t in cols:
                v = SH[per].get(t)
                if v:
                    fila += f"{float(v['value_numeric']):>22,.0f} "
                    reg[t] = float(v["value_numeric"])
                else:
                    fila += f"{'n/d':>22} "
            print(fila)
            ev["acciones"][per] = reg

        # ---- 4. P/E por caminos -------------------------------------------
        print("\n4. P/E - caminos independientes, mismo instante de mercado")
        p_adr = precio(conn, "84")   # YPF NYSE, ratio 1:1, USD
        p_bue = precio(conn, "83")   # YPFD BUE, ARS
        print(f"   precio ADR  NYSE : {p_adr['close']} {p_adr['currency']}  ({p_adr['d']})")
        print(f"   precio local BUE : {p_bue['close']} {p_bue['currency']}  ({p_bue['d']})")
        print("   ratio ADR: 1.00  (identity_v1.instrument MKT:84 y 20-F 'Class D share')\n")

        for per in sorted(eps, reverse=True)[:4]:
            e = eps[per]
            tn, fn = elegir(F[per], NI_TAGS)
            print(f"   --- ejercicio {per} ---")
            # camino A: precio / EPS reportado
            if e["currency"] != p_adr["currency"]:
                print(f"   A  precio/EPS_reportado             NO_CALCULABLE   "
                      f"EPS en {e['currency']}, precio en {p_adr['currency']}; sin FX declarado")
                ev["pe"].append({"periodo": per, "camino": "A", "estado": "NO_CALCULABLE",
                                 "motivo": "monedas distintas sin FX declarado"})
            elif float(e["value_numeric"]) <= 0:
                print(f"   A  precio/EPS_reportado             NO_CALCULABLE   "
                      f"EPS={float(e['value_numeric']):.2f} <= 0 (ejercicio con perdida)")
                ev["pe"].append({"periodo": per, "camino": "A", "estado": "NO_CALCULABLE",
                                 "motivo": f"EPS={float(e['value_numeric'])} <= 0"})
            else:
                v = float(p_adr["close"]) / float(e["value_numeric"])
                print(f"   A  precio/EPS_reportado             {v:>8.2f}       "
                      f"{float(p_adr['close']):.2f}/{float(e['value_numeric']):.2f}")
                ev["pe"].append({"periodo": per, "camino": "A", "estado": "CALCULADO",
                                 "valor": round(v, 4),
                                 "insumos": {"precio": float(p_adr["close"]),
                                             "eps": float(e["value_numeric"]),
                                             "accession": e["accession_number"]}})
            # camino B: (precio * acciones) / resultado neto
            for st in ("EntityCommonStockSharesOutstanding", "NumberOfSharesOutstanding"):
                sh = SH.get(per, {}).get(st)
                if fn is None or sh is None:
                    continue
                et = f"B[{st[:26]}]"
                if fn["currency"] != p_adr["currency"]:
                    print(f"   {et:<36}NO_CALCULABLE   NI en {fn['currency']}, "
                          f"precio en {p_adr['currency']}")
                    ev["pe"].append({"periodo": per, "camino": f"B:{st}",
                                     "estado": "NO_CALCULABLE", "motivo": "monedas distintas"})
                    continue
                if float(fn["value_numeric"]) <= 0:
                    print(f"   {et:<36}NO_CALCULABLE   resultado neto <= 0")
                    ev["pe"].append({"periodo": per, "camino": f"B:{st}",
                                     "estado": "NO_CALCULABLE", "motivo": "net income <= 0"})
                    continue
                mcap = float(p_adr["close"]) * float(sh["value_numeric"])
                v = mcap / float(fn["value_numeric"])
                print(f"   {et:<36}{v:>8.2f}       mcap={mcap/1e9:.2f}e9  "
                      f"acciones={float(sh['value_numeric']):,.0f}")
                ev["pe"].append({"periodo": per, "camino": f"B:{st}", "estado": "CALCULADO",
                                 "valor": round(v, 4),
                                 "insumos": {"precio": float(p_adr["close"]),
                                             "acciones": float(sh["value_numeric"]),
                                             "acciones_tag": st,
                                             "net_income": float(fn["value_numeric"]),
                                             "ni_tag": tn}})
            print()

    (OUT / "multipath.json").write_text(
        json.dumps(ev, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print("  -> outputs/docs/fase_ratios/multipath.json")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    raise SystemExit(main())
