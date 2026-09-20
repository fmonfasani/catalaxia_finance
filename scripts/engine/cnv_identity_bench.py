#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fase A — banco de la resolucion de identidad de C3 contra identity_v1.

Verifica el ESTADO de la resolucion, no la ausencia de excepcion. No descarga
nada de CNV: ejercita `resolver_en_identity_v1` y `load_identity`, que son las
dos puertas por las que pasa toda ingesta.

Lo que se prueba:
  - YPF y TGS resuelven por bridge VERIFIED (eran PROVISIONAL_CUIT antes)
  - CEPU sigue funcionando
  - GGAL queda BLOQUEADA: su CUIT esta CANDIDATE, no VERIFIED
  - entrar por --cik DERIVA el CUIT y da el mismo resultado que entrar por CUIT
  - un CUIT que no esta en identity_v1 no obtiene clave provisional

SOLO LECTURA.
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from engine.config import load_settings  # noqa: E402
from engine.db import get_admin_engine  # noqa: E402

import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "c3_cnv_fetch", REPO / "scripts" / "engine" / "c3_cnv_fetch.py")
c3 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(c3)

OUT = REPO / "outputs" / "docs" / "fase_cnv"

# (etiqueta, cuit, cik, esperado_ok, motivo_esperado)
CASOS = [
    ("YPF   por CUIT", "30546689979", None, True,  "AUTORITATIVO"),
    ("YPF   por CIK ", None, "0000904851", True,  "AUTORITATIVO"),
    ("TGS   por CUIT", "30657862068", None, True,  "AUTORITATIVO"),
    ("TGS   por CIK ", None, "0000931427", True,  "AUTORITATIVO"),
    ("CEPU  por CUIT", "33650305499", None, True,  "AUTORITATIVO"),
    ("CEPU  por CIK ", None, "0001717161", True,  "AUTORITATIVO"),
    ("GGAL  por CUIT", "30704962807", None, False, "CUIT_NO_AUTORITATIVO"),
    ("GGAL  por CIK ", None, "0001114700", False, "CUIT_NO_AUTORITATIVO"),
    ("CUIT inexistente", "99999999999", None, False, "NO_ESTA_EN_IDENTITY_V1"),
    ("CIK  sin CUIT (AAPL)", None, "0000320193", False, "SIN_CUIT"),
]


def main() -> int:
    s = load_settings()
    if s.is_prod:
        print("EXT-010: abortado.")
        return 2
    eng = get_admin_engine(s)
    OUT.mkdir(parents=True, exist_ok=True)
    res, ok_total = [], True

    print("BANCO — resolucion de identidad CNV contra identity_v1\n")
    print(f"  {'caso':<22} {'esperado':<24} {'obtenido':<24} entity_key / motivo")

    for etiqueta, cuit, cik, esp_ok, esp_motivo in CASOS:
        r = c3.resolver_en_identity_v1(eng, cuit, cik)
        ok = (r["ok"] == esp_ok) and (r["motivo"] == esp_motivo)
        det = r.get("entity_key", "-") if r["ok"] else r["motivo"]
        print(f"  {'OK   ' if ok else 'FALLA'} {etiqueta:<22} "
              f"{esp_motivo:<24} {r['motivo']:<24} {det}")
        res.append({"caso": etiqueta, "esperado": esp_motivo, "obtenido": r["motivo"],
                    "ok": ok, "entity_key": r.get("entity_key"),
                    "cuit": r.get("cuit"), "cik": r.get("cik")})
        ok_total &= ok

    # --- CUIT derivado del CIK == CUIT pasado a mano ------------------------
    print("\n  equivalencia de las dos puertas de entrada")
    for nombre, cuit, cik in (("YPF", "30546689979", "0000904851"),
                              ("TGS", "30657862068", "0000931427"),
                              ("CEPU", "33650305499", "0001717161")):
        a = c3.resolver_en_identity_v1(eng, cuit, None)
        b = c3.resolver_en_identity_v1(eng, None, cik)
        igual = a.get("entity_key") == b.get("entity_key") and a.get("cuit") == b.get("cuit")
        print(f"  {'OK   ' if igual else 'FALLA'} {nombre:<6} --cuit y --cik dan la misma "
              f"entidad y el mismo CUIT  ({b.get('cuit')})")
        res.append({"caso": f"{nombre}: --cuit == --cik", "ok": igual})
        ok_total &= igual

    # --- load_identity: el BLOCK tiene que ser un corte, no un hallazgo -----
    print("\n  load_identity() corta antes de abrir corrida cuando no hay VERIFIED")
    try:
        c3.load_identity(eng, cuit="30704962807")
        print("  FALLA GGAL: load_identity no bloqueo")
        res.append({"caso": "GGAL bloquea en load_identity", "ok": False})
        ok_total = False
    except SystemExit as e:
        corta = "BLOCK identidad" in str(e) and "CUIT_NO_AUTORITATIVO" in str(e)
        print(f"  {'OK   ' if corta else 'FALLA'} GGAL -> {str(e)[:110]}")
        res.append({"caso": "GGAL bloquea en load_identity", "ok": corta, "mensaje": str(e)})
        ok_total &= corta

    print("\n  load_identity() acepta a YPF y devuelve la clave opaca de identity_v1")
    ident = c3.load_identity(eng, cik="0000904851")
    bien = (ident["binding"] == "IDENTITY_V1_AUTORITATIVO"
            and ident["cuit"] == "30546689979"
            and ident["entity_key"].startswith("E")
            and len(ident["entity_key"]) == 27)
    print(f"  {'OK   ' if bien else 'FALLA'} entity_key={ident['entity_key']} "
          f"cuit={ident['cuit']} binding={ident['binding']}")
    for f in ident["findings"]:
        print(f"         [hallazgo] {f[:150]}")
    res.append({"caso": "YPF via load_identity", "ok": bien, "ident": {
        k: v for k, v in ident.items() if k != "identity_db"}})
    ok_total &= bien

    n_ok = sum(1 for r in res if r["ok"])
    print(f"\n  {n_ok}/{len(res)} controles OK")
    (OUT / "cnv_identity_bench.json").write_text(
        json.dumps({"ok": ok_total, "controles": res}, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8")
    print("  evidencia -> outputs/docs/fase_cnv/cnv_identity_bench.json")
    return 0 if ok_total else 1


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    raise SystemExit(main())
