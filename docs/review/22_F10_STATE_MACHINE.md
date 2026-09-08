# 22 — F10: Cierre de la máquina de estados de ejecución

Determina y cierra el defecto transversal que F9 encontró: `run_scope` cerraba
el *run* ante una excepción pero nunca la *etapa*. Solo DEV
(`catalaxia_engine@127.0.0.1:5433`). Evidencia
`[CÓDIGO]`/`[TEST]`/`[EJECUCIÓN]`/`[NO DETERMINABLE]`.

## Contrato actual: RUN STATE vs STAGE STATE (Paso 1)

| | RUN (`engine.runs.status`) | STAGE (`engine.stage_runs.state`) |
|---|---|---|
| tipo | `TEXT`, sin `CHECK` | `TEXT`, sin `CHECK` |
| enforcement | ninguno a nivel DB; por convención en `start_run`/`finish_run` | `StageState` (Python) vía `assert_transition` |
| escritura | `UPDATE` (una fila por run) | `INSERT` puro (log append-only; "estado actual" = última fila por `id`) |
| dueño del cierre | `run_scope` (o el orquestador, en modo E2E) | **nadie**, hasta F10 |
| valores en uso | `RUNNING`, `OK`, `ABORTED`, `BLOCKED` | los 9 de `StageState` (+`ABORTED`, F10) |

**Tabla estado → transición → actor → condición → resultado** (antes de F10,
sólo camino feliz + FAILED; el aborto no tenía representación de etapa):

| estado actual | transición | actor | condición | resultado |
|---|---|---|---|---|
| PLANNED | → READY | script | arranca `run_scope` | fila `READY` |
| READY | → RUNNING | script | empieza el trabajo | fila `RUNNING` |
| RUNNING | → VALIDATING | script | trabajo terminó sin excepción | fila `VALIDATING` |
| VALIDATING | → PASSED / FAILED | script | gate | fila terminal, con `gate_status` y `report` |
| **RUNNING** | **→ (nada)** | **nadie** | **excepción** | **fila RUNNING para siempre** — el defecto |

### ¿`RUN ABORTED` implica `STAGE ABORTED`?

**Sí, por evidencia, no por intuición.** Tres fuentes independientes lo
confirman:

1. **Código**: los 6 escritores de `stage_runs` (`S00`–`S04` + `C3`) siguen el
   idéntico patrón — escriben READY→RUNNING al entrar a `run_scope`, y sólo
   escriben el tramo terminal si el cuerpo no lanzó. Si el run termina
   `ABORTED`, es *porque* el cuerpo lanzó — y ese cuerpo es exactamente la
   etapa. No existe ningún caso donde el run termine ABORTED por una causa
   ajena a la etapa que estaba corriendo dentro de él. `[CÓDIGO]`.
2. **Datos**: los 16 residuos de F9 — re-verificados en `22_PRE_F10_STATE.md`
   — tienen **100 %** de correlación: los 16 tienen `run.status='ABORTED'` y
   la etapa en `RUNNING`. **0 casos** de run ABORTED con etapa en un estado
   terminal (PASSED/FAILED/CHECKPOINTED). `[EJECUCIÓN]`.
3. **Tests existentes**: ninguno de los tres archivos de lifecycle
   (`test_engine_run_lifecycle.py`, `test_f040_lifecycle_c3.py`,
   `test_f050_lifecycle_s00_s02.py`) afirma nada sobre
   `stage_runs.state` — sólo verifican `engine.runs.status`. No hay ningún
   test que dependa de "RUN ABORTED + STAGE RUNNING" como comportamiento
   esperado. `[TEST]` (lectura completa de los tres archivos).

**No existe ningún caso legítimo de `RUN ABORTED + STAGE RUNNING`.** Es
siempre el mismo defecto: la etapa que estaba corriendo dentro del run que
abortó se quedó sin cerrar.

## Impacto transversal (Paso 2)

Se buscaron **todos** los lugares que crean, actualizan, finalizan
`stage_runs`, manejan excepciones, cierran runs, usan `StageState`/`RunState`
o consultan `RUNNING`/`ABORTED` — no sólo `c11_certificar.py`. Resultado: **14
scripts** importan `run_scope`/`record_stage_transition` desde el mismo
`engine/db.py`:

| script | escribe `stage_runs` | patrón afectado |
|---|:-:|:-:|
| `s00_smoke.py` | sí | sí (idéntico) |
| `s01_identity.py` | sí | sí |
| `s02_fetch_ypf.py` | sí | sí |
| `s03_parse_ypf.py` | sí | sí |
| `s04_normalize.py` | sí | sí |
| `c3_cnv_fetch.py` | sí | sí |
| `ratio_engine.py` | no | — |
| `identity_v1_backfill_dev.py` | no | — |
| `identity_v1_backfill_piloto.py` | no | — |
| `backfill_cik.py` | no | — |
| `f024_bma.py` | no | — |
| `f041_reafirmacion.py` | no | — |
| `cnv_negative_pilot.py` | no (sólo docstring) | — |
| `e2e_orchestrator.py` | orquesta a los 6, cierre de *run* propio | — |

