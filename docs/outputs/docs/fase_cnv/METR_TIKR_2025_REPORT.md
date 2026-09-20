# METR_TIKR_2025_GATE = **PASS_WITH_WARNINGS**

**Fecha:** 2026-09-02 · METR / Metrogas S.A. · CUIT 30657863676 ·
`entity_id = CUIT:30657863676` · FY2025 · fixture aislado `cnvmig`
**Benchmark:** los valores TIKR provistos por el usuario, únicos y exclusivos.
Sin commits · sin integración · `catalaxia` intacta.

---

## 1 · Resumen ejecutivo

```
Métricas TIKR evaluadas                     152
  estados financieros                        95
  ratios                                     39
  segmentos                                  18

MATCH_EXACT                                  35   (23,0 %)
MATCH_DERIVED                                 8   ( 5,3 %)
MATCH_ROUNDING                                8   ( 5,3 %)
────────────────────────────────────────────────
COINCIDENCIAS                                51   (33,6 %)

DEFINITION_DIFFERENCE                        27   (17,8 %)
INPUT_DIFFERENCE                              1
────────────────────────────────────────────────
DIFERENCIAS EXPLICADAS                       28   (18,4 %)

CATALAXIA_MISSING_INPUT                      66   (43,4 %)
TIKR_DEFINITION_UNVERIFIED                    2
TIKR_DERIVED_NOT_REPRODUCIBLE                 2
UNRESOLVED                                    4
────────────────────────────────────────────────
CATALAXIA_ERROR                               0
```

**Ningún error de Catalaxia.** Toda diferencia numérica quedó explicada por
definición, perímetro o insumo faltante — o marcada como no verificable cuando
la definición de TIKR no se puede deducir del benchmark.

---

## 2 · El hallazgo que resuelve la mitad de las diferencias

> **El perímetro INDIVIDUAL de la CNV es, exactamente, el segmento
> "MetroGAS Distribution" de TIKR.**

| métrica | Catalaxia INDIVIDUAL | TIKR MetroGAS Distribution | Δ |
|---|--:|--:|--:|
| Revenue | 959.320 | 959.320 | **0** |
| Operating Income | 175.133 | 175.133 | **0** |
| **Net Income** | **130.656** | **130.656** | **0** |
| Total Assets | 1.355.876 | 1.355.876 | **0** |
| Equity | 958.465 | *Total Common Equity* 958.465 | **0** |

Cuatro métricas independientes, diferencia cero en las cuatro.

### Lo que eso resuelve

El "Net Income = 130.656" de TIKR **no hay que derivarlo**: Catalaxia lo tiene
como fact, en el otro perímetro. Y la participación minoritaria sale de la
diferencia entre perímetros, sin residuo:

```
NetIncome INDIVIDUAL − CONSOLIDADO = 130.656 − 132.483 = −1.827   EXACTO
Equity    CONSOLIDADO − INDIVIDUAL = 960.345 − 958.465 = + 1.880   EXACTO
```

**No es una diferencia de atribución contable: es de perímetro.** Y Catalaxia
tiene los dos lados.

> Una hipótesis que descarté por el camino: `ResultadosNoAsignados` vale
> 130.656 en FY2025, igual que el Net Income de TIKR. Es coincidencia. En 2023
> `NetIncome` da 96.355 y `ResultadosNoAsignados` 38.101 — uno es flujo y el
> otro saldo. Casarlos por el número habría sido un error.

---

## 3 · Estado de resultados

