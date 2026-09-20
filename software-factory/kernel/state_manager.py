"""StateManager -- persistencia de un Run.

Decision de implementacion (documentada en FACTORY-KERNEL.md): un archivo
JSON por run_id, bajo `software-factory/runs/` por defecto. Es deliberadamente
la opcion mas simple que no agrega una dependencia nueva (nada de Postgres/
SQLite propios todavia) y que mantiene al Kernel independiente del ETL
financiero (que si usa Postgres, via `engine/db.py` / `market_db.py` -- el
Kernel no importa ninguno de los dos). FACTORY-SPEC.md Seccion 9 deja el
mecanismo de persistencia como NO DETERMINABLE CON LA INFORMACION DISPONIBLE
a nivel de diseño; esta es la eleccion concreta para el primer Kernel, no una
promesa de que sea la definitiva.

Fase 5D (FINDING-01, INDEPENDENT-VERIFICATION-5C.md): `_path_for()` era
`runs_dir / f"{run_id}.json"` sin validar `run_id` -- un `run_id="../escape"`
(p. ej. en `save()`, que lo toma del propio `run_dict` que le pasan) permitia
escribir fuera de `runs_dir`. Corregido con `kernel.identifiers`, mismo
mecanismo de dos capas que `GenerationWorkspace`.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from kernel.errors import RunNotFoundError
from kernel.identifiers import assert_safe_identifier, safe_child_path

DEFAULT_RUNS_DIR = Path(__file__).resolve().parents[1] / "runs"


class StateManager:
    def __init__(self, runs_dir: Path | str = DEFAULT_RUNS_DIR):
        self.runs_dir = Path(runs_dir)
        self.runs_dir.mkdir(parents=True, exist_ok=True)

    def _path_for(self, run_id: str) -> Path:
        assert_safe_identifier(run_id, label="run_id")
        return safe_child_path(self.runs_dir, f"{run_id}.json")

    def save(self, run_dict: dict[str, Any]) -> None:
        run_id = run_dict["run_id"]
        path = self._path_for(run_id)
        path.write_text(json.dumps(run_dict, indent=2, default=str), encoding="utf-8")

    def load(self, run_id: str) -> dict[str, Any]:
        path = self._path_for(run_id)
        if not path.is_file():
            raise RunNotFoundError(f"No hay un run persistido con run_id={run_id!r}")
        return json.loads(path.read_text(encoding="utf-8"))

    def exists(self, run_id: str) -> bool:
        return self._path_for(run_id).is_file()

    def list_run_ids(self) -> list[str]:
        return sorted(p.stem for p in self.runs_dir.glob("*.json"))
