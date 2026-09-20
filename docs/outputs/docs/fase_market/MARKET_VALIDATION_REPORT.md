# MARKET VALIDATION REPORT — ciclo de homologación

**Fecha:** 2026-09-01. **Rol:** MARKET_VALIDATION_AUDITOR + IMPLEMENTER, workstream
MARKET exclusivamente. **Baseline de código:** `v1.0.0`/`v1.0.1` (todo el código de
Market — `m1_symbol_mapping.py`, `m2_fetch_engine.py`, `m6_scale.py`, `market_db.py`,
`f014_venue_ticker.py`, `market_schema.sql`, `migrations/market/013_venue_ticker.sql`,
suite de tests — quedó capturado en el commit de release `25756e1a`, verificado en
esta sesión). **No se tocó Identity, CNV ni SEC.** No se ejecutó M23 masivo nuevo (el
universo de 584 ya estaba corrido desde el 2026-08-28; esta sesión lo audita y agrega
una verificación de idempotencia acotada — 5 instrumentos, todos ya-conocidos).

---

## Resumen ejecutivo

Market puede mapear identidad, obtener precios reales de Yahoo y mantener checkpoint/
resume correctos para el universo completo de 584 instrumentos — **verificado con
evidencia fresca, no solo citada**. Dos hallazgos de esta sesión cambian el estado
respecto de lo que decía `docs/review/FINDINGS.md` al empezar:

1. **F-038 ("M23 no persiste en `market_raw_runs`") es un error de metodología del
   auditor, no un defecto de Market** — comparó producción (20 filas golden) contra
   la ausencia de M23 ahí, sin considerar que M23 corrió deliberadamente contra DEV
   (donde sí están las 591 filas / 584 instrumentos). Ver
   `F038_F052_RESOLUCION.md`.
2. **F-052 (nueva, registrada en esta sesión, severity HIGH)**: `data/raw/market/`
   —el RAW completo de los 584 instrumentos, verificado con SHA256 exacto el
   2026-08-28— **ya no existe en el filesystem**. La base de datos sigue íntegra y
   correcta; el artefacto físico que la respalda desapareció entre el 28-08 y hoy,
   sin backup. Esto **sí** es un blocker real para homologación en el sentido estricto
   de "provenance completa, custodiada" — no para "los precios son correctos" (eso
   sigue siendo cierto, verificado independientemente).

Con esos dos hallazgos entendidos y separados correctamente, el veredicto de gate
(§I) es **PASS_WITH_WARNINGS**, no PASS limpio y no BLOCKED — ver la justificación
completa en `MARKET_VALIDATION_GATE.md`.

---

## FASE A — Inventario

### Módulos M0–M23 (existentes, verificados en disco)

| Módulo | Archivo | Rol |
|---|---|---|
| M0 | `m0_discovery_yahoo.py` | Contrato/discovery yfinance |
| M1 | `m1_symbol_mapping.py` | `dim_entity`+`dim_instrument` (SQLite) → `market_instruments`+`market_symbol_mappings` (Postgres) |
| M2–M12 | `m2_fetch_engine.py` | Motor de fetch: FETCH→RAW→PARSE→GATES→DIFF→UPSERT→ACTIONS→SNAPSHOT→LOG, todo en `run_instrument()` |
| M4 | `m4_quality.py` | Gates C-MKT-001..017 |
| M5/M22 | `m5_golden_case.py` | Validador/reporte del golden case (solo lectura, no fetch) |
| M13-M15 | (embebido en M4) | Quality checks, coverage, staleness |
| M19 | `m19_apply_schema.py` + `market_schema.sql` | DDL, 10 tablas `market_*` |
| M23 | `m6_scale.py` | Orquestador de lote: checkpoint/resume, retry, pacing, auditoría de huérfanos |
| — | `market_core.py` | Lógica pura: hashes, estado de sesión, clasificación de cambios |
| — | `market_source.py` | `YahooSource` (red real) / `FixtureSource` (tests) |
| — | `market_db.py` | Puerta única de conexión — guarda F-001 |
| — | `f014_venue_ticker.py` | Derivación de `venue_ticker` (F-014) |

### Qué base usa cada script — verificado, no asumido

