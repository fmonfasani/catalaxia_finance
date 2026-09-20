# ACTA DE CERTIFICACIÓN — F12

MODO: READ-ONLY. Ningún código, configuración, DB ni Git fue modificado
para emitir esta acta. Certificación evaluada contra el contrato congelado
en `26_F12_ARCHITECTURE_DECISION.md`, sin sustituir criterios propios.

## 1. Alcance

F12 — Runtime objetivo del pipeline engine:

```
S00 → S01 → S02 → S03 → S04 → ratio_engine → C10 → C11 → C12
```

Incluye: runtime containerizado, `Dockerfile.engine`, `docker-compose.yml`
(servicio `engine`), `requirements-engine.txt`, entrypoint único
`scripts/engine/run_e2e_certified.py`, advisory lock, migraciones 035/036,
cron/runtime objetivo (`setup_vps.sh`), variables y secretos de runtime,
separación respecto del pipeline legacy, guards de producción (EXT-010),
integración C10/C11/C12, y los required-fix R1 (REPO_URL) y R2
(PROJECT_DIR).

No incluye: F11 (excepto verificación de no-regresión), F13 (excepto
verificación de no-regresión), F14 ni ninguna fase posterior, ejecución
real en VPS (evaluado en §9 si es obligatorio o no).

## 2. Contrato de aceptación utilizado

`docs/review/26_F12_ARCHITECTURE_DECISION.md` — sección "Acceptance
criteria" (20 ítems) y "Certification evidence" (5 ítems), congelado antes
de esta certificación. Documentos de contexto: `23_F12_DECISION.md`,
`23_F12_RUNTIME_CRON_VPS_AUDIT.md`, `23_F12_PRE_STATE.md`,
`25_F12_TARGET_RUNTIME.md`. Ningún criterio fue añadido ni removido para
esta acta.

## 3. Matriz requisito → evidencia → resultado

| Requisito (ADR) | Evidencia | Método | Resultado |
|---|---|---|---|
| Entrypoint único | `scripts/engine/run_e2e_certified.py`, único `ENTRYPOINT` de `Dockerfile.engine` | [VERIFICADO POR CÓDIGO] | PASS |
| S00→S04 | Report real `outputs/e2e/e2e_2026-09-09T045350.json` + `engine.runs` (`run_id=836dfbd5...`, `status=OK`) | [VERIFICADO POR EJECUCIÓN, DEV] | PASS |
| ratio_engine en la cadena | Mismo report, paso `RATIO ok:true` | [VERIFICADO POR EJECUCIÓN] | PASS |
| C10 (validación) | `c10_836dfbd5....json`: `verdict:"PASS"`, `NO_DANGLING: 0` | [VERIFICADO POR EJECUCIÓN] | PASS |
| C11 (certificación) | Acta C11: `veredicto="CERTIFICADA"`, `cert_hash=ef207c88...`, cruzado contra `engine.certifications` | [VERIFICADO POR EJECUCIÓN] | PASS |
| C12 (publicación) | Implementado; sin `ENGINE_PUBLISH_SOURCE` → `SKIPPED` declarado (`publish_skipped:true`, exit 0) — decisión de integración diferida por la propia ADR | [VERIFICADO POR CÓDIGO+EJECUCIÓN] | PASS |
| Fail-fast | Cada paso evalúa `exit_code`/veredicto antes de continuar; único camino de retorno vía `_finalize` | [VERIFICADO POR CÓDIGO] | PASS |
| Advisory lock (AC-4) | `pg_try_advisory_lock`/`pg_advisory_unlock`; ejercitado directamente: 2ª adquisición concurrente devuelve `False`, libera y reingresa correctamente | [VERIFICADO POR EJECUCIÓN, no solo test] | PASS |
| ENGINE_MODE | `--mode` + `dataclasses.replace` (Settings frozen) + propagación por env a subprocesos; reflejado en report real (`mode=FULL`) | [VERIFICADO POR CÓDIGO+EJECUCIÓN] | PASS |
| Rol `catalaxia_engine` / migración 035 | Query directa: `pg_roles.rolcanlogin = True` | [VERIFICADO POR EJECUCIÓN] | PASS |
| Migraciones 035/036 aplicadas | Query directa a `engine.schema_migrations`: ambas registradas; `staging` schema existe | [VERIFICADO POR EJECUCIÓN] | PASS |
| `Dockerfile.engine` (lectura) | Lockfile propio, sin `fastapi`/`yfinance`, `ENTRYPOINT` correcto | [VERIFICADO POR CÓDIGO] | PASS |
| `Dockerfile.engine` (build real) | No se construyó la imagen en ninguna auditoría | [NO DETERMINABLE] | No bloqueante (ver §9) |
| `docker-compose.yml`, servicio `engine` | `profiles:[run-e2e]`, `depends_on db healthy`, env `ENGINE_*`, volúmenes | [VERIFICADO POR CÓDIGO] | PASS |
| `setup_vps.sh`: smoke test | Paso 7 cambiado de `run_update.py` (legacy) a `docker compose --profile run-e2e run --rm engine` | [VERIFICADO POR CÓDIGO] | PASS |
| Cron FAST | `30 6 * * 1-5 ... --rm engine` | [VERIFICADO POR CÓDIGO] | PASS |
| Cron FULL | `0 7 1 1,4,7,10 * ... --rm engine --mode FULL` | [VERIFICADO POR CÓDIGO] | PASS |
| Secretos runtime engine | `ENGINE_DB_PASSWORD`/`ENGINE_ADMIN_DB_PASSWORD` interpolados desde `${POSTGRES_PASSWORD}`, sin hardcode en artefactos nuevos de F12 | [VERIFICADO POR CÓDIGO] | PASS |
| Separación legacy/certified (infra) | Comentarios "(legacy)" explícitos, `profiles` distintos; `api/main.py` no tocado | [VERIFICADO POR CÓDIGO] | PASS |
| Separación legacy/certified (dato, flag de origen) | No implementado — la propia ADR lo marca como decisión de integración diferida, no exigida en esta entrega | [VERIFICADO POR CÓDIGO] | No aplica a este cierre (fuera de alcance declarado) |
| Guard EXT-010 | Reutilizado sin modificar (`load_settings()`); `docker-compose.yml` declara `ENGINE_ALLOW_PROD=1` explícito para el destino productivo del compose | [VERIFICADO POR CÓDIGO] | PASS |
| Exit codes 0/1/2/3 | Documentados en docstring y `DEPLOY.md`; `exit 0` observado en la corrida real | [VERIFICADO POR CÓDIGO+EJECUCIÓN] | PASS |
| Generación de evidencia (report JSON) | 3 archivos en `outputs/e2e/` existen y coinciden con la DB | [VERIFICADO POR EJECUCIÓN] | PASS |
| G-019 (gate contra `migrate_sqlite_to_pg.py` sobre DB con datos) | `setup_vps.sh` agrega un guard de conteo de filas antes de invocar el script; mecanismo distinto al sugerido en la ADR (cambiar de script) pero protege la misma invariante (nunca corre el reemplazo destructivo contra una base con datos) | [VERIFICADO POR CÓDIGO] | PASS (invariante protegida; mecanismo distinto — IMPROVEMENT, no BLOCKER) |

