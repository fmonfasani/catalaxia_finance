# IDENTITY V1 — CERTIFICACIÓN INDEPENDIENTE (CICLO 5)

**Fecha:** 2026-08-25
**Objeto:** schema `identity_v1` en `catalaxia-engine-dev` (127.0.0.1:5433) + piloto de 4 emisores
**Método:** ataque directo a la base. Sin importar `engine/identity_v1.py`, sin correr `tests/test_identity_v1.py`.

# VEREDICTO: `IDENTITY_V1_BLOCKED`

---

## 0. Declaración de conflicto de interés — LEER PRIMERO

El ciclo 5 pide **auditar independientemente** un componente y, en la misma consigna,
**no auditar código propio**. Ambas cosas no se pueden cumplir a la vez: Identity v1 lo
implementó este mismo agente en el ciclo 4.

**Esta auditoría no es independiente en el sentido organizativo.** Lo que sí se hizo, y es
lo máximo que el rol permite:

- **no se leyó el código de aplicación como fuente de verdad.** Todos los controles se
  atacaron con SQL crudo contra la base desplegada;
- **no se corrieron los tests del implementador.** Se escribió un banco de ataque nuevo
  (`docs/review/identity_v1_audit.sql`, `identity_v1_audit_pass2.sql`);
- **no se leyó la migración `.sql` como especificación.** El inventario de constraints,
  triggers e índices se sacó de `pg_catalog` / `pg_proc.prosrc`, que es lo desplegado;
- los hallazgos **contradicen documentación que el implementador escribió**, incluida una
  afirmación central suya que resultó falsa (F-018) y un conteo suyo equivocado por ~615×
  (F-020).

Aun así: **una revisión humana o de otro agente sigue siendo necesaria.** Este documento es
evidencia, no absolución.

---

## 1. Resumen ejecutivo

| | |
|---|---|
| Ataques ejecutados | **47** (36 en la pasada 1, 11 en la pasada 2) |
| Controles confirmados presentes | **26** |
| Huecos confirmados | **11 defectos distintos** |
| Findings emitidos | **F-015 … F-024** (3 HIGH, 5 MEDIUM, 1 LOW, 1 HIGH externo) |
| Estado del piloto tras la auditoría | **intacto** (4 entidades / 16 assertions / 12 identifiers) |

**Lo que sí funciona, verificado contra la base y no contra la palabra del implementador:**

> El pairing **YPF + CUIT 33650305499** es **RECHAZADO POR LA BASE**, independientemente
> de la aplicación:
> `ERROR: duplicate key value violates unique constraint "ux_identifier_autoritativo_unico"`

Lo mismo en el sentido inverso (CEPU + CUIT de YPF) y con terceros (GGAL + CUIT de TGSU2).
El error histórico que originó todo este trabajo **está efectivamente cerrado a nivel schema.**

**Por qué igual se bloquea:** la garantía central que el implementador declara —
*"no existe un identificador autoritativo sin cita reproducible y sin responsable"* — es
**falsa en el estado desplegado**. Una assertion vigente puede reescribirse, reapuntarse a
otra entidad y promoverse de `REVIEW_REQUIRED` a `VERIFIED` sin dejar rastro (F-015). Y el
golden case atribuye a una persona nombrada una decisión humana que nunca ocurrió (F-016).

---

## 2. Inventario del schema desplegado (`pg_catalog`, no el `.sql`)

```
tablas: assertion(18c) conflict(11c) entity(7c) identifier(11c)
        instrument(11c) instrument_symbol(6c) review(12c) source(7c)
vista : v_entity_resolution
CHECK ck_*        : 9    (+12 CHECK de dominio de enum)
FK                : 12   · identifier.assertion_id es NOT NULL  ✔
índices únicos parciales: 3
   ux_identifier_autoritativo_unico  (id_type,id_namespace,id_value) WHERE is_authoritative AND valid_to IS NULL
   ux_entity_un_autoritativo_por_tipo(entity_key,id_type,id_namespace) WHERE is_authoritative AND valid_to IS NULL
   ux_symbol_vigente                 (id_namespace,symbol) WHERE valid_to IS NULL
triggers          : 3
   tg_assertion_inmutable      BEFORE UPDATE ON assertion
   tg_no_borrar_vigente        BEFORE DELETE ON assertion
   tg_identifier_autoritativo  BEFORE INSERT OR UPDATE ON identifier
```

