# scripts/pipeline/validar_suite.py — FICHA DEEP AUDIT

> FORMATO OBLIGATORIO. Cada afirmación lleva clase de evidencia:
> VERIFICADO POR CÓDIGO · VERIFICADO POR TEST · VERIFICADO POR EJECUCIÓN · NO DETERMINABLE.

CAPA →
PRIMARIA: 10_VALIDACION. [VERIFICADO POR CÓDIGO — corre ~18 cruces independientes por empresa]  
SECUNDARIAS: 11_CERTIFICACION (asigna nivel CERTIFICADO/alto/interno-ok/REVISAR y escribe `screener_nivel`); 04_PARSED (valida sobre datos ya extraídos de CNV); 08_RATIOS (recalcula ROE/márgenes para contrastar). Accede a CNV vía `cnv_reextract` (capa 05_NORMALIZED). [VERIFICADO POR CÓDIGO]

PLANOS →
- DATOS: lee `dim_entity` (grupo byma_only/cuit), `cnv_reextract` (conceptos por cuit), `screener` (MarketCapUSD), `market_cap_derivado` (mcap cold/derivado), `eerr_externos` (revenue investing), `ratios_externos` (roe investing); escribe `validacion_suite` y `screener_nivel` (DROP+CREATE+INSERT). [VERIFICADO POR CÓDIGO — validar_suite.py:18-30, 98-102]
- CONTROL: 4 capas de checks (1 identidades internas, 2 continuidad temporal, 3 externa investing, 4 ancla de mercado) con regla de certificación (validar_suite.py:3-6); tolerancias `rel_ok`/`sign_ok` (validar_suite.py:11-13). NO: gates formales, log de path decisorio por fila completo, manejo de excepciones.
- EJECUCIÓN: script plano sin `main_guard`; idempotente por DROP+CREATE previos (validar_suite.py:28, 98). Determinista (misma entrada → mismo nivel). Sin retries ni timeouts. [VERIFICADO POR CÓDIGO]
- INFRA: SQLite local vía env SCREENER_DB (validar_suite.py:10). Sin red (usa tablas ya cargadas, p.ej. `eerr_externos`/`ratios_externos` de investing con carga manual previa). [VERIFICADO POR CÓDIGO]

CICLO →
- DEFINIR: regla explícita en docstring: pasa TODAS identidades internas aplicables + continuidad + ≥1 ancla independiente (validar_suite.py:5-6). [VERIFICADO POR CÓDIGO]
- IMPLEMENTAR: valida + certifica en el mismo script (ver RIESGOS 1). Persiste el nivel en `screener_nivel` como «fuente única para el screener_gold» (validar_suite.py:98-102).
- VERIFICAR: sin tests unitarios de las funciones de check en repo; el "qué falla" se imprime por empresa (validar_suite.py:110-113) pero no se testea contra un fixture. [VERIFICADO POR CÓDIGO — ausencia]
- CERTIFICAR: emite sello (11) con la regla privada dentro del script; no hay certificación independiente de este certificador (autocertificación del universo byma). [NO DETERMINABLE]

HOY → Recorre las 56 byma_only, arma ~18 checks por empresa en 4 capas, calcula el nivel (CERTIFICADO/alto/interno-ok/REVISAR) y lo persiste en `validacion_suite` (detalle) y `screener_nivel` (nivel por ticker consumido por f5). NO cubre el universo EDGAR (sp500+ADR): eso está en `validar_suite_edgar.py`, separado. [VERIFICADO POR CÓDIGO — validar_suite.py:30-102]
[OBJETIVO] → Separar VALIDACIÓN (10: emitir checks y su detalle en `validacion_suite`) de CERTIFICACIÓN (11: que un proceso/gate con regla formal e independiente derive `screener_nivel`) y dejar TESTs que fijen la regla de bind (qué combos de checks dan cada nivel). HOY ambos viven en el mismo script con la regla como lógica privada.
[HOY] [VERIFICADO POR CÓDIGO]

DEPENDENCIAS → DB:screener.cnv_reextract (dataset principal); DB:screener.dim_entity (universo byma_only); DB:screener.screener + market_cap_derivado (anclas); DB:screener.eerr_externos + ratios_externos (investing, carga manual previa); env:SCREENER_DB. Consumido por f5_screener (screener_nivel → screener_gold). [VERIFICADO POR CÓDIGO/CENSO — f5_screener.py:96-97]

