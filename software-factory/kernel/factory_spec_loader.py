"""FactorySpecLoader -- lee y valida FACTORY-SPEC.md; no la duplica en Python.

Extrae de forma declarativa lo que FACTORY-SPEC.md ya define en prosa/tablas,
en vez de hardcodear una segunda copia de esas reglas en codigo:

  - la version de la Factory (encabezado del documento)
  - las etapas del Pipeline y su orden (tabla de la Seccion 7)
  - los nombres de estado que la Seccion 8 menciona, para que
    `state_machine.py` pueda contrastarse contra ellos (ver
    `tests/test_factory_spec_loader.py`)

Lo que NO hace: no interpreta la prosa de gobierno (Secciones 2, 11, 12,
etc.) -- esas reglas son normativas para las personas y para los Agents que
todavia no existen, no datos que el Kernel deba parsear para operar.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from kernel.errors import SpecLoadError
from kernel.pipeline_definition import PipelineDefinition, PipelineStage

DEFAULT_SPEC_PATH = Path(__file__).resolve().parents[1] / "FACTORY-SPEC.md"

# Secciones cuya presencia se exige para considerar la spec estructuralmente
# valida (requisito del pedido: "validar su estructura basica"). No exige que
# el contenido sea semanticamente correcto -- eso no es verificable por
# codigo sin un Reviewer humano o de agente, que todavia no existe.
REQUIRED_SECTIONS = (
    "## 1 · Propósito",
    "## 2 · Principios",
    "## 3 · Alcance",
    "## 4 · No-alcance",
    "## 6 · Agentes",
    "## 7 · Pipeline",
    "## 8 · State Machine",
)

_VERSION_RE = re.compile(r"\*\*Versión\*\*:\s*([0-9]+\.[0-9]+\.[0-9]+)")
_SECTION_RE = re.compile(r"^## (\d+(?:\.\d+)?) · (.+)$", re.MULTILINE)
_STATE_TOKEN_RE = re.compile(r"\b(pending|running|blocked|failed|completed|approved|rejected)\b")


@dataclass(frozen=True)
class FactorySpec:
    version: str
    source_path: Path
    pipeline: PipelineDefinition
    state_names_mentioned: frozenset[str]
    raw_text: str


class FactorySpecLoader:
    def __init__(self, spec_path: Path | str = DEFAULT_SPEC_PATH):
        self.spec_path = Path(spec_path)

    def load(self) -> FactorySpec:
        if not self.spec_path.is_file():
            raise SpecLoadError(f"FACTORY-SPEC.md no encontrada en {self.spec_path}")
        text = self.spec_path.read_text(encoding="utf-8")
        if not text.strip():
            raise SpecLoadError(f"FACTORY-SPEC.md esta vacia: {self.spec_path}")

        self._validate_structure(text)
        version = self._extract_version(text)
        pipeline = self._extract_pipeline(text)
        state_names = self._extract_state_names(text)

        return FactorySpec(
            version=version,
            source_path=self.spec_path,
            pipeline=pipeline,
            state_names_mentioned=state_names,
            raw_text=text,
        )

    # ------------------------------------------------------------ privados

    def _validate_structure(self, text: str) -> None:
        faltantes = [s for s in REQUIRED_SECTIONS if s not in text]
        if faltantes:
            raise SpecLoadError(
                f"FACTORY-SPEC.md no tiene la estructura minima exigida; "
                f"faltan secciones: {faltantes}"
            )

    def _extract_version(self, text: str) -> str:
        m = _VERSION_RE.search(text)
        if not m:
            raise SpecLoadError(
                "FACTORY-SPEC.md no declara una version en el formato "
                "'**Versión**: X.Y.Z' esperado en su encabezado"
            )
        return m.group(1)

    def _section_body(self, text: str, heading_prefix: str) -> str:
        """Texto entre un heading '## N · Titulo' (matcheado por prefijo) y
        el siguiente '## '. Falla explicito si no encuentra el heading --
        nunca devuelve una seccion equivocada en silencio."""
        starts = list(_SECTION_RE.finditer(text))
        for i, m in enumerate(starts):
            if text[m.start():].startswith(heading_prefix):
                end = starts[i + 1].start() if i + 1 < len(starts) else len(text)
                return text[m.end():end]
        raise SpecLoadError(f"No se encontro la seccion que empieza con {heading_prefix!r}")

    def _extract_pipeline(self, text: str) -> PipelineDefinition:
        body = self._section_body(text, "## 7 · Pipeline")
        filas = [l for l in body.splitlines() if l.strip().startswith("|")]
        # primera fila = encabezado de la tabla, segunda = separador '---'
        filas_datos = [f for f in filas[2:] if "---" not in f]
        stages = []
        for fila in filas_datos:
            celdas = [c.strip() for c in fila.strip().strip("|").split("|")]
            if len(celdas) < 3:
                continue
            etapa, agentes, condicion = celdas[0], celdas[1], celdas[2]
            if not etapa:
                continue
            typical_agents = tuple(a.strip() for a in agentes.split("+") if a.strip())
            stages.append(PipelineStage(
                name=etapa, transition_condition=condicion, typical_agents=typical_agents,
            ))
        if not stages:
            raise SpecLoadError(
                "La Seccion 7 (Pipeline) de FACTORY-SPEC.md no tiene una tabla "
                "de etapas reconocible -- no se puede derivar el Pipeline sin "
                "duplicarlo a mano"
            )
        return PipelineDefinition(stages=tuple(stages))

    def _extract_state_names(self, text: str) -> frozenset[str]:
        body = self._section_body(text, "## 8 · State Machine")
        return frozenset(_STATE_TOKEN_RE.findall(body))
