# CATÁLOGO DE LOGS

## 1 · Dónde se registra qué

**No hay archivos de log.** Todo va a **stdout** o a **PostgreSQL**. No existe
`logging` configurado, ni rotación, ni un directorio de logs.

| destino | qué contiene | quién escribe |
|---|---|---|
| `engine.runs` | una fila por corrida: `run_id`, `mode`, `status`, `git_commit`, `pipeline_version`, `started_at`, `finished_at` | `engine/db.py::start_run` / `finish_run` |
| `engine.stage_runs` | una fila por **transición** de estado: `stage_id`, `state`, `prev_state`, `gate_status`, `gate_reasons`, `report` | `record_stage_transition` |
| `engine.checkpoints` | `checkpoint_id`, `stage_id`, `run_id`, `input_hash`, `code_version`, `contract_version`, `artifact_ref` | S03 |
| `fetch_raw.download_log` | **una fila por descarga SEC** con `sha256` | S02 |
| `fetch_raw.cnv_download_log` | una fila por artefacto CNV | C3 |
| `market_fetch_log` | 601 filas, corridas de market | scripts de `scripts/market/` |
| **stdout** | todo lo demás, incluida **toda** la extracción CNV legacy | job5, s0_normalizar |

## 2 · El `report` JSON — el log más completo del sistema

Lo define `engine/report.py::StageReport`. Se guarda en
`engine.stage_runs.report`.

```json
{
  "stage": "S03_parse",
  "run_id": "…", "mode": "FAST",
  "started_at": "…", "finished_at": "…",
  "input":     { "checkpoint_id": "…", "rows": 0 },
  "coverage":  { "expected": 0, "parsed": 0, "rejected": 0, "by_reason": {} },
  "integrity": { "hash_in": "…", "hash_out": "…" },
  "gate":      { "status": "PASS", "reasons": [], "checks": [ … ] }
}
```

Más `nulls_count`, `nulls_by_reason`, `parser_version`, `script`, `git_commit`.

Leerlo:
```bash
docker exec catalaxia-engine-dev psql -U catalaxia -d catalaxia -tAc \
  "SELECT jsonb_pretty(report) FROM engine.stage_runs \
    WHERE run_id='<RUN_ID>' AND report IS NOT NULL ORDER BY started_at DESC LIMIT 1"
```

Tres invariantes que `validate()` impone y que explican fallas al cerrar etapa:
campos obligatorios presentes; **`checks` no vacío**; y
**`expected == parsed + rejected`**.

## 3 · Matriz de huecos de logging

| etapa | dato | ¿existe? | ¿dónde? | formato | ¿alcanza para reconstruir? |
|---|---|---|---|---|---|
| S00–S04 | timestamp | sí | `engine.runs`, `stage_runs` | `timestamptz` | sí |
| S00–S04 | RUN_ID | sí | `engine.runs.run_id` | hex 32 | sí |
| S00–S04 | stage | sí | `stage_runs.stage_id` | texto | sí |
| S00–S04 | input/output | sí | `report.input`, `report.coverage` | JSON | sí |
| S00–S04 | counts | sí | `expected/parsed/rejected` | JSON | sí |
| S00–S04 | errors | sí | `rejected_by_reason` | JSON | sí |
| S00–S04 | warnings | sí | `checks[].result = WARN` | JSON | sí |
| S00–S04 | digest | sí | `hash_in` / `hash_out` (`hashout-v2`) | hex 64 | sí |
| S00–S04 | checkpoint | sí | `engine.checkpoints` | fila | sí |
| S02 | entity / period | sí | `download_log.cik`, `period_of_report` | columnas | sí |
| S02 | **retries** | **parcial** | no hay columna de intentos en `download_log` | — | **no**: se sabe el status final, no cuántas veces se intentó |
| S02 | fallback usado | **no** | — | — | **no** |
| C3 | retries | sí | `cnv_download_log.attempts` | int | sí (valor observado siempre 1) |
| C3 | hash de origen | **columna sí, dato no** | `hash_cnv` NULL en 4.005/4.005 | — | **no** |
| **CNV job5** | **todo** | **no** | sólo stdout | contadores agregados | **no** |
| ratios | provenance de inputs | sí | `derived.ratio.inputs` (JSONB) | JSON | sí |

### Los tres huecos que importan

1. **`LOG GAP 1` — la extracción CNV no deja rastro.** `job5` imprime
   `ok/skip/cache/err/dp` y nada más. Un documento descartado es un `+1` en un
   entero. No hay `run_id`, ni tabla, ni motivo, ni el GUID afectado.
   **Consecuencia demostrada:** el CONSOLIDADO de METR al 30/09/2024 falta y no
   hay forma de saber por qué sin abrir el HTML a mano. (`SG-04`)

2. **`LOG GAP 2` — S02 no registra los reintentos.** `engine/fetch.py`
   reintenta hasta 3 veces con backoff, pero `download_log` guarda sólo el
   resultado final. No se puede distinguir "salió a la primera" de "salió tras
   dos 429". Para diagnosticar rate limiting eso es justamente lo que hace
   falta.

3. **`LOG GAP 3` — el hash de origen de CNV nunca se captura.** La columna
   `hash_cnv` y el check `C-C3-008` existen; el dato no. El mecanismo de
   detección de SHA mismatch está montado sobre una columna vacía. (`SG-02`)

## 4 · Ejemplo real

Distribución observada en `engine.stage_runs` de la base `cnvmig`:

```
   stage_id    | transiciones | corridas | con_report |   gates
---------------+--------------+----------+------------+------------
 C3_CNV_fetch  |          294 |      108 |         26 | BLOCK,PASS
 C3_CNV_FETCH  |          120 |       80 |          0 |
 S00_bootstrap |           20 |        4 |          2 | PASS
 S01_identity  |           11 |        3 |          2 | BLOCK,PASS
 S02_fetch     |           73 |       17 |         12 | BLOCK,PASS
 S03_parse     |          163 |       39 |         27 | BLOCK,PASS
 S04_normalize |          133 |       29 |         27 | BLOCK,PASS
```

Dos cosas se leen ahí:

- **La mayoría de las transiciones no llevan reporte.** Es correcto: sólo el
  cierre de etapa lo adjunta; las intermedias registran el cambio de estado.
- **`C3_CNV_fetch` y `C3_CNV_FETCH` conviven.** Son claves distintas para la
  base. La variante en mayúsculas tiene 120 transiciones y **cero** reportes y
  gates. Al consultar histórico de CNV, usá `upper(stage_id)='C3_CNV_FETCH'`.
  (`SG-06`)
