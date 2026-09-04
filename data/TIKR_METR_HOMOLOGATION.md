# TIKR vs Catalaxia — homologación exhaustiva de METROGAS

**327 comparaciones. 8 sin explicar (2,4 %).**
No se modificó producción, ni `screener.db`, ni el ratio engine, ni ninguna
fórmula. No se ajustó nada para acercarse a TIKR.

| | |
|---|---|
| entidad | Metrogas S.A. · CUIT 30657863676 · `entity_id` `CUIT:30657863676` |
| ejercicios | FY2021 – FY2025, perímetro CONSOLIDADO |
| benchmark | `TIKR_METR_BENCHMARK_ARS_USD.xlsx` · md5 `0ebef96aa8f6b4a59abf57207901015c` |
| base del demo | `metr5y` @ 5433 (aislada) — **no** es producción |
| producción | `catalaxia` @ 5432, esquema `public`; `screener.db` 1.504.714.752 B — intactos |

---

## 1. Diagnóstico del entorno

Antes de comparar, qué es qué:

| pieza | dónde |
|---|---|
| pipeline CNV | `scripts/tickets/cnv/jobs/job5_v2_extract_eeff.py` (extracción del formulario) |
| adapter a canónico | `scripts/engine/c4_cnv_adapter.py` → `parsed.facts` + `derived.fact` |
| demo METR 5Y | `scripts/engine/d2_metr5y_model.py` (Financial Model + ratios) |
| outputs METR | `outputs/docs/fase_cnv/METR_5Y_DEMO.*` |
| registry de ratios | `scripts/engine/ratio_defs.py` (`CONCEPTOS`, `RATIOS_MODELO`) |
| ratio engine SEC | `scripts/engine/ratio_engine.py` + `ratio_inputs.py` |
| provenance | `derived.fact.source_fact_ids` → `parsed.facts`; `fact_key`, `econ_key` |
| market / FX | `market.price` (yfinance METR.BA), `market.fx_rate` (MEP de dolarito) |
| **base del demo** | **`metr5y`** — creada para esto, con las 35 migraciones canónicas |
| **producción** | **`catalaxia` @ 5432 y `screener.db`** — sólo lectura en todo el trabajo |

De dónde sale cada cosa en Catalaxia: los *facts* del formulario estructurado de
la CNV; el *contexto* de `context_id` (perímetro + tipo de período + fechas); los
*períodos* de `report_period` y `measurement_date`; las *unidades* de `unit_ref`
(`ars@1e6`) y `unit_measure`; los *ratios* del registry evaluado sobre el
Financial Model; el *market* de yfinance con guarda de moneda; el *FX* del MEP
de dolarito; las *acciones* del capital social nominal; la *valuación* de
precio × acciones.

---

## 2. El benchmark es más chico de lo que el encargo asume

El encargo describe hojas de Income Statement, Balance Sheet, Cash Flow, Ratios,
Business Segments, Valuation y LTM. El archivo real tiene **5 hojas y 14 KB**:

| hoja | contenido |
|---|---|
| `ARS_KEY` | 15 métricas × 2020–2025 + LTM |
| `USD_KEY` | 22 métricas × 2021–2025 + LTM |
| `USD_TIKR_USD_RAW` | estado de resultados en USD, 2021–2025 + LTM |
| `ARS_SCOPE`, `USD_README` | metadatos |

**No hay hoja de Balance Sheet detallado, ni de Cash Flow detallado, ni de
Business Segments.** La hoja `ARS_SCOPE` los declara como alcance, pero los datos
no están en el archivo. Por eso las secciones 8, 9 y 12 del encargo se responden
por lo que el benchmark efectivamente trae: de los ~60 renglones de balance
pedidos sólo se pueden comparar 5 (Cash, Total Assets, Total Liabilities, Total
Equity, Total Debt, Net Debt), y de los ~25 de cash flow sólo 3 (CFO, CapEx,
FCF). Los segmentos no se pueden comparar: no están de ningún lado.

---

## 3. Los períodos: TIKR y Catalaxia no hablan del mismo número

**Éste es el hallazgo central y explica el 25 % de las diferencias.**

