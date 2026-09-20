# EXTRACTION_KNOWLEDGE_BASE.md

**Memoria técnica de extracción y provenance — Catalaxia Finance**
Generado: 2026-08-22 · Método: auditoría documental de los `.md` del repo (sin modificar código).
Etiquetado: `[DOCUMENTADO]` (respaldado por archivo) · `[INFERENCIA]` · `[RECOMENDACIÓN]` · `[NO DETERMINADO]`.

---

## 1. Executive Summary

```
DOCUMENTOS .MD ANALIZADOS:        ~50 relevantes (de 145 totales; el resto es branding/agents/sprints)
FUENTES IDENTIFICADAS:            10 (CNV aif2, SEC EDGAR ×4 endpoints, yfinance, IAMC,
                                     investing.com, JPM adr.com, Comafi, INDEC IPC,
                                     BYVA/TIKR descartadas)
PROBLEMAS HISTÓRICOS:             52 fichas consolidadas (registro §5)
├── CRITICAL:                     10
├── HIGH:                         21
├── MEDIUM:                       14
└── LOW:                          7
PROBLEMAS RESUELTOS:              38
PROBLEMAS ABIERTOS:               14
CONTRADICCIONES DOCUMENTALES:     14 catalogadas (§22)
GAPS DE PROVENANCE:               11 identificados (§19.4)
DATOS NO REPRODUCIBLES:           4 categorías (§19)
```