CONTRATO →
- INPUT: filas de `cnv_reextract` por cuit (conceptos: revenue..cash, cnv_roe/roa/margen), `dim_entity` (grupo byma_only, fy_end_month, es_financiera), mcap externo, eerr/ratios externos investing.
- OUTPUT: `validacion_suite` (ticker, check_id, capa, resultado OK/FAIL/NA, detalle) y `screener_nivel` (ticker, es_financiera, nivel, checks_ok, checks_aplicables, fallidos).
- PRECONDICIONES: `cnv_reextract` poblada (f2/batch+fixes previos); `screener` y `market_cap_derivado` con anclas; `eerr_externos`/`ratios_externos` cargadas (investing manual).
- POSTCONDICIONES: `screener_nivel` con el nivel por ticker byma_only (fuente única del sello).
- INVARIANTES: I-001 RAW inmutable (NO aplica: lee derivada); I-006 PROVENANCE (PARCIAL: registra check ids/fallidos pero no sha/origen de los valores contrastados); I-007 DETERMINISMO (sí: checks deterministas sobre tablas estables); I-008 IDEMPOTENCIA (sí: DROP+CREATE). [VERIFICADO POR CÓDIGO]

RIESGOS →
1. VALIDACIÓN y CERTIFICACIÓN en el mismo script: la regla de nivel es lógica privada (validar_suite.py:85-95) sin gate/certificador independiente ni test que la fije; quien valida decide el sello (P0). [VERIFICADO POR CÓDIGO — validar_suite.py:85-95]
2. Autocertificación de un solo universo: certifica byma_only con sus propias tablas CNV; el sello de salida no contrasta contra el universo EDGAR ni contra una certificación externa a la suite (P1). [VERIFICADO POR CÓDIGO]
3. Checks con hard exclusions y NA-skip: c5/c6/c8/c10 marcados «informativos» y excluidos de las identidades duras (validar_suite.py:83-84); un dato ausente (NA) nunca bloquea; la cobertura efectiva de "identidades duras" depende de cuántos valores existan (P1). [VERIFICADO POR CÓDIGO — validar_suite.py:83-91]
4. `market_cap_derivado` se lee en `try/except OperationalError: pass` (validar_suite.py:19-22): si la tabla no existe, se cae silenciosamente a mcap de `screener` sin marcarlo; las anclas pueden estar huérfanas (P1). [VERIFICADO POR CÓDIGO]
5. Identidad por alias hardcodeada BOLT/PATA (validar_suite.py:27): duplica el fix de identidad de `fix_mapeo`; si el universo renombra cambia la clave de cruce (P2). [VERIFICADO POR CÓDIGO]
6. Sin manejo de errores ni checkpoint: DROP+CREATE no son transaccionales; si falla a mitad, `validacion_suite` puede quedar truncada sin rollback, y no hay registro forense de path (P2). [VERIFICADO POR CÓDIGO — validar_suite.py:28]

DECISIÓN → (FASE 1: NO EJECUTAR NADA) **KEEP** (censo: KEEP) con revisión de la separación validación/certificación. Acción a planificar: extraer regla de nivel a un gate/checker con tests que fijen el bind de checks→nivel; no caer silencioso si `market_cap_derivado` falta; documentar NA-skip.

EVIDENCIA →
- VERIFICADO POR CÓDIGO: validar_suite.py:11-13 (rel_ok/sign_ok tolerancias); :19-22 (fallback silencioso mcap); :27 (alias hardcodeado); :28 (DROP+CREATE validacion_suite); :30 (universo byma_only); :45-77 (checks c1..c17 en 4 capas); :83-95 (regla de nivel); :98-102 (screener_nivel fuente única); :110-113 (impresión de fallidos).
- VERIFICADO POR EJECUCIÓN: CENSO PIP025 (suite corre y emite niveles; consumido por f5_screener:96-97).
- NO DETERMINABLE: test automatizado de la regla bind checks→nivel; certificación independiente del propio suite.

ESTADO: **PASS_WITH_WARNINGS** (valida de verdad; riesgo P0 de autocertificación + exclusions NA).

