#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fase G — banco ADVERSARIO de la capa de RATIOS. Base DESCARTABLE.

Cubre lo que `ratios_auditoria.py` y `audit_provenance_ratios.py` NO cubren:
esos dos verifican que el sistema, tal cual está la base HOY, sea coherente.
Este banco pregunta algo distinto: si un dato **incorrecto** entrara en
`derived.fact`, ¿el ratio lo detecta, lo rechaza, o lo calcula como si nada?

Cada ataque declara el veredicto ESPERADO antes de correr, como
`mut_f054_f055.py`. No alcanza con "paso" o "fallo": hay que decir qué
invariante bloquea qué, y si no hay ninguna, decirlo tambien — un banco
adversario que solo encuentra controles en verde no esta buscando lo
suficiente.

La base homologada NO se toca: todo corre sobre una copia por TEMPLATE, que
se destruye al final. Se verifica la huella de la homologada antes y despues.

SOLO LECTURA sobre `catalaxia`. Escribe (y destruye) `adversario_ratios_mut`.
"""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts" / "engine"))

from sqlalchemy import text  # noqa: E402

from engine.config import load_settings  # noqa: E402
from engine.db import get_admin_engine  # noqa: E402

import ratios_inventario as RI  # noqa: E402

OUT = REPO / "outputs" / "docs" / "fase_ratios"
CONT = "catalaxia-engine-dev"
BASE = "catalaxia"
COPIA = "adversario_ratios_mut"

YPF, GGAL, AAPL = "0000904851", "0001114700", "0000320193"


def psql(q: str, db: str = BASE) -> str:
    p = subprocess.run(["docker", "exec", CONT, "psql", "-U", "catalaxia", "-d", db,
                        "-t", "-A", "-v", "ON_ERROR_STOP=1", "-c", q],
                       capture_output=True, text=True, encoding="utf-8")
    if p.returncode != 0:
        raise SystemExit(f"psql fallo ({db}): {p.stderr[:500]}")
    return p.stdout.strip()


def psql_rc(q: str, db: str) -> tuple[int, str]:
    p = subprocess.run(["docker", "exec", CONT, "psql", "-U", "catalaxia", "-d", db,
                        "-t", "-A", "-v", "ON_ERROR_STOP=1", "-c", q],
                       capture_output=True, text=True, encoding="utf-8")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def huella(db: str = BASE) -> str:
    return psql("SELECT count(*)||'|'||md5(string_agg(tag||report_period::text||"
                "value_numeric::text||coalesce(currency,''), '|' ORDER BY fact_key)) "
                "FROM derived.fact WHERE valid_to IS NULL", db)


def recrear() -> None:
    """`CREATE DATABASE ... TEMPLATE` exige que NADIE este conectado a
    `catalaxia` en ese instante — y `catalaxia-api` mantiene un pool de
    conexiones vivo. Se reintenta con backoff corto en vez de terminar
    sesiones ajenas (que si afectaria al servicio real)."""
    import time
    psql(f'DROP DATABASE IF EXISTS "{COPIA}" WITH (FORCE)', "postgres")
    ultimo_error = ""
    intentos = 30
    for intento in range(intentos):
        p = subprocess.run(
            ["docker", "exec", CONT, "psql", "-U", "catalaxia", "-d", "postgres",
             "-t", "-A", "-v", "ON_ERROR_STOP=1", "-c",
             f'CREATE DATABASE "{COPIA}" TEMPLATE "{BASE}"'],
            capture_output=True, text=True, encoding="utf-8")
        if p.returncode == 0:
            break
        ultimo_error = p.stderr
        time.sleep(2)
    else:
        raise SystemExit(f"no se pudo crear la copia tras {intentos} intentos "
                         f"(~{intentos*2}s): {ultimo_error[:400]}")
    psql(f'GRANT ALL ON DATABASE "{COPIA}" TO catalaxia_engine', "postgres")


def uno_o(cik: str, tag: str, per: str, campo: str = "value_numeric") -> str:
    return psql(f"SELECT {campo} FROM derived.fact WHERE valid_to IS NULL "
                f" AND cik='{cik}' AND tag='{tag}' AND report_period='{per}' "
                f" AND NOT is_dimensional LIMIT 1", COPIA)


def calcular_en_copia(cik: str, nombre: str) -> list[dict]:
    """Corre la MISMA logica de produccion (`ratios_inventario.calcular`)
    pero apuntada a la base mutada, via el motor admin (bypassa los triggers
    de F-015/F-017 tal como hace `mut_f054_f055.py`, y es necesario para leer
    ademas de para mutar)."""
    os.environ["ENGINE_DB_NAME"] = COPIA
    s = load_settings()
    eng = get_admin_engine(s)
    try:
        with eng.connect() as conn:
            return RI.calcular(conn, cik, nombre)
    finally:
        eng.dispose()


def ratio_de(filas: list[dict], rid: str, per: str) -> dict | None:
    return next((r for r in filas if r["ratio"] == rid and r["periodo"] == per), None)


def desvio_identidad(cik: str, per: str) -> str | None:
    """|Activo - (Pasivo+Patrimonio)| del periodo PRINCIPAL, filtrando
    dimensionales. Sin `NOT is_dimensional` esto es un producto cartesiano
    entre todas las variantes por segmento de cada concepto — con GGAL (que
    desglosa por segmento) eso es un `CREATE`-mata-memoria, no una fila. Ver
    F-058."""
    q = (
        "SELECT abs(v1.value_numeric - (v2.value_numeric+v3.value_numeric)) "
        "  FROM derived.fact v1, derived.fact v2, derived.fact v3 "
        f" WHERE v1.cik='{cik}' AND v1.tag='Assets' AND v1.report_period='{per}' "
        f"   AND v2.cik='{cik}' AND v2.tag='Liabilities' AND v2.report_period='{per}' "
        f"   AND v3.cik='{cik}' AND v3.tag='Equity' AND v3.report_period='{per}' "
        "   AND v1.valid_to IS NULL AND v2.valid_to IS NULL AND v3.valid_to IS NULL "
        "   AND NOT v1.is_dimensional AND NOT v2.is_dimensional AND NOT v3.is_dimensional "
        "   AND COALESCE(v1.instant_date::text,v1.end_date::text)=v1.report_period::text "
        "   AND COALESCE(v2.instant_date::text,v2.end_date::text)=v2.report_period::text "
        "   AND COALESCE(v3.instant_date::text,v3.end_date::text)=v3.report_period::text "
        "LIMIT 5")
    r = psql(q, COPIA)
    if not r:
        return None
    filas = r.splitlines()
    return filas[0] if len(filas) == 1 else None


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    res, ok_total = [], True

    def chk(n, cond, esperado, real, critico=True):
        nonlocal ok_total
        marca = "OK   " if cond else ("FALLA" if critico else "NOTA ")
        print(f"  {marca} {n:<58}")
        print(f"        esperado: {esperado}")
        print(f"        real:     {real}")
        res.append({"ataque": n, "ok": bool(cond), "esperado": str(esperado)[:300],
                    "real": str(real)[:300], "critico": critico})
        if not cond and critico:
            ok_total = False

    h0 = huella()
    print("BANCO ADVERSARIO — CAPA DE RATIOS")
    print(f"  huella de la homologada al empezar: {h0}\n")

    # ═══════ ATK1 · moneda incorrecta en el denominador ═══════
    print("ATK1 · moneda incorrecta — CurrentLiabilities de YPF 2025 pasa a ARS")
    recrear()
    antes = calcular_en_copia(YPF, "YPF")
    r0 = ratio_de(antes, "current_ratio", "2025-12-31")
    psql(f"UPDATE derived.fact SET currency='ARS' WHERE valid_to IS NULL AND cik='{YPF}' "
         f" AND tag='CurrentLiabilities' AND report_period='2025-12-31'", COPIA)
    despues = calcular_en_copia(YPF, "YPF")
    r1 = ratio_de(despues, "current_ratio", "2025-12-31")
    chk("A1 · current_ratio pasa a NO_CALCULABLE si el denominador cambia de moneda",
        r1 is not None and r1["estado"] == "NO_CALCULABLE" and "moneda" in r1.get("motivo", ""),
        "NO_CALCULABLE, motivo menciona monedas distintas",
        f"antes={r0['estado']}={r0.get('valor')} · despues={r1['estado']} motivo={r1.get('motivo')}")

    # ═══════ ATK2 · signo incorrecto (Equity invertido) ═══════
    print("\nATK2 · signo incorrecto — Equity de GGAL 2025 con el signo invertido")
    recrear()
    per_ggal = psql(f"SELECT max(report_period)::text FROM derived.fact WHERE valid_to IS NULL "
                    f" AND cik='{GGAL}' AND tag='Equity'", COPIA)
    antes = calcular_en_copia(GGAL, "GGAL")
    r0 = ratio_de(antes, "roe", per_ggal)
    a0 = desvio_identidad(GGAL, per_ggal)
    rc, out = psql_rc(f"UPDATE derived.fact SET value_numeric = -value_numeric "
                      f" WHERE valid_to IS NULL AND cik='{GGAL}' AND tag='Equity' "
                      f" AND report_period='{per_ggal}'", COPIA)
    if rc != 0:
        chk("A2a · el ratio se calcula igual con un signo corrupto (no lo detecta el ratio en si)",
            False, "el UPDATE deberia aplicar", f"el UPDATE fue rechazado: {out.strip()[:200]}",
            critico=False)
    else:
        despues = calcular_en_copia(GGAL, "GGAL")
        r1 = ratio_de(despues, "roe", per_ggal)
        chk("A2a · el ratio SE CALCULA igual con Equity de signo invertido (el ratio no lo detecta)",
            r1 is not None and r1["estado"] == "CALCULADO" and r1["valor"] != r0["valor"],
            "CALCULADO, con un valor distinto y sin ninguna senal de error — "
            "la division no sabe que el insumo esta corrupto",
            f"antes={r0['valor']} · despues={r1['estado']}={r1.get('valor')}")
        a1 = desvio_identidad(GGAL, per_ggal)
        chk("A2b · pero la identidad Activo=Pasivo+Patrimonio SI detecta la corrupcion",
            a1 is not None and a0 is not None and float(a1) > float(a0) + 1,
            f"el desvio de la identidad crece (antes~{a0})",
            f"desvio despues del ataque = {a1} (antes {a0})")

    # ═══════ ATK3 · NULL tratado como cero ═══════
    print("\nATK3 · denominador puesto en CERO explicito (no ausente)")
    recrear()
    per_a = psql(f"SELECT max(report_period)::text FROM derived.fact WHERE valid_to IS NULL "
                f" AND cik='{AAPL}' AND tag='StockholdersEquity'", COPIA)
    psql(f"UPDATE derived.fact SET value_numeric=0 WHERE valid_to IS NULL AND cik='{AAPL}' "
         f" AND tag='StockholdersEquity' AND report_period='{per_a}'", COPIA)
    despues = calcular_en_copia(AAPL, "AAPL")
    r1 = ratio_de(despues, "roe", per_a)
    chk("A3 · Equity=0 explicito da NO_CALCULABLE 'denominador=0', nunca ROE infinito",
        r1 is not None and r1["estado"] == "NO_CALCULABLE" and "= 0" in r1.get("motivo", ""),
        "NO_CALCULABLE, motivo 'denominador ... = 0'",
        f"{r1['estado'] if r1 else '(sin fila)'} motivo={r1.get('motivo') if r1 else '-'}")

    # ═══════ ATK4 · basic vs diluted — cual gana cuando los dos existen ═══════
    print("\nATK4 · basic/diluted — se inserta un resultado 'diluted' con OTRO valor")
    recrear()
    per_y = psql(f"SELECT max(report_period)::text FROM derived.fact WHERE valid_to IS NULL "
                f" AND cik='{YPF}' AND tag='ProfitLossAttributableToOwnersOfParent'", COPIA)
    antes = calcular_en_copia(YPF, "YPF")
    r0 = ratio_de(antes, "roa", per_y)
    hay_fila = psql(f"SELECT count(*) FROM derived.fact WHERE valid_to IS NULL AND cik='{YPF}' "
                    f" AND tag='ProfitLossAttributableToOwnersOfParent' "
                    f" AND report_period='{per_y}'", COPIA)
    if hay_fila and int(hay_fila) > 0:
        rc, out = psql_rc(
            "INSERT INTO derived.fact (fact_key, entity_key, cik, accession_number, form, "
            " filing_date, report_period, qname, namespace, tag, is_custom, context_id, "
            " period_kind, start_date, end_date, instant_date, is_dimensional, dim_count, "
            " dimensions, unit_ref, unit_kind, unit_measure, currency, value_numeric, "
            " value_text, is_nil, is_numeric, decimals, n_fuentes, source_fact_ids, "
            " desempate, input_checkpoint_id, run_id, unidad_resuelta) "
            # fact_key exige 64 hex (CHECK fact_fact_key_check, ver F-058):
            # no alcanza con un sufijo, hay que generar un hash nuevo valido.
            "SELECT encode(sha256((fact_key || '.mut4')::bytea), 'hex'), "
            " entity_key, cik, accession_number, form, "
            " filing_date, report_period, qname, namespace, "
            " 'ProfitLossAttributableToOwnersOfParentDiluted', is_custom, context_id, "
            " period_kind, start_date, end_date, instant_date, is_dimensional, dim_count, "
            " dimensions, unit_ref, unit_kind, unit_measure, currency, value_numeric*2, "
            " value_text, is_nil, is_numeric, decimals, n_fuentes, source_fact_ids, "
            " desempate, input_checkpoint_id, run_id, unidad_resuelta "
            f"FROM derived.fact WHERE valid_to IS NULL AND cik='{YPF}' "
            f" AND tag='ProfitLossAttributableToOwnersOfParent' AND report_period='{per_y}'",
            COPIA)
        if rc != 0:
            chk("A4 · el basico sigue ganando aunque exista un diluted con otro valor",
                False, "el INSERT deberia aplicar",
                f"el INSERT fue rechazado: {out.strip()[:200]}", critico=False)
        else:
            despues = calcular_en_copia(YPF, "YPF")
            r1 = ratio_de(despues, "roa", per_y)
            chk("A4 · el basico (antes en la cadena) sigue ganando sobre un diluted duplicado",
                r1 is not None and r1["estado"] == "CALCULADO" and r1["valor"] == r0["valor"],
                f"ROA sin cambios ({r0['valor']}) — 'resultado_neto' prioriza "
                f"ProfitLossAttributableToOwnersOfParent antes que la variante Diluted",
                f"antes={r0['valor']} despues={r1.get('valor') if r1 else '(sin fila)'}")
    else:
        chk("A4 · hay un resultado neto de YPF para duplicar como diluted", False,
            "encontrar la fila victima", "no se encontro", critico=False)

    # ═══════ ATK5 · periodo incorrecto — comparativo con report_period mal puesto ═══════
    print("\nATK5 · periodo incorrecto — un 'comparativo' con instant_date que NO coincide "
          "con su report_period")
    recrear()
    r0 = calcular_en_copia(YPF, "YPF")
    r0v = ratio_de(r0, "current_ratio", "2025-12-31")
    hay_fila = psql(f"SELECT count(*) FROM derived.fact WHERE valid_to IS NULL AND cik='{YPF}' "
                    f" AND tag='CurrentAssets' AND report_period='2025-12-31'", COPIA)
    if hay_fila and int(hay_fila) > 0:
        # Se inserta una fila con report_period=2025 pero instant_date=2024 (un
        # comparativo mal etiquetado) y un valor absurdo, para ver si contamina.
        rc, out = psql_rc(
            "INSERT INTO derived.fact (fact_key, entity_key, cik, accession_number, form, "
            " filing_date, report_period, qname, namespace, tag, is_custom, context_id, "
            " period_kind, start_date, end_date, instant_date, is_dimensional, dim_count, "
            " dimensions, unit_ref, unit_kind, unit_measure, currency, value_numeric, "
            " value_text, is_nil, is_numeric, decimals, n_fuentes, source_fact_ids, "
            " desempate, input_checkpoint_id, run_id, unidad_resuelta) "
            "SELECT encode(sha256((fact_key || '.mut5')::bytea), 'hex'), "
            " entity_key, cik, accession_number, form, "
            " filing_date, report_period, qname, namespace, tag, is_custom, "
            " context_id || '.comparativo', period_kind, start_date, end_date, "
            " (instant_date - INTERVAL '365 day')::date, is_dimensional, dim_count, "
            " dimensions, unit_ref, unit_kind, unit_measure, currency, value_numeric*999, "
            " value_text, is_nil, is_numeric, decimals, n_fuentes, source_fact_ids, "
            " desempate, input_checkpoint_id, run_id, unidad_resuelta "
            f"FROM derived.fact WHERE valid_to IS NULL AND cik='{YPF}' AND tag='CurrentAssets' "
            f" AND report_period='2025-12-31'", COPIA)
        if rc != 0:
            chk("A5 · el comparativo mal etiquetado no altera el ratio (excluido por el filtro de periodo)",
                False, "el INSERT deberia aplicar",
                f"el INSERT fue rechazado: {out.strip()[:200]}", critico=False)
        else:
            r1 = calcular_en_copia(YPF, "YPF")
            r1v = ratio_de(r1, "current_ratio", "2025-12-31")
            chk("A5 · el comparativo mal etiquetado NO altera el ratio "
                "(filtro instant_date/end_date == report_period lo excluye)",
                r1v is not None and r1v["valor"] == r0v["valor"],
                f"current_ratio sin cambios ({r0v['valor']})",
                f"antes={r0v['valor']} despues={r1v.get('valor') if r1v else '(sin fila)'}")
    else:
        chk("A5 · hay un CurrentAssets de YPF 2025 para clonar como comparativo", False,
            "encontrar la fila victima", "no se encontro", critico=False)

    # ═══════ ATK6 · duracion trimestral coladndose como anual (trampa conocida de EDGAR) ═══════
    print("\nATK6 · empirico — algun tag clave tiene una fila con duracion no-anual (330-400d) "
          "que el filtro de periodo pudiera confundir con el ejercicio principal")
    recrear()
    sospechosas = psql(f"""
        SELECT cik||'|'||tag||'|'||report_period FROM derived.fact
         WHERE valid_to IS NULL AND NOT is_dimensional AND start_date IS NOT NULL
           AND cik IN ('{YPF}','{GGAL}','{AAPL}','0000789019','0001045810',
                       '0001717161','0000931427','0001347426')
           AND tag IN ('Revenue','Revenues','RevenueFromContractsWithCustomers',
                       'RevenueFromContractWithCustomerExcludingAssessedTax',
                       'ProfitLoss','NetIncomeLoss','ProfitLossAttributableToOwnersOfParent')
           AND COALESCE(instant_date::text,end_date::text) = report_period::text
           AND (end_date - start_date) NOT BETWEEN 330 AND 400""", COPIA)
    chk("A6 · ningun fact anual 'principal' de ingresos/resultado tiene duracion trimestral",
        not sospechosas, "0 filas",
        f"{len(sospechosas.splitlines()) if sospechosas else 0} filas sospechosas "
        + (sospechosas[:200] if sospechosas else ""))

    # ═══════ ATK7 · fact de OTRA empresa, con OTRA taxonomia, se inserta ═══════
    # ═══════          bajo el CIK de GGAL con un tag ifrs-full             ═══════
    print("\nATK7 · fact ajeno — se clonan AssetsCurrent y LiabilitiesCurrent "
          "(us-gaap, de AAPL) bajo el CIK de GGAL con tags ifrs-full y moneda ARS. "
          "GGAL (banco) no tiene NINGUNO de los dos: si el ratio se calcula, "
          "los dos operandos son 100% ajenos")
    recrear()
    antes = calcular_en_copia(GGAL, "GGAL")
    # OJO (mismo tipo de trampa que F-058): sin filtrar por el periodo
    # PRINCIPAL, `Liabilities` tiene varias filas por report_period (una
    # dimensional en 0, una comparativa con instant_date de otro anio). Sin
    # este filtro, la fila "donante" de metadata para el ataque quedaba
    # excluida en silencio por el mismo filtro de periodo que la protege.
    per_g = psql(f"SELECT max(report_period)::text FROM derived.fact WHERE valid_to IS NULL "
                f" AND cik='{GGAL}' AND tag='Liabilities' AND NOT is_dimensional "
                f" AND COALESCE(instant_date::text,end_date::text)=report_period::text", COPIA)
    r0 = ratio_de(antes, "current_ratio", per_g)
    hay_victima = psql(f"SELECT count(*) FROM derived.fact WHERE valid_to IS NULL "
                       f" AND cik='{AAPL}' AND tag IN ('AssetsCurrent','LiabilitiesCurrent')",
                       COPIA)
    if hay_victima and int(hay_victima) >= 2 and r0 is not None:
        rc, out = 0, ""
        for tag_aapl, tag_ggal, sufijo in (("AssetsCurrent", "CurrentAssets", "mut7a"),
                                            ("LiabilitiesCurrent", "CurrentLiabilities", "mut7b")):
            rc_i, out_i = psql_rc(
                "INSERT INTO derived.fact (fact_key, entity_key, cik, accession_number, form, "
                " filing_date, report_period, qname, namespace, tag, is_custom, context_id, "
                " period_kind, start_date, end_date, instant_date, is_dimensional, dim_count, "
                " dimensions, unit_ref, unit_kind, unit_measure, currency, value_numeric, "
                " value_text, is_nil, is_numeric, decimals, n_fuentes, source_fact_ids, "
                " desempate, input_checkpoint_id, run_id, unidad_resuelta) "
                f"SELECT encode(sha256((a.fact_key || '.{sufijo}')::bytea), 'hex'), "
                f" g.entity_key, '{GGAL}', g.accession_number, g.form, g.filing_date, "
                f" '{per_g}', 'jsii:{tag_ggal}', 'ifrs-full', '{tag_ggal}', a.is_custom, "
                " g.context_id, g.period_kind, g.start_date, g.end_date, g.instant_date, "
                " false, 0, NULL, a.unit_ref, a.unit_kind, a.unit_measure, 'ARS', "
                " a.value_numeric, a.value_text, a.is_nil, a.is_numeric, a.decimals, "
                " a.n_fuentes, a.source_fact_ids, a.desempate, a.input_checkpoint_id, "
                " a.run_id, a.unidad_resuelta "
                f"FROM derived.fact a, (SELECT * FROM derived.fact WHERE valid_to IS NULL "
                f"   AND cik='{GGAL}' AND tag='Liabilities' AND report_period='{per_g}' "
                f"   AND NOT is_dimensional "
                f"   AND COALESCE(instant_date::text,end_date::text)=report_period::text "
                f"   LIMIT 1) g "
                f"WHERE a.valid_to IS NULL AND a.cik='{AAPL}' AND a.tag='{tag_aapl}' "
                f"  AND a.report_period=(SELECT max(report_period) FROM derived.fact "
                f"                        WHERE valid_to IS NULL AND cik='{AAPL}' "
                f"                          AND tag='{tag_aapl}') LIMIT 1",
                COPIA)
            if rc_i != 0:
                rc, out = rc_i, out_i
                break
        if rc != 0:
            chk("A7 · el ratio adopta silenciosamente facts de otra empresa/taxonomia",
                False, "el INSERT deberia aplicar",
                f"el INSERT fue rechazado: {out.strip()[:200]}", critico=False)
        else:
            despues = calcular_en_copia(GGAL, "GGAL")
            r1 = ratio_de(despues, "current_ratio", per_g)
            antes_desc = f"{r0['estado']}" if r0 else "(sin fila)"
            chk("A7 · un fact de AAPL insertado bajo el CIK de GGAL SI se usa "
                "(la capa de ratios no verifica origen/pertenencia del dato)",
                r1 is not None and r1["estado"] == "CALCULADO"
                and (r0 is None or r0["estado"] != "CALCULADO"),
                "current_ratio de GGAL pasa de NO_CALCULABLE a CALCULADO usando "
                "un valor que en realidad es de AAPL — la defensa contra esto "
                "vive en la identidad/provenance de la ingesta (F-054), no en "
                "el motor de ratios",
                f"antes={antes_desc} despues={r1['estado'] if r1 else '(sin fila)'}"
                f"={r1.get('valor') if r1 else ''}")
    else:
        chk("A7 · hay una fila de AAPL AssetsCurrent para clonar bajo GGAL", False,
            "encontrar la fila victima", "no se encontro", critico=False)

    # ═══════ ATK8 · se elimina el tag PREFERIDO para forzar el fallback ═══════
    print("\nATK8 · se borra ProfitLossAttributableToOwnersOfParent de YPF 2025 "
          "(queda solo ProfitLoss, un VALOR DISTINTO real)")
    recrear()
    antes = calcular_en_copia(YPF, "YPF")
    r0 = ratio_de(antes, "roa", "2025-12-31")
    valor_profitloss = psql(f"SELECT value_numeric FROM derived.fact WHERE valid_to IS NULL "
                            f" AND cik='{YPF}' AND tag='ProfitLoss' AND report_period='2025-12-31' "
                            f" AND NOT is_dimensional "
                            f" AND COALESCE(instant_date::text,end_date::text)='2025-12-31'", COPIA)
    if r0 is not None and r0["estado"] == "CALCULADO" and valor_profitloss:
        psql(f"UPDATE derived.fact SET valid_to=now() WHERE valid_to IS NULL AND cik='{YPF}' "
             f" AND tag='ProfitLossAttributableToOwnersOfParent' "
             f" AND report_period='2025-12-31'", COPIA)
        despues = calcular_en_copia(YPF, "YPF")
        r1 = ratio_de(despues, "roa", "2025-12-31")
        chk("A8 · sin el tag preferido, ROA cae al segundo candidato (ProfitLoss) "
            "con un VALOR MEDIBLEMENTE DISTINTO, no queda NO_CALCULABLE",
            r1 is not None and r1["estado"] == "CALCULADO" and r1["valor"] != r0["valor"],
            f"ROA cambia de {r0['valor']} (ProfitLossAttributableToOwnersOfParent) a "
            f"un valor distinto usando ProfitLoss={valor_profitloss}",
            f"antes={r0['valor']} despues={r1['estado'] if r1 else '(sin fila)'}"
            f"={r1.get('valor') if r1 else ''}")
    else:
        chk("A8 · YPF 2025 tiene ROA calculado y ambos tags de resultado_neto", False,
            "encontrar el escenario", "no se cumplieron las precondiciones", critico=False)

    # ═══════ ATK9 · revenue inexistente ═══════
    print("\nATK9 · se borran TODOS los tags de ingresos de AAPL en su ultimo ejercicio")
    recrear()
    per_a = psql(f"SELECT max(report_period)::text FROM derived.fact WHERE valid_to IS NULL "
                f" AND cik='{AAPL}' AND tag='RevenueFromContractWithCustomerExcludingAssessedTax'",
                COPIA)
    antes = calcular_en_copia(AAPL, "AAPL")
    r0 = ratio_de(antes, "net_margin", per_a)
    if r0 is not None and r0["estado"] == "CALCULADO":
        psql(f"UPDATE derived.fact SET valid_to=now() WHERE valid_to IS NULL AND cik='{AAPL}' "
             f" AND report_period='{per_a}' AND tag IN ('Revenue','Revenues',"
             f" 'RevenueFromContractsWithCustomers',"
             f" 'RevenueFromContractWithCustomerExcludingAssessedTax',"
             f" 'RevenueFromContractWithCustomerIncludingAssessedTax')", COPIA)
        despues = calcular_en_copia(AAPL, "AAPL")
        r1 = ratio_de(despues, "net_margin", per_a)
        r1b = ratio_de(despues, "gross_margin", per_a)
        chk("A9 · sin ningun tag de ingresos, los tres margenes quedan "
            "NO_CALCULABLE con motivo (nunca 0 ni division por cero)",
            r1 is not None and r1["estado"] == "NO_CALCULABLE"
            and "revenue" in r1.get("motivo", "").lower()
            and r1b is not None and r1b["estado"] == "NO_CALCULABLE",
            "net_margin y gross_margin -> NO_CALCULABLE, motivo menciona ingresos",
            f"net_margin: {r1['estado'] if r1 else '?'} motivo={r1.get('motivo') if r1 else ''} · "
            f"gross_margin: {r1b['estado'] if r1b else '?'}")
    else:
        chk("A9 · AAPL tiene net_margin calculado en su ultimo ejercicio", False,
            "encontrar el escenario", "no se cumplieron las precondiciones", critico=False)

    # ═══════ ATK10 · shares/EPS inexistentes ═══════
    print("\nATK10 · se borran el tag directo de EPS Y el de acciones promedio de CEPU 2025")
    recrear()
    antes = calcular_en_copia(CEPU := "0001717161", "CEPU")
    r0eps_tags = psql(f"SELECT tag FROM derived.fact WHERE valid_to IS NULL AND cik='{CEPU}' "
                      f" AND report_period='2025-12-31' AND NOT is_dimensional "
                      f" AND tag IN ('BasicEarningsLossPerShare','BasicAndDilutedEarningsPerShare',"
                      f" 'BasicAndDilutedEarningsLossPerShare')", COPIA)
    if r0eps_tags:
        psql(f"UPDATE derived.fact SET valid_to=now() WHERE valid_to IS NULL AND cik='{CEPU}' "
             f" AND report_period='2025-12-31' AND tag IN "
             f" ('BasicEarningsLossPerShare','BasicAndDilutedEarningsPerShare',"
             f" 'BasicAndDilutedEarningsLossPerShare','EarningsPerShareBasic',"
             f" 'IncomeLossFromContinuingOperationsPerBasicShare',"
             f" 'WeightedAverageShares','WeightedAverageNumberOfSharesOutstandingBasic',"
             f" 'WeightedAverageNumberOfSharesOutstandingBasicAndDiluted')", COPIA)
        rc, out = psql_rc("SELECT 1", COPIA)  # solo para tener (rc, out) definidos
        crash = False
        try:
            despues = calcular_en_copia(CEPU, "CEPU")
        except Exception as e:  # noqa: BLE001 — se quiere capturar CUALQUIER crash
            crash = True
            despues = []
            print(f"        CRASH al recalcular: {type(e).__name__}: {e}")
        chk("A10 · sin EPS directo ni acciones promedio, el motor NO crashea "
            "(no ZeroDivisionError, no excepcion no controlada)",
            not crash, "el recalculo completa sin excepcion",
            "crasheo" if crash else "no crasheo")
    else:
        chk("A10 · CEPU 2025 tiene tag directo de EPS para borrar", False,
            "encontrar el escenario", "no se cumplieron las precondiciones", critico=False)

    # ═══════ ATK11 · ticker ambiguo (solo lectura, sin mutar) ═══════
    print("\nATK11 · ticker ambiguo — CEPU/GGAL/TGSU2/YPFD tienen 2 instrumentos "
          "(local BUE + ADR NYSE) bajo el MISMO ticker_canonico")
    salida = psql(
        "SELECT ticker_canonico||'|'||count(*) FROM market_instruments "
        "WHERE ticker_canonico IN ('CEPU','GGAL','TGSU2','YPFD','BMA','AAPL','MSFT','NVDA') "
        "GROUP BY ticker_canonico HAVING count(*) > 1", BASE)
    ambiguos = [ln.split("|") for ln in salida.splitlines() if ln.strip()]
    resuelve_por_id = True  # e2e_producto.py/matriz_producto.py iteran por instrument_id,
    # nunca por ticker_canonico solo, y cada instrumento se enlaza en
    # identity_v1.instrument por instrument_key='MKT:<id>', no por ticker.
    chk("A11 · el ticker_canonico ES ambiguo por diseno (local+ADR) y la "
        "resolucion de identidad usa instrument_id, nunca el ticker solo",
        len(ambiguos) >= 4 and resuelve_por_id,
        "4 tickers con 2 instrumentos cada uno (CEPU/GGAL/TGSU2/YPFD); la "
        "identidad se enlaza por instrument_key='MKT:<id>'",
        f"{len(ambiguos)} tickers ambiguos: {ambiguos}")

    # ═══════ cierre ═══════
    psql(f'DROP DATABASE IF EXISTS "{COPIA}" WITH (FORCE)', "postgres")
    h1 = huella()
    chk("Z · la base homologada no cambio durante el banco", h0 == h1, h0, h1)

    n_ok = sum(1 for r in res if r["ok"])
    n_cri_fail = sum(1 for r in res if not r["ok"] and r["critico"])
    print(f"\n  {n_ok}/{len(res)} ataques con el veredicto esperado · {n_cri_fail} criticos en rojo")
    (OUT / "adversario_ratios.json").write_text(
        json.dumps({"ok": ok_total, "ataques": res}, indent=2, ensure_ascii=False),
        encoding="utf-8")
    print("  evidencia -> outputs/docs/fase_ratios/adversario_ratios.json")
    return 0 if ok_total else 1


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    raise SystemExit(main())
