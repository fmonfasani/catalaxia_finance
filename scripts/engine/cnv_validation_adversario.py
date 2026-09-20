#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Banco adversario — validación CNV multi-empresa (Fase F).

Cada ataque corre en una transacción que se REVIERTE al final (no deja rastro
en la base), salvo que se indique lo contrario. El objetivo de cada uno es
identificar la barrera EXACTA que lo rechaza, no solo si "funciona".

Ataques cubiertos acá (los restantes del enunciado — idempotencia real,
ADR-vs-local, colisión de ticker en vivo — ya están demostrados con
ejecuciones reales del fetcher y se referencian en el reporte, no se repiten
como transacciones sintéticas):

  1. CUIT incorrecto (checksum roto)
  2. CUIT de otra entidad (ya autoritativo)
  3. Entity sin CUIT verificado (BMA) — vía el legacy corrupto de F-024
  4. "Ticker" pasado donde se espera CUIT (formato)
  6. Vínculo por coincidencia de nombre (estructural: no existe código que lo haga)
  10. Reescribir una assertion vigente (cambio de CUIT post-fetch)
  11. Provenance de CNV manipulada por UPDATE directo (no DELETE)

Uso:
    python scripts/engine/cnv_validation_adversario.py
"""
from __future__ import annotations

import io
import json
import re
import subprocess
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy import text  # noqa: E402
from sqlalchemy.exc import DBAPIError, IntegrityError  # noqa: E402

from engine.config import REPO_ROOT, load_settings  # noqa: E402
from engine.db import get_engine  # noqa: E402
from engine import identity_v1 as idv  # noqa: E402
from engine.identity_v1 import Evidence  # noqa: E402

resultados: list[dict] = []


def registrar(n: str, nombre: str, resultado: str, barrera: str, detalle: str):
    resultados.append({"ataque": n, "nombre": nombre, "resultado": resultado,
                       "barrera": barrera, "detalle": detalle})
    print(f"[{resultado:8}] #{n} {nombre}\n           barrera: {barrera}\n           {detalle}\n")


def main() -> int:
    s = load_settings()
    eng = get_engine(s)

    # ---- 1. CUIT incorrecto (checksum roto) --------------------------------
    with eng.begin() as conn:
        ypf_key = idv.entity_of(conn, "CIK", "SEC", "0000904851")
        r = idv.assert_identifier(
            conn, entity_key=ypf_key, id_type="CUIT", id_namespace="AFIP",
            id_value="30546689970",  # digito verificador deliberadamente roto
            method="REGISTRY",
            evidence=Evidence("GLEIF", "test-adversario", "cita falsa", "test:adversario"))
        ok = r.status == "REJECTED" and "digito verificador" in r.motivo
        registrar("1", "CUIT con digito verificador invalido", "RECHAZADO" if ok else "PASÓ",
                  "identity_v1.assert_identifier() -> cuit_valido() (modulo 11)", r.motivo)
        conn.rollback()

    # ---- 2. CUIT de otra entidad (ya autoritativo) -------------------------
    with eng.begin() as conn:
        ypf_key = idv.entity_of(conn, "CIK", "SEC", "0000904851")
        r = idv.assert_identifier(
            conn, entity_key=ypf_key, id_type="CUIT", id_namespace="AFIP",
            id_value="33650305499",  # CUIT real de CEPU, no de YPF
            method="REGISTRY",
            evidence=Evidence("GLEIF", "test-adversario",
                              "intento de atribuir el CUIT de CEPU a YPF", "test:adversario"))
        ok = r.status == "REJECTED" and r.conflict_id is not None
        registrar("2", "CUIT ya autoritativo de OTRA entidad (CEPU) atribuido a YPF",
                  "RECHAZADO" if ok else "PASÓ",
                  "ux_identifier_autoritativo_unico + identity_v1.assert_identifier()",
                  f"{r.motivo} (conflict_id={r.conflict_id})")
        conn.rollback()

    # ---- 3. Entity sin CUIT verificado (BMA / F-024) -----------------------
    with eng.begin() as conn:
        bma_key = idv.entity_of(conn, "CIK", "SEC", "0001347426")
        n_cuit = conn.execute(text(
            "SELECT count(*) FROM identity_v1.identifier "
            " WHERE entity_key=:e AND id_type='CUIT'"), {"e": bma_key}).scalar()
        n_lei = conn.execute(text(
            "SELECT count(*) FROM identity_v1.identifier "
            " WHERE entity_key=:e AND id_type='LEI'"), {"e": bma_key}).scalar()
        ok = n_cuit == 0
        registrar("3", "Macro Bank Inc. (BMA): fetch sin CUIT verificado",
                  "CORRECTAMENTE BLOQUEADO" if ok else "RIESGO",
                  "ausencia de identifier CUIT en identity_v1 (F-024: el legacy tiene un CIK "
                  "mal cargado en la columna cuit, nunca promovido)",
                  f"identity_v1.identifier para {bma_key}: CUIT={n_cuit}, LEI={n_lei} "
                  f"(LEI=0 porque F-024/review 17 declara AMBIGUO: GLEIF devuelve 2 LEI vigentes "
                  f"para Banco Macro). Conclusion: no hay CUIT que pasar a c3_cnv_fetch.py sin "
                  f"inventarlo. No se intento ningun --cuit para BMA en Fase D.")

    # ---- 4. "Ticker" pasado donde se espera CUIT (formato) -----------------
    for entrada in ("YPF", "GGAL.BA", "12345"):
        proc = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts/engine/c3_cnv_fetch.py"),
             "--cuit", entrada, "--scope", "EEFF_PROPIO"],
            capture_output=True, text=True, timeout=30)
        ok = proc.returncode != 0 and "CUIT invalido" in (proc.stdout + proc.stderr)
        registrar("4", f"ticker/valor no-CUIT pasado como --cuit ({entrada!r})",
                  "RECHAZADO" if ok else "PASÓ",
                  "c3_cnv_fetch.py: val.normalize_cuit() + chequeo de 11 digitos, antes de "
                  "tocar red o identity_v1",
                  (proc.stdout + proc.stderr).strip().splitlines()[-1] if (proc.stdout+proc.stderr).strip() else "(sin salida)")

    # ---- 6. Vínculo por coincidencia de nombre (estructural) ---------------
    fetcher_src = (REPO_ROOT / "scripts/engine/c3_cnv_fetch.py").read_text(encoding="utf-8")
    link_src = (REPO_ROOT / "scripts/engine/c3_identity_link.py").read_text(encoding="utf-8")
    identity_src = (REPO_ROOT / "engine/identity_v1.py").read_text(encoding="utf-8")
    patron_nombre = re.compile(r"ILIKE|similarity\(|difflib|fuzzy|preferred_name\s*=\s*:", re.I)
    hits = [f for f in (fetcher_src, link_src, identity_src) if patron_nombre.search(f)]
    ok = len(hits) == 0
    registrar("6", "atribucion CNV<->Identity por coincidencia de nombre",
              "ESTRUCTURALMENTE IMPOSIBLE" if ok else "RIESGO",
              "revisión estática: c3_cnv_fetch.py, c3_identity_link.py y engine/identity_v1.py "
              "resuelven exclusivamente por CIK/CUIT/LEI vigentes (entity_of()); ningún camino "
              "de código compara preferred_name contra el CUIT/CIK entrante",
              f"{len(hits)}/3 archivos con algún patrón de matching por nombre (esperado 0)")

    # ---- 10. Reescribir una assertion vigente (cambio de CUIT post-fetch) --
    with eng.begin() as conn:
        try:
            conn.execute(text(
                "UPDATE identity_v1.assertion SET evidence='HACKEADO' WHERE assertion_id=345"))
            conn.execute(text("SELECT 1"))  # fuerza el envío antes del rollback
            ok, motivo = False, "el UPDATE no lanzó excepción (inesperado)"
        except (IntegrityError, DBAPIError) as e:
            ok, motivo = True, str(e.orig).strip().splitlines()[0]
        finally:
            conn.rollback()
    registrar("10", "reescribir evidence de la assertion vigente del CUIT de YPF (id 345)",
              "RECHAZADO" if ok else "PASÓ",
              "identity_v1.assertion: trigger tg_assertion_inmutable (F-015)", motivo)

    # ---- 11. Provenance de CNV manipulada: DELETE vs UPDATE ----------------
    with eng.connect() as conn:
        fila = conn.execute(text(
            "SELECT log_id, sha256 FROM fetch_raw.cnv_download_log "
            " WHERE cuit='30546689979' LIMIT 1")).first()
    if fila is None:
        registrar("11a", "borrar una fila de fetch_raw.cnv_download_log (DELETE)", "NULO",
                  "sin blanco real: todavía no hay filas de YPF en fetch_raw", "-")
        registrar("11b", "falsificar el sha256 de una fila ya persistida (UPDATE)", "NULO",
                  "sin blanco real: todavía no hay filas de YPF en fetch_raw", "-")
    else:
        log_id, sha_original = fila
        with eng.begin() as conn:
            try:
                conn.execute(text("DELETE FROM fetch_raw.cnv_download_log WHERE log_id=:i"),
                            {"i": log_id})
                del_ok, del_motivo = False, "el DELETE no lanzó excepción (inesperado)"
            except (IntegrityError, DBAPIError) as e:
                del_ok, del_motivo = True, str(e.orig).strip().splitlines()[0]
            finally:
                conn.rollback()
        with eng.begin() as conn:
            try:
                conn.execute(text(
                    "UPDATE fetch_raw.cnv_download_log SET sha256=:falso WHERE log_id=:i"),
                    {"falso": "0" * 64, "i": log_id})
                upd_ok, upd_motivo = False, "el UPDATE se aplicó sin excepción"
            except (IntegrityError, DBAPIError) as e:
                upd_ok, upd_motivo = True, str(e.orig).strip().splitlines()[0]
            finally:
                conn.rollback()
        registrar("11a", "borrar una fila de fetch_raw.cnv_download_log (DELETE)",
                  "RECHAZADO" if del_ok else "PASÓ",
                  "privilegios de rol: catalaxia_engine NO tiene DELETE en fetch_raw "
                  "(migracion 011)", del_motivo)
        extra = ("" if upd_ok else ". Mitigación parcial: el auditor independiente "
                 "(AUD-HASH-001) recalcula el sha256 desde el archivo en disco y "
                 "detectaría la discrepancia en la SIGUIENTE auditoría, pero nada "
                 "en la base impide la escritura en el momento en que ocurre.")
        registrar("11b", "falsificar el sha256 de una fila ya persistida (UPDATE)",
                  "RECHAZADO" if upd_ok else "*** SIN BARRERA ***",
                  "ninguna: catalaxia_engine SÍ tiene UPDATE en fetch_raw.* (migracion 011, "
                  "a diferencia de identity_v1 que sí tiene triggers de inmutabilidad)",
                  upd_motivo + extra)

    print("=" * 78)
    print(f"RESUMEN: {sum(1 for r in resultados if 'RECHAZADO' in r['resultado'] or 'BLOQUEADO' in r['resultado'] or 'IMPOSIBLE' in r['resultado'])}/{len(resultados)} ataques con barrera confirmada")
    for r in resultados:
        print(f"  #{r['ataque']:<4} {r['resultado']:<22} {r['nombre']}")

    out_path = REPO_ROOT / "outputs" / "docs" / "fase_cnv" / "CNV_VALIDATION_ADVERSARIO.json"
    out_path.write_text(json.dumps(resultados, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nInforme escrito en {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