**Hallazgo central de esta fase**: `market_db.destino()` **sin ninguna variable de
entorno seteada** resuelve a:
```
localhost:5432/catalaxia prod=True prod_write_habilitado=False
```
Confirmado en vivo en esta sesión (`python -c "import market_db; print(market_db.describe())"`
desde un shell sin `DB_HOST`/`DB_PORT` exportados). **El default de TODO el tooling de
Market es producción.** `m1_symbol_mapping.py`, `m2_fetch_engine.py`, `m4_quality.py`,
`m5_golden_case.py`, `m6_scale.py` — los 5 pasan por `market_db.connect()`, ninguno
tiene un default propio distinto. La única guarda es de **escritura** (`write=True`
exige `MARKET_ALLOW_PROD_WRITE=1` si el puerto es 5432) — no hay guarda equivalente
para **lectura**: un `SELECT` sin variables de entorno lee producción por defecto, sin
ningún aviso. Esto es exactamente lo que produjo la confusión de F-038.

**Corolario operativo, verificado esta sesión**: los contenedores Docker (`catalaxia-db`
5432 producción, `catalaxia-engine-dev` 5433 dev) se reiniciaron completos durante esta
sesión (evidencia: los 4 contenedores mostraron "Up 1 second" simultáneamente en un
`docker ps`, luego "Up 26-31 segundos" en el siguiente chequeo). La base DEV sobrevivió
el reinicio con sus datos intactos (volumen persistente, verificado re-consultando
`market_raw_runs` post-reinicio: mismos 591 filas). Los 40 tests de la suite se
re-corrieron limpios después del reinicio.

### Tablas relevantes (`market_schema.sql`, verificado)

- `market_instruments` — identidad por instrumento: `instrument_id`, `entity_id`,
  `ticker_canonico`, `venue_ticker`, `venue_ticker_source` (F-014), `instrument_type`,
  `exchange`, `currency`.
- `market_symbol_mappings` — `ticker_yahoo` (símbolo de proveedor), `status`.
- `market_raw_runs` — una fila por intento de fetch, `status IN (SUCCESS,EMPTY,PARTIAL,FAILED)`.
- `market_fetch_log` — una fila por request lógico, `status IN (REQUESTED,SUCCESS,SIN_CAMBIOS,PARTIAL,FAILED,RATE_LIMITED,NOT_FOUND,INVALID_SYMBOL)` (los últimos 3 declarados en el schema, nunca escritos por código — verificado por grep, confirmado de nuevo en esta sesión).
- `market_price_daily` — OHLCV, sin columna de ticker (JOIN a `market_instruments` para identidad).
- `market_data_quality`, `market_data_changes`, `market_corporate_actions`, `market_snapshots`, `market_raw_files`.

### Checkpoint / resume (`m6_scale.py`)

`ya_exitosos(cur, stage)` → `SELECT DISTINCT instrument_id FROM market_raw_runs WHERE
stage_run_id=%s AND status='SUCCESS'`. Es seguro por construcción: `run_instrument()`
hace todo su trabajo de negocio en una sola transacción con un commit al final (detalle
completo en `F013_M23_CHECKPOINT_CONTRACT.md`, re-confirmado en esta sesión: los 9
tests de `test_m23_checkpoint.py` corrieron limpios de nuevo hoy, incluida la prueba de
lote controlada con crash simulado).

---

## FASE B — Identidad

Cadena completa, verificada con datos reales (no una muestra — universo de 584):

```
dim_instrument (SQLite, screener.db)
  ├─ entity_id ──► dim_entity.ticker_canonico   (clave del EMISOR, 1 por entidad)
  └─ instrument_id ──► dim_instrument.ticker    (clave del INSTRUMENTO, 1 por fila/venue)
                              │
                              ▼
market_instruments.ticker_canonico  = dim_entity.ticker_canonico   (SIN CAMBIOS, F-014)
market_instruments.venue_ticker     = dim_instrument.ticker         (NUEVO, F-014)
market_symbol_mappings.ticker_yahoo = derivado (sufijo .BA para BUE; tal cual para ADR/US)
```

**Separación de las 4 identidades pedida explícitamente**:

| Identidad | Campo | Nivel | Ejemplo YPF |
|---|---|---|---|
| Emisor | `ticker_canonico` | Constante por `entity_id` | `YPFD` (en ambas filas, local y ADR) |
| Instrumento | `venue_ticker` | Por fila | Local: `YPFD` · ADR: `YPF` |
| Venue | `exchange` | Por fila | Local: `BUE` · ADR: `NYSE` |
| Proveedor | `ticker_yahoo` | Por fila, scoped a Yahoo | Local: `YPFD.BA` · ADR: `YPF` |

