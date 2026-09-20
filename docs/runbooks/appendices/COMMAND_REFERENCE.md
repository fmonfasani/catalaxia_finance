# REFERENCIA DE COMANDOS

Sólo los comandos del E2E. Todo desde la raíz del repo. Los argumentos están
verificados contra el `argparse` de cada script.

---

## Pipeline SEC

| # | comando | argumentos | escribe |
|---|---|---|---|
| 1 | `python scripts/engine/s00_smoke.py` | ninguno | `engine.*` |
| 2 | `python scripts/engine/s01_identity.py` | `--cik` (def. `0000904851`, YPF golden) | `identity.*` (**no** `identity_v1`, ese esquema es del camino CNV/C3); `engine.checkpoints` si no es E2E |
| 3 | `python scripts/engine/s02_fetch_ypf.py` | `--cik` (def. `0000904851`) · `--forms` · `--max-filings` | `data/raw/engine/`, `fetch_raw.download_log` |
| 4 | `python scripts/engine/s03_parse_ypf.py` | `--cik` (def. `0000904851`) · `--min-xbrl` | `parsed.*`, `engine.checkpoints` (F13: condicional a `decidir_reemplazo`) |
| 5 | `python scripts/engine/s04_normalize.py` | `--dry-run` | `derived.fact`, `derived.normalize_conflict` |
| 6 | `python scripts/engine/ratio_engine.py` | `--persist` · `--cik` | `derived.ratio` (**sólo con `--persist`**; 4 `canonical_id`: `eps`,`pb`,`pe`,`ev_sales`) |

Prefijo obligatorio en todas:
```
ENGINE_DB_NAME=<base> ENGINE_DB_PORT=5433
```

## Pipeline engine — validación, certificación, publicación (F12)

| # | comando | argumentos | escribe |
|---|---|---|---|
| 7 | `python scripts/engine/c10_evaluate.py` | `--sec-runs` · `--ciks` · `--tickers` · `--scope {sec,market,cross,cnv,all}` · `--json-out` | nada (solo lectura) |
| 8 | `python scripts/engine/c11_certificar.py` | `--run-id` (def. último terminal) · `--mode` · `--rule` (def. `c11-rule-v1`) · `--json-output` | `engine.certifications` |
| 9 | `python scripts/engine/publisher.py` | `--source` · `--target` (**obligatorio**) · `--run-id` · `--pk` · `--filter` · `--min-rows` · `--dry-run` · `--rollback` | `staging.<target>__new__*`, `staging._publications` |
| 10 | `python scripts/engine/e2e_orchestrator.py` | `--mode` · `--run-id` · `--cik` · `--forms` · `--min-xbrl` | encadena S00→S04 (subprocesos, mismo `run_id`) |
| 11 | `python scripts/engine/run_e2e_certified.py` | `--mode` · `--cik` · `--tickers` · `--scope` · `--run-id` · `--no-lock` · `--no-ratios` · `--dry-run` · `--publish-source` · `--publish-target` · `--publish-pk` · `--json-out` | encadena S00→S04→ratio_engine→C10→C11→C12; advisory lock; `outputs/e2e/e2e_<ts>.json` |

Contenedor (F12): `docker compose --profile run-e2e run --rm engine [--mode FULL]`.

## Pipeline CNV

| # | comando | argumentos | escribe |
|---|---|---|---|
| A | `python scripts/engine/c3_cnv_fetch.py` | `--cuit` **o** `--cik` (exactamente uno) · `--scope` (def. `FINANCIERO`) · `--desde-anio` · `--max-visores` · `--adjuntos-presentaciones` (def. `0`) · `--adjunto-max-mb` (def. `30.0`) · `--rerun` · `--delay-visor` | `fetch_raw.cnv_download_log`, RAW |
| B1 | `python scripts/tickets/cnv/jobs/job5_v2_extract_eeff.py` | ver abajo — **no usa `argparse`** | **`data/screener.db`**, `data/log_job5_v2_done.txt` |
| B2 | `python scripts/tickets/screener/s0_normalizar_cnv.py` | ninguno | `data/screener.db` |

### job5 — argumentos reales

Parsea `sys.argv` a mano, así que **no tiene `--help`**. Los que reconoce:

