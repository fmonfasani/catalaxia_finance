# METR · Metrogas S.A. — extracción CNV · FY2025

**2026-09-02** · fuente única: **CNV** (EEFF vía `cnv-aif2`) · solo lectura
Datos: [`METR_CNV_EXTRACCION.csv`](METR_CNV_EXTRACCION.csv) — 77 campos

> **El único dato que NO es CNV** es el precio (2.547,50 ARS al 31/12/2025, Yahoo
> Finance, aportado por el usuario). Está etiquetado en cada celda que lo toca.
> **CNV no publica precios.**

---

## 1. Identificación

| campo | valor | tipo |
|---|---|---|
| Razón social | **Metrogas S.A.** | REPORTADO |
| Ticker | **METR** | REPORTADO |
| Identificador CNV | **CUIT 30657863676** | REPORTADO |
| Tipo de instrumento | acción ordinaria | REPORTADO |
| Mercado | BYMA · grupo `byma_only` (cotiza sólo en BYMA, sin ADR) | REPORTADO |
| Sector | Energía · `es_financiera = 0` | REPORTADO |
| Moneda | **ARS** | REPORTADO |
| Escala de los EEFF | 1.000.000 (millones) | REPORTADO |
| Capital social | **569.000.000** | REPORTADO (tag `Capital`) |
| Acciones emitidas | **N/D** — CNV no publica el conteo | N/D |
| Acciones en circulación | **N/D** | N/D |
| Valor nominal | **N/D** | N/D |
| Fecha de la información | cierre **2025-12-31** | REPORTADO |

### ¿La especie está listada en BYMA?

**SÍ**, según la clasificación del propio universo CNV/BYMA del proyecto
(`grupo = 'byma_only'`, 56 especies). **Advertencia de honestidad:** esa
clasificación proviene del pipeline, no de un documento oficial de BYMA que yo
haya leído en esta extracción. Como constancia documental directa de listado:
**NO VERIFICABLE** con lo que tengo a mano.

---

## 2. LA DECISIÓN QUE CONDICIONA TODO — individual vs consolidado

METR presenta **dos juegos completos de estados para el mismo FY2025**, en dos
presentaciones distintas ante CNV:

```
CONSOLIDADO   accn d96fd259-c5ce-431f-8e14-17af592b99f9   50 conceptos
INDIVIDUAL    accn 576dbb0d-3527-46a9-b335-6f9aaf54d26e   50 conceptos
```

Y las diferencias **no son menores**:

| concepto | CONSOLIDADO | INDIVIDUAL | dif |
|---|---:|---:|---:|
| Ingresos | 1.217.305 M | 959.320 M | **+26,9 %** |
| Flujo operativo | 89.042 M | 50.397 M | **+76,7 %** |
| Caja | 116.132 M | 76.691 M | **+51,4 %** |
| Activos corrientes | 330.646 M | 261.862 M | **+26,3 %** |
| Resultado bruto | 465.192 M | 384.681 M | +20,9 % |
| EBIT | 196.311 M | 175.133 M | +12,1 % |
| EBITDA | 256.694 M | 235.516 M | +9,0 % |
| Pasivos totales | 429.731 M | 397.411 M | +8,1 % |
| Resultado neto | 132.483 M | 130.656 M | +1,4 % |
| Patrimonio | 960.345 M | 958.465 M | +0,2 % |
| **EPS básico** | **229,62** | **229,62** | **0,0 %** |

**Base elegida: CONSOLIDADO.** Es la que corresponde al grupo económico que
cotiza. La individual queda declarada como alternativa; **nunca se mezclan**.

El margen neto ilustra por qué importa: consolidado **10,88 %**, individual
**13,62 %**. Elegir mal cambia la respuesta en un cuarto.

### Y una identidad que cierra sola

```
NI consolidado total        132.483 M
NI individual (= atribuible a los propietarios)  130.656 M
diferencia (participación no controladora)        1.827 M

EPS = 130.656.000.000 / 569.000.000 = 229,62   ← exacto
```

**El EPS que CNV reporta se calcula sobre el resultado atribuible a los
propietarios, y el divisor es exactamente el capital social.** Se verifica sin
que CNV publique el conteo de acciones: la identidad lo demuestra.

---

## 3. Precio de mercado

| campo | valor | fuente |
|---|---|---|
| Precio de cierre | **2.547,50 ARS** | **Yahoo Finance — NO ES CNV** |
| Fecha | **2025-12-31** (último día hábil del FY) | aportado por el usuario |
| Moneda | ARS | — |
| Máximo 52 semanas | **N/D** | CNV no lo publica; la serie local cubre sólo 2026-07-09 a 2026-08-21 |
| Mínimo 52 semanas | **N/D** | ídem |
| Dif. contra máximo/mínimo | **N/D** | dependen de los anteriores |

