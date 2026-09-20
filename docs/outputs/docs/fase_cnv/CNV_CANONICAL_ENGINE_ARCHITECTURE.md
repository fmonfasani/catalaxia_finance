# CNV Canonical Engine Architecture

**2026-09-02** · análisis arquitectónico · **sin modificar nada, sin ejecutar nada**
Todo lo afirmado sale de inspección del esquema y del código. Lo indeterminable va como `UNKNOWN`.

---

## 1. Executive Conclusion

# GENERALIZABLE CON CAMBIOS MENORES

Y el motivo es que **el acoplamiento a XBRL es mucho menor de lo que el análisis
previo sugería**. Siete de los ocho bloqueos aparentes se disuelven al leer el
código:

| bloqueo aparente | qué muestra la inspección |
|---|---|
| `source_kind` sólo admite XBRL | **NO hay CHECK sobre `source_kind`.** `CNV_EEFF` entra sin cambiar el esquema |
| `entity_key` es del mundo SEC | **FK a `identity_v1.entity`**, que sólo exige ULID + nombre. Agnóstica de fuente |
| identity no admite CUIT | **`id_type` ya admite `CUIT` y `CNV_ENTITY_ID`**, con validador propio |
| `context_id` es XBRL | **el ratio engine lo lee 0 veces.** Es de ingesta |
| `qname` es XBRL | el ratio engine lo usa **sólo como clave de comparación** en la guarda F-061; nunca lo interpreta |
| `source_hash` no existe en CNV | **56/56 documentos HTML de METR están en disco.** Es calculable |
| no hay abstracción de fuente | **`parsed.facts.entity_id` ya guarda `CIK:0000021344`** — namespaced. La abstracción existe y está sin usar |

**Queda un solo acoplamiento real: la columna `cik`.** Es `NOT NULL` en las dos
tablas y su *nombre* afirma semántica SEC. Su *función* es otra: clave del emisor
en el registro de la fuente.

**Ninguno de los cambios necesarios toca el ratio engine.**

---

## 2. Current Architecture

```
SEC/XBRL ──> S02 fetch ──> S03 parse ──> parsed.facts ──> S04 ──> derived.fact ──> ratio_engine ──> derived.ratio
                                              ▲                        ▲
                                    source_hash, qname,        entity_key (FK a identity_v1)
                                    context_id, entity_id      fact_key = sha256(...)

CNV/HTML ──> C3 fetch ──> fetch_raw.cnv_artifact ──> ✗ (no hay C4/C5)
             (legacy)  ──> cnv_estados_v2 ──> cnv_estados_norm ──> ratios_cnv   [SQLite]
```

Sin triggers en `parsed`/`derived`. Una sola vista: `derived.v_fact_pertenencia`.

---

## 3. `derived.fact` Contract

| Campo | Oblig. | Propósito real | Clase | Quién lo usa |
|---|:-:|---|---|---|
| `fact_key` | **sí** | PK · `sha256(entity_key\|accession\|qname\|context_id\|unit_ref)` | **D — implementación** | S04, hashout |
| `entity_key` | **sí** | identidad canónica · **FK a `identity_v1.entity`** | **B — provenance universal** | ratio engine, guards |
| `cik` | **sí** | clave del emisor **en el registro de la fuente** | **C en el nombre · A en la función** | guarda F-061, selección de insumos |
| `accession_number` | **sí** | identificador del documento | **B — universal** | ratio engine, guarda F-061 |
| `form`, `filing_date` | no | metadata del documento | B | provenance |
| `report_period` | no | período que el documento declara | **A — financiero universal** | ratio engine |
| `qname` | **sí** | id del concepto en la taxonomía de la fuente | **C en el nombre · A en la función** | guarda F-061, hashout, índice |
| `namespace`, `tag`, `is_custom` | no | descomposición del qname | C | ratio engine (`tag`) |
| `context_id` | **sí** | id del contexto del hecho dentro del documento | **C — específico XBRL** | S04 (dedup + fact_key), hashout. **ratio engine: 0 usos** |
| `period_kind`, `start/end/instant_date` | no | ventana temporal | **A — universal** | ratio engine (filtro de período principal) |
| `is_dimensional`, `dim_count`, `dimensions` | sí/no | desglose por segmento | **C — XBRL**, pero conceptualmente universal | selección de insumos |
| `unit_ref`, `unit_kind`, `unit_measure`, `currency` | no | unidad y moneda | **A — universal** | ratio engine (regla R2) |
| `value_numeric`, `value_text`, `is_nil`, `is_numeric`, `decimals` | sí/no | el dato | **A — universal** | ratio engine |
| `n_fuentes`, `source_fact_ids` | **sí** | punteros a `parsed.facts` | **B — universal** | **guarda F-061**, provenance |
| `desempate` | **sí** | cómo se resolvió el duplicado | **D — implementación** | S04 |
| `input_checkpoint_id`, `run_id` | **sí** | corrida que lo produjo | **B — universal** | linaje |
| `valid_to` | no | ciclo de vida | **B — universal** | todo |
| `unidad_resuelta` | **sí** | F-026 · la unidad se pudo resolver | **A — universal** | `ck_numerico_con_unidad` |

