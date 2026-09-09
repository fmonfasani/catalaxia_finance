# 25 — F12: Runtime objetivo (estado HOY vs OBJETIVO)

MODO: READ-ONLY. CAPA: EJECUCIÓN + INFRAESTRUCTURA. PLANOS: EJECUCIÓN +
INFRAESTRUCTURA. CICLO: DEFINIR. Ningún código, configuración, DB ni Git
tocado para producir este documento.

## 1. Objetivo

Cerrar la definición arquitectónica de F12: determinar de forma inequívoca
cuál es (y cuál debería ser) el runtime productivo de Catalaxia/BYMAStocks,
separando siempre lo demostrado en el código de hoy de lo que se decide como
objetivo. No implementa nada; deja los criterios para que otro agente
implemente sin volver a decidir arquitectura.

## 2. Estado HOY — el hallazgo central

**Existen dos pipelines completamente desconectados entre sí, y el que está
en producción HOY no es el que este proyecto certificó (F5-F13).**

### 2.1 Pipeline "engine" (SEC/EDGAR) — el que F5-F13 validaron

`S00_bootstrap → S01_identity → S02_fetch → S03_parse → S04_normalize →
ratio_engine → C10 (validación) → C11 (certificación) → publisher.py (C12)`.

- Cada etapa tiene `STAGE_ID` registrado en `engine.stage_runs`
  [VERIFICADO POR CÓDIGO: `docs/runbooks/00_START_HERE.md` §3 + `engine/states.py`].
- Corre sobre PostgreSQL, schemas `engine.*`/`parsed.*`/`derived.*`
  [VERIFICADO POR EJECUCIÓN: consultas directas en la auditoría F13 anterior,
  `catalaxia_engine@127.0.0.1:5433`].
- `scripts/engine/e2e_orchestrator.py` encadena S00→S04 como subprocesos bajo
  un mismo `run_id` [VERIFICADO POR CÓDIGO: líneas 41-45, 127-153]. **No
  invoca `c10_evaluate.py`, `c11_certificar.py` ni `publisher.py`** — no hay
  grep de esos nombres dentro del archivo. La cadena
  `VALIDACIÓN→CERTIFICACIÓN→PUBLICACIÓN` para este pipeline es HOY tres
  comandos manuales separados, no un entrypoint único
  [VERIFICADO POR CÓDIGO].
- **Ningún mecanismo de scheduler/cron/VPS lo conoce.** Grep de
  `s00_smoke|s01_identity|s02_fetch_ypf|s03_parse_ypf|s04_normalize` sobre
  `scripts/setup_vps.sh`, `docker-compose.yml`, `Dockerfile`,
  `setup_scheduler.ps1`: **0 coincidencias** [VERIFICADO POR CÓDIGO]. Hoy
  este pipeline solo se ejecuta manualmente (o desde pytest) por un
  desarrollador en DEV.
- CNV bajo este camino (`c3_cnv_fetch.py`, `STAGE_ID=C3_CNV_fetch`) **solo
  descarga páginas de visor y de empresa** (`artifact_kind` = `VISOR` /
  `EMPRESA_PAGE`); no descarga estados financieros
  [VERIFICADO POR CÓDIGO, confirmado también en `docs/runbooks/00_START_HERE.md` §3].

### 2.2 Pipeline "screener/legacy" — el que está en producción HOY

`run_all.py` (EXTRACT→TRANSFORM→ASSEMBLE→EXPORT, s0→s8) y
`run_update.py --daily/--monthly/--quarterly/--annual/--rebuild`, en
`scripts/tickets/screener/`.

- Opera sobre SQLite `data/screener.db` (~750 MB, no versionado)
  [VERIFICADO POR CÓDIGO: `docs/screener/OPERACION.md` §1].
- CNV en este camino: `job5_v2_extract_eeff.py → data/screener.db` — **es el
  que produjo todos los datos CNV que existen hoy**, sin ledger, sin SHA256
  almacenado [VERIFICADO POR CÓDIGO, confirmado en `00_START_HERE.md` §3].
- Grep de `c10_evaluate|c11_certificar|publisher\.py|engine\.runs|
  engine\.stage_runs|StageState|run_scope` sobre `run_update.py` y
  `run_all.py`: **0 coincidencias** [VERIFICADO POR CÓDIGO]. Este pipeline
  **nunca pasa por C10, C11 ni C12** — no tiene noción de validación ni
  certificación tal como las define este harness.
