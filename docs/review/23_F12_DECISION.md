# 23 — F12 DECISION — Runtime + Cron-VPS

## Decisión arquitectónica requerida (antes de implementar)

El análisis (23_PRE_F12_STATE + 23_F12_RUNTIME_CRON_VPS_AUDIT) demuestra que la
implementación de la operación productiva requiere decidir primero:

### D1 — ¿Cuál es el runtime productivo para el cron?
- **Opción A (legacy endurecido):** mantener `run_update.py` como job productivo;
  agregar `yfinance`+`requests`+`pandas` al `requirements.txt`/`Dockerfile` del
  pipeline (o usar `backend/requirements.txt`).
- **Opción B (motor/engine):** el pipeline SEC (S00→S04 + ratio_engine) pasa a ser
  la ejecución productiva sobre PostgreSQL; requiere imagen con `sqlalchemy`,
  rol `catalaxia_engine`, migraciones y cron definido. Controversia: los datos
  CNV actuales NO provienen del engine (C3 solo descarga visor/empresa) → si se
  elige B, CNV queda como gestión legacy.
- **Opción C (híbrido):** engine para SEC; screener/CNV legacy para los datos
  actuales, con frontera explícita y sin duplicación nominal.

### D2 — ¿Qué `requirements.txt` es el oficial del runtime?
- Raíz (solo API) vs `backend/requirements.txt` (yfinance/sqlalchemy/asyncpg).
- Evidencia: ningún Dockerfile usa `backend/requirements.txt`; el contenedor HOY
  no puede correr su propio cron (gap #4). Decisión o gap permanece BLOCK.

### D3 — ¿Dónde vive el scheduler productivo?
- Windows Task Scheduler local/VM (`setup_scheduler.ps1`) vs cron VPS
  (`/etc/cron.d/catalaxia`) vs híbrido con API_KEY/CORS en `.env`.
- Hornada actual define ambos; docs contradictorios → NO DETERMINABLE, requiere decisión.

### D4 — ¿Qué env necesita el cron en VPS?
- `POSTGRES_PASSWORD`, `API_KEY`, `API_CORS_ORIGINS` (F11). setup_vps v2 solo
  escribe POSTGRES_PASSWORD → la API quedaría 503 tras apply sin decidir D4.

## Qué NO se implementa en F12

- NO se modifica setup_vps.sh, Dockerfile, Dockerfile.api, requirements.txt,
  docker-compose, run_update, engine, api/main.py, migrations, `.env.example`.
- NO se toca producción (VPS) ni datos productivos ni schema. NO se borra nada.
- NO se inicia F13 ni F14.

## Qué SÍ se entrega en F12

- Documentación de auditoría y pre-state reconciliado.
- Esta decisión (D1–D4) documentada para el gate arquitectónico.
- Dependency/mapeo JOB→SCRIPT→DEPENDENCIA→DATOS→DESTINO→FRECUENCIA.
- Verificación de que F11 permanece verde.

## DETENER

F12 concluye en DEFINIR + auditoría + decisión. La implementación de runtime/cron
queda pendiente de D1–D4. No se inventa la decisión; se documenta.