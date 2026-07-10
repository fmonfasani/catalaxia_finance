# screener_export.csv — Guía de uso y limitaciones honestas (v4)

> Screener de **571 empresas** (499 S&P 500 + 16 ADR argentinos + 56 BYMA-only),
> **16 ratios comparables** + payout_status + margen_operativo + EV/EBITDA.
> Fundamentales: **S&P/ADR → SEC EDGAR** (10-K, 20-F, XBRL), **BYMA → CNV** (estados
> contables oficiales v2 normalizada). Precios desde yfinance. Pipeline modular en
> `scripts/tickets/screener/` (s0→s2→s3→s4→s6→s7→s8→s5).
>
> **Leé esto antes de usar los datos.** Este archivo documenta cobertura real, fuentes
> y limitaciones de cada ratio.

**Cambios v4 (2026-07):**
- **Fix regresión silenciosa de PER**: en la v3 la tabla `ratios` había perdido la columna
  `per` (se corría `calcular_ratios_base` sin `precios_y_valuacion`), dejando el PER de las
  499 S&P en NULL mientras el pipeline "corría OK". Corregido: los dos pasos van apareados
  en `run_all.py`; el PER de S&P volvió a **93%**.
- **PER válido con equity negativo**: MCD, SBUX, PM, AZO, HCA... tienen patrimonio contable
  negativo por recompras pero PER perfectamente válido. La v3 lo anulaba por error; ahora
  solo se anula P/B y ROE (que sí quedan sin sentido con equity ≤ 0).
- **Sanity gate NIC-29 en EV/EBITDA y Deuda/EBITDA**: valores absurdos por EBITDA ≈ 0 o
  mala unidad (ROSE ev_ebitda=80M, AUSO=142M, ROSE D/EBITDA=14M) se anulan + flag.
- **Reproducibilidad**: `run_all.py` (reconstrucción end-to-end) + jobs periódicos en
  `run_update.py`. Operación documentada en [docs/screener/OPERACION.md](../docs/screener/OPERACION.md).

Fecha de generación: 2026-07.
Cada fila tiene `period_ref` (fecha del último estado contable disponible),
`fuente_fund` (edgar/cnv), `grupo` (sp500/adr/byma_only), `sector` (GICS para S&P,
clasificación propia para AR) y `payout_status` (calculado/no_paga/falta_dato).

**Dos formatos de salida (mismo dato):**
- `screener_export.csv` — para planillas / análisis (CSV con BOM UTF-8).
- `screener_export.json` — para consumo por apps: **array plano de 571 objetos**
  `{columna: valor}` (NaN → `null`). ~490 KB. Se lee en una línea:
  `const data = await fetch("screener_export.json").then(r => r.json())`.
  Ambos se regeneran juntos en `s5_exportar.py`.

---

## Cobertura medida (no estimada)

| Ratio | S&P 500 (499) | ADR (16) | BYMA (56) | Total (571) |
|---|---|---|---|---|
| ROE | 88% | 100% | 93% | 88% |
| ROA | 98% | 100% | 100% | 98% |
| Margen Neto | 89% | 62% | 93% | 89% |
| Deuda/EBITDA | 60% | 50% | 68% | 61% |
| EPS | 98% | 94% | 89% | 97% |
| FCF/CE | 84% | 69% | 91% | 84% |
| Payout | 73% | 44% | 61% | 71% |
| CAGR EPS 5y | 69% | 12% | 61% | 67% |
| PER | 93% | 62% | 34% | 86% |
| P/B | 87% | 88% | 64% | 85% |
| P/S | 91% | 56% | 64% | 87% |
| Precio | 100% | 94% | 96% | 99% |
| **payout_status** | 100% | 100% | 100% | 100% |
| **ev_ebitda** | 72% | 50% | 43% | 68% |
| **margen_operativo** | 73% | 69% | 89% | 74% |

Medido con `scripts/tickets/screener/validar_final.py` (2026-07, post-fixes v4).

**Notas de cobertura:**
- **PER S&P 93%** (antes reportado 94%): el gap restante son 23 empresas con ganancias ≤ 0
  (PER sin sentido), 9 sin NetIncome TTM ensamblable, y unas pocas con PER > 500 flageadas.
- **ROE 88%** (antes 94%): bajó porque ahora se **anula ROE cuando equity ≤ 0** (recompras) —
  ROE = NI/patrimonio no está definido con patrimonio negativo. No es falta de dato, es que
  el ratio no aplica. Los analistas tampoco reportan ROE para esas empresas.
