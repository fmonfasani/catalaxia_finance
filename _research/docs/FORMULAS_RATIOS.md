# Fórmulas de Ratios Detalladas

## 📊 Ratios de Valuación

### PER (Price-Earnings Ratio) TTM

```
PER = Precio Actual / EPS_TTM

Donde:
  Precio = De yfinance (last_price)
  EPS_TTM = NetIncome_TTM / Shares_Diluted_Weighted

Caso especial:
  - Si EPS ≤ 0 → PER = NULL (nunca negativo)
  - Si Precio es NULL → PER = NULL
```

**Interpretación:** Cuántos dólares paga el mercado por cada dólar de ganancia.
- PER < 10: Posiblemente subvaluado (o en problemas)
- PER 15-25: Rango típico
- PER > 40: Posiblemente sobrevaloado (o con fuerte crecimiento esperado)

---

### EPS (Earnings Per Share) TTM Diluted

```
EPS_TTM = NetIncome_TTM / WeightedAverageNumberOfDilutedSharesOutstanding

Donde:
  NetIncome_TTM = Suma de últimos 4 trimestres o Annual + YTD actual - YTD prior
  Shares_Diluted = Último período disponible (stock, no flujo)

Fallback (si NetIncome no existe):
  Buscar "OperatingIncomeLoss" o últimas opciones del script
```

**Interpretación:** Ganancia por acción. Usa "diluted" (incluye opciones/warrants).

---

### Crecimiento EPS 5 años (CAGR)

```
EPS_5Y_CAGR = (EPS_fin / EPS_ini)^(1/5) - 1

Donde:
  EPS_fin = EPS del año fiscal más reciente
  EPS_ini = EPS del año fiscal hace 5 años
  
Requisitos:
  - Mínimo 6 años de datos anuales (10-K)
  - EPS_ini > 0 y EPS_fin > 0
  - Si no hay 5 años → NULL
```

**Interpretación:** Tasa de crecimiento anualizado de ganancias.

---

## 💰 Ratios de Rentabilidad

### Margen Neto TTM

```
Margen Neto = NetIncome_TTM / Revenue_TTM

Donde:
  Revenue_TTM = Suma de últimos 4 trimestres (flujo)
  NetIncome_TTM = Suma de últimos 4 trimestres (flujo)

Fallback Revenue (en orden):
  1. "Revenues"
  2. "RevenueFromContractWithCustomerExcludingAssessedTax"
  3. "SalesRevenueNet"

Caso especial:
  - Si Revenue = 0 → NULL
  - Si Revenue < 0 → NULL (empresa no genera ingresos)
```

**Interpretación:** De cada dólar de ingresos, cuánto es ganancia neta.
- 5%: Bajo margen (ej. retail, energía)
- 15%: Margen saludable
- >30%: Margen muy alto (ej. software, pharma)

---

### ROE (Return on Equity) 5 años CAGR

```
ROE_Año = NetIncome / StockholdersEquity (para ese año)
ROE_5Y_CAGR = CAGR(ROE_años)

Implementación:
  1. Extraer serie anual de NetIncome (10-K solo, ~365d)
  2. Extraer serie anual de StockholdersEquity (último período cada año)
  3. Agrupar por año fiscal
  4. Calcular ROE para cada año
  5. CAGR de esa serie

Requisitos:
  - Mínimo 6 años de datos
  - Equity > 0 para cada año
```

**Interpretación:** Cuánta ganancia genera por cada dólar de patrimonio.
- <5%: Bajo
- 10-15%: Saludable
- >20%: Excelente

---

## 💵 Ratios de Flujo de Caja

### FCF (Free Cash Flow) TTM

```
FCF_TTM = CFO_TTM - CapEx_TTM

Donde:
  CFO = Cash Flow from Operations (NetCashProvidedByUsedInOperatingActivities)
  CapEx = Capital Expenditures (PaymentsToAcquirePropertyPlantAndEquipment)

Fallback CapEx (si no existe primary):
  1. "PaymentsToAcquirePropertyPlantAndEquipment"
  2. "PaymentsToAcquireProductiveAssets"
```

**Interpretación:** Cash disponible después de mantener/expandir assets.
- Si FCF > 0: Empresa genera cash, puede dividendos
- Si FCF < 0: Invirtiendo más de lo que genera, puede estar OK (growth)

---

### FCF on Capital Employed (DOS VARIANTES)

```
VARIANTE 1 (Long-Term Debt):
  CE_1 = StockholdersEquity + LongTermDebt
  FCFonCE_1 = FCF_TTM / CE_1

VARIANTE 2 (Neto de Caja):
  CE_2 = StockholdersEquity + Deuda_Total - Cash
  FCFonCE_2 = FCF_TTM / CE_2
  
  Donde Deuda_Total = LT_Debt + ST_Debt

Ambas buscan responder:
  "De cada dólar invertido en la empresa, cuánto genera en FCF?"
```

