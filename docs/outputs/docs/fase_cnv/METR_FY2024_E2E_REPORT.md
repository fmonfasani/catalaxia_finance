# METR FY2024 · E2E — INGESTA, PERSISTENCIA Y CERTIFICACIÓN HISTÓRICA

**Metrogas S.A. · CUIT 30657863676 · ejercicio 2024**

Snapshot histórico independiente de FY2025. No se recalibró ninguna fórmula,
no se introdujo ningún mapping, no se consultó TIKR, no se tocó producción.

---

## 1 · Estado inicial (FASE 0)

| precondición | verificación |
|---|---|
| Fixture aislado | **`cnvmig` @ puerto 5433** (contenedor `catalaxia-engine-dev`) |
| Producción intacta | `catalaxia` @ 5432 (`catalaxia-db`) tiene **sólo el esquema `public`** — no existen `parsed` ni `derived` |
| Base homologada | `catalaxia` @ 5433: **0 facts CNV, 0 facts de METR** |
| `screener.db` | mtime `2026-08-23 13:42:23`, 1.504.714.752 bytes |
| Puerto/base explícitos | `ENGINE_DB_NAME=cnvmig ENGINE_DB_PORT=5433` en cada invocación |
| Identidad authoritative | `EY9TRR9RPRVSV916PD0CB9Z93NT` · Metrogas S.A. · `CUIT:AFIP:30657863676` · `is_authoritative=t` · **ACTIVE** |
| `entity_key` ↔ `derived.fact` | coinciden |

Cardinalidades al comenzar:

```
parsed.facts    228.350      derived.fact   136.777      contexts   71.692
parsed CNV        2.875      derived ratio       36      entidades   7.998
METR total        2.875 facts  (2018–2025)
METR 2024           371 facts  ·  7 documentos
```

Digests de línea base (MD5 sobre las claves ordenadas):

```
parsed_metr    1ca1474a5feb08958d0491dd6338554e   n=2.875
derived_metr   84249140c005f834468fbb1a1b993826   n=2.875
derived_2024   7416322fefbea1b48253075268d48e09   n=  371
derived_2025   cb2e25f9ca47237c04f85cb742a8f73f   n=  426
derived_global 4e716252e387bdedc313567c621caf73   n=136.777
```

> **Hallazgo de FASE 0.** FY2024 **ya estaba ingestado**. El adaptador
> certificado durante el sprint FY2025 procesó **toda la historia de METR
> (2018–2025)**, no sólo el último ejercicio. Este sprint no es una primera
> ingesta: es la **certificación** de un tramo que hasta ahora nunca había sido
> auditado, y la construcción de su snapshot. La FASE 7 lo aprovecha —
> la corrida de este sprint es, por construcción, una segunda corrida — y se
> complementa con una corrida en frío deliberada sobre una copia (§8).

---

## 2 · Corpus utilizado

`scripts/tickets/cnv/eeff/eeff_html` — los mismos HTML de la CNV que usó el
piloto FY2025. Ningún archivo fue creado, modificado ni eliminado.

---

## 3 · Documentos encontrados (FASE 1)

**7 documentos.** El período de cada uno se determinó **leyendo el contenido**
(`FechaCierre` y `PeriodoBalance` del propio HTML), nunca el nombre del archivo,
y luego se contrastó contra lo que la tabla declaraba.

| cierre | perímetro | `PeriodoBalance` | clase | SHA256 | período | presentación |
|---|---|---|---|---|---|---|
| 2024-03-31 | CONSOLIDADO | 3 | TRIMESTRAL | ✓ | ✓ | #3195871 |
| 2024-03-31 | INDIVIDUAL | 3 | TRIMESTRAL | ✓ | ✓ | #3195834 |
| 2024-06-30 | CONSOLIDADO | 3 | TRIMESTRAL | ✓ | ✓ | #3235674 |
| 2024-06-30 | INDIVIDUAL | 3 | TRIMESTRAL | ✓ | ✓ | #3235667 |
| 2024-09-30 | INDIVIDUAL | 3 | TRIMESTRAL | ✓ | ✓ | #3277348 |
| **2024-12-31** | **CONSOLIDADO** | **1** | **ANUAL** | ✓ | ✓ | #3326103 |
| **2024-12-31** | **INDIVIDUAL** | **1** | **ANUAL** | ✓ | ✓ | #3326092 |

