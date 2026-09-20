# 02 · SEC / EDGAR — E2E PASO A PASO

Pipeline oficial y completo. Es el único de los dos que se puede ejecutar de
punta a punta desde el repo principal.

**Caso de referencia (Golden Run): CIK `0000904851` — YPF S.A.** Está fijado
como `GOLDEN_CIK` en `scripts/engine/s02_fetch_ypf.py:29` y
`scripts/engine/s03_parse_ypf.py`. Es el default de `--cik` en las dos etapas.

**Antes de empezar:** ejecutá la verificación de entorno completa de
`01_COMMON_OPERATIONS.md` §1. No es opcional.

---

## Orden de ejecución

```
S00_bootstrap → S01_identity → S02_fetch → S03_parse → S04_normalize → ratios → C10 → C11 → C12
```

Cada etapa lee el resultado de la anterior **buscando en la base la última
corrida con gate `PASS`** de esa etapa (excepto S02→S03: ver nota). Si la
anterior no tiene `PASS`, la siguiente aborta con `BLOCK`.

**Precisión sobre "no se pasan archivos".** Es cierto para el *encadenamiento*
(cada etapa ubica su input por `run_id`/checkpoint en la base, no por
argumento de línea de comandos), pero **no** para el contenido: S02
**sí** escribe archivos RAW reales en `data/raw/engine/`, y S03 los lee de
ahí (`RAW_ROOT`, verificando SHA256 contra `fetch_raw.download_log` antes
de parsear). Lo que no se pasa es una ruta por parámetro: S03 la
redescubre buscando la última corrida S02 con gate `PASS` **del mismo
CIK**.

**F12 — encadenamiento automatizado.** Correr las 5 etapas a mano, una por
una, sigue siendo válido, pero hay dos scripts que las encadenan bajo un
mismo `run_id`:

- `scripts/engine/e2e_orchestrator.py` — S00→S04 como subprocesos, mismo
  `run_id` (`ENGINE_E2E_RUN_ID`). No toca ratios/C10/C11/C12.
- `scripts/engine/run_e2e_certified.py` — la cadena completa **S00→S04→
  ratio_engine→C10→C11→C12**, con `abort-on-fail` y advisory lock de
  PostgreSQL contra corridas cron superpuestas. Es el entrypoint del
  runtime containerizado (F12, `Dockerfile.engine`, servicio `engine` de
  `docker-compose.yml`, perfil `run-e2e`). Ver §"RATIO → C10 → C11 → C12"
  más abajo y `docs/review/26_F12_ARCHITECTURE_DECISION.md`.

---

## S00 · Bootstrap

**1. Objetivo.** Aplicar migraciones pendientes y verificar que el destino no
es producción. Es la etapa que crea `engine.runs`, `engine.stage_runs`,
`engine.checkpoints` y `engine.schema_migrations`.

**2. Precondiciones.** Docker arriba; `01_COMMON_OPERATIONS.md` §1 en verde.

**3. Comando exacto.**
```bash
ENGINE_DB_NAME=catalaxia ENGINE_DB_PORT=5433 python scripts/engine/s00_smoke.py
```
No tiene argumentos de línea de comandos.

**4. Input.** Los archivos `migrations/engine/*.sql` y `migrations/market/*.sql`.

**5. Output esperado.**
```
[run] run_id=<32 hex> git=<sha>
--- conciliacion ---
rows_expected   = 2
rows_parsed     = 2
rows_rejected   = 0 {}
gate            = PASS
```

**6. Cómo interpretarlo.** `rows_expected` son los checks, no filas de datos.
Los dos son `C-S00-001` y `C-S00-002`.

**7. Validaciones.**

| check | bloqueante | qué verifica |
|---|---|---|
| `C-S00-001` | sí | `engine.schema_migrations` registra `001_s00_bootstrap` |
| `C-S00-002` | sí | el destino **no** es producción (`port != 5432`) |