- **ev_ebitda BYMA 43%** (antes 61%): se anularon los valores absurdos por unidad NIC-29.
  Preferimos NULL honesto a un 142.000.000 falso.
- **BYMA FCF/CE y PER bajos** son el techo conocido de la fuente CNV (períodos sin flujo de
  caja; muchas BYMA no son rentables → PER sin sentido).

---

## Cobertura payout_status (nuevo en v3)

| Estado | Total | S&P | ADR | BYMA |
|---|---|---|---|---|
| **calculado** | 403 (71%) | 362 (73%) | 7 (44%) | 34 (61%) |
| **no_paga** | 124 (22%) | 103 (21%) | 6 (38%) | 15 (27%) |
| **falta_dato** | 44 (8%) | 34 (7%) | 3 (19%) | 7 (13%) |
| **respondido** | **527 (92%)** | **465 (93%)** | **13 (81%)** | **49 (88%)** |

---

## Novedades de la v3

### Universo unificado: S&P 500 + ADR + BYMA
Las 571 empresas se unifican en una sola tabla con clave `cuit` (CIK para S&P, CUIT para
Argentina — sin colisiones). Los S&P provienen de EDGAR (SEC), los ADR tienen fundamentales
de EDGAR (20-F) + CNV, y los BYMA-only de CNV. Cada fila lleva `fuente_fund` (edgar/cnv).

### payout_status (nuevo)
Cada empresa se clasifica en tres estados:
- **calculado**: payout numérico disponible (EDGAR para S&P, facts o CNV para BYMA/ADR)
- **no_paga**: la empresa no paga dividendos verificable (sin Dividends en facts/EDGAR)
- **falta_dato**: paga dividendos pero el dato no está disponible (brecha conocida)

Para S&P se verifica contra la tabla facts (CIK→Dividends). Para BYMA/ADR contra
facts.BYMA-* y cnv_dividendos. ~44 empresas (8%) en falta_dato — son el techo actual
de la fuente.

### EV/EBITDA (nuevo)
Enterprise Value / EBITDA. EV = MarketCap + TotalDebt. Para S&P desde ratios EDGAR
(_deuda + _ebitda_ttm, con fallback a pasivos totales). Para BYMA desde CNV
(DebtNonCurrent + DebtCurrent + EBITDA). Para ADR con fuente EDGAR se usa
ratios.ev_ebitda directo de SEC.

**Fuente CNV:** se consulta primero `cnv_estados_v2` (validado); como respaldo
`cnv_estados_norm` con sanity check (el _norm contiene períodos 2026-03-31 con
datos corruptos para TXAR/MOLA EBITDA ~50K vs ~200B real; el sanity rechaza
valores < 0.1% del período anterior). Cobertura 72%, BYMA 61%.

### FCF/CE — cambio en v3.1
De 11% a 84% gracias a los building blocks de EDGAR. Se computa como:
`FCF/CE = _fcf_ttm / (_equity + _deuda)` para cada S&P, usando los mismos valores
que usa EV/EBITDA. BYMA se mantienen en 96% (desde CNV). ADR desde CNV o EDGAR
según fuente.

### flag_no_significativo — saneamiento de valores absurdos (corregido en v4)
Se aplica un post-pase (`s8.apply_no_significativo`) sobre todas las filas que anula el
ratio **solo cuando no tiene sentido**, no cuando es simplemente alto:
- **PER** → NULL si NetIncome (TTM) ≤ 0, o PER > 500. **NO** se anula por equity ≤ 0
  (MCD/SBUX/PM/AZO tienen equity negativo por recompras y PER válido) ni por eps_anual ≤ 0
  (puede ser un corte anual atípico con TTM positivo).
- **P/B** → NULL si equity ≤ 0 o P/B > 50.
- **ROE** → NULL si equity ≤ 0 (indefinido con patrimonio negativo) o |ROE| > 5 (500%, dato
  de unidad mala o equity ínfimo).
- **P/S** → NULL si revenue ≤ 0 o P/S > 50.
- **EV/EBITDA** → NULL si no está en (0, 100] (EBITDA ≈ 0 o mala unidad NIC-29 en BYMA:
  ROSE 80M, AUSO 142M, OEST 71M).
