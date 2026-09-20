# MANUAL_COMMAND_CATALOG — catálogo operativo de comandos

**Fecha:** 2026-09-04 · **Insumo de Paso 4, no el manual.** No se escribió
`CATALAXIA_OPERATIONS_MANUAL.md`. No se modificó código.

**Método:** cada comando de este catálogo se verificó leyendo directamente
el `argparse` (o el parseo manual de `sys.argv`, donde no hay `argparse`) y
el `if __name__ == "__main__"` de su script — no se copió de
`docs/runbooks/appendices/COMMAND_REFERENCE.md` ni de ningún otro documento.
Donde ese apéndice ya decía lo mismo, se cita como confirmación adicional,
no como fuente. Los 10 códigos de gate de S02, los 9 de S03, los 9 de S04 y
los 10 de C3 se grepearon uno por uno contra el archivo fuente (§8).

**No se inventó ningún comando.** Donde un script no tiene argumentos, dice
"ninguno" — no se completó con lo que "debería" aceptar. Donde una
categoría del encargo (PROVENANCE, CERTIFICATION) no tiene un script propio,
se dice explícitamente y se cita cómo se hace hoy en su lugar (§7).

---

## 0. Resultado — qué es y qué no es un entry point

Revisados: `scripts/engine/` (53 archivos `.py`), `scripts/market/` (11),
`scripts/tickets/cnv/jobs/` y `scripts/tickets/screener/` (los dos citados
por los runbooks), `scripts/dolares/` (4, no documentados en ningún
runbook — encontrados por búsqueda directa, no por referencia previa).

**20 entry points confirmados.** Un entry point, en este catálogo, es un
script que (a) tiene un bloque `if __name__ == "__main__":` que ejecuta una
operación completa — no una librería que otro script importa — y (b) un
operador lo correría directamente para operar el sistema, no para
investigar un defecto puntual ya cerrado.

| categoría | comandos |
|---|---:|
| SEC | 5 |
| CNV | 3 |
| MARKET | 6 |
| RATIO | 1 |
| UTILITY | 5 |
| PROVENANCE | 0 — sin script propio, ver §7 |
| VALIDATION | 0 — sin script propio fuera de MARKET, ver §7 |
| CERTIFICATION | 0 — sin script propio fuera de MARKET, ver §7 |

---

## 1. SEC

### 1.1 · `s00_smoke.py`

| campo | valor |
|---|---|
| **Comando exacto** | `ENGINE_DB_NAME=catalaxia ENGINE_DB_PORT=5433 python scripts/engine/s00_smoke.py` |
| **Script** | `scripts/engine/s00_smoke.py` |
| **Argumentos** | ninguno — no llama `argparse` |
| **Obligatorios** | ninguno |
| **Opcionales** | ninguno |
| **Variables de entorno** | `ENGINE_DB_HOST` (def. `127.0.0.1`) · `ENGINE_DB_NAME` (def. `catalaxia`) · `ENGINE_DB_PORT` (def. `5433`) · `ENGINE_DB_USER` (def. `catalaxia_engine`) · `ENGINE_DB_PASSWORD`/`POSTGRES_PASSWORD` · `ENGINE_MODE` (def. `FAST`; `FAST`\|`FULL`\|`AUDIT`) · `ENGINE_ALLOW_PROD` · `ENGINE_ADMIN_DB_USER`/`ENGINE_ADMIN_DB_PASSWORD` (def. `catalaxia`) — leídas por `engine/config.py::load_settings()`, común a todo SEC/RATIO |
| **Base de datos** | PostgreSQL, esquemas `engine.*` (crea `engine.runs`, `engine.stage_runs`, `engine.checkpoints`, `engine.schema_migrations` si no existen) y, si `market_instruments`/`market_raw_runs` ya existen, aplica también las migraciones de `migrations/market/` |
| **Puerto** | `5433` (dev). `EXT-010` en `engine/config.py::load_settings()`: si `ENGINE_DB_PORT=5432` y `ENGINE_ALLOW_PROD` no es `"1"`, `RuntimeError` **antes de conectar** |
| **Qué modifica** | aplica `migrations/engine/*.sql` (+ `migrations/market/*.sql` condicional, ver `MARKET_REQUIERE` en `engine/db.py`) vía `engine/db.py::apply_migrations()`, con el usuario **admin** (no `catalaxia_engine`, que no tiene DDL) |
| **Qué genera** | una fila en `engine.runs`; transiciones en `engine.stage_runs`; `report` JSON con `checks` |
| **Resultado esperado** | `rows_expected = 2`, `rows_rejected = 0`, `gate = PASS` |
| **Exit code** | `0` si `gate is GateStatus.PASS`; `1` en cualquier otro caso — `return 0 if gate is GateStatus.PASS else 1` |
| **Gate asociado** | `C-S00-001` (bloqueante: `001_s00_bootstrap` registrada en `engine.schema_migrations`) · `C-S00-002` (bloqueante: destino ≠ producción) |
| **Clasificación** | **SEC** (primera etapa registrada del pipeline SEC; también deja aplicadas las migraciones de Market, que ningún otro script de Market aplica por sí solo salvo `m19_apply_schema.py` para el DDL propiamente dicho) |

### 1.2 · `s01_identity.py`

| campo | valor |
|---|---|
| **Comando exacto** | `ENGINE_DB_NAME=catalaxia ENGINE_DB_PORT=5433 python scripts/engine/s01_identity.py` |
| **Script** | `scripts/engine/s01_identity.py` |
| **Argumentos** | ninguno |
| **Obligatorios** | ninguno |
| **Opcionales** | ninguno |
| **Variables de entorno** | las de `engine/config.py` (ver 1.1) |
| **Base de datos** | PostgreSQL, esquema `identity_v1.*` |
| **Puerto** | `5433` (dev), mismo guard `EXT-010` |
| **Qué modifica** | siembra/resuelve entidades e identificadores en `identity_v1` desde el catálogo `company_tickers` de SEC en disco (`engine/identity.py::load_sec_catalog`); `upsert_entity`/`add_identifier` son idempotentes (no duplican) |
| **Qué genera** | fila en `engine.runs`; `report` con `identifiers nuevos=<n>` |
| **Resultado esperado** | `checks_expected = 4`, `checks_pass = 4`, `checks_rejected = 0`, `gate = PASS` |
| **Exit code** | `0` si `gate is not GateStatus.BLOCK` (es decir, también con `WARNING`); `1` solo si `BLOCK` — `return 0 if gate is not GateStatus.BLOCK else 1` |
| **Gate asociado** | `C-S01-001` (identidad canónica única por tipo/valor/mercado) · `C-S01-002` (discrepancias fuera de identidad usable) · `C-S01-003` (`entities` sin columnas de ticker) · `C-S01-004` (**clavado a YPF**: exige que la entidad `CIK:0000904851` exista con el `legal_name` esperado — falla en una base donde YPF nunca se sembró, aunque el resto esté sano) |
| **Clasificación** | **SEC** |