**8. Logs.** `engine.runs` (una fila) + `engine.stage_runs` (transiciones) +
`report` JSON. Ver `01_COMMON_OPERATIONS.md` §4.

**9. Fallback automático.** Ninguno. Es una etapa determinística local.

**10. Fallback manual.** Si falla `C-S00-001`, revisá que el usuario admin
pueda hacer DDL (`ENGINE_ADMIN_DB_USER`, default `catalaxia`). F-025 dejó a la
aplicación corriendo como `catalaxia_engine`, que **no** es superusuario; las
migraciones van por la vía administrativa (`engine/db.py::apply_migrations`).

**11-13. Errores.** `ERROR_CATALOG.md`: `C-S00-001`, `C-S00-002`, `ENG-DB-001`
(permission denied), `EXT-010`.

**14. PASS.** `gate = PASS`, exit code `0`.
**15. PASS_WITH_WARNINGS.** No aplica: los dos checks son bloqueantes.
**16. BLOCKED.** Cualquier check en `FAIL` ⇒ `gate = BLOCK`, exit `1`.
**17. FAILED.** Excepción no controlada; la corrida queda `ABORTED` por el
`finally` de `run_scope`.

**18. Después.** S01.
**19. Evidencia.** `run_id` + salida de consola.
**20. Reanudar.** Volver a correrlo. No tiene checkpoint; es barato.
**21. Idempotencia.** **Demostrada**: la segunda corrida aplica 0 migraciones
(todas registradas en `engine.schema_migrations`) y vuelve a dar `PASS`. Crea
una fila nueva en `engine.runs`, que es lo esperado: cada ejecución es una
corrida.

---

## S01 · Identity

**1. Objetivo.** Sembrar y resolver la identidad de emisores desde el catálogo
de SEC, dejando el esquema **`identity`** (no `identity_v1` — ese esquema es
del camino CNV/C3, `engine/identity_v1.py`) consistente. Ninguna etapa
posterior puede inventar una entidad.

**2. Precondiciones.** S00 con `PASS`.

**3. Comando exacto.**
```bash
ENGINE_DB_NAME=catalaxia ENGINE_DB_PORT=5433 python scripts/engine/s01_identity.py --cik 0000904851
```

| argumento | default | qué hace |
|---|---|---|
| `--cik` | `YPF_CIK` (`0000904851`) | CIK objetivo, 10 dígitos. **Si es el CIK de YPF**, corre `resolve_golden_ypf` + `C-S01-004` (el set completo de checks del Golden Run). **Si es cualquier otro CIK** (vía genérica, F4/multiemisor), corre `resolve_por_cik` sin los checks de YPF: si el CIK no existe en `identity.entities`, agrega el check `C-S01-GEN` en `FAIL` en vez de `C-S01-004`. |

**4. Input.** Catálogo `company_tickers` de SEC en disco
(`engine/identity.py::load_sec_catalog`).

**5. Output esperado.**
```
[seed] entidades nuevas=<n> identificadores nuevos=<n> yf_symbols nuevos=<n>
[links] BYMA nuevos=<n> YF .BA nuevos=<n> conflictos legacy=<n>
[manual] resoluciones aplicadas: identifiers nuevos=<n> yf nuevos=<n> problemas=<n>
--- conciliacion ---
checks_expected = 4
checks_pass     = 4
checks_rejected = 0 {}
gate            = PASS
```

**6. Qué escribe realmente.** Tres pasos, en orden, todos vía `engine/identity.py`:
`seed_from_sec_catalog` (siembra entidades/identificadores nuevos desde el
catálogo SEC), `cross_check_legacy_and_link_byma` (enlaza BYMA/Yahoo,
detecta conflictos legacy), `apply_manual_resolutions` (aplica
resoluciones manuales pendientes). Ninguno de los tres es opcional ni se
puede omitir por argumento.

**7. Validaciones.**

