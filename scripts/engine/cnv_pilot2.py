#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CNV PILOT 2 — validación multi-emisor.

Mide cobertura REAL sobre una muestra diversa tomada de Identity v1. No maximiza
cobertura: demuestra qué funciona, qué queda bloqueado y por qué.

SALVAGUARDA (la que faltó en CNV_NEGATIVE_PILOT_20)
El fetcher se invoca SOLO si `resolver_en_identity_v1` devuelve ok=True. Es un
`continue`, no un `print`: un caso no elegible no puede llegar al fetcher aunque
el universo esté mal construido.

Uso:
    python scripts/engine/cnv_pilot2.py [--fetch] [--repeticiones 2]

Sin `--fetch` no se descarga nada: sólo se resuelve elegibilidad (solo lectura).
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
OUT = REPO / "outputs" / "docs" / "fase_cnv"
CONT = "catalaxia-engine-dev"
FETCHER = REPO / "scripts" / "engine" / "c3_cnv_fetch.py"

from engine.config import load_settings  # noqa: E402
from engine.db import get_admin_engine  # noqa: E402

import importlib.util  # noqa: E402
_spec = importlib.util.spec_from_file_location("c3", FETCHER)
c3 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(c3)

# Muestra deliberada. Cada caso declara POR QUE fue elegido.
# Nada se inventa: todos salen de identity_v1 tal como esta hoy.
CASOS = [
    ("A", "CEPU", "33650305499", None,
     "caso positivo conocido: CUIT autoritativo, unica entidad"),
    ("B", "YPF", "30546689979", None,
     "positivo con bridge CIK->LEI->CUIT; el de mayor volumen (2.498 artefactos)"),
    ("B", "TGSU2", "30657862068", None,
     "positivo con bridge; volumen intermedio (1.076 artefactos)"),
    ("B*", "YPF por CIK", None, "0000904851",
     "el mismo positivo por la OTRA puerta de entrada: --cik en vez de --cuit"),
    ("D", "Banco Galicia y Bs.As.", "30500001735", None,
     "AMBIGUO: el CUIT resuelve a 3 entidades distintas"),
    ("D", "Aeropuertos Argentina 2000", "30696170580", None,
     "AMBIGUO: 3 entidades"),
    ("D", "YPF Energia Electrica", "30714128309", None,
     "AMBIGUO: 3 entidades. Ademas comparte nombre con un positivo (YPF)"),
    ("D", "Banco Supervielle", "33500005179", None,
     "AMBIGUO: 3 entidades. Coexiste con 'Grupo Supervielle' como entidad aparte"),
    ("E", "GGAL", "30704962807", None,
     "CUIT no autoritativo, entidad unica: el caso negativo canonico"),
    ("E", "TELECOM ARGENTINA", "30639453738", None,
     "CUIT no autoritativo; emisor grande con ADR"),
    ("E", "Pampa Energy", "30526552659", None,
     "CUIT no autoritativo; nombre en ingles en identity_v1"),
    ("E", "Vista Energy", "33515950899", None,
     "CUIT no autoritativo; emisor con domicilio en Mexico (S.A.B. de C.V.)"),
    ("F", "AAPL", None, "0000320193",
     "identidad valida SIN CUIT: emisor no argentino, no puede tener perfil CNV"),
    ("F", "BMA / Macro Bank Inc.", None, "0001347426",
     "sin CUIT + nombre historico ('Macro Bank Inc.' por Banco Macro): cubre F y J"),
    ("H/I", "instrumentos BUE vs ADR", None, None,
     "no se resuelve por CNV: se audita aparte que el ticker NO participa"),
]

REPETIR = {"33650305499", "30657862068", "30500001735"}   # 2 positivos + 1 AMBIGUO


def psql(q: str, intentos: int = 12) -> list[list[str]]:
    ultimo = ""
    for _ in range(intentos):
        try:
            p = subprocess.run(
                ["docker", "exec", CONT, "psql", "-U", "catalaxia", "-d", "catalaxia",
                 "-t", "-A", "-F", "\x1f", "-c", q],
                capture_output=True, text=True, encoding="utf-8", timeout=45)
        except subprocess.TimeoutExpired:
            ultimo = "timeout"; time.sleep(12); continue
        if p.returncode == 0:
            return [ln.split("\x1f") for ln in p.stdout.splitlines() if ln.strip()]
        ultimo = (p.stderr or "")[:200]; time.sleep(12)
    raise SystemExit(f"psql bloqueado: {ultimo}")


def uno(q):
    r = psql(q)
    return r[0][0] if r else None


