"""FactorySpecLoader: carga la FACTORY-SPEC.md REAL del repositorio.

Cubre TEST 6 del pedido de Fase 2 -- no un mock, la especificacion real que
vive en software-factory/FACTORY-SPEC.md.
"""
from __future__ import annotations

import pytest

from kernel.errors import SpecLoadError
from kernel.factory_spec_loader import FactorySpecLoader
from kernel.state_machine import TRANSITIONS


def test_carga_la_factory_spec_real(real_spec):
    """TEST 6."""
    assert real_spec.version == "0.1.0"
    assert real_spec.source_path.name == "FACTORY-SPEC.md"
    assert len(real_spec.pipeline.stages) == 12   # Requirement..Delivery, Seccion 7
    assert real_spec.pipeline.first_stage() == "Requirement"
    assert "Delivery" in real_spec.pipeline.stage_names


def test_las_12_etapas_de_la_spec_estan_en_orden(real_spec):
    esperado = [
        "Requirement", "Specification", "Architecture", "Contracts",
        "Invariants", "Evals", "Plan", "Tasks", "Code", "Validation",
        "Review", "Delivery",
    ]
    assert real_spec.pipeline.stage_names == esperado


def test_estados_de_state_machine_coinciden_con_lo_que_menciona_la_spec(real_spec):
    """Si `state_machine.py` y FACTORY-SPEC.md Seccion 8 alguna vez
    divergen, este test falla y reporta la contradiccion -- no la resuelve
    en silencio (regla explicita del pedido de Fase 2)."""
    nombres_en_codigo = {s.value.lower() for s in TRANSITIONS}
    assert real_spec.state_names_mentioned == nombres_en_codigo, (
        f"Contradiccion entre state_machine.py y FACTORY-SPEC.md Seccion 8: "
        f"codigo declara {sorted(nombres_en_codigo)}, "
        f"la spec menciona {sorted(real_spec.state_names_mentioned)}"
    )


def test_spec_inexistente_falla_explicito(tmp_path):
    loader = FactorySpecLoader(spec_path=tmp_path / "NO-EXISTE.md")
    with pytest.raises(SpecLoadError):
        loader.load()


def test_spec_sin_estructura_minima_falla_explicito(tmp_path):
    incompleta = tmp_path / "FACTORY-SPEC.md"
    incompleta.write_text("# Spec a medio escribir\n\nNada mas.", encoding="utf-8")
    loader = FactorySpecLoader(spec_path=incompleta)
    with pytest.raises(SpecLoadError):
        loader.load()
