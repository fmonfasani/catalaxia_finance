# INDEPENDENT RE-VERIFICATION — FASE 5D

**Rol**: verificador independiente (mismo que auditó 5C; implementador 5D:
Claude). Cero modificaciones a producción, tests o git. Probes adversariales
en archivos temporales fuera del árbol (eliminados; limpieza verificada).
Único permanente: este informe. Marco: CAPA → software-factory
(gobierno/orquestación). PLANOS → CONTROL + DATOS (lineage). CICLO →
VERIFICAR. HOY → 5D implementada sin commitear (sesión 23:33–23:50 UTC
09/09, por mtimes). OBJETIVO → falsar los cierres. DECISIÓN → §13.
EVIDENCIA → clasificada por afirmación (§14).

Lecturas: `INDEPENDENT-VERIFICATION-5C.md`, `HARDENING-5D.md`,
`kernel/identifiers.py` (nuevo), hunks en `generation_workspace.py`,
`state_manager.py`, `coordinator.py`, `validator.py`,
`tests/test_identifiers.py` (28), `tests/test_hardening_5d.py` (13).

## 1. Scope

Cierre de FINDING-01 (MEDIUM, traversal por `run_id`), FINDING-02/04 (LOW,
veredicto sin rol) y FINDING-03-de-5D/FINDING-04-de-5C (LOW, excepción en
Eval). Sin Reviewer/MCP/Risk/Human Gates/paralelismo/capas nuevas (verificado:
no existen en el árbol). Alcance declarado por 5D: 4 archivos nuevos +
4 modificados — confirmado por inspección (más este informe pendiente).

## 2. Baseline

- Comando: `python -m pytest tests/ -q --tb=short`, cwd `software-factory/`.
- Resultado: **179 passed, 0 failed, 0 errors, en 4.04s**
  (VERIFICADO POR EJECUCIÓN). Sin discrepancia con los 179 declarados
  (138 + 28 + 13 = 179, aritmética exacta).
- Entorno: Windows, Python 3.11, pytest 9.1.0; sin DB/red/ETL.

## 3. FINDING-01 Reverification

### Original Finding

`run_id` sin sanitizar → escritura fuera del root en `GenerationWorkspace`
y `StateManager` (MEDIUM, probado en 5C con `run_id="../pz-escape"` →
status OK + archivo externo).

### Attack

Batería de 20 vectores (§4.1 del pedido + `ene`, `...`, `CON`,
`NUL.json`, abierto 5000-caracteres) contra AMBOS sinks, verificando
forma, escritura efectiva y ausencia de archivos fuera de los roots;
containment con symlink real; más ataque derivado: filenames desde
`Specification` (§8 del pedido: "todos los caminos relevantes").

### Evidence

