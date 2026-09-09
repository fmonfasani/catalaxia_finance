# 23 — F12 AUDIT — Runtime + Cron-VPS (reconciliado)

Auditoría de operación productiva (CAPA EJECUCIÓN + INFRAESTRUCTURA) sobre el
estado REAL reconciliado del árbol. Objetivo: gaps #3 (cron-VPS) y #4 (runtime
legacy). Sin tocar código, datos ni producción. Lo no evidenciado = NO DETERMINABLE.

## 1. Cron HOY en VPS — `setup_vps.sh` (v2) → `/etc/cron.d/catalaxia`

| Cron | Comando | Job |
|---|---|---|
| `30 18 * * 1-5` | `run_update.py --daily --quiet` | precios yfinance |
| `0 8 1 * *` | `run_update.py --monthly --quiet` | IPC |
| `0 10 1 1,4,7,10 *` | `run_update.py --quarterly --quiet` | EDGAR+CNV+rebuild |
| `0 12 1 1 *` | `run_update.py --annual --quiet` | ADR 20-F |
| `0 3 * * *` | `scripts/backup.sh` | pg_dump + exports |

Los jobs `pipeline` corren como `docker compose run --rm pipeline python
scripts/tickets/screener/run_update.py <modo>`. Modos válidos en run_update.py:
`--daily --monthly --quarterly --annual --rebuild` (argparse, verificado).

**Hallazgo crítico (gap #4):** la imagen pipeline se construye con
`requirements.txt` (raíz), que tras `4b74df2` no contiene `yfinance` ni
`requests`. `run_update.py` importa `yfinance as yf` + `import requests` →
**el contenedor no puede ejecutar ningún job del cron**. El runtime real que
produjo los datos actuales es el venv local/DEV (yfinance 1.3.0, requests 2.32.5,
SQLAlchemy 2.0.48…), no la imagen Docker.

## 2. Mapa JOB → SCRIPT → DEPENDENCIA → DATOS → DESTINO → FRECUENCIA

| JOB | SCRIPT | DEPENDENCIA | DATOS | DESTINO | FRECUENCIA |
|---|---|---|---|---|---|
| daily | run_update.py --daily | yfinance, requests, sqlite3 | precios máx/mín 52s, mkt cap | data/screener.db | 18:30 lun–vie |
| monthly | run_update.py --monthly | requests (IPC INDEC) | serie 145.3, índice | data/ipc_nacional.csv | 1ro del mes 08:00 |
| quarterly | run_update.py --quarterly | request SEC/CNV, yfinance, sqlite3 | companyfacts cache + CNV subset (72 cuits), rebuild s0→s8→s5 | data/screener.db + raw | 1ro de 1,4,7,10 10:00 |
| annual | run_update.py --annual | requests (20-F), sec_adr_ratios | ratios ADR | data/screener.db | 1ro de enero 12:00 |
| backup | backup.sh | docker compose exec pg_dump, gzip, find | pg_dump + exports csv/json | backups/*.sql.gz (retención 30d) | diario 03:00 |
| migrate | migrate_sqlite_to_pg.py | psycopg2, sqlite3 | screener.db → PG prod | PostgreSQL catalaxia | manual (setup paso 6) |
| sync | sincronizar_a_produccion.py | psycopg2, sqlite3 | SQLite → PG prod (upsert/reemplazo) | PostgreSQL prod | manual (--dry-run) |
| api | api/main.py (uvicorn) | psycopg2, fastapi | servicio: endpooints v1/v2 | nginx 9200 → api 8100 | siempre (non-cron) |

## 3. Auditoría `setup_vps.sh` (v2, 175 líneas)

| Paso | Acción | Estado |
|---|---|---|
| 1 | prerequisitos docker/docker-compose/git | OK |
| 2 | dirs backups/logs/data | OK |
| 3 | clonar/pull repo | WARN: REPO_URL `git@github.com:anomalyco/catalaxia-cedears-prod.git` ≠ remote real (`https://github.com/fmonfasani/catalaxia_finance.git`) |
| 4 | `.env` con POSTGRES_PASSWORD | OK (ya no escribe vacío) |
| 5 | `docker compose up -d db` + pg_isready wait | OK |
| 6 | migrar si existe screener.db (migrate_sqlite_to_pg.py) | WARN: no define API_KEY/CORS; migrar es 1-vez manual |
| 7 | smoke `run_update.py --rebuild --quiet` | **BLOCK**: imagen sin yfinance/requests → falla al importar |
| 8 | cron `/etc/cron.d/catalaxia` | WARN: 5 líneas válidas, pero todas dependen de imagen rota; no define API_KEY para la API |

`deploy.sh` (legacy): usa `docker-compose` (v1) y `up -d` sin `--profile manual`
→ api/pipeline/migrate tienen perfil `manual`; el `up` genérico solo garantiza db+nginx.
`DEPLOY.md` usa `/opt/catalaxia`; `setup_vps.sh` usa `/infra/projects/0009-catalaxia` → path inconsistente (WARN).

## 4. NO DETERMINABLE (no inventar)

- Cuál de los 3 cron/path models (Task Scheduler local vs cron VPS) es el que
  realmente opera producción hoy (docs contradictorios; sin verificación en VPS).
- Si `backend/requirements.txt` es el runtime oficial del pipeline o un borrador.
- Estado real del VPS (no accesible; pendiente runbook verificado en servidor).
- Disponibilidad de `bash`/`docker` locales para validar `bash -n` y `docker compose config`.

## 5. Dependencia F11 concreta

- API fail-closed (503 sin API_KEY): setup_vps v2 no provee la var → configuración
  incompleta si se aplica. F11 permanece verde (15/15) y NO se modifica en F12.
- TLS productivo: jobs confirmados contra fuentes con cert válido; REQUESTS_VERIFY=1
  por default; backups/export no dependen de F11.