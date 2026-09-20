# IDENTITY_CNV_AUTHORITY_CONTRACT_AUDIT

**Fecha:** 2026-09-01 · **Rol:** Auditor de sólo lectura
**Propósito:** especificación definitiva que habilitará la implementación posterior
**No se modificó código, base, constraints, statuses, `valid_to`, assertions, CNV ni RAW.**
**No se ejecutó `VALIDATE CONSTRAINT`.**

---

## 1. HECHOS

### 1.1 · El modelo de autoridad es coherente. Los cinco controles estructurales dan limpio.

| # | control | resultado |
|---|---|---|
| 1 | assertion `VERIFIED` + identifier **no** autoritativo | **0** |
| 2 | identifier autoritativo + assertion **≠** `VERIFIED` | **0** |
| 3 | identifier autoritativo + `status ≠ ACTIVE` **y vigente** | **0** |
| 4 | identifier autoritativo con `valid_to` cerrado | 9, **todos correctamente cerrados** |
| 5 | más de un CUIT autoritativo `ACTIVE` vigente por entidad | **0** |

**El invariante 14 se cumple, y también su recíproco**, que el modelo no
garantiza formalmente: hoy no existe ninguna assertion `VERIFIED` sobre un
identificador no autoritativo.

### 1.2 · La supersesión funciona: cierra las tres cosas a la vez

Las 9 filas del control 4 son supersesiones correctas:

```
CIK   status=RETIRED    6 filas   cerradas 2026-08-28   vigentes: 0
CUIT  status=DISPUTED   3 filas   cerradas 2026-08-26   vigentes: 0
```

Cuando una fila autoritativa se supersede, se le pone `valid_to` **y** se mueve
`status` a `RETIRED`/`DISPUTED`. No quedan autoritativas vigentes con estado
anómalo.

### 1.3 · El universo real es de 17 CUIT, no de 56

```
filas CUIT vigentes ............ 56
CUIT DISTINTOS vigentes ........ 17     <-- el número que importa
CUIT autoritativos ACTIVE ......  3
```

**Corrección a informes previos**, incluido el mío: los «53 candidatos» son
**filas**, no empresas. El universo de CUIT distintos no autoritativos es de
**14**, no de 53. Cualquier piloto negativo tiene ahí su techo real.

### 1.4 · Las dos reglas de elegibilidad dan el mismo resultado HOY

```
regla ACTUAL     max(assertion.status) = 'VERIFIED'   ->  3 entidades
regla PROPUESTA  is_authoritative AND status='ACTIVE' ->  3 CUIT
```

La coincidencia es **fáctica, no estructural**. Ver §3.1.

---

## 2. EVIDENCIA

### 2.1 · El CHECK `NOT VALID` — 3 violaciones, todas históricas

Consulta equivalente a la validación completa, **sin ejecutar `VALIDATE`**:

```
assertions con left_ref LIKE 'CUIT:%' AND status='VERIFIED' ......... 6
que violarían ck_cuit_exige_evidencia_estructurada .................. 3
```

| assertion_id | source_id | resolved_by | `source_facts` |
|---|---|---|---|
| 4 | GLEIF | `proc:gleif_fetch` | **(null)** |
| 8 | GLEIF | `proc:gleif_fetch` | **(null)** |
| 16 | GLEIF | `proc:gleif_fetch` | **(null)** |

Las tres son las assertions de los identificadores `DISPUTED` **ya cerrados el
2026-08-26** (ids 3, 6, 12 de §1.2). **Ninguna está vigente.** Las tres
autoritativas actuales —345, 346, 347— satisfacen el constraint.

**Consecuencia operativa:** ejecutar `VALIDATE CONSTRAINT` hoy **fallaría**, y
fallaría por filas que el propio modelo ya superseció. No es un defecto de datos
vivos.

### 2.2 · Los 8 grupos duplicados — completos

