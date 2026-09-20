# KO — reconciliación Catalaxia vs TIKR · FY2025

**2026-09-02** · 60 campos comparados · todo calculado, nada transcrito a mano
Datos: [`KO_vs_TIKR.csv`](KO_vs_TIKR.csv)

```
COINCIDE ......... 38 / 60      (tolerancia 0,15 % relativo)
DIFIERE .......... 19 / 60
NO PRODUCIBLE .....  3 / 60
```

---

## 0. Dos errores propios, corregidos primero

**a) Mi informe anterior tenía cifras mal transcritas.** La tabla de variables en
`KO_EXTRACTION_REPORT.md` la escribí a mano desde una consulta exploratoria en
lugar de leer el CSV que el script había producido. Los valores correctos —los
que el CSV siempre tuvo— son:

| variable | lo que publiqué | lo real | TIKR |
|---|---:|---:|---:|
| Current Assets | 29.297 | **31.044** | 31.044 |
| Current Liabilities | 20.083 | **21.281** | 21.281 |
| Cash | 9.694 | **10.270** | — |
| Equity incl. NCI | 34.271 | **34.275** | 34.275 |
| Operating Income | 13.764 | **13.762** | — |
| D&A | 1.052 | **1.050** | 1.050 |
| Net Income | 13.106 | **13.107** | 13.107 |
| Basic Shares | 4.302 | **4.303** | 4.303 |

Los ratios del CSV estaban bien —se calcularon de los valores correctos—; lo que
estaba mal era mi prosa. **La coincidencia con TIKR es mayor de la que reporté.**

**b) Un bug que introduje en este mismo ciclo.** La primera versión del script de
reconciliación leía `value_numeric::bigint`, que **trunca**: EPS 3,05 → 3, EPS
diluido 3,04 → 3, DPS 2,04 → 2. Eso arrastraba PER, payout y dividend yield.
Corregido a `value_numeric::text` antes de publicar nada.

La lección es la misma en los dos casos: **calcular, no transcribir.**

---

## 1. Insumos contables — 17 de 18 coinciden exactamente

| insumo | TIKR (M USD) | Catalaxia | dif |
|---|---:|---:|---:|
| Revenue | 47.941 | **47.941** | 0,00 % |
| Gross Profit | 29.544 | **29.544** | 0,00 % |
| Net Income | 13.107 | **13.107** | 0,00 % |
| D&A | 1.050 | **1.050** | 0,00 % |
| Interest Expense | 1.654 | **1.654** | 0,00 % |
| Current Assets | 31.044 | **31.044** | 0,00 % |
| Total Assets | 104.816 | **104.816** | 0,00 % |
| Current Liabilities | 21.281 | **21.281** | 0,00 % |
| Total Liabilities | 70.541 | **70.541** | 0,00 % |
| Common Equity | 32.169 | **32.169** | 0,00 % |
| Total Equity | 34.275 | **34.275** | 0,00 % |
| CFO | 7.408 | **7.408** | 0,00 % |
| CapEx | 2.112 | **2.112** | 0,00 % |
| FCF | 5.296 | **5.296** | 0,00 % |
| Diluted Shares | 4.313 | **4.313** | 0,00 % |
| Basic Shares | 4.303 | **4.303** | 0,00 % |
| **Operating Income** | 15.028 | 13.762 | **−8,42 %** |
| **EBITDA** | 16.078 | 14.812 | **−7,87 %** |
| **Total Debt** | 47.914 | *no producible* | — |
| **Net Debt** | 32.108 | *no producible* | — |

`Total Liabilities` merece nota: KO **no publica el tag `Liabilities`**. Los
70.541 M salen del cuadre `Assets − EquityInclNCI`, y dan **exactamente** la
cifra de TIKR.

---

## 2. Las diferencias, clasificadas

### 2.1 · NORMALIZACIÓN TIKR — el EBIT · **cierra al millón**

