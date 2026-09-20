"""Fase 5D -- FINDING-01 (INDEPENDENT-VERIFICATION-5C.md, MEDIUM): un run_id
sin sanitizar permitia escapar del workspace/root autorizado en
GenerationWorkspace y StateManager. Corregido con kernel.identifiers
(assert_safe_identifier + safe_child_path, dos capas independientes: forma
y containment).

Todos los tests aislados con tmp_path -- nunca escriben en
software-factory/runs/ real.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from agents.generation_workspace import GenerationWorkspace
from agents.generator import GeneratorAgent, GeneratorInput
from agents.specification import FieldSpec, Specification
from kernel.identifiers import UnsafeIdentifierError, assert_safe_identifier, safe_child_path
from kernel.state_manager import StateManager

TRAVERSAL_VARIANTS = (
    "..",
    ".",
    "../escape",
    "../../etc",
    "a/b",
    "a\\b",
    "..\\..\\x",
    "run_id/../../escape",
    "",
)


# ------------------------------------------------------- 1. run_id valido funciona

def test_run_id_valido_funciona_generation_workspace(tmp_path):
    ws = GenerationWorkspace("a1b2c3d4-uuid-like", base_dir=tmp_path)
    ruta = ws.write_text("generated", "modulo.py", "contenido")
    assert ruta.is_file()
    assert ruta.is_relative_to(tmp_path.resolve())


def test_run_id_valido_funciona_state_manager(tmp_path):
    sm = StateManager(runs_dir=tmp_path)
    sm.save({"run_id": "a1b2c3d4-uuid-like", "status": "PENDING"})
    assert sm.exists("a1b2c3d4-uuid-like")
    assert sm.load("a1b2c3d4-uuid-like")["status"] == "PENDING"


# --------------------------------------------- 2. run_id con path traversal rechazado

def test_run_id_con_traversal_rechazado_generation_workspace(tmp_path):
    with pytest.raises(UnsafeIdentifierError):
        GenerationWorkspace("../escape", base_dir=tmp_path)


def test_run_id_con_traversal_rechazado_state_manager(tmp_path):
    sm = StateManager(runs_dir=tmp_path)
    with pytest.raises(UnsafeIdentifierError):
        sm.save({"run_id": "../escape", "status": "PENDING"})


# ------------------------------------------- 3. variantes equivalentes rechazadas

@pytest.mark.parametrize("variante", TRAVERSAL_VARIANTS)
def test_variantes_de_traversal_son_rechazadas(tmp_path, variante):
    with pytest.raises(UnsafeIdentifierError):
        assert_safe_identifier(variante, label="run_id")


@pytest.mark.parametrize("variante", TRAVERSAL_VARIANTS)
def test_variantes_de_traversal_rechazadas_en_state_manager(tmp_path, variante):
    sm = StateManager(runs_dir=tmp_path)
    with pytest.raises(UnsafeIdentifierError):
        sm.save({"run_id": variante, "status": "PENDING"})


# ------------------------------------------ 4. ningun archivo creado fuera del root

def test_ningun_archivo_se_crea_fuera_del_root_generation_workspace(tmp_path):
    contenido_antes = set(tmp_path.parent.iterdir())
    try:
        GenerationWorkspace("../escape-gw", base_dir=tmp_path)
    except UnsafeIdentifierError:
        pass
    assert set(tmp_path.parent.iterdir()) == contenido_antes
    assert not (tmp_path.parent / "escape-gw").exists()


def test_ningun_archivo_se_crea_fuera_del_root_state_manager(tmp_path):
    sm = StateManager(runs_dir=tmp_path / "runs")
    contenido_antes = set(tmp_path.iterdir())
    try:
        sm.save({"run_id": "../escape-sm", "status": "PENDING"})
    except UnsafeIdentifierError:
        pass
    assert set(tmp_path.iterdir()) == contenido_antes
    assert not (tmp_path / "escape-sm.json").exists()


def test_generator_con_run_id_malicioso_no_escribe_nada_fuera_del_root(tmp_path):
    """Extremo a extremo: el Generator real (no solo GenerationWorkspace en
    aislamiento) rechaza un run_id malicioso -- status=ERROR, sin escritura
    fuera del `output_dir` autorizado (FINDING-01, reproducido tal como lo
    demostro el reporte independiente contra `Generator.execute()`)."""
    especificacion = Specification(
        spec_id="SPEC-TRAV", entity_name="Cliente", requirement_ref="algo",
        fields=(FieldSpec("nombre", "str", required=True),
                FieldSpec("dni", "str", required=True, unique=True)),
    )
    output_dir = tmp_path / "autorizado" / "generated"
    gi = GeneratorInput(run_id="../pz-escape", requirement="algo", specification=especificacion,
                        authorized_context={"output_dir": output_dir})
    resultado = GeneratorAgent().execute(gi)

    assert resultado.status == "ERROR"
    assert not (tmp_path / "pz-escape").exists()
    assert not (tmp_path.parent / "pz-escape").exists()


# --------------------------------- 5. comportamiento normal de runs existentes intacto

def test_comportamiento_normal_de_runs_reales_no_cambia(tmp_path):
    """Un run_id real (uuid4, formato que RunManager.create_run() ya
    produce) sigue funcionando exactamente igual -- generacion completa,
    archivo fisico, sin ningun cambio de comportamiento."""
    import uuid
    run_id_real = str(uuid.uuid4())
    especificacion = Specification(
        spec_id="SPEC-NORMAL", entity_name="Cliente", requirement_ref="alta normal",
        fields=(FieldSpec("nombre", "str", required=True),
                FieldSpec("dni", "str", required=True, unique=True)),
    )
    output_dir = tmp_path / run_id_real / "generated"
    gi = GeneratorInput(run_id=run_id_real, requirement="alta normal",
                        specification=especificacion,
                        authorized_context={"output_dir": output_dir})
    resultado = GeneratorAgent().execute(gi)

    assert resultado.status == "OK"
    artifact = resultado.output["artifact"]
    assert Path(artifact["reference"]).is_file()
    assert artifact["run_id"] == run_id_real


# --------------------------------------------- extra: containment de safe_child_path

def test_safe_child_path_rechaza_aunque_la_forma_sea_valida_si_escapa(tmp_path):
    """Defensa en profundidad: aunque alguien construyera `parts` de forma
    tal que la concatenacion escape (p. ej. un separador de OS distinto no
    cubierto por el regex), `safe_child_path()` lo bloquea por containment,
    no solo por forma."""
    with pytest.raises(UnsafeIdentifierError):
        safe_child_path(tmp_path, "..", "..", "escape")


def test_safe_child_path_acepta_child_normal(tmp_path):
    resultado = safe_child_path(tmp_path, "sub", "archivo.txt")
    assert resultado.is_relative_to(tmp_path.resolve())