| argumento | forma | default | efecto |
|---|---|---|---|
| `--rango` | `--rango R0 R1` | todo | procesa `filas[R0:R1]` de la whitelist |
| `--max` | `--max N` | `10**9` | tope de **descargas HTTP** (no de documentos procesados) |
| `--sleep` | `--sleep S` | `0.3` | espera entre fetches reales |
| `--whitelist` | `--whitelist RUTA` | `scripts/tickets/cnv/datos/whitelist_eeff.csv` | otra lista de entrada |
| `--cuits` | `--cuits RUTA.csv` | todos | filtra por los CUIT del CSV |
| `--codigos` | bandera | off | usa `whitelist_eeff_codigos.csv` |
| `--offline` | bandera | off | no descarga; sólo procesa lo que ya está en disco |

**`--rango` y `--max` son la causa de `CNV-COV-001`.** Una corrida acotada deja
documentos sin procesar y **nada lo reporta**. Si querés cobertura completa de
un emisor, corré con `--cuits` y **sin** `--rango`, y después verificá la
reconciliación de `03_CNV_E2E_RUNBOOK.md`.
| C | `python scripts/engine/c4_cnv_adapter.py` | `--cuit` (obligatorio) · `--persist` | **no está en este repo**: worktree `catalaxia-cnvmig` |

## Market

| comando | argumentos |
|---|---|
| `python scripts/market/m2_fetch_engine.py` | `--instruments` · `--limit` · `--stage` (def. `batch`) · `--no-snapshot` · `--json-out` |
| `python scripts/market/m19_apply_schema.py` | aplica `market_schema.sql` |
| `python scripts/market/m4_quality.py` | chequeos de calidad |
| `python scripts/market/m5_golden_case.py` | caso de referencia de market |

---

## Verificaciones

```bash
# entorno
python -c "from engine.config import load_settings; s=load_settings(); print(s.describe())"

# contenedores
docker ps --format "{{.Names}}\t{{.Ports}}"

# huella de screener.db
stat -c '%y %s' data/screener.db

# corridas recientes
docker exec catalaxia-engine-dev psql -U catalaxia -d catalaxia -c \
  "SELECT run_id, mode, status, pipeline_version, started_at \
     FROM engine.runs ORDER BY started_at DESC LIMIT 10"

# etapas de una corrida
docker exec catalaxia-engine-dev psql -U catalaxia -d catalaxia -c \
  "SELECT stage_id, state, gate_status, gate_reasons FROM engine.stage_runs \
    WHERE run_id='<RUN_ID>' ORDER BY started_at"

# reporte completo
docker exec catalaxia-engine-dev psql -U catalaxia -d catalaxia -tAc \
  "SELECT jsonb_pretty(report) FROM engine.stage_runs \
    WHERE run_id='<RUN_ID>' AND report IS NOT NULL ORDER BY started_at DESC LIMIT 1"

# checkpoints
docker exec catalaxia-engine-dev psql -U catalaxia -d catalaxia -c \
  "SELECT stage_id, left(input_hash,16), code_version, contract_version, created_at \
     FROM engine.checkpoints ORDER BY created_at DESC LIMIT 10"

# migraciones
docker exec catalaxia-engine-dev psql -U catalaxia -d catalaxia -c \
  "SELECT filename, applied_at FROM engine.schema_migrations ORDER BY filename"

# produccion intacta
docker exec catalaxia-db psql -U catalaxia -d catalaxia -tAc \
  "SELECT string_agg(nspname,',') FROM pg_namespace \
    WHERE nspname NOT LIKE 'pg_%' AND nspname<>'information_schema'"
```

---

## Scripts que NO son parte del E2E

`scripts/engine/` tiene 60 archivos. Éstos **no** se ejecutan como parte de un
pipeline:

| patrón | qué son |
|---|---|
| `audit_*.py`, `audit_f0NN_*.py` | auditorías puntuales de defectos cerrados |
| `f0NN_*.py`, `mut_*.py` | bancos de prueba y mutaciones adversariales |
| `*_adversario.py`, `*_bench.py` | pruebas de robustez |
| `cnv_pilot*.py`, `identity_v1_pilot*.py` | pilotos históricos |
| `homologacion_*.py`, `release_*.py` | procesos de release |
| `demo_*.py`, `screener_demo.py` | demos |

**Peligrosos — no ejecutar sin leer el archivo:**

| script | por qué |
|---|---|
| `scripts/engine/mut_f054_f055.py` | ejecuta `DELETE FROM parsed.facts` |
| `scripts/engine/reparse_universo.py` | reprocesa todo el universo |
| `scripts/pipeline/fix_*.py` | parches históricos de un solo uso |

**Regla:** si el script no está en las tablas de arriba, no es parte del E2E.
