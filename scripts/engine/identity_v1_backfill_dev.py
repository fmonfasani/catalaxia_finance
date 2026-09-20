#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BACKFILL DEV de identity_v1 — universo SEC + legacy (solo 5433).

Materializa el universo aprobado por el dry-run (READY_FOR_BACKFILL):
  * 8.004 entidades SEC (una por CIK unico del catalogo RAW), CIK autoritativo
    desde SEC_REGISTRY (method=REGISTRY).
  * 512 entidades legacy dim_entity con CIK se FUSIONAN en la entidad SEC
    (mismo CIK = misma entidad; el legacy nunca reemplaza al SEC).
  * 13 ADR con CIK+CUIT: CUIT legacy como CANDIDATE (LEGACY_DIM_ENTITY,
    CORROBORATING -> nunca autoritativo) + bridge IDENTIFIER_BRIDGE CIK<->CUIT
    CANDIDATE.
  * 4 LEI del ciclo G4 (GLEIF) + 4 puentes CIK<->LEI como PROPUESTA
    (CROSS_REFERENCE CANDIDATE; la ratificacion es humana, G5/F-016).
  * CUIT via GLEIF con el mecanismo real `link_cuit_desde_gleif`: con puentes
    sin ratificar produce REVIEW_REQUIRED (3) y GGAL sin registeredAs abre la
    suya (1). El CUIT de GLEIF no consolida sin puente verificado.
  * 4 conflictos CIK legacy (CSV) vs SEC: SEC gana; el CIK podrido queda
    documentado en identity_v1.conflict, jamas como identificador.

REGLAS D-I-04 implementadas:
  LEI opcional (US sin LEI no abre review) · SEC autoridad del CIK ·
  mismo CIK = misma entidad · legacy CUIT nunca autoridad ·
  solo ambiguedad real abre review · provenance completa (source/record/
  evidence/resolved_by) · un CIK = una entidad (los 2.387 CIK multi-ticker
  del catalogo NO duplican).

Idempotente (F-023/F-032/F-034): segunda corrida = 0 inserciones.
SOLO escribe en identity_v1 de 5433. EXT-010: aborta contra 5432.

Uso:
    python scripts/engine/identity_v1_backfill_dev.py
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts" / "engine"))

from sqlalchemy import text  # noqa: E402

from engine import db as edb  # noqa: E402
from engine import identity_v1 as idv  # noqa: E402
from engine.config import load_settings  # noqa: E402
from engine.identity import SEC_CATALOG_DIR  # noqa: E402
from engine.identity_v1 import Evidence  # noqa: E402
from identity_v1_pilot import EMISORES, GLEIF_SNAPSHOT  # noqa: E402

PIPELINE_VERSION = "identity-backfill-dev-v1"
SCRIPT = "scripts/engine/identity_v1_backfill_dev.py"
BY = "proc:identity_backfill_dev"
TABLES = ("entity", "identifier", "assertion", "instrument",
          "instrument_symbol", "review", "conflict")


