"""Evals concretos de la Factory -- separados de `evals.py` (el modelo
generico) por el mismo motivo que `contracts_catalog.py`/`invariants_catalog.py`
estan separados de sus modelos genericos.

Un solo Eval en esta fase, deliberadamente ("no crear artificiales"): el
caso de comportamiento que distingue un Eval de un Invariant -- no basta con
que "el DNI sea unico" como propiedad (eso ya lo cubre INV-002); un Eval
verifica que el SOFTWARE GENERADO efectivamente rechaza el intento, con la
excepcion correcta, ejecutando el modulo real -- comportamiento observado,
no una propiedad inferida de una lista de registros ya existentes.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

from evals import Eval, EvalCheckResult, EvalRegistry


def _dos_altas_mismo_dni_deben_rechazar(input_: Any, expected: Any, context: dict[str, Any]) -> EvalCheckResult:
    """EVAL-001: importa dinamicamente el modulo generado (referenciado por
    `context["code_reference"]`) y ejecuta el escenario real: dos altas con
    el mismo DNI. `expected` describe que la SEGUNDA alta debe levantar
    `ValueError` -- si no lo hace (o si levanta otra excepcion), el Eval
    falla. Esto ejercita el software generado de verdad, igual que la
    "comprobacion minima" de `demo.py` (Fase 4B) -- reutilizando la misma
    tecnica de import dinamico (registrar en `sys.modules` antes de
    `exec_module()`, requerido por el uso de `@dataclass` en el modulo
    generado)."""
    ruta_modulo = context.get("code_reference")
    if not ruta_modulo or not Path(ruta_modulo).is_file():
        return EvalCheckResult("EVAL-001", passed=False,
                               detail=f"code_reference ausente o inexistente: {ruta_modulo!r}")

    nombre_modulo = f"_eval001_{Path(ruta_modulo).stem}"
    try:
        mod_spec = importlib.util.spec_from_file_location(nombre_modulo, ruta_modulo)
        modulo = importlib.util.module_from_spec(mod_spec)
        sys.modules[nombre_modulo] = modulo
        mod_spec.loader.exec_module(modulo)

        alta_cls = getattr(modulo, expected["clase_alta"])
        alta = alta_cls()
        primera = input_["primera_alta"]
        segunda = input_["segunda_alta"]
        alta.alta(**primera)

        try:
            alta.alta(**segunda)
        except ValueError as exc:
            if expected["excepcion_esperada_contiene"] in str(exc):
                return EvalCheckResult("EVAL-001", passed=True,
                                       detail=f"segunda alta rechazada correctamente: {exc}")
            return EvalCheckResult("EVAL-001", passed=False,
                                   detail=f"ValueError con mensaje inesperado: {exc}")
        else:
            return EvalCheckResult("EVAL-001", passed=False,
                                   detail="la segunda alta con DNI duplicado NO fue rechazada")
    finally:
        sys.modules.pop(nombre_modulo, None)


EVAL_001_DNI_DUPLICADO_RECHAZADO = Eval(
    eval_id="EVAL-001",
    version="1.0",
    name="Dos altas con el mismo DNI deben producir rechazo",
    description=(
        "Comportamiento esperado del software generado: dar de alta dos registros "
        "con el mismo DNI debe rechazar el segundo intento con ValueError."
    ),
    input={
        "primera_alta": {"nombre": "Ada Lovelace", "dni": "20111222333", "email": "ada@example.com"},
        "segunda_alta": {"nombre": "Otra Persona", "dni": "20111222333", "email": "otra@example.com"},
    },
    expected={"clase_alta": "AltaClientes", "excepcion_esperada_contiene": "duplicado"},
    evaluation_method=_dos_altas_mismo_dni_deben_rechazar,
    scope="Generator",
)


def build_default_registry() -> EvalRegistry:
    registry = EvalRegistry()
    registry.register(EVAL_001_DNI_DUPLICADO_RECHAZADO)
    return registry