**Reparto: 11 universales financieros o de provenance · 4 específicos de XBRL ·
2 de implementación.**

### Los CHECK, y qué asumen

```
ck_fact_tiene_origen        n_fuentes>=1 AND array_length(source_fact_ids,1)=n_fuentes
ck_periodo_coherente        INSTANT⇒instant_date · DURATION⇒start+end
ck_numerico_con_unidad      numérico resuelto ⇒ unit_measure
ck_dimensional_coherente    (dim_count>0) = is_dimensional
fact_fact_key_check         fact_key ~ '^[0-9a-f]{64}$'
fact_desempate_check        UNICO|IDENTICO|POR_PRECISION|POR_FACT_ID
```

**Ninguno menciona XBRL, CIK ni taxonomía.** Los seis son satisfacibles por un
hecho CNV sin falsificar nada.

---

## 4. `parsed.facts` Contract

**Escribe:** sólo `s03_parse_ypf.py` (vía `engine/s03.py`, `engine/xbrlparse.py`).
**Lee:** S04, la guarda F-061, `ratio_engine.evidencia()`, y los auditores.

| campo | NOT NULL | quién depende |
|---|:-:|---|
| `entity_id` | sí | **S03 lo escribe como `CIK:0000021344` — namespaced. Ni el ratio engine ni hashout lo leen. Abstracción existente y sin uso** |
| `cik` | **sí** | guarda F-061 (`gp.cik <> d.cik`) |
| `accession_number` | **sí** | guarda F-061, hashout |
| `qname` | **sí** | guarda F-061, hashout |
| `tag` | **sí** | S04 |
| `source_kind` | sí | **sin CHECK.** Valores actuales: `XBRL_INSTANCE`, `XBRL_PACKAGE_ZIP`, `XBRL_PACKAGE_ZIP_INLINE` |
| `source_file`, `source_path`, `source_hash` | **sí** | `ratio_engine.evidencia()` para provenance |
| `context_id` | no | S04 (dedup) |

### La pregunta clave, respondida

> **¿El ratio engine está acoplado a XBRL, o sólo la capa de ingestión?**

**Sólo la ingestión.** Medido:

```
context_id en ratio_engine.py · ratio_inputs.py · ratio_api.py ....... 0 usos
entity_id  en ratio_engine.py · ratio_inputs.py · hashout.py ......... 0 usos
```

El ratio engine lee `cik`, `qname` y `accession_number` **exclusivamente como
claves de comparación** dentro de `GUARDA_PERTENENCIA`. No las interpreta:

```sql
WHERE gp.fact_id IS NULL
   OR gp.cik <> d.cik
   OR gp.accession_number <> d.accession_number
   OR gp.qname <> d.qname
```

Esa cláusula funciona idéntica con cualquier par de valores que coincidan. **Es
una regla de igualdad, no de semántica XBRL.**

---

## 5. `derived.ratio` Contract

Lo que realmente necesita para calcular y publicar:

| grupo | campos | ¿depende de XBRL? |
|---|---|---|
| **INPUT FINANCIERO** | `value`, `unit`, `currency`, `period_end`, `period_window`, `denominator_basis` | **no** |
| **IDENTIDAD** | `entity_key`, `canonical_id`, `formula_version` | **no** |
| **PROVENANCE** | `inputs` (jsonb), `input_checkpoint_id`, `run_id`, `valid_from/to` | **no** |
| ESTADO | `status`, `motivo`, `publicable` | no |
| legado de ingesta | `cik` | **sí, y sólo por arrastre** |

`derived.ratio.cik` existe pero **no participa de la clave única**:

```sql
UNIQUE (entity_key, canonical_id, period_end, period_window,
        denominator_basis, coalesce(currency,'-')) WHERE valid_to IS NULL
```

**La identidad del ratio es `entity_key`, no `cik`.** `derived.ratio` es
completamente agnóstica de la fuente salvo por esa columna heredada.

---

## 6. Identity Contract

`identity_v1.entity` exige **sólo dos cosas**:

```
entity_key      ULID  ~ '^E[0-9A-HJKMNP-TV-Z]{26}$'
preferred_name  texto
```

Ni CIK, ni país, ni fuente. **Agnóstica por diseño.**

`identity_v1.identifier.id_type` ya admite:

```
CIK · CUIT · LEI · TICKER · ISIN · YF_SYMBOL · CNV_ENTITY_ID · LEGACY_ENTITY_ID
```

Con validación por tipo: el CUIT pasa por `identity_v1.cuit_valido()`.

### Cómo se representaría METR — sin cambiar nada

```
entity           E01…  ·  preferred_name = 'Metrogas S.A.'  ·  country = AR
identifier       CUIT 30657863676   is_authoritative = true  (requiere assertion VERIFIED)
identifier       TICKER METR        is_authoritative = false (ck_ticker_no_autoritativo)
identifier       CNV_ENTITY_ID 249  is_authoritative = false
instrument       MKT:38 → entity_key
```

**El único requisito no satisfecho hoy es la evidencia del CUIT.** El CHECK
`ck_cuit_exige_evidencia_estructurada` admite GLEIF, SEC_20F, AFIP y HUMAN. Para
METR sirven **AFIP** (constancia) o **HUMAN** (ratificación). No hace falta LEI.

**Conclusión: `identity_v1` NO necesita cambios.**

---

## 7. Provenance Contract

| eslabón | SEC | CNV disponible hoy |
|---|---|---|
| documento | archivo del filing | `eeff/eeff_html/{guid}.html` — **56/56 en disco** |
| **hash** | `source_hash` sha256 | **calculable, no calculado** |
| identificador del documento | `accession_number` | **GUID** |
| identificador del concepto | `qname` (`ns#Tag`) | `concepto` (`Revenue`) |
| contexto del hecho | `context_id` | **`tipo_balance` + `period_end`** |
| emisor en la fuente | `cik` | **`cuit`** |
| entidad canónica | `entity_key` | falta crear |
| puntero hecho→origen | `source_fact_ids` | `accn` (mismo rol) |

### Contrato mínimo común

Los seis elementos que hacen a un hecho trazable, sin mencionar XBRL:

```
1. entidad canónica            entity_key
2. documento de origen         referencia + sha256 del archivo
3. concepto en la fuente       identificador textual, namespaced
4. contexto del hecho          qué período y qué perímetro
5. unidad y moneda             explícitas
6. puntero al hecho crudo      con verificación de pertenencia
```

**CNV puede satisfacer los seis.** El único que hoy no existe es el hash — y los
archivos están.

---

## 8. SEC Dependencies

Lo que **debe permanecer específico de SEC**:

- `engine/xbrlparse.py` — parser XBRL (1.341 líneas)
- `s03_parse_ypf.py` — contextos, unidades, linkbases, taxonomías
- `parsed.contexts`, `parsed.units`, `parsed.concepts`, `parsed.link_relations`
- `parsed.companyfacts_compare` — contraste contra la API de la SEC
- `context_id` **como concepto XBRL** — aunque el campo se generalice