- **Deuda/EBITDA** → NULL si no está en [-25, 40] (ROSE 14M, VICI 51.7, RICH -71).
- Flag `no_significativo=1` en todos esos casos (82 empresas). El valor crudo original vive
  en la tabla `ratios`; el screener muestra NULL para no contaminar rankings/promedios.

### Margen operativo (nuevo)
OperatingIncome / Revenue. Para S&P desde ratios EDGAR (margen_operativo). Para BYMA
desde CNV (OperatingIncome / Revenue). Cobertura 73%. Refleja el negocio subyacente
sin ruido de resultados financieros o extraordinarios.

---

## Novedades de la v2

### CAGR real (deflactado IPC INDEC)
La serie histórica de EPS se **deflacta** por el coeficiente IPC (base dic-2016=100,
proveído en `data/ipc_nacional.csv`) antes de computar el CAGR. El resultado es **crecimiento
real**, no nominal. Los valores **negativos** (ej. TXAR -45%, BPAT -35%) son **correctos**:
en la mayoría de las empresas argentinas las ganancias nominales no le ganaron a la
inflación → caída real. Excepción: BHIP +0.9% real (banco que preservó valor).

El flag `vintage_mixto` indica que las fechas de la serie no alinean exactamente con el
período base de 5 años (esperado en empresas con cambios de fecha de cierre).

### Payout desde CNV (ventana de 12 meses)
Además del payout desde facts (yfinance, 33 entidades), se suma el payout calculado desde
los formularios 339 de dividendos de CNV. El monto del dividendo es **total** (no por
acción) y el formulario 339 **no tiene** campo de UnidadMedida (a diferencia de los EEFF),
por lo que el valor es directo.

**Alineación fiscal:** A diferencia de la v1 que agrupaba dividendos por año calendario
de pago (causando desajustes con el ejercicio fiscal), la v2 suma solo los dividendos
pagados en los **12 meses anteriores al cierre fiscal** (`ultimo`). Esto evita mezclar
dividendos de ejercicios distintos y asegura que `payout = dividendos_del_ejercicio / NI_del_mismo_ejercicio`.
Si el total supera 2× el NetIncome (ej. TXAR 516% → filtrado), se descarta como payout
no operativo.

### Valuación por acción (shares_CNV consistente)
En v1 y v2 inicial, PER = market_cap_yahoo / NetIncome_TTM, P/B = market_cap / Equity,
P/S = market_cap / Revenue. Esto suponía que el market cap de Yahoo usaba las mismas
acciones que CNV. En realidad, Yahoo puede usar solo una clase de acciones (ej. CVH:
552M acciones CNV vs 181M Yahoo, ratio 3.06×), o el TTM de NetIncome suma valores
acumulados duplicando períodos (ej. MOLA: PER 3.10 vs Precio/EPS 6.12). La v2 final
usa **Precio / EPS directo** (no necesita acciones), y para P/B/P/S deriva
`shares = abs(NetIncome / EPS_basico)` del mismo período, consistente con CNV.

Para ADR, el precio en USD se convierte a ARS (`precio_ars = precio_usd / fx_usd_per_ars`)
antes de computar los ratios, asegurando moneda homogénea con los fundamentales CNV.

### Normalización de UnidadMedida
Los estados contables CNV v2 se normalizan por su `UnidadMedida` (MILES → ×1000,
MILLONES → ×1.000.000, otro → ×1). Esto corrigió el bug del v1 que dejaba escalas
inconsistentes entre períodos pre-2021 y post-2021.

### Fallback CNV_* eliminado
En v1 se usaban los ratios oficiales CNV (`CNV_roe`, `CNV_margen_neto`, etc.) como
fallback cuando el valor calculado difería del oficial. Con la v2 normalizada, los valores
calculados son más confiables que los v1 stale que aún persisten en esas columnas.
Ya no se aplica.

---

## Fuente por ratio