| CUIT | filas | estados | evidencias distintas | fuentes | registros | confianzas | entity_key |
|---|---:|---|---:|---:|---:|---:|---|
| 30546689979 | 7 | CANDIDATE | 1 | 1 | 1 | 1 | `E01M0X99C8F87H9TH9N39H2D1NW` |
| 33650305499 | 7 | CANDIDATE | 1 | 1 | 1 | 1 | `E01M0X99DQ7P5TQ4Z6Z58RC5PB3` |
| 30704962807 | 7 | CANDIDATE | 1 | 1 | 1 | 1 | `E01M0X99EXSQTYKWZMDEMMBX8QY` |
| 30657862068 | 7 | CANDIDATE | 1 | 1 | 1 | 1 | `E01M0X99G29RBSSFSGAM5S1QZMT` |
| 30696170580 | 2 | CANDIDATE | 1 | 1 | 1 | 1 | `E01M13XBSB1SNWTM8WJ512Z329H` |
| 30500001735 | 2 | CANDIDATE | 1 | 1 | 1 | 1 | `E01M13XBSD0VA2QVCX4VNT1SGV9` |
| 33500005179 | 2 | CANDIDATE | 1 | 1 | 1 | 1 | `E01M13XBSFF6T7J5X49T9FWG30E` |
| 30714128309 | 2 | CANDIDATE | 1 | 1 | 1 | 1 | `E01M13XBSHZ6D5QT5SRETQQMJ80` |

**Veredicto: los 8 son duplicados SEMÁNTICOS, no assertions legítimamente
distintas.** Cada grupo tiene **un solo valor distinto** en `evidence`,
`source_id`, `source_record` y `confidence`. Es la misma afirmación registrada N
veces, no N afirmaciones diferentes sobre el mismo hecho.

### 2.3 · Lo que el fetcher declara hoy

`c3_cnv_fetch.py`, docstring:

> «La autorización para ingerir es la assertion del CUIT en estado `VERIFIED`:
> si está `CANDIDATE`, la empresa queda bloqueada aunque su CUIT sea conocido y
> correcto.»

**La regla está declarada en términos de `assertion.status`, no de
`is_authoritative`.** El código es fiel a su propia documentación; lo que está
desalineado es esa documentación respecto del modelo de identidad.

---

## 3. INCONSISTENCIAS

### 3.1 · CNV decide por un eje que el modelo no usa para autoridad — y por `max()`

```sql
-- c3_cnv_fetch.py:68
max(CASE WHEN i.id_type = 'CUIT' THEN a.status::text END)  AS cuit_status
```

Tres problemas encadenados:

1. **No filtra `is_authoritative`.** El contrato dice: «Sólo los identificadores
   marcados `is_authoritative` pueden fundar una aserción `AUTHORITATIVE`».
2. **No mira `identifier.status`.** Una fila `DISPUTED` o `RETIRED` habilitaría
   igual, si estuviera vigente.
3. **`max()` alfabético.** Con `assertion_status_check` =
   `{UNRESOLVED, CANDIDATE, REVIEW_REQUIRED, VERIFIED, REJECTED}`, el orden es
   `CANDIDATE < REJECTED < REVIEW_REQUIRED < UNRESOLVED < VERIFIED`, de modo que
   `VERIFIED` gana siempre. **El resultado correcto sale de una propiedad del
   alfabeto, no de una regla.**

**S04 sí usa el mecanismo del modelo** (`resolver_entidad`:
`AND is_authoritative AND valid_to IS NULL`). CNV es el único consumidor
desalineado.

### 3.2 · Un invariante recíproco que no existe

El modelo garantiza **`autoritativo ⇒ VERIFIED`** (trigger
`tg_identifier_autoritativo`). **No garantiza `VERIFIED ⇒ autoritativo`.**

Hoy se cumple de hecho (control 1 = 0), pero nada lo impide. Bastaría una
assertion `VERIFIED` sobre un identificador CUIT no autoritativo para que la
regla actual de CNV habilite una descarga que el modelo **no autoriza**.

### 3.3 · El importador no es idempotente

8 grupos, 30 filas redundantes (4×6 + 4×1). No corrompe —ninguna es
autoritativa— pero **envenena todo conteo por filas**. Ya causó un incidente: el
piloto CNV pidió 20 filas creyendo pedir 20 empresas y recibió 3 CUIT distintos,
uno de ellos autoritativo, y disparó una descarga real.

---

## 4. RIESGOS

