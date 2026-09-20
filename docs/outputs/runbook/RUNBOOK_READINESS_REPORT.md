# INFORME DE OPERABILIDAD DEL RUNBOOK

> **CORRECCIÓN (2026-09-03, Golden Run METR).** Este informe afirmó que había
> **230 documentos descargados y nunca procesados**. La medición era correcta
> en su aritmética pero **incorrecta en su interpretación**: de esos 230,
> **226 no son documentos**. Son la página de espera del visor de la CNV
> —"Cargando información…", ~77 KB de UI, **cero códigos con valor**, sin
> `FechaCierre` ni `TipoBalance`—: la descarga capturó el shell antes de que
> el contenido se cargara.
>
> El desglose correcto de los 286 EEFF de Metrogas es:
>
> ```
> PROCESSED_OK    56    documentos extraídos
> PENDING          4    EEFF genuinos que el extractor nunca intentó
> FAILED         226    descargas que no capturaron el documento
> REJECTED         0
> ```
>
> **Siguen siendo dos problemas reales, pero distintos**, y el segundo es más
> grave que el que yo había descrito: no es que falte procesar el 80 % del
> corpus, es que **el 79 % de las descargas nunca trajo nada y nada lo
> detectó**. La brecha de procesamiento real es de 4 documentos.
> Ver `outputs/docs/fase_cnv/METROGAS_GOLDEN_RUN_REPORT.md`.

**Pregunta del sprint:** ¿puede una persona independiente operar Catalaxia de
forma determinística siguiendo sólo manuales?

**Respuesta:** **para SEC/EDGAR, sí, con reservas. Para CNV, no.**

Nada de lo que sigue afirma que algo esté implementado si el código no lo
demuestra. Cada afirmación tiene su comando de verificación.

---

## 1 · Resumen ejecutivo

Catalaxia tiene **dos mitades de madurez muy distinta**, y el hallazgo central
del sprint es que esa diferencia no estaba documentada en ninguna parte.

**El engine SEC está bien construido.** Máquina de estados validada en código,
39 checks con identificador, reportes JSON con conciliación obligatoria,
checkpoint por hash de contenido, guard de producción que aborta antes de
conectar, ledger de descargas con SHA256 poblado. Un operador nuevo puede
correrlo.

**El camino CNV que produjo todos los datos no es el camino oficial.** El
oficial (`c3_cnv_fetch.py`) está instrumentado pero **no descarga estados
financieros**: los 4.005 artefactos de su ledger son sólo `VISOR` y
`EMPRESA_PAGE`. Los datos vienen de un script legacy sin gate, sin `run_id`,
sin SHA almacenado y sin registro de rechazos.

**El hallazgo más caro es que nadie mide la cobertura.** Para Metrogas hay
**286 documentos EEFF en la whitelist y sólo 56 con datos**. Del resto,
**226 no son EEFF estructurados** —197 son presentaciones de 2000-2018 cuyo
estado contable es un PDF adjunto y 29 son el formulario de participaciones,
ver GATE 2— y **4 son EEFF genuinos que el extractor nunca intentó**. Ninguno de los
dos casos aparece en un contador, reporte o gate. El caso de diagnóstico
obligatorio del sprint —el CONSOLIDADO al 30/09/2024— es uno de esos 4: se
descargó entero, parsea perfectamente (38 conceptos, período, perímetro y
escala correctos) y simplemente nunca le tocó el turno.

| | veredicto |
|---|---|
| **SEC/EDGAR** | `PASS_WITH_WARNINGS` |
| **CNV** | `BLOCKED` |
| **Market** | `PARTIAL` |
| **GLOBAL** | **`BLOCKED`** |

## 2 · Estado actual

Matriz completa en `RUNBOOK_READINESS_MATRIX.csv` (19 filas × 16 campos).

| estado | filas |
|---|---:|
| `READY` | 4 |
| `PARTIAL` | 8 |
| `SOFTWARE_GAP` | 5 |
| `RUNBOOK_GAP` | 2 |