7/7 con SHA256 recomputado desde el archivo y coincidente con `parsed.facts`.
7/7 con el CUIT extraído del documento igual a 30657863676.

El ejercicio se identifica por **`PeriodoBalance=1`**, no por la fecha ni por el
campo `tipo` ('A'/'P'), que es discrepante en 754 documentos del corpus.

> **Asimetría real del corpus:** falta el **CONSOLIDADO de 2024-09-30**. Existe
> el INDIVIDUAL de ese trimestre, no su par consolidado. Es un hueco del corpus
> descargado, no un fallo del pipeline — ver §14.

Detalle completo: `METR_FY2024_DOCUMENTS.csv` (23 campos por documento).

---

## 4 · Facts (FASE 2 y 3)

**203 facts** sobre 30 conceptos, 29 por documento × 7 documentos.

Reglas aplicadas — las mismas certificadas en FY2025, sin excepción:

| regla | valor en FY2024 |
|---|---|
| `entity_id` | `CUIT:30657863676` en los 203 |
| `entity_key` | `EY9TRR9RPRVSV916PD0CB9Z93NT` en los 203 |
| `context_id` | `PERIMETRO\|KIND\|inicio\|fin\|medición` |
| `period_kind` | `1xxxxxx`/`2xxxxxx` → INSTANT · `3xxxxxx` → DURATION |
| `start_date` | `2024-01-01` en **todos** los DURATION (la CNV acumula YTD) |
| `measurement_date` | el `FechaCierre` del documento, en los 203 |
| `perimetro` | del `TipoBalance` del documento |
| `unit_measure` | `iso4217:ARS` · `iso4217:ARS/xbrli:shares` (EPS) |
| escala | factor 1e6 — la CNV declara **"Millones de $"** |
| `fact_key` | `sha256(entity_key\|accn\|qname\|context_id\|unit_measure)` |
| `econ_key` | serialización canónica de la migración 036 |

**`audit_status != OK`: 0 de 203.** Ningún DURATION sin start/end, ningún
INSTANT con inicio, ninguna unidad vacía, ningún `measurement_date` ausente,
ninguna fila no vigente.

### Cifras del ejercicio anual (2024-12-31, millones de ARS del cierre)

| concepto | CONSOLIDADO | INDIVIDUAL |
|---|---:|---:|
| Revenue | 925.090 | 694.455 |
| COGS | −585.444 | −424.325 |
| GrossProfit | 339.646 | 270.130 |
| OperatingIncome | 145.372 | 129.457 |
| PretaxIncome | 258.215 | 238.222 |
| IncomeTax | −101.587 | −83.807 |
| **NetIncome** | **156.628** | **154.415** |
| Assets | 1.100.677 | 1.070.313 |
| Liabilities | 470.135 | 441.040 |
| **Equity** | **630.542** | **629.273** |
| PatrimonioAperturaEjercicio | 475.654 | 474.858 |
| Cash | 122.280 | 86.396 |
| CF_Operativo | 161.133 | 99.641 |
| **EPS básico** | **271,38** | **271,38** |

Dos coherencias que el propio dato confirma: la diferencia
`NetIncome` consolidado − individual = **2.213** es la participación no
controlante, y el **EPS es idéntico en ambos perímetros**, como corresponde a
una magnitud atribuible a los propietarios de la controladora.

Detalle: `METR_FY2024_FACTS.csv` (24 campos por fact).

### El saldo de apertura y la reexpresión IAS 29