### 1.3 · `s02_fetch_ypf.py`

| campo | valor |
|---|---|
| **Comando exacto** | `ENGINE_DB_NAME=catalaxia ENGINE_DB_PORT=5433 python scripts/engine/s02_fetch_ypf.py --cik 0000904851` |
| **Script** | `scripts/engine/s02_fetch_ypf.py` |
| **Argumentos** | `--cik` · `--forms` · `--max-filings` |
| **Obligatorios** | ninguno (los tres tienen default) |
| **Opcionales** | `--cik` (def. `GOLDEN_CIK = "0000904851"`, se normaliza con `.zfill(10)`) · `--forms` (def. `FORMS = ("20-F", "20-F/A")`, coma-separado) · `--max-filings` (def. `MAX_FILINGS = 0` = sin tope, `type=int`) |
| **Variables de entorno** | las de `engine/config.py` |
| **Base de datos** | PostgreSQL, `fetch_raw.download_log` |
| **Puerto** | `5433` (dev), `EXT-010` |
| **Qué modifica** | descarga artefactos de EDGAR a `data/raw/engine/`; una fila por descarga en `fetch_raw.download_log` (`accession_number`, `request_kind`, `raw_path`, `http_status`, `sha256`, `bytes`, `critical`) |
| **Qué genera** | fila en `engine.runs`; `report` con conciliación `rows_expected/rows_ok/rows_failed` |
| **Resultado esperado** | `rows_failed = 0`, `gate = PASS` |
| **Exit code** | `0` si `gate is GateStatus.PASS`; `1` en cualquier otro caso |
| **Gate asociado** | `C-S02-001` (conciliación plan→descargas) · `C-S02-002` (integridad RAW, SHA256 re-leído de disco) · `C-S02-003` (vinculación entidad→cik→fuente→accession) · `C-S02-004` (cortesía SEC: intervalo mínimo ≥ `delay*0.5`) · `C-S02-005` (S01 consumido en exclusiva) |
| **Clasificación** | **SEC** |

### 1.4 · `s03_parse_ypf.py`

| campo | valor |
|---|---|
| **Comando exacto** | `ENGINE_DB_NAME=catalaxia ENGINE_DB_PORT=5433 python scripts/engine/s03_parse_ypf.py --cik 0000904851` |
| **Script** | `scripts/engine/s03_parse_ypf.py` |
| **Argumentos** | `--cik` · `--min-xbrl` |
| **Obligatorios** | ninguno |
| **Opcionales** | `--cik` (def. `GOLDEN_CIK = "0000904851"`, `.zfill(10)`) · `--min-xbrl` (def. `MIN_XBRL_FILINGS = 9`, `type=int`) |
| **Variables de entorno** | las de `engine/config.py` |
| **Base de datos** | PostgreSQL, `parsed.facts`/`parsed.contexts`/`parsed.units`/`parsed.concepts`, `engine.checkpoints` |
| **Puerto** | `5433` (dev), `EXT-010` |
| **Qué modifica** | parsea el RAW XBRL/iXBRL de S02 y escribe `parsed.*`; borrado con **alcance por CIK** en las cinco tablas de `PARSED_TABLES` (post-F-054: ya no borra la base entera ni reinicia la secuencia de `fact_id`) |
| **Qué genera** | checkpoint en `engine.checkpoints` (`input_hash` = sha256 de `entity_id` + cada `(raw_path, sha256)`); `hash_out` (`hashout-v2`) impreso y en el `report` |
| **Resultado esperado** | `[hash_out] hashout-v2 = <64 hex>`, `filings_rejected = 0`, `gate = PASS` |
| **Exit code** | `0` si `gate is GateStatus.PASS`; `1` en otro caso — `return 0 if gate is GateStatus.PASS else 1` |
| **Gate asociado** | `C-S03-001` (conciliación filings) · `C-S03-002` (inputs íntegros, SHA de S02) · `C-S03-003` (provenance completa, `facts_total > 0`) · `C-S03-004` (≥ `--min-xbrl` filings XBRL parseados) · `C-S03-005` (era pre-XBRL declarada explícita) · `C-S03-006` (0 contextos/unidades colgantes) · `C-S03-007` (comparación contra `companyfacts`) · `C-S03-008` (outputs no vacíos) · `C-S03-009` (performance, **no bloqueante** — puede quedar `WARN` sin bajar el gate) |
| **Idempotencia** | checkpoint hit ⇒ sale con `0` sin reprocesar; mismo `hash_out` en una segunda corrida con el mismo input |
| **Clasificación** | **SEC** |

### 1.5 · `s04_normalize.py`

| campo | valor |
|---|---|
| **Comando exacto** | `ENGINE_DB_NAME=catalaxia ENGINE_DB_PORT=5433 python scripts/engine/s04_normalize.py --dry-run` (primero) y luego sin la bandera |
| **Script** | `scripts/engine/s04_normalize.py` |
| **Argumentos** | `--dry-run` |
| **Obligatorios** | ninguno |
| **Opcionales** | `--dry-run` (`action="store_true"`, def. `off`: no escribe, corre el gate previo) |
| **Variables de entorno** | las de `engine/config.py` |
| **Base de datos** | PostgreSQL, `derived.fact` |
| **Puerto** | `5433` (dev). `EXT-010` verificado **con mensaje propio**: `"EXT-010: S04 no corre contra 5432."` |
| **Qué modifica** | lleva `parsed.facts` a `derived.fact` resolviendo unidad, desempate y pertenencia; versionado temporal (`valid_to`), no duplica hechos vigentes en una segunda corrida |
| **Qué genera** | `hash_in`/`hash_out` impresos; checkpoint `<run_id[:16]>-s04` si `gate = PASS` y no es `--dry-run` |
| **Resultado esperado** | en `--dry-run`: `C-S04-005..009` en `SKIP` (esperado, no una falla); sin `--dry-run`: `hash_in`/`hash_out` impresos, `gate = PASS` |
| **Exit code** | `2` si `settings.is_prod` (precondición: guard de producción) **o** si hay corridas huérfanas (`F-009`, `engine.corridas_huerfanas()` — este caso puntual devuelve `1`, no `2`, ver detalle); `1` si `gate is GateStatus.BLOCK`; `0` si `gate is GateStatus.PASS` |
| **Gate asociado** | `C-S04-001` (recalcula el `hash_out` de S03 e iguala) · `C-S04-002` (ningún CIK con hechos de más de una corrida) · `C-S04-003` (0 contextos contradictorios) · `C-S04-004` (todo CIK resuelve a una entidad) · `C-S04-005..009` (posteriores a la escritura; `SKIP` en `--dry-run`) |
| **Clasificación** | **SEC** |