| componente | distribución |
|---|---|
| SEC | 3 `READY`, 3 `PARTIAL` |
| CNV | 1 `PARTIAL`, 3 `SOFTWARE_GAP`, 1 `RUNBOOK_GAP` |
| Market | 2 `PARTIAL`, 1 `SOFTWARE_GAP` |
| Transversal | 1 `READY`, 2 `PARTIAL`, 1 `SOFTWARE_GAP`, 1 `RUNBOOK_GAP` |

## 3 · SEC E2E

Seis etapas, todas con `STAGE_ID` registrado:

```
S00_bootstrap → S01_identity → S02_fetch → S03_parse → S04_normalize → ratios
```

Cada una busca en la base la última corrida con gate `PASS` de la anterior. No
se pasan archivos entre etapas: el encadenamiento está en la base.

**Lo que funciona bien:** el checkpoint de S03 (`input_hash` sobre entidad +
cada `(ruta, sha256)`), `hash_out` con spec `hashout-v2` sensible al contenido
e insensible al orden, `C-S04-001` que **recalcula** el `hash_out` de S03 en
vez de creerle, y el `download_log` con SHA poblado (723 de 728 `DOC_HTM`).

**Reservas:** `C-S01-004` está clavado a YPF y falla en una base sana para otro
emisor (`SG-05`); S04 imprime un checkpoint que no persiste (`SG-09`); y de los
14 ratios contables definidos, ninguno se persiste (`SG-03`).

## 4 · CNV E2E

**No existe.** Tres caminos, ninguno completo:

| tramo | estado real |
|---|---|
| **A** `c3_cnv_fetch.py` | instrumentado, con 10 checks y ledger — pero `artifact_kind` sólo toma `VISOR` (3.936) y `EMPRESA_PAGE` (69). **Cero artefactos de estados financieros** |
| **B** `job5_v2_extract_eeff.py` | produjo todos los datos. Sin `argparse`, sin gate, sin `run_id`, sin SHA, sin log de rechazos |
| **C** `c4_cnv_adapter.py` | lleva B al modelo canónico. Vive en el worktree `catalaxia-cnvmig`, **sin mergear** |

Verificación:
```bash
docker exec catalaxia-engine-dev psql -U catalaxia -d catalaxia -c \
  "SELECT artifact_kind, count(*), count(hash_cnv) FROM fetch_raw.cnv_download_log GROUP BY 1"
```

## 5 · ADR

`02A_SEC_EDGAR_ADR_ANNEX.md` separa los tres objetos: **emisor**,
**instrumento**, **datos de mercado**.

Los datos existen: 12 instrumentos `security_type='adr'`, los 12 con
`ratio_adr` (CRES 10, LOMA 5, VIST 1, TGSU2 5, PAMP 25, IRSA 10) y
`venue_ticker` distinto de `ticker_canonico`.

**Lo que no existe es el puente.** `market_instruments.entity_id` es un entero
legacy (`58`, `59`…), no el `CIK:`/`CUIT:` del engine. Sin ese enlace, ningún
múltiplo que combine precio y contabilidad es trazable (`SG-10`). Tampoco se
registra el depositario (`RG-03`).

## 6 · Logging

**No hay archivos de log.** Todo va a stdout o a PostgreSQL.

Lo que sí hay es un contrato fuerte de reporte (`engine/report.py`): campos
obligatorios, **`checks` no vacío** —*"terminó sin excepción nunca es PASS"*— y
**`expected == parsed + rejected`**.

Tres huecos, en `appendices/LOG_CATALOG.md` §3:

1. **La extracción CNV no deja rastro.** Contadores agregados a stdout.
2. **S02 no registra reintentos.** Reintenta 3 veces con backoff pero
   `download_log` guarda sólo el resultado final: no se puede distinguir "salió
   a la primera" de "salió tras dos 429".
3. **El hash de origen de CNV nunca se captura.** Columna y check existen; el
   dato es NULL en 4.005 de 4.005 filas.

## 7 · Manejo de errores

