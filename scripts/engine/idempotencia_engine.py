#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fase E — idempotencia de S03/S04, comparando CONTENIDO.

Contar filas no alcanza. Los `fact_id` cambian entre corridas por diseño —la
secuencia avanza y nunca vuelve atrás, que es la garantía G2 de F-054—, así que
un digest que incluyera el id daría distinto siempre, sin que eso signifique nada.

Lo que debe ser estable es el CONTENIDO y la FORMA de la provenance:

  · parsed   (cik, accession, qname, context_id, unit_ref, valor, archivo)
  · derived  (cik, accession, qname, context_id, unit_ref, valor, moneda,
              n_fuentes, desempate)
  · forma de la provenance: para cada hecho derivado, el CONTENIDO de los hechos
    que lo respaldan, no sus ids

Corre sobre base descartable. La homologada no se toca: se verifica su huella
antes y después.

Uso:
    python scripts/engine/idempotencia_engine.py [--cik 0001717161] [--veces 3]
"""
from __future__ import annotations

import argparse
import hashlib
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
COPIA = "f055_idem"
S03 = REPO / "scripts" / "engine" / "s03_parse_ypf.py"
S04 = REPO / "scripts" / "engine" / "s04_normalize.py"


def psql(q: str, db: str = BASE) -> str:
    p = subprocess.run(["docker", "exec", CONT, "psql", "-U", "catalaxia", "-d", db,
                        "-t", "-A", "-F", "\x1f", "-c", q],
                       capture_output=True, text=True, encoding="utf-8")
    if p.returncode != 0:
        raise SystemExit(f"psql fallo ({db}): {p.stderr[:400]}")
    return p.stdout.strip()


def digest(q: str, db: str) -> tuple[str, int]:
    """md5 del resultado, insensible al orden de las filas."""
    filas = [l for l in psql(q, db).splitlines() if l.strip()]
    filas.sort()
    return hashlib.md5("\n".join(filas).encode()).hexdigest(), len(filas)


def huella(db: str = BASE) -> str:
    return psql("SELECT (SELECT count(*) FROM parsed.facts)||'|'||"
                "(SELECT count(*) FROM derived.fact WHERE valid_to IS NULL)||'|'||"
                "(SELECT count(DISTINCT cik) FROM parsed.facts)", db)


def correr(script: Path, args: list[str], db: str) -> int:
    env = dict(os.environ, ENGINE_DB_NAME=db)
    p = subprocess.run([sys.executable, str(script)] + args, capture_output=True,
                       text=True, encoding="utf-8", errors="replace",
                       cwd=str(REPO), env=env)
    return p.returncode


def foto(db: str, cik: str) -> dict:
    """Estado observable de un emisor, SIN los fact_id."""
    d_parsed, n_parsed = digest(f"""
        SELECT cik||'|'||accession_number||'|'||qname||'|'||context_id||'|'||
               coalesce(unit_ref,'')||'|'||coalesce(value_text,'')||'|'||
               coalesce(value_numeric::text,'')||'|'||coalesce(source_file,'')
          FROM parsed.facts WHERE cik='{cik}'""", db)
    d_ctx, n_ctx = digest(f"""
        SELECT accession_number||'|'||context_id||'|'||coalesce(start_date::text,'')||'|'||
               coalesce(end_date::text,'')||'|'||coalesce(instant_date::text,'')||'|'||
               period_kind||'|'||coalesce(dim_count::text,'')
          FROM parsed.contexts
         WHERE accession_number IN (SELECT DISTINCT accession_number
                                      FROM parsed.facts WHERE cik='{cik}')""", db)
    d_derived, n_derived = digest(f"""
        SELECT cik||'|'||accession_number||'|'||qname||'|'||context_id||'|'||
               coalesce(unit_ref,'')||'|'||coalesce(value_numeric::text,'')||'|'||
               coalesce(currency,'')||'|'||n_fuentes||'|'||coalesce(desempate,'')
          FROM derived.fact WHERE valid_to IS NULL AND cik='{cik}'""", db)
    # forma de la provenance: el CONTENIDO de las fuentes, no sus ids
    d_prov, n_prov = digest(f"""
        SELECT d.qname||'|'||d.context_id||'|'||string_agg(
                 p.qname||'~'||coalesce(p.value_text,'')||'~'||coalesce(p.source_file,''),
                 ';' ORDER BY p.qname, p.value_text, p.source_file)
          FROM derived.fact d
          CROSS JOIN LATERAL unnest(d.source_fact_ids) s(fid)
          JOIN parsed.facts p ON p.fact_id = s.fid
         WHERE d.valid_to IS NULL AND d.cik='{cik}'
         GROUP BY d.fact_key, d.qname, d.context_id""", db)
    contam = psql(f"""
        SELECT count(*) FILTER (WHERE p.cik IS NOT NULL AND p.cik <> d.cik)||'|'||
               count(*) FILTER (WHERE p.fact_id IS NULL)
          FROM derived.fact d
          CROSS JOIN LATERAL unnest(d.source_fact_ids) s(fid)
          LEFT JOIN parsed.facts p ON p.fact_id = s.fid
         WHERE d.valid_to IS NULL""", db)
    aj, col = contam.split("|")
    filas_parsed = int(psql(f"SELECT count(*) FROM parsed.facts WHERE cik='{cik}'", db))
    filas_derived = int(psql(f"SELECT count(*) FROM derived.fact "
                             f" WHERE valid_to IS NULL AND cik='{cik}'", db))
    return {"parsed": d_parsed, "n_parsed": filas_parsed, "lineas_parsed": n_parsed,
            "n_derived_filas": filas_derived,
            "contextos": d_ctx, "n_contextos": n_ctx,
            "derived": d_derived, "n_derived": filas_derived,
            "lineas_derived": n_derived,
            "provenance": d_prov, "n_provenance": n_prov,
            "ajenos": int(aj), "colgados": int(col),
            "rango_ids": psql(f"SELECT min(fact_id)||'-'||max(fact_id) "
                              f" FROM parsed.facts WHERE cik='{cik}'", db)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cik", default="0001717161", help="emisor a reprocesar")
    ap.add_argument("--veces", type=int, default=3)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    # El guard mira solo el workstream Engine. Una corrida de CNV en paralelo
    # no toca `parsed` ni `derived`, y bloquearse por ella dejaria la fase E sin
    # correr por una razon ajena al objeto de la prueba.
    en_vuelo = psql("SELECT coalesce(string_agg(pipeline_version,','),'') "
                    " FROM engine.runs WHERE status='RUNNING' "
                    "   AND pipeline_version NOT LIKE 'cnv%'")
    if en_vuelo:
        print(f"ABORTADO: hay pipeline de Engine en vuelo ({en_vuelo}).")
        return 2
    ajenas = psql("SELECT coalesce(string_agg(pipeline_version,','),'') "
                  " FROM engine.runs WHERE status='RUNNING'")
    if ajenas:
        print(f"  aviso: corridas de otro workstream en vuelo ({ajenas}); "
              f"la copia se hace por pg_dump, que no las bloquea")
    h0 = huella()
    print(f"IDEMPOTENCIA DE S03/S04 — CIK {a.cik}, {a.veces} corridas")
    print(f"  huella de la homologada al empezar: {h0}\n")

    # `CREATE DATABASE ... TEMPLATE` exige que NADIE este conectado a la
    # plantilla. Con otro workstream operando eso no se puede garantizar, asi
    # que la copia va por pg_dump: da un snapshot transaccionalmente consistente
    # sin pedir exclusividad.
    print("  copiando la base por pg_dump (sin exigir exclusividad)...")
    psql(f'DROP DATABASE IF EXISTS "{COPIA}" WITH (FORCE)', "postgres")
    psql(f'CREATE DATABASE "{COPIA}"', "postgres")
    psql(f'GRANT ALL ON DATABASE "{COPIA}" TO catalaxia_engine', "postgres")
    vol = subprocess.run(
        ["docker", "exec", CONT, "bash", "-c",
         f"pg_dump -U catalaxia -d {BASE} | psql -q -U catalaxia -d {COPIA}"],
        capture_output=True, text=True, encoding="utf-8")
    if vol.returncode != 0:
        raise SystemExit(f"pg_dump fallo: {vol.stderr[-600:]}")
    n = psql("SELECT count(*) FROM parsed.facts", COPIA)
    print(f"  copia lista: {int(n):,} filas en parsed.facts")

    base_foto = foto(COPIA, a.cik)
    print(f"  baseline en la copia: parsed={base_foto['n_parsed']:,} "
          f"derived={base_foto['n_derived']:,} ids {base_foto['rango_ids']}")

    fotos = []
    for i in range(1, a.veces + 1):
        rc3 = correr(S03, ["--cik", a.cik, "--min-xbrl", "1"], COPIA)
        rc4 = correr(S04, [], COPIA)
        f = foto(COPIA, a.cik)
        f["corrida"], f["rc_s03"], f["rc_s04"] = i, rc3, rc4
        fotos.append(f)
        print(f"  corrida {i}: S03={rc3} S04={rc4} · parsed={f['n_parsed']:,} "
              f"derived={f['n_derived']:,} · ids {f['rango_ids']}")

    print()
    res, ok_total = [], True

    def chk(n, cond, det=""):
        nonlocal ok_total
        print(f"  {'OK   ' if cond else 'FALLA'} {n:<54} {det}")
        res.append({"control": n, "ok": bool(cond), "detalle": str(det)[:300]})
        if not cond:
            ok_total = False

    # E0 · re-parsear hoy, ¿reproduce lo que la base ya tenia?
    a1 = fotos[0]
    chk("E0 · el re-parseo reproduce el contenido que ya estaba en la base",
        a1["parsed"] == base_foto["parsed"] and a1["derived"] == base_foto["derived"],
        f"parsed {base_foto['n_parsed']:,}->{a1['n_parsed']:,} · "
        f"derived {base_foto['n_derived']:,}->{a1['n_derived']:,}")

    a2, a3 = fotos[1], fotos[-1]
    for campo, etiqueta in (("parsed", "contenido de parsed.facts"),
                            ("contextos", "contenido de parsed.contexts"),
                            ("derived", "contenido de derived.fact"),
                            ("provenance", "forma de la provenance")):
        chk(f"E1 · {etiqueta} estable entre corridas", a2[campo] == a3[campo],
            f"{a2[campo][:16]} vs {a3[campo][:16]}")

    chk("E2 · sin crecimiento espurio de filas",
        a2["n_parsed"] == a3["n_parsed"] and a2["n_derived"] == a3["n_derived"],
        f"parsed {a2['n_parsed']:,}={a3['n_parsed']:,} · "
        f"derived {a2['n_derived']:,}={a3['n_derived']:,}")
    chk("E3 · sin contaminacion ni punteros colgados en ninguna corrida",
        all(f["ajenos"] == 0 and f["colgados"] == 0 for f in fotos),
        ", ".join(f"c{f['corrida']}:{f['ajenos']}/{f['colgados']}" for f in fotos))

    rangos = [f["rango_ids"] for f in fotos]
    chk("E4 · los fact_id AVANZAN en cada corrida (G2 en accion)",
        len(set(rangos)) == len(rangos),
        " → ".join(rangos))

    psql(f'DROP DATABASE IF EXISTS "{COPIA}" WITH (FORCE)', "postgres")
    h1 = huella()
    chk("E5 · la base homologada no cambio", h0 == h1, f"{h0} -> {h1}")

    # el conteo va DESPUES de E5: calcularlo antes reportaba 8/9 cuando los
    # nueve controles pasaban.
    n_ok = sum(1 for r in res if r["ok"])
    print(f"\n  {n_ok}/{len(res)} controles OK")
    (OUT / "idempotencia.json").write_text(
        json.dumps({"ok": ok_total, "cik": a.cik, "fotos": fotos, "controles": res},
                   indent=2, ensure_ascii=False), encoding="utf-8")
    print("  evidencia -> outputs/docs/auditoria/idempotencia.json")
    return 0 if ok_total else 1


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    raise SystemExit(main())
