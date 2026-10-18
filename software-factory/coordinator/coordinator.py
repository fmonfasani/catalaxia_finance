"""Coordinator -- orquesta, no ejecuta logica de negocio de ningun Agent.

Circuito exacto de esta fase:

    Kernel (RunManager/StateMachine/PipelineDefinition)
      -> Coordinator lee la etapa actual del Run
      -> consulta PipelineDefinition.agents_for(etapa)   (de FACTORY-SPEC.md, no hardcodeado)
      -> pide ese agente al AgentRegistry
      -> arma el input, llama agent.execute(input)
      -> pasa el AgentResult a RunManager.record_evidence()
      -> pide al RunManager (Kernel) la transicion de estado que corresponda

El Coordinator NUNCA:
  - implementa la logica de clasificacion (esta en agents/classifier.py)
  - muta run.status o run.evidence directamente (siempre via RunManager)
  - elige un agente que el Pipeline no autorizo para esa etapa
  - ejecuta un agente no registrado o deshabilitado

Fase 4A (observabilidad transversal): el Coordinator ahora EMITE eventos
propios (COORDINATOR_STARTED/COMPLETED, AGENT_SELECTED/STARTED/COMPLETED/
FAILED) ademas de los que el Kernel ya emitia por su cuenta -- pero sigue
sin implementar el mecanismo de observabilidad: construye los eventos con
`EventLogger` (Kernel, reusado) y los registra con `RunManager.emit()`
(Kernel, reusado). El Coordinator no es "el sistema de observabilidad", solo
uno de sus tres emisores (junto con Kernel y Agent).

Fase 5A (Contracts): el Coordinator ahora puede validar el `output` de un
Agent contra un `Contract` (`contracts.py`) ANTES de aceptarlo -- pero la
integracion es completamente generica: busca un contrato cuyo id sea
`f"{agent_id.upper()}_OUTPUT"` (la convencion de `contracts_catalog.py`) y,
si existe, valida; si no existe, sigue como antes (sin Contract, el
comportamiento es identico al de la Fase 4B). Nunca hay un
`if agent_id == "generator"` -- el mismo camino de codigo sirve para
Classifier, Generator, y cualquier Agent futuro que declare su Contract en
el catalogo. `registry_contracts=None` (default) preserva el comportamiento
exacto de las fases anteriores para quien construya un Coordinator sin
pasar un ContractRegistry.

Fase 5B (Invariants + Evals + Validator): un Agent (el Validator, pero el
mecanismo no lo nombra) puede EVALUAR en vez de solo producir -- su
`AgentResult.status` es "OK" (ejecuto correctamente) incluso cuando su
VEREDICTO es FAIL (encontro una violacion real). El Coordinator no puede
tratar eso como exito solo porque `status == "OK"`: la convencion generica
(igual que con `output["artifact"]` desde Fase 4B) es reconocer la forma
`output["result"] in {"PASS", "FAIL"}` cuando esta presente, y usar ESE
veredicto -- no `AgentResult.status` -- para decidir si el Run avanza a
COMPLETED o cae a FAILED. Ningun `if agent_id == "validator"`: cualquier
Agent futuro que devuelva esa misma forma (`output["result"]`) queda
cubierto por el mismo camino de codigo, igual que el Validator de hoy.

Fase 5C (same-run orchestration): `execute_stage()` (arriba) sigue exacta,
sin ningun cambio de comportamiento -- una llamada, un agente, una
transicion terminal (COMPLETED/FAILED) al final. Eso es correcto para un
Run de una sola etapa, pero no alcanza para demostrar Generator y Validator
DENTRO del mismo `run_id`: la StateMachine prohibe explicitamente
COMPLETED->RUNNING (regla de la Fase 2), asi que un segundo `execute_stage()`
sobre un Run ya COMPLETED fallaria.

La solucion NO es tocar la StateMachine (seguiria violando esa regla) ni
cambiar el contrato de `execute_stage()` (romperia a todos los tests/codigo
que ya asumen "una llamada = un veredicto terminal"). En su lugar, se agrega
`execute_pipeline()`: una orquestacion de MULTIPLES etapas sobre un unico
Run, donde solo la ULTIMA etapa decide la transicion terminal -- las
intermedias completan su trabajo (agente, contract, artifact, evidence,
avance de etapa) sin tocar `run.status` mas alla de la unica transicion
PENDING->RUNNING inicial. Reutiliza integramente el helper privado
`_run_single_agent()` (la logica que antes vivia inline dentro de
`execute_stage()`, ahora extraida sin cambiar una sola linea de su
comportamiento) -- `execute_stage()` es, literalmente, `execute_pipeline()`
con una unica etapa.

Fase 5D (FINDING-02, INDEPENDENT-VERIFICATION-5C.md, LOW): la Fase 5B
introdujo `output["result"] in {"PASS","FAIL"}` como veredicto que prevalece
sobre `AgentResult.status` -- pero lo reconocia de CUALQUIER agente
registrado bajo cualquier id, con solo mirar la FORMA del output. El
verificador demostro que un agente "impostor" registrado con id "validator"
(o cualquier otro) podia producir esa forma y completar el Run sin ejecutar
ningun check real. La correccion NO elimina el mecanismo generico (seguiria
haciendo falta para agentes futuros de rol VALIDATOR) -- lo ata al ROL
declarado en `AgentMetadata.role` (`agent_contract.py`, ya existente desde la
Fase 3, sin cambios): solo un agente cuyo `metadata.role is AgentRole.VALIDATOR`
puede hacer que su `output["result"]` sea tratado como veredicto terminal.
Un Generator (role=GENERATOR) que intente devolver `output={"result": "PASS"}`
es ignorado como veredicto -- su exito sigue dependiendo unicamente de
`AgentResult.status`, tal como antes de la Fase 5B. Esto no es un framework
de autorizacion nuevo: es una unica comprobacion de un campo que ya existia
(`AgentMetadata.role`), en el unico punto donde el Coordinator ya interpreta
el output de un agente."""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Callable