---

## 2. RATIO

### 2.1 · `ratio_engine.py`

| campo | valor |
|---|---|
| **Comando exacto** | `ENGINE_DB_NAME=catalaxia ENGINE_DB_PORT=5433 python scripts/engine/ratio_engine.py --cik 0000904851` (sin persistir) y `... --cik 0000904851 --persist` (para escribir) |
| **Script** | `scripts/engine/ratio_engine.py` |
| **Argumentos** | `--persist` · `--cik` |
| **Obligatorios** | ninguno |
| **Opcionales** | `--persist` (`action="store_true"`, def. `off`: **sin esta bandera no escribe nada**) · `--cik` (def. ninguno = todos los CIK de `derived.fact`, vía `ciks_del_universo()`) |
| **Variables de entorno** | las de `engine/config.py` |
| **Base de datos** | PostgreSQL, lee `derived.fact`, escribe `derived.ratio` (solo con `--persist`) |
| **Puerto** | `5433` (dev). Guard propio: `if s.is_prod: return 2` |
| **Qué modifica** | con `--persist`: inserta en `derived.ratio` un `ratio_key` por `(cik, canonical_id)`, versionado por `valid_to` |
| **Qué genera** | consola: una línea por `(CIK, entidad, ratio, ventana, período, estado, valor, moneda)` para cada uno de los `SPECS` soportados; con `--persist`, resumen de acciones por `(cik, canonical_id)` |
| **Resultado esperado** | sin `--persist`: `"(sin --persist: no se escribio nada)"`, exit `0`; con `--persist`: `"persistido en derived.ratio · run <run_id>"` |
| **Exit code** | `2` si `s.is_prod` (guard EXT-010) · `1` si `violaciones_pertenencia(c) > 0` (**F-061**: hay hechos cuya provenance no pertenece a su emisor — el motor se niega a calcular) · `0` en cualquier otro caso, con o sin `--persist` |
| **Gate asociado** | ninguno de los `C-S0N-NNN`; el único chequeo propio es el de **pertenencia F-061** (`violaciones_pertenencia`), que corre **antes** de calcular cualquier ratio, no después |
| **Nota** | solo cuatro `canonical_id` existen hoy en `derived.ratio`: `eps`, `pe`, `pb`, `ev_sales`. Los 14 ratios contables de `ratio_defs.RATIOS` **no los persiste esta ni ninguna otra etapa** — los consume `matriz_producto.py`, que no es un entry point de operación (ver §6) |
| **Clasificación** | **RATIO** |

---

## 3. CNV

### 3.1 · `c3_cnv_fetch.py`

| campo | valor |
|---|---|
| **Comando exacto** | `ENGINE_DB_NAME=catalaxia ENGINE_DB_PORT=5433 python scripts/engine/c3_cnv_fetch.py --cuit 30657863676` |
| **Script** | `scripts/engine/c3_cnv_fetch.py` |
| **Argumentos** | `--cuit` · `--cik` · `--scope` · `--desde-anio` · `--max-visores` · `--adjuntos-presentaciones` · `--adjunto-max-mb` · `--rerun` · `--delay-visor` |
| **Obligatorios** | **exactamente uno** de `--cuit` / `--cik` — si se pasan los dos, o ninguno, `raise SystemExit("indicar exactamente uno: --cuit o --cik")` |
| **Opcionales** | `--scope` (def. `"FINANCIERO"`, `choices=sorted(SCOPES)`) · `--desde-anio` (`type=int`, def. ninguno) · `--max-visores` (`type=int`, def. ninguno) · `--adjuntos-presentaciones` (`type=int`, def. `0`) · `--adjunto-max-mb` (`type=float`, def. `30.0`) · `--rerun` (`action="store_true"`, pasada de verificación de idempotencia) · `--delay-visor` (`type=float`, def. `DEFAULT_DELAYS["aif2.cnv.gov.ar"]`) |
| **Variables de entorno** | las de `engine/config.py` |
| **Base de datos** | PostgreSQL, `fetch_raw.cnv_download_log`; exige que la identidad del CUIT/CIK exista y esté `VERIFIED` en `identity_v1` **antes** de abrir corrida (corta con `SystemExit` si no) |
| **Puerto** | `5433` (dev), `EXT-010` |
| **Qué modifica** | descarga artefactos públicos de CNV; una fila por artefacto en `fetch_raw.cnv_download_log` (`artifact_kind`, `artifact_key`, `endpoint`, `http_status`, `bytes`, `hash_cnv`, `hash_cnv_match`, `raw_path`, `duplicate_of`, `attempts`, `elapsed_ms`) |
| **Qué genera** | `checkpoint=<id>`; `outputs/docs/fase_cnv/C3_CNV_VALIDATION.json` |
| **Resultado esperado** | `gate = PASS  checkpoint=<id>` |
| **Exit code** | `0` si `gate is not GateStatus.BLOCK` (también con `WARNING`); `1` si `BLOCK` — `return 0 if gate is not GateStatus.BLOCK else 1` |
| **Gate asociado** | `C-C3-001` (conciliación plan→manifiesto) · `C-C3-002` (integridad RAW, re-lectura de disco) · `C-C3-003` (provenance entidad→cuit→url) · `C-C3-004` (0 artefactos aceptados sin validar contenido) · `C-C3-005` (rate limiting por host) · `C-C3-006` (idempotencia, evaluado con `--rerun`) · `C-C3-007` (identidad no inventada) · `C-C3-008` (doble hash — **no bloqueante**; verificado: `hash_cnv` es NULL en el 100% de las filas actuales, así que este check da `PASS` sin comparar nada) · `C-C3-009` (0 duplicados `(kind, key, sha)`) · `C-C3-010` (100% de descargas pertenecen al emisor pedido) |
| **Límite verificado** | `artifact_kind` en el ledger solo toma `VISOR` y `EMPRESA_PAGE` — **este tramo no descarga estados financieros** |
| **Clasificación** | **CNV** |