| check | bloqueante | qué verifica |
|---|---|---|
| `C-S01-001` | sí | identidad canónica única por `(id_type, id_value, marketplace)` entre `identity.identifiers` con `status='ACTIVE'` — sin duplicados |
| `C-S01-002` | sí | las discrepancias (`identity.identifier_reviews` `OPEN` + `identity.identifiers` `DISPUTED`) están en revisión manual, al menos tantas como conflictos detectó el paso de enlace |
| `C-S01-003` | sí | `EXT-NEW-002`: `identity.entities` sin columnas de ticker (viven solo en `identifiers`); informa además cuántas filas hay en `identity.classifications` |
| `C-S01-004` | sí, **solo si `--cik` es el de YPF** | la entidad YPF (`CIK:0000904851`) existe, `legal_name = "YPF SOCIEDAD ANONIMA"`, y tiene **activos** los 5 identificadores: `CIK/0000904851/SEC`, `TICKER/YPF/US`, `YF_SYMBOL/YPF/yahoo`, `TICKER/YPFD/BYMA`, `YF_SYMBOL/YPFD.BA/yahoo`; además exige una revisión `OPEN` que documente el conflicto legacy del CIK `1104659` |
| `C-S01-GEN` | sí, **solo si `--cik` ≠ YPF** | el CIK pedido existe en `identity.entities` (vía genérica F4, sin el set de checks de YPF) |

**8. Checkpoint.** S01 **sí escribe** en `engine.checkpoints`
(a diferencia de lo que podría inferirse de otras etapas): si el gate no
es `BLOCK` y la corrida **no** es parte de un E2E (`ENGINE_E2E_RUN_ID` no
seteado), inserta una fila con `artifact_ref="pg://identity.entities"`. En
modo E2E (orquestado por `e2e_orchestrator.py`/`run_e2e_certified.py`) esa
inserción se omite a propósito (decisión R4: no checkpoints individuales
dentro de un E2E).

**14. PASS.** exit `0`. **16. BLOCKED.** exit `1` sólo si el gate es `BLOCK`
(el script devuelve `0` también con `WARNING`: `return 0 if gate is not
GateStatus.BLOCK else 1`).

**21. Idempotencia.** **Demostrada** por diseño: `seed_from_sec_catalog` no
duplica entidades/identificadores ya sembrados. Una segunda corrida reporta
`entidades nuevas=0 identificadores nuevos=0`.

**Nota operativa.** `C-S01-004` (el set rico de checks) sigue clavado a
YPF — corre solo cuando `--cik` es el default. Para cualquier otro emisor,
el gate depende únicamente de `C-S01-GEN` (mera existencia en
`identity.entities`), un check mucho más débil. Registrado como
`SOFTWARE GAP SG-05`.

---

## S02 · Fetch

**1. Objetivo.** Descargar de EDGAR los artefactos del emisor y dejarlos en
`data/raw/engine/`, con un registro por descarga en `fetch_raw.download_log`.

**2. Precondiciones.** S01 con `PASS`. Salida a internet. La cortesía con SEC
es obligatoria: hay un check que la verifica.

**3. Comando exacto.**
```bash
ENGINE_DB_NAME=catalaxia ENGINE_DB_PORT=5433 python scripts/engine/s02_fetch_ypf.py
```

| argumento | default | qué hace |
|---|---|---|
| `--cik` | `0000904851` | CIK objetivo, 10 dígitos |
| `--forms` | ver `FORMS` en el script | formularios, separados por coma |
| `--max-filings` | `MAX_FILINGS` del script | tope de filings |

**5. Output esperado.**
```
[filing] 20-F 0000904851-25-... filed=... period=...
--- conciliacion ---
rows_expected = <n>
rows_ok       = <n>
rows_failed   = 0
gate          = PASS
```

**7. Validaciones.**