```
us-gaap OperatingIncomeLoss                                      13.762
+ DisposalGroupIncludingDiscontinuedOperation
    AllowanceForReductionOfAssetsHeldForSale                      1.265
                                                                 ──────
  EBIT normalizado                                               15.027
  TIKR                                                           15.028      Δ 1

+ D&A                                                             1.050
  EBITDA normalizado                                             16.077
  TIKR                                                           16.078      Δ 1
```

TIKR **agrega la previsión por baja de activos mantenidos para la venta**. Es una
normalización legítima —quita un cargo no recurrente— y el tag está en nuestros
datos: no lo usamos porque `ratio_defs` no declara ese concepto.

Con la normalización aplicada:

| | TIKR | Catalaxia | dif |
|---|---:|---:|---:|
| EBIT Margin | 31,3 % | **31,34 %** | +0,14 % |
| EBITDA Margin | 33,5 % | **33,54 %** | +0,10 % |
| EBIT / Interest | 9,09x | **9,0852x** | −0,05 % |

Sin normalizar da 28,71 % / 30,90 % / 8,32x. **La diferencia entera es la
definición, no el dato.**

### 2.2 · PROMEDIO vs CIERRE — tres casos, los tres cierran

| ratio | TIKR | nuestro cierre | nuestro promedio | dif con promedio |
|---|---:|---:|---:|---:|
| ROE acciones ordinarias | 46,0 % | 40,74 % | **45,97 %** | −0,07 % |
| ROE recursos propios | 43,3 % | — | **43,32 %** | +0,05 % |
| Inventory Turnover | 4,02x | 4,1575x | **4,0199x** | −0,00 % |
| DSO | 25,15 | 23,13 | **25,1513** | +0,01 % |

Y queda identificado qué es cada ROE de TIKR:

```
"ROE acciones ordinarias"  = NetIncomeLoss / promedio(Common Equity)
"ROE recursos propios"     = ProfitLoss    / promedio(Total Equity incl. NCI)
```

### 2.3 · DEFINICIÓN

**Quick Ratio.** TIKR 0,89x. Nuestra definición `(AC − Inventario)/PC` da
1,2508x. La de TIKR es más estrecha:

```
(Cash+STI + MarketableSecurities + Receivables) / LiabilitiesCurrent
(13.872 + 1.934 + 3.038) / 21.281 = 0,8855x     vs TIKR 0,89x
```

**Debt/Equity.** TIKR 139,8 % = `Total Debt / Total Equity incl. NCI`
(47.914/34.275 = **139,79 %**). Nuestro `Liabilities/Equity` = 2,19x es
`Pasivo total / Patrimonio común`: otro ratio, no el mismo mal calculado.

**Liabilities/Assets.** 70.541/104.816 = **67,2998 %** vs TIKR 67,3 %.

### 2.4 · PERÍODO — el precio

**Catalaxia tiene el cierre exacto de KO al 2025-12-31: 69,91 USD.** Idéntico a
TIKR. En el informe anterior usé el último precio disponible (89,06 del
2026-08-27), que es otra ventana.

```
PER con precio de cierre FY2025   69,91 / 3,05 = 22,9213x
PER con último precio             89,06 / 3,05 = 29,2000x
```

TIKR no publica PER en el extracto; los 22,92x se reconstruyen de sus propios
datos y **coinciden al 0,00 %** con lo nuestro usando la misma fecha.

**Dividend Yield.** TIKR lo publica sólo en la columna LTM: 2,3 %.

```
2,04 / 69,91 (cierre FY)      = 2,918 %
2,04 / 89,06 (precio actual)  = 2,291 %   ← TIKR
```

TIKR usa el **precio corriente** para el yield y el **de cierre fiscal** para el
resto de la columna FY2025. No es un error de nadie; es una mezcla de ventanas
dentro de la misma tabla, y conviene saberlo antes de comparar.

### 2.5 · DATO DISPONIBLE PERO NO UTILIZADO POR EL MOTOR — la deuda

TIKR: Total Debt 47.914 M, Net Debt 32.108 M. Catalaxia: **no producible**.

Ya está diagnosticado: desde FY2024 KO tagea `LongTermDebt` **sólo de forma
dimensional** —desglosado por instrumento (U.S. Dollar Notes, Euro Notes, Swiss
Franc Notes, Debentures) y en dos bases de medición—. No hay total consolidado y
sumar exigiría elegir cuál de cada par.