### 3.2 · `job5_v2_extract_eeff.py`

| campo | valor |
|---|---|
| **Comando exacto** | `python scripts/tickets/cnv/jobs/job5_v2_extract_eeff.py` (sin argumentos: procesa la whitelist completa) |
| **Script** | `scripts/tickets/cnv/jobs/job5_v2_extract_eeff.py` |
| **Argumentos** | **no usa `argparse`** — parsea `sys.argv[1:]` a mano (`args = sys.argv[1:]`), sin `--help` |
| **Obligatorios** | ninguno |
| **Opcionales (verificados en el código, no en `--help`)** | `--rango R0 R1` (def. `0, 10**9` = todo) · `--max N` (def. `10**9`; tope de **descargas HTTP**, no de documentos procesados) · `--sleep S` (def. `0.3`) · `--whitelist RUTA` (def. `scripts/tickets/cnv/datos/whitelist_eeff.csv`, o `whitelist_eeff_codigos.csv` si se pasa `--codigos`) · `--cuits RUTA.csv` (def. todos; filtra por los CUIT del CSV) · `--codigos` (bandera; usa la whitelist de códigos) · `--offline` (bandera; no descarga, solo re-procesa HTML ya en disco) |
| **Variables de entorno** | `SCREENER_DB` (def. `screener.db`; permite apuntar a una copia de prueba) |
| **Base de datos** | **SQLite** `data/<SCREENER_DB>` — no PostgreSQL, no engine, no puerto |
| **Puerto** | N/A (SQLite es un archivo, no un servicio de red) |
| **Qué modifica** | crea/escribe `cnv_estados_v2` en `screener.db`; descarga HTML a `scripts/tickets/cnv/eeff/eeff_html/`; agrega GUIDs a `data/log_job5_v2_done.txt` |
| **Qué genera** | ningún `run_id`, ningún `report`, ningún gate — no participa de `engine.runs` |
| **Resultado esperado** | `Listo: ok=<n> skip=<n> cache=<n> err=<n> \| dp=<n> \| fetch=<n>/<n>` — `err` es un contador agregado, no dice qué documento falló |
| **Exit code** | **verificado: siempre `0`.** `main()` no tiene `return`; `if __name__: main()` no envuelve en `SystemExit`. Un documento que falla (`except Exception`) incrementa `err`, se marca `_mark_done(guid)` (no se reintenta) y la corrida sigue — **el exit code no refleja ningún fallo** |
| **Gate asociado** | ninguno — código sin checks estructurados |
| **Advertencia verificada** | `--rango`/`--max` acotan la corrida sin dejar rastro de lo no procesado; una segunda corrida sin `--cuits` reprocesa desde el inicio de la whitelist, no desde donde quedó |
| **Clasificación** | **CNV** |

### 3.3 · `s0_normalizar_cnv.py`

| campo | valor |
|---|---|
| **Comando exacto** | `python scripts/tickets/screener/s0_normalizar_cnv.py` |
| **Script** | `scripts/tickets/screener/s0_normalizar_cnv.py` |
| **Argumentos** | ninguno — sin `argparse`, sin parseo de `sys.argv` |
| **Obligatorios** | ninguno |
| **Opcionales** | ninguno |
| **Variables de entorno** | `SCREENER_DB` (def. `screener.db`) |
| **Base de datos** | **SQLite** `data/<SCREENER_DB>` |
| **Puerto** | N/A |
| **Qué modifica** | `DROP`/`CREATE` de `mapa_entidades` y `cnv_estados_norm` (idempotente por diseño: recrea sus tablas de salida en cada corrida) a partir de `cnv_estados` + `empresas.csv` + `empresas_subset.csv` |
| **Qué genera** | ninguna evidencia en disco fuera de la propia base — solo salida de consola |
| **Resultado esperado** | `PASS: GATE PASADO: 0 huerfanas, <n> entidades mapeadas, <n> filas normalizadas` |
| **Exit code** | **verificado: siempre `0`.** No hay una sola llamada a `sys.exit()`/`exit()` en todo el archivo. Si el gate interno falla (`orphan_old`/`orphan_new` > 0) imprime `"FAIL: GATE FALLADO"` **y el proceso igual termina con exit `0`** — un chequeo de exit code no detecta este fallo |
| **Gate asociado** | uno interno, no estructurado como `C-SNN-NNN`: huérfanas (`orphan_old`/`orphan_new`) = 0. Sin código, sin `report`, sin registro en `engine.*` |
| **Clasificación** | **CNV** |

---

## 4. MARKET

> **Advertencia que aplica a los seis:** Market usa variables de entorno
> **distintas** a las de `engine/config.py` (`DB_HOST`/`DB_PORT`/`DB_NAME`,
> no `ENGINE_DB_*`), definidas en `scripts/market/market_db.py`. Su
> default de puerto es **`5432` — PRODUCCIÓN** (`destino()`:
> `e.get("DB_PORT", PUERTO_PRODUCCION)`, con `PUERTO_PRODUCCION = "5432"`).
> Un comando de Market corrido sin `DB_PORT=5433` explícito **lee** contra
> producción por defecto (con rol `catalaxia_market_ro`, solo `SELECT`) y
> **no puede escribir** en 5432 sin además `MARKET_ALLOW_PROD_WRITE=1`
> (guard `F-001`, `MarketProdWriteBlocked`). Esto es lo opuesto al default
> de `engine/config.py`, que asume 5433 salvo que se pida prod
> explícitamente. **No asumir que fijar `ENGINE_DB_PORT` protege también
> a Market: son variables distintas.**

### 4.1 · `m19_apply_schema.py`