`PatrimonioAperturaEjercicio` (código `8000002`) aparece en los 7 documentos
como un **INSTANT del 2023-12-31** con el `measurement_date` de cada cierre.
El mismo saldo vale distinto en cada documento:

```
31-12-2023 medido al 31-03-2024   331.184
31-12-2023 medido al 30-06-2024   392.674
31-12-2023 medido al 31-12-2024   475.654
```

No es una inconsistencia: es IAS 29 — cada cifra está expresada en el poder
adquisitivo de **su** cierre. Y es exactamente lo que hace legítimo el ROE con
patrimonio promedio: apertura y cierre están en la misma moneda.

---

## 5 · Ratios (FASE 4)

**70 calculados de 77** (11 ratios × 7 combinaciones período/perímetro).

| clase | ratios |
|---|---|
| margen | `net_margin`, `gross_margin`, `operating_margin` |
| liquidez | `current_ratio`, `quick_ratio`, `cash_ratio` |
| solvencia | `debt_to_equity`, `equity_ratio` |
| rentabilidad | `roa`, `roe_promedio` |
| fiscal | `effective_tax_rate` |

### Ejercicio anual 2024-12-31

| ratio | CONSOLIDADO | INDIVIDUAL |
|---|---:|---:|
| net_margin | 0,169311 | 0,222354 |
| gross_margin | 0,367149 | 0,388981 |
| operating_margin | 0,157144 | 0,186415 |
| current_ratio | 0,816974 | 0,724784 |
| cash_ratio | 0,339422 | 0,260791 |
| debt_to_equity | 0,745605 | 0,700872 |
| equity_ratio | 0,572867 | 0,587934 |
| roa | 0,142302 | 0,144271 |
| **roe_promedio** | **0,283183** | **0,279704** |
| effective_tax_rate | −0,393420 | −0,351802 |
| quick_ratio | — | — |

### Los 7 no calculables

**`quick_ratio`, en los 7 períodos: `NO_INPUT — falta insumo: Inventory`.**
METR no declara existencias en ningún documento de 2024. Es una causa
explícita, no una tolerancia.

### Ratios deliberadamente NO implementados

P/E, P/B, P/S, EV/EBITDA, market cap y dividend yield **no se calcularon**:
requieren precio de mercado, que todavía no forma parte del pipeline. Hay un
test que falla si alguno aparece en la matriz.

### Control de coherencia del ROE

La CNV acumula YTD, así que el ROE del ejercicio debe **crecer** trimestre a
trimestre. Lo hace, en ambos perímetros:

```
CONSOLIDADO   Q1 0,0572   H1 0,1748   FY 0,2832
INDIVIDUAL    Q1 0,0562   H1 0,1731   9M 0,2532   FY 0,2797
```

No es una banda de tolerancia: es una consecuencia aritmética de que el
numerador acumule y el denominador sea un promedio.

Detalle: `METR_FY2024_RATIOS.csv`.

---

## 6 · Provenance (FASE 5)

`METR_FY2024_PROVENANCE.csv` — una fila por *(ratio, rol, fact)*, con la cadena
completa hasta el SHA256 del documento. Cobertura: **los 70 ratios calculados**.

Ejemplo — `net_margin` CONSOLIDADO 2024-12-31 = 0,169311:

```
numerator    NetIncome    156.628  DURATION 2024-01-01..2024-12-31  md=2024-12-31
             fact_key  476eed8a3ab5ab6fdfef819c…
             econ_key  373cbea4bb984720f1b09515…
             context   CONSOLIDADO|DURATION|2024-01-01|2024-12-31|2024-12-31
             accn      89e96a2b-946e-4def-85b2-b69f0739bc16
             sha256    469b6c565a2a63e4a205750758fecbe1…

denominator  Revenue      925.090  DURATION 2024-01-01..2024-12-31  md=2024-12-31
             fact_key  dfbfbf27f8327fb36f49672e…
             econ_key  3ec690e0a9fb4b1f943f84cf…
             context   CONSOLIDADO|DURATION|2024-01-01|2024-12-31|2024-12-31
             accn      89e96a2b-946e-4def-85b2-b69f0739bc16
             sha256    469b6c565a2a63e4a205750758fecbe1…
```

