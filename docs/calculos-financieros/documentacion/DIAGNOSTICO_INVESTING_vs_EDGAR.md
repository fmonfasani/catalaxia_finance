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

| Métrica   | n  | \|dif\|≤5% | \|dif\|≤10% | mediana \|dif\| | Veredicto |
|-----------|----|-----------|-------------|-----------------|-----------|
| **EPS TTM**   | 46 | 65% | 83% | **2,6%** | ✅ EDGAR reproduce Investing |
| **PER TTM**   | 43 | 63% | 79% | **3,6%** | ✅ |
| **Margen neto** | 33 | 61% | 82% | **4,0%** | ✅ |
| **Payout**    | 31 | 58% | 68% | **2,6%** | 🟡 bueno salvo casos puntuales |
| **ROE TTM**   | 41 | 22% | 44% | **10,4%** | 🟠 problema de denominador |
| **Crec. EPS 5Y** | 36 | 0% | 3% | **109,5%** | ❌ columna no comparable |

**Conclusión de una línea:** EDGAR-GAAP **sí** está cerca de Investing en las
métricas de nivel (EPS, PER, margen, payout: error mediano 2,6–4%). Las
divergencias grandes **no** son "Investing inventa", sino que se explican por
**7 causas raíz concretas y reproducibles** — y dos de ellas son bugs propios de
nuestro pipeline, no diferencias de criterio de Investing.

---

## 2. Mapa de las divergencias >10%

107 celdas superan el 10% de divergencia. Distribución por métrica:

```
CrecEPS : 35   ← columna estructuralmente rota (ver §3.C)
ROE     : 26   ← denominador equity (ver §3.D)
PER     : 13   ← ventana TTM + one-offs / datos stale (§3.A, §3.B)
EPS     : 12   ← idem
Payout  : 12   ← dividendos mal capturados / NI deprimido
Margen  :  9   ← definición de ingreso/net income (§3.E)
```

Es decir: **57 de las 107 divergencias (CrecEPS+ROE) vienen de solo 2 problemas
metodológicos**, no de 107 misterios distintos.

---

## 3. Las 7 causas raíz (con evidencia)

### A. Datos crudos rotos en EDGAR — NO es diferencia de método, es bug

Acá EDGAR está mal y Investing está bien. Son empresas extranjeras que dejaron de
filear us-gaap detallado o que tienen un tag con la escala equivocada.

| Ticker | Síntoma EDGAR | Causa cruda | Quién tiene razón |
|--------|---------------|-------------|-------------------|
| **NMR** (Nomura) | PER 75.678.166, EPS ≈0 | `WeightedAvgDilutedShares = 3,04×10¹⁵` (×10⁶ de más). El `CommonStockSharesOutstanding`=2,90×10⁹ sí es correcto | Investing (PER 11,77) |
| **SID** (CSN) | PER 1.142, EPS 0,0009 | Solo hay datos de **2009**; `shares basic = 1,49×10¹²` (escala ADR pre-split) | Investing |
| **TM** (Toyota) | EPS 3,59 vs 295,25; PER +402% | Financials **congelados en FY2012** (NetIncome, equity, EPS). Toyota dejó de filear us-gaap XBRL detallado | Investing |
| **VALE** | Margen 11,3% vs 35,1%; EPS 1,06 vs 3,65 | `NetIncomeLoss` y `StockholdersEquity` terminan en **2012**. El "TTM" son cifras de hace 13 años | Investing |
| **HMC** (Honda) | sin ratios | financials vacío (solo `shares` de 2014) | Investing |

> **Patrón:** los *foreign private issuers* que reportan en 20-F/IFRS o que se
> dieron de baja del reporting detallado quedan con datos stale o vacíos. **No
> hay que compararlos**: hay que marcarlos y excluirlos.

### B. IFRS con EDGAR vacío — bug de cobertura del fetcher

