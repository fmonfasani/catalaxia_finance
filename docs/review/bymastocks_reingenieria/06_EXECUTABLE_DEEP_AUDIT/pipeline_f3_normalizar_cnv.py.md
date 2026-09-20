# scripts/pipeline/f3_normalizar_cnv.py — FICHA DEEP AUDIT

> FORMATO OBLIGATORIO. Cada afirmación lleva clase de evidencia:
> VERIFICADO POR CÓDIGO · VERIFICADO POR TEST · VERIFICADO POR EJECUCIÓN · NO DETERMINABLE.

CAPA →
PRIMARIA: 05_NORMALIZED (cnv_estados_v2 → fact_financials, de-acumula a period_type Q/A con unidad base ARS). [VERIFICADO POR CÓDIGO — f3_normalizar_cnv.py:3-6, :69-104]
SECUNDARIAS: 06_ECONOMIC_FACTS (reclasifica flujos y variante RECPAM en la tabla fact_financials); 10_VALIDACION (cuarentena fact_financials_cuarentena con motivos). [VERIFICADO POR CÓDIGO — f3_normalizar_cnv.py:29, :41-44, :91-94]
⚠️ ESTADO MUERTO: declarado fuente corrupta por su reemplazante y NO ejecutado por run_pipeline. [VERIFICADO POR CÓDIGO — f3b_from_reextract.py:5 "Reemplaza la fuente corrupta cnv_estados_v2"; run_pipeline.py:26-28 PASOS no lo lista]

PLANOS →
- DATOS: lee cnv_estados_v2 (concepto,period_end,valor,unidad_factor,fecha_reexpresion) filtrado por cuit desde dim_entity; escribe fact_financials (concepto_canonico,period_end,period_type Q/A,fiscal_q,valor,moneda ARS,unidad_factor,incluye_recpam,fecha_reexpresion,fuente 'cnv',source_ref 'cnv_estados_v2'/'cnv') y fact_financials_cuarentena (motivo). Crosswalk CNV→canónico X[:]. [VERIFICADO POR CÓDIGO — f3_normalizar_cnv.py:15-29, :31-45, :58-68, :115-119]
- CONTROL: idempotente DROP+CREATE (I-008) + insert or ignore; determinismo relativo a contenido de cnv_estados_v2; detectors locales es_pico (30x mediana) y valid_date() (descarta fechas no trimestrales) a cuarentena. Sin gates de salida (no verifica balance A=P+PN). [VERIFICADO POR CÓDIGO — f3_normalizar_cnv.py:48-50, :74-78, :91-94]
- EJECUCIÓN: paso de pipeline NO invocado; sin entrypoint en run_pipeline; sin retries/checkpoints. [VERIFICADO POR CÓDIGO — ausente de PASOS]
- INFRA: sqlite3; SCREENER_DB env default data/screener.db; ruta relativa al CWD. Sin red/credenciales. [VERIFICADO POR CÓDIGO — f3_normalizar_cnv.py:11]

CICLO →
- DEFINIR: contrato en docstring (silver, idempotente, RECPAM doble variante, cuarentena). [VERIFICADO POR CÓDIGO — f3_normalizar_cnv.py:3-6]
- IMPLEMENTAR: en su forma respeta 05_NORMALIZED, pero quedó obsoleto (REEMPLAZADO). [VERIFICADO POR CÓDIGO — f3b_from_reextract.py:5]
- VERIFICAR: sin tests; la cuarentena es el único control interno. [VERIFICADO POR CÓDIGO — ausencia de tests]
- CERTIFICAR: sin certificación formal; hereda el estigma de fuente corrupta declarado por su sustituto. [VERIFICADO POR CÓDIGO — f3b_from_reextract.py:5]

HOY → Existe pero está MUERTO en el pipeline: ya no se ejecuta (f3b_from_reextract tomó su rol desde cnv_reextract "consolidado limpio"). Su fuente cnv_estados_v2 está declarada corrupta. [VERIFICADO POR CÓDIGO]
[OBJETIVO] → Bajo la arquitectura oficial, fact_financials debe venir de capa 05 desde una fuente validada (cnv_reextract / raw inmutable), con identidades contables verificadas (A=P+PN) y provenance por fila; f3_normalizar_cnv es legacy superado y debe retirarse o congelarse.
[HOY] [VERIFICADO POR CÓDIGO]

DEPENDENCIAS → DB:screener.cnv_estados_v2 (FUENTE CORRUPTA); DB:screener.dim_entity; env SCREENER_DB.

CONTRATO → INPUT: cnv_estados_v2 con columnas concepto/period_end/valor/unidad_factor/fecha_reexpresion por cuit; OUTPUT: fact_financials + fact_financials_cuarentena; PRECONDICIONES: dim_entity poblada (f1 previo) y cnv_estados_v2 cargada (job5_v2); POSTCONDICIÓN: hechos Q/A con variante RECPAM doble (incluye_recpam 1/0) y outliers a cuarentena; INVARIANTES: I-008 idempotente, I-007 determinismo; PROVENANCE: I-006 PARCIAL (tiene source_ref 'cnv_estados_v2' pero no ref a fila/archivo RAW ni sha).

RIESGOS →
- Fuente cnv_estados_v2 declarada CORRUPTA por el sustituto (f3b) → escribir fact_financials desde aquí propaga dato inválido. [VERIFICADO POR CÓDIGO — f3b_from_reextract.py:5]
- Concurrencia de escritores: f3_normalizar_cnv y f3b_from_reextract DROP+CREATEAN la MISMA tabla fact_financials; si alguien corre los dos, el segundo pisa al primero (pero run_pipeline solo usa f3b). [VERIFICADO POR CÓDIGO — io_tables.csv muestra ambos escriben fact_financials with same stmt]
- Proveance parcial: no rastrea qué presentación/archivo CNV originó cada hecho (source_ref es solo el nombre de la tabla fuente). [VERIFICADO POR CÓDIGO — f3_normalizar_cnv.py:109, :113 estructura de fila]
- Los outliers (es_pico 30x, fecha no trimestral, revenue negativo) van a cuarentena SIN hardware: dependen de heurística_local, no de identidades contables. [VERIFICADO POR CÓDIGO — f3_normalizar_cnv.py:74-94]
- De-acumulación YTD→standalone con prev None: cuando falta el trimestre previo produce Q=None silenciosamente (no emite, pierde dato sin registrar). [VERIFICADO POR CÓDIGO — f3_normalizar_cnv.py:82-86]

DECISIÓN → (FASE 1: NO ejecutar nada) KEEP (retener como histórico congelado) → planificar DEPRECATE formal y/o borrado, y consolidar TODO en f3b_from_reextract con identidades contables.

EVIDENCIA →
- VERIFICADO POR CÓDIGO: f3_normalizar_cnv.py:3-6 (normaliza cnv_estados_v2); :15-45 (crosswalk + DROP+CREATE fact_financials/cuarentena); :58-68 (lectura cruda); :74-94 (outlier y de-acumulación); :115-119 (persistencia).
- VERIFICADO POR CÓDIGO: f3b_from_reextract.py:5 (declara fuente corrupta y reemplazo); run_pipeline.py:26-28 (NO está en PASOS).
- VERIFICADO POR CÓDIGO: io_tables.csv — f3_normalizar_cnv.py escribe fact_financials (misma tabla que f3b).
- NO DETERMINABLE: estado real de cnv_estados_v2 en producción (la "corrupción" está declarada por código, no verificada aquí).

ESTADO: NOT_IMPLEMENTED (en la práctica muerto: no se ejecuta; fuente corrupta; sustituido por f3b).