Lo que **ya es universal aunque el nombre no lo diga**:

- `cik` → clave del emisor en el registro de la fuente
- `qname` → identificador del concepto en la taxonomía de la fuente
- `accession_number` → identificador del documento
- `source_hash` → huella del archivo

---

## 9. CNV Requirements

Para que un hecho CNV entre a `parsed.facts` sin falsificar nada:

| campo | valor CNV honesto | ¿falsifica? |
|---|---|---|
| `entity_id` | `CUIT:30657863676` | **no** — sigue la convención `CIK:…` que ya existe |
| `cik` | **no tiene** | ← **el único problema real** |
| `accession_number` | el GUID: `d96fd259-c5ce-…` | no — es el id de la presentación |
| `qname` | `cnv:Revenue` | no — es el concepto de la fuente, namespaced |
| `tag` | `Revenue` | no |
| `context_id` | `CONSOLIDADO@2025-12-31` | no — es el contexto real del hecho |
| `source_kind` | `CNV_EEFF` | no · **sin CHECK que lo impida** |
| `source_file` | `{guid}.html` | no |
| `source_path` | ruta del archivo | no |
| `source_hash` | sha256 del HTML | no — **calculable, 56/56 disponibles** |
| `period_kind` + fechas | `DURATION`/`INSTANT` + `period_end` | no |
| `unit_type`, `measure` | `SIMPLE`, `iso4217:ARS` | no |

**Once de doce campos tienen un valor CNV honesto.** El único sin equivalente es
`cik`, porque METR no lo tiene y **inventarlo sería exactamente lo prohibido**.

---

## 10. Option A — Generalized Canonical Facts

Una sola `parsed.facts` / `derived.fact` con `source_kind` discriminando.

**Cambios requeridos:**

1. `parsed.facts.cik` y `derived.fact.cik` → **NULL-able**, o renombrar a
   `source_entity_ref`.
2. `derived.fact` gana `entity_id` namespaced (espejo del que `parsed.facts` ya
   tiene), y **la guarda F-061 compara por ahí en vez de por `cik`**.
3. Adaptador C4/C5 que escriba con `source_kind='CNV_EEFF'`.

**Costo del renombre completo:** `cik` aparece **807 veces en 62 archivos** del
engine y los tests. Renombrar es caro; **hacerlo NULL-able cuesta una migración**.

---

## 11. Option B — Parallel CNV Facts

`parsed.cnv_facts` con su propio contrato, y una capa común hacia `derived.fact`.

**Cambios requeridos:**

1. Tabla nueva con las columnas CNV nativas (`cuit`, `guid`, `concepto`,
   `tipo_balance`, `escala`, `fecha_reexpresion`, `recpam`…).
2. `derived.fact` **igual tiene que aceptar el hecho CNV** → los mismos problemas
   de `cik` y `entity_key` reaparecen un nivel más arriba.
3. Segunda implementación de la guarda de pertenencia contra `parsed.cnv_facts`.
4. Segunda ruta de provenance en `ratio_engine.evidencia()`.

**Observación decisiva: la opción B no evita el problema, lo pospone.** Mientras
el destino común sea `derived.fact`, `cik NOT NULL` bloquea igual. B sólo ayuda
si el destino común fuera `derived.ratio` — y eso **duplicaría el motor**, que es
lo que el criterio de éxito prohíbe.

---

## 12. A vs B Comparison

| criterio | A · generalizar | B · vía paralela |
|---|---|---|
| impacto sobre SEC | 1 columna NULL-able + 1 línea de la guarda | igual, más una tabla |
| impacto sobre CNV | adaptador C4/C5 | adaptador + tabla + guarda propia |
| complejidad | **baja** | media-alta |
| riesgo | acotado: `cik` NULL sólo para `source_kind='CNV_EEFF'`, verificable con un CHECK condicional | mayor: dos rutas de provenance divergen con el tiempo |
| provenance | **una sola cadena** | dos cadenas que hay que mantener sincronizadas |
| integridad | la guarda F-061 sigue siendo **una** | **dos guardas** — el riesgo que F-061 vino a cerrar |
| reutilización | el ratio engine no se toca | idem, pero `evidencia()` se bifurca |
| escalabilidad a otras fuentes | **cada fuente = un `source_kind`** | cada fuente = una tabla |
| compatibilidad con ratios | total | total |
| compatibilidad con API | total | total |

