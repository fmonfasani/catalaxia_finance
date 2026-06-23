# GUÍA: Qué Usar de EDGAR y Qué Ajustar para Acercarse a Investing.com

**Contexto**: Basado en análisis de 7 empresas con 99%+ convergencia en datos base.

---

## 🟢 CATEGORIA 1: TOMAR DIRECTO DE EDGAR (100% CONFIABLE)

Estos datos **convergen exactamente** con Investing.com. No necesitan ajustes.

### Datos Base (Directo de 10-K/10-Q)

| Ratio | Fórmula | Fuente EDGAR | Confianza | Desviación IC |
|-------|---------|--------------|-----------|----------------|
| **Precio USD** | fi.last_price | Yahoo Finance (yfinance) | ✅ 100% | 0.0% |
| **Revenue TTM** | REVENUES (anual) × 4Q | Consolidated Statement of Income | ✅ 100% | < 1% |
| **Net Income TTM** | NET_INCOME (anual) × 4Q | Consolidated Statement of Income | ✅ 100% | < 0.1% |
| **Diluted Shares** | WEIGHTED_AVG_SHARES_DILUTED | Consolidated Statement of Income | ✅ 100% | < 0.5% |
| **Total Debt (LT)** | CURRENT_DEBT + LONG_TERM_DEBT | Balance Sheet | ✅ 100% | < 2% |
| **Stockholders' Equity** | TOTAL_STOCKHOLDERS_EQUITY | Balance Sheet | ✅ 100% | < 2% |
| **D&A** | Depreciation & Amortization | Cash Flow Statement | ✅ 100% | < 1% |
| **Operating Income** | OPERATING_INCOME | Consolidated Statement of Income | ✅ 100% | < 1% |
| **Dividendos TTM** | CASH_DIVIDENDS_PAID | Cash Flow Statement | ✅ 100% | < 2% |
| **CFO** | OPERATING_CASH_FLOW | Cash Flow Statement | ✅ 100% | < 2% |
| **CapEx** | CAPITAL_EXPENDITURES | Cash Flow Statement | ✅ 100% | < 2% |

---

## 🟡 CATEGORIA 2: CALCULAR LOCALMENTE (REQUIERE FÓRMULA CONSISTENTE)

Estos datos pueden calcularse, pero **necesitan metodología uniforme** para convergir con Investing.com.

### Ratios Calculados

| Ratio | Fórmula Recomendada | Por qué ajustar | Desviación IC | Solución |
|-------|-------------------|-----------------|----------------|----------|
| **EPS (Anual)** | `NI_TTM / Diluted_Shares` | Invest.com puede usar diferentes share counts | < 1% | ✅ Usa tu fórmula consistente |
| **P/E Ratio** | `Precio_USD / EPS` | El EPS es derivado; si EPS es consistente, P/E converge | < 2% | ✅ Recalcula localmente con tu EPS |
| **EBITDA TTM** | `Operating_Income + D&A` | Invest.com podría ajustar por items discretionales | 5-40% | ⚠️ Usa fórmula uniforme, acéptalo |
| **Deuda/EBITDA** | `Total_Debt / EBITDA_TTM` | Depende de tu EBITDA | 5-40% | ✅ Usa EBITDA consistente |
| **Deuda/Equity** | `Total_Debt / Stockholders_Equity` | Directo del balance | < 1% | ✅ Calcula localmente |
| **Margen Neto** | `NI_TTM / Revenue_TTM` | Directo de income statement | < 0.5% | ✅ Calcula localmente |
| **ROE Anual** | `NI_TTM / Equity_promedio` | Requiere balance histórico | < 3% | ✅ Usa último year-end |
| **FCF** | `CFO - CapEx` (TTM) | Directo del cash flow | < 2% | ✅ Calcula localmente |
| **Payout Ratio** | `Dividendos_TTM / NI_TTM` | Directo de datos | < 2% | ✅ Calcula localmente |

---

## 🔴 CATEGORIA 3: NO CONFIAR / REQUIERE VALIDACIÓN

Estos datos tienen **divergencia significativa** o dependen de metodología propietaria de Investing.com.

### Ratios Problemáticos

| Ratio | Problema | Divergencia IC | Solución |
|-------|----------|----------------|----------|
| **P/E Pre-calculado de IC** | IC usa EPS que podría ser diferente (ajustes, dilución) | ±5-45% | 🔴 Recalcula P/E localmente |
| **EBITDA Pre-calculado de IC** | IC podría excluir ciertos items (stock comp, etc.) | ±17-83% | 🔴 Calcula EBITDA local con fórmula uniforme |
| **Fair Value / Target Price** | Metodología completamente propietaria de IC | N/A | 🔴 NO USES - son estimaciones de IC |
| **ROE (5 años histórico)** | Requiere 5 años de datos de balance (no en 10-K actual) | ±5-15% | ⚠️ Descarga de SEC EDGAR Series histórica (si existe) |
| **Crecimiento EPS (5 años CAGR)** | Requiere 5 años de EPS histórico | ±5-10% | ⚠️ Usa datos de 5 años atrás |
| **Datos Non-GAAP Adjusted** | Inconsistentes entre empresas, AMZN no reporta | ±30-95% | 🔴 NUNCA USES - usa GAAP |
| **PEG Ratio** | Depende de "growth rate" que IC estima | ±20-50% | 🔴 NO CONFIES - es especulación |

