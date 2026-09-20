# CNV — VALIDACIÓN MULTI-EMPRESA — REPORTE

Rol: CNV_VALIDATION_AUDITOR + IMPLEMENTER. Alcance: exclusivamente el workstream
CNV. Fecha de ejecución: 2026-09-01, baseline de código en el momento de correr
(`git rev-parse HEAD` durante las corridas: `e9d794b8...`, release `v1.0.1`).

**Objetivo**: demostrar que el mecanismo CNV existente — no uno nuevo — obtiene,
identifica, persiste y consume correctamente información de CNV para **múltiples**
emisores argentinos, usando Identity V1 como única fuente de identidad. No es una
prueba basada solo en CEPU.

## Veredicto resumido

Ver `CNV_VALIDATION_GATE.md` para el detalle segmentado. Resumen:

| Segmento | Veredicto |
|---|---|
| IDENTITY_VALIDATION | PASS |
| FETCH_VALIDATION | PASS |
| PERSISTENCE_VALIDATION | PASS_WITH_WARNINGS |
| PROVENANCE_VALIDATION | **PASS_WITH_WARNINGS** (hallazgo real, no bloqueante para lo fetcheado HOY) |
| MULTI_COMPANY_VALIDATION | PASS |
| **CNV_VALIDATION_GATE** | **PASS_WITH_WARNINGS** |

---

## FASE A — Inventario (flujo real)

**Identity → CNV, hoy, es un enlace de código, no manual.** `c3_cnv_fetch.py`
resuelve la identidad llamando a `identity_v1` (no a la tabla legacy
`identity.entities`, no al seed CSV de C1 — esos existieron en versiones
anteriores del script, ya reemplazados): la salida de cada corrida imprime
`binding=IDENTITY_V1_VERIFIED | cuit=<valor> (assertion <id>, <method>)`. Si
identity_v1 no tuviera nada para ese CUIT, el binding sería otro (no se probó
ese camino con una entidad real en esta sesión, pero el código lo contempla —
ver `PROVISIONAL_CUIT` en versiones previas del binding).

**CNV → datos almacenados**: `scripts/engine/c3_cnv_fetch.py` (mecanismo único,
no se escribió ningún scraper paralelo) hace Discovery→Fetch→RAW→Integrity→
Manifest→Provenance→Validation→Checkpoint contra `catalaxia-engine-dev` (5433).
RAW content-addressed en `data/raw/engine/cnv/CUIT{cuit}/{empresa,visor}/`
(gitignored). Metadata en Postgres: `fetch_raw.cnv_presentation` (discovery),
`fetch_raw.cnv_download_log` (una fila por request resuelto), `fetch_raw.cnv_artifact`
(dedupe por sha256), `engine.checkpoints`/`engine.runs`/`engine.stage_runs`
(ciclo de vida). Gate de 10 checks (`C-C3-001`..`010`) definidos inline.

**Identity ↔ CNV, cruce independiente**: `scripts/engine/c3_identity_link.py`
(no reutilizado por el fetcher; corre aparte, solo lee `fetch_raw.cnv_presentation`)
resuelve, para cada CUIT con datos en CNV, si identity_v1 tiene una entidad
autoritativa para ese CUIT (`CUIT_AUTORITATIVO`), o si solo puede atribuirlo por
el CIK embebido en la clave legacy (`CIK_EN_CLAVE_LEGACY`, atribución válida
pero que no demuestra el CUIT), o si no puede resolverlo (`SIN_RESOLVER`, no
inventa nada).

**Contratos/tests existentes**: `docs/architecture/IDENTITY_V1_SCHEMA.md`,
`IDENTITY_ARCHITECTURE_V1.md` (diseño); `tests/test_identity_v1.py`,
`tests/test_engine_cnv.py` (humo, sin red); auditorías previas de un agente
independiente (`docs/review/CNV_REVIEW.md`, `IDENTITY_V1_CERTIFICATION*.md`,
`.claude/state/AUDITOR_STATE.md`) certificaron partes de esta cadena en ciclos
anteriores (identity_v1 hardening, C3 con idempotencia canónica, CNV→Identity
para CEPU). Esta validación es la primera que cubre **más de una empresa** con
ejecución real.