- Scheduler HOY: **Windows Task Scheduler**, local/VM, vía
  `scripts/tickets/screener/setup_scheduler.ps1` (4 tareas: diario 18:30,
  trimestral día 1 03:00, mensual día 5 04:00, anual 2-abr 05:00)
  [VERIFICADO POR CÓDIGO: el script existe y define exactamente esas 4
  tareas con `schtasks /Create`]. **No hay evidencia de que esté
  efectivamente registrado/activo en ninguna máquina real** — el script
  existe y es correcto, pero su ejecución en un Task Scheduler real es
  [NO DETERMINABLE] desde el repo.
- Puente a producción: `data/screener.db` → PostgreSQL, tabla `screener` +
  afines, vía `scripts/deploy/sincronizar_a_produccion.py` (manual,
  `--dry-run` disponible) [VERIFICADO POR CÓDIGO, docstring del script].
- **`api/main.py` sirve exclusivamente desde este camino**: sus queries
  apuntan a `screener`, `screener_hist`, `silver_norm`, `validaciones`,
  `certificacion_nueva`, `mep_actual` [VERIFICADO POR CÓDIGO, líneas
  160-430] — ninguna de estas tablas pertenece a `engine.*`/`parsed.*`/
  `derived.*`. **La API pública no sirve ni un solo dato que haya pasado
  por C10/C11/C12.**

### 2.3 Consecuencia arquitectónica del hallazgo

Bajo la regla del harness *"PUBLICACIÓN requiere VALIDACIÓN + CERTIFICACIÓN"*,
el estado HOY de producción **no cumple el harness**: lo que se publica
(API pública, `screener_final.html`, `dashboard`) proviene íntegramente del
pipeline legacy, que nunca pasa por C10 ni C11. El pipeline que sí lo hace
(engine, S00-S04+C10-C12, el que F5-F13 endurecieron con enorme esfuerzo)
no tiene ningún camino de despliegue, scheduler ni publicación hoy.
[VERIFICADO POR CÓDIGO — conclusión derivada de 2.1 y 2.2, no una opinión.]

### 2.4 Hallazgo adicional de seguridad de datos (D6/riesgo, no en la auditoría F12 previa)

`scripts/deploy/sincronizar_a_produccion.py` documenta en su propio
docstring: `migrate_sqlite_to_pg.py` (el script que **`setup_vps.sh` paso 6
efectivamente invoca**) hace TRUNCATE+INSERT+swap sobre `screener` y
**vacía 12 columnas que la API sirve hoy** (`ccl`, `precio_ars`,
`precio_usd`, `precio_fuente`, `precio_dif_iamc`, `cusip`, `dr_level`,
`cedear_ratio`, `cedear_x`, `div_adr_12m`, `div_yield_adr`,
`last_div_date`) — y la guarda de conteo de filas **no lo detecta** (entran
572, salen 572) [VERIFICADO POR CÓDIGO: docstring íntegro del script,
líneas 1-35]. `setup_vps.sh` usa el script equivocado para ese paso.

### 2.5 Hallazgo adicional de seguridad TLS (D9, no en la auditoría F12 previa)

El patrón `REQUESTS_VERIFY` (fail-closed, `verify=True` salvo
`REQUESTS_VERIFY=0` explícito) está correctamente aplicado en el camino
productivo real: `scripts/dolares/_dolar.py`, `fetch_dolarito_historico.py`,
`scripts/pipeline/fetch_dgce.py`, `scripts/tickets/cnv/jobs/job5*.py`,
`job6_extract_div.py` [VERIFICADO POR CÓDIGO]. Existen, en cambio, **~37
scripts con `verify=False` hardcodeado** (no condicional a ninguna
variable), todos bajo `scripts/tickets/cnv/scripts/{cnv_ir,*}` (exploración
`explorar_*`, `_tmp_*`, `extract_*_masivo.py`) y `scripts/demo_txar/`
[VERIFICADO POR CÓDIGO: grep completo]. Ninguno de ellos aparece importado
por `run_update.py`/`run_all.py` [VERIFICADO POR CÓDIGO: grep de `cnv_ir`
sobre `run_update.py` = 0 coincidencias] — son exploración fuera del E2E,
consistente con la advertencia del propio runbook (`00_START_HERE.md` §3:
"si el script no aparece en las tablas... no lo corras"). Riesgo real solo
si alguien los ejecuta manualmente contra una fuente real.

## 3. Estado OBJETIVO (resuelto en `26_F12_ARCHITECTURE_DECISION.md`)