**CNV no publica cotizaciones.** No se sustituyó por ninguna otra fuente y no se
construyó un rango de 52 semanas mezclando orígenes.

---

## 4. Estados financieros · FY2025 · consolidado · ARS

Todos **REPORTADOS**, tag CNV entre paréntesis, presentación
`accn d96fd259…`, `form EEFF`, `fuente cnv-aif2`, `tipo A` (acumulado anual),
reexpresión al 2025-12-31.

### Estado de resultados

| concepto | valor | tag CNV |
|---|---:|---|
| Ingresos | 1.217.305.000.000 | `Revenue` |
| Costo de ventas | −752.113.000.000 | `COGS` |
| Resultado bruto | 465.192.000.000 | `GrossProfit` |
| Resultado operativo (EBIT) | 196.311.000.000 | `EBIT` |
| **EBITDA** | **256.694.000.000** | `EBITDA` — **publicado por CNV, no derivado** |
| Depreciación y amortización | −60.383.000.000 | `DA` |
| Costo financiero | −52.522.000.000 | `InterestExpense` |
| RECPAM | 4.113.000.000 | `RECPAM` |
| Resultado antes de impuestos | 191.623.000.000 | `PretaxIncome` |
| Impuesto a las ganancias | −59.140.000.000 | `IncomeTax` |
| Resultado neto | 132.483.000.000 | `NetIncome` |
| Atribuible a los propietarios | 130.656.000.000 | derivado de la individual |
| Participación no controladora | 1.827.000.000 | **CALCULADO** = consolidado − individual |

### Balance

| concepto | valor | tag CNV |
|---|---:|---|
| Activos corrientes | 330.646.000.000 | `AssetsCurrent` |
| Activos no corrientes | 1.059.430.000.000 | `AssetsNonCurrent` |
| **Activos totales** | **1.390.076.000.000** | `Assets` |
| Caja y equivalentes | 116.132.000.000 | `Cash` |
| Inversiones corrientes | **N/D** | no hay concepto separado |
| Créditos por ventas | 199.890.000.000 | `Receivables` |
| **Inventarios** | **N/D** | METR no publica inventario — ver §5 |
| Pasivos corrientes | 247.455.000.000 | `LiabilitiesCurrent` |
| Deuda corriente | 71.079.000.000 | `DebtCurrent` |
| Pasivos no corrientes | 182.276.000.000 | `LiabilitiesNonCurrent` |
| Deuda no corriente | 73.480.000.000 | `DebtNonCurrent` |
| Deudas comerciales | 145.428.000.000 | `Payables` |
| **Pasivos totales** | **429.731.000.000** | `Liabilities` |
| **Patrimonio neto** | **960.345.000.000** | `Equity` |
| Patrimonio atribuible a los accionistas | 958.465.000.000 | individual |
| Participaciones no controladoras | 1.880.000.000 | **CALCULADO** = 960.345 − 958.465 |
| Capital de trabajo | 83.191.000.000 | `WorkingCapital` |

### Flujo de efectivo

| concepto | valor | tag CNV |
|---|---:|---|
| Flujo operativo | 89.042.000.000 | `CF_Operativo` |
| Flujo de inversión | −58.733.000.000 | `CF_Inversion` |
| Flujo de financiación | −42.338.000.000 | `CF_Financiacion` |
| Flujo neto | −12.029.000.000 | `CashFlowNeto` |
| **CapEx** | **N/D** | CNV no lo aísla dentro del flujo de inversión |
| **Dividendos pagados** | **N/D** | sin concepto; 0 registros en `cnv_dividendos` |
| **Flujo de caja libre** | **N/D** | CNV no lo publica y **no se deriva**: sin CapEx, `CFO − CapEx` no es construible |

---

## 5. Deuda

| Concepto CNV | Valor | Corriente / No corriente | ¿Es deuda financiera? | Fuente |
|---|---:|---|---|---|
| `DebtCurrent` | 71.079.000.000 | corriente | **SÍ** | EEFF consolidado |
| `DebtNonCurrent` | 73.480.000.000 | no corriente | **SÍ** | EEFF consolidado |
| `Payables` | 145.428.000.000 | corriente | **NO** — comercial | EEFF consolidado |
| `LiabilitiesCurrent` | 247.455.000.000 | corriente | **NO** — agregado, contiene la deuda | EEFF consolidado |
| `LiabilitiesNonCurrent` | 182.276.000.000 | no corriente | **NO** — agregado, contiene la deuda | EEFF consolidado |
| préstamos bancarios · ON · leasing | — | — | **N/D** — CNV no los desagrega | — |