**39 IDs de check reales** (`C-S00-001` … `C-C3-010`), con flag `blocking`
explícito, catalogados en `appendices/ERROR_CATALOG.md`.

**Lo que no existe es un vocabulario de códigos de error operativos** (`SG-07`).
`EXT-010` es el único código que el software emite por su nombre; los `F-0NN`
son identificadores de defectos históricos, no condiciones de runtime. Las
etiquetas `SEC-DL-*` y `CNV-*` del catálogo están marcadas como introducidas
por el runbook.

## 8 · Fallbacks

**Existen tres, y sólo tres:**

1. Reintento HTTP: 3 intentos, backoff `[2, 5, 10]` s, **sólo** en
   429/500/502/503/504 (`engine/fetch.py`).
2. Checkpoint hit en S03.
3. Rate limiting por host en C3.

No hay fuente alternativa, ni parser alternativo, ni cuarentena, ni reproceso
automático.

**Una de las cinco reglas del sprint se viola hoy:** *"un fallback no puede
ocultar un error"*. `_mark_done(guid)` tras un fallo de parseo en CNV lo oculta
de forma permanente y sin registro.

## 9 · Recuperación

20 casos en `appendices/RECOVERY_PROCEDURES.md`, con
`DETECTAR → LOG → AUTOMÁTICA → VERIFICAR → REANUDAR → TERMINAL`.

Recuperación **automática** real: sólo el reintento HTTP y el checkpoint hit.
El resto es humana. `run_scope` cierra la corrida en `finally` —eso resolvió
F-009— pero un `kill -9` la deja en `RUNNING` para siempre;
`corridas_huerfanas` las **detecta y no las cierra** (`SG-11`).

## 10 · Checkpoints

**Uno solo real:** `engine.checkpoints`, escrito por S03, con índice único
`(stage_id, input_hash, code_version, contract_version)`.

- S04 imprime un id de checkpoint pero **no persiste fila** (`SG-09`).
- `job5` usa `data/log_job5_v2_done.txt`, que **no distingue éxito de fracaso**
  y no tiene hash de input ni de output. Es un registro de "ya lo vi".
- **No existe `--resume`** en ningún script (`RG-02`).

## 11 · Idempotencia

| etapa | estado | evidencia |
|---|---|---|
| S00 | **demostrada** | 2ª corrida aplica 0 migraciones |
| S01 | **demostrada** | `upsert` no duplica |
| S02 | **parcial** | RAW no se duplica; `download_log` crece por diseño |
| S03 | **demostrada y automática** | checkpoint hit ⇒ 0 escrituras, mismo `hash_out` |
| S04 | **por diseño** | `valid_to`; verificable por digest de `fact_key` |
| adaptador CNV | **demostrada** | 0 inserts, 2.697 reusados, digests idénticos |
| `job5` | **no verificable** | no hay `hash_out` |
| market | **no verificada** | fuera del alcance auditado |

## 12 · Provenance

Cadena completa documentada en `06_PROVENANCE.md`:
`RESULTADO → FÓRMULA → INSUMO → FACT → CONCEPTO → CONTEXTO → DOCUMENTO → RAW → SHA256`.

Las dos identidades (`fact_key` de la ocurrencia, `econ_key` del hecho
económico) tienen serialización canónica normativa.

Reconstruible: ratios SEC, snapshot METR FY2024. **No reconstruible:** hechos
CNV en `screener.db` (sin SHA de referencia) y cualquier ratio que combine
mercado con contabilidad.

## 13 · Seguridad de producción

**Es lo mejor resuelto del sistema.** Tres capas independientes:

1. **EXT-010** en `engine/config.py`: `load_settings()` lanza `RuntimeError` si
   el puerto es 5432 sin `ENGINE_ALLOW_PROD=1`. **Probado en el test**
   `test_v7_el_guard_de_produccion_existe_y_funciona`, que ejecuta el guard.
2. **Guards por `db_name`** en `c3_cnv_fetch.py` y el adaptador canónico.
3. **Aislamiento estructural**: producción no tiene los esquemas del engine.
   Sólo `public`.