`backend/fetchers/sec_edgar.py` cae a `ifrs-full` solo si `us-gaap` está vacío
(línea 149), **pero `METRICAS_GAAP` lista nombres us-gaap** (`Revenues`,
`NetIncomeLoss`, …). La taxonomía IFRS usa otros nombres (`Revenue`,
`ProfitLoss`, `EquityAttributableToOwnersOfParent`, …). Resultado: el esquema
queda en `ifrs-full` pero se extraen **0 métricas** → columnas EDGAR en blanco.

Afectados (todos con `esquema=ifrs-full`, EDGAR vacío):
**INFY, TSM, RIO, BHP, KGC, NVS, SAP, KOF, TX, BBD.**
Más bancos us-gaap sin tags de income statement: **MUFG, MFG, ITUB, KB.**

> No es divergencia: es **cobertura faltante**. Fix = agregar el mapeo de tags
> IFRS (ver §5).

### C. Crecimiento EPS 5Y — columna no comparable (35 divergencias)

El CAGR geométrico `(EPS_fin/EPS_ini)^(1/5)−1` **explota** si el año base es
chico, cero o está contaminado. Evidencia cruda:

| Ticker | Serie EPS anual (cruda EDGAR) | CAGR EDGAR | Investing | Por qué |
|--------|------------------------------|-----------|-----------|---------|
| **CSCO** | 2020:**0,02**, 2021:2,61 … 2025:2,55 | +173,7% | 2,62% | base FY2020=0,02 es un dato corrupto (el real fue ~2,64) |
| **HON** | 2019:**2,00**, 2020:8,41 … 2025:7,36 | +33,5% | 0,49% | base 2019=2,00 es un período raro (post-spinoffs) |
| **XOM** | 2022:**−5,25** en la ventana | +12,7% | 4,98% | cíclica con año negativo → CAGR sin sentido |
| **TGT, PFE, WMT, IBM, T…** | EPS con baches | signo cambiado | — | la ventana de 6 años incluye un año atípico |

Causas estructurales:
1. `serie_anual()` admite datapoints con `start=None` y `form=10-K` que a veces
   son períodos parciales/transición → años base falsos (CSCO 0,02; HON 2,00).
2. El CAGR de 2 puntos es hipersensible al extremo.
3. Investing casi seguro usa otra definición (normalizado / consenso de analistas
   / otra ventana).

> **Veredicto:** esta columna no es confiable en ninguno de los dos lados.
> Descartarla o recomputar con mediana de crecimientos interanuales + protección
> de base (§5).

### D. ROE — equity puntual vs promedio, y equity diminuto por recompras

ROE es la métrica de "nivel" con peor acuerdo (mediana 10,4%, solo 44% <10%).
Dos efectos se suman:

1. **EDGAR usa equity puntual del último balance**; Investing típicamente usa
   **equity promedio** `(inicial+final)/2`. En empresas normales eso da 5-15% de
   diferencia.
2. **Empresas con recompras agresivas tienen equity ínfimo o negativo**, y ahí
   cualquier diferencia de timing del denominador amplifica el ROE a niveles
   absurdos:

| Ticker | Equity EDGAR | ROE EDGAR | ROE Investing | Lectura |
|--------|-------------|-----------|---------------|---------|
| **CL** | 145 M | 1.470% | 363% | equity casi cero → ROE no interpretable |
| **HD** | 13,9 B | 102% | 128% | buybacks → equity fino |
| **AMGN** | 9,2 B | 83,9% | 101,3% | idem |
| **MMM** | 3,8 B | 99,6% | 71,5% | equity fino **+** NI deprimido |
| **LLY** | 31,2 B | 66,2% | 107,5% | equity creciendo rápido → promedio ≠ puntual |
| **INTC / KB** | — | ≈0% / −3,5% | −3% / 9,99% | ganancias ≈0 → ROE sensible al signo |

> Fix barato: usar **equity promedio de 5 trimestres** y reportar ROE como "n/s"
> (no significativo) cuando equity < 5% de los activos.

### E. Definición de "ingreso" / "net income" — bancos, holdings, minoritarios

- **Citi (C):** margen 16,8% (EDGAR) vs 20,4% (Investing). El tag `Revenues` de un
  banco es ambiguo (ingreso bruto por intereses vs ingreso neto). Investing usa
  "total revenue" neto → margen mayor.