| check | bloqueante | qué verifica |
|---|---|---|
| `C-S02-001` | sí | conciliación plan→descargas y ninguna crítica fallida |
| `C-S02-002` | sí | RAW persistido e integridad: se re-lee el disco y se compara SHA256 |
| `C-S02-003` | sí | vinculación completa entidad→cik→fuente→accession |
| `C-S02-004` | sí | **cortesía SEC**: el intervalo mínimo observado ≥ `delay*0.5` |
| `C-S02-005` | sí | S01 consumido en exclusiva; sin lecturas del esquema legacy |

**8. Logs.** Además del `report`: **una fila por descarga** en
`fetch_raw.download_log` con `accession_number`, `request_kind`, `raw_path`,
`http_status`, `sha256`, `bytes`, `critical`. Es el ledger que permite
responder "¿esto se bajó?" documento por documento.

```bash
docker exec catalaxia-engine-dev psql -U catalaxia -d catalaxia -c \
  "SELECT request_kind, count(*), count(sha256), count(*) FILTER (WHERE http_status>=400) \
     FROM fetch_raw.download_log WHERE run_id='<RUN_ID>' GROUP BY 1"
```

**9. Fallback automático — REAL, en `engine/fetch.py`.**

- `max_attempts = 3`
- `backoff = [2.0, 5.0, 10.0]` segundos
- Reintenta **sólo** en HTTP `429, 500, 502, 503, 504`. Cualquier otro status
  no se reintenta.
- Rate limit: `delay = 0.35 s` entre pedidos.

**10. Fallback manual.** Si un artefacto **crítico** falla, S02 corta con
`SystemExit("BLOCK: submissions crítica falló: …")` antes de cerrar la etapa.
No hay fuente alternativa: se vuelve a correr más tarde.

**11-13. Errores.** `SEC-DL-429`, `SEC-DL-5XX`, `SEC-DL-TIMEOUT`,
`SEC-DL-CRIT`, `C-S02-002`, `C-S02-004`. Ver `ERROR_CATALOG.md`.

**14. PASS.** `gate = PASS` ⇒ exit `0`. **16. BLOCK** ⇒ exit `1`.

**20. Reanudar.** Volver a correr con los mismos argumentos. Los artefactos ya
presentes en disco se verifican por SHA en lugar de re-descargarse.

**21. Idempotencia.** **Parcial y verificable**: el RAW no se duplica y el SHA
se revalida, pero cada corrida escribe filas nuevas en `download_log` con un
`run_id` distinto. `download_log` es un **registro de eventos**, no un estado:
que crezca es correcto. Verificá idempotencia comparando el conjunto de
`(accession_number, sha256)`, no el conteo de filas.

---

## S03 · Parse

**1. Objetivo.** Parsear los crudos XBRL/iXBRL y producir `parsed.facts`,
`parsed.contexts`, `parsed.units`, `parsed.concepts`. Es la etapa con
checkpoint real.

**2. Precondiciones.** Una corrida S02 con gate `PASS` **para ese CIK**. Si no
existe, aborta:
`BLOCK: no hay corrida S02 con gate PASS para el CIK <cik>`.

**3. Comando exacto.**
```bash
ENGINE_DB_NAME=catalaxia ENGINE_DB_PORT=5433 python scripts/engine/s03_parse_ypf.py
```

| argumento | default | qué hace |
|---|---|---|
| `--cik` | `0000904851` | CIK a parsear |
| `--min-xbrl` | `MIN_XBRL_FILINGS` | mínimo de filings XBRL para que `C-S03-004` pase |

**5. Output esperado.**
```
[hash_out] hashout-v2 = <64 hex>
--- conciliacion ---
filings_expected = <n>
filings_ok       = <n> ({'PARSED_XBRL': n, ...})
filings_rejected = 0
gate             = PASS -> <verdict>
```

**7. Validaciones.**