**Hallazgo de contexto, no atribuible a este ciclo**: el CUIT autoritativo de
YPF/CEPU/TGSU2 en identity_v1 tuvo una historia: fabricado como `HUMAN_DECISION`
falsa (F-016, ciclo 5) → retirado por la corrección (ciclo 6, `IDENTITY_V1_CERTIFICATION_R2.md`)
→ re-establecido como assertion `method=REGISTRY`/`resolved_by=proc:gleif_fetch`
condicionada a que GLEIF cruce contra AFIP (RA000009) o IGJ/RNS (RA000010) — un
mecanismo distinto y legítimo (un proceso puede afirmar un hecho de REGISTRY;
solo `HUMAN_DECISION` exige que el firmante sea una persona real). Verificado
en vivo contra la base al momento de esta corrida: la garantía sigue en pie
(revisado el `ck_authoritative_metodo` y el `ck_humano_exige_autor` — ninguno
se viola).

---

## FASE B — Selección de universo (piloto representativo, no masivo)

| # | Empresa | Por qué |
|---|---|---|
| 1 | **CENTRAL PUERTO S.A.** (CUIT 33650305499) | conocida, piloto original, 9.305 presentaciones ya en CNV |
| 2 | **YPF SOCIEDAD ANONIMA** (30546689979) | CUIT autoritativo distinto de CEPU; cero datos CNV previos — mejor caso para "generaliza de verdad" |
| 3 | **TRANSPORTADORA DE GAS DEL SUR S.A.** (30657862068) | ídem YPF; además usado para repetir Fase G (idempotencia) en una segunda entidad |
| 4/6 | **GRUPO FINANCIERO GALICIA S.A.** (30704962807, CANDIDATE) | CUIT de provenance distinta (solo `LEGACY_DIM_ENTITY`, nunca cruzado por GLEIF porque `registeredAt=RA999999` no apunta a AFIP/IGJ) — es a la vez el caso "provenance diferente" y el "caso ambiguo": mismo LEI verificado, cero camino documentado hacia el CUIT |
| 5 | **Macro Bank Inc. / Banco Macro (BMA)** | sin CUIT verificado — F-024 (el legacy tiene un CIK mal cargado en la columna `cuit`) y LEI ambiguo (GLEIF devuelve 2 LEI activos con domicilios que no coinciden del todo, review 17 OPEN) |
| 7 | YPF (doble uso) | dual TICKER `US:YPF` / `BYMA:YPFD` ya modelado en identity_v1 como namespaces distintos; el fetch por CUIT nunca toca esos tickers (scope check `C-C3-010`) |

**Decisión explícita, no forzada**: se **fetchearon** CEPU (ya existente),
YPF y TGSU2 (nuevas). **No se fetchearon** GGAL ni BMA — GGAL porque su CUIT es
legítimo pero solo CANDIDATE (fetchearlo sería defendible pero no era uno de
los 3 mínimos exigidos, y sumar más tráfico contra CNV sin necesidad no aporta
al objetivo de "probar que generaliza"); BMA porque **no tiene ningún CUIT que
usar sin inventarlo** — negarse a fetchear es, en este caso, el comportamiento
correcto y demostrado, no una omisión.

---

## FASE C — Dry run (antes de escribir)

Para YPF y TGSU2, antes de correr el fetcher se determinó — con las queries
de la Fase A, contra la base real, sin escribir nada — qué CUIT se iba a usar,
de qué assertion salía y con qué confianza:

```
YPF    CUIT 30546689979  <- assertion_id 345, method=REGISTRY, confidence=AUTHORITATIVE,
                             status=VERIFIED, source=GLEIF, evidence="AFIP (RA000009)
                             registeredAs=30-54668997-9"
TGSU2  CUIT 30657862068  <- assertion_id 347, method=REGISTRY, confidence=AUTHORITATIVE,
                             status=VERIFIED, source=GLEIF, evidence="IGJ/RNS (RA000010)
                             registeredAs=30-65786206-8"
```

Cantidad esperada: no predecible con precisión antes del discovery (CNV no
publica un conteo previo); se estimó "similar o mayor a CEPU" dado que ambas
son empresas más grandes/antiguas. Resultó: YPF 52 presentaciones EEFF_PROPIO
(74 en discovery general fue el número de CEPU; YPF descubrió 4.919 guids
únicos en total, de los cuales 52 son EEFF_PROPIO modernos), TGSU2 125.

Duplicados posibles identificados de antemano: el mismo problema de
cache-busting/anti-forgery que ya se conocía de CEPU (ver `CNV_C3_STATE.md`) —
esperado, no bloqueante, cubierto por `canonical_sha256`.