- **BAC:** payout 4,68% (EDGAR) vs 30,37%. `PaymentsOfDividendsCommonStock` no
  captura bien el dividendo total del banco.
- **CAT, VALE:** el pipeline usa `ProfitLoss` (incluye intereses minoritarios)
  como fallback de `NetIncomeLoss` (atribuible a la matriz). Para márgenes/ROE,
  Investing usa el atribuible a accionistas comunes → diferencia sistemática.

### F. Ventana TTM: EDGAR cae al "último año fiscal", Investing usa TTM rodante

`ttm_flujo()` tiene 3 estrategias; cuando no puede armar 4 trimestres
consecutivos ni "anual+YTD", **cae a la estrategia C = último anual**. Eso ya no
es un *trailing twelve months* rodante: es el FY cerrado. Si un trimestre reciente
tuvo un ítem no recurrente, Investing (TTM real) lo ve y EDGAR (FY) no.

**Caso testigo MRK** — una sola causa explica sus 4 divergencias:

```
EDGAR usa NI = 18,25 B (FY2025 limpio)  →  EPS 7,38 · margen 28,1% · ROE 39,8% · payout 44,8%
Investing implica NI ≈ 8,84 B (TTM con un cargo no recurrente, p.ej. IPR&D/Daiichi)
   →  EPS 3,58 · margen 13,6% · ROE 19,3% · payout 92%
```

Reconstrucción exacta: NI implícito de Investing = precio/PER × shares =
120,6/33,73 × 2.472 M = **8,84 B**. Con ese NI se reproducen *al decimal* el
margen (13,6%), el ROE (19,3%) y el payout de Investing. **No hay misterio: es la
misma empresa, distinta ventana de 12 meses.**

El mismo mecanismo, con signo invertido:
- **JNJ:** el FY de EDGAR incluye una **ganancia** no recurrente → EPS 10,96 vs
  8,64 de Investing (+26,9%), PER 21,99 vs 27,81. Acá Investing "limpia" lo que
  EDGAR-GAAP deja entrar.
- **LLY:** EPS ANN casi idénticos (23,04 vs 22,95) pero PER +23%: con ganancias
  acelerando, el TTM rodante de Investing > FY → su PER baja.

### G. EBITDA e intangibles (tu hipótesis explícita) — **confirmada**

EBITDA no está entre las 6 columnas comparadas, pero el pipeline lo calcula
(`_ebitda_ttm = OperatingIncome + D&A`) y ahí aparece exactamente el fenómeno que
intuías: **el tag de D&A elegido omite la amortización de intangibles.**

`get_serie_alt()` para D&A elige "el tag con el datapoint más reciente", y eso a
veces selecciona el tag **estrecho** `Depreciation` (solo activos fijos) en lugar
de `DepreciationDepletionAndAmortization` (que incluye amortización):

| Ticker | Tag usado | D&A TTM usado | D&A completo disponible | EBITDA |
|--------|-----------|---------------|-------------------------|--------|
| **GE** | `Depreciation` | 4,25 B | `DepreciationDepletionAndAmortization` = **9,29 B** | **subestimado ~5 B** |
| **ORCL** | `Depreciation` | 3,41 B | (no fetcheado) amortización de intangibles Cerner/NetSuite ≈ 3–4 B/año | **subestimado** |
| **IBM** | `Depreciation` | 2,15 B | amortización de intangibles no incluida | subestimado |

**Cómo se llega al EBITDA "non-GAAP" del proveedor (la ingeniería inversa que
pedías):** los proveedores arman

```
EBITDA = Operating Income + Depreciation + Amortización de intangibles
"Adjusted EBITDA" (Oracle, etc.) = lo anterior + Stock-Based Compensation + cargos one-off
```

La amortización de intangibles vive en un tag XBRL aparte
(`AmortizationOfIntangibleAssets`) que el pipeline **no descarga**. Para empresas
muy adquisitivas (Oracle con Cerner, GE, IBM) ese rubro es de miles de millones
por año. Por eso un EBITDA "GAAP minimalista" como el nuestro queda **por debajo**
del EBITDA del proveedor: la diferencia es, casi exactamente, la amortización de
intangibles (más SBC si es "adjusted").