Resumen — desarrollo completo en el ADR:

- El runtime productivo objetivo, para todo dato que se declare
  "validado"/"certificado"/"publicado" bajo este harness, es el **pipeline
  engine** (S00→S04→C10→C11→C12), containerizado y con scheduler real.
- El pipeline screener/legacy **no se elimina ni se fusiona**: continúa
  operando para BYMA/CNV mientras el gap CNV (SG-01) no esté resuelto — pero
  queda etiquetado explícitamente como LEGACY, fuera del runtime objetivo, y
  su salida no debe presentarse como certificada.
- Ver ADR para el detalle de D1-D10, topología, cadena de ejecución y
  criterios de aceptación.

## 4. Runtime actual demostrado

| Componente | Runtime real HOY | Evidencia |
|---|---|---|
| Engine S00-S04 | Python + venv local/DEV (no contenedor) | [VERIFICADO POR CÓDIGO] ningún Dockerfile lo referencia |
| Engine C10/C11/C12 | Python + venv local/DEV, invocación manual | [VERIFICADO POR CÓDIGO] |
| Screener run_all/run_update | Python + venv local (según `docs/runbooks`, el mismo host que corre Docker `catalaxia-engine-dev`/`catalaxia-db`) | [VERIFICADO POR CÓDIGO] `docs/screener/OPERACION.md` §1 |
| API pública | Contenedor `Dockerfile.api`, `uvicorn api.main:app` puerto 8100 tras nginx 9200/80 | [VERIFICADO POR CÓDIGO] `docker-compose.yml`, `Dockerfile.api` |
| DB dev | Docker `catalaxia-engine-dev`, puerto 5433 | [VERIFICADO POR CÓDIGO] `docs/runbooks/00_START_HERE.md` §4, `engine/manifest.yaml` |
| DB prod | Docker `catalaxia-db`, puerto 5432, guard `EXT-010` en `engine/config.py` | [VERIFICADO POR CÓDIGO] |
| Contenedor `pipeline` (docker-compose) | Definido pero **no puede ejecutar `run_update.py`**: imagen sin `yfinance`/`requests` (root `requirements.txt` post-`4b74df2`) | [VERIFICADO POR CÓDIGO: import de módulo top-level en `run_update.py` líneas 27-28 + contenido de `requirements.txt`] |
| Cron VPS | Definido en `setup_vps.sh` (5 líneas cron), apunta al contenedor `pipeline` roto | [VERIFICADO POR CÓDIGO] |
| Ejecución real en VPS | — | [NO DETERMINABLE: sin acceso al VPS] |
| Windows Task Scheduler activo | Script de alta existe y es correcto | [NO DETERMINABLE si está efectivamente registrado en una máquina] |

## 5. Runtime objetivo

Ver ADR §"Selected architecture" y §"Runtime topology".

## 6. Scheduler

**HOY**: Windows Task Scheduler (screener/legacy, evidencia de código, no de
ejecución) + intento no funcional de cron VPS (engine ni siquiera está en
el intento; el intento apunta al pipeline legacy y está roto por
dependencias) [VERIFICADO POR CÓDIGO].
**OBJETIVO**: cron dentro de un contenedor Linux (VPS), disparando el
entrypoint oficial del pipeline engine — ver ADR.

## 7. Entrypoint

**HOY**: no existe un entrypoint único para el pipeline engine completo
(S00→C12); `e2e_orchestrator.py` cubre solo S00→S04. El pipeline legacy sí
tiene entrypoints únicos (`run_all.py`, `run_update.py`) pero no incluyen
gate/certificación.
**OBJETIVO**: ver ADR §"Execution chain".

## 8. Containers

`Dockerfile` (pipeline, root `requirements.txt` — insuficiente, ver §2),
`Dockerfile.api` (API, root `requirements.txt` — suficiente, `psycopg2`+
`fastapi`+`uvicorn` cubren `api/main.py`), `docker-compose.yml` (`db`,
`pipeline` [profile manual], `migrate` [profile manual], `api`, `nginx`)
[VERIFICADO POR CÓDIGO, archivo completo leído].

## 9. Dependencias