| check | bloqueante | qué verifica |
|---|---|---|
| `C-S03-010` (F13, primero de la lista) | sí | **guarda del replace-all**: el borrado del `parsed.*` previo del CIK solo procede (`decidir_reemplazo`) si el lote nuevo reproduce **todos** los filings que ya tenían hechos Y trae hechos nuevos. Si no, `FAIL` — cero `DELETE`/`INSERT`, el `parsed.*` anterior queda intacto y el checkpoint no se actualiza |
| `C-S03-001` | sí | conciliación filings `expected → parsed/rejected` |
| `C-S03-002` | sí | inputs íntegros: todos los archivos de S02 legibles y con SHA correcto |
| `C-S03-003` | sí | provenance completa y `facts_total > 0` |
| `C-S03-004` | sí | al menos `--min-xbrl` filings parseados como XBRL, ninguno vacío |
| `C-S03-005` | sí | la era pre-XBRL queda declarada explícitamente, no inferida |
| `C-S03-006` | sí | integridad referencial: 0 contextos y 0 unidades colgantes |
| `C-S03-007` | sí | comparación contra `companyfacts` cubre todo el índice |
| `C-S03-008` | sí | outputs escritos y no vacíos |
| `C-S03-009` | **no** | performance; puede quedar en `WARN` sin bloquear |

**7.1 · Por qué existe `C-S03-010` (defecto real, ya corregido — F13).**
Antes, el `DELETE` del `parsed.*` previo corría **siempre**, incondicional,
y el `commit()` quedaba persistido **antes** de evaluar los gates. Un lote
nuevo vacío (S02 sin filings, o filings sin hechos) borraba la provenance
previa igual, y los gates bloqueaban la corrida **sin restaurar nada**:
`derived.fact` quedaba vigente citando `fact_id` ya borrados
(`NO_DANGLING > 0`, medido 90.398 en el incidente de KO). La corrección
(`decidir_reemplazo`, función pura, testeada en
`tests/test_f13_no_reemplazo.py`) reordenó el flujo: **todo el parse ocurre
primero, en memoria**; el `DELETE`+`INSERT` del reemplazo ocurre en la
**misma transacción**, y **solo** si el lote nuevo es fiel al anterior. Si
no, no se toca nada: la corrida BLOCKea con `C-S03-010`, pero el `parsed.*`
anterior —y todo lo que `derived.fact` cita de él— sigue intacto.

**8. Logs.** `report` con `hash_in`, `hash_out` (spec `hashout-v2`),
`rejected_by_reason`, `nulls_by_reason`, y la clave `reemplazo` (F13:
`ejecutado`/`filings_previos_con_hechos`/`hechos_nuevos`/`faltantes`) en
`S03_VALIDATION.json` y en el resumen.

**9. Fallback automático.** **Checkpoint hit.** Antes de parsear calcula
`input_hash = sha256(entity_id + cada (raw_path, sha256))` y busca en
`engine.checkpoints` por `(stage_id, input_hash, code_version,
contract_version)`. Si lo encuentra, **reutiliza y sale con `0` sin
reprocesar**. Ver `appendices/CHECKPOINT_CATALOG.md`. **Distinto** de la
guarda de no-reemplazo (`C-S03-010`): el checkpoint hit evita reprocesar
un input idéntico; la guarda de no-reemplazo actúa cuando sí se reprocesa
pero el resultado no es fiel al `parsed.*` previo.

**11-13. Errores.** `C-S03-002` (SHA mismatch de un input), `C-S03-006`
(colgantes), `C-S03-010` (lote nuevo no reproduce filings previos con
hechos — F13), `ENG-TIMEOUT-001` (subir `ENGINE_STATEMENT_TIMEOUT_MS`, F-028).

**14. PASS** ⇒ exit `0`. **15. PASS_WITH_WARNINGS**: `C-S03-009` en `WARN` con
el resto en `PASS` sigue dando gate `PASS` — el `WARN` queda en el `report`.
**16. BLOCK** ⇒ exit `1`.

