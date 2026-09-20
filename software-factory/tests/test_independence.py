"""El Kernel no depende del ETL financiero.

Cubre TEST 7 del pedido de Fase 2. Dos verificaciones independientes, no una
sola:

  1. ESTATICA: ningun archivo .py de kernel/ contiene un import de `engine`,
     `scripts.engine`, `scripts.market`, `scripts.pipeline`, `scripts.tickets`
     ni `market_db`/`api`/`backend` -- inspeccionado via el AST real de cada
     archivo, no una busqueda de texto que un comentario podria confundir.
  2. DE EJECUCION: importar todo el paquete `kernel` no agrega al proceso
     ningun modulo cuyo nombre empiece con esos prefijos -- si alguna
     dependencia transitiva se colara (p. ej. una libreria interna que a su
     vez importe `engine`), esto la detectaria aunque el import no sea
     textual en kernel/.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

KERNEL_DIR = Path(__file__).resolve().parents[1] / "kernel"

PREFIJOS_PROHIBIDOS = (
    "engine", "scripts.engine", "scripts.market", "scripts.pipeline",
    "scripts.tickets", "scripts.dolares", "market_db", "api", "backend",
)


def _imports_de(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    nombres = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            nombres.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            nombres.add(node.module)
    return nombres


def test_ningun_archivo_de_kernel_importa_el_etl_financiero():
    ofensores = {}
    for py_file in KERNEL_DIR.glob("*.py"):
        imports = _imports_de(py_file)
        prohibidos = {
            imp for imp in imports
            if any(imp == p or imp.startswith(p + ".") for p in PREFIJOS_PROHIBIDOS)
        }
        if prohibidos:
            ofensores[py_file.name] = prohibidos
    assert not ofensores, f"kernel/ importa modulos del ETL financiero: {ofensores}"


def test_importar_kernel_no_carga_modulos_del_etl_en_el_proceso():
    modulos_antes = set(sys.modules)

    import kernel  # noqa: F401
    import kernel.errors  # noqa: F401
    import kernel.state_machine  # noqa: F401
    import kernel.pipeline_definition  # noqa: F401
    import kernel.factory_spec_loader  # noqa: F401
    import kernel.events  # noqa: F401
    import kernel.run_manager  # noqa: F401
    import kernel.state_manager  # noqa: F401

    modulos_nuevos = set(sys.modules) - modulos_antes
    coladas = {
        m for m in modulos_nuevos
        if any(m == p or m.startswith(p + ".") for p in PREFIJOS_PROHIBIDOS)
    }
    assert not coladas, f"importar kernel cargo modulos del ETL financiero: {coladas}"


def test_kernel_no_requiere_variables_de_entorno_de_base_de_datos():
    """El Kernel no debe necesitar DB_HOST/DB_PORT/MARKET_*/ENGINE_* para
    operar -- si los necesitara, dependeria implicitamente de la
    infraestructura del ETL (Postgres compartido). Verificado leyendo el
    codigo fuente de kernel/: ninguna referencia a esas variables."""
    prohibidas = ("DB_HOST", "DB_PORT", "MARKET_ALLOW_PROD_WRITE", "ENGINE_DB_PORT", "ENGINE_ALLOW_PROD")
    ofensores = {}
    for py_file in KERNEL_DIR.glob("*.py"):
        texto = py_file.read_text(encoding="utf-8")
        hits = {v for v in prohibidas if v in texto}
        if hits:
            ofensores[py_file.name] = hits
    assert not ofensores, f"kernel/ referencia configuracion del ETL financiero: {ofensores}"
