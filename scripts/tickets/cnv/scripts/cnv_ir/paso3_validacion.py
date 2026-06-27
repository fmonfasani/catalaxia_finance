# -*- coding: utf-8 -*-
"""
PASO 3 — VALIDACION. Aplica las identidades contables a cada registro extraido.
Marca 'ok' (identidad cierra <1%) / 'parcial' / 'sin_datos'. Solo lo 'ok' se
considera confiable para cargar. Es el CHECKSUM del estado contable.
"""
from __future__ import annotations


def validar(registros):
    from parser_eeff import validar as identidades
    out = []
    for r in registros:
        d = r.get("datos", {})
        chk = identidades(d)
        idv = chk.get("Activo=Pas+PN")
        estado = "ok" if (idv is not None and idv < 1) else ("parcial" if d else "sin_datos")
        out.append({**r, "checks": chk, "identidad": idv, "estado_val": estado})
        if estado != "ok":
            print(f"  {r['ticker']:<7} {estado.upper():<8} identidad={(f'{idv:.2f}%' if idv is not None else 'n/a')}")
        else:
            print(f"  {r['ticker']:<7} OK       identidad={idv:.2f}%  (confiable)")
    return out


if __name__ == "__main__":
    import json
    from pathlib import Path
    from config import Config
    from paso2_extraccion import extraer
    val = validar(extraer(Config()))
    print(f"\nOK: {sum(1 for v in val if v['estado_val']=='ok')}/{len(val)}")
