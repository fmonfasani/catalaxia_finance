# 23 — Pre-state: Checkpoint de preservación F5-F10

CAPA: CONTROL / INFRAESTRUCTURA. Objetivo: preservar en Git el trabajo ya
validado de F5-F10 antes de iniciar F11. No implementa nada, no repara nada.

## 1. Git — estado antes del checkpoint

- HEAD: `5b20266709c14ea77ed0655a487ae397ee02090c`
  (`chore(repo): reorganizar documentos y datos sueltos de la raiz`)
- Branch: `fix/ttm-ratios-cnv`
- `git status --short` (antes de cualquier `git add` de este checkpoint):
  159 `??` (untracked), 60 `M` (modificado no staged), 12 `D` (borrado del
  disco, fenómeno ya conocido — ver memoria), 0 staged.
- Últimos commits: `5b20266` (reorganización repo), `2993918`
  (`fix(F-050): cerrar corridas con run_scope en S00/S01/S02` — el commit que
  ya cerró F-050, anterior e independiente de F10), `3e85c10` (KO golden
  run), `57edebb`/`a4e296e` (manual operativo).

## 2. Archivos por fase (creados, no por mí en esta conversación salvo F10)

**F5** (`STEP_16=PASS`): `docs/review/16_PRE_F5_STATE.md`,
`16_F5_MULTI_SOURCE_E2E.md`, `16_IMPLEMENTATION_RESULT.md`,
`tests/test_f5_multisource.py`.

**F6** (`STEP_17=PASS`): `docs/review/17_PRE_F6_STATE.md`,
`17_F6_VALIDATION.md`, `17_IMPLEMENTATION_RESULT.md`,
`tests/test_f6_validation.py`, `scripts/engine/c10_evaluate.py` (nuevo,
autoría F6).

**F7** (`STEP_18=PASS`): `docs/review/18_PRE_F7_STATE.md`,
`18_F7_CERTIFICATION.md`, `18_IMPLEMENTATION_RESULT.md`,
`tests/test_f7_certification.py`. Dependencia requerida (autoría anterior a
F5, no generada por F5-F9, pero imprescindible para que el test importe):
`scripts/engine/c11_certificar.py`, `migrations/engine/034_c11_certifications.sql`
(crea `engine.certifications`, la tabla que escribe `c11_certificar.py`).

**F8** (`STEP_19=PASS`): `docs/review/19_PRE_F8_STATE.md`,
`20_F8_E2E_INTEGRACION.md`, `20_IMPLEMENTATION_RESULT.md`,
`tests/test_f8_e2e.py`. Dependencia requerida (mismo criterio que F7):
`scripts/engine/publisher.py`.

**F9** (`STEP_20=PASS_WITH_WARNINGS`): `docs/review/21_PRE_F9_STATE.md`,
`21_F9_STATE_RECONCILIATION.md`, `21_F9_GAP_MATRIX.md`,
`21_IMPLEMENTATION_RESULT.md`, `tests/test_f9_state_reconciliation.py`.

**F10** (`STEP_21_STATUS=PASS`, cerrado por mí en la fase anterior):
`docs/review/22_PRE_F10_STATE.md`, `22_F10_STATE_MACHINE.md`,
`22_F10_GAP_UPDATE.md`, `22_IMPLEMENTATION_RESULT.md`,
`tests/test_f10_state_machine.py` (nuevo, 36 tests). Dependencia requerida:
`scripts/engine/e2e_orchestrator.py` (leído como texto por el test `M2`, sin
import).

## 3. F10 — modificaciones productivas (lo único de código que se toca)

`engine/states.py` (`StageState.ABORTED` + `TRANSITIONS` extendido),
`engine/db.py` (`abort_stage_if_open()` + `run_scope(..., stage_id=None)`),
y **un solo parámetro** `stage_id=STAGE_ID` en cada uno de los 6 call-sites:
`scripts/engine/{s00_smoke,s01_identity,s02_fetch_ypf,s03_parse_ypf,
s04_normalize,c3_cnv_fetch}.py`.

## 4. Hallazgo crítico — estos 8 archivos NO están limpios en el working tree

Los 8 archivos de código de F10 tienen, en el working tree, cambios
adicionales de **otras fases/sesiones, no relacionadas con F10**:

- `engine/db.py`: 2 de sus 4 hunks son de **F-051** (Market migrations
  installer: `MARKET_MIGRATIONS_DIR`, `MARKET_REQUIERE`, `_ya_aplicada()`).
  No tocado por F10.
- `s00_smoke.py`, `s01_identity.py`, `s02_fetch_ypf.py`, `s03_parse_ypf.py`,
  `s04_normalize.py`: cada uno tiene además cambios de **R4/modo E2E**
  (`run_id=os.environ.get("ENGINE_E2E_RUN_ID")`, imports, lógica de
  checkpoint `ON CONFLICT`) — anteriores a F10, no generados por F10.
- `c3_cnv_fetch.py`: de ~250 líneas de diff en el archivo, solo 1 línea es
  de F10; el resto (incluida una firma nueva de `load_identity`) es de otra
  sesión/fase, anterior a F10.
- `engine/states.py`: único de los 8 **100% limpio** — todo el diff es F10.

**Consecuencia**: el checkpoint no puede hacer `git add <archivo>` sobre
estos 7 archivos sin arrastrar cambios ajenos a F5-F10 (violaría "NO incluir
cambios preexistentes no relacionados"). Se resuelve con parches parciales
por hunk (`git apply --cached` con patches construidos a mano, uno por
archivo) — ver `23_GIT_CHECKPOINT_RESULT.md` §2 para el detalle verificado
hunk por hunk.

## 5. Archivos nuevos, sin ambigüedad de propiedad (Categoría A)

Las 20 entradas de `docs/review/16_*` a `22_*` listadas en §2 (excluyendo
`22_F10_SECURITY_*`, que son F11), las 6 de `tests/test_f{5,6,7,8,9,10}_*.py`,
y las 4 dependencias requeridas (`c10_evaluate.py`, `c11_certificar.py`,
`publisher.py`, `e2e_orchestrator.py`, `034_c11_certifications.sql`) — 31
archivos en total, ninguno con contenido ajeno a F5-F10.

## 6. Excluido explícitamente — F11 (trabajo en paralelo, fase distinta)

`docs/review/22_F10_SECURITY_TLS_ENDPOINT_AUDIT.md`,
`22_F10_SECURITY_IMPLEMENTATION_RESULT.md` (aparecieron ~20 min después de
que F10 cerrara; `STEP_22 = SECURITY_BLOCKERS`), `tests/test_api_security.py`,
y las modificaciones `M` en `api/main.py`, `.env.example`, `docs/DEPLOY.md`,
`scripts/tickets/cnv/jobs/job5*`, `job6_extract_div.py`,
`scripts/pipeline/fetch_dgce.py`, `scripts/dolares/*`,
`scripts/tickets/screener/{cedear_ratios,jpm_adr,run_update}.py`. Cero
solapamiento de archivos con F5-F10.

## 7. Excluido — preexistente / no relacionado (Categoría C)

`engine/identity.py`, `scripts/market/market_db.py`,
`scripts/market/tests/conftest.py`, `outputs/docs/fase_s02/S02_VALIDATION.json`,
`screener_final.html`, `scripts/deploy/sincronizar_a_produccion.py`,
`scripts/engine/f049_bench.py`, `docs/EXTRACTION_KNOWLEDGE_BASE.md`, todo el
swath `scripts/pipeline/*` / `scripts/tickets/cnv/scripts/*` /
`scripts/tickets/screener/*` (M), `scripts/setup_vps.sh`, la secuencia
`docs/review/01_*`–`15_*` (era F0-F4), y el resto de untracked de
exploración (`scripts/engine/adversario_*`, `cnv_*`, etc.) — ninguno
mencionado en ningún documento F5-F10, ninguno importado por sus tests.

## 8. Los 12 `D` de `docs/pdfs/*`

Instancia separada del fenómeno "archivos que desaparecen del disco sin
acción de git" (ya documentado en memoria). **No tocados, no restaurados,
fuera de alcance de este checkpoint** (no pertenecen a F5-F10).

## 9. Archivos sensibles

Ninguno detectado en el conjunto F5-F10: sin `.env`, sin credenciales, sin
dumps de base de datos, sin `.sqlite`/`.db`. Verificación formal en
`23_GIT_CHECKPOINT_RESULT.md` §3 (Paso 2 — Seguridad).