| # | riesgo | ¿produce dato incorrecto? | ¿se detecta? | probabilidad hoy |
|---|---|---|---|---|
| R1 | Una assertion `VERIFIED` sobre identificador no autoritativo habilita CNV | **sí** — ingesta no autorizada por el modelo | **no**, ningún control lo mira | **nula hoy** (0 casos), no impedida |
| R2 | Se agrega un estado al vocabulario que ordene después de `VERIFIED` | **sí** — invertiría `max()` | no | baja: requiere migración |
| R3 | Una fila autoritativa pasa a `DISPUTED` sin cerrarse | **sí** — CNV no mira `identifier.status` | no | nula hoy (control 3 = 0) |
| R4 | Un conteo por filas se toma por conteo de empresas | **sí, ya ocurrió** | — | **alta** mientras persistan los duplicados |
| R5 | `VALIDATE CONSTRAINT` falla y se interpreta como corrupción de datos vivos | no altera datos | — | media: 3 violaciones históricas |

---

## 5. CONTRATO PROPUESTO — elegibilidad CNV

### 5.1 · Enunciado

> Una entidad es **elegible para ingesta CNV** si y sólo si posee un
> identificador `CUIT` que cumple **las cuatro** condiciones:
>
> 1. `id_type = 'CUIT'`
> 2. `is_authoritative = TRUE`
> 3. `status = 'ACTIVE'`
> 4. `valid_to IS NULL`
>
> La `assertion` asociada **no se consulta para decidir**: el invariante 14 ya
> garantiza que un identificador autoritativo tiene assertion `VERIFIED`. Se
> registra en la provenance de la corrida, no en la decisión.

### 5.2 · Consulta

```sql
SELECT i.entity_key, i.id_value AS cuit, i.assertion_id
  FROM identity_v1.identifier i
 WHERE i.id_type = 'CUIT'
   AND i.is_authoritative
   AND i.status = 'ACTIVE'
   AND i.valid_to IS NULL
   AND i.entity_key = :entity_key
```

**Debe devolver exactamente una fila.** Cero → bloqueada. Más de una →
`AMBIGUO`, y se bloquea igual: el control 5 dice que hoy no pasa, y si pasara
sería un defecto de datos que no debe resolverse eligiendo.

### 5.3 · Por qué no `EXISTS(assertion.status = 'VERIFIED')`

Es mejor que `max()` —explícito en vez de lexicográfico— pero **sigue en el eje
equivocado**: pregunta por la afirmación en vez de por la autoridad. Deja abierto
R1 y R3.

### 5.4 · ¿Existe alguna razón contractual para NO usar `is_authoritative`?

**No se encontró ninguna.** Se revisaron `IDENTITY_ARCHITECTURE_V1.md`,
`IDENTITY_V1_SCHEMA.md`, `F024_CONTRATO.md`, `F037_CONTRATO.md`,
`CNV_VALIDATION_GATE.md` y el docstring del fetcher.

Lo único que apunta en otra dirección es **el docstring del propio
`c3_cnv_fetch.py`** (§2.3), que declara la regla en términos de
`assertion.status`. Es documentación del consumidor, no del modelo, y contradice
la «Regla de autoridad» de la arquitectura. **Debe actualizarse junto con el
código.**

---

## 6. CAMBIOS NECESARIOS — especificados, NO implementados

| # | cambio | archivo | riesgo |
|---|---|---|---|
| C1 | `resolver_en_identity_v1()`: reemplazar `max(a.status::text)` por la consulta de §5.2 | `c3_cnv_fetch.py` | **bajo** — mismo resultado hoy (3 = 3) |
| C2 | Nuevo motivo de rechazo `CUIT_NO_AUTORITATIVO`, distinto de `CUIT_NO_VERIFICADO` | ídem | ninguno |
| C3 | Motivo `AMBIGUO` si la consulta devuelve más de una fila | ídem | ninguno |
| C4 | Actualizar el docstring y el contrato de CNV al enunciado de §5.1 | ídem + `docs/architecture/` | ninguno |
| C5 | Hacer idempotente el importador de candidatos | `backfill_cik.py` / `legacy_import` | medio — define la clave de unicidad |

**C1 no cambia el comportamiento observable hoy.** Es la diferencia entre acertar
y garantizar.

---

## 7. INVARIANTES DE BASE PROPUESTOS

Ninguno se crea acá. Se especifican para decisión.

