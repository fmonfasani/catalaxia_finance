# KO — EXTRACCIÓN COMPLETA · prueba de extremo a extremo

**2026-09-02** · un solo papel, todas las herramientas existentes
Datos: [`KO_VARIABLES.csv`](KO_VARIABLES.csv) · [`KO_RATIOS.csv`](KO_RATIOS.csv) · `KO_EXTRACTION.json`

```
FACTS EXTRAÍDOS ....................... 90.398 parseados · 45.113 normalizados
VARIABLES ECONÓMICAS .................. 41 de 47 (+4 derivadas por identidad)
RATIOS INTENTADOS .....................  79
RATIOS CALCULABLES ....................  67   (84,8 %)
RATIOS NO CALCULABLES .................  12
RATIOS CALCULABLES CON MARKET DATA ....  17
VARIANTES DE RATIOS ...................  20 ratios con más de una variante
```

---

## A · Identificación

| | |
|---|---|
| empresa | **COCA COLA CO** |
| ticker | KO |
| **CIK** | **0000021344** |
| cómo se determinó | `data/raw/catalogo_edgar/company_tickers_2026-08-31.json` (10.391 entradas) — herramienta existente, sin llamada externa |
| entidad | `E01M14TW48R0PBJQPF1GG1B9S5N` · assertion CIK **VERIFIED / REGISTRY** — ya existía |
| filings | **31 descargados · 17 con XBRL · 14 pre-XBRL** |
| formularios | 10-K, 10-K/A |
| períodos | **17: 2009-12-31 .. 2025-12-31** |

### Pipeline ejecutado — sin scripts nuevos

| paso | comando | resultado |
|---|---|---|
| S00 | `s00_smoke.py` | **PASS** · C-S00-001, C-S00-002 |
| S01 | — | innecesario: KO ya estaba en `identity_v1` con CIK VERIFIED |
| S02 | `s02_fetch_ypf.py --cik 0000021344 --forms "10-K,10-K/A"` | **PASS** · 536/541 archivos |
| S03 | `s03_parse_ypf.py --cik 0000021344` | **PASS** · 31/31 filings, 0 rechazados, 375 s |
| S04 | `s04_normalize.py` | **PASS** · 9/9 controles |

**Ninguna herramienta falló.** Los 5 archivos no descargados son
`index-headers.html` de filings de 2010–2014 que la SEC ya no publica (HTTP 404);
el gate los clasificó como no bloqueantes y el XBRL de esos años sí se obtuvo.

Un dato del pipeline: **S02 y S03 corrieron sobre un emisor US-GAAP con
formulario 10-K sin ninguna modificación**, aunque fueron escritos para YPF
(IFRS, 20-F). El trabajo de parametrización de ciclos anteriores se sostuvo.

---

## B · Datos extraídos

```
parsed.facts (KO) .................... 90.398
derived.fact vigentes ............... 45.113
  no dimensionales .................. 15.137
  dimensionales ..................... 29.976
tags distintos ...................... 1.700
facts principales del último ejercicio . 391
F-061 · punteros de provenance ajenos .... 0
```

Facts principales por año (no dimensionales, fecha = cierre declarado):

```
2025: 391   2021: 348   2017: 358   2013: 340
2024: 377   2020: 352   2016: 354   2012: 342
2023: 381   2019: 338   2015: 345   2011: 378
2022: 382   2018: 347   2014: 333   2010: 299   2009: 84
```

---

## C · Variables económicas — 41 de 47

Los tags candidatos **no se fusionaron**: se registran todos los presentes y se
marca cuál gana por orden declarado (columna `candidatos_presentes` en el CSV).

### Disponibles (valor FY2025, USD)