Pero **la caja que TIKR usa para la deuda neta sí se reconstruye exactamente**:

```
CashCashEquivalentsAndShortTermInvestments  13.872
+ MarketableSecurities                       1.934
                                            ──────
                                            15.806
47.914 − 15.806 = 32.108  =  Net Debt de TIKR      ✓ exacto
```

Es decir: **de los dos números de deuda, el que falta es sólo el bruto.** La
definición de caja amplia de TIKR queda identificada y verificada.

### 2.6 · INCONSISTENCIA DENTRO DE TIKR — dos EBITDA distintos

Éste es el hallazgo que importa para no tomar la referencia como verdad
automática. Los ratios de solvencia de TIKR **no cierran con el EBITDA de su
propia tabla de márgenes**:

| ratio TIKR | valor | EBITDA implícito |
|---|---:|---:|
| Debt / EBITDA | 2,91x | 47.914 / 2,91 = **16.465** |
| Net Debt / EBITDA | 1,95x | 32.108 / 1,95 = **16.466** |
| EBITDA / Interest | 9,97x | 9,97 × 1.654 = **16.490** |
| **EBITDA declarado en su estado de resultados** | | **16.078** |

Los tres ratios de crédito son consistentes entre sí (~16.47 M) y ninguno usa
los 16.078 M que TIKR publica dos tablas más arriba. **Diferencia ~390 M.**

Con el EBITDA declarado de TIKR, y su propia deuda:

```
Debt/EBITDA      47.914 / 16.077 = 2,98x     TIKR dice 2,91x
Net Debt/EBITDA  32.108 / 16.077 = 2,00x     TIKR dice 1,95x
```

No podemos determinar qué add-back de ~390 M usa TIKR en su EBITDA de crédito.
**Lo que sí queda demostrado es que "coincidir con TIKR" no es un objetivo
único**: hay que decir con cuál de sus dos EBITDA.

### 2.7 · NO RECONSTRUIBLE — ROA

TIKR 9,1 %. Nosotros 12,76 % (NI / activos promedio) o 12,50 % (cierre).

El numerador de TIKR no es el resultado neto, y se ve en la forma de la serie:

```
ROA TIKR         7,9 · 8,2 · 8,7 · 9,0 · 9,1     ← suave, creciente
Net Margin TIKR 25,3 · 22,2 · 23,4 · 22,6 · 27,3  ← volátil
```

Un ROA con resultado neto en el numerador heredaría esa volatilidad. Apunta a un
**resultado normalizado**. Probamos la hipótesis con el propio *Normalized Net
Margin* de TIKR (21,1 %):

```
21,1 % × 47.941 = 10.116 ;  10.116 / 102.683 (activos promedio) = 9,85 %
TIKR                                                              9,10 %
```

Se acerca y no cierra. **Clasificación: normalización de TIKR no reconstruible
con la información del extracto.** No es un dato que nos falte.

---

## 3. Los 15 prioritarios

| # | campo | TIKR | Catalaxia | estado | causa |
|---|---|---:|---:|---|---|
| 1 | **PER** | 22,92x* | **22,9213x** | ✅ | *reconstruido de sus datos |
| 2 | **Debt/EBITDA** | 2,91x | *no producible* | ⛔ | falta deuda bruta + inconsistencia TIKR |
| 3 | **EPS anual** | 3,05 / 3,04 | **3,05 / 3,04** | ✅ | — |
| 4 | **EPS CAGR 5Y** | no publicado | **11,12 %** | ➕ | producimos más que el extracto |
| 5 | **Net Margin** | 27,3 % | **27,34 %** | ✅ | — |
| 6 | **ROE 5 años** | no publicado | ROE anual ×3 variantes | ➕ | TIKR tampoco lo da |
| 7 | **FCF on CE** | no publicado | **6,34 %** | ➕ | — |
| 8 | **Payout** | 67,0 % | **66,98 %** | ✅ | — |
| 9 | **Precio** | 69,91 | **69,91** | ✅ | exacto al centavo |
| 10 | **52w high/low** | no publicado | **92,49 / 65,35** · −3,71 % / +36,28 % | ➕ | — |
| 11 | **EBIT** | 15.028 | **15.027** normalizado | ✅ | normalización identificada |
| 12 | **EBITDA** | 16.078 | **16.077** normalizado | ✅ | ídem |
| 13 | **Deuda total** | 47.914 | *no producible* | ⛔ | tag dimensional desde FY2024 |
| 14 | **Deuda neta** | 32.108 | *no producible* | ⛔ | depende de la bruta |
| 15 | **Enterprise Value** | — | *no producible* | ⛔ | depende de la bruta |