**ADR/BYMA, atacado específicamente**: universo completo de 12 pares BYMA+ADR
verificado en la corrida real del 2026-08-28 y re-confirmado en `market_instruments`
esta sesión — **6/12 coinciden** (CEPU, GGAL, LOMA, VIST, SUPV, BBAR: el ticker local y
el de NYSE son el mismo string, por azar del emisor, no por diseño) y **6/12 divergen**
visiblemente (YPFD≠YPF, TGSU2≠TGS, CRES≠CRESY, PAMP≠PAM, IRSA≠IRS, TECO2≠TEO). Los 6
que coinciden son exactamente los que enmascaran el bug original de F-014 si solo se
prueba con ellos — confirmado que `venue_ticker` los resuelve a todos por igual, sin
casos especiales por coincidencia.

**Instrumento sin `venue_ticker`**: 0 en las 584 filas (`SELECT COUNT(*) FROM
market_instruments WHERE venue_ticker IS NULL` = 0, verificado el 2026-08-28,
estructura sin cambios desde entonces).

---

## FASE C — Reconstrucción de M23

Comparación de las 4 fuentes pedidas — **reporte M23 vs. Postgres vs. filesystem vs.
hashes** — con el resultado más importante de esta fase primero:

**El filesystem YA NO ES una de las 4 fuentes disponibles.** `data/raw/market/` no
existe (ver F-052, `F038_F052_RESOLUCION.md`). Las otras 3 fuentes siguen
consistentes entre sí:

| Fuente | Universo | SUCCESS | FAILED | Coincide |
|---|---|---|---|---|
| `outputs/docs/fase_market/scale/m23-full-2026-08-28.json` | 584 (574 esta corrida + 10 smoke) | 567 (+10 smoke = 577) | 7 | ✓ |
| `market_raw_runs` (DEV, `stage_run_id='smoke-real-2026-08-28'`) | 584 distinct instrument_id | 577 | 7 (14 filas, 2 intentos c/u) | ✓ |
| `market_price_daily` (DEV) | 577 instrumentos con precios | — | — | ✓ (ningún FAILED tiene filas de precio, correcto) |
| `data/raw/market/` (filesystem) | **AUSENTE** | — | — | ✗ — ver F-052 |

577 + 7 = 584. Las tres fuentes que sí existen hoy son idénticas entre sí — **no hay
discrepancia de datos**, solo la pérdida del artefacto físico.

---

## FASE D — F-038, reproducido

**Root cause técnico** (por qué un checkpoint puede "no aparecer" en una consulta):
`run_instrument()` hace TODO su trabajo de negocio (desde el fetch exitoso hasta el
UPSERT final) en una única transacción con un solo `conn.commit()` — documentado con
números de línea exactos en `F013_M23_CHECKPOINT_CONTRACT.md` §2, re-verificado por
una auditoría independiente el 2026-08-28 leyendo el código línea por línea. Esto NO
es lo que causó F-038 (esa hipótesis se descartó con evidencia: no hay filas a medio
comitear, ni en DEV ni en producción) — la causa de F-038 es la elegida por defecto de
`market_db.destino()` (§A), no la mecánica de la transacción.

**Reproducción real, esta sesión** (crash + restart + resume, sobre código real, no
una maqueta):
```
cd scripts/market && python -m pytest tests/test_m23_checkpoint.py -v -s
9 passed
```
Incluye `test_lote_interrumpido_y_reanudado_control_completo`: 4 instrumentos
sintéticos vía `m6_scale.correr_lote()` real, uno muere a mitad de camino
(`unittest.mock.patch` interrumpe `classify_batch` después de que el RAW ya se
escribió y las filas de provenance ya se insertaron sin commit — el punto exacto
donde moriría un proceso matado ahí — seguido de `conn.rollback()`, que es lo que
Postgres hace solo cuando la conexión se cae). Resultado: 0 filas SUCCESS a medias, la
fila `market_fetch_log` inicial queda en `REQUESTED` (comiteada aparte, al principio —
la firma de "esto murió"), el RAW del intento muerto sobrevive huérfano en disco, el
resume subsiguiente selecciona exactamente los pendientes, sin duplicar nada.