Para cada año N anterior al último, **TIKR publica la cifra de FY(N) tal como fue
REEXPRESADA en los estados de FY(N+1)** — la columna comparativa. Catalaxia
publica la cifra tal como fue reportada en FY(N).

La prueba no es una correlación: es un **coeficiente único por año que aplica
idéntico a métricas independientes**.

| FY | Revenue | Assets | Equity | Net Income | coeficiente |
|---|---:|---:|---:|---:|---:|
| 2021 | 1,948 | 1,948 | 1,948 | 1,960 | **1,9479** |
| 2022 | 3,114 | 3,114 | 3,114 | 3,035 | **3,1141** |
| 2023 | 2,152 | 2,178 | 2,178 | 2,156 | **2,1776** |
| 2024 | 1,316 | 1,316 | 1,315 | 1,297 | **1,3155** |
| 2025 | 1,000 | 1,000 | 1,000 | 0,986 | **1,0000** |

Y la confirmación independiente: el coeficiente se midió **con datos internos de
Catalaxia** —`PatrimonioAperturaEjercicio` de FY(N+1) sobre `Equity` de FY(N)—
sin mirar TIKR. El resultado coincide **exacto** con el patrimonio que TIKR
publica:

```
TIKR Total Equity 2021 = 33.790   Catalaxia PatrimonioAperturaEjercicio(FY2022) = 33.790
TIKR Total Equity 2022 = 123.144  Catalaxia PatrimonioAperturaEjercicio(FY2023) = 123.144
TIKR Total Equity 2023 = 475.654  Catalaxia PatrimonioAperturaEjercicio(FY2024) = 475.654
TIKR Total Equity 2024 = 829.478  Catalaxia PatrimonioAperturaEjercicio(FY2025) = 829.478
```

FY2025 da coeficiente 1,0000 porque todavía no existen los estados de FY2026.
Ahí las cifras coinciden **exacto**: Revenue 1.217.305, Assets 1.390.076, Equity
960.345, Cash 116.132, CFO 89.042, Total Liabilities 429.731. Seis `MATCH`.

**Ninguno de los dos está mal.** Son dos convenciones legítimas: TIKR prioriza la
comparabilidad de la serie, Catalaxia la fidelidad a lo que el emisor reportó y
auditó en cada ejercicio. Lo que sí es un problema —y va al backlog como P0— es
que Catalaxia no persiste la columna comparativa: la tiene delante y la descarta.

---

## 4. El FX: TIKR usa mayorista, Catalaxia usa MEP

El FX implícito de TIKR (ARS ÷ USD, de sus propias hojas) contra las cuatro
series disponibles:

| FY | FX implícito TIKR | OFICIAL | MEP | CCL | **MAYORISTA** | desvío vs mayorista |
|---|---:|---:|---:|---:|---:|---:|
| 2021 | 102,69 | 107,75 | 197,80 | 202,13 | **102,72** | **0,0 %** |
| 2022 | 176,75 | 183,25 | 327,94 | 344,13 | **177,16** | **0,2 %** |
| 2023 | 808,46 | 828,25 | 995,00 | 973,31 | **808,45** | **0,0 %** |
| 2024 | 1.030,50 | 1.052,50 | 1.170,41 | 1.184,16 | **1.032,00** | **0,1 %** |
| 2025 | 1.451,00 | 1.480,00 | 1.480,74 | 1.521,34 | **1.455,00** | **0,3 %** |

**TIKR usa el dólar mayorista (A3500)**, con 0,0–0,3 % de desvío en los cinco
años. Catalaxia usa MEP. La brecha va del **85 % en 2021** al **1,8 % en 2025**.

Confirmación independiente: 7 de las 9 métricas que el benchmark publica en las
dos monedas reconcilian entre sí al 0,0–0,3 % usando mayorista. `FX_DEFINITION_DIFFERENCE`
demostrada. **No se cambió el FX de Catalaxia.**

---

## 5. El perímetro del resultado

TIKR publica *Net Income to Common* (atribuible a los propietarios). El
`NetIncome` de la CNV (código 3049999) es el **total**, con minoritarios.

