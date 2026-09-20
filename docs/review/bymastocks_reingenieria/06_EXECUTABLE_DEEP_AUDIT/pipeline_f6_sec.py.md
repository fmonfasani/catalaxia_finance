# scripts/pipeline/f6_sec.py — FICHA DEEP AUDIT

> FORMATO OBLIGATORIO. Cada afirmación lleva clase de evidencia:
> VERIFICADO POR CÓDIGO · VERIFICADO POR TEST · VERIFICADO POR EJECUCIÓN · NO DETERMINABLE.

CAPA →
PRIMARIA: 08_RATIOS. [VERIFICADO POR CÓDIGO — calcula ratios anuales desde la tabla `facts` SEC]  
SECUNDARIAS: 05_NORMALIZED (lee `facts` pre-normalizado); 11_CERTIFICACION (asigna nivel propio); 12_PUBLICACION (inserta directo en `screener_gold`, la tabla de producto). No hay capa de VALIDACIÓN separada (la certificación vive adentro).

PLANOS →
- DATOS: lee `dim_entity` (cik/grupo), `screener` (precio/mcap/sector), `facts` (conceptos), `cnv_reextract` (ROE anual CNV para ADR); escribe `screener_gold` (DELETE+INSERT). [VERIFICADO POR CÓDIGO — f6_sec.py:50-53, 64, 68, 132-138]
- CONTROL: S/N: guard sanitización SANE (f6_sec.py:19-26), cross-check market cap 2 fuentes (f6_sec.py:94-98), identidad A=P+PN (f6_sec.py:114-117), triangulación ADR (f6_sec.py:120-124). NO: checkpoints, gates, manejo de error, log de ingesta, provenance de insumos.
- EJECUCIÓN: script plano sin `main_guard` (se ejecuta en import); sin retries, sin timeouts, sin manejo de excepciones. [VERIFICADO POR CÓDIGO — ausencia; conserva `if __name__` ausente] Idempotente vía DELETE previo (f6_sec.py:64). [VERIFICADO POR CÓDIGO]
- INFRA: SQLite local `data/screener.db` vía env SCREENER_DB (f6_sec.py:14). Sin red directa (los datos SEC ya están en `facts`). [VERIFICADO POR CÓDIGO]

CICLO →
- DEFINIR: contrato de salida = 38 columnas de `screener_gold` (f6_sec.py:132-138). [VERIFICADO POR CÓDIGO]
- IMPLEMENTAR: calcula ratios + certifica + publica en un único paso (ver RIESGOS 2/3). [VERIFICADO POR CÓDIGO]
- VERIFICAR: solo self-check de legibilidad (identidad, mcap) dentro del script; sin tests unitarios/contrato. [VERIFICADO POR CÓDIGO — ausencia en repo]
- CERTIFICAR: autodeclara niveles 'CERTIFICADO-SEC'/'triangulado-SEC'/'SEC-ok' sin certificación formal externa ni registro. [NO DETERMINABLE]

HOY → Integra las 499 US (sp500) + ADR desde `facts` a `screener_gold` en APPEND: selecciona el anual más reciente (span 350-380d), calcula ratios (ROE/ROA/márgenes/PER/P-B/P-S/EV/EBITDA/Deuda-EBITDA), calcula market cap (derivado precio×shares para US, o NI/EPS×precio/CCL para ADR) e imprime su propio nivel de certificación por fila. [VERIFICADO POR CÓDIGO — f6_sec.py:64-138]
[OBJETIVO] → Separar responsabilidades: una etapa consume `facts` normalizado y produce `fact_ratios`/hechos anuales CON provenance (fact_key/source_ref, I-006/I-007); una etapa de VALIDACIÓN (10) cruza contra `validar_suite_edgar` u otra certificación; y una etapa independiente escribe `screener_gold`. El script hoy combina RATIOS+CERTIFICACIÓN+PUBLICACIÓN en uno.
[HOY] [VERIFICADO POR CÓDIGO]

DEPENDENCIAS → DB:screener.facts (pre-normalizado, sin sha/accession por fila); DB:screener.dim_entity (cik→grupo); DB:screener.screener (precio/mcap); DB:screener.cnv_reextract (ROE CNV triangulación); env:SCREENER_DB. Corre DESPUÉS de f5 en `run_pipeline` (f6_sec.py:9). [VERIFICADO POR CÓDIGO/CENSO]