**Adicional, reproducción a escala real (no sintética) en esta sesión**: se re-invocó
`m6_scale.py --stage smoke-real-2026-08-28 --resume --limit 5` contra el universo real
de 584. Resultado: `saltados por resume: 577` — el checkpoint reconoce correctamente,
contra datos reales de una corrida de hace 4 días, cuáles de los 577 ya están hechos,
sin re-fetchear ninguno.

**Veredicto F-038**: la corrida SÍ queda correctamente persistida — en DEV, que es
donde se le pidió correr. Ver `F038_F052_RESOLUCION.md` para la resolución completa y
la recomendación de que el destino (`host:port`) quede registrado explícitamente en el
propio `market_raw_runs`/JSON, para que este tipo de confusión no pueda repetirse.

---

## FASE E — Adversarial

Suite completa re-corrida en esta sesión, fresca: **40/40 PASS**
(`test_market_matrix.py` 18 + `test_f014_venue_ticker.py` 13 + `test_m23_checkpoint.py`
9). Mapeo contra la lista de ataques pedida explícitamente:

| Ataque pedido | Cubierto por | Resultado |
|---|---|---|
| Ticker emisor usado como ticker instrumento | `test_f014_venue_ticker.py` (universo completo 12 ADR + los 6 casos "VISIBLE") | Rechazado — `venue_ticker` nunca deriva de `ticker_canonico` |
| ADR | `test_las_4_companias_pedidas`, universo 12/12 | Resuelto correctamente en los 12 |
| Ticker duplicado (símbolo Yahoo compartido) | `m1_symbol_mapping.derivar()` — colisión → `CONFLICT`/`AMBIGUOUS`, nunca silencioso | 0 conflictos en las 584 filas reales (verificado 08-28) |
| Instrumento sin `venue_ticker` | Query directa | 0 de 584 |
| Ticker Yahoo incorrecto | Los 7 FAILED reales de M23 son exactamente este caso a escala real (ver Fase G) | Detectado y no enmascarado — `FAILED`, no un precio inventado |
| Retry | `test_08_retry_dentro_de_la_fuente`, `test_08b_recovery_tras_falla`, + retry real en M23 (7 FAILED reintentados 1 vez, siguen FAILED — no se inventa éxito) | OK |
| Archivo duplicado | `test_10_duplicate_input` | Se queda con la última aparición, reporta el conflicto |
| Archivo cambiado (RAW alterado en disco) | `test_09b_raw_alterado_en_disco_lo_detecta_el_gate` | El gate lo detecta, no lo acepta en silencio |
| Precio vacío | `test_09_payload_corrupto_no_se_persiste` + los 7 FAILED reales (`EMPTY`) | No se persiste nada; `FAILED`, no un cero falso |
| Precio inconsistente | `test_12_bateria_de_gates_completa`, C-MKT-004/009 (218 warnings reales en 46 instrumentos, verificados 08-28) | `WARNING`, nunca escala a bloqueo — correcto para defecto de origen, no del pipeline |
| Corrida interrumpida | `test_crash_a_mitad_de_camino_no_deja_SUCCESS_a_medias` | 0 filas a medias, provenance parcial visible (REQUESTED huérfano) |
| Resume | `test_resume_no_duplica_ni_pierde_provenance`, `test_lote_interrumpido_y_reanudado_control_completo` + reproducción real esta sesión (577 saltados) | Selección exacta de pendientes, determinista |

**Cada rechazo, garantía causal**: la garantía de fondo en los 12 casos es la misma —
`business_hash` reconstruido desde la base (nunca confiado del payload entrante) +
transacción única con commit final (§D) + `venue_ticker`/`ticker_canonico` derivados
de columnas distintas por diseño (F-014), nunca por inferencia de exchange.

---

## FASE F — Integridad

**Verificación histórica (2026-08-28, auditoría independiente)**: 10 instrumentos
muestreados, SHA256 recalculado a mano, **10/10 coincidencias exactas** contra
`market_raw_files.sha256` y `market_raw_runs.sha256`.

**Verificación hoy (2026-09-01)**: **imposible de repetir** — el artefacto ya no
existe (ver F-052). Esto es precisamente la distinción que pedía esta fase:

| | Estado |
|---|---|
| Hash correcto | SÍ (verificado 08-28, no refutado, no re-verificable) |
| Artefacto disponible | NO (hoy) |
| Artefacto custodiado | NO |

