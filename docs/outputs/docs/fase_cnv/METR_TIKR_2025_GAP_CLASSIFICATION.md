# METR FY2025 — CLASIFICACIÓN FORENSE DE LOS 66 NO_INPUT

**Fecha:** 2026-09-02 · **READ-ONLY** · no se modificó producción, ni el
modelo, ni una fórmula, ni el gate.
**Universo:** los 66 `CATALAXIA_MISSING_INPUT` de `METR_TIKR_2025_*_MATRIX.csv`,
verificado programáticamente: ni una métrica de más ni de menos.

---

## 1 · Resumen ejecutivo

La pregunta era **por qué** no tenemos cada dato. La respuesta cambia según el
caso, y la diferencia importa:

| clase | problem_type | n | qué significa |
|---|---|--:|---|
| **A** | `EXTRACTION_GAP` | **3** | **está en el RAW y el parser no lo mapea** |
| B | `DERIVATION_GAP` | 10 | derivable de datos que ya tenemos |
| C | `COMPARATIVE_GAP` | 4 | necesita un comparativo o el número de acciones |
| **D** | `CNV_COVERAGE_GAP` | **34** | la CNV no lo publica en el EEFF resumido |
| E | `TIKR_NORMALIZATION` | 4 | criterio propio de TIKR |
| F | `SEMANTIC_AMBIGUITY` | 11 | hay un código relacionado, pero no equivale |
| | **total** | **66** | |

**Evidencia:** 41 HIGH · 25 MEDIUM · 0 LOW.

### Lo que cambió respecto del informe anterior

El informe de reconciliación afirmaba que la participación minoritaria **no
existe como concepto CNV**. **Es falso.** Buscando en el RAW aparecieron
**25 códigos que el parser no mapea**, y tres de ellos son exactamente lo que
TIKR reporta:

| código CNV | etiqueta en el documento | valor | TIKR |
|---|---|--:|--:|
| `2211300` | INTERESES NO CONTROLANTES | **1.880** | 1.880 ✔ |
| `2210300` | AJUSTE DE CAPITAL | **346.707** | 346.707 ✔ |
| `3011100` | OTROS INGRESOS | **10.002** | *Asset Devaluation* 10.002 ✔ |

Los tres coinciden **al peso**. No es que la CNV no los publique: es que
Catalaxia no los extrae.

### Y un hallazgo que no estaba en el universo de los 66

```
8000002  TOTAL PATRIMONIO NETO DEL EJERCICIO ANTERIOR = 829.478
```

El **comparativo re-expresado** está en el RAW, en 51 de los 56 documentos de
METR. Con él:

```
ROE = 132.483 / ((829.478 + 960.345) / 2) = 14,804 %   =  TIKR EXACTO
```

El ciclo anterior clasificó el ROE como `INPUT_DIFFERENCE` y dedujo el factor
de re-expresión (1,3155) del comparativo de caja de TIKR. **El dato estaba
publicado**: 829.478 / 630.542 = 1,3155, el mismo factor.

---

## 2 · Distribución por familia

| familia | A | B | C | D | E | F | total |
|---|--:|--:|--:|--:|--:|--:|--:|
| Balance | 2 | 1 | 0 | 11 | 0 | 8 | **22** |
| Cash Flow | 0 | 1 | 2 | 13 | 0 | 0 | **16** |
| Ratios | 0 | 4 | 0 | 2 | 4 | 0 | **10** |
| Income Statement | 1 | 0 | 0 | 5 | 0 | 2 | **8** |
| Segmentos | 0 | 4 | 0 | 4 | 0 | 0 | **8** |
| Per share | 0 | 0 | 2 | 0 | 0 | 0 | **2** |

---

## 3 · Los tres EXTRACTION_GAP — evidencia directa

Documento `d96fd259-c5ce-431f-8e14-17af592b99f9.html` ·
SHA-256 `460d167241febbe3a3be8142c44be60c6c5eebfd4dc76c53a71b3dfca9b6b191` ·
FY2025 · CONSOLIDADO · escala 10⁶.

| métrica TIKR | código | etiqueta | valor RAW | TIKR | evidencia |
|---|---|---|--:|--:|---|
| Other Comprehensive Income / Other | `2210300` | AJUSTE DE CAPITAL | 346.707 | 346.707 | HIGH |
| Minority Interest | `2211300` | INTERESES NO CONTROLANTES | 1.880 | 1.880 | HIGH |
| Asset Devaluation | `3011100` | OTROS INGRESOS | 10.002 | 10.002 | HIGH |