| campo | valor |
|---|---|
| **Comando exacto** | `DB_PORT=5433 python scripts/market/m19_apply_schema.py` |
| **Script** | `scripts/market/m19_apply_schema.py` |
| **Argumentos** | ninguno |
| **Obligatorios / opcionales** | ninguno |
| **Variables de entorno** | `DB_HOST` (def. `localhost`) · `DB_PORT` (def. `5432`) · `DB_NAME` (def. `catalaxia`) · `MARKET_DB_USER` (def. `catalaxia`) · `DB_PASSWORD`/`POSTGRES_PASSWORD` (def. `catalaxia`) · `MARKET_ALLOW_PROD_WRITE` |
| **Base de datos** | PostgreSQL, `public.market_*` (DDL de `market_schema.sql`) |
| **Puerto** | por defecto `5432` — **fijar `DB_PORT=5433` explícitamente para no apuntar a producción** |
| **Qué modifica** | ejecuta `market_schema.sql` completo (idempotente por diseño del SQL); pide conexión de **escritura** vía `market_db.connect(None, write=True)` |
| **Qué genera** | listado en consola de las tablas `market_*` presentes tras aplicar el schema |
| **Resultado esperado** | `market_* en PG (<n>):` seguido de la lista |
| **Exit code** | no captura excepciones ni retorna código propio — `0` si no hay excepción, traceback + código de error del intérprete si la falla (p. ej. `MarketProdWriteBlocked`) |
| **Gate asociado** | ninguno |
| **Clasificación** | **MARKET** |

### 4.2 · `m1_symbol_mapping.py`

| campo | valor |
|---|---|
| **Comando exacto** | `DB_PORT=5433 python scripts/market/m1_symbol_mapping.py` |
| **Script** | `scripts/market/m1_symbol_mapping.py` |
| **Argumentos** | ninguno |
| **Obligatorios / opcionales** | ninguno |
| **Variables de entorno** | las de `market_db.py` (ver advertencia arriba) |
| **Base de datos** | lee **SQLite** `data/screener.db` (`dim_entity`, `dim_instrument`); escribe **PostgreSQL** `market_instruments` y `market_symbol_mappings` (`ON CONFLICT (instrument_id) DO UPDATE`) |
| **Puerto** | por defecto `5432` (mismo default de `market_db.py`) |
| **Qué modifica** | deriva `instrument_type`/`ticker_yahoo`/`venue_ticker` por instrumento (regla determinista: **CERO mappings inventados** — si no se puede derivar, `UNMAPPED`); detecta colisiones de símbolo Yahoo entre instrumentos (`CONFLICT`) |
| **Qué genera** | consola: conteo por estado (`MAPPED`/`UNMAPPED`/`CONFLICT`), por tipo, lista de divergencias `venue_ticker != ticker_canonico`, lista de `UNMAPPED`/`CONFLICT` |
| **Resultado esperado** | `instrumentos procesados : <n>` + los conteos por estado |
| **Exit code** | igual que `m19`: sin captura propia, `0` si no hay excepción |
| **Gate asociado** | ninguno estructurado |
| **Clasificación** | **MARKET** |

### 4.3 · `m2_fetch_engine.py`

| campo | valor |
|---|---|
| **Comando exacto** | `DB_PORT=5433 python scripts/market/m2_fetch_engine.py --limit 10 --json-out /tmp/market.json` |
| **Script** | `scripts/market/m2_fetch_engine.py` |
| **Argumentos** | `--instruments` · `--limit` · `--stage` · `--no-snapshot` · `--json-out` |
| **Obligatorios** | ninguno |
| **Opcionales** | `--instruments` (lista de `ticker_yahoo` separados por coma; def. universo `MAPPED` completo) · `--limit` (`type=int`, def. ninguno) · `--stage` (def. `"batch"`) · `--no-snapshot` (`action="store_true"`) · `--json-out` (ruta del reporte) |
| **Variables de entorno** | las de `market_db.py` |
| **Base de datos** | PostgreSQL, escribe `market_price_daily` y `market_raw_runs`/`market_raw_files` (`pg_conn(write=True)`) |
| **Puerto** | por defecto `5432` |
| **Qué modifica** | descarga precios de Yahoo Finance por instrumento (`YahooSource`); registra corrida en `market_raw_runs` |
| **Qué genera** | `--json-out`: reporte con un `RunReport` (`asdict`) por instrumento |
| **Resultado esperado** | una línea por instrumento (`estado`, ruedas, rango de fechas, `sha`), y al final `listo: <n> ok / <n> con problema` |
| **Exit code** | `1` si algún `RunReport.status in ("FAILED", "QUARANTINED")`; `0` si todos ok |
| **Gate asociado** | ninguno con código `C-NN`; gates internos por `RunReport.gates`, impresos como `GATE <nombre> INVALID: <detalle>` cuando corresponde |
| **Clasificación** | **MARKET** |

### 4.4 · `m4_quality.py`

| campo | valor |
|---|---|
| **Comando exacto** | `DB_PORT=5433 python scripts/market/m4_quality.py` |
| **Script** | `scripts/market/m4_quality.py` |
| **Argumentos** | `--instruments` · `--gap-habiles` · `--staleness-dias` · `--json-out` · `--dbname` |
| **Obligatorios** | ninguno |
| **Opcionales** | `--instruments` (`instrument_id` separados por coma; def. todos los de `market_price_daily`) · `--gap-habiles` (`type=int`, def. `12`) · `--staleness-dias` (`type=int`, def. `7`) · `--json-out` · `--dbname` |
| **Variables de entorno** | las de `market_db.py` |
| **Base de datos** | PostgreSQL, escribe `market_data_quality` (`pg_conn(write=True)`) |
| **Puerto** | por defecto `5432` |
| **Qué modifica** | corre una batería de gates de calidad (globales + por instrumento) y persiste cada resultado |
| **Qué genera** | `--json-out`: `{run_id, veredicto, resumen, gates}` |
| **Resultado esperado** | `gates ejecutados=<n> -> {...}`, `VEREDICTO: <PASS\|WARNING\|FAIL>` |
| **Exit code** | `1` si `veredicto == "FAIL"`; `0` en otro caso |
| **Gate asociado** | ninguno con código `C-NN` propio; el veredicto agregado (`PASS`/`WARNING`/`FAIL`) es el gate de esta corrida |
| **Clasificación** | **MARKET** — función operativa: validación de calidad de datos |

### 4.5 · `m5_golden_case.py`