| FY | Catalaxia NetIncome | − NCI | × coef | TIKR NI Common | residuo |
|---|---:|---:|---:|---:|---:|
| 2021 | −4.369 | −4.401 | −8.573 | −8.562 | 0,13 % |
| 2022 | 5.814 | 5.663 | 17.635 | 17.648 | 0,07 % |
| 2023 | 96.355 | 95.990 | 209.020 | 207.723 | 0,62 % |
| 2024 | 156.628 | 155.359 | 204.375 | 203.133 | 0,61 % |
| 2025 | 132.483 | 130.603 | 130.603 | 130.656 | 0,04 % |

**Advertencia sobre el método:** el ajuste resta `InteresesNoControlantes`, que
es el NCI **patrimonial** (INSTANT), no la porción del resultado — la CNV no
publica esa última. Es un **proxy**, no el concepto correcto. Reconcilia entre
0,04 % y 0,62 % en los cinco ejercicios, lo que lo valida empíricamente, pero no
lo convierte en el dato bueno. Va al backlog como P1.

---

## 6. Resultado ejecutivo

| estado | n | % |
|---|---:|---:|
| `PERIOD_MISMATCH` | 82 | 25,1 % |
| `CATALAXIA_MISSING` | 73 | 22,3 % |
| `DIFFERENT_DEFINITION` | 63 | 19,3 % |
| `CATALAXIA_ONLY` | 30 | 9,2 % |
| `MATCH` | 25 | 7,6 % |
| `CLOSE` | 16 | 4,9 % |
| `ANOMALY` | 14 | 4,3 % |
| `CURRENCY_MISMATCH` | 11 | 3,4 % |
| `UNRESOLVED` | **8** | **2,4 %** |
| `UNIT_MISMATCH` | 3 | 0,9 % |
| `SOURCE_MISMATCH` | 1 | 0,3 % |
| `TIKR_ONLY` | 1 | 0,3 % |
| **total** | **327** | |

**41 comparaciones (12,5 %) coinciden sin ninguna corrección** — y son
exactamente las que deberían: todo FY2025 en ARS (donde no hay reexpresión), los
precios de cierre, el market cap, los ratios de liquidez y la tasa impositiva
efectiva.

**278 (85 %) difieren por una causa identificada y medida.**

**8 (2,4 %) no tienen explicación** y se declaran así.

### Umbrales usados

No hay un único umbral: 0,5 % sobre un activo de un billón son 5.000 millones y
0,5 % sobre un current ratio es ruido de redondeo.

| naturaleza | `MATCH` | `CLOSE` | por qué |
|---|---|---|---|
| monetario | 0,1 % | 2 % | TIKR redondea a millón |
| ratio | 0,5 % | 5 % | |
| porcentaje | 0,5 pp | 3 pp | se mide en puntos **y** en relativo |
| por acción | 1 % | 5 % | el EPS de TIKR viene con 2 decimales |
| precio / conteo | 0,1 % | 1 % | |

---

## 7. Las 20 diferencias más materiales