### Total Debt = **144.559.000.000 ARS**

```
DebtCurrent  71.079  +  DebtNonCurrent  73.480  =  144.559
```

**Se suma, y la suma es legítima**, porque `DebtCurrent` y `DebtNonCurrent` son
por construcción disjuntos (corriente / no corriente) y **no** se suman los
agregados `LiabilitiesCurrent`/`LiabilitiesNonCurrent`, que los contienen.
Sumarlos sería doble contabilización.

**Deuda neta = 144.559 − 116.132 = 28.427.000.000 ARS.**

**Y la CNV lo confirma:** su ratio oficial `CNV_deuda_fin_ebitda` = **0,56**;
nuestro cálculo `144.559 / 256.694` = **0,5632**. La composición de la deuda
queda validada por el propio regulador.

**Lo que NO se puede hacer:** desagregar en préstamos, obligaciones negociables
y arrendamientos. CNV, en este nivel de normalización, no lo publica.

---

## 6. Los ratios oficiales de la CNV — y el cruce con los nuestros

La CNV publica **doce ratios propios**. Ese es el control independiente que este
ejercicio permite y que ninguna otra fuente da.

| ratio | **CNV oficial** | **nuestro cálculo** | fórmula usada | ¿cierra? |
|---|---:|---:|---|:-:|
| deuda fin. / EBITDA | 0,56 | **0,5632** | (DebtCur+DebtNoCur)/EBITDA | ✅ |
| liquidez | 1,34 | **1,3362** | AC / PC | ✅ |
| rotación de activos | 0,88 | **0,8757** | Revenue / Assets | ✅ |
| margen neto | 0,11 | **0,1088** | NetIncome / Revenue | ✅ |
| ROA | 0,10 | **0,0953** | NetIncome / Assets | ✅ |
| solvencia | 2,23 | **2,2348** | Equity / Liabilities | ✅ |
| endeudamiento | 0,45 | **0,4475** | Liabilities / Equity | ✅ |
| apalancamiento | 1,45 | **1,4475** | Assets / Equity | ✅ |
| cobertura de intereses | −3,74 | **3,7377** | EBIT / \|InterestExpense\| | ✅ signo |
| EBITDA / costos fin. | −4,89 | **4,8874** | EBITDA / \|InterestExpense\| | ✅ signo |
| prueba ácida | 1,34 | **N/D** | (AC−Inv)/PC | ⚠️ ver abajo |
| **ROE** | **0,15** | **0,1380** | NetIncome / Equity | ❌ **no cierra** |

**Diez de doce cierran** con nuestros propios cálculos sobre los datos crudos.
Los signos negativos de las coberturas son de la CNV, que arrastra el signo del
costo financiero; en magnitud coinciden al cuarto decimal.

### Dos observaciones

**Prueba ácida = liquidez (1,34) en la CNV.** Eso confirma que **METR no tiene
inventarios** — es una distribuidora de gas. Nuestro `N/D` en inventario es
correcto, y la CNV lo corrobora al hacer los dos ratios idénticos.

**El ROE no cierra, y no pude explicarlo.** CNV dice 0,15; nosotros 0,1380 con
patrimonio de cierre y 0,1666 con patrimonio promedio. Ninguna de las dos
redondea a 0,15. Probamos también con el resultado atribuible (130.656) sobre
patrimonio de los propietarios (958.465) = 0,1363. **Queda como discrepancia
abierta**: el denominador de la CNV no es ninguno de los tres. No se fuerza una
explicación.

---

## 7. Ratios calculados

### Rentabilidad y márgenes · FY2025 consolidado

| ratio | valor | fórmula |
|---|---:|---|
| Margen bruto | **38,21 %** | GrossProfit / Revenue |
| Margen operativo | **16,13 %** | EBIT / Revenue |
| Margen EBITDA | **21,09 %** | EBITDA / Revenue |
| Margen neto | **10,88 %** | NetIncome / Revenue |
| ROA | **9,53 %** | NetIncome / Assets (cierre) |
| ROE | **13,80 %** | NetIncome / Equity (cierre) |
| ROE (patrimonio promedio) | **16,66 %** | NetIncome / prom(Equity 2025, 2024) |
| ROCE | **17,18 %** | EBIT / (Assets − PasivoCorriente) |
| Tasa efectiva de impuesto | **30,86 %** | \|IncomeTax\| / PretaxIncome |
| **FCF on Capital Employed** | **N/D** | sin FCF (falta CapEx) |