**20. Reanudar.** Volver a correrlo: si el input no cambió, el checkpoint lo
resuelve en segundos.

**21. Idempotencia.** **Demostrada y automática.** Mismo input + mismo
`code_version` + mismo `contract_version` ⇒ checkpoint hit ⇒ 0 escrituras.
`hash_out` es `hashout-v2`, sensible al **contenido** e insensible al orden
(ver `engine/hashout.py`): dos corridas con el mismo contenido declaran el
mismo `hash_out`. La v1 no lo lograba — contaba filas, y tres corridas con
contenido distinto declararon el mismo hash (F-029).

---

## S04 · Normalize

**1. Objetivo.** Llevar `parsed.facts` a `derived.fact` resolviendo unidades,
desempates y pertenencia.

**2. Precondiciones.** S03 con `PASS` y su `hash_out` recalculable.

**3. Comando exacto.**
```bash
ENGINE_DB_NAME=catalaxia ENGINE_DB_PORT=5433 python scripts/engine/s04_normalize.py
```

| argumento | default | qué hace |
|---|---|---|
| `--dry-run` | off | **no escribe**; corre sólo los checks previos |

**Primera vez, siempre en dry-run:**
```bash
ENGINE_DB_NAME=catalaxia ENGINE_DB_PORT=5433 python scripts/engine/s04_normalize.py --dry-run
```

**5. Output esperado.**
```
conflictos registrados: <n>
GATE PASS
   [PASS] C-S04-001  spec=hashout-v2 declarado=<h> recalculado=<h> corrida=OK
   ...
hash_in  <64 hex>
hash_out <64 hex>
checkpoint <run_id[:16]>-s04
```

**7. Validaciones.**

| check | bloqueante | qué verifica |
|---|---|---|
| `C-S04-001` | sí | el `hash_out` declarado por S03 se **recalcula** e igual, y la corrida está `OK` |
| `C-S04-002` | sí | ningún CIK con hechos de más de una corrida |
| `C-S04-003` | sí | 0 contextos contradictorios |
| `C-S04-004` | sí | todo CIK resuelve a una entidad en `identity_v1` |
| `C-S04-005`…`009` | sí | checks posteriores a la escritura; **en `--dry-run` quedan en `SKIP`** |

**6. Cómo interpretar el dry-run.** Ver `SKIP` en `C-S04-005..009` es lo
esperado, no una falla. Es el único lugar del sistema donde `SKIP` existe.

**11-13. Errores.** `C-S04-001` (S03 no reproducible ⇒ **no sigas, reparseá**),
`C-S04-002` (mezcla de corridas), `C-S04-004` (identidad faltante).
Exit `2` = precondición no cumplida; exit `1` = gate `BLOCK`; exit `0` = `PASS`.

**20. Reanudar.** Correr `--dry-run`, revisar, correr sin él.

**21. Idempotencia.** Escribe con versionado temporal (`valid_to`), así que una
segunda corrida no duplica hechos vigentes. **Verificalo así:**

```bash
docker exec catalaxia-engine-dev psql -U catalaxia -d catalaxia -c \
  "SELECT count(*) total, count(*) FILTER (WHERE valid_to IS NULL) vigentes, \
          md5(string_agg(fact_key,'|' ORDER BY fact_key)) digest \
     FROM derived.fact WHERE valid_to IS NULL"
```
El `digest` debe ser idéntico antes y después.

---

## Ratios

**1. Objetivo.** Calcular y persistir ratios en `derived.ratio`.

**3. Comando exacto.** Los únicos argumentos que acepta son:

| argumento | default | qué hace |
|---|---|---|
| `--persist` | off | **sin esta bandera no escribe nada** |
| `--cik` | todos | limita a un emisor |