| # | métrica | FY | TIKR | Catalaxia | estado | causa |
|---|---|---|---:|---:|---|---|
| 1 | EBITDA | 2021 USD | 293,77 | 4,54 | `ANOMALY` | el benchmark se contradice a sí mismo |
| 2 | EBITDA | 2022 USD | 777,18 | 23,80 | `ANOMALY` | ídem |
| 3 | EBITDA | 2023 USD | 493,17 | 21,46 | `ANOMALY` | ídem |
| 4 | EBITDA | 2024 USD | 470,45 | 160,42 | `ANOMALY` | ídem |
| 5 | Revenue | 2022 | 333.607 | 107.128 | `PERIOD_MISMATCH` | reexpresión ×3,1141 |
| 6 | Total Assets | 2022 | 488.254 | 156.788 | `PERIOD_MISMATCH` | ídem |
| 7 | Total Equity | 2023 | 475.654 | 218.430 | `PERIOD_MISMATCH` | reexpresión ×2,1776 |
| 8 | Net Income Common | 2023 | 207.723 | 96.355 | `PERIOD_MISMATCH` | reexpresión + perímetro |
| 9 | Total Debt | 2025 | 86.550 | 144.559 | `DIFFERENT_DEFINITION` | pasivos financieros ⊃ deuda |
| 10 | Total Debt | 2023 | 55.469 | 33.490 | `DIFFERENT_DEFINITION` | ídem |
| 11 | CapEx | todos | −52.073 (2025) | — | `CATALAXIA_MISSING` | la fuente no lo publica |
| 12 | FCF | todos | 36.969 (2025) | — | `CATALAXIA_MISSING` | depende de CapEx |
| 13 | D&A | 2025 | 12,33 USD | −40,78 USD | **`UNRESOLVED`** | factor 2,5–3,7 sin patrón |
| 14 | ROE | 2023 | 69,5 % | 44,1 % | `DIFFERENT_DEFINITION` | TIKR usa patrimonio promedio |
| 15 | ROA | 2023 | 28,0 % | 21,1 % | `DIFFERENT_DEFINITION` | TIKR usa activo promedio |
| 16 | P/E | 2024 | 16,84 | 10,26 | `ANOMALY` | no reconstruible con sus propios inputs |
| 17 | P/B | 2024 | 2,79 | 2,51 | `ANOMALY` | ídem |
| 18 | EV/Revenue | 2024 | 3,25 | 1,63 | `ANOMALY` | ídem |
| 19 | Gross Profit | 2025 | 291,32 USD | 314,16 USD | `DIFFERENT_DEFINITION` | TIKR reclasifica el corte de gastos |
| 20 | Closing Price | 2022 | 101,00 | 103,00 | `SOURCE_MISMATCH` | ninguna rueda cotiza a 101,00 |

---

## 8. CapEx — investigación prioritaria

**Pregunta: ¿de dónde saca TIKR el CapEx y por qué Catalaxia no lo tiene?**

El formulario estructurado de la CNV publica el estado de flujo de efectivo en
**tres renglones y nada más**:

```
3241100  TOTAL CAMBIOS EN ACTIVOS Y PASIVOS OPERATIVOS      89.042
3241200  TOTAL DE ACTIVIDADES DE INVERSION                 -58.733
3241300  TOTAL DE ACTIVIDADES DE FINANCIACION              -42.338
3240000  INCREMENTO (DISMINUCION) NETA DE EFECTIVO         -12.029
```

De los 70 códigos con valor del documento FY2025, **ninguno desagrega la
inversión**. No es un fallo de extracción: el dato no está en la fuente que
Catalaxia lee.

Se descartaron las alternativas:

| hipótesis | resultado |
|---|---|
| ¿está en otro código del formulario? | **no** — los 70 códigos son de los grupos 1/2/3/8 y ninguno es capex |
| ¿es el flujo de inversión total? | **no** — TIKR CapEx 2025 = −52.073 contra CFI −58.733; el resto son otras inversiones |
| ¿se puede derivar de PP&E? | **no bajo IAS 29** — PP&E 2025 − PP&E 2024 = 258.911 más D&A 60.383 = 319.294 contra 52.073 de TIKR. La reexpresión del saldo domina el movimiento real |
| ¿está en un adjunto? | **sí** |

**El adjunto existe, está identificado, y Catalaxia no lo descarga.** El HTML que
ya ingesta publica:

```json
{"nombreArchivo":"Estados Financieros_1225_CON.pdf",
 "guid":"7b20be66-ac97-4ded-f499-dbde07fb7ce6",
 "tamano":"1.54 MB",
 "hash":"5PnF6/cC3SXk664ZeFsYz4nWCcBchyc/LwQrNrI+J44="}
```

**Hay 0 PDF descargados en todo `scripts/tickets/cnv/`.** Catalaxia tiene el
puntero y el control de integridad, y nunca fue a buscar el contenido.

**Conclusión: no es "TIKR correcto / Catalaxia incorrecto". Es una fuente que
Catalaxia debería ingerir y no ingiere.** → **P0**.

## 9. FCF

`FCF = CFO − CapEx`. Los dos lados del CFO **coinciden**: FY2025 TIKR 89.042 y
Catalaxia 89.042, `MATCH` exacto. Sin CapEx no hay FCF.