| campo | valor |
|---|---|
| **Comando exacto** | `DB_PORT=5433 python scripts/market/m5_golden_case.py --instruments <tickers>` |
| **Script** | `scripts/market/m5_golden_case.py` |
| **Argumentos** | `--instruments` · `--out` · `--dbname` · `--sin-gates` |
| **Obligatorios** | `--instruments` (`required=True`; tickers Yahoo o `instrument_id`, separados por coma) |
| **Opcionales** | `--out` (def. `OUT_DEFAULT`) · `--dbname` · `--sin-gates` (`action="store_true"`: no re-ejecuta la batería, usa la última registrada) |
| **Variables de entorno** | las de `market_db.py` |
| **Base de datos** | PostgreSQL, lee precios/calidad; escribe `market_data_quality` vía `quality.Bateria` (salvo `--sin-gates`) |
| **Puerto** | por defecto `5432` |
| **Qué modifica** | corre (o reutiliza) la batería de gates; no modifica `market_price_daily` |
| **Qué genera** | en `--out`: `MARKET_GOLDEN_CASE.md`, `market_fingerprint_report.md`, `market_idempotency_report.md`, `market_validation_report.md`, `market_provenance.md`, CSVs, `market_golden_case.xlsx`, `MANIFEST.json` (con SHA256 por archivo), `CHECKPOINT.json` (`checkpoint_id`, `state_digest`, `veredicto`) |
| **Resultado esperado** | `veredicto : <PASS\|WARNING\|FAIL>`, `checkpoint_id`, `state_digest`, conteo de gates |
| **Exit code** | `2` si ningún instrumento pedido se resuelve (`insts` vacío); `1` si `veredicto == "FAIL"`; `0` en otro caso |
| **Gate asociado** | mismo mecanismo que `m4_quality.py` (`quality.Bateria`), agregado en un `veredicto` único |
| **Clasificación** | **MARKET** — función operativa: certificación/checkpoint de un caso de referencia |

### 4.6 · `m6_scale.py` — **no documentado en `COMMAND_REFERENCE.md`, confirmado por lectura directa**

| campo | valor |
|---|---|
| **Comando exacto** | `DB_PORT=5433 python scripts/market/m6_scale.py --stage <tag> [--limit N] [--resume] [--dry-run]` |
| **Script** | `scripts/market/m6_scale.py` |
| **Argumentos** | `--stage` · `--instruments` · `--limit` · `--resume` · `--sleep` · `--max-retries` · `--retry-sleep` · `--no-snapshot` · `--dry-run` · `--audit-raw-orphans` · `--json-out` |
| **Obligatorios** | `--stage` (`required=True`; tag de la corrida, también clave de resume) |
| **Opcionales** | `--instruments` (subconjunto; def. universo `MAPPED` completo) · `--limit` (`type=int`) · `--resume` (`action="store_true"`: saltea instrumentos ya `SUCCESS` para este `--stage`, vía `market_raw_runs`) · `--sleep` (`type=float`, def. `2.0`) · `--max-retries` (`type=int`, def. `1`) · `--retry-sleep` (`type=float`, def. `5.0`) · `--no-snapshot` (`action="store_true"`) · `--dry-run` (`action="store_true"`: solo lista, no llama a la fuente) · `--audit-raw-orphans` (`action="store_true"`: **solo lectura**, reporta RAW en disco sin fila en `market_raw_files` y termina) · `--json-out` (def. `outputs/docs/fase_market/scale/<stage>.json`) |
| **Variables de entorno** | las de `market_db.py` |
| **Base de datos** | PostgreSQL; orquesta `m2_fetch_engine.run_instrument()` sobre el universo — mismas tablas que `m2` |
| **Puerto** | por defecto `5432`. **`--dry-run` y `--audit-raw-orphans` piden conexión de solo lectura** (`necesita_escritura = not (args.dry_run or args.audit_raw_orphans)`) y por eso pueden correr contra producción sin `MARKET_ALLOW_PROD_WRITE` |
| **Qué modifica** | escala `m2_fetch_engine` a cientos de instrumentos con resume por checkpoint (reusa `market_raw_runs.status='SUCCESS'`, no inventa un estado nuevo); reintenta solo los `FAILED` del propio batch; `QUARANTINED` **nunca** se reintenta solo |
| **Qué genera** | reporte JSON agregado bajo `outputs/docs/fase_market/scale/` con detalle por `RunReport` |
| **Resultado esperado** | `universo MAPPED: <n> \| a procesar ahora: <n> \| ...`; al final, resumen por estado y `duracion: <s>s` |
| **Exit code** | `1` si hay instrumentos `FAILED`/`QUARANTINED` al cierre, o si `--audit-raw-orphans` encuentra huérfanos; `0` en otro caso (incluidos `--dry-run` y "nada para procesar") |
| **Gate asociado** | ninguno con código `C-NN`; hereda los gates de `run_instrument()` (los mismos que `m2_fetch_engine.py`) |
| **Clasificación** | **MARKET** |

---

## 5. UTILITY

### 5.1 · Verificación de entorno (no es un script, es el comando obligatorio de preflight)

| campo | valor |
|---|---|
| **Comando exacto** | `python -c "from engine.config import load_settings; s=load_settings(); print(s.describe())"` |
| **Script** | ninguno propio — invoca `engine/config.py::load_settings().describe()` |
| **Argumentos** | N/A |
| **Variables de entorno** | las mismas de `engine/config.py` (§1.1) |
| **Base de datos** | ninguna — solo arma y describe el destino, no conecta |
| **Puerto** | reporta el que resulte de `ENGINE_DB_PORT` (def. `5433`) |
| **Qué modifica** | nada |
| **Qué genera** | una línea: `<user>@<host>:<port>/<db> mode=<mode> prod=<bool>` |
| **Resultado esperado** | `prod=False`, puerto `5433` |
| **Exit code** | `0`, salvo que `load_settings()` levante (`ENGINE_DB_PORT=5432` sin `ENGINE_ALLOW_PROD=1` ⇒ `RuntimeError`, o `ENGINE_MODE` inválido ⇒ `ValueError`) |
| **Gate asociado** | ninguno — es la verificación previa a todos los gates |
| **Clasificación** | **UTILITY** |

### 5.2 · `market_db.py` (auto-diagnóstico)

