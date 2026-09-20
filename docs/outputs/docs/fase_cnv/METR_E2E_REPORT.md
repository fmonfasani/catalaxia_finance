# METR E2E GATE: **PASS**

**Fecha:** 2026-09-02 · worktree `catalaxia-cnvmig` · fixture `cnvmig`
**Sin commits · sin integración · `catalaxia` intacta**

La pregunta del ciclo era:

> ¿Catalaxia puede tomar información financiera real de Metrogas desde CNV y
> convertirla en un dato/ratio financiero consumible, correctamente normalizado
> y completamente trazable hasta su fuente?

**Sí, y un tercero puede recorrer el camino sin confiar en el código del
extractor.** La cadena completa está en `METR_E2E_PROVENANCE.md`; los siete
pasos que la reproducen no requieren Catalaxia.

---

## 1 · Scope

Un emisor: METR. No se amplió el universo CNV, no se migraron los otros 71
emisores, no se resolvieron los 292 `UNKNOWN` de W-1.4, no se implementó
`supersedes` ni `effective_*`, no se tocó SEC, Market, el ratio engine ni la
publicación.

---

## 2 · Identidad de METR

| | |
|---|---|
| ticker | METR |
| razón social | Metrogas S.A. |
| CUIT | 30657863676 |
| **entity_id** | **`CUIT:30657863676`** |
| entity_key | `EY9TRR9RPRVSV916PD0CB9Z93NT` |
| identificador | `CUIT:AFIP:30657863676` · autoritativo · ACTIVE |
| CIK | **ninguno — no se inventó** |

`entity_id` es determinístico y estable: `CUIT:` + el CUIT. Los 2.697 facts lo
llevan y **ninguno tiene `cik`**.

---

## 3 · Documentos

| | |
|---|--:|
| documentos usados | **56** |
| todos con RAW en disco | **56/56** |
| todos con SHA-256 verificado hoy | **56/56** |
| todos con `Presentación #N` | **56/56** |
| períodos cubiertos | 29, de 2018-12-31 a 2025-12-31 |
| perímetros | INDIVIDUAL y CONSOLIDADO |

Se cubren FY, Q1, Q2 y Q3 de 2025 en los dos perímetros, más siete ejercicios
anteriores.

---

## 4 · Evidencia RAW

Cada fact apunta a un archivo concreto:

```
source_path   .../eeff_html/d96fd259-c5ce-431f-8e14-17af592b99f9.html
source_hash   460d167241febbe3a3be8142c44be60c6c5eebfd4dc76c53a71b3dfca9b6b191
```

El auditor recomputa el SHA-256 de los 56 archivos y compara: **0 desvíos**.

---

## 5 · Conceptos

Los 8 conceptos del conjunto mínimo **existen los 8** para METR. No se asumió:
se verificó contra los conceptos realmente presentes antes de usarlos.

| concepto | código CNV | categoría | tipo | unidad |
|---|---|---|---|---|
| `Revenue` | 3000100 | resultado | DURATION | `iso4217:ARS` |
| `OperatingIncome` | 3019999 | resultado | DURATION | `iso4217:ARS` |
| `NetIncome` | 3049999 | resultado | DURATION | `iso4217:ARS` |
| `Assets` | 1999999 | activo | INSTANT | `iso4217:ARS` |
| `Liabilities` | 2399999 | pasivo | INSTANT | `iso4217:ARS` |
| `Equity` | 2299999 | patrimonio | INSTANT | `iso4217:ARS` |
| `Cash` | 1122500 | activo | INSTANT | `iso4217:ARS` |
| `EPS_basico` | 8000000 | por acción | DURATION | `iso4217:ARS/xbrli:shares` |

La categoría **no sale del nombre**: sale del primer dígito del plan de cuentas
de la CNV (1 y 2 son saldos, 3 son flujos, 8 son calculados).

---

## 6 · Facts

**448 facts** en la matriz del piloto, sobre 2.697 migrados en total.
`METR_E2E_FACT_MATRIX.csv` — una fila por fact con las 21 columnas pedidas,
incluidas `econ_key`, `fact_key`, `sha256` y `presentacion_n`.

`audit_status` = OK en las 448.

---

## 7 · Semántica de período

```
Q1 2025   DURATION   2025-01-01 → 2025-03-31
Q2 2025   DURATION   2025-01-01 → 2025-06-30
Q3 2025   DURATION   2025-01-01 → 2025-09-30
FY 2025   DURATION   2025-01-01 → 2025-12-31
```

**Los cuatro empiezan el 01-01 porque los estados intermedios de la CNV
publican el acumulado del ejercicio, no el trimestre aislado.** Verificado en
el dato: Revenue 205.186 → 504.193 → 898.642 → 1.217.305 millones.

### Cómo se derivó el 01-01, sin hardcodear

```
16 documentos de METR con PeriodoBalance = 1  →  todos cierran 12-31
     →  cierre de ejercicio = 12-31  →  inicio = 01-01
```