def sha16(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()[:16] if Path(p).exists() else "NO"


def norm_cik(x) -> str | None:
    if x is None:
        return None
    s = str(x).strip()
    return s.zfill(10) if s.isdigit() else None


def norm_cuit(x) -> str | None:
    if x is None:
        return None
    d = "".join(c for c in str(x) if c.isdigit())
    return d if len(d) == 11 else None


def main() -> int:
    out = io.StringIO()
    w = out.write

    s = load_settings()
    if s.is_prod or s.db_port != "5433":
        print("EXT-010: el backfill DEV solo corre contra 5433. Abortado.")
        return 2
    eng = edb.get_engine(s)
    huerfanas = edb.corridas_huerfanas(eng)
    if huerfanas:
        print(f"BLOCK · F-009: {len(huerfanas)} corrida(s) huerfana(s).")
        return 1

    # ---------------- fuentes (solo lectura) ----------------
    cat = sorted(SEC_CATALOG_DIR.glob("company_tickers_*.json"))[-1]
    raw = json.loads(cat.read_text(encoding="utf-8"))
    sec_by_cik: dict[str, dict] = {}
    sec_by_ticker: dict[str, str] = {}
    for v in raw.values():
        cik = str(int(v["cik_str"])).zfill(10)
        tk = str(v["ticker"]).strip().upper()
        # un CIK = una entidad: los multi-ticker (clases) no duplican
        sec_by_cik.setdefault(cik, {"ticker": tk, "title": str(v["title"]).strip()})
        sec_by_ticker.setdefault(tk, cik)

    dim_con = sqlite3.connect(f"file:{REPO / 'data' / 'screener.db'}?mode=ro", uri=True)
    dim = dim_con.execute(
        "SELECT entity_id, cik, cuit, ticker_canonico, grupo, nombre FROM dim_entity"
    ).fetchall()
    dim_con.close()

    arg_csv = REPO / "scripts" / "screener" / "datos" / "acciones_argentinas_usa.csv"
    with open(arg_csv, encoding="utf-8-sig", newline="") as f:
        arg_rows = list(csv.DictReader(f))

    LEI_BY_CIK = {em["cik"]: em["lei"] for em in EMISORES}

    w("=" * 76 + "\n")
    w("BACKFILL DEV identity_v1 (solo 5433) · D-I-04 / F-020\n")
    w("=" * 76 + "\n")
    w(f"target={s.describe()}  catalogo={cat.name} sha16={sha16(cat)}\n")

    with edb.run_scope(eng, s, PIPELINE_VERSION) as run:
        run_id = run.run_id
        w(f"run_id={run_id}\n\n")
        stats = {"entidades_creadas": 0, "cik_afirmados": 0, "fusiones": 0,
                 "cuit_legacy": 0, "bridges_cik_cuit": 0, "lei": 0,
                 "bridges_cik_lei": 0, "reviews": 0, "conflictos": 0,
                 "errores": []}

        # una sola transaccion: o todo, o nada
        with eng.begin() as conn:
            # ---------- FASE 1: universo SEC ----------
            for cik in sorted(sec_by_cik):
                title = sec_by_cik[cik]["title"].strip() or f"CIK {cik}"
                ticker = sec_by_cik[cik]["ticker"]
                key, creada = idv.resolve_or_create_entity(
                    conn, preferred_name=title, id_type="CIK", id_namespace="SEC",
                    id_value=cik)
                if creada:
                    stats["entidades_creadas"] += 1
                r = idv.assert_identifier(
                    conn, entity_key=key, id_type="CIK", id_namespace="SEC",
                    id_value=cik, method="REGISTRY",
                    evidence=Evidence(
                        "SEC_REGISTRY", f"{cat.name}#{ticker}",
                        f"SEC company_tickers ({cat.name}) declara CIK {cik} "
                        f"para '{title}' (ticker {ticker})",
                        BY))
                if r.status == "VERIFIED":
                    stats["cik_afirmados"] += 1
                elif r.status != "VERIFIED":
                    stats["errores"].append(f"CIK {cik}: {r.status} {r.motivo}")
                if (stats["entidades_creadas"] + stats["cik_afirmados"]) % 1000 < 2:
                    print(f"  [sec] procesados ~{stats['cik_afirmados']}", flush=True)

            # ---------- FASE 2: legacy dim_entity (fusion SEC>legacy) ----------
            fusionadas = 0
            for (eid, cik, cuit, tk, grupo, nombre) in dim:
                cik_n = norm_cik(cik)
                cuit_n = norm_cuit(cuit)
                if not cik_n or cik_n not in sec_by_cik:
                    continue  # sin ancla SEC: no se crea (regla 2/4 del dry-run)
                key = idv.entity_of(conn, "CIK", "SEC", cik_n)
                fusionadas += 1
                if not cuit_n:
                    continue
                # CUIT legacy: CANDIDATE, nunca autoridad (regla 7)
                r = idv.assert_identifier(
                    conn, entity_key=key, id_type="CUIT", id_namespace="AFIP",
                    id_value=cuit_n, method="REGISTRY",
                    evidence=Evidence(
                        "LEGACY_DIM_ENTITY", f"sqlite:dim_entity#{eid}",
                        f"dim_entity fila {eid} ({grupo}, {tk}) declara cuit={cuit} "
                        "sin autor ni documento de respaldo".replace("{cuit}", str(cuit_n)),
                        BY))
                if r.status in ("CANDIDATE", "VERIFIED"):
                    stats["cuit_legacy"] += 1
                # puente CIK<->CUIT como PROPUESTA (los 13 ADR con ambos)
                if grupo == "adr":
                    rb = idv.assert_bridge(
                        conn, left_ref_=idv.ref("CIK", "SEC", cik_n),
                        right_ref_=idv.ref("CUIT", "AFIP", cuit_n),
                        method="LEGACY_IMPORT",
                        evidence=Evidence(
                            "LEGACY_DIM_ENTITY", f"sqlite:dim_entity#{eid}",
                            f"dim_entity asocia CIK {cik_n} y CUIT {cuit_n} a la misma "
                            f"entidad ({tk}); sin fuente primaria del par",
                            BY))
                    if rb.status in ("CANDIDATE", "VERIFIED"):
                        stats["bridges_cik_cuit"] += 1
            stats["fusiones"] = fusionadas

            # ---------- FASE 3: GLEIF (4 LEI del ciclo G4) ----------
            for em in EMISORES:
                key = idv.entity_of(conn, "CIK", "SEC", em["cik"])
                if not key:
                    stats["errores"].append(f"GLEIF: entidad {em['cik']} no existe")
                    continue
                snap = GLEIF_SNAPSHOT[em["lei"]]
                cita = (f"GLEIF lei-records/{em['lei']} (snapshot ciclo 4): "
                        f"registeredAt={snap['registeredAt']} "
                        f"registeredAs={snap['registeredAs']!r}")
                r = idv.assert_identifier(
                    conn, entity_key=key, id_type="LEI", id_namespace="GLEIF",
                    id_value=em["lei"], method="REGISTRY",
                    evidence=Evidence("GLEIF", f"lei-records/{em['lei']}", cita, BY))
                if r.status in ("VERIFIED", "CANDIDATE"):
                    stats["lei"] += 1
                # puente CIK<->LEI como PROPUESTA (nunca humano desde un proceso)
                rb = idv.assert_bridge(
                    conn, left_ref_=idv.ref("CIK", "SEC", em["cik"]),
                    right_ref_=idv.ref("LEI", "GLEIF", em["lei"]),
                    method="CROSS_REFERENCE",
                    evidence=Evidence(
                        "GLEIF", f"lei-records/{em['lei']}",
                        cita + " — propuesto por denominacion social con el "
                        f"registrante del CIK {em['cik']}; NO demostrado (G5)",
                        BY))
                if rb.status in ("CANDIDATE", "VERIFIED"):
                    stats["bridges_cik_lei"] += 1
                # CUIT via GLEIF con el mecanismo REAL del dominio: sin puente
                # VERIFIED esto produce REVIEW_REQUIRED (no autoridad).
                rec = {"entity": {"registeredAt": {"id": snap["registeredAt"]},
                                  "registeredAs": snap["registeredAs"]}}
                rc = idv.link_cuit_desde_gleif(
                    conn, entity_key=key, lei=em["lei"], gleif_record=rec,
                    source_record=f"gleif:lei-records/{em['lei']}", resolved_by=BY)
                if rc.status == "REVIEW_REQUIRED":
                    stats["reviews"] += 1
                stats.setdefault("gleif_cuit", []).append(
                    {"slug": em["slug"], "status": rc.status, "motivo": rc.motivo[:80]})

            # ---------- FASE 4: conflictos legacy CIK vs SEC ----------
            for r_ in arg_rows_rows(arg_csv):
                tk = r_["ticker_usa"].strip().upper()
                cik_leg = norm_cik(r_.get("cik"))
                cik_sec = sec_by_ticker.get(tk)
                if not (cik_sec and cik_leg and cik_sec != cik_leg):
                    continue
                key = idv.entity_of(conn, "CIK", "SEC", cik_sec)
                motivo = (f"catálogo legacy acciones_argentinas_usa.csv atribuye "
                          f"{tk} al CIK {cik_leg}; la fuente de registro SEC "
                          f"declara {cik_sec}. EXT-NEW-012/D-I-C: gana SEC; el "
                          "CIK legacy se descarta, nunca reemplaza.")
                ya = conn.execute(text(
                    "SELECT 1 FROM identity_v1.conflict "
                    " WHERE id_type='CIK' AND id_namespace='SEC' AND id_value=:v "
                    "   AND reason=:r LIMIT 1"), {"v": cik_leg, "r": motivo}).scalar()
                if not ya:
                    idv.open_conflict(conn, id_type="CIK", id_namespace="SEC",
                                      id_value=cik_leg, candidatos=[key],
                                      reason=motivo, detected_by=BY)
                    stats["conflictos"] += 1

        # ---------------- resumen ----------------
        w("\n-- RESULTADO DEL BACKFILL --\n")
        for k, v in stats.items():
            if k == "errores":
                w(f"  {k:<20} = {len(v)}\n")
                for e_ in v[:10]:
                    w("      " + e_ + "\n")
            else:
                w(f"  {k:<20} = {v}\n")

    # ---------------- conteos finales ----------------
    with eng.connect() as c:
        conteos = {t: c.execute(text(f"SELECT count(*) FROM identity_v1.{t}")).scalar()
                   for t in TABLES}
    print(out.getvalue())
    print("\n-- conteos identity_v1 --")
    for k, v in conteos.items():
        print(f"  {k:<18} = {v}")
    print(f"\nrun_id={run_id}")
    return 0


def arg_rows_rows(path: Path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    raise SystemExit(main())