CONTRATO →
- INPUT: filas de `facts` por CIK (concepto, period_start/end, val, filed, unit), `dim_entity` (grupo sp500/adr, cik, cuit, fy_end_month).
- OUTPUT: INSERT en `screener_gold` (38 columnas) para grupo in ('sp500','adr'); nivel_certificacion, mcap_confiable, flagged.
- PRECONDICIONES: `dim_entity` poblada con cik; `facts` cargada (construir_base previo); `screener` con precios.
- POSTCONDICIONES: `screener_gold` contiene las filas sp500/adr con ratios anuales y sello.
- INVARIANTES: I-001 RAW inmutable (NO aplica: lee `facts` derivada, no RAW); I-006 PROVENANCE (AUSENTE: no guarda origen filing/accession/sha); I-007 DETERMINISMO (sí: selección determinista anual/stock por order desc fecha); I-008 IDEMPOTENCIA (sí: DELETE propio previo f6_sec.py:64). [VERIFICADO POR CÓDIGO]
- PROVENANCE: AUSENTE — lee `facts` sin fact_key/source_fact_ids/sha y no persiste derivación. [VERIFICADO POR CÓDIGO — f6_sec.py:68-71]

RIESGOS →
1. RATIOS+CERTIFICACIÓN+PUBLICACIÓN en un solo script: una etapa de VALIDACIÓN (10) inexistente; el mismo proceso que calcula decide su propio sello (P0). [VERIFICADO POR CÓDIGO — f6_sec.py:114-138 / CENSO PIP011]
2. Sin provenance de insumos (I-006): ratios no reconstruibles hasta el filing/sha; certificación no auditable de origen (P0). [VERIFICADO POR CÓDIGO — f6_sec.py:68-71]
3. Determinismo parcial: en ADR, `mc = sh*precio_ars` o `/ccl` según `eq_unit` (f6_sec.py:84-92) — decisión de moneda por una sola fila `facts`; un cambio de unit altera la conversión (P1). [VERIFICADO POR CÓDIGO — f6_sec.py:84-92]
4. `eps` puede ser None y cae al guard `sane` (f6_sec.py:131) pero `ni/eps` para shares en ADR (f6_sec.py:86) puede dividir por cero/None sin protección explícita si `eps` falsy → `sh=None` (protegido por condicion, pero PER usa `ni>0` y mcap con equity, no eps). Sin manejo de error: si una consulta falla, excepción cruda. (P2). [VERIFICADO POR CÓDIGO — f6_sec.py:86-113]
5. Sin checkpoints ni gates: si falla a mitad, deja `screener_gold` sin las filas sp500/adr (el DELETE+INSERT no es transaccional a nivel fila: solo `con.commit()` al final f6_sec.py:140). (P1). [VERIFICADO POR CÓDIGO — f6_sec.py:140]
6. No hay flujo de errores/retry para `facts` incompleta: empresa con cik pero sin `facts` se salta en silencio (`continue`, f6_sec.py:75) sin registro de por qué. (P2). [VERIFICADO POR CÓDIGO]

DECISIÓN → (FASE 1: NO EJECUTAR NADA) **REVIEW** (censo: REWRITE). Acción a planificar: separar cálculo de ratios (08, con provenance), validación/certificación (10/11, contra `validar_suite_edgar`) y publicación (12) en etapas independientes; persistir provenance de insumos.

EVIDENCIA →
- VERIFICADO POR CÓDIGO: f6_sec.py:19-26 (SANE); :50-53 (lee dim_entity/screener); :64 (delete propio, idempotencia); :68-71 (lee facts sin provenance); :94-98 (mcap 2 fuentes); :114-124 (identidad + triangulación); :132-138 (insert 38 columnas screener_gold); :140 (single commit).
- VERIFICADO POR EJECUCIÓN: CENSO PIP011 reporta corrida real (integra sp500+ADR, niveles).
- NO DETERMINABLE: existencia de certificación formal externa a f6_sec; coverage real tras cada corrida.

ESTADO: **DECISION_REQUIRED** (REWRITE planificado — P0 legitimidad de sello y P0 provenance sin resolver).
