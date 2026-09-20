"""Classifier: clasificacion determinista de FEATURE/BUG/QUESTION.

Cubre TEST 4, TEST 5 y TEST 6 del pedido de Fase 3. Usa el ejemplo textual
del propio pedido ("Necesitamos agregar alta de clientes con DNI unico").
"""
from __future__ import annotations

from agents.classifier import Category, ClassifierAgent, classify


def test_clasifica_correctamente_un_feature():
    """TEST 4 -- ejemplo literal del pedido de Fase 3."""
    resultado = classify("Necesitamos agregar alta de clientes con DNI único")
    assert resultado.category is Category.FEATURE
    assert resultado.confidence > 0.5
    assert resultado.reason


def test_clasifica_correctamente_un_bug():
    """TEST 5."""
    resultado = classify("El login da error 500 y no funciona desde ayer")
    assert resultado.category is Category.BUG
    assert resultado.confidence > 0.5


def test_clasifica_correctamente_una_question():
    """TEST 6."""
    resultado = classify("¿Cómo se calcula el TTM de un ratio?")
    assert resultado.category is Category.QUESTION
    assert resultado.confidence > 0.5


def test_es_determinista_mismo_input_mismo_output():
    a = classify("Necesitamos agregar alta de clientes con DNI único")
    b = classify("Necesitamos agregar alta de clientes con DNI único")
    assert a == b


def test_pregunta_con_palabra_de_bug_adentro_sigue_siendo_question():
    """Una pregunta sobre un error sigue siendo una pregunta, no un bug --
    se pregunta, no se reporta."""
    resultado = classify("¿Por qué da error el login?")
    assert resultado.category is Category.QUESTION


def test_input_ambiguo_cae_a_feature_con_confianza_baja():
    resultado = classify("hola")
    assert resultado.category is Category.FEATURE
    assert resultado.confidence < 0.5


# ---------------------------------------------------- el agente (execute())

def test_classifier_agent_execute_produce_un_agentresult_ok():
    agent = ClassifierAgent()
    result = agent.execute("Necesitamos agregar alta de clientes con DNI único")
    assert result.status == "OK"
    assert result.agent_id == "classifier"
    assert result.output["category"] == "FEATURE"
    assert result.input == "Necesitamos agregar alta de clientes con DNI único"


def test_classifier_agent_no_lanza_excepcion_con_input_invalido():
    agent = ClassifierAgent()
    result = agent.execute("")
    assert result.status == "ERROR"
    result2 = agent.execute(None)
    assert result2.status == "ERROR"


def test_classifier_no_genera_codigo_ni_modifica_nada():
    """No es un test ejecutable de "ausencia de efectos" exhaustivo -- pero
    confirma la propiedad observable: el output es puramente una
    clasificacion estructurada, sin rutas de archivo, sin artefactos."""
    agent = ClassifierAgent()
    result = agent.execute("Necesitamos agregar alta de clientes con DNI único")
    assert set(result.output.keys()) == {"category", "confidence", "reason"}