| variable | tag | valor | períodos |
|---|---|---:|---:|
| Revenue | `Revenues` | 47.941.000.000 | 8 |
| COGS | `CostOfGoodsAndServicesSold` | 18.397.000.000 | 8 |
| GrossProfit | `GrossProfit` | 29.544.000.000 | 17 |
| OperatingIncome | `OperatingIncomeLoss` | 13.764.000.000 | 17 |
| SGA | `SellingGeneralAndAdministrativeExpense` | 14.521.000.000 | 17 |
| D&A | `DepreciationDepletionAndAmortization` | 1.052.000.000 | 17 |
| NetIncome | `NetIncomeLoss` | 13.106.000.000 | 17 |
| NetIncome incl. NCI | `ProfitLoss` | 13.135.000.000 | 17 |
| NCI (resultado) | `NetIncomeLossAttributableToNoncontrollingInterest` | — | 17 |
| PretaxIncome | `IncomeLossFromContinuingOperationsBeforeIncomeTaxes…` | 15.960.000.000 | 16 |
| IncomeTax | `IncomeTaxExpenseBenefit` | 2.854.000.000 | 17 |
| InterestExpense | `InterestExpense` | 1.654.000.000 | 17 |
| InterestIncome | `InvestmentIncomeInterest` | 786.000.000 | 17 |
| Assets | `Assets` | 104.816.000.000 | 17 |
| AssetsCurrent | `AssetsCurrent` | 29.297.000.000 | 17 |
| Cash | `CashAndCashEquivalentsAtCarryingValue` | 9.694.000.000 | 17 |
| Inventory | `InventoryNet` | 4.425.000.000 | 17 |
| Receivables | `AccountsReceivableNetCurrent` | 3.038.000.000 | 17 |
| LiabilitiesCurrent | `LiabilitiesCurrent` | 20.083.000.000 | 17 |
| LiabilitiesAndEquity | `LiabilitiesAndStockholdersEquity` | 104.816.000.000 | 17 |
| Equity | `StockholdersEquity` | 32.169.000.000 | 17 |
| Equity incl. NCI | `StockholdersEquityIncludingPortion…` | 34.271.000.000 | 17 |
| NCI | `MinorityInterest` | 2.102.000.000 | 17 |
| CFO | `NetCashProvidedByUsedInOperatingActivities` | 7.408.000.000 | 17 |
| CFI | `NetCashProvidedByUsedInInvestingActivities` | −67.000.000 | 17 |
| CFF | `NetCashProvidedByUsedInFinancingActivities` | — | 17 |
| CapEx | `PaymentsToAcquirePropertyPlantAndEquipment` | 2.112.000.000 | 17 |
| Dividends | `PaymentsOfDividends` | 8.778.000.000 | 17 |
| DPS | `CommonStockDividendsPerShareCashPaid` | 2,04 | 17 |
| WeightedAvgShares | `WeightedAverageNumberOfSharesOutstandingBasic` | 4.302.000.000 | 17 |
| DilutedShares | `WeightedAverageNumberOfDilutedSharesOutstanding` | 4.313.000.000 | 17 |
| EPS | `EarningsPerShareBasic` | 3,05 | 17 |
| EPS diluido | `EarningsPerShareDiluted` | 3,04 | 17 |
| Goodwill | `Goodwill` | — | 17 |
| PPE | `PropertyPlantAndEquipmentNet` | — | 17 |
| ROU | `OperatingLeaseRightOfUseAsset` | 1.697.000.000 | 6 |
| EffectiveTaxRate | `EffectiveIncomeTaxRateContinuingOperations` | 0,1790 | 16 |
| SharesIssued | `CommonStockSharesIssued` | — | 17 |

### Derivadas por identidad contable — no son equivalencias inventadas

| variable | fórmula | valor FY2025 |
|---|---|---:|
| **Liabilities** | `LiabilitiesAndEquity − EquityInclNCI` | 70.545.000.000 |
| **EBITDA** | `OperatingIncome + D&A` | 14.816.000.000 |
| **FCF** | `CFO − CapEx` | 5.296.000.000 |
| Debt total | `LongTermDebt` o `Current + Noncurrent` | **no disponible en 2025** |

`Liabilities` merece nota: **KO no publica el tag `Liabilities` en ningún
período**. Se deriva del cuadre del balance, que es una identidad, no una
suposición.

### NO disponibles — 6

| variable | por qué |
|---|---|
| **Debt · DebtCurrent · DebtNoncurrent** | ver §G1 — el tag existe hasta 2023 y desaparece del nivel principal en 2024–2025 |
| **SharesOutstanding** | ni `dei:EntityCommonStockSharesOutstanding` ni `CommonStockSharesOutstanding` aparecen como hecho principal. Se usó el promedio ponderado diluido para la capitalización, **declarándolo** |
| **Intangibles** (`FiniteLivedIntangibleAssetsNet`) | presente sólo hasta 2023 |
| **PretaxIncome** en 2009 | el primer ejercicio tiene 84 facts, muy por debajo del resto |

