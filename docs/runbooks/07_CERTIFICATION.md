# 07 · CERTIFICACIÓN

Cuándo una corrida se puede declarar buena, y con qué evidencia.

---

## 1 · La máquina de estados real

`engine/states.py`. **Éstos son todos los estados que existen** (incluye
`ABORTED`, agregado por F10 — gap #11 de `21_F9_GAP_MATRIX.md`, cerrado en
`docs/review/22_F10_STATE_MACHINE.md`):

```
PLANNED → READY → RUNNING → VALIDATING → PASSED → CHECKPOINTED → CERTIFIED
   ↓         ↓        ↓          ↓
   └─────────┴────────┴──── ABORTED (terminal; también desde FIXING/RERUNNING)
                                 ↓
                              FAILED → FIXING → RERUNNING → VALIDATING
```

Las transiciones están **validadas en código** (`assert_transition`,
`TRANSITIONS` en `engine/states.py`): un salto no permitido levanta
`ValueError`. No se puede ir de `RUNNING` a `PASSED` salteando
`VALIDATING`, ni de `FAILED` directo a `PASSED`.

**`ABORTED` (F10) — qué representa y qué no.** Antes de F10, si el cuerpo
de una etapa moría entre "escribió `RUNNING`" y "escribió su tramo
terminal", la fila de `engine.stage_runs` quedaba en `RUNNING` para
siempre — aunque `engine.runs.status` ya dijera `ABORTED` (ese es un
estado de **corrida**, existe desde antes de F10). F10 agregó `ABORTED`
también a nivel de **etapa**: alcanzable desde todo estado sin evidencia
propia todavía (`PLANNED, READY, RUNNING, VALIDATING, FIXING, RERUNNING`),
**nunca** desde un estado que ya tiene evidencia durable
(`FAILED, PASSED, CHECKPOINTED, CERTIFIED` — un aborto posterior no puede
borrar retroactivamente esa evidencia). Lo escribe
`engine.db::abort_stage_if_open`, llamado desde `run_scope(...,
stage_id=...)` en el mismo `except` que cierra la corrida. Es terminal:
nada sale de `ABORTED`. Los 6 escritores reales de `stage_runs`
(S00-S04 + C3) lo implementan; C10/C11/C12 no escriben `stage_runs`, así
que no aplica.

Gates: **`PASS`**, **`WARNING`**, **`BLOCK`**. Nada más.

### Los estados que el sprint pedía y no existen

| pedido | estado real |
|---|---|
| `NOT_STARTED` | existe como **`PLANNED`** |
| `RUNNING` | **`RUNNING`** |
| `PASS` | **`PASSED`** (etapa) / `GateStatus.PASS` (gate) |
| `PASS_WITH_WARNINGS` | existe como **`GateStatus.WARNING`**, a nivel gate, no de etapa |
| `FAILED` | **`FAILED`** |
| `BLOCKED` | existe como **`GateStatus.BLOCK`**, a nivel gate |
| `ABORTED` | **existe desde F10** (`StageState.ABORTED`, ver arriba) — antes de F10 no existía a nivel de etapa, solo de corrida |
| `QUARANTINED` | **NO EXISTE** · `SG-08` |
| `RECOVERED` | **NO EXISTE**. `FIXING`/`RERUNNING` se le acercan pero no lo son |
| `SKIPPED` | **NO EXISTE como estado de etapa.** Existe como `result` de un *check* en `--dry-run` de S04 |
| `NOT_CALCULABLE` | existe como **`derived.ratio.status`**, a nivel dato, no de etapa |

`CERTIFIED` es el estado terminal de **etapa** y sólo se alcanza desde
`CHECKPOINTED`. **No confundir con la certificación de C11** (§7 abajo):
`CERTIFIED` es un estado de `StageState` que hoy ningún escritor de
`stage_runs` produce (los 6 escritores llegan hasta `CHECKPOINTED`); la
certificación real de una *corrida* vive en `engine.certifications`,
emitida por `c11_certificar.py`, y es un concepto separado.

## 2 · Criterios por etapa

Una etapa está certificada cuando **las cuatro** se cumplen:

1. `gate_status = 'PASS'` en `engine.stage_runs`.
2. `report` presente y válido: pasa `StageReport.validate()`.
3. `expected == parsed + rejected` (lo impone `validate()`).
4. **`checks` no vacío.** *"terminó sin excepción nunca es PASS"* es una norma
   del proyecto codificada en `engine/report.py`.

```bash
docker exec catalaxia-engine-dev psql -U catalaxia -d catalaxia -c "
SELECT stage_id, gate_status,
       report->'coverage'->>'expected' AS expected,
       report->'coverage'->>'parsed'   AS parsed,
       report->'coverage'->>'rejected' AS rejected,
       jsonb_array_length(report->'gate'->'checks') AS n_checks
  FROM engine.stage_runs
 WHERE run_id='<RUN_ID>' AND report IS NOT NULL"
```