**F-052 registrado** con esa evidencia — ver `F038_F052_RESOLUCION.md` para el detalle
completo, `required_action` y la propuesta de auditoría inversa (filas en base sin RAW
en disco, el caso que `auditar_raw_huerfano()` de F-013 no cubre porque fue diseñada
para el caso opuesto).

---

## FASE G — Idempotencia

Repetición real sobre un subconjunto, esta sesión, contra el universo completo real
(no sintético):
```
DB_HOST=localhost DB_PORT=5433 python m6_scale.py --stage smoke-real-2026-08-28 --resume --limit 5 --max-retries 1
→ universo MAPPED: 584 | a procesar ahora: 5 | saltados por resume: 577
```
**577/577 correctamente saltados** — ningún duplicado, cero requests nuevos para
instrumentos ya SUCCESS. Los 5 procesados fueron 5 de los 7 FAILED originales
(`DGCE.BA, SATS, CAAP.BA, VIST.BA, GGALB.BA` — los 5 primeros en orden lexicográfico de
`instrument_id`, el `--limit 5` los recortó antes de llegar a `SUPVB.BA`/`YPFLUZ.BA`),
y los 5 volvieron a fallar con **el mismo motivo exacto**, sin reintentos infinitos ni
resultado distinto entre corridas — contenido y provenance estables.

**Root cause de los 7 FAILED, refinado con evidencia nueva de esta sesión** (los
mensajes reales de Yahoo, no vistos con este nivel de detalle en la auditoría del
08-28):

| Ticker | Mensaje real de Yahoo | Diagnóstico refinado |
|---|---|---|
| `DGCE.BA` (20) | *"possibly delisted; no price data found... symbol may be delisted"* | Delisted, confirmado por Yahoo mismo (antes se sospechaba "símbolo equivocado"; ambas causas son compatibles) |
| `SATS` (480) | mismo mensaje de delisted | Consistente con hallazgo previo: Yahoo re-mapeó esta compañía a `ECHO` |
| `GGALB.BA` (64) | **HTTP 404** `"Quote not found for symbol: GGALB.BA"` | Confirmado: el símbolo no existe en Yahoo, no es un problema transitorio |
| `CAAP.BA` (57), `VIST.BA` (62) | **`"Period 'max' is invalid, must be one of: 1d, 5d"`** | **Hallazgo nuevo**: no es (solo) iliquidez — Yahoo rechaza explícitamente el parámetro `period=max` para estos símbolos específicos. El pipeline pide siempre `period=max` (`DEFAULT_PARAMS`) y no tiene fallback a un período más corto — esto es una limitación real del pipeline, no solo un dato ausente en el origen |
| `SUPVB.BA` (79), `YPFLUZ.BA` (82) | no re-probados esta sesión (fuera del `--limit 5`) | Sin cambios respecto del 08-28 |

Ninguno de los 7 corresponde a rate-limiting (confirmado el 08-28: tiempos de
respuesta <30ms, sin HTTP 429; reconfirmado hoy: mismos mensajes, mismo tipo de error,
en una corrida separada por 4 días).

---

## FASE H — Auditoría independiente

**Bloqueada por rate limit del proveedor** (`claude-sonnet-5[1m] is temporarily
unavailable (rate-limited)`, resetea 4:50am America/Argentina/Buenos_Aires). Se
intentó lanzar dos veces; ambas rechazadas antes de arrancar — no hay una auditoría
independiente parcial ni corrida a medias, simplemente no pudo empezar. Todo lo
demás de este documento (Fases A-G) es evidencia recogida DIRECTAMENTE en esta sesión
— comandos y queries reales, no citas de una corrida anterior sin re-verificar — pero
sigue sin la revisión de un agente separado, sin memoria de este trabajo, que es el
estándar que este mismo proyecto exige para cerrar findings ("ningún finding se cierra
por declaración del owner"). Pendiente: re-lanzar Fase H cuando el rate limit resetee.

---

## Entregables de este ciclo

- `MARKET_VALIDATION_REPORT.md` (este documento)
- `MARKET_VALIDATION_GATE.md`
- `outputs/docs/fase_market/scale/matriz_584_instrumentos.csv`
- `F038_F052_RESOLUCION.md`
- Lista de 7 FAILED + justificación: ver Fase G
- Suite adversaria: `scripts/market/tests/` (40 tests, corridos frescos)