Coincide con lo documentado. **El schema documentado es el schema desplegado.** ✔

---

## 3. Banco adversario — pasada 1 (36 ataques)

Cada ataque en un savepoint de plpgsql que se revierte siempre. `[OK]` = rechazado por la
base; `[HUECO]` = aceptado.

### Los 13 ataques exigidos por la consigna

| # | Ataque | Resultado | Mecanismo |
|---|---|---|---|
| 1 | YPF + CUIT de CEPU | **[OK] RECHAZADO** | `ux_identifier_autoritativo_unico` |
| 2 | CEPU + CUIT de YPF | **[OK] RECHAZADO** | `ux_identifier_autoritativo_unico` |
| 3 | GGAL + CUIT de TGSU2 | **[OK] RECHAZADO** | `ux_identifier_autoritativo_unico` |
| 4 | TICKER como identidad | **[OK] RECHAZADO** | `ck_ticker_no_autoritativo` |
| 5 | TICKER/US vs TICKER/BYMA | **[OK]** conviven, ninguno autoritativo | namespaces separados |
| 6 | identificador autoritativo duplicado | **[OK] RECHAZADO** | `ux_identifier_autoritativo_unico` |
| 7 | procedencia ausente | **[OK] RECHAZADO** | `assertion_id NOT NULL` |
| 8 | `VERIFIED` sin evidence | **[OK] RECHAZADO** | `ck_verified_exige_evidencia` |
| 9 | `REVIEW_REQUIRED` → `VERIFIED` sin revisor | **[HUECO] ACEPTADO** | **F-015** |
| 10 | CIK contradictorio | **[OK] RECHAZADO** | `ux_entity_un_autoritativo_por_tipo` |
| 11 | CUIT contradictorio | **[OK] RECHAZADO** | `ux_entity_un_autoritativo_por_tipo` |
| 12 | eliminar procedencia histórica | **[HUECO] ACEPTADO** | **F-017** |
| 13 | modificar assertion vigente sin historial | **[HUECO] ACEPTADO** | **F-015** |

**3 de los 13 ataques exigidos produjeron `VERIFIED` silencioso o pérdida de historia.**
La consigna dice: *"Cada ataque debe producir REJECTED o REVIEW_REQUIRED. Nunca VERIFIED
silencioso."* Ese criterio **no se cumple**.

### Ataques adicionales del auditor

| # | Ataque | Resultado |
|---|---|---|
| 04b | `YF_SYMBOL` autoritativo | [OK] `ck_ticker_no_autoritativo` |
| 07b | identificador autoritativo colgado de assertion `CANDIDATE` | [OK] `tg_identifier_autoritativo` |
| 08b | `VERIFIED` sin `source_id` ni `resolved_by` | [OK] `ck_verified_exige_evidencia` |
| 08c | `DERIVED_RULE` declarada `AUTHORITATIVE` | [OK] `ck_authoritative_metodo` |
| 09a | cerrar review sin reviewer | [OK] `ck_cierre_exige_reviewer` |
| 09b | escribir el CUIT autoritativo con la review ABIERTA | **[HUECO]** F-019 |
| 11b | CUIT con checksum inválido | **[HUECO]** F-018 |
| 11c | CUIT `"no-soy-un-cuit"` | **[HUECO]** F-018 |
| 12a | borrar assertion vigente `VERIFIED` | [OK] `tg_no_borrar_vigente` |
| 12c | borrar assertion `REVIEW_REQUIRED` vigente | **[HUECO]** F-017 |
| 12d | borrar la review ABIERTA de GGAL | **[HUECO]** F-017 |
| 12e | borrar un conflict abierto | **[HUECO]** F-017 |
| 13d | reapuntar un *identifier* vigente a otra entidad | [OK] `ux_entity_un_autoritativo_por_tipo` |
| E1 | instrumento sin assertion | **[HUECO]** F-021 |
| E2 | ADR sin `ratio_underlying` | [OK] `ck_ratio_obligatorio` |
| E3 | `entity_key` = `'YPF'` | [OK] `entity_entity_key_check` |
| E4 | fuente inventada | [OK] FK a `source` |
| E5 | bridge con un solo extremo | [OK] `ck_bridge_dos_extremos` |
| E6 | `HUMAN_DECISION` sin motivo | [OK] `ck_humano_exige_autor` |
| E7 | mismo símbolo YAHOO en dos instrumentos | [OK] `ux_symbol_vigente` |