| # | Ratio | S&P 500 | BYMA / ADR |
|---|---|---|---|
| 1 | Precio | yfinance (USD) | yfinance (ARS/USD) |
| 2 | PER | EDGAR (ratios) | Precio/EPS per-share (BYMA) o EDGAR (ADR) |
| 3 | Máx 52 sem | yfinance | yfinance |
| 4 | Dif Máx | yfinance | yfinance |
| 5 | Mín 52 sem | yfinance | yfinance |
| 6 | Dif Mín | yfinance | yfinance |
| 7 | Deuda/EBITDA | EDGAR (ratios) | CNV (DebtCurrent+DebtNonCurrent)/EBITDA |
| 8 | EPS anual | EDGAR (ratios) | CNV EPS_basico (BYMA) o EDGAR (ADR) |
| 9 | Crec. EPS 5y | EDGAR (nominal USD) | CNV CAGR real (deflactado IPC) |
| 10 | Margen Neto | EDGAR (ratios) | CNV NetIncome/Revenue |
| 11 | ROE | EDGAR (ratios) | CNV NetIncome/Equity |
| 12 | FCF/CE | — | CNV (CF_Op+CF_Inv)/(Equity+DeudaLP) |
| 13 | Payout | EDGAR (ratios) | facts(yfinance) + cnv_dividendos |
| — | payout_status | EDGAR + facts | facts + cnv_dividendos |
| — | ev_ebitda | EDGAR | CNV (deuda+EBITDA) |
| — | margen_operativo | EDGAR | CNV OperatingIncome/Revenue |

---

## Limitaciones (leer sí o sí)

### 1. Universos con fuentes distintas — NO comparar BYMA vs S&P 1:1
BYMA y S&P/ADR usan fuentes fundamentalmente distintas (CNV vs EDGAR), monedas distintas
(ARS nominal vs USD), y entornos económicos distintos (inflación Argentina vs US).
Los ratios son **comparables dentro de cada universo** pero NO entre universos sin ajuste.
BYMA tiene CAGR real (deflactado IPC), S&P tiene CAGR nominal USD. BYMA usa valuación
per-share (shares_CNV), S&P usa ratios directos de EDGAR. **No rankear BYMA vs S&P por
PER, P/B, P/S, CAGR.**

### 2. PER de BYMA — 34% de cobertura (techo conocido)
Muchas BYMA tienen NetIncome ≤ 0 (no rentables) → PER sin sentido (se anula). Esto no es un
bug, es la realidad del mercado argentino donde muchas empresas son holding o no generan
ganancias positivas. S&P PER cubre 93% — la mayoría de las empresas US son rentables.

### 3. CAGR — dos fuentes, distintos significados
- **BYMA**: CAGR real (deflactado IPC INDEC). Puede tener `vintage_mixto` por cambios en
  la reexpresión NIC 29. **Usalo como orden de magnitud.**
- **S&P**: CAGR nominal USD desde EDGAR. Comparable entre sí pero no con BYMA.

### 4. Valuación por acción (PER / P/B / P/S) — BYMA-only
En BYMA: PER = Precio/EPS, P/B = Precio/BVPS, P/S = Precio/SPS. **No usa market_cap.**
shares_CNV = NetIncome/EPS_basico (consistente CNV pero puede diferir de Yahoo).
En empresas con ganancias/patrimonio/ventas ≈ 0, estos ratios explotan → marcados con
`no_significativo`. **Filtralos antes de promediar.**

### 5. Margen Neto y ROE — flag `no_significativo`
Cubre Revenue ≤ 0, |Margen| > 300%, Equity ≤ 0. El valor crudo se conserva; el flag
indica que no es confiable.

### 6. Payout_status — 8% en falta_dato
44 empresas (8%) están en `falta_dato`: pagan dividendos pero el dato no fue capturado.
Para S&P el gap es el `payout` faltante en la tabla ratios (EDGAR). Para BYMA/ADR es
la falta de formularios 339 de CNV (HTML no capturado). **No asumir que falta_dato = 0.**

### 7. EV/EBITDA — 68% de cobertura (con sanity gate NIC-29)
Para S&P usa `_deuda` de ratios EDGAR (cubre empresas con deuda reportada). Fallback
a pasivos totales (_assets - _equity) que sobreestima deuda para financieras. Para BYMA
usa DebtNonCurrent+DebtCurrent de CNV. **Los valores fuera de (0, 100] se anulan**: en BYMA
la extracción NIC-29 de EBITDA a veces toma una celda de mala unidad (ROSE dio EBITDA=103
con deuda de 1.400M → ev_ebitda=80M), y preferimos NULL a un número falso. Empresas sin
deuda o sin EBITDA confiable quedan excluidas. Esta es la limitación BYMA a atacar en la
próxima iteración (normalización de unidad de EBITDA en la extracción CNV).

