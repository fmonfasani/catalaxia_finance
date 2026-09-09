# 23 — PRE-STATE F12 (reconciliado) — Runtime + Cron-VPS

F12 · CAPA EJECUCIÓN + INFRAESTRUCTURA · CICLO DEFINIR→IMPLEMENTAR→VERIFICAR.
Documento de pre-state escrito sobre el estado REAL reconciliado del árbol
(se detectó trabajo concurrente que revirtió una pre-sesión anterior). Sin
escrituras a base, sin despliegue, sin modificar código.

## 1. Identidad del repo

- HEAD: `aa02df9` (`docs(checkpoint): registrar resultado del checkpoint F5-F10`).
- Rama: `fix/ttm-ratios-cnv`.
- Remote: `https://github.com/fmonfasani/catalaxia_finance.git`.
- `git status`: 238 entradas sin commitear (F5–F10 en curso, docs/review 01_*..24_*,
  scripts/engine/c10_evaluate.py, tests/test_f5_multisource.py, …).

## 2. Arquitectura HOY según docs de operación (no por nombre)

`docs/runbooks/00_START_HERE.md` declara el estado real del sistema:

- **SEC** (camino oficial): `scripts/engine/s00_smoke.py` → `s01_identity.py` →
  `s02_fetch_ypf.py` → `s03_parse_ypf.py` → `s04_normalize.py` → `ratio_engine.py`.
  Cada script con STAGE_ID registrado. Runtime: Python + PostgreSQL `catalaxia`
  (DEV 127.0.0.1:5433, rol `catalaxia_engine`; PROD 5432 protegido por EXT-010).
- **CNV** (camino que produjo los datos actuales = NOT oficial): legacy
  `scripts/tickets/cnv/jobs/job5_v2_extract_eeff.py` → `data/screener.db`.
  El camino "engine" (`c3_cnv_fetch.py`) solo descarga visor/empresa; NO estados
  financieros. No existe E2E CNV ejecutable en el repo principal (`SG-01`).
- `scripts/engine/` tiene ~60 archivos; la mayoría son auditorías puntuales
  (`f0NN_*`, `audit_*`, `mut_*`). Regla de runbook: no son parte del E2E.

`docs/screener/OPERACION.md` (pipeline productivo del screener, 571 empresas):

- Reconstrucción: `run_all.py` (EXTRACT→TRANSFORM→ASSEMBLE→EXPORT).
- Jobs periódicos: `run_update.py --daily/--monthly/--quarterly/--annual/--rebuild`.
- Programación de jobs HOY = **Windows Task Scheduler** local/VM
  (`scripts/tickets/screener/setup_scheduler.ps1`), NO cron VPS.
- Datos: `data/screener.db` (SQLite, ~750 MB, no va a git); export `screener_export.csv`.

## 3. Runtime efectivo de los datos actuales

- Entorno local/DEV (donde se generaron los datos del screener):
  Python + venv con `yfinance`, `requests`, `sqlalchemy`, `pandas`, `openpyxl`,
  `psycopg2`, `fastapi`, `uvicorn`. Versiones instaladas verificadas:
  yfinance 1.3.0, requests 2.32.5, SQLAlchemy 2.0.48, fastapi 0.136.3,
  psycopg2-binary 2.9.11.
- La imagen Docker (`Dockerfile`, python:3.12-slim) instala `requirements.txt`
  (raíz), que tras el commit `4b74df2` **solo contiene** `fastapi==0.104.1`,
  `uvicorn[standard]==0.24.0`, `psycopg2-binary==2.9.9` (se removieron
  `requests`, `yfinance`, `pandas`, `openpyxl`, `numpy`, `urllib3`).
- `backend/requirements.txt` existe por separado con `yfinance==0.2.50`,
  `requests==2.32.3`, `sqlalchemy==2.0.36`, `asyncpg`, `pydantic`,
  `python-dotenv` — pero **no lo usa ningún Dockerfile**.
- Consecuencia verificable: el contenedor `pipeline` NO puede ejecutar
  `run_update.py` (importa `yfinance`+`requests`, ausentes en la imagen).

## 4. Archivos VPS que existen HOY (reconciliado)

- `scripts/setup_vps.sh` (175 líneas): 8 pasos, `.env` con POSTGRES_PASSWORD real,
  `migrate_sqlite_to_pg.py` (existe), cron `/etc/cron.d/catalaxia`, smoke `--rebuild --quiet`.
- `scripts/backup.sh` (existe): pg_dump + exports + retención 30 días.
- `docker-compose.yml`: db (postgres:16), pipeline (perfil manual), migrate
  (perfil manual), api (Dockerfile.api), nginx (9200:80, `nginx/nginx.conf`, `public/`).
- `Dockerfile` / `Dockerfile.api` / `nginx/nginx.conf` / `public/*.html`.
- `docs/DEPLOY.md`, `docs/DEPLOY_HETZNER.md`, `docs/DEPLOYMENT_SCREENER_V2.md` (plan lejado).

## 5. Dependencia con F11

- API fail-closed: necesita `API_KEY` y `API_CORS_ORIGINS` en `.env` de VPS.
- `run_update.py`/jobs de extracción verifican TLS por defecto (`REQUESTS_VERIFY=1`).
- F11 quedó verde en esta sesión: `test_api_security` + `test_f9` = 15/15 PASS.
- El cron VPS (setup_vps v2) NO define `API_KEY`/`API_CORS_ORIGINS` en `.env`
  (solo POSTGRES_PASSWORD/DB_*) → si se aplica tal cual, la API queda 503.