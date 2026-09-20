#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fase G — auditoria INDEPENDIENTE de los ratios.

Independencia real: este script no importa `engine.*` ni ninguno de los modulos
que calcularon los ratios. Habla con PostgreSQL por `psql` via subprocess y hace
su propia aritmetica con Decimal (no float). Lo unico que comparte con el
implementador es la base de datos, que es justamente lo que hay que auditar.

Lee los JSON que produjo el implementador y trata cada valor como una AFIRMACION
a verificar, no como un resultado a confirmar.

SOLO LECTURA.
"""
from __future__ import annotations

import io
import json
import subprocess
import sys
from decimal import Decimal, getcontext
from pathlib import Path

getcontext().prec = 40

REPO = Path(__file__).resolve().parents[2]
FASE = REPO / "outputs" / "docs" / "fase_ratios"
CONTENEDOR = "catalaxia-engine-dev"


def sql(q: str) -> list[list[str]]:
    """Consulta cruda por psql. Sin SQLAlchemy, sin codigo del implementador."""
    p = subprocess.run(
        ["docker", "exec", CONTENEDOR, "psql", "-U", "catalaxia", "-d", "catalaxia",
         "-t", "-A", "-F", "\x1f", "-c", q],
        capture_output=True, text=True, encoding="utf-8")
    if p.returncode != 0:
        raise SystemExit(f"psql fallo: {p.stderr[:300]}")
    # NO usar .strip() sobre todo el blob: Python trata \x1c-\x1f como
    # whitespace, asi que se comeria el separador junto con el \n final
    # cuando el ULTIMO campo de la ULTIMA fila viene NULL. Ver F-056/F-057.
    return [ln.split("\x1f") for ln in p.stdout.splitlines() if ln.strip()]


def uno(q: str) -> str | None:
    r = sql(q)
    return r[0][0] if r else None


def main() -> int:
    res, ok_total = [], True

    def chk(nombre, cond, detalle=""):
        nonlocal ok_total
        print(f"  {'OK   ' if cond else 'FALLA'} {nombre:<52} {detalle}")
        res.append({"control": nombre, "ok": bool(cond), "detalle": str(detalle)[:400]})
        if not cond:
            ok_total = False

    print("AUDITORIA INDEPENDIENTE DE RATIOS\n")
    print("  fuente: psql directo · aritmetica: Decimal · sin importar engine.*\n")

    e2e = json.loads((FASE / "e2e_producto.json").read_text(encoding="utf-8"))
    inv = json.loads((FASE / "ratios_calculados.json").read_text(encoding="utf-8"))
    mp = json.loads((FASE / "multipath.json").read_text(encoding="utf-8"))

    # --- A. cada valor CALCULADO se reproduce desde la base -----------------
    print("A. reproducibilidad: recalcular cada ratio desde derived.fact")
    reproducidos = fallidos = 0
    detalle_fallo = []
    for fila in e2e:
        if not fila.get("ratios"):
            continue
        per = fila["ejercicio"]
        cik = fila["entidad"]["cik"]
        for rid, v in fila["ratios"].items():
            if v["estado"] != "CALCULADO" or rid == "pe":
                continue
            tn, td = v["formula"].split("/")
            q = (f"SELECT tag, value_numeric, currency, accession_number FROM derived.fact "
                 f" WHERE valid_to IS NULL AND cik='{cik}' AND NOT is_dimensional "
                 f"   AND report_period='{per}' AND tag IN ('{tn}','{td}') "
                 f"   AND COALESCE(instant_date::text,end_date::text)=report_period::text")
            vals = {r[0]: r for r in sql(q)}
            if tn not in vals or td not in vals:
                fallidos += 1
                detalle_fallo.append(f"{fila['ticker']}/{rid}: falta {tn if tn not in vals else td}")
                continue
            mio = Decimal(vals[tn][1]) / Decimal(vals[td][1])
            suyo = Decimal(str(v["valor"]))
            if abs(mio - suyo) > Decimal("0.000001"):
                fallidos += 1
                detalle_fallo.append(f"{fila['ticker']}/{rid}: yo {mio} vs {suyo}")
            else:
                reproducidos += 1
    chk("A1 · fila del screener reproducida con aritmetica propia", fallidos == 0,
        f"{reproducidos} reproducidos, {fallidos} divergentes "
        + (str(detalle_fallo[:3]) if detalle_fallo else ""))

    # el inventario completo, no solo el ultimo ejercicio
    rep2 = fall2 = 0
    det2 = []
    for r in inv["ratios"]:
        if r["estado"] != "CALCULADO":
            continue
        tn, td = r["numerador"]["tag"], r["denominador"]["tag"]
        # numerador compuesto: la resta se REHACE desde la base, no se toma
        # el `valor_neto` que declaro el implementador.
        tr = r["numerador"].get("resta_tag")
        pedidos = [tn, td] + ([tr] if tr else [])
        lista = ",".join(f"'{t}'" for t in pedidos)
        q = (f"SELECT tag, value_numeric FROM derived.fact WHERE valid_to IS NULL "
             f" AND cik='{r['cik']}' AND NOT is_dimensional AND report_period='{r['periodo']}' "
             f" AND tag IN ({lista}) "
             f" AND COALESCE(instant_date::text,end_date::text)=report_period::text")
        vals = {x[0]: x[1] for x in sql(q)}
        if any(t not in vals for t in pedidos):
            fall2 += 1
            det2.append(f"{r['ratio']}/{r['periodo']}: falta insumo "
                        f"{[t for t in pedidos if t not in vals]}")
            continue
        numerador = Decimal(vals[tn]) - (Decimal(vals[tr]) if tr else Decimal(0))
        mio = numerador / Decimal(vals[td])
        if abs(mio - Decimal(str(r["valor"]))) > Decimal("0.000001"):
            fall2 += 1
            det2.append(f"{r['ratio']}/{r['periodo']}: yo {mio} vs {r['valor']}")
        else:
            rep2 += 1
    chk("A2 · inventario completo reproducido (todos los ejercicios)", fall2 == 0,
        f"{rep2} reproducidos, {fall2} divergentes " + (str(det2[:3]) if det2 else ""))

    # --- B. ningun valor inventado -----------------------------------------
    print("\nB. ningun valor sin respaldo en la base")
    sin_respaldo = []
    for r in inv["ratios"]:
        if r["estado"] != "CALCULADO":
            continue
        for lado in ("numerador", "denominador"):
            d = r[lado]
            n = uno(f"SELECT count(*) FROM derived.fact WHERE valid_to IS NULL "
                    f" AND cik='{r['cik']}' AND tag='{d['tag']}' AND report_period='{r['periodo']}' "
                    f" AND value_numeric={d['valor']} AND currency='{d['moneda']}'")
            if n == "0":
                sin_respaldo.append(f"{r['ratio']}/{r['periodo']}/{d['tag']}={d['valor']}")
        if r["numerador"].get("resta_tag"):
            n = uno(f"SELECT count(*) FROM derived.fact WHERE valid_to IS NULL "
                    f" AND cik='{r['cik']}' AND tag='{r['numerador']['resta_tag']}' "
                    f" AND report_period='{r['periodo']}' AND currency='{r['numerador']['moneda']}'")
            if n == "0":
                sin_respaldo.append(f"{r['ratio']}/{r['periodo']}/"
                                    f"{r['numerador']['resta_tag']} (termino restado)")
    chk("B1 · todo insumo existe en derived.fact con ese valor", not sin_respaldo,
        f"{len(sin_respaldo)} sin respaldo " + (str(sin_respaldo[:3]) if sin_respaldo else ""))

    # --- C. provenance apunta a un filing real ------------------------------
    print("\nC. provenance")
    accs = sorted({r["provenance"]["accession_num"] for r in inv["ratios"]
                   if r["estado"] == "CALCULADO"})
    malas = [a for a in accs
             if uno(f"SELECT count(*) FROM derived.fact WHERE accession_number='{a}'") == "0"]
    chk("C1 · cada accession citada existe en derived.fact", not malas,
        f"{len(accs)} accessions distintas, {len(malas)} inexistentes")
    huerf = uno("SELECT count(*) FROM derived.fact WHERE valid_to IS NULL "
                " AND (accession_number IS NULL OR source_fact_ids IS NULL)")
    chk("C2 · ningun fact derivado sin accession ni source_fact_ids", huerf == "0",
        f"{huerf} facts sin trazabilidad")

    # --- D. unidades y monedas ---------------------------------------------
    print("\nD. unidades y periodos")
    mezcla = [r for r in inv["ratios"] if r["estado"] == "CALCULADO"
              and r["numerador"]["moneda"] != r["denominador"]["moneda"]]
    chk("D1 · ningun ratio mezcla monedas", not mezcla, f"{len(mezcla)} mezclados")
    distinto_per = [r for r in inv["ratios"] if r["estado"] == "CALCULADO"
                    and r["provenance"]["accession_num"] != r["provenance"]["accession_den"]]
    chk("D2 · numerador y denominador del mismo filing", not distinto_per,
        f"{len(distinto_per)} cruzan filings")
    # la regla de seleccion no debe dejar entrar comparativos
    comp = uno("SELECT count(*) FROM derived.fact WHERE valid_to IS NULL AND cik='0000904851' "
               " AND NOT is_dimensional AND tag='Assets' "
               " AND COALESCE(instant_date::text,end_date::text)=report_period::text")
    tot = uno("SELECT count(*) FROM derived.fact WHERE valid_to IS NULL AND cik='0000904851' "
              " AND NOT is_dimensional AND tag='Assets'")
    chk("D3 · la regla de periodo descarta los comparativos",
        comp is not None and tot is not None and int(comp) < int(tot),
        f"Assets: {comp} principales de {tot} filas (los otros son comparativos de 3 anios)")

    # --- E. NULL y NO_CALCULABLE siempre con motivo -------------------------
    print("\nE. tratamiento de lo que falta")
    sin_motivo = [r for r in inv["ratios"] if r["estado"] == "NO_CALCULABLE"
                  and not r.get("motivo")]
    nulos_sin_corte = [f["ticker"] for f in e2e if not f.get("ratios") and not f.get("corte")]
    chk("E1 · todo NO_CALCULABLE declara motivo", not sin_motivo, f"{len(sin_motivo)} sin motivo")
    chk("E2 · toda empresa sin fila declara donde se corto", not nulos_sin_corte,
        f"{len(nulos_sin_corte)} sin eslabon de corte")
    pe_nulos = [f["ticker"] for f in e2e if f.get("ratios", {}).get("pe", {}).get("estado")
                == "NO_CALCULABLE"]
    chk("E3 · P/E con EPS<=0 queda NULL, no negativo",
        all(f["ratios"]["pe"].get("valor") is None for f in e2e
            if f.get("ratios", {}).get("pe", {}).get("estado") == "NO_CALCULABLE"),
        f"{pe_nulos} sin valor")

    # --- F. multi-camino ----------------------------------------------------
    print("\nF. caminos multiples")
    eq = [x for x in mp["equivalencia_eps"] if x.get("veredicto")]
    coinciden = [x for x in eq if x["veredicto"] == "COINCIDE"]
    chk("F1 · EPS reportado == ProfitLoss/WeightedAverageShares",
        len(coinciden) == len(eq) and len(eq) >= 9,
        f"{len(coinciden)}/{len(eq)} coinciden (dif max "
        f"{max((x['dif_pct'] for x in eq), default=0):.2f}%)")
    pes = [x for x in mp["pe"] if x["estado"] == "CALCULADO"]
    pares = {}
    for x in pes:
        pares.setdefault(x["periodo"], []).append(x)
    divergentes = []
    for per, xs in pares.items():
        if len(xs) < 2:
            continue
        vs = [x["valor"] for x in xs]
        if (max(vs) - min(vs)) / min(vs) > 0.05:
            divergentes.append((per, vs))
    chk("F2 · los caminos del P/E concuerdan dentro del 5%", not divergentes,
        f"{len(pares)} ejercicios con >1 camino, {len(divergentes)} divergentes")

    # --- G. determinismo ----------------------------------------------------
    print("\nG. determinismo")
    a = uno("SELECT md5(string_agg(x,'|' ORDER BY x)) FROM (SELECT tag||report_period||"
            "value_numeric::text x FROM derived.fact WHERE valid_to IS NULL AND cik='0000904851' "
            "AND NOT is_dimensional AND COALESCE(instant_date::text,end_date::text)="
            "report_period::text) t")
    b = uno("SELECT md5(string_agg(x,'|' ORDER BY x)) FROM (SELECT tag||report_period||"
            "value_numeric::text x FROM derived.fact WHERE valid_to IS NULL AND cik='0000904851' "
            "AND NOT is_dimensional AND COALESCE(instant_date::text,end_date::text)="
            "report_period::text) t")
    chk("G1 · el conjunto de insumos es estable entre lecturas", a == b and a, (a or "")[:16])

    # --- H. cobertura declarada == cobertura medida -------------------------
    print("\nH. cobertura: lo declarado contra lo medido")
    n_cik = uno("SELECT count(DISTINCT id_value) FROM identity_v1.identifier "
                " WHERE id_type='CIK' AND valid_to IS NULL")
    n_fact = uno("SELECT count(DISTINCT cik) FROM derived.fact WHERE valid_to IS NULL")
    n_link = uno("SELECT count(*) FROM identity_v1.instrument WHERE valid_to IS NULL")
    n_inst = uno("SELECT count(*) FROM market_instruments")
    # El "1" original era un numero copiado del estado de esa corrida, no una
    # invariante. Congelarlo hizo que este mismo control quedara en FALLA
    # cuando la ingesta avanzo de 1 a 7 cadenas completas: un falso negativo,
    # no una regresion. La aserción correcta es contra lo que e2e_producto.py
    # declara (que corte es aceptable y por que), no contra un numero fijo.
    completas = [f["ticker"] for f in e2e if not f.get("corte")]
    bloqueadas = {f["ticker"]: f["corte"] for f in e2e if f.get("corte")}
    chk("H1 · toda empresa de la muestra tiene cadena completa o un corte de causa conocida",
        set(bloqueadas) <= {"BMA"} and bloqueadas.get("BMA") == "IDENTITY",
        f"completas={completas} bloqueadas={bloqueadas}")
    # OJO: fundamentals (n_fact) no tiene por que igualar "cadenas completas"
    # de e2e — BMA tiene fundamentals en derived.fact (Macro Bank Inc., CIK
    # 0001347426) pero su cadena corta ANTES, en IDENTITY, porque el
    # instrumento 584 no esta enlazado. Son dos limites distintos (ingesta de
    # SEC vs. enlace instrumento->entidad); la invariante real es contra el
    # tamano de la muestra deliberada (8 emisores, ni uno mas), no contra
    # cuantas cadenas llegan completas hasta el screener.
    chk("H2 · fundamentals en toda la base == el tamano de la muestra deliberada (no mas)",
        n_fact == str(len(e2e)),
        f"{n_fact}/{n_cik} CIK con facts en derived.fact = {100*int(n_fact)/int(n_cik):.2f}% "
        f"· muestra: {len(e2e)} empresas ({len(completas)} con cadena completa, "
        f"BMA con fundamentals pero sin enlace de instrumento)")
    chk("H3 · el enlace instrumento->entidad es el limite del join",
        int(n_link) < int(n_inst),
        f"{n_link}/{n_inst} instrumentos enlazados = {100*int(n_link)/int(n_inst):.1f}%")

    n_ok = sum(1 for r in res if r["ok"])
    print(f"\n  {n_ok}/{len(res)} controles OK")
    (FASE / "auditoria_independiente.json").write_text(
        json.dumps({"ok": ok_total, "controles": res}, indent=2, ensure_ascii=False),
        encoding="utf-8")
    print("  evidencia -> outputs/docs/fase_ratios/auditoria_independiente.json")
    return 0 if ok_total else 1


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    raise SystemExit(main())