`CATALAXIA_MISSING`, y **no se inventa**: no se sustituye por el flujo de
inversión, que incluye compras de activos financieros y no es capex. Arrastra a
`fcf_margin`, `fcf_yield`, `fcf_to_debt`, `fcf_to_net_income`, `price_to_fcf`,
`fcf_to_ev` y `fcf_growth`.

---

## 10. Valuación — reconstrucción independiente

Se reconstruyó cada componente antes de comparar un solo múltiplo.

| ARS millones | 2021 | 2022 | 2023 | 2024 | 2025 |
|---|---:|---:|---:|---:|---:|
| Price (ARS) | 38,60 | 103,00 | 768,00 | 2.785,00 | 2.547,50 |
| Shares (M) | 569,17 | 569,00 | 569,00 | 569,00 | 569,00 |
| **MC = P × Sh** | 21.970 | 58.607 | 436.992 | 1.584.665 | 1.449.528 |
| **MC TIKR** | 21.970 | 57.486 | 437.123 | 1.585.142 | 1.449.964 |
| **desvío** | **−0,00 %** | 1,95 % | **−0,03 %** | **−0,03 %** | **−0,03 %** |

**El market cap reconcilia al −0,03 % en cuatro de los cinco años.** Eso valida
de forma independiente el recuento de acciones de Catalaxia (569 M, del capital
social nominal): TIKR llega al mismo market cap, luego usa el mismo recuento. El
único año que se aparta es 2022, y por el precio, no por las acciones.

| | 2021 | 2022 | 2023 | 2024 | 2025 |
|---|---:|---:|---:|---:|---:|
| Debt Catalaxia | 17.749 | 21.517 | 33.490 | 44.278 | 144.559 |
| Debt TIKR | 31.499 | 58.522 | 55.469 | 36.207 | 86.550 |
| EV Catalaxia | 33.822 | 66.364 | 438.729 | 1.506.663 | 1.477.954 |
| EV TIKR | 33.667 | 62.024 | 447.777 | 1.511.812 | 1.430.556 |

La deuda es el componente que no cierra, y la causa es de definición (§11).

### Los múltiplos de TIKR no se reconstruyen con los propios números de TIKR

| múltiplo, con inputs de TIKR | 2021 | 2022 | 2023 | 2024 | 2025 |
|---|---:|---:|---:|---:|---:|
| P/E = MC / NI Common | −2,57 | 3,26 | 2,10 | 7,80 | **11,10** |
| P/B = MC / Equity | 0,65 | 0,47 | 0,92 | 1,91 | **1,51** |
| EV/Revenue = EV / Revenue | 0,31 | 0,19 | 0,63 | 1,24 | **1,18** |
| **Catalaxia P/E** | — | 10,34 | 4,58 | 10,26 | **11,09** |
| **Catalaxia P/B** | 1,27 | 1,48 | 2,00 | 2,51 | **1,51** |
| **Catalaxia EV/Revenue** | 0,61 | 0,62 | 1,34 | 1,63 | **1,21** |

**En FY2025 los tres coinciden** (11,10 vs 11,09; 1,51 vs 1,51; 1,18 vs 1,21).
En 2021–2024 los múltiplos de TIKR construidos con sus propios inputs quedan
por debajo de los de Catalaxia por un factor que es **el coeficiente de
reexpresión**: 2,10 × 2,1776 = 4,57 contra 4,58 de Catalaxia en 2023.

**Eso significa que la serie ARS de TIKR mezcla poderes adquisitivos**: el market
cap es nominal del año N y los fundamentals están reexpresados a N+1. Dividir uno
por el otro da un múltiplo que no corresponde a ningún momento. La serie de
Catalaxia no tiene ese problema porque precio y fundamentals son del mismo
cierre.

Y los múltiplos que TIKR **publica** (P/E 16,84, P/B 2,79, EV/Revenue 3,25,
EV/EBITDA 7,28, todos sólo en la columna 2024) no se reconstruyen con los inputs
del propio benchmark en ninguna moneda ni base probada → `ANOMALY`.