No tiene `--dry-run`: el modo seguro es simplemente **omitir `--persist`**.
Primero, para ver qué haría:
```bash
ENGINE_DB_NAME=catalaxia ENGINE_DB_PORT=5433 python scripts/engine/ratio_engine.py --cik 0000904851
```
Y después:
```bash
ENGINE_DB_NAME=catalaxia ENGINE_DB_PORT=5433 python scripts/engine/ratio_engine.py --cik 0000904851 --persist
```

**5. Output esperado.** Una línea por `(cik, canonical_id)` con el valor y el
estado (`CALCULADO` / `NOT_CALCULABLE`).

**7. Qué ratios calcula realmente.** En `derived.ratio` sólo existen cuatro
`canonical_id`: **`eps`, `pe`, `pb`, `ev_sales`**. Tres de los cuatro necesitan
precio de mercado. Los 14 ratios contables definidos en
`scripts/engine/ratio_defs.py` **no los persiste ninguna etapa**: sólo los
consume `scripts/engine/matriz_producto.py`, que es un script de análisis.
Ver `05_RATIO_REFERENCE.md` y `SOFTWARE GAP SG-03`.

**11-13.** Exit `2` = precondición; `1` = falla; `0` = ok.

**21. Idempotencia.** Persiste con `valid_to`; verificá con el mismo patrón de
S04 sobre `derived.ratio` y `ratio_key`.

---

## C10 → C11 → C12 — validación, certificación, publicación (F12)

Tramo agregado por F12/ADR `docs/review/26_F12_ARCHITECTURE_DECISION.md`.
Ninguno de los tres estaba documentado en versiones previas de este
runbook. Guía completa, ejemplo real y `--help` de cada script en
`docs/runbooks/GUIA_OPERATIVA_PIPELINE_ENGINE.md` — esta sección resume lo
operativo.

### C10 · `scripts/engine/c10_evaluate.py` — VALIDACIÓN, solo lectura

**Objetivo.** Evaluar invariantes sobre lo que S00-S04 (y opcionalmente
Market/CNV) ya escribieron. **No escribe ninguna tabla.**

```bash
python -m scripts.engine.c10_evaluate --sec-runs <RUN_ID> --ciks 0000904851 \
  --tickers YPFD --scope sec --json-out outputs/e2e/c10.json
```

`--scope sec` (default de `run_e2e_certified.py`) corre 5 invariantes:
`SEC_GATES`, `IDENTITY`, `PROVENANCE`, `NO_DANGLING`, `NO_ORPHAN_ENTITY`.
`NO_DANGLING` es el invariante que originó F13: cuenta `derived.fact`
vigente cuyo `source_fact_ids` no resuelve en `parsed.facts` — `0` es
`PASS`, `>0` es `BLOCK`. Veredicto final: `PASS`/`WARN`/`BLOCK`, en el JSON
de `--json-out`.

### C11 · `scripts/engine/c11_certificar.py` — CERTIFICACIÓN

**Objetivo.** Emitir un acta única y determinista por `run_id`, leyendo la
evidencia ya producida (`engine.runs`/`stage_runs`/`checkpoints`). Nunca
calcula, nunca publica; **única escritura**: `engine.certifications`.

```bash
python -m scripts.engine.c11_certificar --run-id <RUN_ID> --json-output outputs/e2e
```

Regla determinista: cualquier `gate_status=BLOCK` en alguna etapa →
`NEGADA`; alguna `WARNING` → `CERTIFICADA_CON_OBSERVACIONES`; todo `PASS`
→ `CERTIFICADA`. El `cert_hash` (sha256, sin timestamps) es reproducible:
misma evidencia → mismo hash. Re-ejecutar es idempotente
(`ON CONFLICT (run_id) DO NOTHING` — el acta nunca se reescribe). **Hoy es
informativa**: no bloquea la API ni C12 por sí sola; es `publisher.py`
quien exige `CERTIFICADA` antes de publicar.

### C12 · `scripts/engine/publisher.py` — PUBLICACIÓN a staging

