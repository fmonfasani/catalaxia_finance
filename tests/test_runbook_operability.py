"""¿Los runbooks describen el software que existe?

Un manual operativo se degrada distinto que el código: no falla, simplemente
deja de ser cierto. Estos tests comparan cada afirmación verificable de
`docs/runbooks/` contra el repositorio, para que la divergencia rompa el build
en vez de descubrirse cuando alguien intenta operar el sistema.

Lo que NO se prueba acá: que un comando produzca el resultado correcto. Eso son
los Golden Runs, y necesitan Docker y red.
"""
from __future__ import annotations

import csv
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
RB = REPO / "docs" / "runbooks"
APP = RB / "appendices"
MATRIZ = REPO / "outputs" / "runbook" / "RUNBOOK_READINESS_MATRIX.csv"

DOCS = ["00_START_HERE.md", "01_COMMON_OPERATIONS.md",
        "02_SEC_EDGAR_E2E_RUNBOOK.md", "02A_SEC_EDGAR_ADR_ANNEX.md",
        "03_CNV_E2E_RUNBOOK.md", "04_MARKET_DATA_E2E.md",
        "05_RATIO_REFERENCE.md", "06_PROVENANCE.md", "07_CERTIFICATION.md"]
APENDICES = ["ERROR_CATALOG.md", "FALLBACK_MATRIX.md", "LOG_CATALOG.md",
             "CHECKPOINT_CATALOG.md", "RECOVERY_PROCEDURES.md",
             "COMMAND_REFERENCE.md", "DATABASE_REFERENCE.md",
             "GOLDEN_RUNS.md"]

# Rutas que los manuales citan como comando. Se extraen del texto y se
# verifican contra el disco; esta lista es sólo para el chequeo inverso.
RX_SCRIPT = re.compile(r"python\s+((?:scripts|engine)/[\w/]+\.py)")
RX_RUTA = re.compile(r"`((?:scripts|engine|migrations|data|outputs)/[\w./-]+)`")


def _texto(p: Path) -> str:
    return p.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def todos():
    faltan = [d for d in DOCS if not (RB / d).exists()]
    faltan += [a for a in APENDICES if not (APP / a).exists()]
    if faltan:
        pytest.skip(f"faltan runbooks: {faltan}")
    return {d: _texto(RB / d) for d in DOCS} | {a: _texto(APP / a) for a in APENDICES}


@pytest.fixture(scope="module")
def matriz():
    if not MATRIZ.exists():
        pytest.skip("no existe la matriz de readiness")
    return list(csv.DictReader(MATRIZ.open(encoding="utf-8")))


# ── estructura ──────────────────────────────────────────────────────

def test_existen_todos_los_entregables():
    faltan = [f"docs/runbooks/{d}" for d in DOCS if not (RB / d).exists()]
    faltan += [f"docs/runbooks/appendices/{a}" for a in APENDICES
               if not (APP / a).exists()]
    if not MATRIZ.exists():
        faltan.append(str(MATRIZ.relative_to(REPO)))
    assert not faltan, f"entregables ausentes: {faltan}"


# ── V1 · los comandos documentados existen ──────────────────────────

# Único script que puede citarse sin existir en este repo: vive en el worktree
# `catalaxia-cnvmig` y los manuales lo declaran como no integrado. La excepción
# es nominal a propósito — cualquier otro script ausente es un error real.
FUERA_DEL_REPO = {"scripts/engine/c4_cnv_adapter.py"}


def test_v1_los_scripts_documentados_existen(todos):
    """Cada `python scripts/…py` citado tiene que existir en el disco.

    Es el modo de degradación más común de un runbook: alguien renombra o
    mueve un script y el manual sigue diciendo el nombre viejo.
    """
    faltan = []
    for doc, t in todos.items():
        for ruta in set(RX_SCRIPT.findall(t)):
            if (REPO / ruta).exists() or ruta in FUERA_DEL_REPO:
                continue
            faltan.append(f"{doc}: {ruta}")
    assert not faltan, "scripts documentados que no existen:\n  " + "\n  ".join(faltan)


def test_el_script_fuera_del_repo_esta_declarado_como_tal(todos):
    """La excepción de arriba sólo vale si el manual avisa. Un comando que no
    se puede ejecutar y no lo dice es peor que no documentarlo."""
    for ruta in FUERA_DEL_REPO:
        if (REPO / ruta).exists():
            pytest.fail(f"{ruta} ya existe en el repo: quitar la excepción del test")
        nombre = Path(ruta).name
        citado = [d for d, t in todos.items() if nombre in t]
        assert citado, f"{ruta} está en la lista de excepciones y nadie lo cita"
        for d in citado:
            t = todos[d]
            assert ("worktree" in t.lower() or "no está en" in t
                    or "NO está en" in t or "RUNBOOK GAP" in t), (
                f"{d} cita {nombre} sin declarar que no está en este repo")