---

## 4. Pasada 2 — desambiguación (11 ataques)

Tres resultados de la pasada 1 no eran concluyentes y **dos eran defectos de mi propio
banco de ataque.** Se rehicieron:

| Problema de la pasada 1 | Corrección | Resultado real |
|---|---|---|
| 12b / 13c usaban un **CTE** que cerraba y borraba/modificaba la assertion en la *misma* sentencia. Las dos ramas ven el mismo snapshot, así que la segunda pudo no tocar ninguna fila y "pasar" de forma vacua | sentencias separadas | **13c → [OK] RECHAZADO.** Era un **falso positivo mío**: modificar una assertion histórica **sí** está bloqueado. **12b → [HUECO] confirmado**: borrarla **no** lo está |
| 11d "CIK inválido" fue rechazado por `ux_entity_un_autoritativo_por_tipo` (GGAL ya tenía CIK), no por un control de formato — no probaba nada | entidad nueva sin identificadores | **[HUECO]**: no hay validación de formato |
| La entidad de prueba del auditor `E01AUDITCICLO5…` fue rechazada por `entity_entity_key_check` | clave ULID válida | el CHECK del `entity_key` **funciona** (rechazó al auditor) |

### Resultados de la pasada 2

| # | Ataque | Resultado |
|---|---|---|
| P2-01 | `CIK = "YPF"` (texto) | **[HUECO] ACEPTADO** |
| P2-02 | `CIK = "42"` (sin zero-padding) | **[HUECO] ACEPTADO** |
| P2-03 | `CUIT = "no-soy-un-cuit"` | **[HUECO] ACEPTADO** |
| P2-04 | `CUIT = "99999999999"` (checksum malo) | **[HUECO] ACEPTADO** |
| P2-05 | `LEI = "no-es-un-lei"` | **[HUECO] ACEPTADO** |
| P2-06 | `CUIT = "30-54668997-9"` (con guiones) | **[HUECO] ACEPTADO** |
| P2-07 | modificar assertion histórica | **[OK] RECHAZADO** `tg_assertion_inmutable` |
| P2-08 | **borrar** assertion histórica | **[HUECO] ACEPTADO** |
| P2-09 | cambiar status de histórica a `REJECTED` | **[OK] RECHAZADO** |
| P2-10 | `superseded_by` apuntando a sí misma | **[HUECO] ACEPTADO** |
| P2-11 | `valid_to = '1900-01-01'` | **[HUECO] ACEPTADO** |

P2-06 merece atención: **el mismo CUIT con y sin guiones puede coexistir como dos
identificadores autoritativos distintos**, porque la unicidad se evalúa sobre el texto y la
normalización vive sólo en Python. Es una vía directa para volver a partir una identidad en dos.

---

## 5. Golden cases — verificación independiente

```
                                   CIK          CUIT          LEI                   rev  conf
CENTRAL PUERTO S.A.                0001717161   33650305499   2549005JLIWQ6B7VNR38   1    0
GRUPO FINANCIERO GALICIA S.A.      0001114700   (vacío)       5299008H3AXIXV5G3C23   2    0
TRANSPORTADORA DE GAS DEL SUR S.A. 0000931427   30657862068   5299002TRC7IFQYSW596   1    0
YPF SOCIEDAD ANONIMA               0000904851   30546689979   5493003N7447U18U5U53   1    0
```

Los cuatro CIK y los tres CUIT coinciden con los valores exigidos por la consigna. GGAL sin
CUIT y con review abierta — **correcto**, no es una falla.

### CNV: YPF **no** tiene golden case completo de 4 fuentes