| campo | valor |
|---|---|
| **Comando exacto** | `DB_PORT=5433 python scripts/market/market_db.py` |
| **Script** | `scripts/market/market_db.py` — es la librería de conexión de Market; su bloque `__main__` es un auto-test |
| **Argumentos** | ninguno |
| **Variables de entorno** | `DB_HOST`/`DB_PORT`/`DB_NAME`/`MARKET_DB_USER_RO`/`MARKET_DB_USER`/`DB_PASSWORD`/`POSTGRES_PASSWORD`/`MARKET_ALLOW_PROD_WRITE` — es la fuente de verdad de estas variables para todo `scripts/market/` |
| **Base de datos** | PostgreSQL — lectura (`SELECT current_user, count(*) FROM market_instruments`) y un intento de apertura en escritura, solo para reportar si está permitida |
| **Puerto** | por defecto `5432` |
| **Qué modifica** | nada (la apertura de escritura no ejecuta ningún `INSERT`/`UPDATE`, solo abre y cierra la conexión) |
| **Qué genera** | consola: destino, resultado de lectura, si la escritura está permitida o bloqueada |
| **Resultado esperado** | `lectura OK como catalaxia_market_ro · <n> instrumentos` y `escritura: BLOQUEADA por la guarda F-001` (si no se puso `MARKET_ALLOW_PROD_WRITE=1` contra 5432) |
| **Exit code** | `0` siempre — las excepciones se capturan e imprimen, no se relanzan |
| **Gate asociado** | ninguno |
| **Clasificación** | **UTILITY** — diagnóstico de conectividad y del guard `F-001`, no mueve datos |

### 5.3 · `fetch_dolarito_historico.py`

| campo | valor |
|---|---|
| **Comando exacto** | `python scripts/dolares/fetch_dolarito_historico.py` |
| **Script** | `scripts/dolares/fetch_dolarito_historico.py` |
| **Argumentos** | ninguno |
| **Variables de entorno** | `SCREENER_DB` (def. `screener.db`) · `DOLARITO_AUTH_CLIENT` (**obligatoria en la práctica**: sin ella, `raise SystemExit("FALTA DOLARITO_AUTH_CLIENT...")`; se lee de la variable de entorno o de una línea `DOLARITO_AUTH_CLIENT=` en `.env`) |
| **Base de datos** | **SQLite** `data/<SCREENER_DB>`, tabla `dolarito_cotizaciones` |
| **Puerto** | N/A (SQLite) |
| **Qué modifica** | `INSERT OR REPLACE` de 10 series (`MEP`, `CCL`, `OFICIAL`, `MAYORISTA`, `BLUE`, `CRIPTO`, `TARJETA`, `BANCOS`, `AHORRO`, `QATAR`) desde `api.dolarito.ar` |
| **Qué genera** | nada en disco fuera de la base — resumen en consola, incluido un extracto de los últimos 5 valores de MEP |
| **Resultado esperado** | `Total insertado: <n> filas -- OK` |
| **Exit code** | `1` en `requests.HTTPError` (capturado explícitamente); `SystemExit` con mensaje si falta el token; `0` en éxito |
| **Gate asociado** | ninguno |
| **Nota** | esta es la única fuente CON autenticación de las tres de `scripts/dolares/` — confirmado por lectura directa (`PRE-04` del inventario, ahora verificado en código, no solo en el docstring) |
| **Clasificación** | **UTILITY** — alimenta el MEP que consumen los ratios de emisores CNV, pero no es parte del pipeline CNV ni de su gate |

### 5.4 · `actualizar_dolares.py`

| campo | valor |
|---|---|
| **Comando exacto** | `python scripts/dolares/actualizar_dolares.py` |
| **Script** | `scripts/dolares/actualizar_dolares.py` |
| **Argumentos** | ninguno — **sin `if __name__`**: el cuerpo corre al nivel de módulo apenas se ejecuta el archivo |
| **Variables de entorno** | `SCREENER_DB` (def. `screener.db`) |
| **Base de datos** | **SQLite** `data/<SCREENER_DB>`, tabla `dolares` |
| **Puerto** | N/A |
| **Qué modifica** | `INSERT OR REPLACE` por `(fecha, tipo)` de tres dólares (CCL, MEP, A3500) vía `_dolar.tres_dolares()`; si detecta el esquema viejo (sin columna `cruce`) hace `DROP TABLE` y recrea |
| **Qué genera** | nada en disco fuera de la base |
| **Resultado esperado** | `[dolares] <fecha>: guardados <n>/3 en tabla \`dolares\` (referencia = MEP)`; advertencia en consola si el MEP primario difiere >2% de su cruce |
| **Exit code** | **no verificable de forma independiente del resultado**: no hay `sys.exit()` en el archivo; termina en `0` incluso si alguna de las tres fuentes no respondió (`info.get('valor') is None` → se omite esa fuente y sigue) |
| **Gate asociado** | ninguno |
| **Nota** | pensado para cron/diario, según su propio docstring |
| **Clasificación** | **UTILITY** |

### 5.5 · `comparar_dolares.py`

| campo | valor |
|---|---|
| **Comando exacto** | `python scripts/dolares/comparar_dolares.py` |
| **Script** | `scripts/dolares/comparar_dolares.py` |
| **Argumentos** | ninguno — igual que `actualizar_dolares.py`, sin `if __name__` |
| **Variables de entorno** | ninguna propia (usa `data/screener.db` fijo, no respeta `SCREENER_DB`) |
| **Base de datos** | **SQLite** `data/screener.db`, **solo lectura** (`SELECT ccl FROM screener ...`) |
| **Puerto** | N/A |
| **Qué modifica** | nada — el propio docstring lo dice: "No escribe nada" |
| **Qué genera** | nada en disco — solo consola |
| **Resultado esperado** | comparación MEP/CCL/A3500 entre fuentes independientes, y el CCL fresco contra el guardado en `screener.db` |
| **Exit code** | `0` siempre (sin manejo de errores propio más allá de un `try/except` silencioso alrededor de la lectura de `screener.db`) |
| **Gate asociado** | ninguno |
| **Clasificación** | **UTILITY** |

---

## 6. Scripts revisados y EXCLUIDOS de este catálogo — con motivo

Ninguno de estos es inventado como "faltante": se abrieron y se descartaron
explícitamente.