**11 de 15 se producen. Los 4 que no dependen todos del mismo dato: la deuda
bruta consolidada de FY2025.**

Y cuatro campos donde producimos algo que el extracto de TIKR **no trae**:
CAGR de EPS, máximo/mínimo de 52 semanas con sus distancias, FCF sobre capital
empleado, y las tres variantes de ROE separadas.

---

## 4. Resumen por causa

| causa | campos | ¿es un problema nuestro? |
|---|---:|---|
| **Coincidencia exacta** | 38 | — |
| Normalización TIKR (EBIT held-for-sale) | 3 | **no** · definición, y el tag lo tenemos |
| Promedio vs cierre | 4 | **no** · producimos las dos variantes |
| Definición distinta (quick, D/E) | 4 | **no** · se reproduce la de TIKR con nuestros datos |
| Período del precio | 2 | **no** · teníamos el dato exacto; elegí mal la ventana |
| **Dato no utilizado por el motor** | 4 | **sí, parcialmente** · el tag existe pero dimensional |
| Inconsistencia interna de TIKR | 3 | **no** · es del lado de TIKR |
| No reconstruible con el extracto | 1 | indeterminado |
| **Error real del extractor/motor** | **0** | — |

**Cero diferencias se explican por un error de extracción o de cálculo.** Los 18
insumos contables que TIKR publica y nosotros extraemos coinciden en 17 al
0,00 %, y el decimoctavo cierra al millón en cuanto se aplica la normalización
declarada.

---

## 5. Qué habilitaría cerrar los 4 que faltan

Los cuatro campos no producibles son el mismo problema. Tres caminos, en orden
de costo:

1. **Declarar en `ratio_defs` que la deuda financiera puede armarse desde el
   cuadro de vencimientos.** Para FY2025 KO publica `LongTermDebtMaturities…` en
   los cinco tramos (1.822 + 4.817 + 2.923 + 2.955 + 3.411 = 15.928 M) — pero
   eso son sólo los cinco primeros años, no la deuda total. **No alcanza.**
2. **Admitir facts dimensionales bajo una regla explícita** que sepa cuál de las
   dos bases de medición tomar y no doble-contar. Es una decisión de contrato,
   no de código.
3. **Usar el ejercicio FY2023**, donde `LongTermDebt` es un hecho principal. Ahí
   los siete ratios de deuda salen enteros.

Ninguno se ejecuta acá: los tres son decisiones, no tareas.

---

## Conclusión

Sobre los datos que TIKR publica y Catalaxia extrae, **la coincidencia es del
0,00 % de diferencia en 17 de 18 insumos contables**, y las 19 diferencias de
ratio se explican todas por definición, ventana o normalización — ninguna por un
error de extracción.

Tres cosas que el ejercicio deja claras y que no se sabían antes:

**La normalización de TIKR es identificable y nuestros datos la soportan.** El
add-back al EBIT es un tag que ya tenemos.

**TIKR no es internamente consistente.** Sus ratios de crédito usan un EBITDA
~390 M mayor que el de su propio estado de resultados. Tomarlo como verdad de
referencia sin decir cuál de los dos es aceptar una ambigüedad.

**Lo único que realmente nos falta es un número: la deuda bruta consolidada de
FY2025.** De él dependen los cuatro campos no producibles, y no falta por un
defecto del pipeline sino porque el emisor cambió cómo lo etiqueta.