Verificado, no heredado:

| Emisor | SEC | GLEIF | CNV | Market | presentaciones CNV |
|---|---|---|---|---|---|
| CENTRAL PUERTO | 1 | 2 | **1** | 2 | **9.305** |
| GGAL | 1 | 1 | 0 | 2 | 0 |
| TGSU2 | 1 | 2 | 0 | 2 | 0 |
| **YPF** | 1 | 2 | **0** | 2 | **0** |

**Solo CEPU recorre las cuatro fuentes.** La declaración del implementador es exacta y no
se convierte en PASS por herencia.

### F-014 (MARKET) — remediación verificada

```sql
SELECT count(*) FROM identity_v1.instrument_symbol
 WHERE id_namespace='US' AND symbol IN ('YPFD','TGSU2');
--> 0
```

Los instrumentos de NYSE conservan **solo** el símbolo respaldado por Market/Yahoo
(`YAHOO/YPF`, `YAHOO/TGS`, `YAHOO/CEPU`, `YAHOO/GGAL`), y la ausencia de ticker US genera
las reviews #1, #2, #4 y #5. **No hay inferencia.** F-014 remediado en Identity v1. ✔
(El defecto de origen en `market_instruments` sigue OPEN, como corresponde.)

### Provenance de los bridges `VERIFIED`: reconstruible pero **semánticamente falsa**

Los 7 campos exigidos están presentes en los 4 bridges:

```
identifier : CIK:SEC:0000904851  ↔  LEI:GLEIF:5493003N7447U18U5U53
source     : HUMAN               source_record: docs/architecture/IDENTITY_DECISION_RECORD.md#G5
evidence   : GLEIF …/lei-records/5493003N7447U18U5U53 · legalName='YPF Sociedad Anonima' …
method     : HUMAN_DECISION      resolver: fmonfasani
timestamp  : 2026-08-25 20:20:17.821262+00   status: VERIFIED
```

**Dos objeciones, ambas materiales:**

1. La `evidence` cita **únicamente el registro GLEIF** — es decir, el lado LEI. No contiene
   nada del lado CIK. **No demuestra el puente**: reproduce lo que GLEIF dice del LEI y
   afirma la correspondencia sin respaldarla.
2. `resolved_by = 'fmonfasani'` y `resolution_reason = 'cierre manual…'` los escribió el
   **script**, en bucle, con el mismo texto para los 4 emisores, en el mismo microsegundo
   (`valid_from` idéntico). **Ninguna persona revisó estos bridges.** → **F-016**

---

## 6. Idempotencia y reproducibilidad

| Prueba | Resultado |
|---|---|
| `entity_key` estable entre corridas | **NO.** Corrida 1: `E01M0X94S5BGQFKYV1BY9TG6B49`; corrida 2: `E01M0X99C8F87H9TH9N39H2D1NW` (ULID aleatorio) |
| Re-ejecutar el piloto sin `--reset` | **ABORTA** — `duplicate key ... "instrument_pkey" ... (MKT:83)` |
| ¿La corrida fallida dejó residuo? | **No.** Rollback limpio: 4 / 16 / 12, 0 entidades sin identificador ✔ |

La transacción está bien delimitada. Pero **el piloto no es idempotente ni reproducible**, y
un `entity_key` aleatorio por corrida impide cualquier `state_digest` estable sobre
`identity_v1` — lo que choca de frente con F-013 (semántica de checkpoint). → **F-023**

---

## 7. D-I-04 — auditoría de la propuesta de backfill: **BLOCK**

### La premisa del implementador es un error de conteo

Afirma: *"el backfill produciría del orden de **8.000 `REVIEW_REQUIRED`** por el puente
CIK↔LEI"*. Medido sobre la población real:

```
dim_entity (573)          total  con_CUIT  con_CIK  con_AMBOS
  adr                        18        18       13        13
  byma_only                  56        56        0         0
  sp500                     499         0      499         0

identity.entities (7.998): 7.998 con CIK · 0 con CUIT · 0 con country
identity.identifiers     : TICKER 10.414 · YF_SYMBOL 10.414 · CIK 7.998 · LEI 0
```