## 11. P/E — análisis específico

**Catalaxia, dos caminos** (del demo METR 5Y):

| FY | precio / EPS | market cap / NI | desvío | veredicto |
|---|---:|---:|---:|---|
| 2021 | — (EPS ≤ 0) | −5,03 | — | `INCOMPARABLE` |
| 2022 | 10,34 | 10,08 | 2,6 % | `CLOSE` |
| 2023 | 4,58 | 4,54 | 1,0 % | `CLOSE` |
| 2024 | 10,26 | 10,12 | 1,4 % | `CLOSE` |
| 2025 | 11,09 | 10,94 | 1,4 % | `CLOSE` |

Los dos caminos de Catalaxia cierran entre sí. La diferencia residual es el
recuento de cierre contra el promedio ponderado implícito en el EPS.

**TIKR** publica un único P/E (16,84) en una sola columna, que no se reconstruye
ni con su market cap sobre su net income (7,80) ni con su price sobre su EPS.
El desvío no viene de EPS, ni de acciones, ni de net income, ni de precio: viene
de que **el múltiplo publicado no es reconstruible con lo que el benchmark trae**.

## 12. Acciones

| | tipo | valor | fuente |
|---|---|---|---|
| Catalaxia | recuento de cierre | 569.171.000 / 569.000.000 | `Capital` (capital social nominal, par $1) |
| Catalaxia (control) | promedio ponderado implícito | 565,9 M – 583,7 M | `NetIncome / EPS_basico` |
| TIKR | implícito en su market cap | ≈ 569 M | `Market Cap / Closing Price` |
| TIKR | implícito en su EPS | 555 M – 571 M | `NI Common / Diluted EPS` |

Los cuatro caminos convergen en ~569 M. **No son equivalentes conceptualmente**
—cierre contra promedio ponderado— pero la diferencia es del 0,6–2,5 % y no
mueve materialmente EPS, P/E, market cap, P/B ni P/S.

### Anomalía del benchmark: las acciones convertidas por el tipo de cambio

La fila *Promedio ponderado de acciones* de la hoja USD publica
5,54 / 3,22 / 0,70 / 0,55 / 0,39. Un recuento de acciones no puede caer un 93 %
en cuatro años sin un reverse split, y no lo hubo. La explicación es aritmética:

```
569.000.000 / 102,69 = 5,54     569.000.000 / 1.030,50 = 0,55
569.000.000 / 176,75 = 3,22     569.000.000 / 1.451,00 = 0,39
569.000.000 / 808,46 = 0,70
```

**TIKR aplicó la conversión a USD también al número de acciones.** Es un artefacto
de convertir todas las filas del estado en bloque. No afecta a Catalaxia; sí
invalida esa fila del benchmark como referencia. → `ANOMALY`, P2.

---

## 13. Total Debt — diferencia de definición

La CNV rotula, y Catalaxia toma:

```
2322200  PASIVOS FINANCIEROS CORRIENTES         71.079
2312300  PASIVOS FINANCIEROS NO CORRIENTES      73.480
                                               -------
         deuda_financiera_total                144.559     TIKR Total Debt: 86.550
```

`PASIVOS FINANCIEROS` es una categoría IFRS **más amplia** que "deuda": incluye
pasivos por arrendamiento y derivados. TIKR publica Total Debt en sentido
estricto. La diferencia de FY2025 son 58.009 millones.

Arrastra a `Net Debt`, `EV`, `debt_to_equity`, `debt_to_ebitda` y
`net_debt_to_ebitda`. `ratio_defs.py` ya lleva un comentario advirtiendo lo mismo
para `Borrowings` contra `LongTermDebt` en SEC: es el mismo problema, en otra
taxonomía.

---

## 14. Anomalías del benchmark

Tres, todas verificables con aritmética sobre el propio archivo:

**1. El EBITDA de TIKR en ARS y en USD no reconcilian entre sí.**
Se comprobó dividiendo el valor ARS por el USD y comparando contra el mayorista,
el mismo tipo que el resto de sus métricas respeta al 0,3 %:

| métrica | 2021 | 2022 | 2023 | 2024 | 2025 | |
|---|---:|---:|---:|---:|---:|---|
| Revenue | −0,0 % | −0,2 % | +0,0 % | −0,1 % | −0,3 % | consistente |
| Net Income Common | −0,0 % | −0,2 % | −0,0 % | −0,1 % | −0,3 % | consistente |
| CFO | −0,0 % | −0,2 % | +0,0 % | −0,1 % | −0,3 % | consistente |
| CapEx | −0,0 % | −0,2 % | +0,0 % | −0,2 % | −0,3 % | consistente |
| Total Assets / Liabilities / Equity | ≤0,2 % | ≤0,2 % | ≤0,2 % | ≤0,1 % | ≤0,3 % | consistente |
| **EBITDA** | **−97,6 %** | **−86,7 %** | **−90,6 %** | **−51,7 %** | **−22,2 %** | **inconsistente** |
| **FCF** | **+13,1 %** | +2,6 % | +1,7 % | +2,2 % | +1,7 % | **inconsistente** |

Siete de nueve métricas reconcilian; EBITDA no. Sin saber cuál de las dos series
es la buena, no hay contra qué comparar el EBITDA de Catalaxia → `ANOMALY`.

**2. Los múltiplos de valuación no se reconstruyen con los inputs del benchmark**
(§10).

**3. Las acciones convertidas por el tipo de cambio** (§12).

---

## 15. Qué tiene TIKR que Catalaxia no

Verificado contra la base, no supuesto:

| dato | estado en Catalaxia |
|---|---|
| CapEx | **falta** — fuente no ingerida (§8) |
| FCF y su familia | **falta** — depende de CapEx |
| Segmentos de negocio | **falta** — y tampoco están en el benchmark |
| Normalized EBITDA / EPS / P/E | **falta** — TIKR normaliza con criterio no publicado |
| SG&A con el corte de TIKR | **falta** — la CNV desagrega distinto |
| Remuneraciones al personal | **falta** — no hay código CNV |
| Serie comparativa reexpresada | **falta** — `valor_comparativo` existe en el esquema y está vacío en las 4.648 filas |
| DSO, DIO, DPO, ciclo de conversión, turnovers | **falta en el registry** — pero los insumos (`Receivables`, `Payables`, `Inventory`) **sí están** en la capa canónica |

## 16. Qué tiene Catalaxia que TIKR no expone

| | |
|---|---|
| `fact_key` | identidad de ocurrencia, sha256 de entidad+documento+concepto+contexto+unidad |
| `econ_key` | identidad económica, con `measurement_date` |
| `context_id` | perímetro + tipo de período + fechas, explícito en cada celda |
| `accession` + sha256 del RAW | el documento exacto y su hash de contenido |
| `parsed.facts` → `derived.fact` | la cadena completa, verificada sin eslabones rotos |
| tag elegido por celda | cuál de los candidatos del registry resolvió el concepto |
| `unit_ref` | la escala declarada por el documento (`ars@1e3` en 2021, `ars@1e6` después) |
| perímetro evidenciado | contrastado contra el nombre del adjunto, no sólo el campo declarado |
| motivo tipificado de cada no-calculable | 44 celdas con causa, no celdas vacías |

Ninguna de estas nueve cosas está en el benchmark. Del lado de TIKR no hay forma
de preguntar "¿de qué documento salió este número?".

Y hay una ventaja de método que el propio ejercicio demostró: **la serie de
Catalaxia no mezcla poderes adquisitivos en los múltiplos** (§10), y la de TIKR
sí.

---

## 17. Lo que queda sin explicar

**8 comparaciones (2,4 %), todas D&A / Depreciation.**

El D&A de TIKR es entre 2,5 y 3,7 veces menor que el código 3011600
`DEPRECIACIONES Y AMORTIZACIONES` de la CNV, y **el factor no es constante**:

| FY | Catalaxia × coef | TIKR (ARS) | factor |
|---|---:|---:|---:|
| 2021 | 5.954 | 1.595 | 3,73 |
| 2022 | 19.040 | 6.954 | 2,74 |
| 2023 | 31.924 | 12.854 | 2,48 |
| 2024 | 55.751 | 18.256 | 3,05 |
| 2025 | 60.383 | 17.940 | 3,37 |