## 14 · Golden Runs

**SEC (YPF, `0000904851`)** — comandos y criterios en
`appendices/GOLDEN_RUNS.md` §1.

> **No lo ejecuté en este sprint.** Requiere red y escribiría en la base de
> desarrollo, y el sprint es de documentación. Lo verificado es que los
> comandos y argumentos existen (tests V1 y V3) y que el `GOLDEN_CIK`
> documentado es el del código (test V8). **El criterio de gate 15 queda como
> NO VERIFICADO, no como PASS.**

Además, `RG-01`: no hay conteos esperados canónicos porque dependen de cuántos
filings tenga YPF en EDGAR. Lo determinístico y exigible es: 6 gates en `PASS`,
`rows_failed = 0`, `filings_rejected = 0`, y que una 2ª corrida de S03 dé
checkpoint hit con el mismo `hash_out`.

**CNV (METR)** — parcial por lo de §4. Existe un snapshot certificado
(`METR_FY2024_E2E_REPORT.md`) pero producido con el worktree.

## 14b · Prueba del operador nuevo

Se ejecutaron literalmente los comandos de verificación de
`01_COMMON_OPERATIONS.md` §1, sin usar conocimiento previo del proyecto.
**Los cuatro dan exactamente la salida que el manual anticipa:**

| § | comando | salida obtenida | ¿coincide? |
|---|---|---|---|
| 1.2 | `python -c "…load_settings()…"` | `catalaxia_engine@127.0.0.1:5433/catalaxia mode=FAST prod=False` | sí |
| 1.3 | esquemas del engine | `derived,engine,fetch_raw,identity_v1,parsed` | sí |
| 1.4 | esquemas de producción | `public` | sí |
| 1.5 | huella de `screener.db` | `2026-08-23 13:42:23 · 1504714752` | sí |

**Un punto de interpretación encontrado y corregido:** el manual no explicaba
de dónde sale la contraseña de la base. `load_settings()` la toma de `.env` en
la raíz del repo; sin ese archivo el fallo es
`password authentication failed`, que no menciona el `.env` por ningún lado. Se
agregó a `01_COMMON_OPERATIONS.md` §2.

**No se ejecutaron las etapas del pipeline** — requieren red y escribirían en
la base de desarrollo. Es la limitación que deja el criterio 15 del gate en
`NO VERIFICADO`.

## 15 · Runbook gaps

| id | qué falta documentar de forma determinística |
|---|---|
| **RG-01** | Conteos esperados canónicos del Golden Run SEC |
| **RG-02** | Procedimiento de reanudación: no hay `--resume`; la reanudación real es implícita y distinta en cada etapa |
| **RG-03** | Depositario del ADR: no se registra en ninguna tabla |

## 16 · Software gaps

Ordenados por impacto operativo.

| id | gap | evidencia |
|---|---|---|
| **SG-01** | **No hay E2E de CNV.** El camino instrumentado no descarga EEFF | `artifact_kind` ∈ {`VISOR`, `EMPRESA_PAGE`}; 0 artefactos financieros |
| **SG-04** | **No hay reconciliación descargado → procesado → con datos** | METR: 286 seleccionados, 56 con datos. 226 descargas vacías + 4 sin procesar, sin ningún contador que lo exponga |
| **SG-12** | **No se valida que una descarga contenga un documento** | 226 de 286 archivos son la página de espera del visor: ~77 KB, 0 códigos con valor. Se guardan como si fueran EEFF |
| **SG-02** | **No se almacena el SHA256 de documentos CNV** | `hash_cnv` NULL en 4.005/4.005; ninguna tabla de `screener.db` lo guarda. `C-C3-008` nunca compara nada |
| **SG-10** | **El enlace instrumento ↔ emisor no resuelve** | `market_instruments.entity_id` es entero legacy vs `CIK:`/`CUIT:` |
| **SG-03** | **Los 14 ratios contables no los persiste ninguna etapa** | `derived.ratio` sólo tiene `eps`, `pe`, `pb`, `ev_sales` |
| **SG-07** | No hay vocabulario de códigos de error operativos | `EXT-010` es el único |
| **SG-08** | **No existe cuarentena** | 0 coincidencias de `quarant`/`cuarentena` en `engine/`, `scripts/engine/`, `migrations/` |
| **SG-11** | Las corridas huérfanas se detectan pero no se cierran | `corridas_huerfanas` sólo devuelve la lista |
| **SG-09** | S04 no persiste checkpoint | imprime el id, no inserta fila |
| **SG-06** | Dos `stage_id` para la misma etapa | `C3_CNV_fetch` (294 transiciones, 26 reportes) y `C3_CNV_FETCH` (120, **0**) |
| **SG-05** | `C-S01-004` clavado a YPF | falla en una base sana para otro emisor |

