# 23 — Resultado: Checkpoint de preservación F5-F10

## 1. Commit

`b1d61f2` — `checkpoint: preserve validated F5-F10 pipeline state`
(padre: `5b20266`, branch `fix/ttm-ratios-cnv`). 40 archivos, +4236/-18.

## 2. Paso 5 — Diff review, hunk por hunk (el punto crítico)

7 de los 8 archivos productivos de F10 no estaban limpios en el working
tree: traían además cambios de F-051 (Market migrations installer, en
`engine/db.py`) y de modo E2E/R4 (`run_id` compartido, checkpoints
`ON CONFLICT`, en los 6 scripts S00-S04/C3), ninguno generado por F10.
Se resolvió con parches parciales, uno por archivo, construidos a mano y
verificados con `git apply --cached --check` antes de aplicarlos:

| archivo | hunks totales en worktree | hunks de F10 (commiteados) | excluido (queda unstaged) |
|---|---:|---|---|
| `engine/states.py` | 2 | 2 (100%) | — |
| `engine/db.py` | 4 | 2 (import + `abort_stage_if_open`/`run_scope`) | 2 hunks de F-051 (`MARKET_MIGRATIONS_DIR`, `_ya_aplicada`) |
| `s00_smoke.py` | 3 | 1 línea (`stage_id=STAGE_ID`) | import `os`/`uuid`, `run_id=...`, checkpoint `ON CONFLICT` |
| `s01_identity.py` | — | 1 línea | `run_id=...` (E2E) |
| `s02_fetch_ypf.py` | — | 1 línea | `run_id=...` (E2E) |
| `s03_parse_ypf.py` | 12 | 1 línea | `run_id=...` (E2E) + resto del archivo (no tocado) |
| `s04_normalize.py` | 8 | 1 línea | `run_id=...` (E2E) + resto del archivo (no tocado) |
| `c3_cnv_fetch.py` | ~muchos | 1 línea | firma nueva de `load_identity` + resto (no relacionado, no tocado) |

Verificación final: `git diff --cached` de los 8 archivos productivos,
línea por línea — contiene exactamente `StageState.ABORTED`,
`abort_stage_if_open()`, la firma extendida de `run_scope(..., stage_id=)`
y los 6 `stage_id=STAGE_ID` en las llamadas. Nada más. Cumple literalmente
la instrucción del Paso 5.

## 3. Paso 2 — Seguridad

`git diff --cached | grep -iE "password|secret|api[_-]?key|BEGIN (RSA|PRIVATE|OPENSSH)|token=..."`
sobre el conjunto completo de 40 archivos: **0 coincidencias**. Ningún
`.env`, credencial, dump de base de datos, `.sqlite`/`.db` entre los
archivos commiteados. `.gitignore` no se tocó.

## 4. Paso 3 — Consistencia (archivos requeridos por fase)

Todos presentes y commiteados:

- F6: `c10_evaluate.py` ✅, `tests/test_f6_validation.py` ✅
- F7: `c11_certificar.py` ✅, `tests/test_f7_certification.py` ✅ — más
  `migrations/engine/034_c11_certifications.sql` (dependencia dura no
  listada explícitamente en la consigna, pero sin ella `c11_certificar.py`
  no tiene tabla `engine.certifications` donde escribir; se incluye por
  necesidad de reproducibilidad, no por generosidad de alcance)
- F8: `tests/test_f8_e2e.py` ✅, `20_F8_*` ✅ — más `publisher.py`
  (import directo del test)
- F9: `21_F9_*` ✅ (los 4 documentos)
- F10: `engine/states.py` ✅, `engine/db.py` ✅ (parcial, ver §2), 6
  call-sites ✅, `tests/test_f10_state_machine.py` ✅, `22_F10_*` ✅ (los 4
  documentos) — más `e2e_orchestrator.py` (leído por el test `M2`)

## 5. Paso 4 — Tests

`pytest tests/test_f{5,6,7,8,9,10}_*.py -q`, contra DEV real
(`catalaxia_engine@127.0.0.1:5433`), sin tocar producción:

**105 passed, 1 failed, 1 skipped** (107 tests totales).

El único FAIL es `test_f5_multisource.py::test_J_idempotencia_market`:
`m1_symbol_mapping.py` corta con `MARKET_ALLOW_PROD_WRITE` no seteado —
**PREEXISTENTE**, no relacionado con la máquina de estados ni con ningún
archivo de este checkpoint (invoca scripts de `scripts/market/`, ninguno
tocado por F5-F10; es la misma familia de gaps #7/#10 ya documentados en
`21_F9_GAP_MATRIX.md`: guard de escritura de Market). No se intentó
reparar (regla explícita del checkpoint).