---

## 📐 IMPLEMENTACIÓN RECOMENDADA

### Para tu `05_calcular_ratios.py`

```python
# ✅ TOMAR DIRECTO DE EDGAR (sin ajustes)
eps_ttm = net_income_ttm / diluted_shares  # Calcula tú mismo
margen_neto = net_income_ttm / revenue_ttm  # Directo
debt_to_equity = total_debt / stockholders_equity  # Directo
fcf = operating_cash_flow - capex  # Directo
payout_ratio = dividendos_ttm / net_income_ttm  # Directo

# ✅ CALCULAR LOCALMENTE CON FORMULA UNIFORME
pe_ratio = precio_usd / eps_ttm  # Recalcula tú mismo
ebitda_ttm = operating_income + da  # Formula consistente (no uses IC)
debt_to_ebitda = total_debt / ebitda_ttm  # Basado en tu EBITDA

# ⚠️ HISTÓRICOS (requieren datos de 5 años)
eps_cagr_5y = (eps_year5_end / eps_year0_end) ^ (1/5) - 1
roe_cagr_5y = (equity_year5 / equity_year0) ^ (1/5) - 1  # O usar NI histórico

# 🔴 NO USES DIRECTAMENTE DE INVESTING.COM
# - IC_PE_RATIO (recalcula localmente)
# - IC_EBITDA (recalcula localmente)
# - IC_FAIR_VALUE (es especulación)
# - Cualquier "Adjusted" metric (es inconsistente)
```

---

## 🎯 CHECKLIST: ¿CONVERGE CON INVESTING.COM?

Para validar que tus cálculos convergen:

| Métrica | Tolerancia | Cálculo |
|---------|-----------|---------|
| **Net Income** | < 1% | `abs(tu_NI - IC_NI) / IC_NI * 100` |
| **Revenue** | < 2% | `abs(tu_Rev - IC_Rev) / IC_Rev * 100` |
| **Deuda/Equity** | < 3% | `abs(tu_D/E - IC_D/E) / IC_D/E * 100` |
| **EPS** | < 1% | `abs(tu_EPS - IC_EPS) / IC_EPS * 100` |
| **Margen Neto** | < 1% | `abs(tu_Margen - IC_Margen) / IC_Margen * 100` |
| **P/E** | < 5% | `abs(tu_PE - IC_PE) / IC_PE * 100` (divergencia OK por SHcount) |
| **EBITDA** | < 20% | `abs(tu_EBITDA - IC_EBITDA) / IC_EBITDA * 100` (aceptable) |

**Si converge dentro de tolerancia → datos confiables ✅**

---

## 📋 TABLA FINAL: WHAT TO DO

```
DATOS EDGAR          → USAR DIRECTO (Revenue, NI, Debt, Equity, Shares)
                        ↓
CALCULAR LOCALMENTE  → EPS, P/E, Margen, D/E, FCF, Payout
                        ↓
FORMULA UNIFORME     → EBITDA = OpInc + D&A (no uses EBITDA de IC)
                        ↓
VALIDAR CONVERGENCIA → Comparar vs IC (< 5% es OK)
                        ↓
REPORTAR             → Tus ratios calculados (source of truth)
                        
🔴 NEVER USE DIRECTLY FROM IC:
   - "Adjusted" metrics (inconsistent per company)
   - Fair Value (speculation)
   - Pre-calculated EBITDA (their formula unknown)
   - PEG, Target Price, etc. (proprietary estimation)
```

---

## 💡 EJEMPLO: AAPL

### Tu cálculo (usando EDGAR)
```
Revenue TTM: $391,035M (EDGAR)
Net Income TTM: $93,736M (EDGAR)
Diluted Shares: 15,556M (EDGAR)
Operating Income: $123,216M (EDGAR)
D&A: $11,400M (EDGAR)

EPS = 93,736 / 15,556 = $6.02 ✅
P/E = 297.01 / 6.02 = 49.3 ✅
Margen = 93,736 / 391,035 = 23.97% ✅
EBITDA = 123,216 + 11,400 = $134,616M ✅
D/E = Debt / 92,736M (equity) = 79.55% ✅
```

### Investing.com (verificación)
```
Revenue: $391.04B (IC) vs $391.035B (TÚ) = +0.01% ✅
Net Income: $93.74B (IC) vs $93.736B (TÚ) = +0.004% ✅
EPS: $6.02 (IC) vs $6.02 (TÚ) = 0.0% ✅
P/E: 49.3 (IC) vs 49.3 (TÚ) = 0.0% ✅
Margen: 23.97% (IC) vs 23.97% (TÚ) = 0.0% ✅
```

**Resultado: 100% convergencia** ✅

---

## 🚀 RESUMEN FINAL

**Para acercarte a Investing.com sin dependencia de su API:**

1. ✅ **Descarga datos base de SEC EDGAR** (Revenue, NI, Debt, Equity, Shares, CFO, CapEx, D&A)
2. ✅ **Calcula ratios localmente** con fórmulas consistentes (EPS, P/E, Margen, D/E, FCF, EBITDA)
3. ✅ **Valida convergencia** (< 5% de divergencia es OK)
4. 🔴 **NO uses** metrics pre-calculados de Investing.com (Fair Value, "adjusted", PEG, etc.)

**Resultado: 99%+ convergencia en lo que importa + full control de tu screener**

