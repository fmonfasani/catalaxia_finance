#!/usr/bin/env python3
"""Demo del Factory Kernel + Coordinator + Agent Registry + Generator +
Contracts + Invariants + Evals + Validator + Observabilidad transversal.

Fase 4A mostraba el circuito Classifier con trace explicito. Fase 4B agrego
Requirement -> Specification -> Coordinator -> Generator -> Artifact ->
Evidence -> State -> Trace, ejecutando el modulo generado de verdad. Fase 5A
agrego la validacion de Contract del output del Generator antes de que el
Coordinator lo acepte como exitoso. Fase 5B agrego Invariants + Evals +
Validator (PASS/FAIL real), pero corriendo Generator y Validator en DOS Runs
distintos, enlazados solo por referencia al artifact.

Esta version (Fase 5C) corrige esa deuda: Generator y Validator corren
DENTRO DEL MISMO run_id, orquestados por `Coordinator.execute_pipeline()`:

    RUN (un unico run_id)
      -> Coordinator selecciona Generator (etapa "Code")
      -> Generator ejecuta -> Artifact generado -> Evidence registrada
      -> Coordinator avanza la etapa a "Validation" (MISMO Run)
      -> Coordinator selecciona Validator
      -> Validator recibe una referencia EXPLICITA al Artifact real
         (nunca "adivina" cual validar -- se lo pasa el Coordinator)
      -> Validator ejecuta Invariants + Evals -> PASS o FAIL
      -> Coordinator registra el resultado como Evidence
      -> Kernel decide la transicion final: PASS -> COMPLETED, FAIL -> FAILED

Se demuestran DOS ejecuciones reales, cada una en su propio Run (para poder
mostrar ambos veredictos), pero cada una con Generator+Validator compartiendo
un UNICO run_id:

  CASO A (PASS): sin conflicto de DNI -> Run COMPLETED.
  CASO B (FAIL): DNI duplicado deliberado (INV-002) -> Run FAILED, sin
  avanzar -- el Artifact SI existe (el Generator cumplio), pero el Run nunca
  llega a COMPLETED.

Uso:
    cd software-factory && python demo.py
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from agents.generator import GeneratorAgent, GeneratorInput  # noqa: E402
from agents.specification import FieldSpec, Specification  # noqa: E402
from agents.validator import ValidatorAgent, ValidatorInput  # noqa: E402
from contracts_catalog import build_default_registry as build_contracts  # noqa: E402
from coordinator.agent_registry import AgentRegistry  # noqa: E402
from coordinator.coordinator import Coordinator  # noqa: E402
from evals_catalog import build_default_registry as build_evals  # noqa: E402
from invariants_catalog import build_default_registry as build_invariants  # noqa: E402
from kernel.factory_spec_loader import FactorySpecLoader  # noqa: E402
from kernel.run_manager import RunManager  # noqa: E402
from kernel.state_manager import StateManager  # noqa: E402
from observability import build_trace, query_run, render_trace  # noqa: E402

REQUIREMENT = "Alta de clientes: nombre obligatorio, DNI obligatorio y unico, email obligatorio"


def _comprobacion_minima(ruta_modulo: str) -> None:
    """Prueba que el Artifact generado es software REAL y ejecutable."""
    nombre_modulo = "cliente_generado_demo"
    mod_spec = importlib.util.spec_from_file_location(nombre_modulo, ruta_modulo)
    modulo = importlib.util.module_from_spec(mod_spec)
    sys.modules[nombre_modulo] = modulo
    mod_spec.loader.exec_module(modulo)

    alta = modulo.AltaClientes()
    cliente = alta.alta("Ada Lovelace", "20111222333", "ada@example.com")
    print(f"  [OK] alta() creo: {cliente}")

    try:
        alta.alta("Otra Persona", "20111222333", "otra@example.com")
        print("  [FALLO] permitio un DNI duplicado -- no deberia")
    except ValueError as exc:
        print(f"  [OK] rechazo DNI duplicado: {exc}")

    print(f"  [OK] listar() devuelve {len(alta.listar())} registro(s)")
    del sys.modules[nombre_modulo]


def _validator_input_builder(run_id: str, registros: list[dict]):
    """Cierra sobre `run_id`/`registros` de esta ejecucion; recibe el
    `artifact` REAL del paso anterior recien cuando `execute_pipeline()` lo
    invoca -- el Validator nunca adivina que artifact validar."""
    def builder(artifact, evidence):
        return ValidatorInput(
            run_id=run_id, scope="Generator", artifact=artifact, evidence=evidence,
            context={"code_reference": artifact["reference"], "registros": registros},
            invariant_registry=build_invariants(), eval_registry=build_evals(),
        )
    return builder


def _run_same_run_pipeline(spec, caso: str, registros: list[dict]) -> None:
    """Corre Generator -> Validator DENTRO DEL MISMO Run, via
    `execute_pipeline()`."""
    print(f"\n{'=' * 70}\nCASO {caso}\n{'=' * 70}")

    run_manager = RunManager(pipeline=spec.pipeline, factory_version=spec.version)
    run = run_manager.create_run()
    print(f"RUN CREATED  run_id={run.run_id}  current_stage={run.current_stage}")

    run_manager.advance_stage(run, "Code")
    registry = AgentRegistry()
    registry.register(GeneratorAgent())
    registry.register(ValidatorAgent())
    coordinator = Coordinator(run_manager=run_manager, registry=registry,
                              contract_registry=build_contracts())

    especificacion = Specification(
        spec_id=f"SPEC-{caso[0]}", entity_name="Cliente", requirement_ref=REQUIREMENT,
        fields=(
            FieldSpec("nombre", "str", required=True),
            FieldSpec("dni", "str", required=True, unique=True),
            FieldSpec("email", "str", required=True),
        ),
    )
    print(f"REQUIREMENT: {REQUIREMENT!r}")
    print(f"SPECIFICATION: spec_id={especificacion.spec_id} "
          f"campos={[f.name for f in especificacion.fields]}")

    generator_input = GeneratorInput(
        run_id=run.run_id, requirement=REQUIREMENT, specification=especificacion,
    )

    print("\nGENERATOR SELECTED / GENERATOR STARTED (via Coordinator, mismo run_id)")
    coordinator.execute_pipeline(run, [
        ("Code", generator_input),
        ("Validation", _validator_input_builder(run.run_id, registros)),
    ])

    if not run.artifacts:
        print("ARTIFACT: no se genero ninguno (la generacion fallo antes del Validator)")
        state_manager = StateManager()
        state_manager.save(run.to_dict())
        print(f"STATE: {run.status.value}")
        return

    artifact = run.artifacts[-1]
    print(f"ARTIFACT GENERATED: artifact_id={artifact['artifact_id']} "
          f"run_id={artifact['run_id']}  (== run.run_id: {artifact['run_id'] == run.run_id})")
    print(f"  reference={artifact['reference']}")
    print(f"  archivo existe fisicamente: {Path(artifact['reference']).is_file()}")

    print("\nCOMPROBACION MINIMA DEL SOFTWARE GENERADO")
    _comprobacion_minima(artifact["reference"])

    print(f"\nVALIDATOR SELECTED / VALIDATOR STARTED (via Coordinator, mismo run_id={run.run_id})")
    veredicto = run.evidence[-1]["output"]
    print(f"VALIDATOR RESULT: {veredicto['result']}")
    for check in veredicto["checks"]:
        print(f"  [{check['status']:4}] {check['id']}: {check['detail']}")
    if veredicto["failures"]:
        print("FAILURES:")
        for f in veredicto["failures"]:
            print(f"  - {f['id']} ({f['type']}): {f['reason']}")

    print(f"\nEVIDENCE RECORDED: {len(run.evidence)} elemento(s) "
          f"(agentes: {[e['agent_id'] for e in run.evidence]})")

    state_manager = StateManager()
    state_manager.save(run.to_dict())
    print(f"STATE: {run.status.value}  "
          f"({'ADVANCE' if run.status.value == 'COMPLETED' else 'BLOCK/FAIL -- NO ADVANCE'})")

    trace = build_trace(run.to_dict())
    print("\nTRACE START")
    print(render_trace(trace))
    print("TRACE END")

    consulta = query_run(run.run_id, state_manager=state_manager)
    print(f"\nquery_run(): status={consulta['status']}  agentes={consulta['agents']}  "
          f"evidence={len(consulta['evidence'])}  artifacts={len(consulta['artifacts'])}  "
          f"eventos={len(consulta['events'])}")
    print(f"run_id = {run.run_id}  (UN SOLO run_id para Generator + Artifact + Evidence + "
          f"Validator + estado final)")


def main() -> int:
    print("FACTORY LOADED")
    spec = FactorySpecLoader().load()
    print(f"  FACTORY-SPEC.md version={spec.version} pipeline={len(spec.pipeline.stages)} etapas")

    contract_registry = build_contracts()
    invariant_registry = build_invariants()
    eval_registry = build_evals()
    print(f"\nCONTRACT REGISTRY LOADED: {len(contract_registry.list_ids())} contratos")
    print(f"INVARIANT REGISTRY LOADED: {invariant_registry.list_ids()}")
    print(f"EVAL REGISTRY LOADED: {eval_registry.list_ids()}")

    # CASO A -- VALIDACION EXITOSA: sin conflicto de DNI -> mismo Run COMPLETED.
    _run_same_run_pipeline(spec, "A (validacion exitosa)", registros=[{"dni": "30111222333"}])

    # CASO B -- VALIDACION FALLIDA: DNI duplicado deliberado -> mismo Run FAILED.
    _run_same_run_pipeline(spec, "B (validacion fallida)",
                           registros=[{"dni": "40999888777"}, {"dni": "40999888777"}])

    print("\nDEMO COMPLETA")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