F6, F7, F8, F9 y F10: **0 fallos**. El skip es el de F10 (`ABORTED→ABORTED`
no aplica a sí mismo, intencional, ya documentado en `22_IMPLEMENTATION_RESULT.md`).

Regresión más amplia (11 archivos / 211 tests: lifecycle, orquestador, C11,
F5-F10, F8 E2E): **no se re-corrió completa** — el working tree no se
modificó en ningún momento de este checkpoint (todo el staging usó
`git apply --cached` / `git add`, nunca se escribió sobre archivos del
árbol de trabajo), así que los resultados que dejó F10 en su propia
auditoría (175 passed, 1 skipped, 4 failed — los 4 PREEXISTENTES,
verificados entonces con `git diff` acotado) siguen siendo válidos sin
re-ejecución. Verificación post-commit puntual: `test_f10_state_machine.py`
solo, contra `HEAD` ya con el commit aplicado — **35 passed, 1 skipped**,
idéntico a antes del commit.

## 6. Paso 7 — Post-checkpoint

`git status --short` tras el commit: 159 `??` (untracked, sin cambios —
ninguno pertenece a F5-F10), 12 `D` (los `docs/pdfs/*` ya conocidos, no
tocados), 66 `M` (modificados no-staged — incluye los 7 archivos con
residuo intencionalmente dejado fuera: F-051 en `engine/db.py`, E2E/R4 en
los 6 scripts, más el resto de la superficie no relacionada con F5-F10 que
ya estaba modificada antes de este checkpoint). Ningún archivo quedó a
medio commitear sin explicación.

### Archivos incluidos (40)

21 documentos (`docs/review/16_*` a `23_PRE_GIT_CHECKPOINT_STATE.md`), 6
tests (`test_f5` a `test_f10`), 5 scripts/migración de dependencia
(`c10_evaluate.py`, `c11_certificar.py`, `publisher.py`,
`e2e_orchestrator.py`, `034_c11_certifications.sql`), y 8 archivos de
código productivo de F10 con contenido parcial (ver §2).

### Archivos excluidos, con motivo

- **F11** (`22_F10_SECURITY_*`, `test_api_security.py`, `api/main.py`,
  `.env.example`, `docs/DEPLOY.md`, jobs CNV/dólares/screener modificados):
  fase distinta, explícitamente fuera de alcance ("NO iniciar F11").
- **F-051 y R4/E2E** (2 hunks de `engine/db.py`, 1-2 hunks de cada uno de
  los 6 scripts S00-S04/C3): preexistentes al alcance F5-F10, no generados
  por ninguna de las 6 fases, dejados unstaged para un checkpoint propio.
- **Categoría C** (`engine/identity.py`, `scripts/market/market_db.py`,
  todo `scripts/pipeline/*`/`scripts/tickets/*`, etc.): no mencionados en
  ningún documento F5-F10, no importados por ningún test F5-F10.
- **12 `D` de `docs/pdfs/*`**: fenómeno de archivos desaparecidos del disco,
  ajeno a F5-F10, no tocado.
- **159 `??` restantes**: exploración/one-offs de fases anteriores (F0-F4) o
  posteriores (F11), sin relación con F5-F10.

## 7. Riesgos restantes (no resueltos por este checkpoint, a propósito)

- Los 7 archivos productivos de F10 siguen con residuo sin commitear en el
  working tree (F-051 + R4/E2E). Necesitan su propio checkpoint separado
  cuando esas fases se declaren cerradas — no es tarea de este checkpoint.
  Mientras tanto, un `git stash`/`git reset --hard` accidental sobre el
  working tree perdería ese residuo (no está en ningún commit todavía).
- `test_J_idempotencia_market` (F5) sigue en rojo — gap conocido, no
  bloquea F5-F10 en sí (F5 se documentó `PASS` en su propio cierre; este
  fallo puntual no invalida esa fase, es un guard de entorno).
- Los 16 residuos históricos `stage_runs=RUNNING` de F9 siguen intactos,
  como decisión ya documentada (no se tocan).

---

**CHECKPOINT_STATUS = PASS**
**NEXT_PHASE = F11**

DETENIDO. No se inició ningún trabajo de F11 en este checkpoint.