Limitación identificada ANTES de fetchear: `identity.entities` (schema legacy)
no tiene fila para ninguno de los dos CUIT — no bloquea (identity_v1 ya es la
autoridad), pero se registró como hallazgo esperado, no oculto.

---

## FASE D — Fetch controlado (mecanismo oficial, sin scraper paralelo)

```
python scripts/engine/c3_cnv_fetch.py --cuit 30546689979 --scope EEFF_PROPIO   # YPF
python scripts/engine/c3_cnv_fetch.py --cuit 30657862068 --scope EEFF_PROPIO   # TGSU2
python scripts/engine/c3_cnv_fetch.py --cuit 30657862068 --scope EEFF_PROPIO --rerun  # TGSU2, Fase G
```

| Empresa | run_id | Gate | Checkpoint | Artefactos | Bytes RAW nuevos |
|---|---|---|---|---|---|
| YPF | `cf76f3eee37b4e579114889e38ff531e` | PASS 10/10 | `0e66272e54574c00a81a20252d79b804` | 53 (1 empresa + 52 visores) | 12.568.430 |
| TGSU2 (1ra) | `60d6adb14d36...` | PASS 10/10 | `93d6ae5670ac439c8848a6d1e47ccf31` | 126 (1 + 125) | 15.525.297 |
| TGSU2 (rerun) | `fe56c67a5b72...` | PASS 10/10 | `93d6ae5670ac439c8848a6d1e47ccf31` (reutilizado) | 126 | 0 nuevos (idéntico en sustancia) |

Nota de infraestructura: durante la ejecución, `catalaxia-engine-dev` (Postgres
5433) sufrió al menos dos cortes de conectividad por saturación de checkpoints
WAL (`checkpoints are occurring too frequently`), consistentes con el enorme
volumen de trabajo concurrente de otros agentes sobre la misma base compartida.
Se esperó y reintentó (con backoff acotado); no se reinició el contenedor ni se
tocó la configuración de Postgres — habría afectado a otras sesiones activas.

Por cada empresa se registró (ver JSON archivados en
`outputs/docs/fase_cnv/C3_CNV_STAGE_REPORT_*` y `fetch_raw.cnv_download_log`):
entity_key, CUIT, fuente del CUIT (assertion_id + method), request, response
(http_status, bytes, content_type), cantidad de presentaciones, hash (sha256 +
sha256_b64 + canonical_sha256), timestamp, provenance completa.

---

## FASE E — Validación

Para YPF y TGSU2 (datos de HOY, verificables de punta a punta):

1. **Todas las presentaciones pertenecen al CUIT solicitado** — check `C-C3-010`:
   100% en ambos casos, 0 requests a otros CUIT/SEC/mercado.
2. **No se mezclaron emisores** — confirmado independientemente (Fase H,
   `AUD-ATRIB-001`): 0 corridas de YPF o TGSU2 tocaron un CUIT ajeno.