---

## D · Ratios — 79 intentados, 67 calculables (84,8 %)

| familia | calculables |
|---|---|
| MÁRGENES | **8/8** |
| LIQUIDEZ | **4/4** |
| CASH FLOW | **4/4** |
| DIVIDENDOS | **4/4** |
| MERCADO | **5/5** |
| OTROS | **9/9** |
| CRECIMIENTO | 11/12 |
| RETORNOS | 7/8 |
| VALUACIÓN | 12/17 |
| ENDEUDAMIENTO | **3/8** |

### Resultados

**CRECIMIENTO** — Revenue YoY 1,87 % · Net Income 23,29 % · EPS 23,48 % · EBIT
37,73 % · EBITDA 33,84 % · FCF 11,71 % · Revenue CAGR 3Y 3,69 % / 5Y 7,75 % ·
EPS CAGR 3Y 11,50 % / 5Y 11,12 % / **10Y 6,08 %**

**MÁRGENES** — Gross **61,63 %** *(las dos variantes dan idéntico)* · EBITDA
30,90 % · EBIT 28,71 % · Net 27,34 % (controladora) / 27,40 % (incl. NCI) ·
FCF 11,05 %

**RETORNOS** — ROE **40,74 %** (cierre) / **45,97 %** (promedio) / 38,33 % (incl.
NCI) · ROA 12,50 % / 12,76 % · ROCE 16,47 % · FCF on CE 6,34 %

**ENDEUDAMIENTO** — Liabilities/Equity **2,1928** · Interest Coverage 8,3204
(EBIT) / 8,9553 (EBITDA)

**LIQUIDEZ** — Current **1,4588** · Quick 1,2508 ((AC−Inv)/PC) / 0,6253
((Cash+Recv)/PC) · Cash 0,4826

**CASH FLOW** — FCF **5.296 M** (CFO−CapEx) / **7.341 M** (CFO+CFI) ·
FCF/NetIncome 0,4041 · CFO/Revenue 15,45 %

**VALUACIÓN** — EPS 3,05 / 3,04 / **3,046 derivado** · P/E **29,20** / 29,30 ·
P/B 11,94 / 11,21 · P/S 8,01 · P/FCF 72,53 · P/CFO 51,85 · FCF Yield 1,38 % ·
Market Cap **384.115.771.374**

**DIVIDENDOS** — Payout **66,98 %** (Div/NI) / **66,89 %** (DPS/EPS) ·
Dividend Yield 2,29 % · Dividend/FCF 165,77 %

**MERCADO** — precio 89,06 · máx 52s 92,49 · mín 52s 65,35 · distancia al máximo
**−3,71 %** · al mínimo **+36,28 %**

**OTROS** — Equity Ratio 30,69 % · Asset Turnover 0,4574 · Inventory Turnover
4,1575 · DSO 23,13 días · CapEx/Revenue 4,41 % · Tasa efectiva **17,90 %
declarada / 17,88 % calculada** · OCF/NI 0,5652 · BVPS 7,4586

### Tres controles internos que cerraron solos

| | dos caminos | resultado |
|---|---|---|
| Gross Margin | `GrossProfit/Rev` vs `(Rev−COGS)/Rev` | **61,63 % = 61,63 %** |
| EPS | reportado vs `NetIncome/acciones` | 3,05 vs **3,046** — 0,13 % |
| Tasa efectiva | tag declarado vs `IncomeTax/PretaxIncome` | 17,90 % vs **17,88 %** |
| Payout | `Div/NI` vs `DPS/EPS` | 66,98 % vs **66,89 %** |

Nadie pidió estos cruces: salen de haber mantenido las variantes separadas en
vez de elegir una.

---

## E · Market data

| dato | valor | fuente |
|---|---|---|
| instrumento | **354** · KO · US · USD | `market_instruments` |
| velas diarias | **16.272** · desde **1962-01-02** | `market_price_daily` |
| último cierre | **89,06 USD** (2026-08-27) | ídem |
| máximo 52 semanas | 92,49 | `max(high)` |
| mínimo 52 semanas | 65,35 | `min(low)` |
| acciones para capitalización | 4.313.000.000 — **promedio ponderado diluido** | ver §G2 |
| capitalización | 384.115.771.374 USD | derivada |
| enterprise value | **NO DISPONIBLE** | requiere deuda |
| **enlace instrumento → entidad** | **NO EXISTE** | `identity_v1.instrument` |

