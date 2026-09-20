"""Invariants concretos de la Factory -- separados de `invariants.py` (el
modelo generico) por el mismo motivo que `contracts_catalog.py` esta
separado de `contracts.py`: el modelo generico no debe conocer al Generator
ni al caso de demostracion ("alta de clientes") por nombre.

Deliberadamente pocos -- la Fase 5B pide explicitamente "no crear invariants
artificiales solamente para llenar archivos". Los dos de abajo son los
minimos necesarios para demostrar el mecanismo end-to-end con el Generator
real (Fase 4B) y su caso de "alta de clientes con DNI unico".
"""
from __future__ import annotations

from typing import Any

from invariants import Invariant, InvariantCheckResult, InvariantRegistry, Severity


def _check_artifact_no_completo_sin_evidencia(context: dict[str, Any]) -> InvariantCheckResult:
    """INV-001: un Artifact no puede existir en `run.artifacts` sin una
    entrada de evidencia que lo respalde -- espejo en Invariant de lo que
    FACTORY-SPEC.md Seccion 6 exige del Generator: *"No puede... decidir que
    su output esta listo -- eso lo determina evidencia, no una afirmacion
    del Generator"*. `context` (armado por el Validator) trae `artifact`
    (dict o None) y `evidence` (dict o None) -- la misma evidencia que el
    Coordinator ya asocio via `evidence_ref` (Fase 4B/5A)."""
    artifact = context.get("artifact")
    if artifact is None:
        return InvariantCheckResult("INV-001", passed=True,
                                    detail="no hay artifact que verificar en este contexto")
    evidence_ref = artifact.get("evidence_ref")
    evidence = context.get("evidence")
    if not evidence_ref or evidence is None:
        return InvariantCheckResult(
            "INV-001", passed=False,
            detail=f"artifact {artifact.get('artifact_id')!r} no tiene evidencia asociada "
                   f"(evidence_ref={evidence_ref!r})",
        )
    return InvariantCheckResult("INV-001", passed=True,
                                detail=f"evidence_ref={evidence_ref} presente y resuelto")


INV_001_ARTIFACT_REQUIERE_EVIDENCIA = Invariant(
    invariant_id="INV-001",
    version="1.0",
    name="Artifact requiere evidencia",
    description=(
        "Un Generator no puede producir un resultado aceptado (COMPLETED) sin que "
        "el Artifact quede correlacionado con una evidencia verificable -- nunca una "
        "aprobacion implicita por la sola existencia del archivo generado."
    ),
    severity=Severity.CRITICAL,
    scope="Generator",
    check=_check_artifact_no_completo_sin_evidencia,
)


def _check_dni_unico(context: dict[str, Any]) -> InvariantCheckResult:
    """INV-002: entre los registros que el software generado ya acepto
    (`context["registros"]`, una lista de dicts con al menos "dni"), no debe
    haber dos con el mismo DNI. Esta es la propiedad de dominio concreta que
    el Requirement de "alta de clientes con DNI unico" exige -- no una
    propiedad generica de la Factory, sino la que este caso de demostracion
    necesita para poder mostrar un FAIL real."""
    registros = context.get("registros", [])
    dnis = [r.get("dni") for r in registros if r.get("dni") is not None]
    duplicados = {d for d in dnis if dnis.count(d) > 1}
    if duplicados:
        return InvariantCheckResult("INV-002", passed=False,
                                    detail=f"DNI duplicado(s) detectado(s): {sorted(duplicados)}")
    return InvariantCheckResult("INV-002", passed=True,
                                detail=f"{len(registros)} registro(s), sin DNI duplicado")


INV_002_DNI_UNICO = Invariant(
    invariant_id="INV-002",
    version="1.0",
    name="DNI unico entre altas",
    description=(
        "Una etapa no puede avanzar si existen dos altas de cliente con el mismo DNI "
        "-- propiedad de dominio exigida por el Requirement de esta demostracion."
    ),
    severity=Severity.CRITICAL,
    scope="Generator",
    check=_check_dni_unico,
)


def build_default_registry() -> InvariantRegistry:
    registry = InvariantRegistry()
    registry.register(INV_001_ARTIFACT_REQUIERE_EVIDENCIA)
    registry.register(INV_002_DNI_UNICO)
    return registry
