# Diagnóstico profundo: Investing.com vs SEC EDGAR (GAAP)

Ingeniería inversa de las divergencias del archivo
`informe_seguimiento_detallado.xlsx - Investing_Ratios.csv`, columna por columna
y ticker por ticker, contra los financials crudos descargados en
`scripts/tickets/datos/financials_sec/`.

Pregunta que responde: **cuando Investing se aleja >10% del valor GAAP de EDGAR,
¿por qué? ¿Se puede reconstruir el número de Investing desde los datos crudos?**

---

## 1. Resumen ejecutivo

De 99 tickers de entrada, hay **65 con datos EDGAR comparables**. Sobre ese set,
excluyendo 5 tickers con datos crudos rotos (ver §3.A), el acuerdo real es:

| Métrica   | n  | \|dif\|≤10% | mediana \|dif\| | Veredicto |
|-----------|----|-------------|-----------------|-----------|
| **EPS TTM**   | 46 | 83% | **2,6%** | ✅ EDGAR reproduce Investing |
| **PER TTM**   | 43 | 79% | **3,6%** | ✅ |
| **Margen neto** | 33 | 82% | **4,0%** | ✅ |
| **Payout**    | 31 | 68% | **2,6%** | 🟡 bueno salvo casos puntuales |
| **ROE TTM**   | 41 | 44% | **10,4%** | 🟠 problema de denominador |
| **Crec. EPS 5Y** | 36 | 3% | **109,5%** | ❌ columna no comparable |

**Conclusión de una línea:** EDGAR-GAAP **sí** está cerca de Investing en las
métricas de nivel (EPS, PER, margen, payout: error mediano 2,6–4%). Las
divergencias grandes se explican por **7 causas raíz concretas y reproducibles**.

> Estos números son el **estado ANTES** de los fixes. Para el resultado tras
> implementarlos, ver §7.

---

## 2. Mapa de las divergencias >10%

107 celdas superaban el 10% de divergencia. Distribución por métrica:

```
CrecEPS : 35   ← columna estructuralmente rota (ver §3.C)
ROE     : 26   ← denominador equity (ver §3.D)
PER     : 13   ← ventana TTM + one-offs / datos stale (§3.A, §3.F)
EPS     : 12   ← idem
Payout  : 12   ← dividendos mal capturados / NI deprimido
Margen  :  9   ← definición de ingreso/net income (§3.E)
```

**57 de las 107 divergencias (CrecEPS+ROE) vienen de solo 2 problemas
metodológicos**, no de 107 misterios distintos.

---

## 3. Las 7 causas raíz (con evidencia)

### A. Datos crudos rotos en EDGAR — NO es diferencia de método, es bug

Empresas extranjeras que dejaron de filear us-gaap detallado o con un tag de
escala equivocada. Acá EDGAR está mal y Investing está bien.

| Ticker | Síntoma EDGAR | Causa cruda | Quién tiene razón |
|--------|---------------|-------------|-------------------|
| **NMR** (Nomura) | PER 75.678.166, EPS ≈0 | `WeightedAvgDilutedShares = 3,04×10¹⁵` (×10⁶ de más); el net income usado es de 2010 | Investing (PER 11,77) |
| **SID** (CSN) | PER 1.142, EPS 0,0009 | Solo hay datos de **2009**; `shares = 1,49×10¹²` (escala equivocada) | Investing |
| **TM** (Toyota) | EPS 3,59 vs 295,25; PER +402% | Financials **congelados en FY2012**. Toyota dejó de filear us-gaap XBRL detallado | Investing |
| **VALE** | Margen 11,3% vs 35,1% | `NetIncomeLoss`/`StockholdersEquity` terminan en **2012** | Investing |
| **HMC** (Honda) | sin ratios | financials vacío (solo `shares` de 2014) | Investing |

### B. IFRS con EDGAR vacío — bug de cobertura del fetcher