### Veredicto por el código, no por preferencia

**OPCIÓN A.** Tres razones, todas medidas:

1. **La abstracción ya existe y está sin usar.** `parsed.facts.entity_id` guarda
   `CIK:0000021344` — namespaced, y **cero módulos lo leen**. Alguien ya previó
   múltiples fuentes.
2. **No hay CHECK sobre `source_kind`.** El esquema ya admite un valor nuevo.
3. **B no resuelve el bloqueo**, sólo lo mueve — y duplica la guarda F-061, que es
   precisamente la garantía que más costó conseguir.

---

## 13. METR End-to-End Mapping

### `Revenue` FY2025

```
documento CNV      eeff/eeff_html/d96fd259-c5ce-431f-8e14-17af592b99f9.html
GUID               d96fd259-c5ce-431f-8e14-17af592b99f9
cnv_estados_v2     concepto=Revenue · valor · accn=<guid> · unidad_factor=1000000
cnv_estados_norm   valor=1.217.305.000.000 · tipo_balance=CONSOLIDADO
                   escala=1000000 · fecha_reexpresion=2025-12-31 · moneda=ARS
        ↓  ADAPTADOR C4/C5  (no existe)
parsed.facts       entity_id       = 'CUIT:30657863676'
                   cik             = NULL                    ← el cambio
                   accession_number= '<guid>'
                   qname           = 'cnv:Revenue'
                   tag             = 'Revenue'
                   context_id      = 'CONSOLIDADO@2025-12-31'
                   source_kind     = 'CNV_EEFF'
                   source_file     = '<guid>.html'
                   source_hash     = sha256(archivo)          ← calculable
                   value_numeric   = 1217305000000
                   unit_type='SIMPLE' · measure='iso4217:ARS'
                   period_kind='DURATION' · start/end
        ↓  S04 (sin cambios)
derived.fact       entity_key = E01…(METR)      ← requiere identidad
                   fact_key   = sha256(entity_key|guid|cnv:Revenue|CONSOLIDADO@2025-12-31|ars)
                   currency='ARS' · source_fact_ids=[…] · n_fuentes=1
        ↓  ratio_engine (SIN CAMBIOS)
derived.ratio      canonical_id='net_margin' · period_window='FY'
                   currency='ARS' · inputs=[…] · entity_key=E01…
```

### Los demás insumos — mismo camino

| concepto | qname CNV | contexto | ¿existe? |
|---|---|---|---|
| EBITDA | `cnv:EBITDA` | `CONSOLIDADO@2025-12-31` | **sí, reportado** |
| DebtCurrent + DebtNonCurrent | `cnv:DebtCurrent` / `cnv:DebtNonCurrent` | ídem | **sí** |
| Equity | `cnv:Equity` | ídem | **sí** |
| NetIncome | `cnv:NetIncome` | ídem | **sí** |
| Price | — | `market_price_daily` instrumento 38 | **sí, 6.637 velas** |

### ¿Qué falta exactamente para EV/EBITDA, P/E y ROE en `derived.ratio`?

| # | falta | tipo |
|---|---|---|
| 1 | entidad de METR en `identity_v1` + CUIT con evidencia AFIP/HUMAN | **identidad** |
| 2 | `MKT:38` ligado a esa entidad (para los de precio) | **identidad** |
| 3 | `cik` NULL-able + guarda comparando por `entity_id` | **esquema, 1 migración** |
| 4 | sha256 de los 56 HTML | **cómputo, sin esquema** |
| 5 | adaptador C4/C5 CNV → `parsed.facts` | **código nuevo** |
| 6 | conceptos CNV declarados en `ratio_defs.CONCEPTOS` | **declaración** |