### 8. FCF/CE — 84% total (S&P + BYMA)
Se computa `FCF/CE = _fcf_ttm / (_equity + _deuda)` para S&P desde los building blocks de
EDGAR (84%), y desde CNV (CF_Op+CF_Inv)/(Equity+DeudaLP) para BYMA (91%). Los pocos huecos
son empresas sin flujo de caja reportado en el período.

### 9. Datos desactualizados
BYMA: solo PATA_2 (2023, legítimo). S&P/ADR: datos de los últimos 10-K/20-F (2025-2026),
todos actualizados.

### 10. Precios BYMA en ARS
BYMA cotiza en ARS. Los precios USD pueden diferir del CCL/MEP. Tratá la valuación USD
como referencia gruesa.

### 11. Bancos y financieras
PER de bancos argentinos no es confiable (NetIncome mal mapeado en CNV). S&P bancos
tienen PER desde EDGAR (confiable).

### 12. Sin precio (3 entidades)
BOLT_2, PATA_2 y _ADR_8309 no tienen cotización Yahoo. P/B, P/S, PER son NULL.

### 13. ADR: moneda mixta
Los ADR toman fundamentales de EDGAR (USD) o CNV (ARS) según disponibilidad. La columna
`fuente_fund` indica la fuente predominante. No comparar ADR con fuente_fund='cnv' contra
'edgar' sin ajuste monetario.

### 14. S&P faltante: FDXF
FedEx Freight (FDXF) es spin-off de FDX sin filing EDGAR propio. No está en ratios.
El screener tiene 571/572 empresas.

---

## Cómo leer los flags

Antes de rankear o promediar cualquier ratio, **excluí las filas con el flag correspondiente**:
- Ranking por PER/P/B/P/S → excluir `no_significativo`.
- Análisis de Margen o ROE → excluir `no_significativo`.
- Series de crecimiento → CAGR tiene `vintage_mixto` posible (BYMA) o es nominal (S&P).
- Datos actuales → excluir `dato_desactualizado=1`.
- Precios ARS → tratar valuación como referencia.
- payout_status = 'falta_dato' → no asumir 0.

## Qué NO hacer
- No rankear BYMA vs S&P por PER/P/B/P/S/CAGR sin entender las fuentes distintas.
- No promediar PER/P/B/P/S sin filtrar `no_significativo` (contaminan).
- No asumir CAGR negativo BYMA = empresa en crisis (es real, Argentina no crece).
- No asumir payout=0 donde está NULL o falta_dato.
- No comparar valuación ARS 1:1 contra USD (brecha cambiaria).
- No asumir que EV/EBITDA bajo = barato sin verificar si la deuda incluye pasivos operativos.

## Cómo se reconstruye
- **Reconstrucción end-to-end**: `python run_all.py` (EXTRACT → TRANSFORM → ASSEMBLE → EXPORT;
  saltea lo cacheado). Con cache: `run_all.py --skip-extract` (transform + assemble) o
  `--skip-extract --skip-transform` (solo re-ensambla, ~30s, offline).
- **Solo ensamblar**: `python run_screener.py` → s0 (normalizar CNV) → s2 (ratios CNV) →
  s3 (precios yfinance) → s4 (ensamblar BYMA) → s6 (ajustes ADR/bancos) → s7 (unificar S&P
  desde EDGAR) → s8 (payout_status, EV/EBITDA, margen_operativo, no_significativo) → s5
  (validación + export CSV).
- **Actualización periódica**: `python run_update.py --daily|--monthly|--quarterly|--annual`.
- **Validación**: `python validar_final.py` (cobertura × universo, identidades, outliers).

⚠️ `calcular_ratios_base` y `precios_y_valuacion` van **siempre juntos**: el primero dropea
la tabla `ratios` (sin `per`), el segundo la restaura. Correr uno sin el otro deja el PER
de las S&P en NULL (falla silenciosa). `run_all.py` los corre apareados.

Requiere `data/screener.db` (~754MB, no está en git). Contiene todas las tablas
intermedias (ratios EDGAR, cnv_estados_v2/norm, precios, facts, etc.).

Detalle: [docs/screener/PLAN_PIPELINE_COMPLETO.md](../docs/screener/PLAN_PIPELINE_COMPLETO.md) ·
Operación y jobs: [docs/screener/OPERACION.md](../docs/screener/OPERACION.md).

El archivo IPC (`data/ipc_nacional.csv`) es necesario para CAGR real de BYMA.