Si el emisor no tuviera documentos anuales, la derivación devuelve `None` y sus
flujos quedan fuera. Los saldos (`Assets`, `Equity`, `Cash`, `Liabilities`) son
`INSTANT`, sin `start_date`, con `measurement_date` = cierre del documento.

---

## 8 · Unidades

| clase | `unit_measure` | `unit_kind` | `currency` |
|---|---|---|---|
| monetaria | `iso4217:ARS` | SIMPLE | ARS |
| adimensional | `xbrli:pure` | SIMPLE | NULL |
| por acción | `iso4217:ARS/xbrli:shares` | DIVIDED | ARS |

`decimals` = **NULL en los 2.697**. La escala de presentación **no se usa como
unidad**: vive en `unit_ref` (`ars@1e6`, `ars@1e3`, `pure`, `ars-por-accion`).

---

## 9 · Perímetro

`declared_perimeter` se conserva en el `context_id` de los 2.697 facts —
1.397 INDIVIDUAL y 1.300 CONSOLIDADO.

Se corrió el detector de W-1.4 y **METR no tiene ningún conflicto de
perímetro**. El detector no modificó el dato: verificado comparando la tabla
antes y después (test I12).

---

## 10 · Ocurrencias

```
2.697 facts  ·  2.697 fact_key distintas  ·  2.697 econ_key distintas
econ_key con más de una ocurrencia: 0
```

**METR no está entre los 7 pares de W-1.3A.** La separación
`identidad económica → ocurrencia` está igualmente implementada y verificada:
`fact_key` incluye el `accn` y es la clave de la ocurrencia; `econ_key` no lo
incluye y agrupa. Si mañana apareciera un segundo documento del mismo período,
las dos ocurrencias coexistirían.

---

## 11 · Ratios

`METR_E2E_RATIO_MATRIX.csv` — 112 filas.

| | |
|---|--:|
| ratios calculados | **110** |
| `NOT_CALCULABLE` | **2** |

### Margen neto — FY2025 CONSOLIDADO

```
net_margin = NetIncome / Revenue
           = 132.483.000.000 / 1.217.305.000.000
           = 0,10883304      (10,88 %)
unidad: xbrli:pure
```

### ROE promedio

```
roe_promedio = NetIncome / ((Equity_inicial + Equity_final) / 2)
```

Exige el **saldo de apertura**. Los 2 `NOT_CALCULABLE` son exactamente el
primer período de la serie (2018-12-31), donde no hay saldo anterior.

> **No se sustituyó el promedio por el saldo de cierre.** `NOT_CALCULABLE` es
> la salida correcta y está en la matriz con su motivo.

---

## 12 · Fórmula

Los dos insumos del margen neto comparten `start_date`, `end_date`,
`period_kind`, `measurement_date` y perímetro. Es la condición que el auditor
verifica **antes** de dividir; sin ella el ratio sale `NOT_CALCULABLE`.

---

## 13 · Provenance

Cadena completa en `METR_E2E_PROVENANCE.md`, con las dos fichas y la
reconciliación manual:

```
8 conceptos comparados contra el RAW  →  8 MATCH · 0 MISMATCH · 0 UNKNOWN
```

La única transformación es la multiplicación por la escala que **el propio
documento declara** (`UnidadMedida = "Millones de $"` → 10⁶), y `EPS_basico` no
la lleva: 229,62 impreso, 229,62 persistido.

---

## 14 · Auditoría independiente

`c4_auditoria_metr_e2e.py` — **2.697 facts · 56 documentos · 0 fallas**.

No importa el extractor, el adaptador, el módulo semántico ni el motor de
ratios. Reconstruye desde el RAW: hashes, escalas, valores, cierre de
ejercicio, `period_kind`, unidades, `fact_key`, `econ_key` y el ratio.

Detalle en `METR_E2E_AUDIT.md`.

---

## 15 · Mutaciones

**12 mutaciones, 12 fallas del auditor.** Ninguna sigue produciendo PASS.

| | mutación | detección |
|---|---|---|
| M1 | valor | "valor no reproduce el RAW" |
| M2 / M2b | unidad · escala en `decimals` | "unidad incorrecta" · "decimals no debe llevar la escala" |
| M3 / M3b | período · flujo→instante | "inicio de ejercicio incorrecto" · "period_kind incorrecto" |
| M4 | identidad | "entity_key no coincide" |
| **M4b** | `entity_key` inventado | **rechazado por la clave foránea, antes del auditor** |
| M5 / M5b | `fact_key` · `econ_key` | "no reproduce la fórmula" |
| M6 | SHA-256 | "no coincide con el archivo" |
| M7 | fórmula invertida | deja de reproducirse desde el RAW |
| M8 | ocurrencia de otro período | "valor no reproduce el RAW" |

Cada mutación corre en una transacción que se revierte.

---

## 16 · Idempotencia

Segunda ejecución del flujo completo:

```
METR_E2E_FACT_MATRIX.csv    sha256 6f4739b87be7b545…  IDÉNTICO
METR_E2E_RATIO_MATRIX.csv   sha256 e730917eeedfd22f…  IDÉNTICO
```

0 duplicados · 0 pérdida · 0 overwrite.