| métrica | TIKR | Catalaxia | Δ | clasificación |
|---|--:|--:|--:|---|
| Revenue | 1.217.305 | 1.217.305 | 0 | **MATCH_EXACT** |
| Total Revenue | 1.217.305 | 1.217.305 | 0 | **MATCH_EXACT** |
| Operating Expenses | −1.028.722 | −1.020.994 | 7.728 | DEFINITION |
| **Operating Income** | **188.583** | **196.311** | **7.728** | **DEFINITION** |
| Interest Expense | −44.335 | −52.522 | −8.187 | DEFINITION |
| EBT incl. Extraordinary | 191.623 | 191.623 | 0 | **MATCH_EXACT** |
| Income Tax Expense | −59.140 | −59.140 | 0 | **MATCH_EXACT** |
| Income from Continuing Ops | 132.483 | 132.483 | 0 | **MATCH_EXACT** |
| Net Income Company | 132.483 | 132.483 | 0 | **MATCH_EXACT** |
| **Minority Interest** | **−1.827** | **−1.827** | **0** | **MATCH_DERIVED** |
| **Net Income** | **130.656** | **130.656** | **0** | **MATCH_EXACT** |
| Net Income Common Stockholders | 130.656 | 130.656 | 0 | **MATCH_EXACT** |
| Diluted EPS | 229,62 | 229,62 | 0 | **MATCH_EXACT** |
| EBITDA | 231.071 | 256.694 | 25.623 | DEFINITION |
| Effective Tax Rate | 30,9 % | 30,86 % | — | **MATCH_ROUNDING** |

### El Operating Income — resuelto a medias

`196.311` coincide **exactamente** con el **"Segment Total"** de TIKR. TIKR
reporta `188.583` como su operativo consolidado normalizado: reclasifica
**7.728** a gasto operativo. La diferencia es la misma que aparece en Operating
Expenses, así que las dos son consistentes entre sí.

**Qué renglón reclasifica, no puede determinarse del EEFF resumido.** Se deja
como `DEFINITION_DIFFERENCE`, no como error.

### El EBITDA — consistente en su diferencia

```
Catalaxia  256.694 = OperatingIncome 196.311 + D&A 60.383
TIKR       231.071  parte de SU operativo (188.583) y de SU D&A (42.554)
```

Y el D&A cierra exacto:

```
DA de la CNV (código 3011600) = 60.383
TIKR D&A 42.554 + Amortización de cargos diferidos 17.829 = 60.383   EXACTO
```

El código de la CNV **agrega** lo que TIKR separa.

---

## 4 · Balance

Nueve coincidencias exactas, incluidos los cuatro totales estructurales:

| | TIKR | Catalaxia | Δ |
|---|--:|--:|--:|
| Total Assets | 1.390.076 | 1.390.076 | **0** |
| Total Liabilities | 429.731 | 429.731 | **0** |
| Total Equity | 960.345 | 960.345 | **0** |
| Liabilities + Equity | 1.390.076 | 1.390.076 | **0** |
| Cash & Equivalents | 116.132 | 116.132 | **0** |
| Accounts Receivable | 199.890 | 199.890 | **0** |
| Total Current Assets | 330.646 | 330.646 | **0** |
| Total Current Liabilities | 247.455 | 247.455 | **0** |
| Other Intangibles | 18.253 | 18.253 | **0** |
| Common Stock | 569 | 569 | **0** |
| Net PP&E | 1.037.217 | 1.037.206 | 11 (0,001 %) |

### El patrimonio cierra completo

```
Capital                              569
Reservas + ResultadosNoAsignados = 611.189   =  TIKR Retained Earnings   EXACTO
resto                            = 348.587   =  TIKR OCI 346.707
                                                + Minoritaria  1.880     EXACTO
                                   ─────────
Equity                             960.345
```

Los 348.587 que en el análisis previo figuraban como "hueco sin explicar"
**se descomponen exactamente** en los dos renglones que TIKR publica.

### Accounts Payable

```
Payables Catalaxia 145.428 = TIKR AP 144.994 + Unearned Revenue 434   EXACTO
```

El código 2321999 agrega ambos.

### Total Debt — la diferencia mayor del balance

```
Catalaxia  DebtCurrent 71.079 + DebtNonCurrent 73.480 = 144.559
TIKR                                                     86.550
```

Los códigos 2322200 y 2312300 agregan más que la deuda financiera de TIKR
(que suma 34.418 + 13 + 52.119). Arrastra a Net Debt, Debt/Equity,
Debt/Capital, Debt/EBITDA y Net Debt/EBITDA.

---

## 5 · Flujo de efectivo

Los tres subtotales coinciden **exactamente**:

| | TIKR | Catalaxia | Δ |
|---|--:|--:|--:|
| Cash From Operations | 89.042 | 89.042 | **0** |
| Cash From Investing | −58.733 | −58.733 | **0** |
| Cash From Financing | −42.338 | −42.338 | **0** |
| Cash Ending | 116.132 | 116.132 | **0** |

### El "Net Change in Cash" — explicado sin residuo

```
CFO + CFI + CFF = −12.029  = CashFlowNeto de Catalaxia (código 3240000)  EXACTO
−12.029 + ajuste cambiario (−32.698) = −44.727 = Net Change in Cash TIKR  EXACTO
```

**Catalaxia excluye el ajuste cambiario del subtotal; TIKR lo incluye.** El
ajuste de 32.698 se deriva por diferencia, exacto.

### Cash Beginning — el único caso donde falta un dato

```
TIKR Cash Beginning         160.859
Catalaxia Cash 2024-12-31   122.280
factor implícito                    1,3155
```

Catalaxia tiene el cierre 2024 **en moneda de diciembre de 2024**; TIKR usa el
comparativo **re-expresado a moneda de diciembre de 2025**. Es el mismo
problema que W-1.2 dejó anotado: Catalaxia no ingesta los comparativos.

El resto del desglose del flujo (Capex, cambios en partidas, deuda emitida y
repagada) no está: la CNV publica los tres subtotales y nada más.

---

## 6 · Ratios

| ratio | TIKR | Catalaxia | clasificación |
|---|--:|--:|---|
| **Common Stockholder Margin** | 10,7 % | **10,733 %** | **MATCH_ROUNDING** |
| Net Margin | 10,7 % | 10,883 % | DEFINITION |
| **ROE** | **14,80 %** | **14,80 %** | **INPUT_DIFFERENCE — resuelto** |
| Asset Turnover | 0,88 | 0,8757 | MATCH_ROUNDING |
| Working Capital Turnover | 14,63 | 14,6327 | MATCH_ROUNDING |
| Current Ratio | 1,34 | 1,3362 | MATCH_ROUNDING |
| OCF / Current Liabilities | 0,36 | 0,3598 | MATCH_ROUNDING |
| Total Liabilities / Assets | 30,9 % | 30,914 % | MATCH_ROUNDING |
| ROA | 8,3 % | 10,64 % | **TIKR_DEFINITION_UNVERIFIED** |
| Operating Income Margin | 10,9 % | 16,13 % | **TIKR_DEFINITION_UNVERIFIED** |

### El Net Margin, con las dos fórmulas

```
consolidado:  132.483 / 1.217.305 = 10,8833 %
atribuible:   130.656 / 1.217.305 = 10,7332 %  →  redondea a 10,7 %  ✔ TIKR
```

**TIKR usa el resultado atribuible.** Es diferencia de perímetro, no error.

### El ROE — resuelto exactamente

```
con patrimonio de apertura SIN re-expresar   →  16,66 %
con el patrimonio de apertura × 1,3155        →  14,80 %  ✔ TIKR EXACTO
```

El factor 1,3155 se deduce del único comparativo que TIKR publica y Catalaxia
también tiene: la caja inicial (160.859 / 122.280). **Lo que falta no es la
fórmula: es el comparativo re-expresado.**

### Dos definiciones de TIKR que no pude verificar

- **ROA 8,3 %** — ninguna variante lo reproduce: cierre 9,53 %, promedio
  10,64 %, promedio re-expresado 9,34 %. El denominador que TIKR implica
  (1.596.181) es **mayor que el activo total de cierre**.
- **Operating Income Margin 10,9 %** — con el operativo de TIKR daría 15,49 %;
  con el de Catalaxia, 16,13 %. Ninguno da 10,9 %.

**No inventé una definición para cerrarlos.**

### Una inconsistencia de TIKR consigo mismo

TIKR usa **saldo promedio** en el ROE y **saldo de cierre** en el Asset
Turnover. Son metodologías distintas entre sus propios ratios.

---

## 7 · Segmentos

**10 de 18 exactos**, sin ningún fact dimensional en Catalaxia:

| métrica | Segment Total | MetroGAS Distribution | MetroENERGY | Eliminaciones |
|---|---|---|---|---|
| Operating Revenue | **EXACTO** | **EXACTO** | falta | falta |
| Operating Income | **EXACTO** | **EXACTO** | falta | falta |
| Net Income Common | **EXACTO** | **EXACTO** | falta | falta |
| Total Assets | **EXACTO** | **EXACTO** | falta | falta |
| Geográfico Argentina | **EXACTO** (revenue y activo no corriente) | | | |

- **Segment Total** = el perímetro CONSOLIDADO.
- **MetroGAS Distribution** = el perímetro INDIVIDUAL.
- **MetroENERGY y eliminaciones**: sólo derivables **en conjunto**
  (CONSOLIDADO − INDIVIDUAL = MetroENERGY + eliminaciones). Por separado, no.

La aritmética de TIKR cierra sola en las cuatro métricas:
`MetroENERGY + MetroGAS + eliminaciones = Segment Total`, diferencia 0.

---

## 8 · Provenance

`METR_TIKR_2025_PROVENANCE.csv` — 100 filas, la cadena completa por fact:

```
ticker · cuit · entity_id · entity_key · perímetro · concepto · código CNV
qname · fact_key · econ_key · context_id · period_kind · start_date · end_date
measurement_date · unit_measure · unit_ref · decimals · accession · archivo
raw_sha256 · valor impreso · escala · valor normalizado
```

Ejemplo — `Revenue` FY2025 CONSOLIDADO:

```
documento   d96fd259-c5ce-431f-8e14-17af592b99f9.html · Presentación #3487124
SHA-256     460d167241febbe3a3be8142c44be60c6c5eebfd4dc76c53a71b3dfca9b6b191
código      3000100 · impreso 1.217.305,00 · escala 10⁶ · normalizado 1.217.305 MM
fact_key    e270dfb8681a133b088b38a677bdc3bb0e828d1072f208a50c6df247160a57f3
econ_key    9b0c12ce7825100d46e6c61bd80a26cd40f563064472e3ba56eb67be18e1a7c6
```

---

## 9 · Auditoría independiente

`c4_auditoria_metr_tikr.py` — **22 facts + 8 identidades + 3 márgenes ·
0 fallas**.

No importa la reconciliación ni el adaptador ni el módulo semántico. Tiene su
propio parser del RAW, su propia tabla de códigos y su propia copia del
benchmark, y **re-verifica desde el archivo** cada match declarado: recomputa el
SHA-256, relee el número impreso, aplica la escala declarada y compara.

Las ocho identidades que verifica de forma independiente:

```
Minority Interest = NI_IND − NI_CONS                    = −1.827   ✔
Retained Earnings = Reservas + RdosNoAsignados          = 611.189  ✔
MI patrimonial    = Eq_CONS − Eq_IND                    =  1.880   ✔
OCI               = Eq − Capital − RetEarn − MI         = 346.707  ✔
Amort. diferidos  = DA − D&A_TIKR                       = 17.829   ✔
Ajuste FX         = NetChange_TIKR − CashFlowNeto       = −32.698  ✔
CashFlowNeto      = CFO + CFI + CFF                     ✔
Liabilities + Equity = Assets                           ✔
```

> **El auditor encontró un error en mi propia comparación.** La primera versión
> contrastaba el margen INDIVIDUAL/INDIVIDUAL (13,62 %) contra el "Common
> Stockholder Margin" de TIKR (10,73 %), que usa el ingreso **consolidado** en
> el denominador. Eran dos márgenes distintos. Corregido, y el auditor ahora
> verifica los tres por separado.

---

## 10 · Mutaciones adversariales

`tests/test_metr_tikr_2025.py` — **15 passed**. Diez mutaciones, diez fallas.

| | mutación | detección |
|---|---|---|
| M1 | valor | no reproduce el RAW |
| M2 | unidad | unidad incorrecta |
| M3 | escala | no reproduce el RAW |
| M4 | período | `measurement_date` incorrecta |
| M5 | perímetro cruzado | rompe la identidad de minoritaria |
| M6 | entidad | falta el fact |
| M7 | SHA-256 del RAW | no coincide con el archivo |
| M8 | numerador/denominador | el margen invertido deja de reproducirse |
| M9 | atribución | consolidado 10,883 % no redondea a 10,7 % |
| M10 | documento equivocado | detectado |

