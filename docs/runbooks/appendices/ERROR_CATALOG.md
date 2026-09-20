# CATÁLOGO DE ERRORES

Todo lo que hay acá sale del código. Los `C-*` son **IDs de check reales**,
declarados en los scripts de etapa. Los `SEC-*`, `CNV-*` y `ENG-*` **no existen
en el código**: son etiquetas que este runbook introduce para poder referirse a
condiciones que el software produce pero no nombra. Están marcados como tales.

> **`SOFTWARE GAP SG-07`.** El sistema no tiene un vocabulario de códigos de
> error operativos. Los `F-0NN` que aparecen en comentarios (`F-009`, `F-025`,
> `F-051`…) son identificadores de **defectos históricos**, no condiciones de
> runtime. `EXT-010` es la única etiqueta que el código emite en un mensaje.

---

## 1 · Checks de etapa (existen en el código)

Un check en `FAIL` con `blocking: True` produce gate `BLOCK` y exit `1`.

### S00 — bootstrap

| ID | bloq. | síntoma | causa | detección | recuperación manual | acción del operador |
|---|---|---|---|---|---|---|
| `C-S00-001` | sí | `schema_migrations registra 001_s00_bootstrap` en FAIL | las migraciones no se aplicaron | consulta a `engine.schema_migrations` | verificar `ENGINE_ADMIN_DB_USER` y su permiso de DDL | corregir credenciales admin y re-correr |
| `C-S00-002` | sí | `target no es produccion (port=…)` en FAIL | `ENGINE_DB_PORT=5432` | comparación de puerto | — | **ABORTAR.** `RECOVERY_PROCEDURES.md` caso 20 |

### S01 — identity

| ID | bloq. | qué verifica | acción si falla |
|---|---|---|---|
| `C-S01-001` | sí | identidad canónica única por `(tipo, valor, mercado)` | hay duplicados: resolverlos antes de seguir; no los borres a ciegas |
| `C-S01-002` | sí | discrepancias fuera de identidad usable y en revisión manual | abrir/actualizar las revisiones pendientes |
| `C-S01-003` | sí | `EXT-NEW-002`: `entities` sin columnas de ticker | esquema desactualizado: revisar migraciones |
| `C-S01-004` | sí, solo si `--cik` es YPF | la entidad YPF `CIK:0000904851` existe, `legal_name` exacto, 5 identificadores activos (CIK/TICKER-US/YF-yahoo/TICKER-BYMA/YF-.BA) y una review abierta del conflicto legacy CIK 1104659 | sembrar el catálogo SEC. **Ojo:** este check está clavado al Golden Run (`SG-05`) |
| `C-S01-GEN` | sí, solo si `--cik` ≠ YPF | el CIK pedido existe en `identity.entities` (vía genérica F4/multiemisor, sin el set de checks de YPF) | sembrar/enlazar la identidad de ese CIK |

### S02 — fetch

| ID | bloq. | qué verifica | acción si falla |
|---|---|---|---|
| `C-S02-001` | sí | conciliación plan→descargas; ninguna crítica fallida | ver `download_log` filtrando `critical=true AND http_status>=400`; reintentar más tarde |
| `C-S02-002` | sí | RAW persistido: se re-lee disco y se compara SHA256 | archivo corrupto o borrado: eliminarlo y re-correr S02 |
| `C-S02-003` | sí | vinculación entidad→cik→fuente→accession | S01 incompleto: volver a S01 |
| `C-S02-004` | sí | cortesía SEC: intervalo mínimo ≥ `delay*0.5` | bajaste el delay o corriste dos S02 en paralelo. **No corras dos fetch simultáneos** |
| `C-S02-005` | sí | S01 consumido en exclusiva, sin esquema legacy | defecto de código, no de datos: reportarlo |

### S03 — parse

| ID | bloq. | qué verifica | acción si falla |
|---|---|---|---|
| `C-S03-010` (F13, primero de la lista) | sí | guarda del replace-all: `decidir_reemplazo` — el lote nuevo reproduce todos los filings previos con hechos Y trae hechos nuevos | el lote es incompleto/vacío respecto del anterior: **no es un error de datos**, es el comportamiento correcto para no perder provenance. Conseguir el lote completo (todos los filings con hechos) y re-correr S03 |
| `C-S03-001` | sí | conciliación `expected → parsed/rejected` | leer `rejected_by_reason` del report |
| `C-S03-002` | sí | inputs íntegros (SHA de cada crudo de S02) | **SHA mismatch**: borrar el crudo y re-correr S02 |
| `C-S03-003` | sí | provenance completa y `facts_total > 0` | parser no produjo hechos: revisar `outcomes` |
| `C-S03-004` | sí | ≥ `--min-xbrl` filings XBRL, ninguno vacío | emisor con pocos XBRL: bajar `--min-xbrl` **sólo si sabés por qué** |
| `C-S03-005` | sí | era pre-XBRL declarada explícitamente | filings sin clasificar: revisar `parsed.pre_xbrl_filings` |
| `C-S03-006` | sí | 0 contextos y 0 unidades colgantes | integridad referencial rota: no continuar a S04 |
| `C-S03-007` | sí | comparación contra `companyfacts` cubre el índice | falta descargar `companyfacts` en S02 |
| `C-S03-008` | sí | outputs escritos y no vacíos | escritura falló: revisar permisos y espacio |
| `C-S03-009` | **no** | performance | queda `WARN`; no bloquea |