**Confirmado transversal**: los 6 que escriben `stage_runs` comparten
exactamente el mismo patrón, y todos pasan por el mismo `run_scope`. Los otros
8 usan `run_scope` sólo para el cierre de *run* (no tienen etapas que cerrar,
verificado: `grep -c record_stage_transition` = 0 en los seis). `[CÓDIGO]`.

## Definición: `StageState.ABORTED` (Paso 3)

```python
StageState.ABORTED = "ABORTED"
```

**ABORTED NO es FAILED.** FAILED significa "un gate corrió y dijo que no" —
tiene un `StageReport` real detrás. ABORTED significa "murió antes de que
nada corriera" — no hay `report`, no hay `gate_status`. Mezclarlos habría sido
inventar evidencia que no existe.

| | quién lo produce | cuándo | qué evidencia requiere |
|---|---|---|---|
| ABORTED | `abort_stage_if_open` (dentro de `run_scope`, camino `except`) | el run que contenía la etapa terminó por excepción | ninguna — es la ausencia de evidencia, registrada explícitamente |

**Transiciones** (`TRANSITIONS` en `engine/states.py`):

```
PLANNED, READY, RUNNING, VALIDATING, FIXING, RERUNNING  →  ABORTED  (nuevo)
FAILED, PASSED, CHECKPOINTED, CERTIFIED                 ↛  ABORTED  (bloqueado)
ABORTED                                                  →  (nada; terminal)
```

Los cuatro estados bloqueados ya tienen evidencia propia y durable:

- **FAILED** — tiene un `StageReport` con gate `BLOCK`. Aunque `FAILED`
  puede reintentar (`→ FIXING`), la fila FAILED en sí misma no se toca.
- **PASSED/CHECKPOINTED** — tiene un `StageReport` con gate `PASS` y, desde
  CHECKPOINTED, una fila en `engine.checkpoints`.
- **CERTIFIED** — tiene una fila en `engine.certifications`.

Un aborto de código *no relacionado*, más tarde en el mismo `run_scope`, no
puede retroactivamente borrar esa evidencia. `FIXING`/`RERUNNING` sí pueden
abortar: ese intento puntual de reintento no dejó su propia evidencia, aunque
la fila FAILED original (inmutable, previa) siga intacta en el historial.

**Qué ocurre con cada consumidor** (verificado, no supuesto — Paso 9 lo
confirma con consultas):

| consumidor | qué ve | cambia con F10 |
|---|---|---|
| `checkpoints` | nada nuevo — la fila ABORTED nunca lleva checkpoint | no |
| `StageReport` | nada — ABORTED nunca lleva `report` | no |
| provenance | la etapa deja de estar "colgada": ahora tiene un evento terminal explícito | mejora, no rompe nada |
| **C10** (`c10_evaluate.py`) | lee `gate_status`, no `state` — una fila ABORTED tiene `gate_status=NULL`, igual que la RUNNING que reemplaza. Mismo veredicto (BLOCK) | **ninguno** |
| **C11** (`c11_certificar.py`) | lee `engine.runs.status` para su regla de `TERMINALES`/`ABORTED` — ya existía, ya funcionaba, sin tocar el código | **ninguno** |
| **C12** (`publisher.py`) | `collect_c10` lee `gate_status`, mismo razonamiento que C10 | **ninguno** |

**No se modificó C10, C11 ni C12.** Verificado con `git diff` (§ protecciones,
`22_IMPLEMENTATION_RESULT.md`).

## Implementación mínima (Paso 4)

Dos archivos con lógica nueva, seis con un parámetro nuevo:

**`engine/states.py`** — el enum `ABORTED` + las entradas de `TRANSITIONS`
descritas arriba (26 líneas).

**`engine/db.py`** — una función nueva y una firma extendida:

```python
def abort_stage_if_open(engine, run_id: str, stage_id: str) -> bool:
    """Cierra la etapa como ABORTED si quedo sin evidencia por una excepcion.
    Solo escribe si el ULTIMO estado conocido admite -> ABORTED. Idempotente."""
    # SELECT ultimo estado de (run_id, stage_id)
    # si no hay fila -> False (nunca arranco, nada que cerrar)
    # si TRANSITIONS[ultimo] no admite ABORTED -> False (ya terminal, no se pisa)
    # si no -> INSERT (record_stage_transition) y True

def run_scope(engine, settings, pipeline_version, run_id=None, stage_id=None):
    ...
    except BaseException as e:
        try:
            if stage_id is not None:
                abort_stage_if_open(engine, run.run_id, stage_id)   # NUEVO
            if run_id is None:
                finish_run(engine, run.run_id, "ABORTED")            # sin cambios
        finally:
            raise e
```

`stage_id` es **opt-in** (default `None`): sin él, `run_scope` se comporta
exactamente igual que antes de F10 — no escribe nada en `stage_runs`
(verificado, test N2). Esto es lo que evita "introducir una nueva autoridad":
no hay un componente nuevo decidiendo nada, es el mismo `run_scope` cerrando
un nivel más.

**Seis scripts, un parámetro cada uno**: `S00`–`S04` + `C3` pasan
`stage_id=STAGE_ID` a su llamada existente a `run_scope`. Un `git diff` real
por archivo:

```diff
- with edb.run_scope(engine, settings, PIPELINE_VERSION,
-                    run_id=os.environ.get("ENGINE_E2E_RUN_ID")) as run:
+ with edb.run_scope(engine, settings, PIPELINE_VERSION,
+                    run_id=os.environ.get("ENGINE_E2E_RUN_ID"),
+                    stage_id=STAGE_ID) as run:
```

(`c3_cnv_fetch.py` en una sola línea, mismo cambio.)

**Ningún `UPDATE` masivo**: `abort_stage_if_open` sólo `INSERT`a — el log de
`stage_runs` sigue siendo append-only. **Ningún dato productivo, RAW,
parsed/facts, C10, C11 o C12 se modificó** — confirmado por `git diff`
acotado y por Paso 9. **Provenance se preserva**: la fila ABORTED trae
`prev_state` apuntando al último estado real (test E2). **Idempotencia**:
`TRANSITIONS[ABORTED] = set()` hace que un segundo intento de cierre no
encuentre transición válida y no escriba nada (tests I/J).

**Hallazgo menor, sin acción**: el `STAGE_ID` de `c3_cnv_fetch.py` en el
código actual es `"C3_CNV_fetch"` (minúscula en "fetch"), pero los 16
residuos históricos quedaron grabados como `'C3_CNV_FETCH'` (mayúscula). No
afecta la corrección del fix — `abort_stage_if_open` usa siempre el mismo
string que ya usa `record_stage_transition` en cada corrida — pero explica
por qué, si se buscara reconciliar el histórico algún día, hay que
buscar ambas variantes.

## Históricos: los 16 residuos de F9 (Paso 5)

**Decisión: (C) — legacy/test residue. No se tocan.**

Los 16 no son evidencia perdida de datos: son residuos de *tests* que
inyectan fallos contra el `main()` real (`test_f040_lifecycle_c3.py` con
`donde=0/1/2`, `test_f050_lifecycle_s00_s02.py` con las inyecciones A1/A2).
Ninguno tiene facts, checkpoint, certificación ni publicación asociada
(re-verificado en `22_PRE_F10_STATE.md`); el run padre de cada uno ya está
`ABORTED` con `finished_at`.

**Por qué no (B) — migración explícita**: escribir una fila `ABORTED` para
esos 16 con `abort_stage_if_open` sería técnicamente correcto (la función es
idempotente y no rompería nada), pero violaría la instrucción explícita del
sprint ("NO modificar automáticamente los 16 registros históricos") y no
aporta nada operativo: nadie los consulta, no bloquean ni certificación ni
publicación (ya se verificó que C10 los trataría igual con `state='RUNNING'`
o `'ABORTED'`, porque mira `gate_status`, no `state`).

**Por qué no (A) — evidencia histórica del bug**: técnicamente lo son, pero
mantenerlos así no aporta más que documentarlo, y documentarlo ya está hecho
(F9 + este documento). No hace falta preservar el dato roto para probar que
existió: el hallazgo ya quedó escrito.

Se re-verificaron **exactos, sin tocar** en Paso 9: 16/16 siguen en `RUNNING`.

## Regresión (Paso 8)

Suite dirigida: lifecycle (3 archivos) + orquestador (2) + C11 (1) + F5–F10 (6)
+ F8 E2E (1) = 11 archivos, **211 tests**.

| resultado | n | clasificación |
|---|---:|---|
| PASS | 175 | incluye los 35 nuevos de F10 y toda la regresión de F5–F9 |
| SKIP | 1 | `test_F2` sobre `ABORTED→ABORTED`, no aplica a sí mismo |
| FAIL | 4 | **PREEXISTENTE**, ver abajo |

Los 4 `FAIL`:

| test | causa real | evidencia de que NO es F10 |
|---|---|---|
| `test_c3_real_cierra_su_corrida_cuando_muere` ×3 | `SystemExit: BLOCK identidad [CUIT_NO_AUTORITATIVO]` — Central Puerto S.A. perdió su CUIT autoritativo en DEV | `git diff` de `c3_cnv_fetch.py` muestra mi único cambio (`stage_id=STAGE_ID`, 1 línea); la firma de `load_identity` ya venía modificada de una sesión anterior, sin relación con F10 |
| `test_J_idempotencia_market` (de F5) | `m1_symbol_mapping.py` exit 1, guarda de `MARKET_ALLOW_PROD_WRITE` | F10 no tocó ningún archivo de `scripts/market/`; `git diff --stat scripts/market/` no incluye ningún cambio mío |

Mismo patrón que F9 documentó ("family identidad/universo CNV stale,
autodeclarada en F6"): degradación de datos en DEV, no del código de F10.

## Cierre de esta sección

`RUN ABORTED ⇒ STAGE ABORTED` es la única semántica sostenida por evidencia.
La corrección es mínima (2 archivos con lógica nueva, 6 con un parámetro),
transversal (cierra los 6 escritores reales de una sola vez), retrocompatible
(`stage_id` opt-in), no introduce autoridad nueva, y no modifica C10/C11/C12
ni los históricos.