def huella() -> dict:
    f = uno("""SELECT (SELECT count(*) FROM fetch_raw.cnv_artifact)||'|'||
                      (SELECT count(*) FROM fetch_raw.cnv_download_log)||'|'||
                      (SELECT count(*) FROM engine.runs WHERE pipeline_version LIKE 'cnv%')||'|'||
                      (SELECT count(*) FROM engine.runs WHERE status='RUNNING')||'|'||
                      (SELECT count(*) FROM identity_v1.identifier WHERE valid_to IS NULL)||'|'||
                      (SELECT count(*) FROM identity_v1.assertion WHERE valid_to IS NULL)""")
    k = ("artefactos", "logs", "corridas_cnv", "running", "identifiers", "assertions")
    return dict(zip(k, (int(x) for x in f.split("|"))))


def ficha_identidad(cuit: str | None, cik: str | None) -> dict:
    """Todo lo que la fila del informe pide, leido de identity_v1."""
    if cuit:
        w = f"i.id_type='CUIT' AND i.id_value='{cuit}'"
    else:
        w = f"i.id_type='CIK' AND i.id_value='{cik}'"
    ek = psql(f"""SELECT DISTINCT i.entity_key FROM identity_v1.identifier i
                   WHERE {w} AND i.valid_to IS NULL ORDER BY 1""")
    if not ek:
        return {"entidades": 0}
    eks = [x[0] for x in ek]
    lista = ",".join(f"'{k}'" for k in eks)
    det = psql(f"""
        SELECT e.entity_key, e.preferred_name,
               coalesce(max(CASE WHEN i.id_type='CIK'  THEN i.id_value END),''),
               coalesce(max(CASE WHEN i.id_type='LEI'  THEN i.id_value END),''),
               coalesce(string_agg(DISTINCT CASE WHEN i.id_type='CUIT' THEN i.id_value END,','),''),
               count(*) FILTER (WHERE i.id_type='CUIT'),
               count(*) FILTER (WHERE i.id_type='CUIT' AND i.is_authoritative),
               coalesce(string_agg(DISTINCT CASE WHEN i.id_type='CUIT' THEN i.status END,','),''),
               coalesce(string_agg(DISTINCT CASE WHEN i.id_type='CUIT' THEN a.status END,','),''),
               coalesce(string_agg(DISTINCT CASE WHEN i.id_type='CUIT' AND i.is_authoritative
                        THEN i.assertion_id::text END,','),''),
               coalesce(string_agg(DISTINCT CASE WHEN i.id_type='CUIT' AND i.is_authoritative
                        THEN a.source_id END,','),'')
          FROM identity_v1.entity e
          JOIN identity_v1.identifier i ON i.entity_key=e.entity_key AND i.valid_to IS NULL
          LEFT JOIN identity_v1.assertion a ON a.assertion_id=i.assertion_id
         WHERE e.entity_key IN ({lista}) GROUP BY 1,2 ORDER BY 1""")
    d = det[0]
    return {"entidades": len(eks), "entity_id": d[0], "nombre": d[1], "cik": d[2],
            "lei": d[3], "cuits": d[4], "filas_cuit": int(d[5]),
            "cuit_autoritativas": int(d[6]), "identifier_status": d[7],
            "assertion_status": d[8], "assertion_id": d[9], "source": d[10]}


