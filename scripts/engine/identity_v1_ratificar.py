#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Identity v1 — ratificacion humana de un puente CIK <-> LEI.

El ciclo G5 establecio que ninguna fuente primaria publica el par CIK<->LEI:
ni SEC publica el LEI del registrante, ni GLEIF publica el CIK. La unica via
legitima para que ese puente llegue a VERIFIED es que una PERSONA lo ratifique
con evidencia de los dos lados.

Este script es esa via, y es el unico camino: desde F-016 ningun proceso
automatico puede escribir method='HUMAN_DECISION' — lo impide la capa de dominio
y ademas el CHECK ck_humano_no_es_proceso en la base.

Que cuenta como evidencia (un tercero tiene que poder reproducirla):
  lado CIK  · un documento SEC del registrante: accession del 20-F/F-1/424B,
              con la denominacion social y el domicilio legal que se contrastan
  lado LEI  · el registro GLEIF: URL del lei-record, legalName, registeredAt,
              registeredAs

Uso:
    python scripts/engine/identity_v1_ratificar.py --listar

    python scripts/engine/identity_v1_ratificar.py \\
        --cik 0000904851 --lei 5493003N7447U18U5U53 \\
        --reviewer "nombre.apellido" \\
        --evidencia-cik "20-F FY2023 accession 0001193125-24-091425: 'YPF Sociedad
                         Anonima, Macacha Guemes 515, C1106BKK Buenos Aires'" \\
        --evidencia-lei "GLEIF lei-records/5493003N7447U18U5U53: legalName='YPF
                         Sociedad Anonima', legalAddress Macacha Guemes 515 Buenos
                         Aires, registeredAt=RA000009, registeredAs='30-54668997-9'" \\
        --motivo "denominacion social y domicilio legal coinciden en ambos registros"
"""
from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy import text  # noqa: E402

from engine.config import load_settings  # noqa: E402
from engine.db import get_engine  # noqa: E402
from engine import identity_v1 as idv  # noqa: E402


def listar(conn) -> None:
    filas = conn.execute(text(
        """
        SELECT r.review_id, e.preferred_name,
               r.candidate_identifiers->>'cik'  AS cik,
               r.candidate_identifiers->>'lei'  AS lei,
               r.candidate_identifiers->>'cuit_propuesto_via_gleif' AS cuit
          FROM identity_v1.review r
          JOIN identity_v1.entity e USING (entity_key)
         WHERE r.status = 'OPEN' AND r.reason LIKE 'puente CIK<->LEI%'
         ORDER BY r.review_id
        """)).mappings().all()
    if not filas:
        print("No hay puentes pendientes de ratificacion.")
        return
    print(f"{len(filas)} puente(s) CIK<->LEI esperando a una persona:\n")
    for f in filas:
        print(f"  review #{f['review_id']}  {f['preferred_name']}")
        print(f"      CIK  {f['cik']}")
        print(f"      LEI  {f['lei']}")
        print(f"      habilitaria el CUIT {f['cuit'] or '(GLEIF no lo publica)'}\n")
    print("Ratificar con --cik / --lei / --reviewer / --evidencia-cik / "
          "--evidencia-lei / --motivo")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--listar", action="store_true", help="puentes pendientes")
    ap.add_argument("--cik")
    ap.add_argument("--lei")
    ap.add_argument("--reviewer", help="persona que ratifica. NO puede empezar con 'proc:'")
    ap.add_argument("--evidencia-cik", help="cita del documento SEC del registrante")
    ap.add_argument("--evidencia-lei", help="cita del registro GLEIF")
    ap.add_argument("--motivo", help="por que ambos registros son la misma entidad")
    ap.add_argument("--review-id", type=int, help="review a cerrar (opcional)")
    args = ap.parse_args()

    s = load_settings()
    if s.is_prod:
        print("EXT-010: no se ratifica contra 5432.")
        return 2
    eng = get_engine(s)

    if args.listar:
        with eng.connect() as conn:
            listar(conn)
        return 0

    faltan = [n for n in ("cik", "lei", "reviewer", "evidencia_cik", "evidencia_lei", "motivo")
              if not getattr(args, n)]
    if faltan:
        print(f"Faltan argumentos obligatorios: {', '.join('--' + f.replace('_','-') for f in faltan)}")
        print("Un puente sin evidencia de AMBOS extremos no esta demostrado (G5).")
        return 2

    with eng.begin() as conn:
        rid = args.review_id
        if rid is None:
            rid = conn.execute(text(
                "SELECT review_id FROM identity_v1.review "
                " WHERE status='OPEN' AND reason LIKE 'puente CIK<->LEI%'"
                "   AND candidate_identifiers->>'cik' = :c"),
                {"c": idv.norm_cik(args.cik)}).scalar()
        try:
            res = idv.ratificar_bridge(
                conn, cik=args.cik, lei=args.lei, reviewer=args.reviewer,
                evidencia_cik=args.evidencia_cik, evidencia_lei=args.evidencia_lei,
                motivo=args.motivo, review_id=rid)
        except idv.IdentityError as e:
            print(f"RECHAZADO: {e}")
            return 1

        print(f"Puente ratificado · assertion {res.assertion_id} · status {res.status}")
        if rid:
            print(f"Review #{rid} cerrada por {args.reviewer}")
        print("\nCorra el piloto para que el CUIT se consolide por esta via:")
        print("    python scripts/engine/identity_v1_pilot.py")
    return 0


if __name__ == "__main__":
    # solo al ejecutarse como script: importar no debe tocar sys.stdout
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")
    raise SystemExit(main())