**Objetivo.** Publicar un snapshot a `staging.<target>` con swap atómico,
**sin cutover a producción**; exige `C10 PASS` + `C11 CERTIFICADA`.

```bash
python -m scripts.engine.publisher --source derived.fact --target engine_facts \
  --run-id <RUN_ID> --pk fact_key --dry-run
```

Sin `--dry-run` hace el swap real dentro de `staging.<target>__new__*` →
`staging.<target>`, registrando la publicación en `staging._publications`
(`run_id`, `input_hash`, `content_hash`, `c10_pass`, `certification_id`).
`--rollback` revierte al snapshot anterior. Requiere el schema `staging`
(migración `036_staging_schema.sql`) y que el rol de aplicación
(`catalaxia_engine`) tenga `USAGE, CREATE` sobre él.

**Cuándo C12 queda `SKIPPED` — no es una falla.** El destino de negocio
final (a qué tabla productiva se publica) es una decisión de integración
que la ADR de F12 dejó explícitamente diferida. Si no se define
`ENGINE_PUBLISH_SOURCE` (o `--publish-source` en `run_e2e_certified.py`),
la cadena declara `C12 SKIPPED` con `exit 0` — la validación y
certificación S00→C11 quedan igual de completas y verificadas.

### La cadena completa, en un solo comando

```bash
python -m scripts.engine.run_e2e_certified --mode FAST --cik 0000904851 --tickers YPFD
```

Encadena S00→S04 (`e2e_orchestrator.py`) → `ratio_engine.py --persist` →
C10 → C11 → C12, con **abort-on-fail** (si un eslabón no da
PASS/CERTIFICADA/ALLOW, la cadena se detiene ahí) y un **advisory lock de
PostgreSQL** (`pg_try_advisory_lock`, clave determinista) que impide que
dos corridas de la cadena se superpongan, incluso entre contenedores/hosts
que comparten la base. Exit codes: `0` cadena completa (o C12 `SKIPPED`
declarado), `1` cadena abortada (BLOCK/NEGADA/publish fallido), `2` error
de uso o `EXT-010`, `3` lock ocupado. Deja un report JSON por corrida en
`outputs/e2e/e2e_<timestamp>.json` con el detalle de cada paso.

**Contenedor (F12).** El mismo entrypoint es el `ENTRYPOINT` de
`Dockerfile.engine` (imagen `catalaxia-engine`, lockfile propio
`requirements-engine.txt` — sin `fastapi`/`yfinance`). Se lanza por
corrida, no como servicio permanente:
```bash
docker compose --profile run-e2e run --rm engine              # FAST
docker compose --profile run-e2e run --rm engine --mode FULL
```
En el VPS (`scripts/setup_vps.sh`), cron: `30 6 * * 1-5` FAST y
`0 7 1 1,4,7,10 *` FULL. Certificado (ejecución real verificada
independientemente): `run_id=836dfbd566a440c3ba8eff392f6649f9`, C10 `PASS`
(`NO_DANGLING=0`), C11 `CERTIFICADA`
(`cert_hash=ef207c88828c1e835a7d6284ef53c4289aad51858f79b894815d5da1c620b629`),
C12 `SKIPPED` declarado. Ver `docs/review/27_F12_CERTIFICATION.md`.

---

## Verificación final del E2E

```bash
docker exec catalaxia-engine-dev psql -U catalaxia -d catalaxia -c \
  "SELECT stage_id, state, gate_status FROM engine.stage_runs \
    WHERE run_id IN (SELECT run_id FROM engine.runs ORDER BY started_at DESC LIMIT 6) \
    ORDER BY started_at"
```

Y volvé a correr `01_COMMON_OPERATIONS.md` §1.4 y §1.5: producción sin
esquemas nuevos, `screener.db` con la misma huella.

Comparación contra los valores esperados: `appendices/GOLDEN_RUNS.md`.