El puente CIK↔LEI **sólo hace falta donde una entidad tiene CIK y además necesita CUIT**:

| Población | Cuántas | ¿Necesita puente? |
|---|---|---|
| Sólo CIK (US, `sp500` + las 7.998 de SEC) | 499 + ~7.998 | **No.** El CUIT no aplica |
| Sólo CUIT (argentinas sin CIK, `byma_only` + 5 ADR) | 61 | **No.** No hay CIK que puentear |
| **CIK y CUIT** (`adr`) | **13** | **Sí** |

> **La población que necesita el puente es 13, no ~8.000.** La premisa está errada
> por un factor de ~615×, y con ella la urgencia de D-I-04. → **F-020**

### La regla propuesta es consistente, pero no es la decisión difícil

*"LEI opcional para US + CUIT sólo para emisores argentinos + LEI como bridge hacia CUIT
sólo donde corresponde"* — **es consistente con la arquitectura**: la autoridad ya es por
`id_type` en `identity_v1.source`, y `link_cuit_desde_gleif` sólo exige el puente cuando la
entidad tiene CIK autoritativo. No hace falta cambiar el modelo para adoptarla.

Pero resuelve un problema que **no existía a esa escala**. El problema real de escala es otro
y no está en el plan de migración:

### El riesgo real: **510 CIK solapados**

```
CIK en identity.entities (PostgreSQL) : 7.998
CIK en dim_entity        (SQLite)     :   512
SOLAPAMIENTO                          :   510
```

510 entidades están **en las dos fuentes**. Migradas como entidades separadas producen
**510 conflictos de CIK duplicado** — y entre ellas están las 13 que llevan el CUIT. El plan
de migración no menciona el solapamiento ni define la regla de fusión. → **F-020**

### Una mina en los datos de origen

```
entity_id=572  ticker='BMA'  grupo='adr'  cuit='0001347426'  cik=NULL
```

Banco Macro tiene **un CIK guardado en la columna `cuit`** (10 dígitos, zero-padded) y `cik`
vacío. Es el único de los 74 CUIT del legacy que falla el módulo 11 — **y es exactamente el
error de categoría que Identity v1 existe para impedir, esperando en los datos que la Fase 2
importaría.** Combinado con F-018 (sin validación en la base), entraría como CUIT
autoritativo si la fuente se declarara autoritativa. → **F-024**

**Veredicto D-I-04: BLOCK.** No por la regla propuesta, que es sana, sino porque la decisión
está planteada sobre un conteo equivocado, el riesgo real (510 solapamientos) no está
evaluado, y los datos de origen tienen un identificador en el campo equivocado.

---

## 8. Cobertura por área auditada

| # | Área | Resultado |
|---|---|---|
| 1 | Schema | **PASS** — lo desplegado coincide con lo documentado |
| 2 | Constraints | **PASS** — 9 `ck_*` presentes y efectivos |
| 3 | Triggers | **WARN** — los 3 existen; `tg_assertion_inmutable` sólo cubre filas históricas (F-015); `tg_no_borrar_vigente` no cubre históricas ni `REVIEW_REQUIRED` (F-017) |
| 4 | Índices únicos parciales | **PASS** — los 3 funcionan; cierran el error histórico |
| 5 | Provenance | **FAIL** — estructuralmente completa, reescribible en vigente (F-015) y falsa en el golden case (F-016) |
| 6 | Assertions | **WARN** — el modelo es correcto; la inmutabilidad es parcial |
| 7 | Review workflow | **FAIL** — el cierre exige revisor, pero la review abierta no bloquea nada (F-019) y es borrable (F-017) |
| 8 | Conflict handling | **WARN** — se abren bien; son borrables sin rastro (F-017) |
| 9 | Identifier namespaces | **PASS** — `TICKER/US` ≠ `TICKER/BYMA` verificado |
| 10 | Entity relationships | **PASS** — FK completas; `entity_key` opaco validado por CHECK |
| 11 | Historical validity | **WARN** — modificar histórica: bloqueado ✔; borrarla: no (F-017) |
| 12 | Idempotency | **FAIL** — re-ejecutar aborta (F-023) |
| 13 | Reproducibility | **FAIL** — `entity_key` aleatorio por corrida (F-023) |
| 14 | Backfill behavior | **BLOCK** — F-020, F-024 |