## 4. Verificación R1 — REPO_URL

```
scripts/setup_vps.sh:13   REPO_URL="https://github.com/fmonfasani/catalaxia_finance.git"
git remote get-url origin  https://github.com/fmonfasani/catalaxia_finance.git
```

Coincidencia exacta, carácter por carácter. [VERIFICADO POR CÓDIGO, cruzado
contra `git remote`]. **R1 = PASS.**

## 5. Verificación R2 — PROJECT_DIR

```
scripts/setup_vps.sh:12   PROJECT_DIR="/infra/projects/0009-catalaxia"
docs/DEPLOY.md:65         cd /infra/projects/0009-catalaxia
docs/DEPLOY.md:279-280    /infra/projects/0009-catalaxia (cron ENGINE)
```

Grep de `/opt/catalaxia` sobre `docs/DEPLOY.md`: **0 coincidencias**
restantes. Las dos apariciones detectadas en auditorías previas (la
preexistente en "Despliegue en Producción" §1 y la introducida por
`f375090` en la sección ENGINE) quedaron unificadas al mismo valor que
`setup_vps.sh`. [VERIFICADO POR CÓDIGO]. **R2 = PASS.**

## 6. Regresión

Verificación read-only, sin re-ejecutar E2E (no exigido por el contrato
para este paso — la evidencia previa de ejecución real es válida):

| Componente | Método | Resultado |
|---|---|---|
| F13 (`s03_parse_ypf.py`) | `git diff --numstat`: 205/65, idéntico a la medición de la auditoría F13 | Sin regresión |
| F11 (`.env.example` API_KEY/CORS, contenido en `DEPLOY.md`) | Texto sin cambios respecto al estado preexistente (nunca commiteado, sin alteración) | Sin regresión |
| S00-S04 | Mismos deltas que en la auditoría F12 anterior; ningún hunk nuevo | Sin regresión |
| `ratio_engine.py` | `??` sin cambios | Sin regresión |
| C10/C11/C12 (`c10_evaluate.py`, `c11_certificar.py`, `publisher.py`) | `git diff --stat` vacío | Sin regresión |
| Migraciones 035/036 | `git diff --stat` vacío | Sin regresión |
| `Dockerfile.engine` / `docker-compose.yml` | `git diff --stat` vacío | Sin regresión |
| `run_e2e_certified.py` / `tests/test_run_e2e_certified.py` | `git diff --stat` vacío | Sin regresión |

