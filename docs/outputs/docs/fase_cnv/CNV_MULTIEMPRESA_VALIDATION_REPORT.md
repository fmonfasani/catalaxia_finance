# CNV — VALIDACIÓN MULTI-EMPRESA PARA HOMOLOGACIÓN

Rol: Senior Data/Integration Engineer, validación de trazabilidad. Alcance:
exclusivamente CNV. Fecha: 2026-09-01. DB objetivo verificada en cada corrida:
`catalaxia_engine@127.0.0.1:5433/catalaxia ... prod=False` — **sin ambigüedad
dev/prod en ningún momento**; no fue necesario detenerse por esa causa.

**Objetivo**: determinar si el mecanismo Identity → CNV es generalizable y
suficientemente robusto para homologación — no si "CEPU funciona".

---

## FASE A — Inventario (leído antes de actuar, nada modificado)

Se leyeron `CNV_VALIDATION_REPORT.md`/`GATE.md` previos, `.claude/state/{CNV_C3_STATE,AUDITOR_STATE}.md`,
`docs/architecture/IDENTITY_V1_SCHEMA.md`, y el código vigente de
`scripts/engine/c3_cnv_fetch.py` y `engine/identity_v1.py`. Confirmado, leyendo
código (no asumiendo del reporte anterior, que ya estaba desactualizado en
este punto):

- **Cómo Identity entrega el CUIT**: `c3_cnv_fetch.py::resolver_en_identity_v1(engine, cuit, cik)`
  ejecuta una query fija (`SQL_IDENTITY_V1`) que resuelve por CIK o CUIT
  exactos contra `identity_v1.identifier`/`assertion`, nunca por nombre. Esta
  función es **nueva desde la última validación**: antes la identidad se leía
  de un seed CSV; ahora `load_identity()` llama a `resolver_en_identity_v1()`
  como única fuente de verdad, y el seed/legacy solo se usan para contrastar
  y registrar hallazgos, nunca para decidir.
- **Qué condición PERMITE consultar CNV**: la entidad debe resolver a
  exactamente una fila con `cuit IS NOT NULL` y `cuit_status == 'VERIFIED'`.
