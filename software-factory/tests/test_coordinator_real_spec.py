"""El circuito Coordinator+Registry+Classifier funcionando sobre el Pipeline
REAL de FACTORY-SPEC.md (no el toy_pipeline de prueba) -- confirma que
"Requirement -> Classifier" es lo que la spec de verdad declara hoy, y que
el Coordinator lo respeta sin que nadie lo haya hardcodeado."""
from __future__ import annotations

from coordinator.coordinator import Coordinator


def test_requirement_autoriza_al_classifier_en_la_spec_real(real_run_manager, registry_with_classifier):
    coordinator = Coordinator(run_manager=real_run_manager, registry=registry_with_classifier)
    run = real_run_manager.create_run()
    assert run.current_stage == "Requirement"

    coordinator.execute_stage(run, "Necesitamos agregar alta de clientes con DNI único")

    assert run.last_agent == "classifier"
    assert run.last_result["output"]["category"] == "FEATURE"
    assert run.status.value == "COMPLETED"