## 3 · Criterios de corrida completa

| # | criterio | cómo se verifica |
|---|---|---|
| 1 | Todas las etapas con gate `PASS` | consulta de §2 |
| 2 | `engine.runs.status = 'OK'` | ninguna corrida en `RUNNING` ni `ABORTED` |
| 3 | Idempotencia demostrada | segunda corrida: mismo `hash_out`, 0 inserts |
| 4 | Provenance completa | `06_PROVENANCE.md` §2 sobre una muestra |
| 5 | Producción intacta | `01_COMMON_OPERATIONS.md` §1.4 |
| 6 | `screener.db` intacto | §1.5, salvo tramo B de CNV |

## 3.1 · La certificación formal de una corrida — C10 → C11 → C12 (F12)

Los criterios de §2-§3 son manuales: alguien corre las consultas y decide.
Desde F12 (`docs/review/26_F12_ARCHITECTURE_DECISION.md`) existe una
cadena que los automatiza para el pipeline engine, con su propia
evidencia en base:

1. **C10** (`scripts/engine/c10_evaluate.py`) — evalúa invariantes sobre
   la corrida (solo lectura): `SEC_GATES`, `IDENTITY`, `PROVENANCE`,
   `NO_DANGLING`, `NO_ORPHAN_ENTITY` (scope `sec`). Veredicto
   `PASS`/`WARN`/`BLOCK`. No escribe ninguna tabla.
2. **C11** (`scripts/engine/c11_certificar.py`) — lee la evidencia de C10
   más `engine.stage_runs`/`checkpoints`, y emite **la única fila
   autoritativa de certificación** en `engine.certifications`:
   `certification_id`, `run_id`, `veredicto`
   (`CERTIFICADA`/`CERTIFICADA_CON_OBSERVACIONES`/`NEGADA`), `cert_hash`
   (sha256 determinista, reproducible, sin timestamps). Un `cert_id` por
   `run_id`; re-ejecutar es idempotente, nunca reescribe el acta.
3. **C12** (`scripts/engine/publisher.py`) — exige `C10 PASS` + `C11
   CERTIFICADA` antes de publicar a `staging.<target>` con swap atómico.

```bash
docker exec catalaxia-engine-dev psql -U catalaxia -d catalaxia -c \
  "SELECT certification_id, run_id, veredicto, cert_hash, stages_total, \
          stages_pass, stages_block FROM engine.certifications \
    WHERE run_id='<RUN_ID>'"
```

Esta cadena **no reemplaza** los criterios de §2-§3 (siguen siendo válidos
y son lo que C10 en el fondo automatiza); los formaliza en una fila de
base consultable, en vez de una corrida manual de consultas. Guía
operativa completa: `02_SEC_EDGAR_E2E_RUNBOOK.md` §"C10 → C11 → C12" y
`docs/runbooks/GUIA_OPERATIVA_PIPELINE_ENGINE.md`.

## 4 · Evidencia mínima a archivar

1. `run_id` de cada etapa.
2. Salida de consola completa.
3. El `report` JSON de cada etapa.
4. `hash_in` / `hash_out` de S03 y S04.
5. El resultado de las dos verificaciones de no contaminación.
6. La fecha y el `git_commit` (queda en `engine.runs`).

Sin el `run_id` no se reconstruye nada.

## 5 · Ejemplo de certificación completa

El único E2E de CNV certificado de punta a punta es
**METR FY2024**, en `outputs/docs/fase_cnv/METR_FY2024_E2E_REPORT.md`:

- 7 documentos con SHA256 recomputado
- 203 hechos, `audit_status != OK` = 0
- 70 ratios de 77, los 7 restantes `NO_INPUT` con causa
- auditoría independiente: **0 fallas**
- 10 mutaciones adversariales, todas detectadas
- segunda corrida: 0 inserts, digests idénticos
- producción: 0 cambios

Digests reproducibles en `METR_FY2024_SNAPSHOT.json`.

**Salvedad:** se produjo con el adaptador del worktree `catalaxia-cnvmig`, no
con el repo principal. Ver `03_CNV_E2E_RUNBOOK.md`, tramo C.

## 6 · Lo que NO habilita a certificar

- Que el script termine con exit `0` **sin checks**: `validate()` lo rechaza, y
  con razón.
- Que los números "se vean bien". Sin `expected == parsed + rejected` hay filas
  perdidas o contadas dos veces.
- Que una segunda corrida "no rompa". Idempotencia es **mismo digest**, no
  ausencia de excepción.
- Que la etapa anterior haya pasado **en otra corrida** sin verificar el
  encadenamiento: `C-S04-001` existe justamente porque S04 llegó a correr sobre
  un S03 que no reproducía su `hash_out`.