def test_v2_no_se_documentan_comandos_inexistentes(todos):
    """Un script marcado explícitamente como inexistente no debe aparecer
    además como comando ejecutable."""
    for doc in ("03_CNV_E2E_RUNBOOK.md", "04_MARKET_DATA_E2E.md",
                "appendices/CHECKPOINT_CATALOG.md"):
        t = todos[doc.split("/")[-1]]
        # el adaptador canónico vive en un worktree: si se lo nombra, tiene
        # que decir que no está en este repo
        if "c4_cnv_adapter.py" in t:
            assert ("worktree" in t.lower() or "no está en" in t
                    or "NO está en" in t), (
                f"{doc} cita c4_cnv_adapter.py sin aclarar que no está en el repo")


# ── V3 · los argumentos documentados son válidos ────────────────────

ARGS_ESPERADOS = {
    "scripts/engine/s02_fetch_ypf.py": {"--cik", "--forms", "--max-filings"},
    "scripts/engine/s03_parse_ypf.py": {"--cik", "--min-xbrl"},
    "scripts/engine/s04_normalize.py": {"--dry-run"},
    "scripts/engine/ratio_engine.py": {"--persist", "--cik"},
    "scripts/engine/c3_cnv_fetch.py": {"--cuit", "--cik", "--scope", "--rerun"},
}


def test_v3_los_argumentos_documentados_existen_en_el_codigo():
    """Cada argumento que la referencia promete tiene que estar en el
    `add_argument` del script, no sólo en la prosa."""
    ref = _texto(APP / "COMMAND_REFERENCE.md") if (APP / "COMMAND_REFERENCE.md").exists() else ""
    for ruta, args in ARGS_ESPERADOS.items():
        p = REPO / ruta
        assert p.exists(), ruta
        src = p.read_text(encoding="utf-8", errors="replace")
        reales = set(re.findall(r'add_argument\(\s*"(--[\w-]+)"', src))
        faltan = args - reales
        assert not faltan, f"{ruta}: documentados pero ausentes en el codigo: {faltan}"
        if ref:
            for a in args:
                assert a in ref, f"COMMAND_REFERENCE.md no documenta {a} de {ruta}"


def test_job5_no_usa_argparse_y_el_manual_lo_dice():
    """job5 parsea sys.argv a mano. Documentarlo como si tuviera argparse
    llevaría a un operador a probar `--help` y no obtener nada."""
    src = (REPO / "scripts/tickets/cnv/jobs/job5_v2_extract_eeff.py").read_text(
        encoding="utf-8", errors="replace")
    assert "add_argument" not in src, "job5 ahora usa argparse: actualizar el manual"
    ref = _texto(APP / "COMMAND_REFERENCE.md")
    assert "no usa `argparse`" in ref or "no usa argparse" in ref
    for a in ("--rango", "--max", "--sleep", "--cuits", "--offline"):
        assert f'"{a}"' in src, f"{a} documentado pero ausente en job5"
        assert a in ref, f"{a} existe en job5 pero no está documentado"


# ── V4 · los checks documentados existen ────────────────────────────

def test_v4_los_ids_de_check_existen_en_el_codigo():
    """Los `C-*` del catálogo de errores salen del código. Si el catálogo
    inventa uno, un operador buscaría en los logs algo que nunca aparece."""
    cat = _texto(APP / "ERROR_CATALOG.md")
    documentados = set(re.findall(r"`(C-[A-Z0-9]+-\d{3})`", cat))
    assert documentados, "el catálogo no documenta ningún check"
    reales = set()
    for f in (REPO / "scripts" / "engine").glob("*.py"):
        reales |= set(re.findall(r'"(C-[A-Z0-9]+-\d{3})"',
                                 f.read_text(encoding="utf-8", errors="replace")))
    inventados = documentados - reales
    assert not inventados, f"checks documentados que no existen: {sorted(inventados)}"


def test_los_checks_reales_estan_documentados():
    """Y al revés: un check que el código emite y el catálogo no menciona deja
    al operador sin saber qué hacer cuando lo ve."""
    cat = _texto(APP / "ERROR_CATALOG.md")
    reales = set()
    for f in (REPO / "scripts" / "engine").glob("*.py"):
        reales |= set(re.findall(r'"(C-[A-Z0-9]+-\d{3})"',
                                 f.read_text(encoding="utf-8", errors="replace")))
    # los rangos se documentan de forma compacta (C-S04-005…009)
    sin_doc = [c for c in sorted(reales) if c not in cat]
    assert len(sin_doc) <= 6, f"demasiados checks sin documentar: {sin_doc}"