### Endeudamiento

| ratio | valor | fórmula |
|---|---:|---|
| Debt / Equity | **0,1505x** | Deuda / Equity |
| Debt / Capital | **0,1308x** | Deuda / (Deuda + Equity) |
| Debt / EBITDA | **0,5632x** | Deuda / EBITDA |
| Net Debt / EBITDA | **0,1107x** | (Deuda − Caja) / EBITDA |
| Interest Coverage (EBIT) | **3,7377x** | EBIT / \|costo financiero\| |
| Interest Coverage (EBITDA) | **4,8874x** | EBITDA / \|costo financiero\| |

### Liquidez y eficiencia

| ratio | valor | fórmula |
|---|---:|---|
| Liquidez corriente | **1,3362x** | AC / PC |
| Cash ratio | **0,4693x** | Caja / PC |
| Prueba ácida | **N/D** | sin inventario (no aplica) |
| Asset Turnover | **0,8757x** | Revenue / Assets |
| Receivables Turnover | **6,0899x** | Revenue / Créditos |
| DSO | **59,94 días** | Créditos × 365 / Revenue |
| Inventory Turnover · DIO | **N/D** | sin inventario |
| DPO | **70,58 días** | Deudas comerciales × 365 / \|COGS\| |

### Valuación — **fuente mixta**

Cruzan precio de mercado (no CNV) con denominador CNV. Marcados en el CSV.

| ratio | valor | fórmula |
|---|---:|---|
| **PER** | **11,0944x** | 2.547,50 / 229,62 |
| P/B (sobre capital social) | 1,5094x | Precio / (Equity / Capital) |
| P/S (sobre capital social) | 1,1908x | Precio / (Revenue / Capital) |
| Market Cap | 1.449.527.500.000 ARS | Precio × Capital |
| P/FCF · FCF Yield | **N/D** | sin FCF |

**Advertencia sobre P/B, P/S y Market Cap:** usan `Capital` (capital social) como
divisor porque **CNV no publica el conteo de acciones**. La identidad del EPS
(§2) muestra que el capital social coincide con el divisor del EPS, lo que lo
hace razonable — pero es una inferencia, no un dato. El PER no depende de eso:
usa el EPS reportado.

### Dividendos

| campo | valor |
|---|---|
| DPS | **N/D** — CNV no publica dividendo por acción |
| **Payout** | **N/D** — sin dividendos; el pipeline marca `payout_status = 'no_paga'` |
| Dividend Yield | **N/D** — depende del DPS |

---

## 8. Crecimiento — y por qué NO debe usarse

Serie consolidada disponible: **8 cierres anuales, 2018-12-31 a 2025-12-31.**

| | valor calculado |
|---|---:|
| Revenue crecimiento anual | +31,59 % |
| Revenue CAGR 3Y | +124,82 % |
| Revenue CAGR 5Y | +89,59 % |
| EPS crecimiento anual | −15,39 % |
| EPS CAGR 3Y | +184,61 % |
| **EPS CAGR 5Y** | **N/D** — EPS no positivo en 2020-12-31 |

# ⚠️ Estos CAGR NO SON VÁLIDOS para comparación

Son **nominales en pesos**, y aunque los EEFF llevan reexpresión por IAS 29,
**cada presentación reexpresa a su propia fecha**: el pipeline marca esta serie
como `vintage_mixto (2021-12-31 .. 2026-03-31)`. Un CAGR de ingresos del 124,8 %
anual no mide crecimiento del negocio: mide inflación más cambio de vintage.

La regla del encargo —*no calcular CAGR si hay cambios metodológicos que
invaliden la comparación*— **aplica exactamente acá**. Se reportan sólo para
dejar constancia de que el cálculo se hizo y de por qué se descarta.

---

## 9. Tabla final para reconciliación