| Runtime | Requiere | Fuente actual | Estado |
|---|---|---|---|
| API | `fastapi`, `uvicorn[standard]`, `psycopg2-binary` | `requirements.txt` (raíz) | [VERIFICADO POR CÓDIGO] correcto, coincide con imports de `api/main.py` |
| Pipeline legacy (`run_update.py`/`run_all.py`) | `yfinance`, `requests`, `pandas`, `openpyxl`, `sqlalchemy`(?), `psycopg2` | `backend/requirements.txt` (no usado por ningún Dockerfile) | [VERIFICADO POR CÓDIGO] roto: ningún Dockerfile lo instala |
| Pipeline engine (S00-S04, C10-C12) | `sqlalchemy`, `psycopg2-binary`, stdlib | ninguno de los dos `requirements.txt` fue auditado específicamente para este set en esta sesión | [NO DETERMINABLE — pendiente lockfile propio, ver ADR/criterios] |
| Migrate/sync | `psycopg2`, `sqlite3` | root `requirements.txt` (parcial) | [VERIFICADO POR CÓDIGO] `migrate_sqlite_to_pg.py` corre en el contenedor `migrate` con la misma imagen `pipeline` — hereda el mismo problema de dependencias que el pipeline |

## 10. Configuración

Variables observadas: `POSTGRES_PASSWORD` (obligatoria, sin default,
guardada por `setup_vps.sh` vía `: "${POSTGRES_PASSWORD:?...}"`), `API_KEY`,
`API_CORS_ORIGINS` (leídas por `api/main.py` vía `os.environ.get`, F11),
`DB_HOST/PORT/NAME/USER/PASSWORD`, `TZ`, `REQUESTS_VERIFY` (por script, no
global) [VERIFICADO POR CÓDIGO].

## 11. Secretos

- `POSTGRES_PASSWORD`: exigida sin default en `setup_vps.sh`
  [VERIFICADO POR CÓDIGO] — correcto.
- `API_KEY`/`API_CORS_ORIGINS`: **`setup_vps.sh` nunca las escribe en
  `.env`** [VERIFICADO POR CÓDIGO, grep completo del script] **y aunque se
  escribieran, el servicio `api` de `docker-compose.yml` no tiene
  `environment: API_KEY`/`API_CORS_ORIGINS` ni `env_file:` — nunca
  llegarían al contenedor** [VERIFICADO POR CÓDIGO, `docker-compose.yml`
  completo, sin `env_file` en ningún servicio]. Doble gap, no uno.
- Sin `API_KEY`, `api/main.py` es fail-closed (503 en todos los endpoints)
  [VERIFICADO POR CÓDIGO, F11, confirmado también en auditoría F13 previa:
  `test_api_security` 15/15 PASS].
- Ningún secreto hardcodeado detectado en el código auditado esta sesión
  (repetición del check R2 hecho en la auditoría F13: `deploy.py`/
  `deploy_production.sh` no existen; solo `deploy.sh`, sin credenciales
  embebidas) [VERIFICADO POR CÓDIGO, reconfirmado].
- `nginx.conf`/`public/*`: no auditados en profundidad esta sesión
  [NO DETERMINABLE].

## 12. Base de datos

PostgreSQL es la base productiva declarada (`engine/manifest.yaml`: DEV
5433/`catalaxia-engine-dev`, PROD 5432/`catalaxia-db`, guard `EXT-010`)
[VERIFICADO POR CÓDIGO]. SQLite (`data/screener.db`) es el almacén de
trabajo del pipeline legacy, no versionado, puente manual hacia PostgreSQL
vía `sincronizar_a_produccion.py` (correcto, upsert/reemplazo en
transacción) o `migrate_sqlite_to_pg.py` (peligroso, vacía 12 columnas —
§2.4). `setup_vps.sh` usa el segundo.

## 13. Datos / RAW

RAW inmutable verificado en la auditoría F13 previa (a nivel del pipeline
engine): `fetch.py` bloquea overwrite [VERIFICADO POR CÓDIGO, no repetido
esta sesión]. El pipeline legacy no tiene un concepto equivalente de RAW
inmutable declarado — sus fuentes se re-descargan/sobre-escriben según
`run_update.py` [NO DETERMINABLE en profundidad, fuera del foco de F12].

## 14. Backups

`scripts/backup.sh`: `pg_dump` + copia de 5 exports CSV/JSON + purga >30
días [VERIFICADO POR CÓDIGO, archivo completo leído]. **No define
restauración automatizada ni prueba de restore** — solo el `psql < backup`
manual documentado en `docs/DEPLOY.md`. Cron de backup (`0 3 * * *`) definido
en `setup_vps.sh` pero depende del mismo `docker compose exec db` — si `db`
no está `healthy`, falla; no verificado por ejecución.