**Nada de esto toca el ratio engine.** Los ratios ya están implementados.

---

## 14. SEC Safety Analysis

| garantía | qué protege | ¿sobrevive a la opción A? |
|---|---|---|
| **F-026** `unidad_resuelta` | numérico resuelto ⇒ `unit_measure` | **intacta** — no menciona fuente |
| **F-031** huérfanas de S0x | ciclo de vida de corridas | **intacta** |
| **F-036/F-037** evidencia estructurada | assertions de identidad | **intacta** — otra tabla |
| **F-042** `source_facts` inmutable | trigger sobre `identity_v1.assertion` | **intacta** — otra tabla |
| **F-050** `run_scope` | cierre garantizado de corridas | **intacta** |
| **F-054** aislamiento de emisores | borrado con alcance + sin reset de secuencia | **intacta** — es de S03 |
| **F-055** equivalencia de contextos | orden canónico de dimensiones | **intacta** — es de S04 |
| **F-061** ownership | punteros de provenance del mismo emisor/documento/concepto | **⚠ cambia de columna** |
| `hash_out` | digest de integridad de S03/S04 | **⚠ ver abajo** |
| provenance v2 | listas de `source_hashes` | **intacta** |

### Los dos puntos que sí se tocan

**F-061.** La guarda compara `gp.cik <> d.cik`. Si `cik` puede ser NULL, la
comparación con `<>` **deja pasar NULL en silencio** — el modo exacto de falla que
F-061 vino a cerrar. La generalización **obliga** a cambiarla por una comparación
sobre una clave siempre presente (`entity_id` namespaced) y a usar
`IS DISTINCT FROM`. **Es una línea, y sin ella la generalización debilita la
garantía.** Es el punto más delicado de todo el cambio.

**`hash_out`.** `CAMPOS["derived.fact"]` incluye `qname` y `context_id`. Con
valores CNV el digest cambia — pero eso es correcto: son filas nuevas. **Los
digests históricos de SEC no se alteran** porque el filtro es por `run_id`. Sin
riesgo, con verificación recomendada.

**Ninguna garantía depende de que el `cik` sea un CIK de la SEC.** Dependen de que
haya *una* clave de emisor consistente entre `parsed` y `derived`.

---

## 15. Minimum Required Changes

| # | área | ¿cambia? | qué exactamente | por qué | impacto SEC | riesgo |
|---|---|:-:|---|---|---|---|
| 1 | **schema** | **sí** | `parsed.facts.cik` y `derived.fact.cik` → NULL-able, con CHECK condicional: `source_kind='CNV_EEFF' OR cik IS NOT NULL` | METR no tiene CIK y no se puede inventar | **ninguno** — SEC lo sigue teniendo obligatorio por el CHECK | bajo |
| 2 | **schema** | **sí** | `derived.fact` gana `entity_id` (namespaced), espejo del de `parsed.facts` | dar a la guarda una clave siempre presente | aditivo | bajo |
| 3 | **provenance** | **sí** | calcular sha256 de los 56 HTML | contrato mínimo común §7 | ninguno | **nulo** |
| 4 | **identity** | **sí** | crear entidad METR + CUIT con evidencia AFIP/HUMAN + ligar `MKT:38` | `entity_key` es `NOT NULL` con FK | ninguno | bajo — es dato, no esquema |
| 5 | **ingestion adapter** | **sí** | C4/C5: CNV → `parsed.facts` con `source_kind='CNV_EEFF'` | no existe | ninguno | **el trabajo grande** |
| 6 | **canonical concepts** | **sí** | declarar los conceptos CNV en `ratio_defs.CONCEPTOS` | el motor resuelve por concepto | aditivo | bajo |
| 7 | **ratio engine** | **NO** | — | ya es agnóstico | — | — |
| 8 | **market linkage** | **sí** | `identity_v1.instrument` ← `MKT:38` | atribuir el precio sin join por ticker | ninguno | bajo |
| 9 | **tests** | **sí** | mutación de la guarda con `cik` NULL + regresión SEC | sin eso, el punto 1 debilita F-061 | — | **obligatorio** |