## 17 · Riesgos

1. **Cobertura silenciosa (SG-04, SG-12) — el más grave.** No es que el sistema
   falle: es que reporta éxito sin medir qué fracción del corpus usó. De 286
   documentos seleccionados, 226 descargas no trajeron nada y 4 quedaron sin
   procesar, y nada lo señala.
2. **Dos caminos CNV sin dueño declarado (SG-01).** El instrumentado no sirve;
   el que sirve no está instrumentado. Un operador nuevo elige mal por defecto.
3. **Sin SHA de CNV (SG-02), no hay integridad verificable** de la fuente que
   alimenta todos los datos argentinos.
4. **Sin el puente de market (SG-10)**, los múltiplos no son auditables — y son
   el producto final.
5. **Sin cuarentena (SG-08)**, un documento problemático no tiene dónde
   esperar: o entra o se pierde.

## 18 · Plan de remediación

Ordenado por impacto sobre la operabilidad, no por esfuerzo.

| # | acción | cierra | por qué primero |
|---|---|---|---|
| 1 | **Reconciliación de cobertura**: una consulta que compare whitelist / disco / DONE / con-datos, expuesta como check bloqueante | `SG-04` | Es la más barata y la de mayor impacto. Ya está escrita en `03_CNV_E2E_RUNBOOK.md`; falta convertirla en gate |
| 2 | **Tabla de rechazos por documento** en CNV, con GUID, motivo y `run_id`; y que `_mark_done` distinga éxito de fracaso | `SG-04`, `SG-07` | Sin esto, todo diagnóstico CNV exige leer el código |
| 3 | **Persistir el SHA256** de cada documento CNV al descargarlo, y poblar `hash_cnv` | `SG-02` | Habilita `C-C3-008`, que ya está escrito |
| 4 | **Puente instrumento ↔ entidad**: migrar `market_instruments.entity_id` a namespaced | `SG-10` | Desbloquea todos los múltiplos |
| 5 | **Decidir el camino CNV oficial**: extender C3 a EEFF, o instrumentar job5 | `SG-01` | Es una decisión de arquitectura, no de código |
| 6 | Persistir los 14 ratios contables | `SG-03` | Ya están definidos y probados |
| 7 | Unificar `C3_CNV_fetch` / `C3_CNV_FETCH` | `SG-06` | Trivial, ensucia todo el histórico |
| 8 | Cerrar corridas huérfanas | `SG-11` | |
| 9 | Parametrizar `C-S01-004` | `SG-05` | |
| 10 | Checkpoint persistido en S04 | `SG-09` | |
| 11 | Cuarentena | `SG-08` | Depende de (2) |

Con **(1), (2) y (3)** el runbook de CNV pasaría de `BLOCKED` a
`PASS_WITH_WARNINGS`.

## 19 · Gate final