- **Qué condición BLOQUEA**: 4 motivos posibles, cada uno con mensaje propio:
  `NO_ESTA_EN_IDENTITY_V1` (el identificador no resuelve a ninguna entidad),
  `AMBIGUO` (resuelve a más de una — estructuralmente raro, ver Fase D #9),
  `SIN_CUIT` (la entidad existe pero no tiene CUIT vigente), `CUIT_NO_VERIFICADO`
  (tiene CUIT pero su assertion no es VERIFIED). En los 4 casos, `load_identity()`
  lanza `SystemExit` **antes** de `edb.start_run()` — no se crea ni siquiera un
  `run_id`, y por lo tanto no hay ninguna escritura posible en `fetch_raw.*`.
- **Qué tablas escribe `c3_cnv_fetch.py`**: `fetch_raw.cnv_presentation`
  (discovery), `fetch_raw.cnv_download_log` (una fila por request resuelto,
  con `sha256`/`canonical_sha256`/provenance completa), `fetch_raw.cnv_artifact`
  (dedupe por sha256), `engine.runs`/`engine.stage_runs`/`engine.checkpoints`
  (ciclo de vida). RAW en disco, content-addressed, en
  `data/raw/engine/cnv/CUIT{cuit}/{empresa,visor}/`.
- **Cómo se registra provenance**: cada fila de `cnv_download_log` lleva
  `entity_key`, `cuit`, `endpoint`, `http_status`, `sha256`, `sha256_b64`,
  `canonical_sha256`, `raw_path`, `run_id`, `attempts`, `elapsed_ms`,
  `validation_status`, `validation` (JSONB con las reglas evaluadas).
- **Cómo se identifica una corrida**: `run_id` (UUID hex) generado por
  `edb.start_run()`, ligado a `git_commit` y `pipeline_version`; el ciclo de
  vida pasa por `engine.stage_runs` (`READY→RUNNING→VALIDATING→PASSED/FAILED→CHECKPOINTED`).
- **Cómo se verifica idempotencia**: `--rerun` compara, para cada artefacto,
  el `canonical_sha256` de la corrida actual contra el de la corrida previa
  MÁS RECIENTE para el mismo `(artifact_kind, artifact_key)` (query SQL con
  `LEFT JOIN LATERAL`). Si coincide en el 100%, `C-C3-006` da PASS y el
  checkpoint existente se reutiliza (`ON CONFLICT ... DO UPDATE ... RETURNING`).
  Si NO coincide, da FAIL — **por diseño**, para no enmascarar un cambio real.

No se modificó nada en esta fase.

---

## FASE B — Selección de muestra

**Universo real disponible, verificado por query directa contra
`identity_v1` (525 entidades totales)**:

> Solo existen **3 entidades en todo Identity V1 con CUIT AUTHORITATIVE/VERIFIED
> vigente**: CEPU, YPF, TGSU2. **No existen 5 a 10 emisores adicionales con
> CUIT VERIFIED** — se buscó explícitamente y el resultado es ese, no una
> omisión de la muestra.

Lo que SÍ existe, y se incorpora a la muestra en su lugar: **13 emisores
adicionales con CUIT CANDIDATE/WEAK** (nunca promovido), todos vía
`LEGACY_DIM_ENTITY` sin cruce GLEIF exitoso: Aeropuertos Argentina 2000,
Banco BBVA Argentina, Banco de Galicia y Buenos Aires (la operativa, distinta
de GGAL holding), Banco Supervielle, CRESUD, EDENOR, GGAL, Grupo Supervielle,
IRSA, Loma Negra, Pampa Energy, Telecom Argentina, Vista Energy, YPF Energía
Eléctrica. Se usó **GGAL** como representante (caso "sin CUIT VERIFIED" +
"provenance distinta") sin fetchear los otros 12 — hacerlo no habría agregado
información nueva sobre el mecanismo, solo repetido el mismo resultado (BLOCK
por `CUIT_NO_VERIFICADO`) doce veces más.

| Empresa | Categoría | Elegible |
|---|---|---|
| CEPU | conocida, piloto original | SÍ |
| YPF | CUIT VERIFIED | SÍ |
| TGSU2 | CUIT VERIFIED | SÍ |
| GGAL | sin CUIT VERIFIED (CANDIDATE) | NO |
| BMA (Macro Bank Inc.) | sin CUIT demostrable (F-024, LEI ambiguo) | NO |
| CUIT `20111111112` | control negativo — identidad inexistente | NO |

**Conflicto real disponible en la base** (no sintético): `identity_v1.conflict`
tiene exactamente 1 fila — `conflict_id=29`, sobre BMA/F-024 ("dim_entity#572
declara cuit='0001347426' para el ticker BMA, pero ese valor es el CIK de
Macro Bank Inc. según SEC"). Se usa este, no se inventó uno nuevo.

**Instrumento/ticker ambiguo**: YPF (`TICKER/US=YPF` vs `TICKER/BYMA=YPFD`,
namespaces distintos, ya modelado) y el precedente histórico `COUR→Coursera`
documentado en `IDENTITY_V1_SCHEMA.md`. No se fetcheó nada por ticker — el CLI
no lo admite (ver Fase D #4).

No se inventó ningún CUIT ni se resolvió ninguna entidad por nombre/ticker en
ningún punto de esta fase.

---

## FASE C — Validación (por emisor elegible)

### CEPU (ya fetcheado en sesión previa, reconfirmado)

`entity_key` `E01M0X99DQ7P5TQ4Z6Z58RC5PB3` · CIK `0001717161` · LEI
`2549005JLIWQ6B7VNR38` · CUIT `33650305499` · assertion `346` (REGISTRY,
GLEIF vía AFIP RA000009) · bridge VERIFIED/AUTHORITATIVE · 9.305
presentaciones en `fetch_raw.cnv_presentation` · gate PASS 10/10 en su última
corrida (checkpoint `8db8692e...`) · 0 mezcla con otro CUIT.

### YPF (fetch NUEVO en esta sesión)

`entity_key` `E01M0X99C8F87H9TH9N39H2D1NW` · CIK `0000904851` · LEI
`5493003N7447U18U5U53` · CUIT `30546689979` · assertion `345` (REGISTRY,
GLEIF vía AFIP RA000009) · bridge VERIFIED/AUTHORITATIVE · run
`cf76f3eee37b4e579114889e38ff531e` · scope `EEFF_PROPIO` · 53 artefactos (1
empresa + 52 visores) · gate **PASS 10/10** · checkpoint
`0e66272e54574c00a81a20252d79b804` · 12.568.430 bytes RAW nuevos · 0 mezcla
con otro CUIT (verificado independiente, Fase E).

### TGSU2 (fetch NUEVO + 2 reruns en esta sesión)

`entity_key` `E01M0X99G29RBSSFSGAM5S1QZMT` · CIK `0000931427` · LEI
`5299002TRC7IFQYSW596` · CUIT `30657862068` · assertion `347` (REGISTRY,
GLEIF vía IGJ/RNS RA000010) · bridge VERIFIED/AUTHORITATIVE.

- Corrida 1 (`60d6adb14d3648b0803e5504c5b612d7`): PASS 10/10, checkpoint
  `93d6ae5670ac439c8848a6d1e47ccf31`, 126 artefactos, 15.525.297 bytes nuevos.
- Corrida 2, `--rerun` (`fe56c67a5b72469c9eee91d076cb4590`): PASS 10/10,
  **mismo checkpoint reutilizado**, `C-C3-006`: 126/126 idénticos en
  sustancia, 0 cambios reales.
- Corrida 3, `--rerun` otra vez (`f283cfa93b2c48248a3300e382c1769c`, ~5 h
  después): **gate BLOCK en `C-C3-006`** — 125/126 idénticos, **1 cambio
  real** en `EMPRESA_PAGE`. No es un defecto: es el mecanismo detectando que
  CNV publicó contenido nuevo entre la corrida 2 y la 3 (mismo fenómeno que
  `CNV_REVIEW.md` documentó para CEPU en el ciclo anterior — la página
  empresa es un recurso vivo). El resto de los checks (`002` integridad RAW,
  `007` identidad, `010` scope) siguieron en PASS; solo el que mide
  "sustancia sin cambios" falló, correctamente, porque hubo un cambio.

**Idempotencia ejecutada dos veces, como pide el mandato — y las dos veces
con un resultado correcto distinto**: la primera confirma "no hay falsos
positivos" (0 cambios cuando no los hay); la segunda confirma "no hay falsos
negativos" (1 cambio detectado cuando sí lo hay). Ninguna de las dos por sí
sola demuestra ambas propiedades.

### GGAL, BMA, CUIT inexistente — bloqueo comprobado en vivo

Para los 3, se confirmó con **el CLI real** (no solo con lectura de código):

```
$ python scripts/engine/c3_cnv_fetch.py --cuit 30704962807 --scope EEFF_PROPIO
BLOCK identidad [CUIT_NO_VERIFICADO]: GRUPO FINANCIERO GALICIA S.A.: el CUIT
30704962807 esta en estado CANDIDATE, no VERIFIED. La ingesta CNV exige una
assertion ratificada; atribuir documentos con un CUIT candidato es
exactamente la atribucion cruzada que hay que evitar.

$ python scripts/engine/c3_cnv_fetch.py --cik 0001347426 --scope EEFF_PROPIO
BLOCK identidad [SIN_CUIT]: Macro Bank Inc. (E01M14AP85T67281AA83Z87FMEJ) no
tiene identificador CUIT vigente en identity_v1. Sin CUIT no hay perfil CNV.

$ python scripts/engine/c3_cnv_fetch.py --cuit 20111111112 --scope EEFF_PROPIO
BLOCK identidad [NO_ESTA_EN_IDENTITY_V1]: CUIT 20111111112 no tiene entidad
vigente en identity_v1. C3 no crea identidades: pertenece a Identity.
```

Confirmado además, por query directa (no por confiar en el mensaje):
**0 filas** en `fetch_raw.cnv_download_log` para `cuit IN
('30704962807','0001347426','20111111112')`. No se creó ningún `run_id`
(`load_identity()` aborta antes de `start_run()`). No se usó ningún fallback
legacy: `identity.entities` solo se consulta DESPUÉS de que `identity_v1` ya
resolvió, y únicamente para contrastar — nunca decide.

---

## FASE D — Adversarial

10 ataques, cada uno con garantía atacada / resultado esperado / resultado
real / barrera concreta. Detalle completo: `CNV_MULTIEMPRESA_ADVERSARIAL.json`.

| # | Ataque | Resultado | Barrera |
|---|---|---|---|
| 1 | CUIT de otra empresa (CEPU→YPF) | RECHAZADO | `ux_identifier_autoritativo_unico` + conflicto abierto |
| 2 | CUIT inválido (checksum) | RECHAZADO | `cuit_valido()` módulo 11 |
| 3 | Entity sin CUIT VERIFIED (GGAL, BMA) | BLOCK en vivo, 0 escrituras | `resolver_en_identity_v1()` → `SystemExit` antes de `start_run()` |
| 4 | Identidad por ticker | RECHAZADO | `val.normalize_cuit()`, formato, antes de tocar identity_v1 |
| 5 | Identidad por nombre | ausente por diseño | revisión estática: 0 caminos de matching por nombre |
| 6 | Modificar CUIT/provenance post-fetch | RECHAZADO | permiso denegado sobre `identity_v1.assertion` |
| 7 | Insertar presentación con entity incorrecta | **SIN BARRERA** | `fetch_raw.cnv_download_log.entity_key` es TEXT libre, sin FK ni CHECK de coherencia |
| 8 | Alterar hash persistido | **SIN BARRERA** (mitigación solo posterior) | `catalaxia_engine` tiene UPDATE sobre `fetch_raw.*` |
| 9 | Fetch con identidad incompleta | BLOCK en vivo (`SIN_CUIT`, `NO_ESTA_EN_IDENTITY_V1`) | idem #3; `AMBIGUO` existe en código pero es inalcanzable en la práctica |
| 10 | Repetir la misma corrida | CONFIRMADO (2 veces, en TGSU2) | `canonical_sha256` + checkpoint-reuse |

**8/10 con barrera real confirmada. 2 hallazgos reales, no maquillados** (#7 y
#8): ambos comparten la misma causa raíz — `fetch_raw.*` no tiene ninguna de
las protecciones de escritura que `identity_v1` sí tiene (ni FK de coherencia,
ni triggers de inmutabilidad, ni restricción de UPDATE). Hoy la integridad de
`fetch_raw` depende enteramente de que el único código que escribe ahí
(`c3_cnv_fetch.py`) se porte bien — no de que la base lo exija.

---

## FASE E — Auditoría independiente

`scripts/engine/cnv_validation_auditor.py` (ya existía de la sesión anterior,
re-corrido ahora con los datos de hoy) — **no importa** el fetcher ni
`engine/cnv/*`. Reimplementa dígito verificador, sha256 desde disco, y todas
las queries de atribución/duplicados/provenance. Resultado completo:
`CNV_MULTIEMPRESA_AUDIT.json`.

| Verificación | YPF | CEPU | TGSU2 | Control (`99999999999`) |
|---|---|---|---|---|
| CUIT (checksum) | PASS | PASS | PASS | FAIL (esperado: es inválido) |
| Identity (conocido, ≤1 entidad) | PASS/PASS | PASS/PASS | PASS/PASS | FAIL/PASS (esperado: no existe) |
| Duplicados | PASS (0) | PASS (0) | PASS (0) | PASS (0) |
| Provenance completa y coherente | PASS/PASS | PASS/PASS | PASS/PASS | PASS/PASS (0=0) |
| Atribución (0 mezcla cruzada) | PASS | PASS | PASS | PASS |
| Cantidad manifest==disco | **FAIL** (histórico) | **FAIL** (histórico) | **FAIL** (histórico) | PASS (0=0) |
| Hash recalculado vs disco | **FAIL** (histórico, 0 mismatch) | **FAIL** (histórico, 0 mismatch) | **FAIL** (histórico, 0 mismatch) | PASS (0=0) |

**Contaminación cruzada: 0 casos en las 3 empresas reales** (verificado
independientemente, no es una afirmación del fetcher). **Duplicados: 0**.
**Idempotencia: confirmada de forma independiente** cruzando `canonical_sha256`
entre corridas consecutivas del mismo `(artifact_kind, artifact_key)` — no se
confió únicamente en el veredicto que el propio `c3_cnv_fetch.py` imprime.

**El único hallazgo real de esta fase (ya visto en la sesión anterior, aquí
reconfirmado con TGSU2 sumado)**: la mayoría del RAW histórico (de antes de
hoy) no existe físicamente en disco, aunque la base lo sigue listando como
`DOWNLOADED`, con 0 mismatch en lo que sí sobrevive. **No es un defecto de
identidad ni de atribución** — es exclusivamente un problema de retención de
RAW, ya señalado como F-008 antes de esta sesión, no nuevo.

---

## FASE F — Dictamen

```
CNV_VALIDATION_GATE = PASS_WITH_WARNINGS
```

Ver `CNV_MULTIEMPRESA_GATE.md` para el detalle segmentado y la clasificación
completa de hallazgos (defectos reales / limitaciones de evidencia / datos
faltantes / casos correctamente bloqueados / warnings no bloqueantes).

**Ningún finding se cerró por cuenta propia.** F-007, F-008 (ya abiertos) no
se tocaron. Los 2 hallazgos nuevos de esta sesión (#7 y #8 de Fase D) se
documentan como abiertos, sin decidir su remediación — cambiar permisos de un
rol compartido con SEC/Market no es una decisión que corresponda a esta
validación.
