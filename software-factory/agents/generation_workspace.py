"""GenerationWorkspace -- el directorio aislado de UN Run para sus archivos
generados. Distinto de `StateManager` (que sigue escribiendo, sin cambios,
`software-factory/runs/<run_id>.json` con el estado/eventos/evidence del
Run) -- esto es solo el filesystem de lo que el Generator produce como
software. No colisiona en el path: uno es `<run_id>.json` (archivo), el
otro `<run_id>/` (directorio).

Estructura, tal como la pide la Fase 4B:

    software-factory/runs/<run_id>/
        requirements/
        specification/
        generated/
        evidence/
        audit/

El software generado NUNCA se escribe fuera de este arbol -- aislado por
completo del codigo real de Catalaxia (`engine/`, `scripts/`, `api/`, etc.),
que ademas esta en un working tree distinto de `software-factory/`.

Fase 5D (FINDING-01, INDEPENDENT-VERIFICATION-5C.md): esa garantia NO se
cumplia en codigo -- `Path(base_dir) / run_id` aceptaba cualquier string,
incluido `run_id="../escape"`, permitiendo escribir fuera de `base_dir`. Se
corrige con `kernel.identifiers`: `assert_safe_identifier()` rechaza la
forma antes de tocar el filesystem, y `safe_child_path()` verifica
containment real (defensa en profundidad, no solo forma) al resolver
`self.root`.
"""
from __future__ import annotations

import json
from pathlib import Path

from kernel.identifiers import assert_safe_identifier, safe_child_path

RUNS_DIR = Path(__file__).resolve().parents[1] / "runs"

SUBDIRS = ("requirements", "specification", "generated", "evidence", "audit")


class GenerationWorkspace:
    def __init__(self, run_id: str, base_dir: Path | str = RUNS_DIR):
        assert_safe_identifier(run_id, label="run_id")
        self.run_id = run_id
        self.root = safe_child_path(base_dir, run_id)

    def ensure(self) -> "GenerationWorkspace":
        for sub in SUBDIRS:
            (self.root / sub).mkdir(parents=True, exist_ok=True)
        return self

    def path_for(self, subdir: str, filename: str) -> Path:
        if subdir not in SUBDIRS:
            raise ValueError(f"subdirectorio desconocido: {subdir!r}; validos: {SUBDIRS}")
        return self.root / subdir / filename

    def write_text(self, subdir: str, filename: str, content: str) -> Path:
        self.ensure()
        path = self.path_for(subdir, filename)
        path.write_text(content, encoding="utf-8")
        return path

    def write_json(self, subdir: str, filename: str, data: dict) -> Path:
        return self.write_text(subdir, filename, json.dumps(data, indent=2, default=str))