La muestra exigida por la FASE 5 está cubierta: **Revenue**, **NetIncome**,
**EPS**, **Equity**, un ratio de **margen**, uno de **liquidez** y uno de
**rentabilidad**.

---

## 7 · Auditoría independiente (FASE 6)

`scripts/engine/c4_auditoria_fy2024.py`. **No importa** `c4_metr_fy2024`, ni
`c4_cnv_adapter`, ni `c4_cnv_semantica`, ni `job5`. Tiene su propio parser de
HTML, su propia transcripción del plan de cuentas y su propia implementación de
las dos fórmulas de identidad.

```
A  documentos      7 con SHA256 recomputado          0 fallas
B  valores         203 reconstruidos desde el HTML   0 fallas
C  unidad y escala factor 1e6 deducido del texto     0 fallas
D  período         kind, start/end, measurement_date 0 fallas
E  perímetro       contra TipoBalance del documento  0 fallas
F  fact_key        recomputada                       0 fallas
G  econ_key        recomputada                       0 fallas
H  ratios          70 recalculados                   0 fallas

AUDITORIA = PASS   0 fallas
```

**El auditor encontró tres errores — todos suyos, ninguno del pipeline.** Vale
dejarlos registrados porque muestran qué estaba midiendo:

1. Buscaba la unidad como `"millones de pesos"`; la CNV la declara
   **`"Millones de $"`**, con símbolo. Al no encontrarla caía al factor 1 y
   comparaba 649.387 contra 649.387.000.000.
2. Buscaba el CUIT precedido de la etiqueta `CUIT`; en el documento aparece sin
   rótulo, en el `<title>`, tras la razón social y un pipe.
3. Deducía la naturaleza temporal del primer dígito del código y asignaba
   INSTANT a todo el grupo `8xxxxxx`. El grupo **no es homogéneo**: el EPS se
   gana a lo largo del período (DURATION) y el patrimonio de apertura es un
   saldo (INSTANT).

El tercero también estaba en el script principal (el regex del CUIT), y se
corrigió allí. Los tres se arreglaron **en el auditor**, sin relajar ningún
control ni tocar el pipeline.

---

## 8 · Segunda ejecución e idempotencia (FASE 7)

### Sobre el fixture `cnvmig`

```
                          antes                              después
parsed_2024    371  5471198c19a2ef2cebb639052c76e87d   371  5471198c19a2ef2c…  IGUAL
derived_2024   371  7416322fefbea1b48253075268d48e09   371  7416322fefbea1b4…  IGUAL
econ_2024      371  b2241ff5e1865aa3ed2ce1f3a2d765ed   371  b2241ff5e1865aa3…  IGUAL
derived_2025   426  cb2e25f9ca47237c04f85cb742a8f73f   426  cb2e25f9ca47237c…  IGUAL
metr_todo    2.875  84249140c005f834468fbb1a1b993826 2.875  84249140c005f834…  IGUAL
derived_global 136.777  4e716252e387bdedc313567c621caf73  →  4e716252e387bded…  IGUAL

parsed.facts insertados: 0   reusados:  2.697
derived.fact insertados: 0   sin cambio: 2.697
```

0 duplicados, 0 identidades económicas espurias, 0 modificaciones no explicadas.

### Corrida en frío, para poder informar la primera ejecución

La primera ingesta de METR ocurrió en un sprint anterior, así que sus inserts no
son observables desde aquí. Para no reportar un número que no medí, se creó
`fy2024_fresh` (copia por `TEMPLATE cnvmig`), se borró **sólo METR** — quedaron
los 133.902 facts de SEC — y se corrió el adaptador dos veces:

| | `parsed.facts` | `derived.fact` |
|---|---:|---:|
| **1ª corrida (en frío)** | **2.697 insertados** | **2.697 insertados** |
| **2ª corrida** | 0 insertados · 2.697 reusados | 0 insertados · 2.697 sin cambio |

Y lo que más importa — la corrida en frío produjo claves **byte-idénticas** a
las del fixture para FY2024:

```
                    cnvmig                              fy2024_fresh
fact_key_2024  350  9ae593d3984a4caedda9e6664686adc7   9ae593d3984a4cae…  IGUAL
econ_key_2024  350  89e428ca0dd4f97aeaba0a9af1003413   89e428ca0dd4f97a…  IGUAL
valores_2024   350  dd8eaef77db7f8255ece04342b33a67f   dd8eaef77db7f825…  IGUAL
```

El `entity_key` también se reprodujo idéntico en una base vacía
(`EY9TRR9RPRVSV916PD0CB9Z93NT`): se deriva determinísticamente del CUIT, no de
una secuencia.

`fy2024_fresh` se eliminó al terminar; las bases de 5433 quedaron como estaban.

> Los 350 de la comparación son los conceptos de la base de 2.697 filas. Los 21
> restantes hasta 371 son los 4 conceptos que el sprint anterior agregó desde
> `metr_sprint.db` (`PatrimonioAperturaEjercicio`, `InteresesNoControlantes`,
> `AjusteDeCapital`, `OtrosIngresos`) y que no están en `screener.db`, así que
> la corrida en frío no podía producirlos. Es una diferencia de **origen del
> corpus**, no de determinismo.

### Snapshot reproducible

`METR_FY2024_SNAPSHOT.json`, regenerado tras la segunda corrida:

```
documentos.n              7        IGUAL
documentos.digest         27a779def75d99c0…   IGUAL
facts.n                   203      IGUAL
facts.digest_fact_key     2324f732c8dcd39f…   IGUAL
facts.digest_econ_key     ecd38d81a23c2953…   IGUAL
facts.digest_valores      ff30bc8c1b2b4377…   IGUAL
ratios.n                  77       IGUAL
ratios.digest             250ceb4bfc6adcc6…   IGUAL
```

Lo único que cambia entre ejecuciones es `generado_utc`, que es su propósito.

---

## 9 · Mutaciones adversariales (FASE 8)

`tests/test_metr_fy2024_e2e.py`. Cada mutación se aplica sobre una copia en
memoria: no se toca el RAW, ni el fixture, ni producción.

| | mutación | qué la detecta |
|---|---|---|
| **M1** | valor RAW alterado (+1 %) | el auditor lo reconstruye desde el HTML |
| **M2** | SHA256 alterado | recómputo desde el archivo |
| **M3** | `unit_measure` incorrecta | vocabulario + la unidad entra en `fact_key` |
| **M4** | escala incorrecta (1e3 en vez de 1e6) | factor deducido del texto del documento |
| **M5** | `start_date` incorrecta | el período entra en `econ_key` |
| **M6** | `measurement_date` incorrecta | entra en `econ_key` (IAS 29) |
| **M7** | `entity_id` de otra entidad | entra en ambas claves |
| **M8** | `fact_key` alterada | no reproduce sus componentes |
| **M9** | `econ_key` alterada | no reproduce sus componentes |
| **M10** | DURATION convertido en INSTANT | `econ_key` + plan de cuentas (`3xxxxxx` es flujo) |

**Ninguna pasa en silencio.** M10 es la más peligrosa: no cambia el número,
cambia lo que el número significa — un Revenue INSTANT diría que la empresa
*tiene* 925.090 millones de ingresos a una fecha, en vez de haberlos ganado a lo
largo del ejercicio.

**Suite completa: 29 tests, todos pasan.**

---

## 10 · FY2024 vs FY2025 (FASE 9)

