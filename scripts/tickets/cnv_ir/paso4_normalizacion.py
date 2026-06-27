# -*- coding: utf-8 -*-
"""
PASO 4 — NORMALIZACION. Deja cada registro listo para la base:
  - moneda = ARS, esquema = NIC 29 (re-expresado).
  - fecha_reexpresion = el cierre del periodo (a esa fecha esta re-expresado).
  - period_end ISO + tipo (Q/A).
  - escala ya aplicada en la extraccion (numeros en pesos).
  - HOOK IPC (futuro): re-basar a una fecha comun usando INDEC/FACPCE. Por ahora
    se deja la fecha de re-expresion original (la del filing), que es lo correcto.

No transforma valores (NIC 29 ya viene IPC-ajustado); solo rotula y deja prolijo.
"""
from __future__ import annotations
import calendar


def _period_end(año, mes):
    if not año:
        return None
    mes = mes or 12
    ult = calendar.monthrange(año, mes)[1]
    return f"{año:04d}-{mes:02d}-{ult:02d}"


def normalizar(registros, solo_validos=True):
    out = []
    for r in registros:
        if solo_validos and r.get("estado_val") != "ok":
            continue
        pe = _period_end(r.get("año"), r.get("mes"))
        out.append({
            "ticker": r["ticker"],
            "datos": r["datos"],
            "period_end": pe,
            "tipo": "A" if r.get("tipo") == "anual" else "Q",
            "fecha_reexpresion": pe,         # NIC 29: re-expresado al cierre del periodo
            "moneda": "ARS",
            "esquema": "nic29",
            "fuente": "cnv-ir",
            "metodo": r.get("metodo"),
        })
    print(f"  normalizados (validos): {len(out)}")
    return out


if __name__ == "__main__":
    from config import Config
    from paso2_extraccion import extraer
    from paso3_validacion import validar
    norm = normalizar(validar(extraer(Config())))
    for n in norm[:3]:
        print(f"  {n['ticker']} {n['period_end']} {n['tipo']} | {len(n['datos'])} conceptos")