- **run_id, 20 vectores × 2 sinks** (VERIFICADO POR EJECUCIÓN): todos los
  de traversal rechazados con `UnsafeIdentifierError` (`../../outside`,
  `foo/../outside`, `./outside`, `.`, `..`, `/`, `\`, `foo/bar`,
  `foo\bar`, `%2e%2e`, `..%2f`, `null/../outside`, espacios/tabs, vacío,
  unicode). Permitidos solo nombres inertes (`a`×5000, `...`, `CON`,
  `NUL.json`, `.hidden`, `-lider`, `trailing.`) — 0 escapes, 0 archivos
  fuera de los roots (barrido `rglob` completo). Los permitidos largos/
  reservados fallan cerrado a nivel SO si el SO los rechaza.
- **Symlink** (VERIFICADO POR EJECUCIÓN): enlace dentro del root hacia
  víctima externa → `safe_child_path` RECHAZA por containment (`resolve()`
  + `relative_to`); víctima intacta; limpieza verificada.
- **Reproducción 5C** (`run_id="../pz-escape"` en `Generator.execute`
  real): ahora `status=ERROR` (el `except Exception` preexistente lo
  convierte), cero archivos externos — el escenario original está muerto.
- **Filename vía `Specification` — ESCAPE VIGENTE** (VERIFICADO POR
  EJECUCIÓN, ataque derivado §8): con `run_id` válido,
  `entity_name="../../pz-ent2"` → `write_text("generated", ...)` escribe
  FUERA del workspace root; `Generator.execute(entity_name="../../pz-gen")`
  → `status=OK` con `reference` fuera del root. Causa (VERIFICADO POR
  CÓDIGO): el fix valida `run_id` en `__init__`/`_path_for`, pero
  `path_for`/`write_text` nunca validan `filename` (construido desde
  `entity_name.lower()+".py"` / `spec_id+".json"`, ambos caller-controlled,
  sin chequeo en `Specification.validar()`). La defensa-en-profundidad
  ("el containment sigue bloqueando aunque la forma pase") es FALSA en esta
  dimensión: el containment solo cubre `root/run_id`, jamás
  `root/subdir/filename`. (Caso `../pz-ent`: contenido en root pero fuera
  de `generated/` — sub-containment tampoco existe. Caso `sub/dir`:
  `FileNotFoundError` fail-closed, sin escape.)

### Result

El vector `run_id` está muerto en ambos sinks (cierre total de lo
reclamado). El vector filename queda abierto con la misma primitiva.

### Status: CLOSED (vector `run_id`) + NUEVO FINDING-N1 OPEN (MEDIUM, §10)

Nota honesta sobre §11 ("no existe escritura fuera del root" como cláusula
absoluta): en términos absolutos NO se cumple por N1. Certifico CLOSED para
FINDING-01-en-su-alcance (`run_id`, lo único que 5D declaró corregir —
HARDENING-5D §2 lo delimita explícitamente) y abro N1 como finding nuevo
MEDIUM (misma clase y alcanzabilidad que el F-01 original: input de
caller, sin camino no-confiable implementado hoy). Ver §13 para el encuadre
del veredicto.

## 4. FINDING-02/04 Reverification

### Original Finding

El Coordinator trataba `output["result"]` de CUALQUIER agente como
veredicto (5C P1c: rogue registrado como `"validator"` → COMPLETED sin
checks).

### Attack

Generator-rol forjando PASS/FAIL; spoof de `agent_id` en el result;
rogue con `role=VALIDATOR` autodeclarado; validator real PASS/FAIL.

### Evidence

- **Generator forja PASS** (VERIFICADO POR EJECUCIÓN): COMPLETED por
  `status==OK`, sin validator en el camino — indistinguible del
  comportamiento pre-5B; el veredicto forjado no interviene.
- **Generator forja FAIL** (VERIFICADO POR EJECUCIÓN): **COMPLETED** — el
  FAIL forjado es IGNORADO. Un Generator no puede bloquear ni completar
  como validador. (VERIFICADO POR CÓDIGO: línea 220,
  `... and agent.metadata.role is AgentRole.VALIDATOR`.)
- **Spoof `agent_id="validator"` con rol GENERATOR** (VERIFICADO POR
  EJECUCIÓN): ignorado — manda el rol del **ejecutor registrado**, no el
  `agent_id` declarado en el result. La superficie real es el Registry.
- **Rogue con `role=VALIDATOR` autodeclarado** (VERIFICADO POR EJECUCIÓN):
  COMPLETED con evidencia forjada — **el límite documentado por 5D sigue
  abierto, tal como 5D declara** (HARDENING-5D §3: requeriría atestación
  del Registry, fuera de alcance). `AgentMetadata` es frozen pero
  auto-declarada; `registry._agents[id] = X` admite cualquiera. Sin vía
  runtime para registrar agentes (código fijo), igual que en 5C.
- **Validator real** (VERIFICADO POR EJECUCIÓN): PASS→COMPLETED,
  FAIL→FAILED, siempre vía `RunManager.transition` (último evento
  `COORDINATOR_COMPLETED`, `status` del evento = estado final).
- Forja malformada → `contract_violation` → FAILED (defensa de forma
  intacta). Cero literales de veredicto en `coordinator.py` (grep).

### Result

Generadores/roles no-Validador ya no producen veredicto terminal.
Residual: rol autodeclarado (documentado, sin explotante runtime).

### Status: CLOSED (con límite residual declarado, sin cambios)

## 5. FINDING-03 Reverification

### Original Finding

Excepción real en un Eval atravesaba `Validator.execute` → Run en RUNNING
no-terminal, sin `AGENT_FAILED` (5C: `AttributeError` de EVAL-001 con
entidad ≠ Cliente).

### Attack

Reproducción exacta TallerX por pipeline + Eval que levanta a propósito en
aislamiento + persistencia + cadena observable.

### Evidence

- **Pipeline TallerX** (VERIFICADO POR EJECUCIÓN): `status=FAILED` (no
  RUNNING, no COMPLETED, no PASS); `evidence[-1] = {status ERROR,
  error: validation_exception}`; `AGENT_FAILED(validator)` presente;
  último evento `COORDINATOR_COMPLETED/FAILED`.
- **Aislamiento directo** (VERIFICADO POR EJECUCIÓN): `AttributeError`
  deliberado → `status=ERROR`, `checks_completados_antes_de_la_excepción`
  preservados.
- **Persistencia** (VERIFICADO POR EJECUCIÓN): `save/load` sin errores,
  `status=FAILED`, evidencia de la excepción intacta en el JSON.
- **Observabilidad** (VERIFICADO POR EJECUCIÓN): `AGENT_STARTED(validator)`
  → `AGENT_FAILED` → `EVIDENCE_RECORDED` → `STATE_CHANGED→FAILED` →
  `COORDINATOR_COMPLETED`; reconstrucción completa sin inferencia.

### Result

Excepción → ERROR → FAILED terminal, persistido y observable. Nada queda
en RUNNING; nada completa por excepción.

### Status: CLOSED

## 6. Regression

Suite 179/179 (incluye `test_same_run_pipeline` 11/11 y
`test_execute_stage…secuencia exacta`). Re-probado independientemente:
PASS→COMPLETED, FAIL→FAILED (R2e), single-`run_id` (TEST 1 en baseline),
`execute_stage` doble rechaza (P2d de 5C, mecanismo intacto). Demo no
re-ejecutada por mí (5D la re-ejecutó con resultado idéntico; re-ejecutarla
agregaría runs/ sin nueva información — decisión explícita, no omisión).
Sin regresiones.

## 7. Same-Run Verification

TEST 1 (11-checks de 5C re-ejecutados en baseline 179) + R2e: un solo
`run_id` en eventos/evidence/artifacts; `create_run` ×1 por pipeline;
`artifact.evidence_ref ↔ result_id`; validator recibe el artifact del
mismo run. Continúa demostrado.

## 8. Kernel Verification

`RunManager.transition` sigue siendo la única vía de mutación (grep
repetido: cero asignaciones directas fuera de `kernel/run_manager.py`);
terminal única al final de `execute_pipeline()`; `state_machine.py`
idéntico al auditado en 5C (mapa §8: 7 estados/9 transiciones, ver §12 de
mi reporte 5C — re-leído, sin cambios); batería 5C de 17 inválidas sigue
válida por código inalterado. Sin bypass del Kernel.

## 9. Test Quality

- `test_identifiers.py` (28: 2+2+9+9+3+1+2, conteo exacto): sinks reales,
  `tmp_path`, cero mocks, variante end-to-end con `Generator` real,
  comportamiento normal con uuid4, 2 de containment. **STRONG** para el
  vector `run_id` (cualquier reversión del fix lo rompe). Dos puntos
  ciegos honestos: (a) no verifica INDEPENDENCIA de capas (quitar
  `assert_*` dejando `safe_child_path`, o viceversa, seguiría en verde —
  la defensa-en-profundidad se declama pero no se testea por capa);
  (b) **cero cobertura de filename/entity** (mi N1) — coherente con que el
  fix no lo cubre. Clasificación archivo: STRONG con blind-spots
  documentados.
- `test_hardening_5d.py` (13, conteo exacto): rogue PASS/FAIL con rol
  GENERATOR (incluye la aserción honesta de que el dato forjado queda pero
  no domina), malformado→contract, AST anti-forja + presencia de
  `AgentRole.VALIDATOR` (tripwire; el peso lo llevan los tests
  conductuales), excepción exacta/aislada/persistida/nunca-COMPLETED,
  anti-ETL extendido (3 archivos relevantes). Sin mocks; `tmp_path`.
  **STRONG**. Omisión correcta: no testea el residual de rol
  autodeclarado como cerrado (no lo está).
- Regla mutacional aplicada mentalmente a ambos: revertir cada fix rompe
  sus tests (verificado por lectura de las aserciones contra el código
  revertido hipotético). Sin asserts débiles detectados; sin `assert True`
  nuevos.

## 10. New Findings

### FINDING-N1 — Path traversal vía `entity_name`/`spec_id` en filenames (MEDIUM, OPEN)

Ver §3 R1e/R1g: `entity_name="../../pz-gen"` + `run_id` válido →
`GeneratorAgent.execute` devuelve OK con artefacto fuera del workspace.
Misma primitiva y mismos sinks que FINDING-01, dimensión no cubierta por
5D (ni por sus tests). Alcanza MEDIUM por la misma baremación del F-01
original (debilidad real + prueba; sin camino no-confiable implementado
hoy: specifications solo desde tests/demo/builders). Dirección de
endurecimiento (no implementada, regla §15): validar `filename` final con
`safe_child_path(root, subdir, filename)` en `path_for`/`write_text`, o
restringir el charset de `entity_name`/`spec_id` en `Specification`.
No es regresión (el vector existía en 5C, fuera de mi batería de
entonces); es deuda hermanada que el fix dejó al alcance.

## 11. ETL Independence

Cero imports ETL en los 7 archivos nuevos/modificados de 5D (scan
`engine|scripts.*|market_db|api|backend|psycopg2|sqlite3|requests|socket` —
cero hits); `identifiers.py` solo usa stdlib (`re`, `pathlib`).
Mtimes confirman que 5D no tocó nada fuera de `software-factory/`
(ventana 5D 23:33–23:50 UTC; ETL trackeado con mtimes 08/09, 03:36, 21:10
— todos previos y de actividad paralela ajena). `runs/` sigue gitignoreado.
PASS.

## 12. Final Test Count

179 passed, 0 failed (138 previos intactos + 28 + 13 nuevos; ningún test
existente modificado — verificado por conteo y por contenido de los
archivos nuevos). Probes propios: 4 scripts temporales (≈40 verificaciones
de ataque), eliminados con limpieza comprobada.

## 13. Final Verdict

**PASS WITH FINDINGS**

FINDING-01/run_id: CLOSED (batería completa 20 vectores × 2 sinks +
symlink + repro-5C muerto). FINDING-02/04: CLOSED (generadores no
producen veredicto; residual de rol autodeclarado documentado y sin
explotante runtime). FINDING-03: CLOSED (excepción → FAILED terminal,
persistido, observable). Sin regresiones; same-run, Kernel, ETL intactos.

Posición explícita sobre §11/§12: la cláusula absoluta ("no existe
escritura fuera del root") NO se cumple por FINDING-N1 (MEDIUM nuevo,
§10) — y lo declaro en vez de certificar un absoluto falso. El veredicto
no es FAIL porque N1 tiene la misma clase y alcanzabilidad que el F-01
original (que convivió con PASS WITH FINDINGS en 5C), no falsifica
ninguna garantía A–M, y los tres cierres reclamados están demostrados;
FAIL queda reservado (según §12) a findings originales explotables o
bypasses críticos, ninguno presente. Toda la evidencia queda expuesta
arriba para re-baremación independiente.