**Interpretación:**
- >15%: Excelente retorno
- 5-15%: Saludable
- <5%: Baja eficiencia

---

## 📈 Ratios de Endeudamiento

### Deuda / EBITDA (DOS VARIANTES)

```
EBITDA = OperatingIncome + Depreciation & Amortization
         (No existe como métrica XBRL, se calcula)

VARIANTE 1 (Long-Term Debt):
  D/EBITDA_LP = LongTermDebt / EBITDA_TTM

VARIANTE 2 (Total Debt):
  D/EBITDA_Total = (LT_Debt + ST_Debt) / EBITDA_TTM

Especial:
  - Si EBITDA ≤ 0 → NULL (empresa no es rentable operacionalmente)
  - Si EBITDA es NULL (falta OperatingIncome o D&A) → NULL
  - NUNCA se estima

Fallback D&A (en orden):
  1. "DepreciationDepletionAndAmortization"
  2. "DepreciationAndAmortization"
  3. "Depreciation"
```

**Interpretación:** Años de EBITDA necesarios para pagar toda la deuda.
- <2x: Muy bajo apalancamiento
- 2-4x: Típico
- >6x: Alto riesgo de default

---

### Payout Ratio TTM

```
Payout = Dividendos_TTM / NetIncome_TTM

Donde:
  Dividendos = PaymentsOfDividendsCommonStock (flujo)
  NetIncome = NetIncomeLoss_TTM (flujo)

Fallback Dividendos (si no existe primary):
  1. "PaymentsOfDividendsCommonStock"
  2. "PaymentsOfDividends"

Caso especial:
  - Si NetIncome ≤ 0 → NULL (no puede haber payout si no hay ganancia)
  - Si Dividendos = 0 → Payout = 0 (empresa no paga dividendos)
  - Si Payout > 1.0 → Empresa paga más de lo que gana (insostenible)
```

**Interpretación:** % de ganancias retornado a accionistas.
- 0%: Reinvierte todo (ej. growth tech)
- 30-50%: Balance entre dividendos e inversión
- >70%: Maduro, poca oportunidad de reinversión

---

## 📏 Cambios de Precio 52 Semanas

### Diferencia Máximo 52w

```
Dif_Max = (Precio / Year_High) - 1

Resultado típico:
  -1 a 0 (ó -100% a 0%)
```

**Interpretación:** Cuánto está por debajo del máximo del año.
- -0.05 = 5% por debajo del máximo
- -0.50 = 50% por debajo del máximo (posible compra)

---

### Diferencia Mínimo 52w

```
Dif_Min = (Precio / Year_Low) - 1

Resultado típico:
  0 a ∞ (ó 0% a infinito)
```

**Interpretación:** Cuánto está por encima del mínimo del año.
- 0.20 = 20% por encima del mínimo
- 2.00 = 100% (precio es 2x el mínimo)

---

## 🧮 Cálculo TTM (Trailing Twelve Months)

### Para FLUJOS (Revenue, NetIncome, CFO, CapEx, etc.)

**Estrategia A (Preferida): 4 Trimestres Consecutivos**

```
Requisito:
  - Encontrar 4 datapoints ~90 días cada uno
  - Que sean consecutivos (gap < 5 días entre fin de uno e inicio del siguiente)

TTM = Suma(Q1 + Q2 + Q3 + Q4)
```

**Estrategia B (Fallback): Annual + YTD Actual - YTD Prior**

```
Requisito:
  - Último 10-K (annual, ~365d)
  - Último 10-Q (YTD, 100-290d)
  - YTD del año anterior (mismo período)

TTM = Annual + YTD_Actual - YTD_Prior_Year
      (Equivalente a sumar 4 Q, cuando no hay Q standalone)
```

**Estrategia C (Último Recurso): Último Annual Solo**

```
TTM = Último 10-K valor
      (Si no hay trimestres disponibles)
```

### Para STOCKS (Equity, Debt, Cash, Shares)

```
Valor = Último período disponible (sin sumar)
        (Stock items no se "acumulan" trimestres)
```

---

## ⚠️ Reglas de NULL

**NUNCA se estima un ratio.** Si un componente es NULL o ≤ 0:

| Ratio | Si componente es NULL |
|-------|----------------------|
| PER | Si EPS ≤ 0 → NULL |
| EPS | Si Shares = 0 → NULL |
| Margen | Si Revenue ≤ 0 → NULL |
| ROE | Si Equity ≤ 0 → NULL |
| FCF | Si componente falta → NULL |
| D/EBITDA | Si EBITDA ≤ 0 → NULL |
| Payout | Si NetIncome ≤ 0 → NULL |
| CAGR | Si no hay 5+ años → NULL |

**Implicación:** Un ratio NULL significa "no hay suficiente data confiable", no "asumamos un valor".

---

**Ver también:** `SCRIPT_05_RATIOS.md` para ejemplos con números reales.