### S04 — normalize

| ID | bloq. | qué verifica | acción si falla |
|---|---|---|---|
| `C-S04-001` | sí | el `hash_out` de S03 se recalcula igual y la corrida está `OK` | **S03 no es reproducible: volvé a S03.** No fuerces S04 |
| `C-S04-002` | sí | ningún CIK con hechos de más de una corrida | mezcla de corridas: limpiar antes de normalizar |
| `C-S04-003` | sí | 0 contextos contradictorios | volver a S03 |
| `C-S04-004` | sí | todo CIK resuelve a entidad en `identity_v1` | volver a S01 |
| `C-S04-005`…`009` | sí | checks post-escritura | en `--dry-run` aparecen como `SKIP`: es lo esperado |

### C3 — CNV fetch

| ID | bloq. | qué verifica | acción si falla |
|---|---|---|---|
| `C-C3-001` | sí | conciliación plan→manifiesto | revisar `cnv_download_log` de la corrida |
| `C-C3-002` | sí | integridad del RAW re-leyendo disco | borrar el artefacto y re-correr |
| `C-C3-003` | sí | provenance entidad→cuit→url | identidad incompleta |
| `C-C3-004` | sí | 0 artefactos aceptados que no validen contenido | página de error guardada como si fuera válida |
| `C-C3-005` | sí | rate limiting por host | no correr dos C3 en paralelo |
| `C-C3-006` | sí | idempotencia (`--rerun`) | ver `FALLBACK_MATRIX.md` |
| `C-C3-007` | sí | identidad no inventada | no cerrar reviews a mano para destrabar |
| `C-C3-008` | **no** | doble hash CNV vs calculado | **hoy nunca se ejercita** (`SG-02`): `hash_cnv` es NULL en las 4.005 filas |
| `C-C3-009` | sí | 0 duplicados `(kind, key, sha)` | |
| `C-C3-010` | sí | 100 % de las descargas del emisor pedido | scope contaminado: no mezclar emisores en una corrida |

### C10/C11/C12 — validación, certificación, publicación (F12)

C10 no usa el prefijo `C-*`: sus invariantes se llaman por nombre.

| invariante (scope `sec`) | bloq. | qué verifica | acción si falla |
|---|---|---|---|
| `SEC_GATES` | sí | los `run_id` pasados tienen sus etapas con gate registrado | corrida incompleta: volver a correr la etapa que falta |
| `IDENTITY` | sí | los CIK resuelven en identidad | volver a S01 |
| `PROVENANCE` | sí | `derived.fact` cita `parsed.facts` existentes del mismo CIK/accession/qname | volver a S03/S04 |
| `NO_DANGLING` | sí | `derived.fact` vigente no cita `fact_id` inexistentes (`count=0`) | **BLOCKER real, ya corregido en la causa por F13**: si aparece, es un residuo histórico o una vía distinta de S03; no forzar, investigar |
| `NO_ORPHAN_ENTITY` | sí | toda entidad citada existe en identidad | volver a S01 |

C11 no tiene checks bloqueantes propios: certifica según el `gate_status`
de cada etapa que C10/las etapas ya escribieron. `NEGADA` no bloquea nada
por sí sola (hoy informativa); `publisher.py` es quien exige `CERTIFICADA`.

---

## 2 · Condiciones sin código de error (etiquetas de este runbook)

### Guard de producción

| etiqueta | origen | síntoma | recuperación |
|---|---|---|---|
| **`EXT-010`** | **existe en el código** (`engine/config.py`) | `RuntimeError: EXT-010: el engine apunta al puerto de produccion (5432)` | quitar `ENGINE_ALLOW_PROD`, poner `ENGINE_DB_PORT=5433` |

Es el **único** código de error que el software emite por su nombre.

### Descarga SEC — *etiquetas del runbook, no del código*

| etiqueta | síntoma | reintento automático | condición terminal |
|---|---|---|---|
| `SEC-DL-429` | HTTP 429 | **sí**: 3 intentos, backoff `[2, 5, 10]` s | agotados los 3, la fila queda con su `http_status` |
| `SEC-DL-5XX` | HTTP 500/502/503/504 | **sí**, mismo mecanismo | ídem |
| `SEC-DL-OTHER` | cualquier otro status | **no** — `if resp.status_code not in (429,500,502,503,504)` corta | queda registrado, sin reintento |
| `SEC-DL-TIMEOUT` | timeout | `connect=10 s`, `read=180 s` | tras `max_attempts` |
| `SEC-DL-CRIT` | artefacto crítico falla | no | `SystemExit("BLOCK: submissions crítica falló: …")` |