Control de consistencia del pipeline, **sin TIKR**.

**54 conceptos comparados · 0 alertas.** Ningún cambio de unidad, ningún cambio
de `period_kind`, ningún concepto que aparezca en un año y desaparezca en el
otro, ningún período duplicado, ningún fact con contextos incompatibles.

| concepto (CONSOLIDADO, millones) | FY2024 | FY2025 | var |
|---|---:|---:|---:|
| Revenue | 925.090 | 1.217.305 | +31,6 % |
| GrossProfit | 339.646 | 465.192 | +37,0 % |
| OperatingIncome | 145.372 | 196.311 | +35,0 % |
| NetIncome | 156.628 | 132.483 | −15,4 % |
| Assets | 1.100.677 | 1.390.076 | +26,3 % |
| Liabilities | 470.135 | 429.731 | −8,6 % |
| Equity | 630.542 | 960.345 | +52,3 % |
| Cash | 122.280 | 116.132 | −5,0 % |
| CF_Operativo | 161.133 | 89.042 | −44,7 % |
| EPS básico | 271,38 | 229,62 | −15,4 % |

> **Estas variaciones NO son comparables como crecimiento real.** Bajo IAS 29
> las cifras de FY2024 están expresadas en pesos del 31-12-2024 y las de FY2025
> en pesos del 31-12-2025. La variación mezcla cambio real e inflación. Para
> compararlas haría falta reexpresar FY2024 al poder adquisitivo de FY2025, y
> Catalaxia no tiene ese índice. Se informan como **control de consistencia del
> pipeline**, no como análisis económico.

Dos coherencias internas sí verificables sin reexpresar: `EPS` (−15,39 %) y
`NetIncome` (−15,42 %) varían prácticamente igual — la diferencia de 0,03 pp se
explica por los dos decimales con que la CNV publica el EPS —, lo que indica que
el denominador en acciones no cambió entre ejercicios; y las tres partidas de
resultado
(`Revenue`, `GrossProfit`, `OperatingIncome`) se mueven juntas mientras
`NetIncome` cae, lo que ubica la diferencia por debajo del resultado operativo
— no un error de extracción, sino un hecho del ejercicio.

---

## 11 · Controles de no contaminación (FASE 10)

| control | antes | después |
|---|---|---|
| `screener.db` mtime | `2026-08-23 13:42:23` | **idéntico** |
| `screener.db` tamaño | 1.504.714.752 | **idéntico** |
| Producción 5432, esquemas | `public` | `public` |
| Producción 5432, `parsed`/`derived` | no existen | no existen |
| Homologada `catalaxia`@5433, facts CNV | 0 | **0** |
| Homologada `catalaxia`@5433, METR | 0 | **0** |
| `derived_global` en `cnvmig` | 136.777 · `4e716252…` | **idéntico** |
| Bases en 5433 | catalaxia, cnvmig, dbgcopy, e2e_final, f051_check | **las mismas** |
| Archivos RAW | — | ninguno creado, modificado ni borrado |

Todo cambio quedó dentro del worktree `catalaxia-cnvmig` (rama
`feat/cnv-canonical`) y del fixture `cnvmig`. `screener.db` se abrió siempre
con `?mode=ro`. Cada script lleva un guard que aborta si `db_name == "catalaxia"`
o si el puerto es el de producción.

---

## 12 · Entregables

| archivo | contenido |
|---|---|
| `METR_FY2024_E2E_REPORT.md` | este informe |
| `METR_FY2024_DOCUMENTS.csv` | 7 documentos × 23 campos |
| `METR_FY2024_FACTS.csv` | 203 facts × 24 campos |
| `METR_FY2024_RATIOS.csv` | 77 ratios × 18 campos |
| `METR_FY2024_PROVENANCE.csv` | cadena completa de los 70 ratios calculados |
| `METR_FY2024_SNAPSHOT.json` | digests reproducibles |
| `scripts/engine/c4_metr_fy2024.py` | pipeline E2E (worktree) |
| `scripts/engine/c4_auditoria_fy2024.py` | auditor independiente (worktree) |
| `tests/test_metr_fy2024_e2e.py` | 29 tests, M1–M10 (worktree) |

