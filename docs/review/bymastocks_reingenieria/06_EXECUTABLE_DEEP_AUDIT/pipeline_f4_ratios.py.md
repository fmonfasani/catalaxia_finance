# scripts/pipeline/f4_ratios.py — FICHA DEEP AUDIT

> FORMATO OBLIGATORIO. Cada afirmación lleva clase de evidencia:
> VERIFICADO POR CÓDIGO · VERIFICADO POR TEST · VERIFICADO POR EJECUCIÓN · NO DETERMINABLE.

CAPA →
PRIMARIA: 08_RATIOS (deriva fact_ratios PER/P·B/ROE/ROA/márgenes/EV-EBITDA/deuda/EBITDA desde fact_financials vía TTM+snapshot). [VERIFICADO POR CÓDIGO — f4_ratios.py:3-6, :25-36, :44-80]
SECUNDARIAS: 07_FINANCIAL_MODEL (modela TTM = suma de últimos 4 trimestres standalone); 10_VALIDACION (cruce PER/ROE vs investing, confianza alta/baja). [VERIFICADO POR CÓDIGO — f4_ratios.py:55-80, :94-117]
⚠️ NO guarda provenance de inputs: la tabla fact_ratios NO tiene columna de insumos (ni fact_key ni source_ref), a diferencia del motor canónico ratio_engine (provenance R10 obligatoria).

PLANOS →
- DATOS: lee fact_financials (concepto_canonico,period_end,valor,period_type,incluye_recpam) por entity_id; screener.precio_ars por ticker; dim_entity (grupo!='sp500'); ratios_externos (roe,per) para el cruce investing. Escribe fact_ratios (entity_id,ticker,period_end,period_type 'TTM',incluye_recpam,ratio,valor,confianza,built_at) con UNIQUE(entity_id,period_type,incluye_recpam,ratio). Monedas: ARS implícito; el precio viene de screener.precio_ars. [VERIFICADO POR CÓDIGO — f4_ratios.py:16-22, :25-40, :43, :82-84]
- CONTROL: idempotente DROP+CREATE + insert or ignore (I-008); DETERMINISMO relativo al contenido de fact_financials y screener.precio_ars; confianza 'alta'/'baja' por completitud (nrev==4) y rangos (PER 1..100); sin gate de salida. [VERIFICADO POR CÓDIGO — f4_ratios.py:14-22, :59, :80]
- EJECUCIÓN: paso 9 de run_pipeline; sin checkpoints/retries; falla total si fact_financials vacía. [VERIFICADO POR CÓDIGO — run_pipeline.py:27]
- INFRA: sqlite3; SCREENER_DB env default data/screener.db (ruta relativa). Sin red/credenciales. [VERIFICADO POR CÓDIGO — f4_ratios.py:11]

CICLO →
- DEFINIR: contrato en docstring (gold, TTM, doble RECPAM, confianza, cruce investing). [VERIFICADO POR CÓDIGO — f4_ratios.py:3-6]
- IMPLEMENTAR: respeta 08_RATIOS pero con provenance ausente — incumplimiento de I-006. [VERIFICADO POR CÓDIGO — estructura fact_ratios sin columna de inputs]
- VERIFICAR: sin tests unitarios; el cruce vs investing es el único control (externo indirecto, consola). [VERIFICADO POR CÓDIGO — f4_ratios.py:94-117]
- CERTIFICAR: no certifica formalmente; los ratios se certifican posteriormente por validar_suite (nivel screener). [NO DETERMINABLE]

HOY → Deriva fact_ratios con TTM (últimos 4 trimestres standalone, span 9-meses validado) y snapshot de balance, doble variante RECPAM (con/sin), confianza por completitud, y cruce PER/ROE vs investing en stdout. Shares derivadas NI/EPS (no de fuente de acciones) → market_cap auto-consistente en ARS. [VERIFICADO POR CÓDIGO — f4_ratios.py:25-32, :51-54]
[OBJETIVO] → Bajo la arquitectura oficial el cálculo canónico es ratio_engine/ratio_inputs (provenance R10 obligatoria, ratio_key por huella de insumos, ventana FY explícita, monedas no mezcladas F-061). f4_ratios es la variante legacy sin provenance y con TTM — debe fusionarse/deprecarse en favor del motor canónico.
[HOY] [VERIFICADO POR CÓDIGO]

DEPENDENCIAS → DB:screener.fact_financials; DB:screener.screener (precio_ars); DB:screener.dim_entity; DB:screener.ratios_externos; env SCREENER_DB.

CONTRATO → INPUT: fact_financials (Q+A, incluye_recpam), screener.precio_ars, dim_entity, ratios_externos (rosa/PER); OUTPUT: fact_ratios por (entity_id,period_type 'TTM',incluye_recpam,ratio); PRECONDICIÓN: fact_financials poblada por f3b; POSTCONDICIÓN: ratios con confianza y, para recpam=1, cruce vs investing; INVARIANTES: I-008 idempotente, I-007 determinismo; PROVENANCE: I-006 NO CUMPLIDA — fact_ratios no guarda qué facts/precio originaron cada ratio.

RIESGOS →
- Ausencia de provenance de insumos (I-006): no se puede auditar de qué hecho/periodo/precio salió cada ratio; es la diferencia central vs ratio_engine. [VERIFICADO POR CÓDIGO — fact_ratios sin columna de inputs f4_ratios.py:16-22; contraste censo ENG010 ratio_engine provenance R10]
- Shares derivadas NI/EPS en lugar de fuente de acciones: market_cap/p_p_book/p_sales heredan ese supuesto (si EPS distinto de la fuente oficial, market_cap es derivado, no observado). [VERIFICADO POR CÓDIGO — f4_ratios.py:51-54]
- TTM por suma de trimestres: span validado a 9 meses pero con descenso a -1/None si falta un trimestre → silencio de dato (len<4 devuelve None). [VERIFICADO POR CÓDIGO — f4_ratios.py:29, :31]
- El cruce vs investing usa alias BOLT_2/PATA_2 hardcodeados y umbral near() con regla ad-hoc → presión de ajuste a fuente externa no controlada. [VERIFICADO POR CÓDIGO — f4_ratios.py:97-98]
- Duplicado de función con ratio_engine.py (motor canónico) → dos implementaciones del mismo ratio con distinto rigor, riesgo de divergencia de valores. [VERIFICADO POR CÓDIGO — censo ENG010 duplicacion: f4_ratios.py]

DECISIÓN → (FASE 1: NO ejecutar nada) REVIEW. Planificar: migrar consumidores a ratio_engine (con provenance R10/F-061) y deprecar f4_ratios o añadirle provenance + fuente canónica de acciones.

EVIDENCIA →
- VERIFICADO POR CÓDIGO: f4_ratios.py:14-22 (DROP+CREATE fact_ratios sin columna inputs/provenance); :25-36 (ttm/snap); :51-54 (shares derivadas NI/EPS, market_cap); :55-80 (emit + doble RECPAM + PER); :82-84 (persistencia idempotente); :94-117 (cruce investing con alias).
- VERIFICADO POR CÓDIGO: ausencia de provenance → I-006 incompleta (contraste ratio_engine.py:22-29 provenance R10, censo ENG010).
- NO DETERMINABLE: coincidencia real del cruce investing (usa datos externos no verificados aquí).

ESTADO: PASS_WITH_WARNINGS (funciona e idempotente, pero sin provenance de insumos y duplicado del motor canónico).
