"""Validacion minima de identificadores usados para construir paths --
Fase 5D, corrigiendo FINDING-01 (INDEPENDENT-VERIFICATION-5C.md): un `run_id`
no sanitizado permitia escapar del arbol de trabajo esperado en
`GenerationWorkspace` y `StateManager` (`Path(base_dir) / run_id` sin
ninguna validacion de forma).

Alcance deliberadamente minimo: NO es un sistema general de seguridad --
es la defensa puntual que cierra el sink concreto que el reporte demostro
explotable (`run_id="../algo"` escapando el root autorizado). Dos capas,
ambas necesarias (una sola no alcanza):

  1. `assert_safe_identifier()` -- forma: solo caracteres seguros para un
     nombre de componente de path (alfanumerico, guion, guion bajo), nunca
     vacio, nunca "." ni "..". Rechaza ANTES de tocar el filesystem.
  2. `safe_child_path()` -- containment: resuelve el path final
     (`Path.resolve()`) y verifica que sigue siendo descendiente del root
     autorizado (tambien resuelto). Defensa en profundidad: aunque la forma
     pasara la validacion 1 por algun caso no anticipado, el containment
     check sigue bloqueando cualquier escritura fuera del root.

No valida "que run_id sea un UUID" (la regla explicita del pedido: "No
confiar solamente en que los run_id normales son UUID" iba en el sentido de
NO asumir eso como suficiente defensa -- pero tampoco hace falta exigir
formato UUID; alcanza con que sea un nombre de componente de path seguro).
"""
from __future__ import annotations

import re
from pathlib import Path

_SAFE_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9._-]+$")


class UnsafeIdentifierError(ValueError):
    """Un identificador (hoy: `run_id`) no es seguro para usarse como
    componente de un path -- o bien su forma es invalida, o bien el path
    resultante escaparia del root autorizado."""


def assert_safe_identifier(value: str, *, label: str = "identifier") -> None:
    """Rechaza cualquier `value` que no sea un nombre de componente de path
    seguro: vacio, con separadores (`/`, `\\`), o igual a `.`/`..` (que un
    regex de caracteres permitidos no captura por si solo, ya que `.` y `-`
    son caracteres validos en un run_id normal)."""
    if not isinstance(value, str) or not value:
        raise UnsafeIdentifierError(f"{label} vacio o no es un str: {value!r}")
    if value in (".", ".."):
        raise UnsafeIdentifierError(f"{label} no puede ser {value!r}")
    if not _SAFE_IDENTIFIER_RE.fullmatch(value):
        raise UnsafeIdentifierError(
            f"{label} contiene caracteres no permitidos: {value!r} "
            f"(solo se permite [A-Za-z0-9._-])"
        )


def safe_child_path(root: Path | str, *parts: str) -> Path:
    """Resuelve `root/parts...` y garantiza por CONTAINMENT (no solo por
    forma) que el resultado sigue siendo un descendiente de `root` --
    segunda capa de defensa independiente de `assert_safe_identifier()`.
    Levanta `UnsafeIdentifierError` si el path resuelto escapa del root."""
    root_resolved = Path(root).resolve()
    candidate = (root_resolved / Path(*parts)).resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError:
        raise UnsafeIdentifierError(
            f"path resultante {candidate} escapa del root autorizado {root_resolved}"
        ) from None
    return candidate