---

## 9. Findings emitidos

| ID | Sev | Componente | Titular |
|---|---|---|---|
| **F-015** | **HIGH** | `identity_v1.assertion` | Una assertion **vigente** puede reescribirse, reapuntarse y promoverse sin dejar historia |
| **F-016** | **HIGH** | `identity_v1_pilot.py` | Se atribuye a una persona nombrada una decisión humana que nunca ocurrió |
| **F-017** | **HIGH** | `identity_v1` (DELETE) | Procedencia histórica y gobernanza son borrables sin rastro |
| **F-018** | MEDIUM | `identity_v1.identifier` | Sin validación de formato ni checksum en la base para CIK/CUIT/LEI |
| **F-019** | MEDIUM | review workflow | Una review ABIERTA no bloquea la escritura del identificador que gobierna |
| **F-020** | MEDIUM | D-I-04 | Premisa errada por ~615×; el riesgo real (510 CIK solapados) sin evaluar |
| **F-021** | MEDIUM | `identity_v1.instrument` | `assertion_id` nullable: instrumentos sin procedencia |
| **F-022** | LOW | `identity_v1.assertion` | `superseded_by` auto-referenciable; `valid_to` retro-fechable |
| **F-023** | MEDIUM | `identity_v1_pilot.py` | No idempotente ni reproducible |
| **F-024** | **HIGH** | `dim_entity` (legacy) | CIK guardado en la columna `cuit` (BMA, entity 572) |

Detalle completo con `evidence` / `impact` / `owner` / `required_action` / `acceptance_test`
en `docs/review/FINDINGS.md`.

---

## 10. Qué hace falta para levantar el BLOCK

Condiciones de salida, todas verificables contra su `acceptance_test`:

1. **F-015 cerrado.** Una assertion vigente `VERIFIED` no puede cambiar `evidence`,
   `entity_key`, `source_id`, `status` ni `confidence` por `UPDATE`. El camino es
   supersedencia, no edición.
2. **F-017 cerrado.** `DELETE` prohibido sobre `assertion`, `review` y `conflict` en todos
   los estados relevantes, no sólo `VERIFIED`/`CANDIDATE` vigentes.
3. **F-016 cerrado.** Los 4 bridges del piloto: o los ratifica una persona con evidencia
   propia de cada uno, o se degradan a `REVIEW_REQUIRED` y `resolved_by` deja de nombrar a
   alguien que no decidió.
4. **F-018 cerrado.** Formato y checksum validados **en la base**.
5. **D-I-04 re-presentado** sobre la población real (13 puentes, 510 solapamientos) con
   regla de fusión definida.

Los ítems 1, 2 y 4 son `CHECK`/trigger: horas de trabajo, no rediseño. **El modelo
conceptual de Identity v1 es sólido y el error histórico está cerrado.** Lo que falta es que
las garantías declaradas sean ciertas en el schema, no sólo en Python.

---

## 11. Alcance y honestidad del método

- **Cero modificaciones** a `identity_v1`, a `engine/`, a `tests/` o a `migrations/`.
  Escrituras únicamente en `docs/review/`.
- Los 47 ataques corrieron en transacciones revertidas. Estado final verificado idéntico al
  inicial: **4 entidades / 16 assertions / 12 identifiers / 5 reviews abiertas / 0 conflicts.**
- Una corrida del piloto sin `--reset` (prueba de idempotencia) abortó y revirtió limpio; se
  verificó que no dejó residuo.
- **Correcciones registradas del propio auditor: 2.** El ataque 13c fue un falso positivo por
  usar un CTE; la entidad de prueba `E01AUDITCICLO5…` fue rechazada por el CHECK del
  `entity_key` y hubo que rehacerla. Ambas se corrigieron en la pasada 2 y se dejan escritas
  porque la primera habría producido un finding inexistente.
- **Ningún finding se cierra en este ciclo.** No se declara `READY_FOR_CANONICAL_LAYER`.