---

## 13 · Distinción FY2024 / FY2025

Los dos ejercicios conviven en el mismo fixture y se distinguen sin ambigüedad
por tres vías independientes:

- **`report_period`** — `2024-*` contra `2025-*`
- **`context_id`** — incluye inicio, fin y `measurement_date`
- **`econ_key`** — incorpora `period_kind`, `start_date`, `end_date` y
  `measurement_date`: dos hechos del mismo concepto en años distintos **no
  pueden colisionar**

FY2024 tiene 371 facts derivados y FY2025 426. Ninguna operación de este sprint
modificó una sola fila de FY2025: su digest `cb2e25f9ca47237c04f85cb742a8f73f`
es idéntico antes y después.

---

## 14 · Limitaciones

1. **Falta el CONSOLIDADO de 2024-09-30.** Existe el INDIVIDUAL de ese
   trimestre pero no su par consolidado. Es un hueco del corpus descargado, no
   del pipeline: 7 documentos donde cabrían 8. Por eso el ROE consolidado tiene
   3 puntos y el individual 4.
2. **`quick_ratio` no es calculable**: METR no declara existencias.
3. **FY2024 y FY2025 no son comparables en términos reales** sin reexpresar
   bajo IAS 29 (§10).
4. **Ratios de mercado fuera de alcance** por decisión del sprint: exigen una
   fuente de precios que el pipeline todavía no tiene.
5. **La primera ingesta de METR no ocurrió en este sprint.** Los inserts en
   frío se midieron sobre una copia creada para eso (§8), no sobre el fixture.
6. **El corpus se limitó a los EEFF resumidos.** Las notas contables no se
   descargan, lo que acota qué conceptos existen — ver
   `METR_TIKR_2025_DEPENDENCY_MAP.md`.
7. **No se comparó contra TIKR**, por diseño: ése es el sprint siguiente.

---

## 15 · Estado final

```
GATE FINAL — METR FY2024

 1. FY2024 correctamente identificado ................ PASS
      periodo leido del contenido (FechaCierre + PeriodoBalance)
      7/7 documentos coinciden con lo declarado
 2. RAW con SHA256 verificable ....................... PASS   7/7 recomputados
 3. Facts y contexts pasan los contratos ............. PASS   203/203 audit_status OK
 4. fact_key correcta ................................ PASS   203/203 reproducibles
 5. econ_key correcta ................................ PASS   203/203 reproducibles
 6. Provenance completa para la muestra .............. PASS   70/70 ratios
 7. Auditoria independiente = 0 failures ............. PASS   secciones A-H
 8. Mutaciones todas detectadas ...................... PASS   M1-M10
 9. Segunda corrida idempotente ...................... PASS   0 inserts, digests iguales
10. Produccion = 0 cambios ........................... PASS
11. TIKR no se uso para calibrar ..................... PASS
12. Snapshot persistido y reproducible ............... PASS

METR_FY2024_E2E = PASS
```

**PASS.** Los doce criterios se cumplen por verificación, no por aproximación.
Las limitaciones de §14 son del corpus y del alcance declarado del sprint;
ninguna afecta un criterio del gate.

```
base            cnvmig @ 5433 (fixture aislado)
documentos      7        facts  203        ratios  70/77
auditoria       PASS 0 fallas               tests  29/29
digest facts    2324f732c8dcd39fa3ef1d9f12f356840321d9b4
digest econ     ecd38d81a23c295302f2b64e9b7f61a1e5700fa1
digest valores  ff30bc8c1b2b437707ffb998c8eecf3523a156d2
produccion      SIN CAMBIOS
```