**REGRESIÓN F12 = NO.**

## 7. Hallazgos

| Hallazgo | Clasificación | Requisito afectado | Bloquea |
|---|---|---|---|
| IP literal productiva retirada de una cabecera en `docs/DEPLOY.md` (fuera del alcance declarado "exclusivamente R1/R2") | OBSERVATION | Ninguno de F12 | No |
| Gate G-019 implementado como guard de conteo en vez del cambio de script sugerido por la ADR | IMPROVEMENT | Ninguno (invariante de seguridad protegida igual) | No |
| `ENGINE_DB_PASSWORD` y `ENGINE_ADMIN_DB_PASSWORD` comparten el mismo valor en `docker-compose.yml` | IMPROVEMENT | Ninguno (la ADR no exige secretos distintos) | No |
| `POSTGRES_PASSWORD` con default hardcodeado (`catalaxia_prod_2024`) en `setup_vps.sh`, preexistente desde `72debe8`, no tocado por F12 | OUT_OF_SCOPE | Pertenece a R2-secretos, fase anterior a F12 | No |
| Build real de `Dockerfile.engine` no ejecutado | NO DETERMINABLE (no obligatorio) | Ninguno de la lista de AC exige build verificado para esta certificación | No |
| Ejecución real en VPS | NO DETERMINABLE (no obligatorio) | Ver §9 | No |

Ningún hallazgo de esta lista fue corregido, ampliado a nueva fase, ni
convertido en requisito nuevo.

## 8. BLOCKERS

**Ninguno.** No se encontró evidencia de violación de un requisito
obligatorio del contrato, de una invariante previamente definida, ni de
una condición de seguridad previamente definida como obligatoria.

## 9. Evidencia E2E

Reutilizada de la implementación y de las dos auditorías previas (F12
independiente y F12 post-required-fix), sin re-ejecutar en esta
certificación por instrucción explícita:

- `run_id = 836dfbd566a440c3ba8eff392f6649f9`, `engine.runs.status = OK`.
- C10: `verdict = PASS`, `NO_DANGLING = 0` (5/5 invariantes PASS).
- C11: `veredicto = CERTIFICADA`, `cert_hash = ef207c88828c1e835a7d6284ef53c4289aad51858f79b894815d5da1c620b629`, verificado también contra `engine.certifications` directamente (no solo el JSON).
- C12: `SKIPPED` declarado explícitamente (decisión de integración de destino, diferida por la ADR — no una falla).
- Objetivo de la corrida: `catalaxia_engine@127.0.0.1:5433/catalaxia mode=FULL prod=False` — DEV, consistente con la regla de no tocar producción durante la verificación.

**Sobre la ejecución real en VPS**: no es un requisito obligatorio literal
de la sección "Acceptance criteria" de `26_F12_ARCHITECTURE_DECISION.md`.
Esa sección exige artefactos de código/infraestructura verificables
(entrypoint, lock, migraciones, cron, secretos, exit codes, generación de
evidencia) y una ejecución E2E reproducible — todo lo cual está
verificado por ejecución real en DEV. Una corrida en un VPS de internet
real es un hito de **operación productiva** (fuera del ciclo
DEFINIR→IMPLEMENTAR→VERIFICAR→CERTIFICAR de esta fase, que certifica la
*definición e implementación del runtime*, no su despliegue operativo
final). **No bloquea esta certificación.**

## 10. Resultado de certificación

Todos los requisitos obligatorios del contrato = PASS. R1 = PASS. R2 =
PASS. Sin regresión. Sin BLOCKERS. La evidencia disponible (ejecución real
en DEV, cruzada independientemente contra la base de datos, no solo contra
los artefactos JSON) es suficiente para certificar la definición e
implementación del runtime objetivo de F12.

**CERTIFICADA.**

## 11. Criterio de cierre

- Todos los requisitos obligatorios = PASS ✓
- No existen BLOCKERS pendientes ✓
- La evidencia requerida está disponible (código + ejecución real en DEV, cruzada contra DB) ✓
- VALIDACIÓN cumple (auditoría independiente previa + auditoría post-fix, ambas con verificación por ejecución donde fue posible) ✓
- CERTIFICACIÓN emitida contra el contrato congelado en `26_F12_ARCHITECTURE_DECISION.md`, sin criterios añadidos ni removidos ✓

## 12. Estado final

**ESTADO FINAL: F12 = CERTIFIED / CLOSED**

Observaciones, mejoras y elementos fuera de alcance (§7) quedan
registrados para referencia futura, sin abrir ninguna fase nueva. Ejecución
real en VPS queda como hito de operación productiva posterior, no
bloqueante, no incluido en este cierre.
