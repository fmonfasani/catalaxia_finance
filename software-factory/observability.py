"""Observabilidad transversal de la Software Factory.

NO pertenece al Kernel, al Coordinator ni a ningun Agent -- es la unica
capa que los conoce a los tres sin que ninguno la conozca a ella en sentido
inverso (Kernel/Coordinator/Agent no importan este modulo; este modulo
importa sus tipos de datos para poder leerlos). Por eso vive en la raiz de
`software-factory/`, al mismo nivel que `agent_contract.py`, no adentro de
`kernel/`.

Tres responsabilidades, deliberadamente separadas (ver OBSERVABILITY.md,
seccion "Audit vs Observability vs Traceability" -- no se mezclan):

  1. Redaccion   -- que NO debe terminar en un evento/referencia.
  2. Trace       -- reconstruir la ejecucion de un Run a partir de sus
                    eventos, ya persistidos por el Kernel (no agrega
                    almacenamiento nuevo).
  3. Consulta    -- una funcion Python para responder "que paso con este
                    run_id" sin tener que leer el JSON a mano.

No crea un mecanismo de eventos paralelo: lee `Run`/`Event`/`StateManager`
tal como el Kernel ya los define.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, is_dataclass
from typing import Any

from kernel.run_manager import Run
from kernel.state_manager import StateManager

# ============================================================== redaccion

# Nombres de clave que, si aparecen en un dict de input/output/evidence,
# nunca deben llegar a un evento en claro. Es una heuristica por NOMBRE de
# clave -- ver limitacion explicita en OBSERVABILITY.md: no detecta un
# secreto embebido dentro de un string libre sin una clave que lo declare.
SENSITIVE_KEY_MARKERS = (
    "password", "passwd", "secret", "token", "api_key", "apikey",
    "credential", "credentials", "auth", "authorization", "private_key",
)


def _is_sensitive_key(key: str) -> bool:
    k = key.lower()
    return any(marker in k for marker in SENSITIVE_KEY_MARKERS)


def redact_value(value: Any) -> str:
    """Reemplaza un valor sensible por una referencia irreversible (hash) --
    permite correlacionar ("es el mismo valor que en otro evento") sin
    exponerlo."""
    huella = hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:16]
    return f"<REDACTED:sha256:{huella}>"


def redact_structure(value: Any) -> Any:
    """Recorre dicts/listas recursivamente y redacta los valores cuya CLAVE
    coincide con `SENSITIVE_KEY_MARKERS`. No toca valores de claves no
    sensibles ni intenta adivinar secretos dentro de un string libre."""
    if isinstance(value, dict):
        return {
            k: (redact_value(v) if _is_sensitive_key(k) else redact_structure(v))
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact_structure(v) for v in value]
    return value


def make_reference(value: Any, max_len: int = 160) -> str:
    """Convierte un input/output de agente en una referencia corta y segura
    para guardar en un Event (`input_reference`/`output_reference`) -- nunca
    el payload completo (eso ya vive, sin truncar, en `run.evidence`, que es
    un mecanismo distinto y ya existente de la Fase 3; esto es solo para el
    rastro de observabilidad, mas liviano).

    Fase 4B: si `value` es una dataclass (p. ej. `GeneratorInput`), se
    convierte a dict (recursivo -- incluye dataclasses anidadas como
    `Specification`) antes de redactar/truncar. No hace falta que cada Agent
    nuevo sepa serializarse: alcanza con ser una dataclass."""
    if is_dataclass(value) and not isinstance(value, type):
        value = asdict(value)
    if isinstance(value, (dict, list, tuple)):
        seguro = redact_structure(value)
        texto = json.dumps(seguro, ensure_ascii=False, default=str)
    else:
        texto = str(value)
    if len(texto) > max_len:
        return texto[:max_len] + f"...(truncado, {len(texto)} caracteres totales)"
    return texto


# ================================================================== artifact

@dataclass(frozen=True)
class Artifact:
    """Modelo de artefacto -- definido en Fase 4A como preparacion (sin
    ningun Generator que lo produjera todavia); la Fase 4B lo CONECTA sin
    cambiar su forma original, solo agregando los campos de trazabilidad
    (`requirement_ref`/`specification_ref`/`evidence_ref`) que la Fase 4A no
    necesitaba porque no habia Requirement/Specification/Evidence que
    enlazar. No es un modelo nuevo -- es el mismo, extendido."""
    artifact_id: str
    run_id: str
    stage: str
    agent_id: str
    type: str
    reference: str
    created_at: str
    parent_artifact_id: str | None = None
    # Fase 4B: trazabilidad REQ -> SPEC -> GEN -> ART -> EVIDENCE
    requirement_ref: str | None = None
    specification_ref: str | None = None
    evidence_ref: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "run_id": self.run_id,
            "stage": self.stage,
            "agent_id": self.agent_id,
            "type": self.type,
            "reference": self.reference,
            "created_at": self.created_at,
            "parent_artifact_id": self.parent_artifact_id,
            "requirement_ref": self.requirement_ref,
            "specification_ref": self.specification_ref,
            "evidence_ref": self.evidence_ref,
        }


# ==================================================================== trace

@dataclass(frozen=True)
class TraceNode:
    event: dict[str, Any]
    children: tuple["TraceNode", ...]


@dataclass(frozen=True)
class Trace:
    """Reconstruccion de una ejecucion completa a partir de `run.events`.

    No es un almacenamiento nuevo: es una VISTA sobre los eventos que el
    Kernel/Coordinator ya escribieron. `roots` son los eventos sin
    `parent_event_id` (o cuyo padre no esta en este Run); `by_id` permite
    ubicar cualquier evento por su `event_id` sin recorrer la lista.
    """
    run_id: str
    events: tuple[dict[str, Any], ...]  # orden cronologico tal como se emitieron
    roots: tuple[TraceNode, ...]
    by_id: dict[str, dict[str, Any]]

    def event_types_in_order(self) -> list[str]:
        return [e["event_type"] for e in self.events]

    def find(self, event_type: str) -> list[dict[str, Any]]:
        return [e for e in self.events if e["event_type"] == event_type]

    def children_of(self, event_id: str) -> list[dict[str, Any]]:
        return [e for e in self.events if e.get("parent_event_id") == event_id]


def build_trace(run_dict: dict[str, Any]) -> Trace:
    """Construye un Trace a partir de un Run ya serializado (`Run.to_dict()`
    o lo que devuelve `StateManager.load()`) -- no requiere reconstruir
    objetos `Event`, trabaja sobre los dicts tal cual quedaron persistidos."""
    eventos = list(run_dict.get("events", []))
    by_id = {e["event_id"]: e for e in eventos}

    nodos: dict[str, TraceNode] = {}

    def nodo_de(event_id: str) -> TraceNode:
        if event_id not in nodos:
            hijos = tuple(
                nodo_de(h["event_id"]) for h in eventos
                if h.get("parent_event_id") == event_id
            )
            nodos[event_id] = TraceNode(event=by_id[event_id], children=hijos)
        return nodos[event_id]

    raices = tuple(
        nodo_de(e["event_id"]) for e in eventos
        if not e.get("parent_event_id") or e["parent_event_id"] not in by_id
    )

    return Trace(
        run_id=run_dict["run_id"],
        events=tuple(eventos),
        roots=raices,
        by_id=by_id,
    )


def render_trace(trace: Trace) -> str:
    """Representacion de texto simple del arbol de eventos -- suficiente
    para la demo y para debugging manual; no reemplaza una UI.

    Usa solo ASCII (`+--`, `|`) a proposito: los conectores Unicode de caja
    (`└──`) rompen en una consola Windows con codepage cp1252 por defecto --
    verificado al correr esto mismo en este entorno."""
    lineas = [f"TRACE run_id={trace.run_id}"]

    def _render(nodo: TraceNode, prefijo: str, es_ultimo: bool) -> None:
        conector = "+-- "
        ev = nodo.event
        lineas.append(f"{prefijo}{conector}{ev['event_type']} "
                      f"(component={ev.get('component')} stage={ev.get('stage')})")
        nuevo_prefijo = prefijo + ("    " if es_ultimo else "|   ")
        for i, hijo in enumerate(nodo.children):
            _render(hijo, nuevo_prefijo, i == len(nodo.children) - 1)

    for i, raiz in enumerate(trace.roots):
        _render(raiz, "", i == len(trace.roots) - 1)
    return "\n".join(lineas)


# =================================================================== consulta

def query_run(run_id: str, state_manager: StateManager | None = None) -> dict[str, Any]:
    """Reconstruye lo minimo pedido para poder responder "que paso con este
    run_id": estado, etapa, eventos, agentes involucrados, transiciones,
    evidence, artifacts. Lee unicamente lo que `StateManager` ya persiste --
    no agrega una fuente de datos nueva."""
    sm = state_manager or StateManager()
    run_dict = sm.load(run_id)

    agentes = sorted({
        e["component_id"] for e in run_dict.get("events", [])
        if e.get("component") == "AGENT" and e.get("component_id")
    })
    transiciones = [
        {"from": e["metadata"]["from_status"], "to": e["metadata"]["to_status"],
         "timestamp": e["timestamp"]}
        for e in run_dict.get("events", []) if e["event_type"] == "STATE_CHANGED"
    ]

    return {
        "run_id": run_dict["run_id"],
        "status": run_dict["status"],
        "current_stage": run_dict["current_stage"],
        "events": run_dict["events"],
        "agents": agentes,
        "transitions": transiciones,
        "evidence": run_dict["evidence"],
        "artifacts": run_dict["artifacts"],
    }