| Campo | Valor CNV | Unidad | Período | Rep./Calc. | Fórmula | Fuente |
|---|---:|---|---|---|---|---|
| Especie | METR · Metrogas S.A. | — | 2025-12-31 | REPORTADO | — | CNV · CUIT 30657863676 |
| Listada en BYMA | SÍ (clasificación del pipeline) | — | — | REPORTADO | — | **NO VERIFICABLE** documentalmente |
| Precio | **2.547,50** | ARS | 2025-12-31 | REPORTADO | — | **Yahoo Finance — NO CNV** |
| **PER** | **11,0944** | x | FY2025 | CALCULADO | Precio / EPS | MIXTO |
| Máximo 52 semanas | **N/D** | — | — | — | — | CNV no publica precios |
| Dif. contra máximo | **N/D** | — | — | — | — | — |
| Mínimo 52 semanas | **N/D** | — | — | — | — | — |
| Dif. contra mínimo | **N/D** | — | — | — | — | — |
| **Deuda / EBITDA** | **0,5632** | x | FY2025 | CALCULADO | (DebtCur+DebtNoCur)/EBITDA | CNV · **CNV oficial 0,56 ✅** |
| **EPS anual** | **229,62** | ARS/acción | FY2025 | **REPORTADO** | tag `EPS_basico` | CNV consolidado |
| EPS CAGR 5Y | **N/D** | — | — | — | — | EPS no positivo en 2020 |
| **Margen neto** | **10,88 %** | fracción | FY2025 | CALCULADO | NetIncome/Revenue | CNV · **CNV oficial 0,11 ✅** |
| ROE 5Y | **N/D** | — | — | — | — | serie con vintage mixto |
| FCF on CE | **N/D** | — | — | — | — | sin CapEx, no hay FCF |
| Payout | **N/D** | — | — | — | — | METR no paga dividendos |

---

## 10. Control de calidad

**A · ¿Cuántos de los 15 prioritarios se encontraron?** → **7 / 15**
Especie, listada en BYMA, precio, PER, Deuda/EBITDA, EPS anual, margen neto.

**B · ¿Cuántos calculados?** → **4** (PER, Deuda/EBITDA, margen neto, y las
participaciones no controladoras como derivadas).

**C · ¿Cuántos reportados directamente por CNV?** → **2** (EPS anual, especie).
El precio es reportado pero **no por CNV**.

**D · ¿Cuántos N/D?** → **8**
Máximo y mínimo 52 semanas + sus dos distancias (CNV no publica precios), EPS
CAGR 5Y, ROE 5Y, FCF on CE, Payout.

**E · ¿Campos con definición CNV no inequívoca?**
1. **Individual vs consolidado** — dos juegos completos para el mismo período,
   con hasta 76,7 % de diferencia. Sin elección declarada, todo ratio es ambiguo.
2. **`Capital`** — se usa como divisor pero CNV no declara si es el número de
   acciones o el capital social en pesos. La identidad del EPS sugiere lo primero.
3. **`CNV_roe`** — 0,15 oficial contra 0,138 / 0,167 / 0,136 según denominador.
   Ninguno cierra.
4. **Signo de las coberturas** — CNV las publica negativas; en magnitud coinciden.
5. **`CF_Inversion`** — no separa CapEx de otras inversiones.

**F · ¿Qué requiere normalización para comparar contra TIKR?**
1. **Moneda**: todo en ARS; TIKR trabaja en USD.
2. **Reexpresión IAS 29**: los EEFF están ajustados por inflación a una fecha; la
   contabilidad estadounidense no lo hace.
3. **RECPAM** (+4.113 M): resultado por exposición a la inflación, sin equivalente.
4. **Perímetro**: consolidado o individual, declarado.
5. **EBITDA**: acá es **reportado por CNV**; en el mundo SEC hay que construirlo.
6. **Escala**: valores en millones (`escala = 1000000`), ya normalizados.
7. **Fiscal year**: cierra 31-12, coincide con el año calendario.

**G · Ejercicio fiscal exacto** → **cierre 2025-12-31**, `tipo A` (acumulado
anual), presentación `accn d96fd259-c5ce-431f-8e14-17af592b99f9`, `form EEFF`,
`fuente cnv-aif2`.

**H · Fecha exacta del precio** → **2025-12-31** (último día hábil del ejercicio).
Fuente **Yahoo Finance**, no CNV.

**I · Principal limitación**
> **CNV no publica cotizaciones, y por eso ocho de los quince campos prioritarios
> —todos los que dependen de precio histórico— no son producibles bajo la regla
> «CNV Only»; y en lo contable, la coexistencia de estados individuales y
> consolidados para el mismo período hace que ningún ratio sea interpretable sin
> declarar antes cuál de los dos perímetros se usó.**

---

## Trazabilidad

Toda cifra contable de este documento tiene, en el CSV:

```
fuente     CNV EEFF consolidado
accn       d96fd259-c5ce-431f-8e14-17af592b99f9   ← presentación ante CNV
form       EEFF
fuente     cnv-aif2                                ← sistema de origen
tipo       A (acumulado anual)
escala     1.000.000
reexpresión 2025-12-31
tag        el concepto CNV exacto
```

**Lo que la trazabilidad NO alcanza:** no hay hash del archivo. Se llega a *qué
presentación*, no a *qué archivo con qué huella*. Es una diferencia real con el
estándar que se aplica del lado SEC, y conviene no confundirlas.