---

## 4. Tabla de ingeniería inversa (divergencias >10%, agrupadas por causa)

| Causa | Tickers afectados | "Quién tiene razón" / qué hacer |
|-------|-------------------|---------------------------------|
| A — datos crudos rotos/stale | NMR, SID, TM, VALE, HMC | Investing. Excluir de EDGAR |
| B — IFRS/banco sin tags | INFY, TSM, RIO, BHP, KGC, NVS, SAP, KOF, TX, BBD, MUFG, MFG, ITUB, KB | Mapear tags IFRS |
| C — CrecEPS roto | CSCO, HON, JNJ, PFE, TGT, VZ, MRK, C, WMT, DE, IBM, T, AMGN, KMB, HD, XOM, USB, LMT, CAT, PCAR, EBAY, GRMN, AXP, LLY, BAC, SNA, ORCL… (35) | Descartar/recomputar la columna |
| D — ROE denominador | CL, HD, AMGN, MMM, LLY, KMB, ORCL, NEM, HON, AMAT, KO, IBM, TRV, PEP, C, BIIB, XOM, MMM | Equity promedio + flag "n/s" |
| E — ingreso/NI bancos | C, BAC, NMR, CAT, USB | Definir revenue/NI por sector |
| F — ventana TTM + one-offs | MRK, JNJ, LLY, BG, NEM, KMB, TRV, MMM | Forzar TTM rodante real; reportar GAAP y "ajustado" |
| G — EBITDA/intangibles | GE, ORCL, IBM, INTC | Fetchear `AmortizationOfIntangibleAssets` |

---

## 5. Recomendaciones concretas para el pipeline

1. **(Bug, alto impacto)** Mapear tags IFRS en `METRICAS_GAAP` o un dict paralelo
   `METRICAS_IFRS` (Revenue, ProfitLoss, EquityAttributableToOwnersOfParent,
   ProfitLossAttributableToOwnersOfParent…). Recupera ~14 tickers hoy en blanco.
2. **(Bug)** Validar escala de shares: si `WeightedAvgDilutedShares` difiere >100×
   de `CommonStockSharesOutstanding`, descartar (arregla NMR, SID).
3. **(Stale data)** Marcar como inválido cualquier ratio cuyo `end` del NI/equity
   sea > 2 años más viejo que el último 10-Q (arregla TM, VALE).
4. **(EBITDA)** Agregar `AmortizationOfIntangibleAssets` y sumarlo al D&A; preferir
   `DepreciationDepletionAndAmortization` sobre `Depreciation` cuando ambos existan
   (arregla GE, ORCL, IBM).
5. **(ROE)** Usar equity **promedio** de 5 trimestres y devolver `n/s` cuando
   equity < 5% de activos.
6. **(TTM)** No dejar que la estrategia C ("último anual") se reporte como "TTM";
   marcar la fila como FY, no TTM. Idealmente exigir 4 trimestres reales.
7. **(CrecEPS)** Reemplazar el CAGR de 2 puntos por mediana de crecimientos
   interanuales, con `base>0` obligatorio y excluyendo años con EPS<0.

---

## 6. Veredicto final

- **Para valuación de nivel (EPS, PER, margen, payout): EDGAR-GAAP está validado.**
  Error mediano 2,6–4% contra Investing en ~45 empresas. Donde diverge >10%, en
  casi todos los casos es por *ventana TTM* o *un ítem no recurrente* — y el número
  de Investing se reconstruye exactamente desde los datos crudos (caso MRK).
- **Para ROE: usable pero con la corrección de equity promedio**; hoy el
  denominador puntual lo hace ruidoso en empresas con recompras.
- **Para Crecimiento EPS 5Y: no usar ninguno de los dos** sin rehacer el cálculo.
- **14 tickers IFRS + 5 stale**: no son "Investing tiene razón y EDGAR no" en el
  sentido metodológico — son **cobertura/calidad de datos** a arreglar en el
  fetcher, no diferencias de criterio.