**Una migración, un adaptador, una declaración de conceptos y datos de identidad.
El ratio engine no se toca.**

---

## 16. Migration / Implementation Sequence

**Sin ejecutar.** Orden por dependencia:

```
1  identidad          crear entidad METR + CUIT (AFIP/HUMAN) + ligar MKT:38
2  test rojo          mutación: guarda con cik NULL debe seguir bloqueando el ajeno
3  migración          cik NULL-able + CHECK condicional + derived.fact.entity_id
4  guarda F-061       comparar por entity_id con IS DISTINCT FROM
5  verificar SEC      296 tests + hash_out sin cambios en los run_id históricos
6  hashes CNV         sha256 de los 56 HTML
7  adaptador C4/C5    CNV → parsed.facts (source_kind='CNV_EEFF')
8  conceptos          declarar los CNV en ratio_defs
9  correr             ratio_engine --cik ... sobre METR, sin tocar el motor
```

**El paso 2 va antes del 3 a propósito**: la migración que habilita `cik` NULL es
la que puede debilitar F-061, y el test tiene que existir antes.

---

## 17. Risks

| # | riesgo | mitigación |
|---|---|---|
| **R1** | `cik` NULL rompe la guarda F-061 en silencio (`<>` con NULL) | comparar por `entity_id` con `IS DISTINCT FROM`; test de mutación previo |
| **R2** | `context_id` sintético (`CONSOLIDADO@2025-12-31`) colisiona entre documentos del mismo período | incluir el GUID en el contexto si hace falta; **UNKNOWN hasta verlo con datos** |
| **R3** | El `fact_key` de CNV depende de que `qname` y `context_id` sean estables entre corridas | derivarlos determinísticamente del concepto y del perímetro |
| **R4** | Sin `Inventory` ni `CapEx`, algunos ratios quedan `NOT_CALCULABLE` en CNV | comportamiento correcto, ya contemplado |
| **R5** | Dos perímetros por período: sin `statement_scope`, uno pisa al otro | el `context_id` los separa naturalmente; **conviene resolver el multi-scope antes** |
| **R6** | `hash_out` de S04 cambia al entrar filas CNV | filtrado por `run_id`; verificar que los digests SEC históricos no se muevan |

---

## 18. Final Recommendation

# OPCIÓN A · GENERALIZAR — con una precondición innegociable

El modelo canónico **no está tan acoplado a XBRL como parecía**. La prueba está
en el propio esquema: `source_kind` sin CHECK, `entity_key` con FK a una tabla de
identidad agnóstica, `id_type` que ya admite CUIT, y sobre todo
**`parsed.facts.entity_id` guardando `CIK:0000021344`** — una abstracción de
fuente que alguien construyó y nadie usa.

Lo que está acoplado es **una columna: `cik`**. Y su acoplamiento es de nombre,
no de función: el código la usa como clave de igualdad entre `parsed` y
`derived`, nunca como un CIK.

**La precondición:** el cambio del punto 1 —`cik` NULL-able— **debilita F-061 si
se hace solo**, porque `gp.cik <> d.cik` deja pasar NULL. La guarda tiene que
migrar a `entity_id` con `IS DISTINCT FROM` **en el mismo commit**, y el test de
mutación tiene que existir **antes**. Ése es el único punto donde este cambio
puede hacer daño real.

**Lo que NO recomiendo:** la opción B. No evita el bloqueo —`derived.fact` sigue
exigiendo `cik`— y duplica la guarda de pertenencia, que es exactamente la
garantía que más costó conseguir.

### UNKNOWN declarados

- **R2**: si dos presentaciones del mismo período pueden generar el mismo
  `context_id` sintético. No determinable sin construir el adaptador.
- Si `job5_v2` produce concepto+perímetro de forma **determinista entre
  corridas** — condición para que `fact_key` sea estable. No verificado.
- El costo real del adaptador C4/C5. La estimación previa (8–15 días) sigue
  siendo la referencia, y depende del spike de generalización del parser.