3. **No se atribuyó por ticker** — nunca se usó un ticker como entrada; el CLI
   solo acepta `--cuit`, validado por formato antes de tocar identity_v1 o la
   red (ver adversario #4).
4. **Sin duplicados** — `AUD-DUP-001`: 0 en ambos.
5. **Provenance apunta al request real** — `AUD-PROV-001`/`002`: 100% completa
   y coherente (el CUIT de la fila coincide con el `CUIT{n}` de su `raw_path`).
6. **Hashes coinciden** — `AUD-HASH-001` para los archivos de HOY: 53/53 (YPF)
   y 126+126/126+126 (TGSU2, ambas corridas) recalculados desde disco,
   coinciden exactamente con la base. 0 mismatch.
7. **Cantidad persistida == cantidad descargada** — `AUD-CANT-001` para las
   corridas de hoy: exacto (53=53, 126=126, 126=126).

**Hallazgo real, no oculto (afecta a la evidencia HISTÓRICA, no a lo fetcheado
hoy)**: el auditor independiente encontró que la mayoría de los archivos RAW
de corridas ANTERIORES a esta sesión —incluidas las 5 corridas propias de CEPU
del 2026-08-25 (375 archivos) y dos corridas masivas de alcance más amplio
para YPF (1.782 + 653 archivos) y TGSU2 (692 archivos)— **ya no existen en
disco**, aunque `fetch_raw.cnv_download_log` los sigue listando como
`DOWNLOADED` con su sha256. Los archivos que SÍ sobreviven (los de corridas
recientes, incluidas las de hoy) verifican su hash exactamente. Patrón: corte
temporal limpio, 0 mismatch (ningún archivo remanente está corrupto o alterado)
— consistente con una limpieza de retención (relacionada con el hallazgo
abierto F-008, "RAW sin política de retención") aplicada a nivel de sistema de
archivos sobre `data/raw/` (directorio con `.gitignore`), sin una reconciliación
correspondiente en la base. **No se puede, hoy, re-verificar físicamente la
mayoría de las 36.136 presentaciones que la base dice tener** — se puede
verificar su metadata (provenance, atribución, ausencia de mezcla) pero no su
contenido byte a byte. Se documenta como hallazgo de esta auditoría, no se
oculta ni se intenta reparar (no corresponde al alcance: no se hizo backfill
masivo ni se tocó RAW histórico).

---

## FASE F — Adversarial

10 ataques ejecutados de forma real (transacciones revertidas donde
correspondía). Detalle completo: `CNV_VALIDATION_ADVERSARIO.json`.

| # | Ataque | Resultado | Barrera |
|---|---|---|---|
| 1 | CUIT con dígito verificador roto | RECHAZADO | `identity_v1.assert_identifier()` → `cuit_valido()` (módulo 11) |
| 2 | CUIT de otra entidad (CEPU) atribuido a YPF | RECHAZADO | `ux_identifier_autoritativo_unico` + conflicto abierto automáticamente |
| 3 | Fetch sin CUIT verificado (BMA) | CORRECTAMENTE BLOQUEADO | 0 identifiers CUIT/LEI en identity_v1 para BMA — no hay nada que pasarle al fetcher sin inventarlo |
| 4 | Ticker/valor no-CUIT como `--cuit` (×3) | RECHAZADO | `val.normalize_cuit()` + chequeo de 11 dígitos, antes de tocar red o DB |
| 5 | ADR vs instrumento local | (cubierto por Fase E ítem 1: `C-C3-010`) | scope 100% al CUIT local, 0 mezcla con el ADR/ticker NYSE |
| 6 | Vínculo por coincidencia de nombre | ESTRUCTURALMENTE IMPOSIBLE | revisión estática: 0/3 archivos de código (`c3_cnv_fetch.py`, `c3_identity_link.py`, `identity_v1.py`) tienen algún camino que compare nombres |
| 7/12 | Retry / reejecución del mismo fetch | (cubierto por Fase G) | `canonical_sha256` + checkpoint-reuse — ya probado 2 veces (CEPU en sesión previa, TGSU2 en esta) |
| 8 | Respuesta duplicada | (cubierto por `C-C3-009`) | 0 duplicados en las 3 corridas de hoy |
| 9 | Respuesta vacía / shell genérica | (cubierto, sesión previa) | `validate_empresa_page` (`V-GENERIC-PAGE`, `V-MIN-SIZE`) — probado con CUIT inexistente, BLOCK correcto |
| 10 | Reescribir una assertion vigente (cambio de CUIT post-fetch) | RECHAZADO | permiso denegado sobre `identity_v1.assertion` (rol `catalaxia_engine` sin UPDATE ahí — más fuerte que el trigger `tg_assertion_inmutable` documentado, que sería la segunda barrera si la primera no existiera) |
| 11a | Borrar una fila de `fetch_raw.cnv_download_log` (DELETE) | RECHAZADO | permiso denegado — el rol no tiene DELETE en `fetch_raw` (migración 011) |
| 11b | Falsificar el sha256 de una fila ya persistida (UPDATE) | **SIN BARRERA** | el rol SÍ tiene UPDATE en `fetch_raw.*`. El `UPDATE` se aplica sin excepción. Mitigación parcial: el auditor independiente (`AUD-HASH-001`) lo detectaría en la siguiente pasada al recalcular contra el archivo real — pero nada impide la escritura en el momento en que ocurre |

**9/10 barreras confirmadas. 1 gap real encontrado y no maquillado (11b)**:
a diferencia de `identity_v1` (que blinda hasta el UPDATE con triggers de
inmutabilidad), el schema `fetch_raw` de CNV solo bloquea el DELETE a nivel de
permisos; un UPDATE que falsifique un hash pasaría sin que la base lo note en
el momento. Es una asimetría real entre el rigor de identity_v1 y el de CNV,
para cerrar en un ciclo futuro (no se implementó un fix acá: cambiar permisos
de un rol compartido con otros workstreams no es "estrictamente necesario"
para esta validación y sí es un cambio transversal que el mandato pide evitar
salvo necesidad).

---

## FASE G — Idempotencia (repetida en una SEGUNDA entidad, no solo CEPU)

TGSU2, `--rerun`: 126/126 artefactos comparados contra la corrida anterior por
`canonical_sha256`, **0 cambios reales**, checkpoint reutilizado exacto
(`93d6ae5670ac439c8848a6d1e47ccf31`, mismo en ambas corridas). Confirma que el
mecanismo de idempotencia (hash canónico + checkpoint-reuse, ambos corregidos
en la sesión C2→C3 anterior) **generaliza** más allá de CEPU — no era una
solución ad-hoc para un solo caso.

---

## FASE H — Auditoría independiente

`scripts/engine/cnv_validation_auditor.py` — **no importa** `c3_cnv_fetch.py`
ni `engine/cnv/{discovery,validate,rawstore}.py`. Reimplementa desde cero:
dígito verificador AFIP, cálculo de sha256 desde disco, y todas las queries de
identidad/cantidad/duplicados/provenance/atribución. Corrido contra los 3 CUIT
con datos reales (más el CUIT de prueba `99999999999`, que correctamente da
0 en todo). Resultado completo: `CNV_VALIDATION_AUDITOR_REPORT.json`.

Veredicto por CUIT (gate propio del auditor, más estricto que el del fetcher
porque exige que el archivo físico exista, no solo que el manifest lo declare):

| CUIT | AUD-CUIT | AUD-IDENT | AUD-CANT (histórico) | AUD-DUP | AUD-HASH (histórico) | AUD-PROV | AUD-ATRIB |
|---|---|---|---|---|---|---|---|
| YPF | PASS | PASS | FAIL (55/2492 en disco) | PASS | FAIL (2437 faltantes) | PASS | PASS |
| CEPU | PASS | PASS | FAIL (6/390 en disco) | PASS | FAIL (384 faltantes) | PASS | PASS |
| TGSU2 | PASS | PASS | FAIL (128/820 en disco) | PASS | FAIL (692 faltantes) | PASS | PASS |
| 99999999999 (control negativo) | FAIL (dígito no coincide) | FAIL (0 en identity_v1) | PASS (0=0) | PASS | PASS (0=0) | PASS | PASS |

El auditor da **FAIL global por el hallazgo real de Fase E** (RAW histórico
faltante) — deliberadamente no lo suaviza. Desglosado por antigüedad (ver
Fase E): **0 discrepancias en las corridas de HOY** para las 3 empresas; el
100% de las discrepancias son de corridas anteriores a esta sesión.

---

## FASE I — Gate

Ver `CNV_VALIDATION_GATE.md`.

---

## Lista de blockers para CNV masivo

1. **RAW histórico sin retención documentada** (Fase E/H): definir una política
   explícita (¿cuánto se conserva? ¿se reconcilia la DB cuando se borra RAW?)
   antes de escalar — hoy el volumen ya generó una limpieza no auditada.
2. **`fetch_raw.*` sin protección de UPDATE** (adversario #11b): un rol con
   permisos de escritura puede falsificar un hash ya persistido sin que nada
   lo impida en el momento. Cerrar antes de dar por buena la integridad del
   RAW a escala.
3. **GGAL y BMA no tienen camino de CUIT autoritativo** (F-024, LEI ambiguo de
   Banco Macro; RA999999 de GGAL): escalar a estas dos, u otras con el mismo
   patrón, requiere primero cerrar esos hallazgos de identidad — no es un
   problema de CNV, es un prerrequisito de Identity V1.
4. **Volumen**: YPF y TGSU2 con solo `--scope EEFF_PROPIO` ya generaron
   28 MB combinados en una corrida cada uno; escalar a `FINANCIERO`/`TODO`
   sobre un universo de decenas de emisores multiplica esto linealmente (ya
   señalado como F-008 antes de esta sesión).
5. **Infraestructura compartida bajo estrés**: la base de datos de desarrollo
   mostró cortes de conectividad reales durante esta sesión por la carga
   concurrente de múltiples agentes. Un fetch masivo debería tener su propio
   manejo de reintentos con backoff a nivel de conexión (hoy `apply_migrations`/
   `get_engine` no lo tienen) antes de correr desatendido a escala.