# ── V5 · los estados documentados son los reales ────────────────────

def test_v5_la_maquina_de_estados_documentada_coincide():
    """`07_CERTIFICATION.md` afirma cuáles son los estados. Si alguien agrega
    uno a `engine/states.py`, el manual queda incompleto en silencio."""
    from importlib import import_module
    sys.path.insert(0, str(REPO))
    st = import_module("engine.states")
    reales = {s.value for s in st.StageState}
    gates = {g.value for g in st.GateStatus}
    doc = _texto(RB / "07_CERTIFICATION.md")
    for s in reales | gates:
        assert s in doc, f"estado real no documentado: {s}"
    for inventado in ("QUARANTINED", "RECOVERED"):
        assert inventado not in reales, f"{inventado} ahora existe: actualizar el manual"
        assert "NO EXISTE" in doc, "el manual debe declarar los estados ausentes"


def test_las_transiciones_estan_validadas_en_codigo():
    from importlib import import_module
    sys.path.insert(0, str(REPO))
    st = import_module("engine.states")
    with pytest.raises(ValueError):
        st.assert_transition(st.StageState.RUNNING, st.StageState.PASSED)
    st.assert_transition(st.StageState.RUNNING, st.StageState.VALIDATING)


# ── V6 · checkpoints ────────────────────────────────────────────────

def test_v6_el_checkpoint_documentado_existe():
    cat = _texto(APP / "CHECKPOINT_CATALOG.md")
    ddl = (REPO / "migrations/engine/001_s00_bootstrap.sql").read_text(
        encoding="utf-8", errors="replace")
    assert "engine.checkpoints" in ddl
    for col in ("input_hash", "code_version", "contract_version"):
        assert col in ddl, f"{col} documentada pero ausente del DDL"
        assert col in cat
    s03 = (REPO / "engine/s03.py").read_text(encoding="utf-8", errors="replace")
    assert "def find_checkpoint" in s03 and "def input_hash" in s03


def test_no_existe_resume_y_el_manual_lo_declara():
    """El manual afirma que `--resume` no existe. Si alguien lo implementa,
    el manual pasa a estar mal justo en el punto que más importa."""
    hay = []
    for d in ((REPO / "scripts" / "engine"), (REPO / "engine")):
        for f in d.glob("*.py"):
            src = f.read_text(encoding="utf-8", errors="replace")
            if re.search(r'add_argument\(\s*"--resume"', src):
                hay.append(str(f.relative_to(REPO)))
    assert not hay, f"--resume ahora existe en {hay}: actualizar CHECKPOINT_CATALOG.md"
    assert "no existe" in _texto(APP / "CHECKPOINT_CATALOG.md").lower()


# ── V7 · guard de producción ────────────────────────────────────────

def test_v7_el_guard_de_produccion_existe_y_funciona():
    """EXT-010 es el único código de error real del sistema y el manual lo
    pone como verificación obligatoria. Tiene que dispararse de verdad."""
    cfg = (REPO / "engine/config.py").read_text(encoding="utf-8", errors="replace")
    assert "EXT-010" in cfg
    assert 'db_port == "5432"' in cfg
    r = subprocess.run(
        [sys.executable, "-c",
         "import os,sys; sys.path.insert(0,r'%s');"
         "os.environ['ENGINE_DB_PORT']='5432';"
         "os.environ.pop('ENGINE_ALLOW_PROD',None);"
         "from engine.config import load_settings; load_settings()" % REPO],
        capture_output=True, text=True, timeout=60)
    assert r.returncode != 0, "load_settings() aceptó el puerto de producción"
    assert "EXT-010" in (r.stderr + r.stdout)


def test_el_puerto_de_produccion_esta_documentado_en_todos_lados(todos):
    for doc in ("00_START_HERE.md", "01_COMMON_OPERATIONS.md"):
        t = todos[doc]
        assert "5432" in t and "5433" in t
        assert "EXT-010" in t


# ── V8 · golden runs ────────────────────────────────────────────────

def test_v8_el_golden_run_sec_apunta_al_cik_real():
    gr = _texto(APP / "GOLDEN_RUNS.md")
    src = (REPO / "scripts/engine/s02_fetch_ypf.py").read_text(
        encoding="utf-8", errors="replace")
    m = re.search(r'GOLDEN_CIK\s*=\s*"(\d{10})"', src)
    assert m, "GOLDEN_CIK ya no está declarado en s02"
    assert m.group(1) in gr, (
        f"GOLDEN_RUNS.md no menciona el GOLDEN_CIK real {m.group(1)}")