Ni una reclasificación ni un cambio de escala explican un factor que varía así.
El EBITDA de TIKR tampoco reconcilia con su propio D&A. **Se declara
`UNRESOLVED`; no se inventa una explicación.**

---

## 18. Backlog

| # | prioridad | hallazgo | acción |
|---|---|---|---|
| 1 | **P0** | no se descargan los PDF adjuntos de la CNV | bajar por GUID, verificar el hash publicado, extraer el flujo de efectivo completo |
| 2 | **P0** | la serie multi-año mezcla poderes adquisitivos | persistir la columna comparativa como hecho propio con su `measurement_date` |
| 3 | **P1** | no se modela el resultado atribuible a los propietarios | agregar `resultado_neto_controladora` al registry |
| 4 | **P1** | no hay datos de segmentos | misma fuente que P0-1 |
| 5 | P2 | la fórmula del EBITDA de TIKR no se pudo determinar | dejarlo declarado; **no** ajustar el EBITDA de Catalaxia, que es el que el emisor declara y audita |
| 6 | P2 | el benchmark convierte las acciones por el FX | no usar esa fila como referencia |
| 7 | P3 | faltan métricas de capital de trabajo | agregarlas al registry; los insumos ya están |

Detalle completo con evidencia en `TIKR_METR_BACKLOG.csv`. **Ningún fix se
implementó**: esto es diagnóstico.

---

## 19. Criterio de éxito

De las quince métricas que el encargo exige explicar:

| métrica | resultado |
|---|---|
| Revenue | **EXPLICADA** — reexpresión IAS 29; `MATCH` exacto en FY2025 |
| EBITDA | **EXPLICADA** como `ANOMALY` — el benchmark se contradice a sí mismo |
| Net Income | **EXPLICADA** — reexpresión + perímetro del resultado, residuo ≤0,62 % |
| EPS | **EXPLICADA** — reexpresión + FX; el EPS reportado es el mismo |
| CapEx | **EXPLICADA** — fuente no ingerida, adjunto identificado con GUID y hash |
| FCF | **EXPLICADA** — depende de CapEx |
| Cash | **EXPLICADA** — `MATCH` exacto en FY2025, reexpresión antes |
| Debt | **EXPLICADA** — `PASIVOS FINANCIEROS` ⊃ Total Debt |
| Equity | **EXPLICADA** — reexpresión; coincide exacto con `PatrimonioAperturaEjercicio` |
| EV | **EXPLICADA** — arrastra la definición de deuda |
| P/E | **EXPLICADA** — coincide en FY2025 (11,09 vs 11,10); el publicado por TIKR es `ANOMALY` |
| P/B | **EXPLICADA** — coincide exacto en FY2025 (1,51) |
| P/S | **EXPLICADA** — reexpresión |
| ROE | **EXPLICADA** — TIKR usa patrimonio promedio |
| ROIC | TIKR no lo publica en el benchmark |

Ninguna quedó en una explicación inventada. Las ocho `UNRESOLVED` son D&A y se
dicen tal cual.

---

## Archivos

| archivo | contenido |
|---|---|
| `TIKR_METR_HOMOLOGATION.xlsx` | `MASTER_COMPARISON`, `EXECUTIVE_SUMMARY`, `TOP_DIFFERENCES`, `DEFINITIONS`, `BACKLOG`, `PROVENANCE`, `FX_AND_REEXPRESSION`, `TIKR_UNMAPPED` |
| `TIKR_METR_DIFFERENCES.csv` | las 327 comparaciones, con provenance por celda |
| `TIKR_METR_FORMULAS.csv` | definición TIKR vs Catalaxia por métrica |
| `TIKR_METR_PROVENANCE.csv` | cadena canónica de cada concepto usado |
| `TIKR_METR_BACKLOG.csv` | 7 hallazgos priorizados con evidencia |

Herramienta: `scripts/engine/h1_tikr_metr_homologacion.py` (worktree
`catalaxia-cnvmig`), sólo lectura.