from agent_contract import AgentRole
from contracts import Contract, ContractRegistry
from coordinator.agent_registry import AgentRegistry
from kernel.errors import KernelError, NoAgentAuthorizedError
from kernel.events import EventLogger
from kernel.run_manager import Run, RunManager
from kernel.state_machine import RunStatus
from observability import make_reference


@dataclass(frozen=True)
class _StepOutcome:
    """Resultado interno de ejecutar UN agente para UNA etapa -- lo que
    `execute_pipeline()` necesita para decidir si sigue a la etapa
    siguiente o corta la orquestacion, sin tocar `run.status` todavia."""
    avanza: bool
    artifact: dict[str, Any] | None
    evidence: dict[str, Any]
    agent_id: str


class Coordinator:
    def __init__(self, run_manager: RunManager, registry: AgentRegistry,
                contract_registry: ContractRegistry | None = None):
        self.run_manager = run_manager
        self.registry = registry
        self.contract_registry = contract_registry
        self.event_logger = EventLogger()

    def _output_contract_for(self, agent_id: str) -> Contract | None:
        """El Contract que declara la forma del output de `agent_id`, si el
        catalogo lo registro -- convencion `f"{AGENT_ID}_OUTPUT"`
        (`contracts_catalog.py`). `None` si no hay ContractRegistry o si ese
        agente todavia no tiene un Contract declarado -- en ambos casos el
        Coordinator sigue funcionando exactamente como en la Fase 4B."""
        if self.contract_registry is None:
            return None
        contract_id = f"{agent_id.upper()}_OUTPUT"
        if not self.contract_registry.is_registered(contract_id):
            return None
        return self.contract_registry.get(contract_id)

    def _agent_id_for_current_stage(self, run: Run) -> str:
        """El primer agente que FACTORY-SPEC.md Seccion 7 declara para la
        etapa actual, normalizado a minuscula (convencion de id del
        Registry: `classifier`, no `Classifier`). Si la tabla declara mas de
        uno (p. ej. "Generator + Reviewer"), esta fase solo sabe pedir el
        primero -- orquestar multiples agentes para una misma etapa es
        trabajo de una fase futura, no de este Coordinator minimo."""
        agentes = self.run_manager.pipeline.agents_for(run.current_stage)
        if not agentes:
            raise NoAgentAuthorizedError(run.current_stage)
        return agentes[0].lower()

    def _run_single_agent(self, run: Run, input_data: Any, *, parent: str) -> _StepOutcome:
        """Corre el agente autorizado para `run.current_stage` sobre
        `input_data`: selecciona, transiciona a RUNNING si hace falta,
        ejecuta, valida Contract, registra evidencia/artifact -- todo, salvo
        la transicion de estado TERMINAL (COMPLETED/FAILED), que decide
        quien llama (`execute_stage()` o `execute_pipeline()`), no este
        metodo. Es exactamente la logica que antes vivia inline dentro de
        `execute_stage()`, extraida sin cambiar una sola decision de
        comportamiento -- solo se le quito el tramo final de transicion
        terminal + COORDINATOR_COMPLETED, que ahora es responsabilidad de
        quien orquesta (para poder encadenar mas de un paso antes de decidir
        el veredicto del Run)."""
        stage = run.current_stage
        agent_id = self._agent_id_for_current_stage(run)

        self.run_manager.emit(run, self.event_logger.agent_selected(
            run.run_id, stage=stage, agent_id=agent_id, parent_event_id=parent,
        ))

        # el Registry es quien sabe si esta registrado Y habilitado -- el
        # Coordinator no duplica esa logica, solo la usa
        agent = self.registry.get_enabled(agent_id)

        if run.status is not RunStatus.RUNNING:
            self.run_manager.transition(run, RunStatus.RUNNING, parent_event_id=parent)

        self.run_manager.emit(run, self.event_logger.agent_started(
            run.run_id, stage=stage, agent_id=agent_id,
            input_reference=make_reference(input_data), parent_event_id=parent,
        ))

        result = agent.execute(input_data)

        # Fase 5A: si el agente reporto OK pero su output no cumple el
        # Contract declarado para el (cuando existe uno), el Coordinator no
        # lo acepta como exitoso -- lo trata como una falla del agente. Esto
        # es lo que impide que un output estructuralmente invalido llegue a
        # convertirse en evidencia/artifact/estado COMPLETED.
        contract = self._output_contract_for(agent_id)
        if result.status == "OK" and contract is not None:
            violaciones = contract.validate_output(result.output)
            if violaciones:
                result = replace(result, status="ERROR",
                                 output={"error": "contract_violation",
                                        "contract_id": contract.contract_id,
                                        "violations": violaciones,
                                        "original_output": result.output})

        # Convencion generica, no especifica de Generator: si el output de
        # CUALQUIER agente trae un "artifact" con esa forma, el Coordinator
        # lo registra -- no necesita saber que agente es, solo reconocer la
        # forma que `agent_contract`/ARTIFACTS.md ya definen.
        artifact = None
        if result.status == "OK" and isinstance(result.output, dict):
            artifact = result.output.get("artifact")

        # Fase 5B: un Agent puede EVALUAR (Validator) en vez de solo
        # producir -- `status == "OK"` significa "se ejecuto sin error de
        # programa", no "el veredicto fue favorable". Si el output trae la
        # forma `{"result": "PASS"|"FAIL", ...}` (convencion generica, ver
        # docstring del modulo), ese veredicto manda sobre `AgentResult.status`
        # para decidir si el Run avanza o queda FAILED.
        #
        # Fase 5D (FINDING-02): ese veredicto SOLO se reconoce si quien lo
        # produjo tiene `metadata.role is AgentRole.VALIDATOR` -- la forma
        # del output ya no alcanza por si sola. Un Generator (o cualquier
        # rol que no sea VALIDATOR) que devuelva `output["result"]` no logra
        # que el Coordinator lo trate como veredicto: `avanza` sigue
        # dependiendo unicamente de `AgentResult.status` para el, exactamente
        # como antes de que existiera este mecanismo.
        veredicto_evaluacion: str | None = None
        if result.status == "OK" and isinstance(result.output, dict) \
                and agent.metadata.role is AgentRole.VALIDATOR:
            veredicto_evaluacion = result.output.get("result")
        avanza = result.status == "OK" and veredicto_evaluacion != "FAIL"

        if avanza:
            self.run_manager.emit(run, self.event_logger.agent_completed(
                run.run_id, stage=stage, agent_id=agent_id,
                output_reference=make_reference(result.output), parent_event_id=parent,
                artifact_id=artifact.get("artifact_id") if artifact else None,
            ))
        else:
            self.run_manager.emit(run, self.event_logger.agent_failed(
                run.run_id, stage=stage, agent_id=agent_id,
                output_reference=make_reference(result.output), parent_event_id=parent,
            ))

        evidence_dict = result.to_dict()
        if artifact and avanza:
            artifact = {**artifact, "evidence_ref": evidence_dict["result_id"]}
            self.run_manager.record_artifact(run, artifact)

        self.run_manager.record_evidence(
            run, agent_id=agent.metadata.id, evidence=evidence_dict, parent_event_id=parent,
            artifact_id=artifact.get("artifact_id") if artifact and avanza else None,
        )

        return _StepOutcome(avanza=avanza, artifact=artifact if avanza else None,
                           evidence=evidence_dict, agent_id=agent_id)

    def execute_stage(self, run: Run, input_data: Any) -> Run:
        """Corre el agente autorizado para `run.current_stage` sobre
        `input_data`, registra la evidencia, y transiciona el estado segun
        el resultado. Devuelve el mismo `run` (mutado via las interfaces del
        Kernel, nunca a mano). Cada paso queda observable, encadenado por
        `parent_event_id` al COORDINATOR_STARTED de esta llamada.

        Sin ningun cambio de comportamiento desde la Fase 5B: una llamada,
        un agente, una transicion terminal. Para orquestar mas de una etapa
        sobre el mismo Run, ver `execute_pipeline()`."""
        stage = run.current_stage
        coord_started = self.event_logger.coordinator_started(run.run_id, stage=stage)
        self.run_manager.emit(run, coord_started)
        parent = coord_started.event_id

        try:
            outcome = self._run_single_agent(run, input_data, parent=parent)
        except NoAgentAuthorizedError as exc:
            self.run_manager.emit(run, self.event_logger.error(
                run.run_id, message=str(exc), stage=stage,
                component="COORDINATOR", parent_event_id=parent,
            ))
            self.run_manager.emit(run, self.event_logger.coordinator_completed(
                run.run_id, stage=stage, status="ERROR", parent_event_id=parent,
            ))
            raise

        if outcome.avanza:
            self.run_manager.transition(run, RunStatus.COMPLETED, parent_event_id=parent)
        else:
            self.run_manager.transition(run, RunStatus.FAILED, parent_event_id=parent)

        self.run_manager.emit(run, self.event_logger.coordinator_completed(
            run.run_id, stage=stage, status=run.status.value, parent_event_id=parent,
        ))

        return run

    @staticmethod
    def _tests_aprobados(evidencia: dict[str, Any]) -> list[str]:
        """IDs de los checks (Invariants + Evals) que REALMENTE corrieron y
        dieron PASS en este paso (DEC-SF-001 regla 3).

        Se leen de `checks`, que es el registro de lo ejecutado -- no de la
        lista de checks que el registro declara conocer. Un test que no corrio
        no aparece, y por lo tanto no puede satisfacer un `required_tests`:
        omitir un test y reprobarlo bloquean COMPLETED por igual.
        """
        if not isinstance(evidencia, dict):
            return []
        # `evidencia` es `AgentResult.to_dict()`: los checks viven en `output`
        # (la forma que declara VALIDATOR.md), no en la raiz.
        output = evidencia.get("output")
        if not isinstance(output, dict):
            return []
        aprobados = []
        for check in output.get("checks", []) or []:
            if isinstance(check, dict) and check.get("status") == "PASS":
                check_id = check.get("id")
                if check_id:
                    aprobados.append(check_id)
        return aprobados

    def execute_pipeline(
        self, run: Run,
        steps: list[tuple[str, Any | Callable[[dict[str, Any] | None, dict[str, Any] | None], Any]]],
    ) -> Run:
        """Orquesta VARIAS etapas sobre el MISMO `run_id` -- Fase 5C
        (same-run orchestration). `steps` es una lista de
        `(stage_name, input_data_o_builder)`; `run.current_stage` debe ser
        ya `steps[0][0]` (el llamador avanza el Run a la primera etapa antes
        de invocar esto, igual que `execute_stage()` no avanza etapas por si
        solo).

        Para cada paso, `input_data_o_builder` puede ser:
          - un valor ya construido (como en `execute_stage()`), o
          - un callable `(artifact_previo, evidence_previa) -> input_data`,
            invocado con el `artifact`/`evidence` que produjo el paso
            ANTERIOR -- asi el Validator recibe una referencia EXPLICITA al
            artifact real del Generator, dentro del mismo Run, sin que
            quien arma `steps` tenga que conocer de antemano un artifact que
            todavia no existe.

        Se detiene en el primer paso que no avanza (`avanza=False`) -- las
        etapas restantes de `steps` no se ejecutan. La transicion TERMINAL
        (COMPLETED si TODOS los pasos avanzaron, FAILED si alguno no) ocurre
        una unica vez, al final, evitando el COMPLETED->RUNNING que la
        StateMachine prohibe entre pasos intermedios."""
        coord_started = self.event_logger.coordinator_started(run.run_id, stage=run.current_stage)
        self.run_manager.emit(run, coord_started)
        parent = coord_started.event_id

        # DEC-SF-001: antes de ejecutar, el alcance declarado manda sobre los
        # steps que trajo el llamador. Si el Run declara un contrato y los
        # steps no lo cubren, esto falla ACA -- no despues de haber corrido
        # agentes para terminar igual en un COMPLETED que no corresponde.
        if run.scope is not None:
            run.scope.assert_steps_cover_scope([nombre for nombre, _ in steps])

        ultimo_artifact: dict[str, Any] | None = None
        ultima_evidencia: dict[str, Any] | None = None
        avanza_pipeline = True
        # Agentes que dejaron evidencia en este pipeline. `run.evidence`
        # guarda el dict crudo del Agent (sin su id), y el id lo conoce el
        # Coordinator al seleccionarlo -- se registra aca en vez de cambiar
        # la forma persistida de la evidencia, que es area protegida.
        agentes_con_evidencia: list[str] = []

        for stage_name, input_data_o_builder in steps:
            if run.current_stage != stage_name:
                self.run_manager.advance_stage(run, stage_name, parent_event_id=parent)

            input_data = (
                input_data_o_builder(ultimo_artifact, ultima_evidencia)
                if callable(input_data_o_builder) else input_data_o_builder
            )

            try:
                outcome = self._run_single_agent(run, input_data, parent=parent)
            except NoAgentAuthorizedError as exc:
                self.run_manager.emit(run, self.event_logger.error(
                    run.run_id, message=str(exc), stage=stage_name,
                    component="COORDINATOR", parent_event_id=parent,
                ))
                avanza_pipeline = False
                break

            ultimo_artifact = outcome.artifact
            ultima_evidencia = outcome.evidence

            # Registro de lo REALMENTE ejecutado, que es contra lo que se
            # verifica el contrato al final. Un paso que no avanzo no cuenta
            # como etapa ejecutada: ejecutarse y cumplir no son lo mismo.
            if outcome.avanza:
                run.executed_stages.append(stage_name)
                if run.last_agent and run.last_agent not in agentes_con_evidencia:
                    agentes_con_evidencia.append(run.last_agent)
                for test_id in self._tests_aprobados(outcome.evidence or {}):
                    if test_id not in run.passed_tests:
                        run.passed_tests.append(test_id)

            if not outcome.avanza:
                avanza_pipeline = False
                break

        # DEC-SF-001 regla 4: agotar los steps no alcanza. COMPLETED exige que
        # el contrato declarado se haya satisfecho de verdad. Sin contrato,
        # `execute_pipeline()` no puede afirmar completitud -- falla cerrado.
        if avanza_pipeline:
            if run.scope is None:
                self.run_manager.emit(run, self.event_logger.error(
                    run.run_id,
                    message=(
                        "DEC-SF-001: execute_pipeline() no puede declarar COMPLETED "
                        "sin un contrato de alcance declarado (run.scope). "
                        "Agotar los pasos del llamador no es evidencia de completitud."
                    ),
                    stage=run.current_stage, component="COORDINATOR", parent_event_id=parent,
                ))
                avanza_pipeline = False
            else:
                try:
                    run.scope.assert_no_stage_skipped(run.executed_stages)
                    run.scope.assert_completion(
                        executed_stages=run.executed_stages,
                        passed_tests=run.passed_tests,
                        evidence_agents=agentes_con_evidencia,
                    )
                except KernelError as exc:
                    self.run_manager.emit(run, self.event_logger.error(
                        run.run_id, message=str(exc), stage=run.current_stage,
                        component="COORDINATOR", parent_event_id=parent,
                    ))
                    avanza_pipeline = False

        if avanza_pipeline:
            self.run_manager.transition(run, RunStatus.COMPLETED, parent_event_id=parent)
        else:
            self.run_manager.transition(run, RunStatus.FAILED, parent_event_id=parent)

        self.run_manager.emit(run, self.event_logger.coordinator_completed(
            run.run_id, stage=run.current_stage, status=run.status.value, parent_event_id=parent,
        ))

        return run
