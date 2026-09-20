#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Banco MUTACIONAL y ADVERSARIO de F-054 y F-055 — base DESCARTABLE.

Un control que sólo sabe aprobar no prueba nada. Este banco revierte cada
garantía POR SEPARADO y exige saber cuál bloquea qué. No alcanza con "falló":
hay que identificar la invariante responsable.

Dos garantías distintas intervienen en F-054 y conviene no confundirlas:

  G1  el borrado tiene ALCANCE  (DELETE ... WHERE cik = X)
  G2  la secuencia de fact_id NO se reinicia

Predicción antes de medir:
  - sin G1 y sin G2  -> CONTAMINACION: ids reutilizados, punteros de otra empresa
  - sin G1, con G2   -> punteros COLGADOS: se pierde la provenance, sin mezclarla
  - con G1, sin G2   -> los ids nuevos chocan con los que sobrevivieron:
                        violacion de clave primaria, fallo RUIDOSO

Si la realidad no coincide con esa predicción, la explicación del arreglo es
incorrecta aunque los números den bien.

La base homologada NO se toca: se verifica su huella antes y después.
"""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "outputs" / "docs" / "auditoria"
CONT = "catalaxia-engine-dev"
BASE = "catalaxia"
COPIA = "f054_mut"
S03 = REPO / "scripts" / "engine" / "s03_parse_ypf.py"
S04 = REPO / "scripts" / "engine" / "s04_normalize.py"
MUT = REPO / "scripts" / "engine" / "_mutado_tmp.py"

CEPU, TGS = "0001717161", "0000931427"

BLOQUE_ACTUAL = '''        cur.execute("SELECT DISTINCT run_id FROM parsed.facts WHERE cik = %s "
                    " UNION SELECT DISTINCT run_id FROM parsed.pre_xbrl_filings "
                    "  WHERE cik = %s", (GOLDEN_CIK, GOLDEN_CIK))
        runs_previos = [r[0] for r in cur.fetchall()]
        cur.execute("DELETE FROM parsed.facts WHERE cik = %s", (GOLDEN_CIK,))
        cur.execute("DELETE FROM parsed.pre_xbrl_filings WHERE cik = %s", (GOLDEN_CIK,))
        if runs_previos:
            for table in ("parsed.contexts", "parsed.units", "parsed.concepts",
                          "parsed.link_relations", "parsed.companyfacts_compare",
                          "parsed.parse_errors"):
                cur.execute(f"DELETE FROM {table} WHERE run_id = ANY(%s)", (runs_previos,))'''

RESET = ('        cur.execute("SELECT setval(pg_get_serial_sequence('
         "'parsed.facts','fact_id'), 1, false)\")")
BORRA_TODO = ('        for table in PARSED_TABLES:\n'
              '            cur.execute(f"DELETE FROM {table}")')

VARIANTES = {
    # nombre                     bloque de reemplazo
    "sin_G1_sin_G2": BORRA_TODO + "\n" + RESET,          # el codigo original
    "sin_G1_con_G2": BORRA_TODO,                          # borra todo, no resetea
    "con_G1_sin_G2": BLOQUE_ACTUAL + "\n" + RESET,        # alcance, pero resetea
}


def psql(q: str, db: str = BASE) -> str:
    p = subprocess.run(["docker", "exec", CONT, "psql", "-U", "catalaxia", "-d", db,
                        "-t", "-A", "-c", q], capture_output=True, text=True,
                       encoding="utf-8")
    if p.returncode != 0:
        raise SystemExit(f"psql fallo ({db}): {p.stderr[:400]}")
    return p.stdout.strip()


def psql_rc(q: str, db: str) -> tuple[int, str]:
    p = subprocess.run(["docker", "exec", CONT, "psql", "-U", "catalaxia", "-d", db,
                        "-t", "-A", "-v", "ON_ERROR_STOP=1", "-c", q],
                       capture_output=True, text=True, encoding="utf-8")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def huella(db: str = BASE) -> str:
    return psql("SELECT (SELECT count(*) FROM parsed.facts)||'|'||"
                "(SELECT count(*) FROM derived.fact WHERE valid_to IS NULL)||'|'||"
                "(SELECT count(DISTINCT cik) FROM parsed.facts)||'|'||"
                "(SELECT count(*) FROM parsed.contexts)", db)


def estado_provenance(db: str) -> dict:
    r = psql("""
        SELECT count(*) FILTER (WHERE p.cik IS NOT NULL AND p.cik <> d.cik)||'|'||
               count(*) FILTER (WHERE p.fact_id IS NULL)||'|'||count(*)
          FROM derived.fact d
          CROSS JOIN LATERAL unnest(d.source_fact_ids) s(fid)
          LEFT JOIN parsed.facts p ON p.fact_id = s.fid
         WHERE d.valid_to IS NULL""", db)
    a, c, t = r.split("|")
    return {"ajenos": int(a), "colgados": int(c), "punteros": int(t)}


def recrear() -> None:
    psql(f'DROP DATABASE IF EXISTS "{COPIA}" WITH (FORCE)', "postgres")
    psql(f'CREATE DATABASE "{COPIA}" TEMPLATE "{BASE}"', "postgres")
    psql(f'GRANT ALL ON DATABASE "{COPIA}" TO catalaxia_engine', "postgres")


def correr(script: Path, args: list[str], db: str) -> tuple[int, str]:
    env = dict(os.environ, ENGINE_DB_NAME=db)
    p = subprocess.run([sys.executable, str(script)] + args, capture_output=True,
                       text=True, encoding="utf-8", errors="replace",
                       cwd=str(REPO), env=env)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def variante(nombre: str) -> Path:
    src = S03.read_text(encoding="utf-8")
    if BLOQUE_ACTUAL not in src:
        raise SystemExit("no se encontro el bloque corregido en S03")
    MUT.write_text(src.replace(BLOQUE_ACTUAL, VARIANTES[nombre], 1), encoding="utf-8")
    return MUT


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    res, ok_total = [], True

    def chk(n, cond, det=""):
        nonlocal ok_total
        print(f"  {'OK   ' if cond else 'FALLA'} {n:<54} {det}")
        res.append({"escenario": n, "ok": bool(cond), "detalle": str(det)[:400]})
        if not cond:
            ok_total = False

    if psql("SELECT count(*) FROM engine.runs WHERE status='RUNNING'") != "0":
        print("ABORTADO: hay pipeline en vuelo; la copia no seria consistente.")
        return 2

    h0 = huella()
    print("BANCO MUTACIONAL Y ADVERSARIO — F-054 / F-055")
    print(f"  huella de la homologada al empezar: {h0}\n")

    # ═══════════════ F-054 · dissección de garantías ═══════════════
    print("F-054 · que invariante bloquea la contaminacion")
    print("        escenario: parsear CEPU sobre una base que ya tiene 8 emisores\n")

    recrear()
    base_prov = estado_provenance(COPIA)
    chk("M0 · la copia arranca sin contaminacion",
        base_prov["ajenos"] == 0 and base_prov["colgados"] == 0,
        f"ajenos={base_prov['ajenos']} colgados={base_prov['colgados']} "
        f"de {base_prov['punteros']:,}")

    # --- codigo actual: G1 + G2 ---
    rc3, o3 = correr(S03, ["--cik", CEPU, "--min-xbrl", "1"], COPIA)
    rc4, _ = correr(S04, [], COPIA) if rc3 == 0 else (1, "")
    act = estado_provenance(COPIA)
    chk("M1 · con G1+G2: re-parsear CEPU no contamina a los otros 7",
        rc3 == 0 and rc4 == 0 and act["ajenos"] == 0 and act["colgados"] == 0,
        f"S03={rc3} S04={rc4} ajenos={act['ajenos']} colgados={act['colgados']}")

    # --- sin G1 y sin G2: la secuencia HISTORICA completa ---
    #
    # Una sola corrida mutada NO reproduce el defecto sobre esta base: los
    # fact_id vivos arrancan en 12.841, asi que al reiniciar la secuencia los
    # ids nuevos (1..N) caen en una zona que NINGUN puntero de `derived`
    # referencia. Para reproducirlo hay que recorrer la secuencia entera:
    #
    #   A parseado con la secuencia en 1  ->  S04 fija los punteros de A en 1..N
    #   B parseado con la secuencia en 1  ->  B ocupa 1..M
    #   los punteros de A ahora resuelven contra filas de B
    recrear()
    correr(variante("sin_G1_sin_G2"), ["--cik", CEPU, "--min-xbrl", "1"], COPIA)
    correr(S04, [], COPIA)
    ids_a = psql(f"SELECT min(fact_id)||'-'||max(fact_id) FROM parsed.facts "
                 f" WHERE cik='{CEPU}'", COPIA)
    prov_a = estado_provenance(COPIA)
    correr(variante("sin_G1_sin_G2"), ["--cik", TGS, "--min-xbrl", "1"], COPIA)
    ids_b = psql(f"SELECT min(fact_id)||'-'||max(fact_id) FROM parsed.facts "
                 f" WHERE cik='{TGS}'", COPIA)
    m2 = estado_provenance(COPIA)
    print(f"     paso 1 · CEPU parseado, secuencia reiniciada : ids {ids_a}")
    print(f"              S04 fija sus punteros               : ajenos={prov_a['ajenos']}")
    print(f"     paso 2 · TGS parseado, secuencia reiniciada  : ids {ids_b}")
    ajenos_cepu = psql(f"""
        SELECT count(*) FROM derived.fact d
         CROSS JOIN LATERAL unnest(d.source_fact_ids) s(fid)
          JOIN parsed.facts p ON p.fact_id = s.fid
         WHERE d.valid_to IS NULL AND d.cik='{CEPU}' AND p.cik <> d.cik""", COPIA)
    print(f"              punteros de CEPU que caen en filas de TGS: {int(ajenos_cepu):,}")
    chk("M2 · sin G1 ni G2: la CONTAMINACION historica reaparece",
        int(ajenos_cepu) > 0,
        f"{int(ajenos_cepu):,} punteros de CEPU resuelven a hechos de TGS "
        f"(total ajenos en la base: {m2['ajenos']:,})")

    # --- sin G1, con G2: se pierde, no se mezcla ---
    recrear()
    correr(variante("sin_G1_con_G2"), ["--cik", CEPU, "--min-xbrl", "1"], COPIA)
    m3 = estado_provenance(COPIA)
    chk("M3 · sin G1 pero con G2: punteros COLGADOS, sin mezcla",
        m3["colgados"] > 0 and m3["ajenos"] == 0,
        f"ajenos={m3['ajenos']} colgados={m3['colgados']:,} de {m3['punteros']:,}")

    # --- con G1, sin G2 ---
    #
    # Prediccion original: "la PK rechaza el id repetido, fallo ruidoso".
    # ES FALSA EN GENERAL, y la base lo demuestra: con el borrado acotado las
    # filas de los otros emisores sobreviven en 12.841+, y la secuencia
    # reiniciada reparte 1..N en una franja libre. No hay choque, no hay error,
    # y sin embargo el invariante "un fact_id designa un hecho para siempre" ya
    # quedo roto para las corridas futuras. La PK protege SOLO donde los rangos
    # se pisan.
    recrear()
    rc_a, out_a = correr(variante("con_G1_sin_G2"), ["--cik", CEPU, "--min-xbrl", "1"], COPIA)
    m4a = estado_provenance(COPIA)
    ids_libre = psql(f"SELECT min(fact_id)||'-'||max(fact_id) FROM parsed.facts "
                     f" WHERE cik='{CEPU}'", COPIA)
    chk("M4a · con G1 sin G2 y franja libre: NO falla, pero el id ya no es unico en el tiempo",
        rc_a == 0 and m4a["ajenos"] == 0,
        f"rc={rc_a} CEPU quedo en {ids_libre}; la PK no intervino")

    # el mismo escenario, forzando el solape: ahi si la PK es la barrera
    recrear()
    tope = psql(f"SELECT min(fact_id) FROM parsed.facts WHERE cik <> '{CEPU}'", COPIA)
    src = S03.read_text(encoding="utf-8")
    reset_colision = ('        cur.execute("SELECT setval(pg_get_serial_sequence('
                      f"'parsed.facts','fact_id'), {tope}, false)\")")
    MUT.write_text(src.replace(BLOQUE_ACTUAL, BLOQUE_ACTUAL + "\n" + reset_colision, 1),
                   encoding="utf-8")
    rc_b, out_b = correr(MUT, ["--cik", CEPU, "--min-xbrl", "1"], COPIA)
    dup = ("duplicate key" in out_b.lower() or "llave duplicada" in out_b.lower()
           or "facts_pkey" in out_b.lower())
    chk("M4b · con G1 sin G2 y rangos que se pisan: la PK rechaza (fallo RUIDOSO)",
        rc_b != 0 and dup, f"rc={rc_b} secuencia forzada a {tope} · pk_violada={dup}")
    if not dup and rc_b != 0:
        print(f"        motivo real: {next((l for l in out_b.splitlines() if 'rror' in l), '')[:120]}")

    MUT.unlink(missing_ok=True)

    # --- el escenario historico, explicitamente ---
    print("\n   el escenario historico (YPF -> replace-all de GGAL -> YPF apunta a GGAL)")
    recrear()
    x = psql("SELECT fact_id FROM parsed.facts WHERE cik='0000904851' ORDER BY fact_id LIMIT 1",
             COPIA)
    duenio_antes = psql(f"SELECT cik FROM parsed.facts WHERE fact_id={x}", COPIA)
    rc, _ = correr(S03, ["--cik", "0001114700", "--min-xbrl", "1"], COPIA)
    correr(S04, [], COPIA)
    duenio_despues = psql(f"SELECT coalesce((SELECT cik FROM parsed.facts "
                          f" WHERE fact_id={x}),'(no existe)')", COPIA)
    print(f"     fact_id {x}: duenio antes={duenio_antes} · despues del replace-all "
          f"de GGAL={duenio_despues}")
    chk("M5 · un replace-all de GGAL no cambia el duenio de un fact_id de YPF",
        duenio_antes == duenio_despues == "0000904851",
        f"{duenio_antes} -> {duenio_despues}")

    # ═══════════════ F-055 · banco adversario de contextos ═══════════════
    print("\nF-055 · ataques sobre la equivalencia de contextos")
    print("        cada ataque declara el veredicto ESPERADO antes de medirlo\n")

    SQL_CANON = """
    SELECT accession_number, context_id, start_date, end_date, instant_date, period_kind,
      CASE WHEN jsonb_typeof(dimensions)='array'
           THEN (SELECT jsonb_agg(x ORDER BY x::text)
                   FROM jsonb_array_elements(dimensions) x) ELSE dimensions END d1,
      CASE WHEN jsonb_typeof(typed_dimensions)='array'
           THEN (SELECT jsonb_agg(y ORDER BY y::text) FROM (
                   SELECT CASE WHEN x ? 'content'
                               THEN jsonb_set(x,'{content}', to_jsonb(regexp_replace(
                                      x->>'content','\\s+xmlns(:[-\\w.]+)?="[^"]*"','','g')))
                               ELSE x END y
                     FROM jsonb_array_elements(typed_dimensions) x) q)
           ELSE typed_dimensions END d2
      FROM parsed.contexts"""

    def conflictos(db: str) -> int:
        return int(psql(f"""
            SELECT count(*) FROM (SELECT accession_number, context_id FROM ({SQL_CANON}) z
              GROUP BY 1,2 HAVING count(DISTINCT (start_date,end_date,instant_date,
                period_kind,d1,d2)::text) > 1) y""", db))

    recrear()
    linea_base = conflictos(COPIA)
    print(f"     conflictos en la copia limpia: {linea_base}")

    # el contexto victima: uno con al menos 2 dimensiones, para poder permutarlas
    victima = psql("""
        SELECT ctx_id||'|'||accession_number||'|'||context_id FROM parsed.contexts
         WHERE jsonb_typeof(dimensions)='array' AND jsonb_array_length(dimensions) >= 2
         ORDER BY ctx_id LIMIT 1""", COPIA)
    if not victima:
        chk("A0 · hay un contexto con >=2 dimensiones para atacar", False, "no se encontro")
    else:
        cid, acc, ctxid = victima.split("|")
        print(f"     contexto victima: ctx_id={cid} accession={acc} context_id={ctxid}\n")

        ATAQUES = [
            ("A1 · permutar el ORDEN de las dimensiones", "NO debe generar conflicto", False,
             f"""INSERT INTO parsed.contexts (run_id,entity_id,accession_number,context_id,
                   scheme,identifier,start_date,end_date,instant_date,period_kind,
                   dimensions,typed_dimensions,dim_count,has_typed,source_file,source_hash)
                 SELECT run_id,entity_id,accession_number,context_id,scheme,identifier,
                   start_date,end_date,instant_date,period_kind,
                   (SELECT jsonb_agg(x ORDER BY x::text DESC)
                      FROM jsonb_array_elements(dimensions) x),
                   typed_dimensions,dim_count,has_typed,source_file||'.permutado',source_hash
                   FROM parsed.contexts WHERE ctx_id={cid}"""),
            ("A2 · duplicado IDENTICO del contexto", "NO debe generar conflicto", False,
             f"""INSERT INTO parsed.contexts (run_id,entity_id,accession_number,context_id,
                   scheme,identifier,start_date,end_date,instant_date,period_kind,
                   dimensions,typed_dimensions,dim_count,has_typed,source_file,source_hash)
                 SELECT run_id,entity_id,accession_number,context_id,scheme,identifier,
                   start_date,end_date,instant_date,period_kind,dimensions,typed_dimensions,
                   dim_count,has_typed,source_file||'.copia',source_hash
                   FROM parsed.contexts WHERE ctx_id={cid}"""),
            ("A3 · cambiar un MIEMBRO de dimension", "DEBE generar conflicto", True,
             f"""INSERT INTO parsed.contexts (run_id,entity_id,accession_number,context_id,
                   scheme,identifier,start_date,end_date,instant_date,period_kind,
                   dimensions,typed_dimensions,dim_count,has_typed,source_file,source_hash)
                 SELECT run_id,entity_id,accession_number,context_id,scheme,identifier,
                   start_date,end_date,instant_date,period_kind,
                   jsonb_set(dimensions,'{{0,member}}','"zz:MiembroFalso"'),
                   typed_dimensions,dim_count,has_typed,source_file||'.miembro',source_hash
                   FROM parsed.contexts WHERE ctx_id={cid}"""),
            ("A4 · cambiar el PERIODO (end_date + 1 dia)", "DEBE generar conflicto", True,
             f"""INSERT INTO parsed.contexts (run_id,entity_id,accession_number,context_id,
                   scheme,identifier,start_date,end_date,instant_date,period_kind,
                   dimensions,typed_dimensions,dim_count,has_typed,source_file,source_hash)
                 SELECT run_id,entity_id,accession_number,context_id,scheme,identifier,
                   start_date,end_date + INTERVAL '1 day',instant_date,period_kind,
                   dimensions,typed_dimensions,dim_count,has_typed,
                   source_file||'.periodo',source_hash
                   FROM parsed.contexts WHERE ctx_id={cid} AND end_date IS NOT NULL"""),
            ("A5 · cambiar DURATION por INSTANT", "DEBE generar conflicto", True,
             f"""INSERT INTO parsed.contexts (run_id,entity_id,accession_number,context_id,
                   scheme,identifier,start_date,end_date,instant_date,period_kind,
                   dimensions,typed_dimensions,dim_count,has_typed,source_file,source_hash)
                 SELECT run_id,entity_id,accession_number,context_id,scheme,identifier,
                   NULL,NULL,end_date,'INSTANT',
                   dimensions,typed_dimensions,dim_count,has_typed,
                   source_file||'.instant',source_hash
                   FROM parsed.contexts WHERE ctx_id={cid} AND end_date IS NOT NULL"""),
            ("A6 · cambiar la ENTIDAD del contexto", "DEBE generar conflicto", True,
             f"""INSERT INTO parsed.contexts (run_id,entity_id,accession_number,context_id,
                   scheme,identifier,start_date,end_date,instant_date,period_kind,
                   dimensions,typed_dimensions,dim_count,has_typed,source_file,source_hash)
                 SELECT run_id,entity_id,accession_number,context_id,scheme,'0000000000',
                   start_date,end_date,instant_date,period_kind,
                   dimensions,typed_dimensions,dim_count,has_typed,
                   source_file||'.entidad',source_hash
                   FROM parsed.contexts WHERE ctx_id={cid}"""),
            ("A7 · agregar una dimension mas", "DEBE generar conflicto", True,
             f"""INSERT INTO parsed.contexts (run_id,entity_id,accession_number,context_id,
                   scheme,identifier,start_date,end_date,instant_date,period_kind,
                   dimensions,typed_dimensions,dim_count,has_typed,source_file,source_hash)
                 SELECT run_id,entity_id,accession_number,context_id,scheme,identifier,
                   start_date,end_date,instant_date,period_kind,
                   dimensions || '[{{"typed":false,"member":"zz:Extra",
                     "container":"segment","dimension":"zz:EjeExtra"}}]'::jsonb,
                   typed_dimensions,dim_count+1,has_typed,source_file||'.extra',source_hash
                   FROM parsed.contexts WHERE ctx_id={cid}"""),
        ]
        hallazgos = []
        for nombre, esperado, debe_conflictuar, sql_ins in ATAQUES:
            recrear()
            rc_i, out_i = psql_rc(sql_ins, COPIA)
            if rc_i != 0:
                chk(nombre, False, f"el INSERT del ataque fallo: {out_i.strip()[:90]}")
                continue
            n = conflictos(COPIA)
            hubo = n > linea_base
            ok = hubo == debe_conflictuar
            chk(nombre, ok, f"esperado: {esperado} · real: "
                            f"{'conflicto' if hubo else 'equivalentes'} (n={n})")
            if not ok:
                hallazgos.append({"ataque": nombre, "esperado": esperado,
                                  "real": "conflicto" if hubo else "equivalentes"})

    # ═══════════════ cierre ═══════════════
    psql(f'DROP DATABASE IF EXISTS "{COPIA}" WITH (FORCE)', "postgres")
    MUT.unlink(missing_ok=True)
    h1 = huella()
    chk("Z · la base homologada no cambio durante el banco", h0 == h1, f"{h0} -> {h1}")

    n_ok = sum(1 for r in res if r["ok"])
    print(f"\n  {n_ok}/{len(res)} escenarios OK")
    (OUT / "f054_f055_mutacional.json").write_text(
        json.dumps({"ok": ok_total, "escenarios": res}, indent=2, ensure_ascii=False),
        encoding="utf-8")
    print("  evidencia -> outputs/docs/auditoria/f054_f055_mutacional.json")
    return 0 if ok_total else 1


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    raise SystemExit(main())