| script(s) | por qué se excluye |
|---|---|
| `f014_venue_ticker.py` | librería — define `derivar_venue_ticker()`, la usa `m1_symbol_mapping.py`. Sin `if __name__`, sin uso standalone. |
| `market_core.py`, `market_source.py` | librerías puras — sin `if __name__`, sin `argparse`. |
| `m0_discovery_yahoo.py` | exploración puntual pre-pipeline ("sondeos controlados... antes de construir el pipeline"), código de nivel de módulo sin guard — no es una herramienta operativa recurrente. |
| `c4_cnv_adapter.py` | **no existe en este repositorio.** Confirmado por búsqueda de archivo en todo el árbol, incluidos los worktrees presentes localmente. Vive únicamente en `catalaxia-cnvmig` (rama `feat/cnv-canonical`), no mergeada. El comando de referencia que citan los runbooks (`--cuit <CUIT> --persist`) no es ejecutable hoy. |
| `matriz_producto.py`, `ratio_engine` (comparado), `ratios_inventario.py`, `screener_demo.py` | scripts de **análisis**, no de pipeline — `05_RATIO_REFERENCE.md` ya lo dice explícitamente para `matriz_producto.py`: "es un script de análisis". No participan de `engine.runs`, no tienen gate. |
| `audit_*.py`, `audit_f0NN_*.py`, `f0NN_*.py`, `mut_*.py`, `*_adversario.py`, `*_bench.py`, `*_pilot*.py`, `homologacion_*.py`, `release_*.py`, `demo_*.py`, `screener_auditoria.py`, `e2e_producto.py`, `independent_audit_matrix.py`, `adversario_ratios.py` | auditorías puntuales, bancos de mutación, pilotos históricos y demos — 32 de los 53 archivos `.py` de `scripts/engine/`. `00_START_HERE.md` ya los excluye por patrón; se verificó que el patrón sigue vigente contando los archivos reales del directorio hoy. |
| `mut_f054_f055.py` | **peligroso** — ejecuta `DELETE FROM parsed.facts`. No es un entry point de operación. |
| `reparse_universo.py` | **peligroso** — reprocesa todo el universo. |
| `scripts/pipeline/fix_*.py` | parches históricos de un solo uso. |

---

## 7. Las tres categorías del encargo sin script propio

**`PROVENANCE`, `VALIDATION` (fuera de Market) y `CERTIFICATION` (fuera de
Market) no tienen un entry point dedicado hoy.** No se inventó uno para
llenar la categoría. Lo que existe en su lugar:

| categoría | cómo se hace hoy | evidencia |
|---|---|---|
| **PROVENANCE** | consultas SQL manuales encadenadas (`derived.ratio` → `derived.fact`/`parsed.facts` → `sha256sum` del archivo), documentadas paso a paso en `docs/runbooks/06_PROVENANCE.md` §2-§3. No hay un script `provenance.py` que las automatice. | `06_PROVENANCE.md` completo; confirmado que ningún script de `scripts/engine/` se llama o funciona como recorredor de provenance genérico |
| **VALIDATION** | embebida en el gate de cada etapa (cada script de §1 y §3 corre sus propios checks y termina en `PASS`/`WARNING`/`BLOCK`). El único validador **standalone** es `m4_quality.py` (Market, §4.4) — se clasificó `MARKET` porque solo opera sobre datos de Market, no porque no sea, funcionalmente, un validador. | inventario `GAT-01`, `GAT-02` |
| **CERTIFICATION** | lectura manual de `engine.stage_runs` contra los criterios de `07_CERTIFICATION.md` §2-§3 — **no existe un script único de gate/certificación con exit code agregado** (`GAT-02`, también citado `FAL-06`). El único generador de un artefacto de certificación standalone es `m5_golden_case.py` (Market, §4.5), que sí produce un `CHECKPOINT.json` con `veredicto`. | inventario `GAT-02`; `07_CERTIFICATION.md` §6 ("qué NO habilita a certificar") |

---

## 8. Verificación de los códigos de gate — grep directo contra el código

Para que "verificado contra argparse/código" no sea una afirmación sin
respaldo, cada lista de códigos citada en §1 y §3 se extrajo así (reproducible):

```bash
grep -o "C-S00-[0-9]*" scripts/engine/s00_smoke.py       | sort -u   # 2 códigos
grep -o "C-S01-[0-9]*" scripts/engine/s01_identity.py    | sort -u   # 4 códigos
grep -o "C-S02-[0-9]*" scripts/engine/s02_fetch_ypf.py   | sort -u   # 5 códigos
grep -o "C-S03-[0-9]*" scripts/engine/s03_parse_ypf.py   | sort -u   # 9 códigos
grep -o "C-S04-[0-9]*" scripts/engine/s04_normalize.py   | sort -u   # 9 códigos
grep -o "C-C3-[0-9]*"  scripts/engine/c3_cnv_fetch.py    | sort -u   # 10 códigos
```

Los seis conteos coinciden exactamente con lo que ya afirmaba
`docs/runbooks/appendices/COMMAND_REFERENCE.md` — se cita ese apéndice como
**confirmación cruzada**, no como la fuente de este catálogo.

---

## 9. Hallazgos nuevos de este catálogo (no estaban en `COMMAND_REFERENCE.md`)

1. **`m6_scale.py` no está documentado en ningún runbook**, pese a ser el
   script que escala Market a cientos de instrumentos (según su propio
   docstring, y según la advertencia de `market_db.py`: *"esta guarda
   existe porque `m6_scale.py` escala a 584 instrumentos"*). Tiene 11
   argumentos, incluida una bandera de solo-lectura (`--audit-raw-orphans`)
   sin cobertura previa en ningún documento.
2. **`s0_normalizar_cnv.py` no tiene NINGUNA llamada a `sys.exit()`** — un
   gate fallado (`orphan_old`/`orphan_new` > 0) imprime `FAIL` en pantalla y
   el proceso igual termina en `0`. Cualquier automatización que confíe en
   el exit code de este script para detectar el fallo está equivocada.
3. **`job5_v2_extract_eeff.py` tampoco tiene código de salida propio** —
   confirmado a nivel de código (antes solo estaba dicho a nivel de
   comportamiento en el runbook): `main()` no retorna nada y `if __name__`
   no lo envuelve en `SystemExit`.
4. **Market usa un espacio de variables de entorno distinto al del engine**
   (`DB_HOST`/`DB_PORT`/`DB_NAME` vs. `ENGINE_DB_HOST`/`ENGINE_DB_PORT`/
   `ENGINE_DB_NAME`) **con default de puerto invertido**: el engine por
   defecto apunta a dev (`5433`), Market por defecto apunta a **producción**
   (`5432`). Ningún runbook lo dice en esos términos explícitos.
5. **`scripts/dolares/` (3 scripts operativos + 1 librería) no aparece en
   ningún runbook ni apéndice**, pese a que `fetch_dolarito_historico.py`
   es la única fuente de la serie MEP histórica que consumen los ratios de
   emisores CNV bajo IAS 29.
6. **`ratio_engine.py --persist` ya corre un chequeo de pertenencia
   (`violaciones_pertenencia`) antes de calcular cualquier ratio** y se
   niega (`exit 1`) si encuentra alguno — un guard de integridad que no
   está descrito en `05_RATIO_REFERENCE.md` ni en ningún runbook leído.