def ejecutar_fetch(cuit: str | None, cik: str | None) -> dict:
    arg = ["--cuit", cuit] if cuit else ["--cik", cik]
    p = subprocess.run([sys.executable, str(FETCHER)] + arg +
                       ["--scope", "EEFF_PROPIO", "--max-visores", "1"],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", cwd=str(REPO), timeout=600)
    sal = (p.stdout or "") + (p.stderr or "")
    run_id = next((l.split("run_id=")[1].split()[0] for l in sal.splitlines()
                   if "[run] run_id=" in l), "")
    gate = next((l.split("=")[1].strip().split()[0] for l in sal.splitlines()
                 if l.strip().startswith("gate ")), "")
    http = [l for l in sal.splitlines() if "http=" in l]
    return {"rc": p.returncode, "run_id": run_id, "gate": gate,
            "http": http[0].split("http=")[1].split()[0] if http else "",
            "cola": sal.strip().splitlines()[-1][:130] if sal.strip() else ""}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fetch", action="store_true",
                    help="autorizacion EXPLICITA para descargar en los casos elegibles")
    ap.add_argument("--repeticiones", type=int, default=2)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    s = load_settings()
    if s.is_prod:
        print("EXT-010: abortado.")
        return 2
    eng = get_admin_engine(s)

    print("CNV PILOT 2 — validacion multi-emisor")
    print(f"  DB: {s.describe()}")
    print(f"  modo: {'CON FETCH autorizado' if a.fetch else 'SOLO LECTURA (sin --fetch)'}\n")

    h0 = huella()
    print(f"  huella ANTES: {h0}")
    if h0["running"] != 0:
        print("  ABORTADO: hay corridas RUNNING")
        return 2

    filas, fetch_calls = [], []
    print(f"\n  {'cat':<4} {'caso':<28} {'elegibilidad':<24} {'ents':>4} {'auth':>4} fetch")
    for cat, nombre, cuit, cik, motivo in CASOS:
        if cat == "H/I":
            continue
        f = {"categoria": cat, "caso": nombre, "cuit_pedido": cuit, "cik_pedido": cik,
             "motivo_seleccion": motivo}
        f.update(ficha_identidad(cuit, cik))
        r = c3.resolver_en_identity_v1(eng, cuit, cik)
        f["eligibility_result"] = r["motivo"]
        f["ok"] = r["ok"]
        f["detalle"] = (r.get("detalle") or "")[:220]

        # ── LA SALVAGUARDA ──────────────────────────────────────────────
        if not r["ok"]:
            f.update({"cnv_request": "no", "http": "", "run_id": "", "gate": "",
                      "presentaciones": 0, "artifacts": 0})
        elif not a.fetch:
            f.update({"cnv_request": "no (sin --fetch)", "http": "", "run_id": "",
                      "gate": "", "presentaciones": 0, "artifacts": 0})
        else:
            reps = a.repeticiones if (cuit in REPETIR) else 1
            corridas = []
            for _ in range(reps):
                res = ejecutar_fetch(cuit, cik)
                fetch_calls.append(cuit or cik)
                corridas.append(res)
            f.update({"cnv_request": f"si x{reps}", "http": corridas[0]["http"],
                      "run_id": corridas[0]["run_id"], "gate": corridas[0]["gate"],
                      "corridas": corridas})
        print(f"  {cat:<4} {nombre[:27]:<28} {f['eligibility_result']:<24} "
              f"{f.get('entidades',0):>4} {f.get('cuit_autoritativas',0):>4} "
              f"{f['cnv_request']}")
        filas.append(f)

    # artefactos y hashes por CUIT elegible
    for f in filas:
        if not f["ok"]:
            continue
        cu = f.get("cuits") or f.get("cuit_pedido")
        if not cu:
            continue
        d = psql(f"""SELECT count(*), count(DISTINCT sha256), count(DISTINCT canonical_sha256),
                            count(*) FILTER (WHERE sha256 IS NOT NULL AND raw_path IS NOT NULL
                                              AND entity_key IS NOT NULL AND endpoint IS NOT NULL)
                       FROM fetch_raw.cnv_artifact WHERE cuit='{cu}'""")[0]
        f.update({"artifacts": int(d[0]), "raw_sha256_distintos": int(d[1]),
                  "canonical_hash_distintos": int(d[2]),
                  "provenance_completa": int(d[3]) == int(d[0])})
        f["presentaciones"] = int(uno(
            f"SELECT count(*) FROM fetch_raw.cnv_presentation WHERE cuit='{cu}'") or 0)

    h1 = huella()
    print(f"\n  huella DESPUES: {h1}")
    delta = {k: h1[k] - h0[k] for k in h0}
    print(f"  delta: {delta}")
    print(f"  invocaciones al fetcher: {len(fetch_calls)} -> {fetch_calls}")

    # negativa: ningun no-elegible llego al fetcher
    no_eleg = [f["caso"] for f in filas if not f["ok"]]
    llamados_no_eleg = [f["caso"] for f in filas
                        if not f["ok"] and f["cnv_request"].startswith("si")]
    print(f"\n  casos NO elegibles: {len(no_eleg)} · de esos, con fetch: "
          f"{len(llamados_no_eleg)}  {'OK' if not llamados_no_eleg else 'FALLA'}")

    with (OUT / "CNV_PILOT2_MATRIX.csv").open("w", newline="", encoding="utf-8") as fh:
        cols = ["categoria", "caso", "entity_id", "nombre", "cik", "lei", "cuits",
                "filas_cuit", "cuit_autoritativas", "identifier_status",
                "assertion_status", "assertion_id", "source", "entidades",
                "eligibility_result", "cnv_request", "http", "run_id", "gate",
                "presentaciones", "artifacts", "raw_sha256_distintos",
                "canonical_hash_distintos", "provenance_completa",
                "motivo_seleccion", "detalle"]
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for f in filas:
            w.writerow(f)
    (OUT / "CNV_PILOT2_RESULT.json").write_text(json.dumps(
        {"db": s.describe(), "fetch_autorizado": a.fetch, "huella_antes": h0,
         "huella_despues": h1, "delta": delta, "fetch_calls": fetch_calls,
         "no_elegibles": len(no_eleg), "no_elegibles_con_fetch": llamados_no_eleg,
         "casos": filas}, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"\n  -> CNV_PILOT2_MATRIX.csv · CNV_PILOT2_RESULT.json")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    raise SystemExit(main())