| # | invariante | forma | qué impide | ¿lo viola algo hoy? |
|---|---|---|---|---|
| **I1** | Un identificador `VERIFIED` debe ser autoritativo | trigger recíproco de `tg_identifier_autoritativo` | **R1** | **no** — 0 casos |
| **I2** | A lo sumo un identificador autoritativo vigente por `(entity_key, id_type)` | índice único parcial `WHERE is_authoritative AND valid_to IS NULL` | ambigüedad de autoridad | **no** — control 5 = 0 |
| **I3** | Un identificador autoritativo vigente debe tener `status = 'ACTIVE'` | CHECK o trigger | **R3** | **no** — control 3 = 0 |
| **I4** | Al cerrar `valid_to` de un autoritativo, `status` deja de ser `ACTIVE` | trigger | supersesión a medias | **no** — §1.2 |
| **I5** | Unicidad de candidato: `(entity_key, id_type, id_value, method, resolved_by, source_record)` vigente | índice único parcial | **R4** / duplicados | **sí — los 8 grupos** |

**I1 a I4 son gratis**: ninguna fila actual los viola, y todos cierran un riesgo
que hoy sólo está cerrado por casualidad.

**I5 requiere decidir antes qué hacer con las 30 filas redundantes** — ver D2.

---

## 8. TESTS NECESARIOS

| # | test | debe fallar si |
|---|---|---|
| T1 | Un CUIT autoritativo `ACTIVE` vigente ⇒ elegible | se rompe el camino positivo |
| T2 | Un CUIT `CANDIDATE` no autoritativo ⇒ `CUIT_NO_AUTORITATIVO`, **0 corridas, 0 requests** | reaparece el bypass |
| T3 | Un CUIT autoritativo pero `status='DISPUTED'` ⇒ bloqueado | se ignora `identifier.status` |
| T4 | Un CUIT autoritativo con `valid_to` cerrado ⇒ bloqueado | se ignora la vigencia |
| T5 | Dos autoritativos vigentes ⇒ `AMBIGUO`, **no se elige uno** | el resolver desempata solo |
| T6 | **Mutación**: quitar `is_authoritative` de la consulta ⇒ T2 falla | el test no prueba la barrera |
| T7 | Invariante: `count(*) = 0` en los controles 1, 2, 3, 5 de esta auditoría | regresión estructural |
| T8 | El piloto negativo **no puede** invocar el fetcher: espía con `fetch_calls = 0` incluso si el universo trae un autoritativo por error | vuelve el incidente |

T3, T4 y T5 **no se pueden escribir contra la base homologada**: no existen esos
casos. Requieren un schema temporal, como los tests de F-054.

---

## 9. DECISIONES PENDIENTES

| # | decisión | quién | bloquea |
|---|---|---|---|
| **D1** | ¿Se adopta el contrato de §5.1? | producto + arquitectura | C1–C4, T1–T8 |
| **D2** | Las 30 filas duplicadas: ¿se supersedan, se consolidan, o se aceptan como registro histórico? | producto | C5, I5 |
| **D3** | ¿Se crean I1–I4 ahora que ninguna fila los viola? | arquitectura | — |
| **D4** | Las 3 assertions históricas sin `source_facts`: ¿se completan, se marcan `REJECTED`, o el constraint queda `NOT VALID` de forma permanente y documentada? | arquitectura | `VALIDATE CONSTRAINT` |
| **D5** | ¿El docstring de CNV es normativo? Hoy contradice la arquitectura y nadie lo detectó hasta esta auditoría | arquitectura | C4 |

---

## 10. CONCLUSIÓN

**El modelo de identidad está sano.** Cinco controles estructurales en cero, la
supersesión cierra `valid_to` y `status` a la vez, y no hay ninguna entidad con
autoridad ambigua.

**Lo que falta no es corrección, es garantía.** Tres cosas hoy se cumplen por
casualidad y no por construcción:

- que ningún `VERIFIED` esté sobre un identificador no autoritativo (I1);
- que `VERIFIED` sea el máximo alfabético del vocabulario (R2);
- que CNV acierte pese a mirar el eje equivocado (§3.1).

Y una cosa está mal de verdad, aunque no produzca dato incorrecto: **el
importador duplica**, y ese defecto ya provocó un incidente real.

El cambio C1 no altera ningún resultado observable. Ése es exactamente el
argumento para hacerlo: **hoy es barato, y sólo lo es mientras siga siendo
cierto por casualidad.**