| # | criterio | resultado |
|---|---|---|
| 1 | Los comandos documentados existen | **PASS** — test V1 |
| 2 | Los argumentos documentados existen | **PASS** — test V3 |
| 3 | El orden del pipeline coincide con el código oficial | **PARCIAL** — sí en SEC; CNV no tiene camino oficial único |
| 4 | Cada etapa tiene precondiciones | **PASS** |
| 5 | Cada etapa tiene output esperado | **PASS** |
| 6 | Cada etapa tiene criterio PASS/FAIL | **FAIL** — `job5` y `s0_normalizar_cnv` no tienen gate |
| 7 | Los errores tienen código o están marcados como gap | **PASS** |
| 8 | Los fallbacks reales están documentados | **PASS** |
| 9 | Los fallbacks quedan logueados | **FAIL** — el descarte de CNV no deja registro |
| 10 | Las recuperaciones reales están documentadas | **PASS** |
| 11 | Los checkpoints reales están documentados | **PASS** |
| 12 | La idempotencia está demostrada | **PARCIAL** — sí en S03 y el adaptador; no en `job5` ni market |
| 13 | Production safety documentado **y probado** | **PASS** — el test ejecuta el guard |
| 14 | Provenance documentada | **PASS** |
| 15 | SEC Golden Run funciona | **NO VERIFICADO** — no se ejecutó en este sprint |
| 16 | CNV Golden Run funciona | **FAIL** — no hay E2E de CNV |
| 17 | METR 30/09/2024 permite diagnosticar | **PARCIAL** — 9 de 10 preguntas; falta la validez del SHA |
| 18 | ADR tiene anexo separado | **PASS** |
| 19 | Ninguna instrucción requiere consultar a una IA | **PASS** — verificado por test |
| 20 | El operador nuevo puede correr el Golden Run con sólo el manual | **PARCIAL** — plausible en SEC; imposible en CNV |

```
SEC/EDGAR   = PASS_WITH_WARNINGS
CNV         = BLOCKED
MARKET      = PARTIAL
─────────────────────────────────
RUNBOOK_READINESS = BLOCKED
```

**`BLOCKED`, no `PASS_WITH_WARNINGS`.** Tres criterios fallan de plano (6, 9,
16) y uno quedó sin verificar (15). El bloqueo no es del manual: es del
software que el manual describe. La documentación está completa y es fiel —
lo que no se puede hacer es operar CNV de punta a punta, porque el camino no
existe.

El sprint pedía determinar si Catalaxia puede operarse determinísticamente por
una persona independiente y, si no, dejar identificadas las modificaciones
necesarias. **Están en §18, son once, y las tres primeras alcanzan para
desbloquear CNV.**

---

### Entregables

```
docs/runbooks/
├── 00_START_HERE.md              01_COMMON_OPERATIONS.md
├── 02_SEC_EDGAR_E2E_RUNBOOK.md   02A_SEC_EDGAR_ADR_ANNEX.md
├── 03_CNV_E2E_RUNBOOK.md         04_MARKET_DATA_E2E.md
├── 05_RATIO_REFERENCE.md         06_PROVENANCE.md
├── 07_CERTIFICATION.md
└── appendices/
    ├── ERROR_CATALOG.md          FALLBACK_MATRIX.md
    ├── LOG_CATALOG.md            CHECKPOINT_CATALOG.md
    ├── RECOVERY_PROCEDURES.md    COMMAND_REFERENCE.md
    ├── DATABASE_REFERENCE.md     GOLDEN_RUNS.md

outputs/runbook/RUNBOOK_READINESS_MATRIX.csv   19 filas × 16 campos
outputs/runbook/RUNBOOK_READINESS_REPORT.md    este informe
tests/test_runbook_operability.py              22 tests, todos pasan
```

**No se modificó lógica de negocio.** Todo lo creado en este sprint lleva fecha
`2026-09-03`; los archivos que `git status` muestra modificados en `engine/` y
`scripts/` traen mtime del 31/08 y 01/09, de sprints anteriores. Verificable:

```bash
git status --short | grep '^??' | grep runbook
stat -c '%y %n' engine/db.py scripts/engine/c3_cnv_fetch.py
```

`screener.db` quedó con su huella original (`2026-08-23 13:42:23`) y producción
con el esquema `public` y nada más.