**Veredicto central** `[DOCUMENTADO]`: la memoria técnica es excepcionalmente honesta — casi todo
problema tiene medición, causa raíz y regla derivada ("marcar antes que fabricar", "medir la regla
antes de aplicarla"). La debilidad estructural es doble: (1) la **provenance profunda** por dato
individual (accession, decimales XBRL, hash por valor, versión de parser) existe en diseño pero
no siempre en las tablas vivas; (2) conviven **tres generaciones documentales** (investigación
`_research`/`calculos-financieros`, fase tickets, screener v5/v3-audit) sin mecanismo uniforme
de deprecación, lo que ya produjo errores reales (migración destructiva aprobada en papel).

---

## 2. Arquitectura actual de extracción

```
┌─ EXTRACCIÓN (upstream, 3 fuentes primarias + 4 secundarias) ──────────────┐
│ CNV (aif2.cnv.gov.ar)      jobs/job1..job8  → cnv_estados(_v2/norm)       │
│ SEC EDGAR (companyfacts)   sec_edgar/01..07 → facts (4.6M filas)          │
│ yfinance                   cargar_byma_yfinance, s3/s3b/s3c → precios     │
│ secundarias: IAMC (cierre oficial BYMA), Comafi (ratio CEDEAR),           │
│ JPM adr.com (CUSIP/dividendos ADR), INDEC (IPC deflactor),                │
│ investing.com (SOLO carga manual validada, rol contraste)                 │
└───────────────────────────────────────────────────────────────────────────┘
            ↓
┌─ NORMALIZACIÓN ───────────────────────────────────────────────────────────┐
│ s0 clave canónica CUIT │ s1_unidades factor_unidad │ s1_bimoneda ARS+USD │
│ s2a fiscal_calendar desde PeriodoBalance                                  │
└───────────────────────────────────────────────────────────────────────────┘
            ↓
┌─ TRANSFORMACIÓN/CÁLCULO ──────────────────────────────────────────────────┐
│ s2 ratios_cnv (7 fundamentales+CAGR) │ s7b eps_ttm/per_base │ s7c CAGR USD│
│ s4 ensamblar 13 ratios │ s7d ADR dos fuentes │ s8 payout_status/EV/EBITDA │
└───────────────────────────────────────────────────────────────────────────┘
            ↓
┌─ VALIDACIÓN Y CALIDAD ────────────────────────────────────────────────────┐
│ s5 gates+export │ s6_contraste vs externos │ s9 guards yfinance-only │    │
│ job7 identidad contable │ v3-audit b0..b9 (snapshot→certificación)        │
└───────────────────────────────────────────────────────────────────────────┘
            ↓
┌─ PUBLICACIÓN ─────────────────────────────────────────────────────────────┐
│ sincronizar_a_produccion.py → PostgreSQL VPS → API FastAPI (11 endpoints) │
└───────────────────────────────────────────────────────────────────────────┘
```

Principios no negociables declarados `[DOCUMENTADO]`: rastreabilidad a raw · un comando reconstruye
todo · moneda por-fact (nunca "SEC=USD") · nada entra al gold sin validar · flags antes que
fabricación · orden de ejecución ES información (no buscar independencia de orden).

---

## 3. Fuentes

### 3.1 SEC EDGAR — fuente primaria US + ADR `[DOCUMENTADO]`

| Aspecto | Detalle |
|---|---|
| Endpoints | `companyfacts/CIK{n}.json` (principal), `companyconcept`, `frames`, `submissions/CIK.json` (**metadata only — NO trae números**), `files/company_tickers.json` (mapping, bajar 1 vez) |
| Auth | Sin API key. **User-Agent obligatorio "Nombre Real email"** — genérico (`Mozilla/5.0`, `python-requests`) → HTTP 403 (verificado 2026-06-24) |
| Rate limit | Oficial 10 req/s compartido. Pipeline usa sleep 0.15s ≈ 6 req/s. **Nunca dos descargas SEC en paralelo**. El mito "5s entre requests" está desmentido |
| CORS | No soporta → llamar siempre desde backend |
| CIK | Siempre `zfill(10)` |
| Forms | 10-K anual, 10-Q trimestral (**Q4 va dentro del 10-K, no existe Q4 standalone**), 20-F anual extranjero, 6-K interino extranjero, F-6 (ratio DR:ORD) |
| Fact XBRL | `{start,end,val,accn,fy,fp,form,filed,frame}`. **flujo** (start+end: Revenue, NI, CF) vs **foto** (solo end: Assets, Equity, Debt). `fy` = año del *filing*, no del período (un 10-K trae 2–3 años con mismo `fy`). Orden de registros NO garantizado |
| Taxonomías | us-gaap (~82%) + ifrs-full (~4%). Buscar SIEMPRE en ambas. Mapeo GAAP↔IFRS construido empíricamente sobre GGAL/ABEV/VIV/PAM/UGP/NU/GGB/LOMA; verificado con ING (482 tags) |
| Tags prioridad | Revenue: `RevenueFromContractWithCustomerExcludingAssessedTax`→`Revenues`→`SalesRevenueNet`. NI: `NetIncomeLoss`→`ProfitLoss` (CAT consolida sub financiera → tagea ProfitLoss). Equity: `StockholdersEquity`. CFO: `NetCashProvidedByUsedInOperatingActivities`. CapEx: `PaymentsToAcquirePropertyPlantAndEquipment`. D&A: `DepreciationDepletionAndAmortization`→`DepreciationAndAmortization` (+`AmortizationOfIntangibleAssets` aparte). EPS diluido: `EarningsPerShareDiluted`. Shares: `WeightedAverageNumberOfDilutedSharesOutstanding` |
| IFRS | `Revenue`, `ProfitLoss`, `ProfitLossFromOperatingActivities`, `Assets`, `Liabilities`, `Equity`, `CashFlowsFromUsedInOperatingActivities`, `DilutedEarningsLossPerShare`, `EquityAttributableToOwnersOfParent` |
| Moneda | Casi todo USD, pero **empresas extranjeras reportan en moneda local**: 11/13 ADR argentinos reportan en ARS `[DOCUMENTADO]`. Excepciones de unidad: `shares`, `USD-per-shares` |
| Cache | Raw cache `data/raw/*.json` = fuente de verdad; re-parseo sin red. Historia inicial 6 años (ampliable re-procesando raw). ⚠️ **Cache eterno detectado**: `construir_base.py` salta empresas con `fecha_facts` no nulo → filings nuevos jamás se bajan (ver EXT-031) |
| Confiabilidad | 🟢 alta como regulador, pero "oficial ≠ limpio": filings con datos corruptos propios (NMR shares ×10⁶, TM/VALE congelados 2012, SID solo 2009, HMC vacío, CAT sin NetIncomeLoss desde 2011) |

### 3.2 CNV Argentina — fuente primaria fundamentales BYMA-only `[DOCUMENTADO]`

| Aspecto | Detalle |
|---|---|
| Endpoints | AutoComplete `cnv.gov.ar/SitioWeb/Empresas/AutoComplete` (universo ~556 empresas: nombre, CUIT, ticker, GUIDs); company page `…/Empresa/{CUIT}` (HTML con todos los GUIDs en acordeón por tipo); presentación `https://aif2.cnv.gov.ar/presentations/publicview/{GUID}`. **`aif2` NO geo-bloqueado; `aif.cnv.gov.ar` SÍ** |
| Clasificación | Variables JS `presentationIdGlobal`, `formTypeId`, `formTypeName` en el HTML → clasificar SIN bajar PDFs. Catálogo `catalogo_formtypes.csv` marca `es_eeff`. FormTypeIds EEFF `{147,349,487,142,488,1001,1002}`; dividendos `{339,244,1007,198,334,1006}`. La página muestra nombre, no ID → keywords |
| Parser EEFF | Códigos universales de 7 dígitos (`1999999`=Activo, `3049999`=NetIncome, `3021800`=RECPAM, `8000009`=ROE pre-calculado). **Ratios pre-calculados `CNV_*` DESCARTADOS** (parser mal-asocia código↔valor: TXAR `CNV_margen_neto=0.85` era solvencia 0.90) |
| Unidades | Normalización por `UnidadMedida` (MILES ×1000, MILLONES ×1e6, `$`=1). CNV cambió convención ~2021 (MILES→MILLONES). Form 339 dividendos **no tiene UnidadMedida** (monto directo total, no por acción). NIC-29 introduce ambigüedad que ensucia EBITDA (TXAR/MOLA ~50K vs ~200B real) |
| Perímetro | INDIVIDUAL vs CONSOLIDADO: Revenue/COGS/Inventory salen del consolidado; NI/Equity/Assets casi siempre individual. Regla adoptada: `perimetro_preferido()` = elegir el perímetro que contenga Revenue y agotarlo |
| Reexpresión | `fecha_reexpresion` columna fantasma (vacía al 100%). Derivable al 100%: NIC 29/RT 6 ⇒ `vintage = period_end`. Una serie puede mezclar hasta **34 vintages**; homogeneización logra 99,78% (178 filas pre-dic-2016 fuera de rango IPC) |
| Rate limit | Respuesta 2–5 s/request. Sleep default 0.3s (extract) / 1s (download). Tope práctico ~800 req/corrida. **Una sola instancia contra aif2**; paralelizar solo con `--rango` disjuntos; respiro 1–2 min entre corridas |
| Resume/cache | resume-safe por logs `log_job5_done.txt`/`log_job6_done.txt`; borrar log = reprocesar. DB `INSERT OR IGNORE` (⚠️ exige saber qué ignora — ver EXT-002). HTMLs crudos gitignoreados en disco, nunca re-bajar |
| Trampas operativas | `job5_v2` sin `--codigos` usa whitelist default que cubre solo 630/2.145 docs (la correcta: 2.144/2.145). `--max` es tope de red, no de documentos. `TipoDeDocumento` ausente en 100% de muestras (callejón sin salida) |
| Confiabilidad | 🔴 el eslabón más frágil (se cae/rate-limitea seguido). Backoff, difiere en vez de arrastrar dato viejo, status en `cnv_last_status.json`. Validación con empresa no-cotizante (360 Energy, CUIT 30711204055) |

### 3.3 yfinance — precios `[DOCUMENTADO]`

| Aspecto | Detalle |
|---|---|
| Rol | Precios de mercado BYMA (`TICKER.BA`) y ADRs US. Única fuente de precio admitida para el gold (política **"yfinance-only"**: si el dato no es confiable → NULL explícito, nunca parchear con otra fuente) |
| Guards | `s9_guards_yfinance.py` valida sanity antes de aceptar; `s9b_rango_52w` calcula rango 52 semanas |
| Trampas | `.BA` devuelve data basura o vacía para ~6 tickers (BOLT_2, PATA_2, _ADR_8309 sin precio); ajustes por splits/dividendos alteran series históricas; no hay garantía de completitud intradía histórica |
| Staleness | Cada fila de precio lleva `staleness_dias`; el snapshot b4 del 2026-08-22 mostró todo VIEJO (44–54 días) → refresco con `s3c_refrescar.py` |

### 3.4 Fuentes secundarias `[DOCUMENTADO]`

| Fuente | Uso | Notas críticas |
|---|---|---|
| IAMC (BCBA) | Precio de cierre oficial BYMA | Requiere slug por empresa; sin API formal |
| Comafi | Ratio CEDEAR (ORD:ADR) | Scraping HTML; usado en s0/s1 para normalizar exposición |
| JPM adr.com / MarkitDigital | CUSIP ADR, dividendos ADR | JSON público; complementa EDGAR para ADRs |
| INDEC | IPC serie mensual | Deflactor NIC-29 base dic-2016=100; serie congelada en repo (riesgo EXT-052) |
| investing.com | Contraste s6 únicamente | **Solo carga manual validada**. El scraping automatizado falló (Playwright bloqueado por Cloudflare) — ver EXT-027 |

### 3.5 Fuentes evaluadas y descartadas `[DOCUMENTADO]`

| Fuente | Motivo de descarte |
|---|---|
| BYVA (proveedor local) | Sin cobertura suficiente / calidad inferior a CNV directa |
| TIKR | Pago; EDGAR gratuito cubre lo mismo |
| Scraping investing automático | Bloqueo Cloudflare persistente; se resolvió con procedimiento manual documentado |

---

## 4. Inventario de datos actual

| Dataset | Ubicación | Volumen medido | Fuente | Estado |
|---|---|---|---|---|
| facts XBRL | `data/screener.db` tabla facts | ~4.600.000 filas | SEC EDGAR companyfacts | 🟢 núcleo |
| cnv_estados_norm | SQLite + Postgres prod | 84.316→**106.421** (post-migr 003) | CNV aif2 | 🟢 reparada |
| cnv_estados_v2 | idem | 81.695→**102.323** | derivada | 🟢 |
| ratios_cnv | idem | 0→**72** | derivada | 🟢 |
| screener.db completo | SQLite local | 754 MB | todas | 🟢 dev |
| PostgreSQL producción | VPS prod (docker catalaxia-db PG16; host en `CATALAXIA_HOST`) | migraciones 002/003 aplicadas 2026-08-22 | sincronización | 🟢 |
| byma_pipeline.db (audit v3) | `data/byma_pipeline.db` | 10 tablas: universo 73, partidas_norm 85.370, anomalias 234, certificación 487/72 | CNV+yf | 🟢 snapshot certificado SHA256 |
| Traza LLM | `data/export_llm/traza_13ratios.csv` | 728 filas = 56×13, capas L0–L5 | derivada | 🟢 verificada contra b6/b7 |
| Reporte auditoría | `docs/10-auditoria-byma-pipeline-2026-08-22.md` | vivo | derivado | 🟢 |

Universo vigente: **73 entidades** = 56 byma_only + 17 ADR (incluye `_ADR_0084` Banco Macro SIN_CNV). Los 13 ratios mapean 1:1 con las columnas 3–15 de `Seguimiento_original.xlsx`. `[DOCUMENTADO]`

## 5. Registro maestro de problemas históricos

Formato: **EXT-### · severidad · fuente · componente · estado**. Evidencia = archivo→sección. Consolidación de las fichas P01–P30 (guías), P-01–P-23 (proyecto/migraciones) y H01–H16 (calculos-financieros), deduplicadas.

### 5.1 CRITICAL (10)

| ID | Problema | Causa raíz | Solución aplicada | Estado |
|---|---|---|---|---|
| EXT-001 | Unidades MILES/Millones mal interpretadas en CNV | Cambio de convención ~2021; parser asumía unidad fija → valores ×1000 y staleness masivo | `factor_unidad()` por `UnidadMedida`; staleness 16/72→1/72 | ✅ RESUELTO |
| EXT-002 | PK `(cuit,concepto,period_end,fecha_reexpresion)` sin tipo_balance: INDIVIDUAL/CONSOLIDADO colisionaban; INSERT OR IGNORE descartaba en silencio (HAVA consolidado 04cfdb86: 72→16 conceptos; 293/2145 docs mutilados =13,7%; prod 84.316 vs local 106.421) | PK diseñada sin perímetro + reexpresión vacía al 100% | Migración 002 (+tipo_balance) + 003 re-extracción offline (+20.628 filas); regla "INSERT OR IGNORE exige saber qué ignora" | ✅ RESUELTO |
| EXT-003 | Dedup de serie XBRL por `fy` colapsaba años comparativos (MRK perdía historia) | `fy` XBRL = año del filing, no del período | Deduplicar SIEMPRE por `end` (fecha del dato) | ✅ RESUELTO |
| EXT-004 | `migrate_sqlite_to_pg.py` destructivo: TRUNCATE + `except: pass` silenciaba fallos; PLAN_MIGRACION_SCREENER_V2 lo aprobaba "listo para producción" | Script escrito rápido, plan no lo leyó | Precondiciones obligatorias (conteos pre/post); migración real hecha con 09-migracion-produccion | ✅ RESUELTO |
| EXT-005 | Regresión silenciosa: correr solo `calcular_ratios_base` borraba columnas `per` de ratios previos | Scripts sobrescribían tabla sin preservar columnas ajenas | Aparear scripts que comparten tabla; verificar columnas post-run | ✅ RESUELTO |
| EXT-006 | Precios cruzados entre mercados (AGRO/CELU/COUR/INTR/HAVA): mismo ticker en BA y NY con monedas distintas | Moneda no era parte de la clave de precio | Incluir moneda como discriminador en clave de precio | ✅ RESUELTO |
| EXT-007 | Re-descarga EDGAR con ventana de 6 años borró ~1.483 filas de historia anterior | Ventana fija en vez de merge incremental | Reparado desde cache raw; regla: re-descarga debe hacer MERGE, nunca REPLACE | ✅ RESUELTO |
| EXT-008 | Mezcla de perímetros en ratios de holdings: MargenNeto HAVA = NI individual ÷ Revenue consolidado (GCLA individual ~5.000M vs consolidado ~119.000M = 16×; HAVA+GARO 85/141 contaminados) | Ratios armados cruzando partidas de perímetros distintos | `perimetro_preferido()` = perímetro que contiene Revenue, agotarlo completo | ✅ RESUELTO |
| EXT-009 | Duplicación de 190.737 filas en carga | Cambio de formato de clave entre corridas sin upsert | Upsert con clave canónica estable | ✅ RESUELTO |
| EXT-010 | Scripts de análisis escribían directo sobre la DB de producción real (SCREENER_DB faltante apuntaba a prod) | Path default no configurado + sin entorno separado | Separar dev/prod explícito; nunca default silencioso a prod | ✅ RESUELTO (parcialmente verificado `[INFERENCIA]`) |

### 5.2 HIGH (21)

| ID | Problema | Estado |
|---|---|---|
| EXT-011 | IFRS sin fallback de tags → 0 métricas para emisores IFRS | ✅ RESUELTO (mapeo GAAP↔IFRS empírico) |
| EXT-012 | TTM con datos incompletos: estrategia A (solo último FY) y B (10-K+10-Q) insuficientes; adoptada **estrategia C** = 4 trimestres exactos del calendario fiscal propio | ✅ RESUELTO |
| EXT-013 | Stale data en foreign issuers (TM/VALE congelados desde 2012 en EDGAR) | ⚠️ PARCIAL: detectados y excluidos; no hay guard automático permanente `[INFERENCIA]` |
| EXT-014 | Escala de shares corrupta en filings (NMR ×10⁶, SID solo 2009) → PER absurdo | ✅ RESUELTO por detección; regla "validar escala antes de calcular" |
| EXT-015 | EBITDA tag demasiado estrecho (solo `DepreciationDepletionAndAmortization`) subestimaba D&A real | ✅ RESUELTO con fallback `AmortizationOfIntangibleAssets` |
| EXT-016 | ROE con equity puntual (fin de año) vs promedio — distorsión en empresas en crecimiento | ⚠️ DOCUMENTADO como limitación conocida |
| EXT-017 | CAGR calculado sobre base corrupta (años con datos faltantes o negativos) | ✅ RESUELTO: extremos >0, mín 6 años anuales |
| EXT-018 | CAT sin `NetIncomeLoss` desde 2011 (tagea solo ProfitLoss) | ✅ RESUELTO con fallback a ProfitLoss documentado |
| EXT-019 | **Cache eterno**: `construir_base.py` saltaba empresas si `fecha_facts` no era NULL → filings nuevos jamás descargados | ✅ RESUELTO 2026-08-22 — invalidación POR FECHA vía `_caducidad.py` (BLOCK si falta el módulo); flag `--force-refresh` en `construir_base.py` y `run_all.py`; huella de descargas en `ingesta_log` |
| EXT-051 | Namespace dual de precios: `precios_diarios` usa ticker canónico (`YPFD`) pero filas legacy de `precios` usan símbolo yfinance (`YPF`) → ADRs stale pese a serie fresca | ✅ MITIGADO 2026-08-22 — `s3c` aparea via `screener.cuit ↔ ADR_YF`. Deuda P1: consolidar convención única de ticker en `precios` (O3) |
| EXT-020 | 10 ADRs argentinos sin asociar a su CIK/estructura DR→ORD | ❌ ABIERTO |
| EXT-021 | PER S&P500 no reproducible contra Investing (usaban mcap/NI vs precio/EPS) | ✅ RESUELTO: definición por grupo (S&P mcap/NI; BYMA precio/EPS_ttm) |
| EXT-022 | Refresco parcial MSFT incoherente (mezclaba snapshot viejo+parcial nuevo) | ✅ RESUELTO: refresco atómico por empresa |
| EXT-023 | ADRs keyed por razón social → splits de nombre rompían joins | ✅ RESUELTO: claves canónicas CUIT/CIK v2 |
| EXT-024 | Vintage NIC-29 fantasma: columna fecha_reexpresion vacía 100% pero 34 vintages reales mezclados | ✅ RESUELTO: derivable `vintage=period_end` + deflactación IPC INDEC (99,78% homogéneo) |
| EXT-025 | Moneda ARS reportada en facts de ADR contradecía supuesto "SEC=USD" | ✅ RESUELTO: moneda por-fact |
| EXT-026 | Market cap clase única para empresas multi-clase (CVH) distorsiona mcap | ❌ ABIERTO `[NO DETERMINADO]` tratamiento final |
| EXT-027 | Scraping investing automatizado fallido (Cloudflare) | ✅ RESUELTO: procedimiento manual validado |
| EXT-028 | Payout con ventanas desalineadas al cierre fiscal (TXAR 149%, luego 516% con otra ventana) | ✅ RESUELTO: ventana 12m alineada a cierre fiscal |
| EXT-029 | NIC-29 ensucia unidad de EBITDA (TXAR/MOLA ~50K vs ~200B) | ⚠️ PARCIAL: flags NOMINAL_sin_deflactar; EBITDA nominal aún ambiguo |
| EXT-030 | 6-K ignorados por el extractor → eventos interinos extranjeros perdidos | ❌ ABIERTO |
| EXT-031 | Bancos/financieras usan plantilla CNV distinta (códigos universales no aplican igual) | ❌ ABIERTO — cobertura parcial |

### 5.3 MEDIUM (14)

| ID | Problema | Estado |
|---|---|---|
| EXT-032 | IPC INDEC serie congelada en repo → deflactación desactualiza | ❌ ABIERTO (monitoreo) |
| EXT-033 | CSV con separador ambiguo para Excel (locale AR) | ✅ RESUELTO convención export |
| EXT-034 | `period_ref` faltante en TTM de 13 ADR → no se sabía qué trimestres componían el TTM | ✅ RESUELTO: period_ref obligatorio |
| EXT-035 | PER anulado indebidamente cuando equity<0 (regla aplicada donde no correspondía) | ⚠️ PARCIAL |
| EXT-036 | Auditoría sin expectativa previa → falsos huecos reportados | ✅ RESUELTO: siempre definir expectativa antes |
| EXT-037 | `ultimo_periodo` del S&P500 falso (mezclaba fechas de filing) | ✅ RESUELTO |
| EXT-038 | tipo_balance vacío en filas BYMA históricas | ✅ RESUELTO migración 002 |
| EXT-039 | 659 period_end fuera de fin de mes (fechas intermedias XBRL) | ⚠️ DOCUMENTADO, tolerado con normalización |
| EXT-040 | screener_hist / tabla histórica prometida no existe; endpoint /v2/hist 500 (función nunca implementada) | ❌ ABIERTO |
| EXT-041 | Ejercicios no-calendario (A3/RIGO/BOLT_2/PATA_2/CELU/LEDE/CAPX/MOLA): CAGR y TTM mal alineados si se asume dic | ✅ RESUELTO: fiscal_calendar desde PeriodoBalance |
| EXT-042 | LONG salto ~100× en partida (escala) detectado en anomalías b2 | ⚠️ EN SEGUIMIENTO (anomalias ESCALA_JUMP ALTA=178) |
| EXT-043 | TXAR falta EERR 2025 en CNV (documento no publicado) | ❌ ABIERTO re-extraer al publicarse |
| EXT-044 | _ADR_0580 EPS anual roto (~258 billones de acciones) | ❌ ABIERTO investigar filing |
| EXT-045 | _ADR_2807 revenue corrupto en EDGAR | ❌ ABIERTO |

### 5.4 LOW (7)

| ID | Problema | Estado |
|---|---|---|
| EXT-046 | INVJ/DOME/VALO sin cash flow declarado (CF_Op/NI>10x o nulo) → FCF inválido | ⚠️ flags activos |
| EXT-047 | GRIM/AGRO/FIPL línea de resultado ambigua (continuadas vs totales) | ❌ ABIERTO decisión metodológica |
| EXT-048 | Payout definición bancaria distinta (dividendos sobre utilidades vs fcf) | ❌ ABIERTO |
| EXT-049 | Revenue/NI definición por sector (financieras: Revenue≈Ingresos financieros) | ❌ ABIERTO |
| EXT-050 | Shares inestables NI/EPS → PER_2PATH divergente (10 FAIL b6: AGRO, ALUA, A3, SEMI, MIRG, CGPA2, ECOG, MOLA, BYMA, DGCE — DGCE factor ~1000 sospecha splits no reflejados) | ❌ ABIERTO hipótesis documentada |
| EXT-051 | Referencias cruzadas `CNV_*` pre-calculadas rotas (TXAR margen 0.85 era solvencia) | ✅ RESUELTO descarte total + parser propio |
| EXT-052 | Monitoreo INDEC/manual investing sin automatización | ❌ ABIERTO aceptado |

**Balance**: 40 resueltos/mitigados · 13 abiertos (EXT-020, 026, 030, 031, 032, 040, 043, 044, 045, 047, 048, 049, 050) · resto parcial/en seguimiento.

---

## 6. DO_NOT_REPEAT (extracto ejecutable)

La lista completa normativa está en **DO_NOT_REPEAT.md** (raíz). Núcleo:

1. Nunca deduplicar series XBRL por `fy` — SIEMPRE por `end`.
2. Nunca asumir unidad fija en CNV — leer `UnidadMedida` por documento.
3. Nunca mezclar perímetros INDIVIDUAL/CONSOLIDADO dentro de un ratio.
4. Nunca TRUNCATE+except-pass en migraciones — precondiciones de conteo.
5. Nunca dejar INSERT OR IGNORE sin log de lo que ignora.
6. Nunca parchear dato dudoso con otra fuente — flag/NULL antes que fabricación.
7. Nunca correr dos descargas SEC en paralelo; User-Agent real obligatorio.
8. Nunca confiar en ratios pre-calculados de terceros (`CNV_*`) sin auditar el parser.
9. Nunca sobrescribir una tabla compartida sin verificar columnas de otros scripts.
10. Nunca default silencioso a la DB de producción.

## 7. Dónde se pierde información (por etapa)

| Etapa | Qué se pierde | Gravedad |
|---|---|---|
| Descarga CNV | Documento original PDF nunca se baja (solo HTML publicview); respuesta HTTP no persistida (no existe ≠ rate-limited se ven igual); `TipoDeDocumento` ausente en muestras | MEDIA |
| Parseo CNV | Asociación código↔valor del parser propio puede fallar silenciosamente si no hay validación de identidad contable; ratios pre-calculados descartados sin conservar copia cruda | ALTA (mitigado con job7 identidad) |
| Descarga EDGAR | `fecha_facts` pisada en cada descarga (solo queda la última); accession y decimales XBRL presentes en raw pero **no propagados** a facts normalizado | MEDIA |
| Normalización | Unidad original a veces sobrescrita tras factor_unidad (sin columna `_unidad_original` uniforme); perímetro original en algunos paths | MEDIA |
| Cálculo | Motivo de descarte (por qué un ratio quedó NULL) no siempre persistido como flag; TTM sin period_ref fue resuelto pero ADRs históricos carecen de él | BAJA-MEDIA |
| Export/publicación | job_id / parser_version / git_commit no incluidos en exports; hash por valor inexistente | MEDIA |

`[DOCUMENTADO]` salvo indicación. Conclusión: la pérdida grave ya está mitigada (identidad contable, period_ref, claves canónicas); la pérdida **residual es de metadata de auditoría**, no de valores.

## 8. Identidad de empresas

- Claves canónicas v2: CUIT para BYMA, CIK para US/ADR; prefijos sintéticos `BYMA-*` para entidades sin CUIT mapeable. `[DOCUMENTADO]`
- La equivalencia `cuit == cik` numérica NO colisiona en la práctica, PERO los prefijos sintéticos no son detectables por tipo → ambigüedad de clasificación. `[DOCUMENTADO]`
- ADRs keyed históricamente por razón social causó splits (EXT-023). Regla: identidad solo por clave canónica, jamás por nombre.
- 10 ADRs siguen sin asociar CIK↔ORD (EXT-020). `_ADR_0084` Banco Macro SIN_CNV es caso especial (solo SEC). `[DOCUMENTADO]`

## 9. Unidades

- Única verdad: `UnidadMedida` por documento CNV (`$`=1, MILES ×10³, MILLONES ×10⁶). Cambio de convención ~2021 hace inválida cualquier tabla histórica que no aplique `factor_unidad()`. `[DOCUMENTADO]`
- Form 339 dividendos SIN unidad (monto total directo). `[DOCUMENTADO]`
- NIC-29 reexpresión rompe unidades relativas (EBITDA TXAR/MOLA off por ~4.000×): flag obligatorio. `[DOCUMENTADO]`
- XBRL: unidades explícitas por fact (`shares`, `USD-per-shares`, moneda local). Nunca asumir USD. `[DOCUMENTADO]`

## 10. Monedas

- Regla adoptada: **moneda por-fact**, nunca por fuente. 11/13 ADR argentinos reportan en ARS dentro de EDGAR. `[DOCUMENTADO]`
- Bimoneda BYMA: s1_bimoneda mantiene ARS y USD paralelos; conversión solo vía MEP pareado (b4 dif_check 56/56 OK). `[DOCUMENTADO]`
- CAGR dolarizado: BYMA deflactada IPC INDEC (base dic-2016=100) y luego convertida MEP; S&P nominal USD. Flag `NOMINAL_sin_deflactar`. `[DOCUMENTADO]`
- Diseño CCL existente pero NO verificado contra realidad → no usar sin validar. `[DOCUMENTADO]`

## 11. Calendarios y períodos

- Ejercicio fiscal propio desde `PeriodoBalance` (fiscal_calendar s2a) — 8 empresas no-calendario ya cubiertas (A3/RIGO/BOLT_2/PATA_2/CELU/LEDE/CAPX/MOLA). `[DOCUMENTADO]`
- TTM = estrategia C: 4 trimestres exactos consecutivos del calendario fiscal; `period_ref` obligatorio. Q4 vive dentro del 10-K. `[DOCUMENTADO]`
- EPS anual = último FY completo (NO TTM) porque faltan shares trimestrales confiables. `[DOCUMENTADO]`
- 659 `period_end` intermedios fuera de fin de mes: tolerados, normalizar al comparar. `[DOCUMENTADO]`

## 12. Separación RAW / PARSED / NORMALIZED / DERIVED

```
RAW        HTMLs CNV en disco (gitignore), JSON companyfacts en data/raw/*.json,
           respuestas yfinance crudas. Inmutable, cache permanente. Fuente de verdad.
PARSED     cnv_estados (valores por documento+código universal), facts (XBRL plano).
           Determinista desde RAW. Aquí viven accession/unidad original.
NORMALIZED cnv_estados_norm/_v2: factor_unidad aplicado, perímetro resuelto,
           claves canónicas, vintage=period_end. Rebuildable desde PARSED.
DERIVED    ratios_cnv, screener final, metricas b5, traza LLM. NUNCA editable a mano;
           todo valor debe poder reconstruirse citando sus inputs (lineage §14).
```

## 13. Especificación de huella (provenance) por capa

**Objetivo declarado del proyecto**: poder demostrar, dentro de años, de dónde salió cada número. `[DOCUMENTADO]`

| Nivel | Campos |
|---|---|
| **OBLIGATORIO** | `source_system` (cnv/sec/yfinance/manual) · `entity_key` canónico (CUIT/CIK) · `concepto` · `period_end` · `unidad` post-factor · `moneda` · `perimetro` (I/C) · `extracted_at` · `doc_guid` o `accn` |
| **RECOMENDADO** | `raw_ref` (path HTML/JSON crudo) · `unidad_original` · `parser_version`/git_commit · `job_id` · `download_date` · `form_type` · `es_restatement` · `decimales_xbrl` |
| **OPCIONAL** | `hash_valor` · URL completa · `response_http` · `motivo_descarte` para NULLs · vintage del deflactor usado |

Estado real `[DOCUMENTADO]`: OBLIGATORIO mayormente cubierto desde migración 002; RECOMENDADO parcial — accession y decimales existen en raw pero NO se propagan a facts; OPCIONAL casi inexistente (gaps §19.4).

## 14. Lineage de derivados

Cada DERIVED debe citar `(tabla_norm, entity_key, concepto, period_end, perimetro)` de cada input + versión de fórmula. Implementaciones vivas `[DOCUMENTADO]`:
- `payout_source` indica qué fórmula/fallback produjo el payout.
- Traza LLM L0→L5 (`data/export_llm/traza_13ratios.csv`): valor final reproducido con inputs por capa — patrón de lineage a generalizar.
- Certificación b7: motivos NOT_CERTIFIED citan el check fallado (PER_2PATH_desvio, ESCALA_ALTA_xN, IDENTIDAD_balance, MARGEN_ALTA_CNV).
- Regla de oro: si un número no responde "¿de qué partidas saliste?", no entra al gold.

## 15. Snapshots e inmutabilidad

- `snapshot_byma.py` certifica fuentes con SHA256 antes del pipeline audit → cada corrida es reproducible contra snapshot nombrado. `[DOCUMENTADO]`
- Filosofía vigente: difiere/refresca antes que arrastrar dato viejo; status visible (`cnv_last_status.json`, `staleness_dias`). `[DOCUMENTADO]`
- Deuda: producción sin swap atómico ni screener_hist (EXT-040); snapshots hoy solo en flujo audit local. `[INFERENCIA]`

## 16. Matriz de confiabilidad fuente × dato

| Dato | EDGAR | CNV | yfinance | Secundarias |
|---|---|---|---|---|
| EEFF anual US/ADR | 🟢 alta (trampas conocidas §3.1) | n/a | n/a | — |
| EEFF BYMA-only | n/a | 🟡 media-alta (unidades/perímetro resueltos; plantilla financieras abierta EXT-031) | n/a | — |
| Precio ADR US | n/a | n/a | 🟢 alta | — |
| Precio .BA | n/a | n/a | 🟡 media (~6 tickers basura) | IAMC contraste |
| Ratio CEDEAR | n/a | n/a | n/a | 🟡 Comafi scraping |
| CUSIP/dividendos ADR | 🟢 20-F/F-6 | n/a | 🟢 dividendos | JPM adr.com |
| IPC deflactor | n/a | n/a | n/a | 🔴 INDEC serie congelada (EXT-032) |
| Contraste cruzado | s6 vs investing manual | job7 identidad contable | guards s9 | — |

## 17. Checklists operativos por extracción

**CNV**: 1 instancia contra aif2 · sleep ≥0.3s · resume-safe borrar solo si re-proceso intencional · `--codigos` completo (2.144/2.145) · validar identidad contable post-parseo (job7) · `UnidadMedida` siempre leída · status a `cnv_last_status.json`.
**EDGAR**: UA real nombre+email · secuencial · CIK zfill(10) · dedup por `end` · buscar us-gaap E ifrs-full · flujo vs foto según start/end · cache raw primero (`--force-refresh` cuando exista, EXT-019) · validar escala de shares antes de calcular.
**yfinance**: guards s9 obligatorios · NULL ante dato dudoso (nunca parche) · staleness visible · refresco s3c tras corrida larga.
**Cualquier fuente**: snapshot/hash ANTES de correr pipeline pesado · expectativa definida antes de auditar (EXT-036) · flags/motivos para todo NULL.

## 18. Backlog priorizado de extracción

| Prioridad | Ítem | Ref |
|---|---|---|
| P0 | Invalidación de cache EDGAR por fecha filing (forzar refresh incremental) | EXT-019 |
| P0 | Resolver PER_2PATH: splits/dilución/shares (empezar por DGCE ×1000) | EXT-050 |
| P1 | Asociar 10 ADRs restantes a CIK + estructura DR→ORD | EXT-020 |
| P1 | Ingerir 6-K interinos extranjeros | EXT-030 |
| P1 | Plantilla CNV bancos/financieras (códigos alternativos) | EXT-031 |
| P1 | Propagar accn+decimales+unidad_original a facts normalizado | §13/§19.4 |
| P2 | _ADR_0580 EPS roto / _ADR_2807 revenue corrupto: revisar filings | EXT-044/045 |
| P2 | Definición EBITDA única + payout bancario + Revenue/NI por sector | EXT-029/048/049 |
| P2 | screener_hist + swap atómico en producción | EXT-040 |
| P3 | Actualizar serie INDEC + automatizar monitoreo | EXT-032/052 |
| P3 | TXAR re-extraer al publicarse EERR 2025 | EXT-043 |

## 19. Reproducibilidad

### 19.1 Clasificación de componentes

| Clase | Definición | Componentes |
|---|---|---|
| **A** Rebuildable-total | Sin red, determinista desde RAW/PARSED | s0,s1,s2,s2a,s4,s7*,s8,b1–b9,traza |
| **B** Red-determinista | Idempotente con clave canónica, resume-safe | jobs CNV 1–8, extractores EDGAR 01–07, yfinance s3/s3c/s9 |
| **C** Manual-dependiente | Requieren humano o fuente opaca | carga investing validada, IAMC slug, Comafi |
| **D** Frágil/deprecada | No confiar | migraciones destructivas viejas (EXT-004), screener_hist (inexistente), parsers pre-factor_unidad |

### 19.2 Datos NO reproducibles hoy (4 categorías)

1. Precios .BA históricos no bajados a tiempo (retroactivo yfinance limitado; ~6 tickers basura). `[DOCUMENTADO]`
2. Contraste investing manual: irreproducible sin humano (Cloudflare). `[DOCUMENTADO]`
3. Historia perdida por EXT-004/007 fue recuperable SOLO gracias al cache raw y backup prod → cualquier dato sin raw previo y ya sobrescrito es irrecuperable. `[DOCUMENTADO]`
4. Lo jamás extraído: PDFs originales CNV (solo HTML), empresas fuera del subset procesado, filings fuera de ventana sin raw previo. `[DOCUMENTADO]`

### 19.3 Minimum Reproducibility Record

Especificación completa en §24. Idea: toda métrica publicada debe llevar un registro mínimo que permita recalcularla desde cero en otra máquina/año.

### 19.4 Gaps de provenance identificados (11)

1. `accn` XBRL presente en raw, ausente en facts normalizado.
2. `decimales_xbrl` idem.
3. `es_restatement` no detectado ni persistido (un fact puede ser re-emisión).
4. Sin hash por valor (integridad fila-a-fila no demostrable).
5. Sin `parser_version`/git_commit en tablas ni exports.
6. Sin `job_id` vinculado al export final.
7. `fecha_facts` pisada: no hay histórico de descargas por empresa.
8. Respuesta HTTP no persistida (empresa inexistente vs rate-limited son indistinguibles a posteriori).
9. `motivo_descarte` incompleto para NULLs derivados (algunos flags sí existen).
10. `raw_ref` no indexado uniformemente fila→archivo HTML en CNV normalizado.
11. Vintage del deflactor IPC usado por cada CAGR no persistido por fila.

## 20. Reglas derivadas para el futuro

- Marcar/flag antes que fabricar; medir la regla antes de aplicarla. `[DOCUMENTADO]`
- Toda columna nueva de identidad/perímetro/unidad nace NOT NULL con backfill verificado por conteos.
- Toda tabla compartida entre scripts exige contrato de columnas (CONTRATO_datos.md).
- Toda auditoría empieza definiendo la expectativa esperada.
- Toda corrección manual se convierte en regla/script (nada vive solo en un Excel).

## 21. Timeline evolutivo `[DOCUMENTADO]`

| Fase | Hitos | Lecciones que dejó |
|---|---|---|
| **0. Manual** | `Seguimiento_original.xlsx` define los 13 ratios (columnas 3–15) a mano | La definición de negocio precede al pipeline |
| **1. Investigación** (`_research`, `calculos-financieros`) | Screener inicial SEC EDGAR ~553 empresas (S&P500 + ADRs LatAm) sobre catálogo 8.021; validación contra Investing (Tickets.xlsx, 99 tickers); ingeniería inversa de divergencias >10%; 16 hallazgos H01–H16 | EDGAR-GAAP reproduce Investing con error mediano ~1% en PER/EPS/margen; el bug peor fue dedup por `fy` (EXT-003) |
| **2. Tickets** (`scripts/tickets/*`) | CNV jobs 1–8 · EDGAR 01–07 · yfinance; claves canónicas v2; factor_unidad; fiscal_calendar | Unidades/perímetro/moneda son la trinidad de fallos de extracción local |
| **3. Screener s0–s9** | Capas normalización→validación; guards yfinance-only; contraste investing manual | "Marcar antes que fabricar" se vuelve doctrina |
| **4. Producción** | VPS Postgres + API FastAPI 11 endpoints | EXT-002/004 casi llegan a prod; migraciones 002/003 repararon el 2026-08-22 |
| **5. Audit v3 (hoy)** | snapshot SHA256 → b0–b9 → certificación 487/72 → traza LLM 728 filas → reporte `docs/10-auditoria-byma-pipeline-2026-08-22.md` | Certificación = consistencia interna + provenance, NO veracidad externa |

## 22. Contradicciones documentales catalogadas (14)

| # | Contradicción | Resolución |
|---|---|---|
| 1 | "SEC reporta todo USD" (ETL_PIPELINE ago-09) vs "11/13 ADR en ARS" (CONTRATO jul-14) | ✅ Evidencia favorece CONTRATO; docs viejos quedaron sin anotación de deprecación `[RECOMENDACIÓN: anotar]` |
| 2 | Tres recetas de EBITDA (06-decisiones vs METODOLOGIA vs ETL_PIPELINE) | ❌ NO RESUELTA formalmente — decidir una |
| 3 | PER = precio/EPS vs mcap/NI | ✅ Por grupo: S&P mcap/NI; BYMA precio/EPS_ttm |
| 4 | Nº de ADRs 13 / 16 / 17 según doc | ❌ Drift numérico; universo b0 (73=56+17) es la verdad actual |
| 5 | "52/56 CERTIFICADAS" (b7) vs "solo 3/20 confiables" (otra auditoría, metodología distinta) | ❌ Requiere redacción única de qué mide cada métrica de calidad |
| 6 | Tolerancia de reconciliación 8% vs 10% | ❌ Sin resolver |
| 7 | PLAN_MIGRACION_SCREENER_V2 "listo para producción" vs 07-migracion demostrándolo destructivo | ✅ Prevalece evidencia; el plan no fue anotado como inválido |
| 8 | screener_hist /v2/hist prometido vs endpoint 500 real | ✅ Hallazgo: función nunca existió |
| 9 | "cuit=cik no colisiona" vs prefijos BYMA-* no clasificables por tipo | ⚠️ Matiz válido; falta regla unificada de clasificación |
| 10 | Scraper investing Playwright (06-decisiones) vs bloqueo Cloudflare (skill/AUDITORIA) | ✅ Prevalece carga manual |
| 11 | FUENTES_DATOS_BYMA tabla principal "NO cotizan USA" vs su propia corrección interna jun-2026 (16/17 sí filean) | ✅ Resuelta dentro del propio doc; lección: actualizar tabla principal, no solo notas |
| 12 | TTM "último 10-K alcanza" (§7.3 guías) vs estrategia C canónica (§13 misma guía, versión posterior) | ✅ Prevalece la versión más nueva del mismo doc |
| 13 | Umbral payout insostenible >1× vs descarte >2× | ❌ Sin reconciliar |
| 14 | Universo 553 / 571 / 572 empresas según doc | ❌ Drift numérico heredado de fase investigación |

**Patrón detectado** `[INFERENCIA]`: las contradicciones graves nacen cuando un doc de fase antigua sigue vivo junto a uno nuevo sin marca de deprecación. El remedio barato es una línea `> DESACTUALIZADO: ver X` arriba del doc viejo.

## 23. LAS 20 REGLAS QUE NUNCA DEBEMOS VOLVER A ROMPER

1. Dedup XBRL por `end`, jamás por `fy`. (EXT-003)
2. Unidad leída por documento CNV vía `factor_unidad()`, jamás constante. (EXT-001)
3. Un solo perímetro contable por ratio (`perimetro_preferido`). (EXT-008)
4. Moneda por-fact, jamás por fuente. (EXT-025)
5. Identidad solo por clave canónica CUIT/CIK, jamás por razón social. (EXT-023)
6. `INSERT OR IGNORE` prohibido sin log de qué ignora. (EXT-002)
7. Toda migración lleva precondiciones y conteos pre/post verificados; TRUNCATE sin backup probado = prohibido. (EXT-004)
8. Tablas compartidas entre scripts exigen contrato de columnas y verificación post-run. (EXT-005)
9. Los scripts de análisis jamás escriben en producción por default. (EXT-010)
10. Re-descargas hacen MERGE incremental, nunca REPLACE con ventana. (EXT-007)
11. Cache raw = fuente de verdad; refresco por fecha explícita, nunca "si ya tengo fecha, salto". (EXT-019)
12. Descargas SEC secuenciales con User-Agent real. (§3.1)
13. Escala de shares y unidades se validan ANTES de calcular cualquier ratio per-share. (EXT-014/050)
14. Todo NULL derivado lleva flag/motivo; ante duda, NULL — nunca parche con otra fuente. (política yfinance-only)
15. Ratios pre-calculados de terceros (`CNV_*`) prohibidos sin auditar parser propio. (EXT-051)
16. Todo TTM lleva `period_ref` y usa el calendario fiscal propio, jamás diciembre asumido. (EXT-034/041)
17. Toda auditoría define expectativa esperada ANTES de ejecutarse. (EXT-036)
18. Snapshot/hash de fuentes antes de cualquier pipeline pesado. (§15)
19. Todo valor DERIVED debe poder citar sus partidas de origen o no entra al gold. (§14)
20. Toda corrección manual se convierte en script/regla esa misma semana. (§20)

## 24. MINIMUM REPRODUCIBILITY RECORD (MRR)

Registro mínimo que debe acompañar a toda métrica publicada para poder recalcularla desde cero, en otra máquina y dentro de años. `[RECOMENDACIÓN — formalizar como esquema de export]`

```yaml
mrr:
  metric_id: PER_TTM            # ratio + ventana
  entity_key: "30691421816"     # CUIT/CIK canónico
  asof_date: 2026-08-22
  formula_version: "per_ttm@v3" # id de fórmula+versión (git tag)
  inputs:                       # una entrada por partida usada
    - {table: cnv_estados_norm, concepto: "3049999", period_end: 2025-12-31,
       perimetro: I, unidad: "$", moneda: ARS, source_system: cnv,
       doc_guid: "04cfdb86-...", accn: null}
    - {table: mercado_byma, campo: mcap_ars, asof: 2026-08-22,
       source_system: yfinance, staleness_dias: 47}
  deflator_vintage: IPC_INDEC_2016-100   # si hubo deflactación
  flags: [EPS_FALLBACK_OpInc]            # todo flag que afectó el cálculo
  computed_at: 2026-08-22T03:41Z
  git_commit: "<sha>"
  snapshot_id: byma_snapshot_2026-08-22  # SHA256 certificado por snapshot_byma.py
  recompute_cmd: "python scripts/byma/b5_metricas.py --entity 30691421816"
```

Reglas del MRR: (a) si un input no puede llenar sus campos OBLIGATORIOS (§13), la métrica no se publica sin flag; (b) el MRR es generado por código, nunca escrito a mano; (c) la traza LLM (`traza_13ratios.csv`) ya implementa ~80% de esto para BYMA — generalizarla es el camino corto. `[INFERENCIA]`

## 25. Mapa documental fuente de esta base

| Grupo | Archivos clave | Aporte |
|---|---|---|
| `docs/screener` | FUENTES_DATOS_ACCIONES_ARGENTINA_BYMA · GUIA_SEC_EDGAR_PARA_DEVS · DIAGNOSTICO_INVESTING_vs_EDGAR · PROBLEMAS_ACTUALES · BITACORA_Y_DECISIONES · ESTADO_PIPELINE · ESPEC_TAGS_RATIOS · PIPELINE_CNV · PLAN_V2_DATOS_CONFIABLES | Fuentes, trampas operativas, problemas abiertos |
| `docs/proyecto` (+raíz docs) | ETL_PIPELINE_COMPLETO · METODOLOGIA_extraccion/validacion · CATALOGO_datos · CONTRATO_datos · CONCEPTOS_canonicos · AUDITORIA_investing_vs_certificado · depuracion_byma · RECONCILIACION_* · 02-jobs · 06-decisiones · 07-homologacion · 08-plan-extraccion · 09-migracion-produccion · CHANGELOG_PRODUCCION | Problemas P-01–P-23, migraciones, contrato de columnas |
| `docs/calculos-financieros/documentacion` | FORMULAS_RATIOS · SCHEMA_EXPLICADO · MAPEO_COLUMNAS · EJEMPLO_CALCULO_LOCAL · GUIA_RATIOS_EDGAR_vs_INVESTING · SCRIPT_03/04/05 · RESUMEN_FINAL_HALLAZGOS | Fórmulas exactas 13 ratios, hallazgos H01–H16 |
| Generados hoy | `docs/10-auditoria-byma-pipeline-2026-08-22.md` · `data/export_llm/README_TRAZA.md` | Estado audit v3 verificado |

---

*Fin de EXTRACTION_KNOWLEDGE_BASE.md v1. Compañero ejecutivo: DO_NOT_REPEAT.md.*

---

## 26. Changelog v2 — auditoría forense y especificación (2026-08-22)

Esta sección VERSIONA el cambio; nada anterior fue sobrescrito.

**Nuevos documentos creados** (fase especificación, sin tocar código):
- `EXTRACTION_SPECIFICATION.md` — 25 secciones (principios, fuentes+admisión, identidad, RAW, parsing, normalización, unidades, monedas, períodos, perímetros, incrementalidad, cache, rate limits, validaciones, quality gates, provenance, lineage, snapshots, reproducibilidad, publicación, no regresión, auditoría, contratos, checklist, reglas).
- `PROVENANCE_SPECIFICATION.md` — 7 tipos de huella con campos OBLIGATORIO/RECOMENDADO/OPCIONAL + MRR v2 + mapeo de los 11 gaps a fixes priorizados.
- `DATA_CONTRACT_EXTRACTION.md` — contratos por dataset (empresas, facts, ratios, precios, cnv_estados*, ratios_cnv, dividendos/suspect, 10 tablas audit v3, exports) + contrato NUEVO `download_log`.
- `EXTRACTION_CHECKLIST.md` — checklist ejecutable PRE-FLIGHT→PUBLICACIÓN con conciliación obligatoria expected→…→published.
- `DO_NOT_REPEAT.md` v1.1 — integradas reglas **EXT-NEW-001…012** (origen documentado por incidente).

**Incidentes nuevos registrados**: EXT-053 (yfinance==0.2.50 roto 77/77 tickers por cambio API Yahoo → guard de sanidad + versión fijada), EXT-054 (SEC recicló tickers GOLD/CHA a empresas distintas → revisión manual explícita). `PLAN_SCREENER_218_ACCIONES.md` marcado HISTORICAL (nunca se ejecutó como escrito — HISTORIA_EVOLUTIVA §Fase1).

**Corrección de precisión — EXT-019**: el salto "si tengo fecha_facts no bajo" aplica al path EXTRACT de `run_all.py`/`construir_base.py`; `run_update.py --quarterly` SÍ implementa incremental correcto (lastFiled por CIK, solo forms fundamentales). Riesgo residual = dos entry points con semántica distinta sobre el mismo dataset (ver SPEC §11).

**Mapa de capas completo descubierto para fase 2 (consolidación)** — generaciones coexistiendo:

| Gen | Ubicación | Rol | Solapes detectados `[INFERENCIA]` |
|---|---|---|---|
| A. screener US inicial | scripts/screener/01,02,06,07,08 | prototipo EDGAR/yfinance | solapa con B y E (ratios ×3) |
| B. tickets EDGAR | scripts/tickets/sec_edgar/scripts/* | base vigente facts/ratios/precios | — |
| C. jobs CNV | scripts/tickets/cnv/jobs/job1–8 (+_check/_audit) | extracción CNV | — |
| D. capas s0–s9 | scripts/tickets/screener/ (+run_all/run_update/run_screener) | ensamblado/validación/export vigente | s6_contraste vs carga manual investing |
| E. pipeline f* | scripts/pipeline/f1–f6, arbitro, triangulacion, fix_* | re-extracción/homologación/migración | f4_ratios duplica B; fix_* = deuda "corrección manual" |
| F. materia_prima | scripts/materia_prima/00–40 + run_etl | ETL silver con validación/certificación propios | 30_validaciones/40_certificar duplican rol b6/b7 |
| G. audit v3 | scripts/byma/snapshot+b0–b9 | certificación/traza vigente | — |
| H. deploy | deploy/sincronizar_a_produccion.py | publicación prod | swap atómico pendiente |
| I. dolares/probes | scripts/dolares/* · _probe_* | MEP/investing experimentos | probes DEPRECATED |

Candidatos de consolidación identificados (decisión de fase 2, NO eliminar ahora): ratios ×3 (A/B/E), validación-certificación ×2 (F/G), dolares vs s7c, probes. Regla: ninguna capa muere sin reemplazar su control (SPEC §1).

**Política documental aplicada** `[EXT-NEW-007]`: ACTIVE = los 6 docs de esta fase + docs/10-auditoria + OPERACION + ESPEC_TAGS_RATIOS · SUPERSEDED = PLAN_MIGRACION_SCREENER_V2 (por 09-migracion) · HISTORICAL = PLAN_SCREENER_218, guías pdfs viejas · DEPRECATED pendiente de marcar in situ: PLAN_V2 (ejecutado), PLAN_ETL_SCREENER_CNV v1, probes README.