## 15. Observabilidad

- `run_id`/`stage_id`/estados: existen y son robustos en el pipeline
  **engine** (F5-F10 los certificaron) [VERIFICADO POR TEST, sesiones
  previas].
- El pipeline legacy usa logs planos en `data/logs/upd_YYYYMMDD_HHMMSS.log`
  y `data/logs/cnv_last_status.json` — sin `run_id`/`stage_id`, sin
  vínculo con `engine.*` [VERIFICADO POR CÓDIGO, `docs/screener/OPERACION.md`].
- `api/main.py` expone `/health` [VERIFICADO POR CÓDIGO, línea 143], pero
  `docker-compose.yml` **no define `healthcheck:` para el servicio `api`**
  (solo `db` lo tiene) [VERIFICADO POR CÓDIGO] — gap de observabilidad de
  infraestructura no mencionado en la auditoría F12 previa.
- Alertas: ninguna evidencia de mecanismo de alerta (email/Slack/webhook)
  en ningún script auditado [NO DETERMINABLE / probablemente ausente].

## 16. Failure handling

Ver ADR §"Failure model" para la tabla completa por escenario (S00-S04,
C10 BLOCK, C11 NEGADA, C12 BLOCK, pérdida de contenedor, reinicio VPS,
scheduler duplicado, fallo DB, fallo red, datos parciales).

## 17. Seguridad

F11 (TLS + API auth/CORS) verde y no modificado esta sesión [VERIFICADO
POR TEST, reconfirmado de la auditoría F13: 15/15]. Hallazgos nuevos de
esta sesión: doble gap API_KEY/CORS en compose (§11), ~37 scripts con
`verify=False` hardcodeado fuera del E2E productivo (§2.5).

## 18. Legacy

Pipeline screener/CNV completo (`run_all.py`, `run_update.py`,
`job5_v2_extract_eeff.py`, `sincronizar_a_produccion.py`,
`migrate_sqlite_to_pg.py`, `data/screener.db`, tablas PG `screener`/
`screener_hist`/`silver_norm`/`validaciones`/`certificacion_nueva`/
`mep_actual`), `scripts/tickets/cnv/scripts/*` (exploración), demos
(`scripts/demo_txar/`). Ver ADR §"Legacy boundary" — **no se elimina**.

## 19. Dependencias externas

yfinance (Yahoo Finance, no oficial), SEC EDGAR (oficial, XBRL), CNV
(portal argentino, HTML frágil), INDEC (IPC), dominio
`api.catalaxia.webshooks.com` (según `docs/DEPLOY.md`, no verificable sin
DNS real) [NO DETERMINABLE su estado actual].

## 20. Riesgos

1. **Publicación sin certificación** (§2.3) — el más severo, estructural.
2. `setup_vps.sh` invoca `migrate_sqlite_to_pg.py`, que vacía 12 columnas
   productivas sin que la guarda de conteo lo detecte (§2.4).
3. Imagen `pipeline` no puede ejecutar ningún job (F12-1, ya conocido).
4. `REPO_URL`/paths inconsistentes (F12-2/F12-3, ya conocidos).
5. `API_KEY`/`API_CORS_ORIGINS` no llegan al contenedor ni por
   `setup_vps.sh` ni por `docker-compose.yml` (F12-4, ampliado en §11).
6. Sin healthcheck de `api` en compose — un contenedor "up" puede estar
   sirviendo 503 sin que Docker lo detecte.
7. Sin prueba de restore de backup.
8. `e2e_orchestrator.py` no encadena C10/C11/C12 — cualquier automatización
   futura del pipeline engine necesita ese tramo, no solo S00-S04.

## 21. Evidencia

Todo lo anterior es trazable a: lectura directa de
`scripts/setup_vps.sh`, `docker-compose.yml`, `Dockerfile`,
`Dockerfile.api`, `requirements.txt`, `backend/requirements.txt`,
`api/main.py`, `scripts/engine/e2e_orchestrator.py`,
`scripts/tickets/screener/run_update.py`, `docs/screener/OPERACION.md`,
`docs/runbooks/00_START_HERE.md`, `docs/DEPLOY.md`,
`scripts/deploy/sincronizar_a_produccion.py`, `scripts/backup.sh`, y greps
dirigidos sobre el árbol completo. Ninguna DB fue escrita; ninguna
ejecución de red o de contenedor fue lanzada. Donde no hubo evidencia
directa, se marcó [NO DETERMINABLE] explícitamente, sin inventar.