**Los tres cierran el patrimonio completo:**

```
Capital 569 + (Reservas + RdosNoAsignados) 611.189
            + AJUSTE DE CAPITAL 346.707
            + INTERESES NO CONTROLANTES 1.880   =  960.345  =  Equity   ✔
```

`2211300` aparece en 27 de los 56 documentos; `2210300` en los 56; `3011100`
en 44.

---

## 4 · Los 34 CNV_COVERAGE_GAP — dónde se concentran

**No están en el EEFF resumido de la CNV.** Se buscó en los 76 códigos
presentes en los documentos de METR y no hay equivalente.

| bloque | n | qué falta |
|---|--:|---|
| desglose del flujo de efectivo | 13 | la CNV publica **tres subtotales** (3241100/200/300) y nada más: sin capex, sin cambios en partidas, sin deuda emitida/repagada |
| desglose del balance | 11 | PP&E bruto, depreciación acumulada, tierra, edificios, obras en curso, otras cuentas por cobrar, gastos pagados por adelantado, leasing |
| segmentos: eliminaciones | 4 | la CNV no publica eliminaciones de consolidación |
| partidas inusuales del resultado | 5 | ganancias por venta de inversiones, litigios, otros no operativos, dividendos |
| ratios que dependen de lo anterior | 2 | Return on Capital, Dividend Yield |

El desglose del balance está **en las notas** a los estados contables, que no
se descargan: el pipeline baja el EEFF resumido.

---

## 5 · Los 11 SEMANTIC_AMBIGUITY — el caso más delicado

En estos **sí existe un código CNV**, pero **no equivale** al renglón de TIKR.
Mapearlos por nombre sería exactamente el error que este ciclo debe evitar.

| métrica TIKR | TIKR | código CNV | valor CNV | ¿por qué no equivale? |
|---|--:|---|--:|---|
| Short-Term Investments | 2.555 | `1122300` | 14.624 | agrupan distinto |
| Long-Term Investments | 1.834 | `1112400` | 2.872 | ídem |
| Other Long-Term Assets | 2.126 | `1112500` | 1.099 | ídem |
| Current Income Taxes Payable | 7.176 | `2322100` | 30.948 | ídem |
| Non-Current Deferred Tax Liab. | 102.098 | `2312200` | 290 | ídem |
| Other Non-Current Liabilities | 28.059 | `2312400` | 108.506 | ídem |
| Current Portion Long-Term Debt | 34.418 | `2322200` | 71.079 | el código agrega más que la deuda financiera |
| Long-Term Debt | 52.119 | `2312300` | 73.480 | ídem |
| Interest Income | 17.052 | `3021400` | 43.721 | el código agrega intereses y otros resultados financieros |
| FX Gains/Losses | −3.121 | `3021400`/`3021500` | — | el resultado cambiario está embebido |
| SG&A Margin | 13,0 % | `3011200`+`3011300`+`3011301` | 216.763 | los tres códigos existen, pero su suma implica 17,8 %, no 13,0 % |

> **El caso SG&A es instructivo.** Los tres códigos **sí están en el RAW**:
> GASTOS DE COMERCIALIZACIÓN 128.411, OTROS GASTOS DE ADMINISTRACIÓN 87.580,
> HONORARIOS A DIRECTORES 772. Suman 216.763. TIKR implica 13,0 % × 1.217.305 =
> 158.250. **No hay combinación evidente que dé ese número**, así que no se
> mapea. Es `SEMANTIC_AMBIGUITY`, no `EXTRACTION_GAP`.

---

## 6 · Los 10 DERIVATION_GAP — y por qué 6 están bloqueados

| métrica | insumos | estado |
|---|---|---|
| Free Cash Flow | CF_Operativo ✔ + **Capex ✘** | bloqueado |
| Levered FCF Margin | FCF ✘ + Revenue ✔ | bloqueado |
| Unlevered FCF Margin | FCF ✘ + Revenue ✔ | bloqueado |
| (EBITDA − Capex) / Interés | EBITDA ✔ + **Capex ✘** + Interés ✔ | bloqueado |
| Net Debt / (EBITDA − Capex) | deuda ✔ + Cash ✔ + EBITDA ✔ + **Capex ✘** | bloqueado |
| Current Unearned Revenue | Payables ✔ − AP de TIKR | **circular**: sólo se deriva conociendo el dato de TIKR |
| MetroENERGY · 4 métricas | CONSOLIDADO ✔ − INDIVIDUAL ✔ | **parcial**: da MetroENERGY **+ eliminaciones**, no cada uno |