---

## F · Cobertura

```
ratios intentados ..................... 79
calculables ........................... 67   84,8 %
no calculables ........................ 12   15,2 %
que dependen de market data ........... 17   (todos calculables salvo los 5 de EV)
ratios con más de una variante ........ 20
variables económicas .................. 41/47 + 4 derivadas
```

### Canónico vs experimental

| | |
|---|---|
| **canónico** (`derived.ratio`, el motor) | **1 de 79** — sólo `eps` |
| **experimental** (calculado fuera del motor) | 66 |

El motor canónico devuelve para KO: `eps` CALCULADO 3,05; `pb`, `pe` y
`ev_sales` NOT_CALCULABLE. Los 66 restantes se calcularon **fuera del engine**
con los mismos datos persistidos y están marcados `EXPERIMENTAL / NO CANÓNICO`
en el CSV.

**La brecha no es de datos: es de motor.** Los datos soportan 67; el motor
implementa 4 conceptos de ratio y sólo uno se resuelve para KO.

---

## G · Razones de no calculabilidad — 12 ratios, 2 causas

### G1 · Sin tag de deuda financiera en FY2025 — **11 de los 12**

Afecta: `Debt/Equity`, `Debt/EBITDA`, `Net Debt/EBITDA`, `FCF/Debt`, `CFO/Debt`,
`ROIC`, `EV/Revenue`, `EV/EBIT`, `EV/EBITDA`, `FCF/EV`, `Enterprise Value`.

**No es que el dato no exista. Es que cambió de forma.** Medido:

```
2023-12-31   LongTermDebt 37.507 M · Current 1.960 M · Noncurrent 35.547 M
2024-12-31   ninguno a nivel principal
2025-12-31   ninguno a nivel principal
```

En 2025 `LongTermDebt` **sí existe, pero sólo como hecho dimensional**: 9 filas
desglosadas por instrumento de deuda —U.S. Dollar Notes, Euro Notes, Swiss Franc
Notes, Debentures, Other— y aparentemente en dos bases de medición (26.945 vs
26.931; 15.470 vs 13.619; 778 vs 767; 726 vs 635).

**No hay un total consolidado.** Sumar esas filas exigiría elegir cuál de cada
par y arriesgar doble conteo entre dimensiones. El sistema se negó, y es la
decisión correcta.

**Prueba de que el bloqueo es del período y no del sistema:** los mismos siete
ratios, sobre FY2023, salen todos.

```
deuda total (cur + ncur)   37.507.000.000
Debt/Equity                        1,4459
Debt/EBITDA                        3,0153
Net Debt/EBITDA                    2,2623
FCF/Debt                           0,2599
CFO/Debt                           0,3092
ROIC                              17,28 %
```

**Con FY2023 la cobertura sería 78/79 (98,7 %).**

### G2 · `Revenue CAGR 10Y` — historia del tag

`Revenues` sólo existe desde 2018 (8 períodos). Antes de eso KO usaba otro tag
para el mismo concepto económico, que **no se fusionó por decisión explícita**.
`EPS CAGR 10Y` sí sale (6,08 %) porque `EarningsPerShareBasic` cubre los 17 años.

### G3 · Nota sobre las acciones — no bloquea, pero condiciona

KO no publica `dei:EntityCommonStockSharesOutstanding` como hecho principal. La
capitalización usa el **promedio ponderado diluido**, que no es el conteo de
cierre. P/S, P/FCF, P/CFO, FCF Yield, P/B y BVPS heredan esa aproximación, y
está declarada en cada celda del CSV.

Por eso el motor canónico da `pb` NOT_CALCULABLE: exige el conteo de circulación
y no lo acepta sustituido.

### G4 · El motor no atribuye el precio — bloquea `pe` canónico

`MKT:354` **no está ligado a la entidad** en `identity_v1.instrument`. El precio
existe (16.272 velas) y el motor se niega a usarlo: atribuirlo sería un join por
ticker. Fuera del engine se calculó igual, marcado experimental.

---

## H · Trazabilidad

Ejemplo, `Gross Margin = 61,63 %`:

```
ratio        GrossProfit / Revenue
inputs       GrossProfit  29.544.000.000 USD  ← tag GrossProfit
             Revenues     47.941.000.000 USD  ← tag Revenues
derived.fact fact_key por insumo (en KO_VARIABLES.csv)
             qname http://fasb.org/us-gaap/2025#GrossProfit
source_fact_ids → parsed.facts (mismo cik, mismo accession, mismo qname)
filing       accession 0000021344-26-000009 · form 10-K
RAW          data/raw/engine/CIK0000021344/... con sha256 por archivo
```

`KO_VARIABLES.csv` trae por variable: `accession`, `form`, `filing_date`,
`qname`, `n_source_facts` y `fact_key`. La cadena hasta el archivo es la misma
que valida el control F-061, que sobre KO da **0 punteros ajenos**.

---

## I · Comparación con la tabla de referencia

| campo de referencia | ¿se produce? | valor | fuente |
|---|---|---:|---|
| Precio | **sí** | 89,06 | `market_price_daily` 354 |
| Máximo 52 semanas | **sí** | 92,49 | ídem |
| Mínimo 52 semanas | **sí** | 65,35 | ídem |
| EPS | **sí** ×3 variantes | 3,05 / 3,04 / 3,046 | XBRL |
| P/E | **sí** ×2 | 29,20 / 29,30 | precio + XBRL |
| Net Margin | **sí** ×2 | 27,34 % / 27,40 % | XBRL |
| ROE | **sí** ×3 | 40,74 % / 45,97 % / 38,33 % | XBRL |
| Payout | **sí** ×2 | 66,98 % / 66,89 % | XBRL |
| FCF on Capital Employed | **sí** | 6,34 % | XBRL |
| **Debt/EBITDA** | **no en FY2025** · sí en FY2023 (3,0153) | — | ver G1 |

**Nueve de diez campos de la tabla de referencia se producen para KO**, la
mayoría con más de una variante. El décimo se produce para 2023 y no para 2025,
por el cambio de etiquetado del emisor.

---

## Ventanas

| ventana | estado |
|---|---|
| **FY** | **17 ejercicios, 2009–2025.** Todo lo de este informe es FY |
| **TTM / LTM** | **NO CALCULABLE con lo descargado.** Sólo se pidieron 10-K. Para TTM hacen falta los 10-Q, que `s02_fetch_ypf.py` sabe traer: `--forms "10-Q"`. No se ejecutó por no estar en el alcance |
| trailing de precio | **sí** — 52 semanas, sobre 16.272 velas |

El motor canónico soporta `FY` y `PIT` únicamente, y lo declara en la columna
`window`. No se etiquetó nada como TTM.

---

## ¿Hasta dónde podemos llegar hoy con un único papel?

**Con los datos: hasta 67 de 79 ratios, 84,8 %, sobre 17 años de historia.** Con
20 ratios en más de una variante, cuatro controles internos que cierran solos, y
la cadena de procedencia intacta hasta el archivo de la SEC.

**Con el motor: hasta 1 de 79.**

Ésa es la única conclusión que el ejercicio permite, y es una sola frase: **la
limitación de Catalaxia hoy no está en la extracción ni en los datos — está en
que el motor canónico implementa cuatro ratios.** Descargar, parsear, normalizar
y trazar un emisor nuevo tomó tres comandos y once minutos, sin tocar una línea
de código. Calcular sobre eso 67 ratios tomó un script de análisis.

Los 12 que faltan tampoco son del sistema: 11 salen de que KO dejó de publicar
un total de deuda consolidado en 2024, y se recuperan enteros si se pide FY2023.

---

### Anexo · comandos

```bash
python -c "import json; d=json.load(open('data/raw/catalogo_edgar/company_tickers_2026-08-31.json'));
           print([v for v in d.values() if v['ticker']=='KO'])"      # CIK 21344

python scripts/engine/s00_smoke.py                                    # PASS
python scripts/engine/s02_fetch_ypf.py --cik 0000021344 --forms "10-K,10-K/A"
python scripts/engine/s03_parse_ypf.py --cik 0000021344
python scripts/engine/s04_normalize.py
python scripts/engine/ratio_engine.py --cik 0000021344                # 1/4
python scratchpad/ko_extraction.py                                    # 67/79
```
