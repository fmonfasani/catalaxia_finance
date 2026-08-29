#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Clasificacion RELEASE / EXCLUDE para el commit de Catalaxia V1.0.0.

No decide por extension: decide por RUTA y por rol en el release. Cada regla
lleva su motivo, y todo lo que no matchea una regla explicita queda en
SIN_CLASIFICAR -- que obliga a detenerse, no a incluir por defecto.

SOLO LECTURA sobre el disco. No borra nada; solo decide que entra en git.
"""
from __future__ import annotations

import io
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "docs" / "release"

# (prefijo, decision, motivo) -- se evalua EN ORDEN, gana la primera
REGLAS = [
    # ---------- RELEASE: lo necesario para reproducir V1 ----------------
    ("migrations/",                  "RELEASE", "schema de V1"),
    ("engine/",                      "RELEASE", "codigo del engine"),
    ("scripts/engine/",              "RELEASE", "pipeline SEC/CNV/Identity y auditorias"),
    ("scripts/market/",              "RELEASE", "Market homologado (M23, F-014, gate F-001)"),
    ("tests/",                       "RELEASE", "suite de V1"),
    ("docs/architecture/",           "RELEASE", "contratos y diseno"),
    ("docs/review/",                 "RELEASE", "auditorias y findings"),
    ("docs/release/",                "RELEASE", "baseline, manifest, release docs"),
    ("outputs/docs/homologacion/",   "RELEASE", "evidencia citada por el release"),

    # ---------- EXCLUDE: artefactos ajenos al release -------------------
    ("scratchpad/",                  "EXCLUDE", "scratchpad de trabajo"),
    (".vscode/",                     "EXCLUDE", "config personal del editor"),
    ("_legacy/",                     "EXCLUDE", "codigo de un proyecto anterior"),
    ("lib/",                         "EXCLUDE", "vendored JS ajeno a V1"),
    ("data/",                        "EXCLUDE", "datos, backups y xlsx; data/raw no se versiona"),
    ("outputs/",                     "EXCLUDE", "outputs de fase, reproducibles con los scripts"),
    ("docs/proyecto/",               "EXCLUDE", "notas de proyecto, no del release tecnico"),
    ("docs/webshooks/",              "EXCLUDE", "material ajeno a V1"),
    ("docs/libro/",                  "EXCLUDE", "material editorial"),
    ("docs/pdfs/",                   "EXCLUDE", "material editorial"),
    ("docs/producto/",               "EXCLUDE", "material de producto"),
    ("docs/masterclass/",            "EXCLUDE", "material de formacion"),
    ("scripts/pipeline/",            "EXCLUDE", "pipeline legacy, fuera del alcance de V1"),
    ("scripts/tickets/",             "EXCLUDE", "scripts ad-hoc de tickets"),
    ("scripts/docgen/",              "EXCLUDE", "generacion de documentos, ajena a V1"),
]

# archivos sueltos en la raiz: ninguno pertenece al release
def clasificar(ruta: str) -> tuple[str, str]:
    for pref, dec, motivo in REGLAS:
        if ruta.startswith(pref):
            return dec, motivo
    if "/" not in ruta:
        return "EXCLUDE", "artefacto en la raiz (dashboards, deploys, xlsx, tmp)"
    if ruta.startswith("docs/"):
        return "EXCLUDE", "documento fuera del release tecnico"
    return "SIN_CLASIFICAR", "no matchea ninguna regla explicita"


def git(*args) -> list[str]:
    r = subprocess.run(["git", *args], cwd=str(REPO), capture_output=True, text=True)
    return [l for l in r.stdout.splitlines() if l.strip()]


def main() -> int:
    untracked = git("ls-files", "--others", "--exclude-standard")
    modificados = [l[3:] for l in git("status", "--porcelain") if l.startswith(" M")]
    borrados = [l[3:] for l in git("status", "--porcelain") if l.startswith(" D")]

    res: dict[str, list] = {"RELEASE": [], "EXCLUDE": [], "SIN_CLASIFICAR": []}
    for origen, lista in (("untracked", untracked), ("modificado", modificados)):
        for f in lista:
            dec, motivo = clasificar(f)
            res[dec].append({"path": f, "origen": origen, "motivo": motivo})

    print("CLASIFICACION PARA EL COMMIT DE RELEASE\n")
    print(f"  untracked={len(untracked)}  modificados={len(modificados)}  "
          f"borrados={len(borrados)}\n")
    for dec in ("RELEASE", "EXCLUDE", "SIN_CLASIFICAR"):
        print(f"  {dec:<16} {len(res[dec])}")
    print("\n  RELEASE por seccion:")
    sec: dict[str, int] = {}
    for i in res["RELEASE"]:
        k = "/".join(i["path"].split("/")[:2]) if "/" in i["path"] else "(raiz)"
        sec[k] = sec.get(k, 0) + 1
    for k, v in sorted(sec.items()):
        print(f"    {k:<32} {v}")

    if res["SIN_CLASIFICAR"]:
        print(f"\n  DETENERSE: {len(res['SIN_CLASIFICAR'])} archivos sin clasificar")
        for i in res["SIN_CLASIFICAR"][:20]:
            print(f"    {i['path']}")

    # los borrados NO se incluyen: son logs de data/, ajenos al release
    print(f"\n  borrados NO incluidos (data/, ajenos al release): {borrados}")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "_clasificacion.json").write_text(
        json.dumps({"release": res["RELEASE"], "exclude": res["EXCLUDE"],
                    "sin_clasificar": res["SIN_CLASIFICAR"],
                    "borrados_no_incluidos": borrados},
                   indent=2, ensure_ascii=False), encoding="utf-8")
    (OUT / "_release_files.txt").write_text(
        "\n".join(sorted(i["path"] for i in res["RELEASE"])) + "\n", encoding="utf-8")
    print(f"\n  -> docs/release/_clasificacion.json")
    print(f"  -> docs/release/_release_files.txt  ({len(res['RELEASE'])} archivos)")
    return 1 if res["SIN_CLASIFICAR"] else 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    raise SystemExit(main())