**Cinco de las diez dependen del mismo dato faltante: el capex.** No son cinco
problemas, es uno.

---

## 7 · Los 4 COMPARATIVE_GAP

| métrica | qué falta |
|---|---|
| Cash Beginning | la caja de apertura **re-expresada**. Se buscó en el RAW: **ningún código tiene un valor cercano a 160.859**, y los únicos códigos de flujo son los tres subtotales |
| Book Value / Share | el número de acciones en circulación |
| Tangible Book Value / Share | ídem |
| Cash Flow per Share | ídem |

> **`Capital` = 569 y las acciones ponderadas de TIKR también valen 569.** Es
> una coincidencia de magnitud entre el capital social y el número de acciones.
> **No hay evidencia de que sean el mismo concepto**, y usarla sería
> exactamente el error de `ResultadosNoAsignados` que ya se descartó.

---

## 8 · Los 4 TIKR_NORMALIZATION

| métrica | por qué no se puede reproducir |
|---|---|
| EBT excl. Unusual Items | exige la lista de partidas inusuales de TIKR |
| EBITA Margin | exige separar amortización de depreciación; el código `3011600` las agrega |
| FFO / Interest Expense | el FFO exige el desglose del flujo operativo |
| FFO / Total Debt | ídem |

---

## 9 · Clusters: cinco dependencias explican 30 métricas

| dependencia | métricas que desbloquea |
|---|--:|
| **desglose del flujo de efectivo** (capex y demás) | **18** — 13 D + 5 B |
| **desglose del balance** (notas) | **11** |
| **desglose de la deuda financiera** | **4** (2 F del balance + 2 ratios) |
| **número de acciones** | **3** |
| **eliminaciones de consolidación** | **4** + habilita las 4 B de segmentos |

Reportar 66 problemas independientes sería engañoso: **son cinco.**

---

## 10 · Tabla completa

`METR_TIKR_2025_GAP_CLASSIFICATION.csv` — 66 filas, 23 columnas:

```
metric · tikr_value · classification · problem_type · cnv_available
cnv_code · cnv_qname · cnv_value · cnv_unit · cnv_scale · period · perimeter
derivable · required_inputs · inputs_available · requires_comparative
requires_reexpression · requires_reclassification · raw_evidence
evidence_strength · recommended_action · notes · family
```

---

## 11 · Tests

`tests/test_metr_tikr_2025_gap_classification.py` — **22 passed**.

| grupo | qué exige |
|---|---|
| cobertura | las 66 clasificadas exactamente una vez, ninguna fuera del universo |
| consistencia | clase ↔ `problem_type` biunívoco; toda métrica con nota |
| clase A | código CNV presente, valor releído del RAW, **coincide con TIKR**, evidencia HIGH obligatoria |
| clase B | insumos concretos enumerados |
| clase C | nombra el comparativo o el dato periódico que falta |
| clase D | declara `cnv_available = no` |
| D/E/F | ninguna se trata como match |
| LOW | prohibido sin explicar por qué la evidencia es débil |

**Mutaciones (M1–M7):** borrar el código del RAW, alterar el valor, el período,
el perímetro, la unidad, quitar un insumo de una derivación B, quitar el
comparativo de una C. **Las siete tumban la clasificación.**

> **Los tests encontraron dos errores míos.** (1) Clasifiqué `Cash Beginning`
> como A sin código que la sustentara — el test de evidencia lo detectó y se
> reclasificó a C tras verificar que el comparativo de caja **no** está en el
> RAW. (2) M7 asumía que toda C menciona "acciones"; se generalizó sin
> debilitarlo.

---

## 12 · Integridad — read-only confirmado

| | |
|---|---|
| `derived.fact` | 136.599 |
| `identity_v1.entity` | 526 |
| `derived.ratio` | 36 |
| documentos CNV | 56 |
| digest `fact_key` SEC · `source_hash` SEC · ratios SEC | **IGUAL** |
| digest `fact_key` CNV · `context_id` CNV | **IGUAL** |
| `screener.db` mtime | 2026-08-23 13:42:23 (sin cambios) |
| `catalaxia` | 34 migraciones · 0 hechos CNV |

**Ningún script de este ciclo escribe.** Todos abren la base en modo lectura y
el RAW con `read_text`.