Todo esto queda en `fetch_raw.download_log` con `http_status` y `sha256`.

### Extracción CNV legacy — *etiquetas del runbook*

| etiqueta | síntoma | causa real | detección | recuperación |
|---|---|---|---|---|
| **`CNV-EX-001`** | el documento no produce ninguna fila | `period_end(html)` devuelve `None`: el HTML no expone `FechaCierre` ni `FechaHasta` | **ninguna**: sólo incrementa `err` y llama `_mark_done(guid)` | **ninguna automática.** El GUID queda marcado como hecho y no se reintenta |
| **`CNV-EX-002`** | ídem | `len(datos) < 5`: se encontraron menos de 5 conceptos del mapa | ídem | ídem |
| **`CNV-EX-003`** | filas con `tipo_balance` vacío | el HTML no expone `TipoBalance` | la fila **se escribe igual**, con perímetro vacío | el adaptador canónico las excluye y las censa |
| **`CNV-COV-001`** | un documento descargado no tiene filas **y tampoco error** | `job5` procesa un rango `filas[r0:r1]` acotado por `--max`; la corrida terminó antes de alcanzarlo | **ninguna.** No hay reconciliación entre descargados, procesados (`data/log_job5_v2_done.txt`) y con datos | volver a correr `job5` con un rango que lo cubra — pero **hay que descubrirlo primero a mano** |

**`CNV-COV-001` es el problema más caro del sistema.** No es un error: es
trabajo que nunca se hizo y que nada reporta. Medido sobre METR:

```
  whitelist EEFF   286
  en disco         286
  PROCESSED_OK      56
  PENDING            4   EEFF genuinos nunca intentados  -> CNV-COV-001
  FAILED           226   descargas sin documento         -> CNV-DL-001
```

**`CNV-DL-001` (nuevo).** 226 de los 286 archivos son la página de espera del
visor de la CNV: ~77 KB de UI, **cero códigos con valor**, sin `FechaCierre` ni
`TipoBalance`. La descarga se guardó igual, con nombre de EEFF y sin ninguna
validación de contenido. No hay reintento ni registro.

El CONSOLIDADO de METR al 30/09/2024 —el caso obligatorio de
`GOLDEN_RUNS.md` §3— es uno de esos 230: se descargó, parsea perfectamente
(38 conceptos, período, perímetro y escala correctos, ningún guard se
activaría) y simplemente **nunca le tocó el turno**. `SG-04`.

### Base de datos — *etiquetas del runbook*

| etiqueta | síntoma | causa | recuperación |
|---|---|---|---|
| `ENG-DB-001` | `permission denied for database catalaxia` | la app corre como `catalaxia_engine`, que no es superusuario (F-025) | el DDL va por `get_admin_engine`; revisar `ENGINE_ADMIN_DB_USER` |
| `ENG-DB-002` | `connection refused` | contenedor caído | `RECOVERY_PROCEDURES.md` caso 1 |
| `ENG-TIMEOUT-001` | `canceling statement due to statement timeout` | estadísticas del planner viejas tras un replace masivo (F-028) | subir `ENGINE_STATEMENT_TIMEOUT_MS` |
| `ENG-MODE-001` | `ValueError: ENGINE_MODE invalido` | valor fuera de `FAST`/`FULL`/`AUDIT` | corregir la variable |

### Contrato de reporte (`engine/report.py`)

Estas tres excepciones aparecen **al cerrar** una etapa, no durante:

| mensaje | qué significa | qué hacer |
|---|---|---|
| `Reporte incompleto, campos obligatorios ausentes: [...]` | falta un campo del contrato | defecto de código de la etapa |
| `Reporte sin checks: 'termino sin excepcion' nunca es PASS` | la etapa no declaró ningún check | ídem |
| `Conciliacion invalida: expected(N) != parsed(M) + rejected(K)` | las cuentas no cierran | **no es cosmético**: hay filas perdidas o contadas dos veces |

---

## 3 · Lo que NO existe

| mecanismo | estado |
|---|---|
| Cuarentena | **no existe**. 0 coincidencias de `quarant`/`cuarentena` en `engine/`, `scripts/engine/` y `migrations/`. `SG-08` |
| Códigos de error operativos | **no existen** como vocabulario. `SG-07` |
| Reintento tras fallo de parseo | **no existe**: `_mark_done` lo impide |
| Log de rechazos por documento en CNV legacy | **no existe**. `SG-04` |
| Bandera `--resume` | **no existe** en ningún script del engine |
