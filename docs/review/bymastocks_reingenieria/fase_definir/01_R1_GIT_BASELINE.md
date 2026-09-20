# CONTRATO R1 — GIT BASELINE
Estado: **DEFINIENDO (HOLD)** · Origen: ficha P0-R1 (07_REENGINEERING_PLAN) · Evidencia verificada 2026-09-06.
Decisión OWNER: NO ejecutar todavía el baseline. La clasificación de las 1001 entradas requiere revisión semántica
del repositorio. R1 permanece en DEFINIR hasta completar esa clasificación.

## 1. OBJETIVO

Fijar el baseline de tracking del repositorio (el audit medía ~41 % del código fuera de git).
Que `git status` quede limpio y todo lo que es **fuente de verdad** quede versionado; todo lo que es
**artefacto/dato secreto** quede ignorado. El repo es PÚBLICO (política en `.gitignore`), por lo que el
baseline no puede introducir datos personales ni credenciales en la historia.

## 2. INVARIANTES (lo que NO puede pasar)

- INV1 — No entra a git: `data/`, `*.db*`, `.env`, `~$*` (locks de Office), `*.rar`, binarios generados por el pipeline, `outputs/`, `scratchpad/`.
- INV2 — No se versiona NINGÚN valor de credencial/infraestructura (ver R2); si un archivo rastreado antes del baseline lo contiene, se limpia/rota ANTES del primer commit.
- INV3 — El baseline se hace en UNA decisión documentada (criterios de clasificación aprobados) y UN commit por categoría, no un `git add .`.
- INV4 — `git status --porcelain` post-baseline = 0 salvo los artefactos vivos de ejecución que estén ignorados.
- INV5 — Ningún archivo de `docs/`/`scripts`/`engine/`/`api/`/`migrations/`/`tests/` legítimamente de producción queda untracked.

## 3. ALCANCE EXACTO (evidencia)

- Estado actual: **1001 entradas** en `git status --porcelain` = 954 untracked + 47 modified.
- Clasificación observada de untracked (muestras) — **PENDIENTE de revisión semántica owner**:
  | Grupo | Cantidad | Clasificación provisional |
  |---|---|---|
  | `outputs/` | 291 | IGNORAR (artefactos) |
  | `docs/` | 233 + 162 (chars especiales) | REVISAR: docs legítimos a trackear; descargas html/cache no |
  | `scratchpad/` | 116 | IGNORAR (borrador) |
  | `scripts/` | 72 | TRACKEAR los de producción; verificar prefijos `_tmp/_diag` ya ignorados |
  | `data/` | 16 + 3 | IGNORAR (ya política `data/raw/`, `*.db*`) |
  | `tests/` | 7 | TRACKEAR |
  | `migrations/` | 2 | TRACKEAR |
  | Root basura | `tmp_byma3.py`, `tmp_byma_audit.py`, `audit_cnv_coverage.py`, `scripts.rar`, `~$Seguimiento*.xlsx`, `dashboard*.html`, `screener*.html`, `Dashboard_GRIM*.xlsx`, `test_local.py` | REVISAR (archivar o ignorar por tipo) |
  | Snapshots previos | `catalaxia_{untracked,before,pre_restructure}.*`, patches | REVISAR (legado docs/review) |

- Ya existen inventarios previos reutilizables: `catalaxia_untracked_before_restructure.txt`, `catalaxia_pre_restructure.patch`.
- `.gitignore` cubre ya: `.env*`, `data/raw/`, `data/*.db*`, `scripts/**/_tmp/_diag/_probe`, CNV html/logs,
  `financials_sec`, `__pycache__`. Faltan por incorporar (en la fase de implementación del baseline): `outputs/`,
  `scratchpad/`, `*.rar`, `~$*`, dashboards generados en root.

## 4. DISEÑO (para fase EXEC, bloqueada hasta clasificación)

1. Completar clasificación semántica de las 1001 entradas → tabla `{archivo o patrón → trackear|ignorar|archivar}` (owner).
2. Extender `.gitignore` con las categorías que se ignoren.
3. Gitignore anticipado, luego `git add -A && git status` para revisar la lista ANTES del commit (evitar fugas).
4. Commit baseline en lotes por categoría (`.gitignore` primero, luego fuente lícita).
5. Verificación anti-secreta (grep + revisión manual de diffs del commit antes de push).

## 5. VERIFICACIÓN (válida cuando R1 pase a IMPLEMENTAR)

- `git status --porcelain` → solo output esperado (ignorado).
- `git log --stat -1` del commit baseline incluye fuente de verdad, sin basura.
- `git grep -nE "(passwor|token|secret|api_?key)"` en el commit → 0.
- No aparece ningún archivo de `data/` ni `.env` en el diff del baseline.

## 6. GATES DE PASO (bloqueados = HOLD)

- [ ] (HOLD) Clasificación semántica de las 1001 entradas aprobada por owner.
- [ ] (HOLD) `.gitignore` cubre categorías de basura.
- [ ] (HOLD) Baseline commiteado con diffs revisados, sin datos ni secretos.
- [ ] (HOLD) `git status --porcelain` limpio en checkout fresco.

## 7. CHECKLIST 10 PASOS (regla de seguridad)

| Paso | Estado |
|---|---|
| 1 dependencias reales | Repo entero; no cambia ejecución de código |
| 2 ownership | Tracking; propietario: owner + git |
| 3 duplicación semántica | N/A (no fusiona lógica) |
| 4 comportamiento | Sin cambio de comportamiento en runtime |
| 5 consumidores | Ninguno |
| 6 impacto | Historia pública: riesgo fuga datos/secretos → mitigado por INV2 + verificación |
| 7 alternativa | No hacer baseline = 954 untracked siguen fuera; riesgo de pérdida en sync |
| 8 plan migración | Sección 4 (lotes) |
| 9 verificación | Sección 5 |
| 10 certificación | Review del owner sobre el diff del baseline |

## 8. RIESGOS Y LÍMITES

- Riesgo mayor: fuga de CUIT/nombres de personas físicas (CNV) o credenciales a un repo público.
- Bug: `git add -A` con ignorados mal configurados arrastra basura.
- Límite: este contrato no decide contenido de negocio de `docs/` (162 con chars especiales); queda en revisión owner.

## 9. DECISIÓN OWNER

| Decisión | Resultado |
|---|---|
| Ejecutar baseline ahora | **NO — HOLD** |
| Clasificación semántica de 1001 entradas | PENDIENTE (requiere revisión del repositorio) |
| DELETE / MERGE / REPLACE / ARCHIVE de componentes | **Todos bloqueados** |
| Fase | **DEFINIENDO** |