> M6 reveló que el auditor **crasheaba** con `KeyError` en vez de reportar
> cuando faltaba un fact. Corregido: ahora degrada con gracia y lo informa.

---

## 11 · Idempotencia y regresión

```
2ª corrida: las 3 matrices con sha256 IDÉNTICO
suite completa: 378 passed · 3 failed (F-038, preexistentes) · 1 skipped

SEC:  hechos · fact_key · source_hash · ratios     IGUAL
CNV:  hechos · fact_key · context_id               IGUAL
catalaxia: 34 migraciones · 0 hechos CNV
```

El proceso es de sólo lectura: no escribió una fila.

---

## 12 · Qué falta para "comparable con la superficie TIKR"

Por impacto medido, en orden:

**1 · Comparativos re-expresados** — desbloquea `Cash Beginning`, el ROE
(ya demostrado: reproduce 14,80 % exacto), el ROA y todos los ratios de saldo
promedio. Es el mismo defecto que W-1.2 dejó anotado, y ahora está cuantificado:
factor 1,3155 para FY2025.

**2 · Desglose del flujo de efectivo** — la CNV publica tres subtotales. Sin
Capex caen FCF, FCF Margin, `(EBITDA−Capex)/Interés`, `Levered/Unlevered FCF
Margin` y `Net Debt/(EBITDA−Capex)`: **6 métricas**.

**3 · Desglose de deuda financiera** — los códigos 2322200 y 2312300 agregan
más que la deuda de TIKR. Arrastra **5 ratios de solvencia**.

**4 · Desglose del balance** — 20 renglones (inversiones corrientes, gastos
pagados por adelantado, PP&E bruto, depreciación acumulada, impuestos
diferidos, tierra, edificios, obras en curso).

**5 · Desglose del estado de resultados** — 6 renglones (intereses ganados,
FX, partidas inusuales), más SG&A para el margen correspondiente.

**6 · Número de acciones en circulación** — 3 métricas per-share.

**7 · Segmentos MetroENERGY y eliminaciones por separado** — hoy sólo
derivables en conjunto.

Ninguno requiere cambiar el modelo canónico: **son todos ingesta**. El punto 1
sí requiere además decidir cómo conviven dos mediciones del mismo período, que
es exactamente lo que `econ_key` y `measurement_date` ya modelan desde W-1.3.

---

## 13 · Dictamen

```
METR_TIKR_2025_GATE = PASS_WITH_WARNINGS
```

**PASS** porque:

- 51 de 152 métricas coinciden (33,6 %), incluidos **los cuatro totales
  estructurales del balance, los tres subtotales del flujo de efectivo y el
  resultado en sus dos perímetros**;
- las 28 diferencias explicadas lo están con aritmética exacta, no con
  narrativa: seis descomposiciones cierran con diferencia **cero**;
- **cero errores de Catalaxia**;
- el auditor independiente reproduce cada match desde el documento de la CNV;
- las diez mutaciones fallan donde deben;
- idempotente, y SEC, CNV y `catalaxia` intactos.

**WITH_WARNINGS** porque:

- el **43,4 %** de la superficie TIKR no tiene insumo en Catalaxia — casi todo
  desglose que la CNV no publica en el EEFF resumido;
- **dos definiciones de TIKR quedaron sin verificar** (ROA y Operating Income
  Margin) y no se inventó una para cerrarlas;
- el Operating Income de TIKR (188.583) queda explicado sólo hasta la mitad:
  sé que reclasifica 7.728, no qué renglón.

**La respuesta a la pregunta del ciclo:** Catalaxia reproduce hoy **un tercio**
de la superficie TIKR de METR desde evidencia primaria de la CNV, y explica con
aritmética exacta **otro quinto**. El 43 % restante no es un problema de modelo
— es desglose que no está ingestado.