`backend/fetchers/sec_edgar.py` cae a `ifrs-full` solo si `us-gaap` está vacío,
**pero `METRICAS_GAAP` lista nombres us-gaap**. La taxonomía IFRS usa otros
(`Revenue`, `ProfitLoss`, …) → se extraen **0 métricas** → columnas en blanco.

Afectados: **INFY, TSM, RIO, BHP, KGC, NVS, SAP, KOF, TX, BBD** + bancos
us-gaap sin tags de income (**MUFG, MFG, ITUB, KB**). Es **cobertura faltante**,
no divergencia. (Fix #1 — pendiente, ver §7.)

### C. Crecimiento EPS 5Y — columna no comparable (35 divergencias)

El CAGR geométrico `(EPS_fin/EPS_ini)^(1/5)−1` explota si el año base es chico,
cero o está contaminado.

| Ticker | Serie EPS anual cruda | CAGR EDGAR | Investing | Por qué |
|--------|----------------------|-----------|-----------|---------|
| **CSCO** | 2020:**0,02** … 2025:2,55 | +173,7% | 2,62% | base FY2020=0,02 corrupto (real ~2,64) |
| **HON** | 2019:**2,00** … 2025:7,36 | +33,5% | 0,49% | base 2019=2,00 (período post-spinoffs) |
| **XOM** | 2022:**−5,25** en la ventana | +12,7% | 4,98% | cíclica con año negativo |

Causas: `serie_anual()` admitía datapoints con `start=None` (períodos
parciales) como años base; el CAGR de 2 puntos es hipersensible; e Investing
usa otra definición (normalizada/consenso).

### D. ROE — equity puntual vs promedio, y equity diminuto por recompras

ROE es la métrica de nivel con peor acuerdo. Dos efectos: EDGAR usaba **equity
puntual** (Investing usa **promedio**), y las empresas con recompras tienen
equity ínfimo que amplifica cualquier diferencia de timing.

| Ticker | Equity EDGAR | ROE EDGAR | ROE Investing |
|--------|-------------|-----------|---------------|
| **CL** | 145 M | 1.470% | 363% |
| **HD** | 13,9 B | 102% | 128% |
| **AMGN** | 9,2 B | 83,9% | 101,3% |
| **MMM** | 3,8 B | 99,6% | 71,5% |

### E. Definición de "ingreso" / "net income" — bancos, holdings, minoritarios

- **Citi (C):** margen 16,8% vs 20,4% — `Revenues` de un banco es ambiguo.
- **BAC:** payout 4,68% vs 30,37% — dividendo total no capturado.
- **CAT, VALE:** pipeline usa `ProfitLoss` (incluye minoritarios) vs el
  atribuible a la matriz que usa Investing.

### F. Ventana TTM: EDGAR cae al "último año fiscal", Investing usa TTM rodante

Cuando `ttm_flujo()` no arma 4 trimestres ni "anual+YTD", cae a la estrategia C
= último FY cerrado, que ya no es un TTM rodante. Si un trimestre reciente tuvo
un ítem no recurrente, Investing lo ve y EDGAR no.

**Caso testigo MRK** — una sola causa explica sus 4 divergencias:

```
EDGAR usa NI = 18,25 B (FY2025 limpio)  →  EPS 7,38 · margen 28,1% · ROE 39,8% · payout 44,8%
Investing implica NI ≈ 8,84 B (TTM con cargo no recurrente)
   →  EPS 3,58 · margen 13,6% · ROE 19,3% · payout 92%
```

Reconstrucción: NI implícito de Investing = precio/PER × shares =
120,6/33,73 × 2.472 M = **8,84 B**, que reproduce *al decimal* margen, ROE y
payout de Investing. Mismo mecanismo invertido en **JNJ** (el FY de EDGAR
incluye una ganancia one-time que Investing limpia) y **LLY** (earnings
acelerando → TTM rodante > FY → PER de Investing menor).

### G. EBITDA e intangibles (hipótesis del usuario) — **confirmada**

`get_serie_alt()` para D&A elegía "el tag con el datapoint más reciente", que a
veces es el **estrecho** `Depreciation` (solo PP&E, sin amortización de
intangibles):

| Ticker | Tag usado (antes) | D&A usado | D&A completo |
|--------|-------------------|-----------|--------------|
| **GE** | `Depreciation` | 4,25 B | `DepreciationDepletionAndAmortization` = **9,29 B** |
| **ORCL** | `Depreciation` | 3,41 B | + amortización intangibles Cerner/NetSuite ≈ 3–4 B |

Para llegar al EBITDA del proveedor:
`EBITDA = OperatingIncome + Depreciation + AmortizationOfIntangibleAssets`
(+ SBC para "adjusted EBITDA"). La amortización de intangibles vive en el tag
`AmortizationOfIntangibleAssets`, que el pipeline no descargaba.

---

## 4. Recomendaciones → implementadas en §7.

---

## 7. Fixes implementados (2026-06-24)

Se implementaron todos los fixes **excepto el #1 (mapeo IFRS)**, que queda
pendiente (enfoque por ahora solo en papeles US-GAAP).

| Fix | Dónde | Qué hace |
|-----|-------|----------|
| #2 escala shares | `03_calcular_ratios.py` | descarta `diluted_shares` si difiere >100× del `CommonStockSharesOutstanding` (NMR) |
| #3 datos stale | `03` | anula todos los ratios si el net income usado tiene >2 años (TM, VALE, SID, NMR) |
| #4 EBITDA/D&A | `sec_edgar.py` + `03` | fetchea `AmortizationOfIntangibleAssets`; elige DDA si existe, si no el tag de mayor TTM, y suma intangibles cuando solo hay `Depreciation` (GE, ORCL, IBM, INTC) |
| #5 ROE | `03` | usa **equity promedio** (no puntual) + flag `roe_no_significativo` si equity <5% de activos (CL) |
| #6 ventana TTM | `03` | flag `ni_es_fy_no_ttm` cuando el "TTM" salió del último FY (estrategia C) en vez de un TTM rodante (MRK) |
| #7 Crec. EPS | `03` | serie anual limpia (solo años fiscales completos) + descarte de año base outlier (<10% de la mediana) → mata el CAGR falso de CSCO |

Flags de calidad expuestos en `ratios_tickets.json` campo `_flags`:
`shares_descartadas_escala`, `stale_<fecha>`, `ebitda_da_mas_intangibles`,
`roe_no_significativo`, `ni_es_fy_no_ttm`.

### Resultado medido (set limpio, antes → después)

| Métrica | mediana antes | mediana después | ≤10% antes → después |
|---------|---------------|-----------------|----------------------|
| **ROE** | 10,4% | **4,1%** | 44% → **62%** |
| EPS | 2,6% | 2,6% | 83% → 84% |
| PER | 3,6% | 3,6% | 79% → 79% |
| Margen | 4,0% | 4,0% | 82% → 82% |
| Payout | 2,6% | 2,6% | 68% → 68% |
| Crec. EPS | 109,5% | 104,2% | 3% → 3% (ya sin valores basura) |

- **Divergencias >10% totales: 107 → 81** (−24%).
- **NMR, SID, TM, VALE** ahora quedan en blanco (antes daban PER 75 millones,
  1.142, etc.): se detectan como stale/escala y no contaminan la comparación.
- **EBITDA** de GE/ORCL/IBM/INTC ahora incluye amortización de intangibles
  (GE 31,4 B comprensivo; INTC 9,5 B; ORCL 29,9 B con intangibles).
- **Crec. EPS** sigue sin ser comparable contra Investing (metodología
  propietaria), pero el lado EDGAR ya no produce valores absurdos como +6528%.

### Pendiente

- **Fix #1 (mapeo IFRS):** recupera ~14 tickers hoy en blanco (INFY, TSM, RIO,
  BHP, KGC, NVS, SAP, KOF, TX, BBD…). Requiere agregar nombres de tags IFRS al
  fetcher. Postergado por decisión de enfocarse en US-GAAP primero.