---

## 17 · Regresión W-1.2

`period_kind` · `start_date` · `end_date` · `measurement_date` ·
`unit_measure` · `decimals` · `context_id` · `fact_key`:

```
1.423 DURATION · 1.274 INSTANT · 2.697 measurement_date · 0 decimals no nulos
digest de fact_key y context_id CNV: IDÉNTICOS
auditor W-1.2/W-1.3: sin fallas
```

**W1.2 = PASS**

---

## 18 · Regresión W-1.3A

```
tests W-1.3A            16 passed
auditor W-1.3A          13 OK · 0 fallas · 1 aviso
103.268 ocurrencias · 102.976 identidades · 0 pérdidas
```

**W1.3A = PASS**

---

## 19 · Regresión W-1.4

```
auditor W-1.4           11 OK · 0 fallas
292 identidades múltiples · 7 pares · BYMA con sus 2 ocurrencias
0 supersedes creados · UNKNOWN preservados
```

**W1.4 = PASS**

---

## 20 · Regresión SEC

| | |
|---|---|
| hechos SEC | **IGUAL** — 133.902 |
| digest `fact_key` | **IGUAL** |
| digest `context_id` | **IGUAL** |
| digest `source_hash` | **IGUAL** |
| digest de ratios | **IGUAL** |

```
SEC_UNCHANGED = PASS
```

---

## 21 · Regresión `catalaxia`

```
migraciones                                     34
CNV facts                                        0
columnas entity_id / measurement_date / econ_key  0
```

---

## 22 · Cuestiones abiertas

**O-1 · El ROE promedio de los períodos intermedios no está anualizado.** Se
calcula sobre el acumulado del ejercicio contra el patrimonio promedio de esa
ventana. Es correcto para lo que declara, pero no comparable con un ROE anual.
No se anualizó porque hacerlo requiere una convención que este ciclo no fija.

**O-2 · El trimestre aislado no se persiste.** `YTD(n) − YTD(n−1)` se muestra
en el informe para probar la semántica, y nada más. Persistirlo sería una
transformación adicional con su propia identidad económica.

**O-3 · Un solo emisor, y el más benigno.** METR no tiene conflictos de
perímetro, ni ocurrencias múltiples, ni documentos faltantes. **Que el piloto
pase no prueba que los otros 71 emisores pasen**: BYMA, LONG, INTR, FIPL y
_ADR_0580 tienen problemas que METR no tiene.

**O-4 · Los 12 ratios `CNV_*` que la propia CNV publica no se auditaron** — el
piloto calcula los suyos. La discrepancia conocida de `CNV_roe` sigue abierta.

**O-5 · Nada de esto está integrado.** Vive en el worktree y en el fixture
`cnvmig`. `catalaxia` no tiene un solo hecho CNV.

---

## 23 · Dictamen

| condición de PASS | estado |
|---|---|
| METR correctamente identificado | ✔ CUIT autoritativo, sin CIK inventado |
| `entity_id` correcto | ✔ `CUIT:30657863676` en los 2.697 |
| los documentos RAW existen | ✔ 56/56 |
| los hashes son verificables | ✔ recomputados, 0 desvíos |
| los conceptos están sustentados | ✔ 8/8, desde el código de cuenta |
| los facts están normalizados | ✔ 448 en la matriz, `audit_status` OK |
| los períodos son correctos | ✔ derivados, no hardcodeados |
| las unidades son correctas | ✔ tres clases, `decimals` NULL |
| el perímetro se conserva | ✔ declarado, sin modificar |
| las ocurrencias se preservan | ✔ `fact_key` ≠ `econ_key` |
| al menos un dato atraviesa la cadena | ✔ Revenue FY2025 |
| al menos un ratio la atraviesa | ✔ margen neto 10,88 % |
| la fórmula es reproducible | ✔ desde el RAW |
| los inputs son reproducibles | ✔ 8 MATCH manuales |
| provenance llega hasta RAW | ✔ archivo + SHA-256 |
| auditor independiente coincide | ✔ 0 fallas sobre 2.697 |
| las mutaciones fallan | ✔ 12 de 12 |
| segunda ejecución idempotente | ✔ CSV idénticos |
| W-1.2 sigue PASS | ✔ |
| W-1.3A sigue PASS | ✔ |
| W-1.4 sigue PASS | ✔ |
| SEC intacto | ✔ 5 digests |
| `catalaxia` intacta | ✔ |

Suite completa: **363 passed · 3 failed · 1 skipped** — las 3 son
`test_f038_traza_corrida`, preexistentes desde `DAY3_IMPLEMENTATION_REPORT`.

```
METR E2E GATE = PASS
```

Las cinco cuestiones abiertas son de alcance declarado, no de evidencia
faltante: ninguna afecta al caso certificado. El piloto no necesitó inventar un
mapping, ni completar un dato con conocimiento externo, ni relajar una
tolerancia para convertir un MISMATCH en PASS.

**METR es el primer caso certificado de Catalaxia:
CNV → dato financiero → ratio → provenance → auditoría.**