def test_v8b_el_caso_de_diagnostico_cnv_existe_en_disco():
    """El caso obligatorio METR 30/09/2024 tiene que ser reproducible: si el
    archivo no está, el manual documenta un ejemplo que nadie puede correr."""
    gr = _texto(APP / "GOLDEN_RUNS.md")
    m = re.search(r"`([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})`", gr)
    assert m, "GOLDEN_RUNS.md no declara el GUID del caso de diagnóstico"
    guid = m.group(1)
    p = REPO / "scripts/tickets/cnv/eeff/eeff_html" / f"{guid}.html"
    if not p.exists():
        pytest.skip("el corpus RAW no está en esta instalación")
    import hashlib
    sha = hashlib.sha256(p.read_bytes()).hexdigest()
    assert sha in gr, f"el SHA256 publicado no coincide con el archivo ({sha})"


# ── V9 · la matriz ──────────────────────────────────────────────────

ESTADOS = {"READY", "PARTIAL", "RUNBOOK_GAP", "SOFTWARE_GAP", "BLOCKED"}
COLUMNAS = ["component", "stage", "command", "precondition", "output",
            "checkpoint", "logging", "error_code", "fallback", "recovery",
            "idempotency", "provenance", "production_guard", "documented",
            "tested", "status"]


def test_v9_la_matriz_tiene_el_formato_pedido(matriz):
    assert list(matriz[0].keys()) == COLUMNAS
    for f in matriz:
        assert f["status"] in ESTADOS, f"{f['stage']}: estado {f['status']}"
        for c in ("component", "stage", "command", "output"):
            assert f[c], f"{f['stage']}: {c} vacío"


def test_la_matriz_no_declara_READY_lo_que_tiene_gaps(matriz):
    """Una fila READY no puede admitir a la vez que le falta el mecanismo."""
    for f in matriz:
        if f["status"] != "READY":
            continue
        for c in ("logging", "recovery", "idempotency", "production_guard"):
            assert "NINGUN" not in f[c].upper(), (
                f"{f['stage']} es READY pero {c}={f[c]!r}")


def test_los_scripts_de_la_matriz_existen(matriz):
    faltan = []
    for f in matriz:
        for ruta in RX_SCRIPT.findall(f["command"]):
            if not (REPO / ruta).exists():
                # el adaptador canónico está declarado como fuera del repo
                if "c4_cnv_adapter" in ruta and f["status"] == "RUNBOOK_GAP":
                    continue
                faltan.append(f"{f['stage']}: {ruta}")
    assert not faltan, f"la matriz cita scripts inexistentes: {faltan}"


# ── V10 · lo que el manual promete que NO existe ────────────────────

def test_v10_los_gaps_declarados_siguen_siendo_gaps():
    """Si alguien implementa cuarentena, el manual queda mintiendo al revés:
    diría que no existe algo que sí. Es tan malo como lo contrario."""
    hits = []
    for d in ((REPO / "engine"), (REPO / "scripts" / "engine"),
              (REPO / "migrations" / "engine")):
        for f in list(d.glob("*.py")) + list(d.glob("*.sql")):
            if re.search(r"quarant|cuarentena",
                         f.read_text(encoding="utf-8", errors="replace"), re.I):
                hits.append(str(f.relative_to(REPO)))
    assert not hits, f"la cuarentena ahora existe en {hits}: actualizar los manuales"


def test_ningun_manual_manda_a_consultar_una_ia():
    """Criterio 19 del gate: el runbook tiene que ser autosuficiente."""
    prohibido = ("preguntale a chatgpt", "preguntar a chatgpt", "usa claude",
                 "consultá a claude", "consultar a claude", "pedile a la ia",
                 "preguntale al desarrollador", "consultá al desarrollador")
    for p in list(RB.glob("*.md")) + list(APP.glob("*.md")):
        t = p.read_text(encoding="utf-8").lower()
        for f in prohibido:
            assert f not in t, f"{p.name} manda a consultar: {f!r}"


def test_cada_gap_declarado_tiene_identificador():
    """Un gap sin identificador no se puede seguir entre documentos."""
    ids = set()
    for p in list(RB.glob("*.md")) + list(APP.glob("*.md")):
        ids |= set(re.findall(r"\b(SG-\d{2}|RG-\d{2})\b", p.read_text(encoding="utf-8")))
    assert len(ids) >= 8, f"sólo {len(ids)} gaps identificados: {sorted(ids)}"
    reporte = REPO / "outputs" / "runbook" / "RUNBOOK_READINESS_REPORT.md"
    if reporte.exists():
        t = reporte.read_text(encoding="utf-8")
        sin_explicar = [i for i in sorted(ids) if i not in t]
        assert not sin_explicar, f"gaps citados y no explicados en el informe: {sin_explicar}"
