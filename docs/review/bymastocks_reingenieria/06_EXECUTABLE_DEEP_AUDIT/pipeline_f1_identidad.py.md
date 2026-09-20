# scripts/pipeline/f1_identidad.py — FICHA DEEP AUDIT

> FORMATO OBLIGATORIO. Cada afirmación lleva clase de evidencia:
> VERIFICADO POR CÓDIGO · VERIFICADO POR TEST · VERIFICADO POR EJECUCIÓN · NO DETERMINABLE.

CAPA →
PRIMARIA: 02_IDENTIDAD (construye identidad canónica dim_entity/dim_instrument). [VERIFICADO POR CÓDIGO — f1_identidad.py:17-38 crea dim_entity y dim_instrument]
SECUNDARIAS: 01_FUENTES (lee screener/adr_ratios/empresas/fiscal_calendar/mapa_entidades); 12_PUBLICACION (el reporte de cobertura imprime gaps). NO clasifica compañías más allá de es_financiera derivado de sector. [VERIFICADO POR CÓDIGO — f1_identidad.py:43-54 fuente, :60-75 lectura]

PLANOS →
- DATOS: lee screener (cuit/ticker/grupo/es_financiera/sector), adr_ratios (cik ADR, ratio), empresas (fiscal_year_end/moneda/nombre), fiscal_calendar (fy AR), mapa_entidades (nombre primario). Escribe dim_entity (cuit/cik/ticker_canonico UNIQUE/nombre/grupo/moneda_funcional/fy_end_month/es_financiera) y dim_instrument (ticker/mercado/tipo/moneda/ratio). Unidad de identidad = ticker_canonico; moneda funcional ARS/USD; puente cuit/cik/ticker. [VERIFICADO POR CÓDIGO — f1_identidad.py:15-38]
- CONTROL: idempotente vía DROP+CREATE (I-008) + insert or ignore; DETERMINISMO: derivado de fuente fija (no network, no reloj salvo nada); unico punto de verdad de identidad dentro del medallion SQLite. NO hay validación de consistencia (un CUIT sin fy pasa a 12 por default, f1_identidad.py:56 default). [VERIFICADO POR CÓDIGO — f1_identidad.py:15-39 DROP+CREATE; :56 mes() default fye None]
- EJECUCIÓN: entrypoint de paso dentro de run_pipeline (paso 1); sin checkpoints/retries/provenance de corrida; falla total si la DB no tiene las tablas fuente. [VERIFICADO POR CÓDIGO — ejecutado por run_pipeline.py:41]
- INFRA: sqlite3 directo; DB vía SCREENER_DB env con default "screener.db" relativo a data/ (ruta relativa al CWD: si se corre desde otro directorio, abre/crea otra DB — fragilidad). Sin red, sin credenciales. [VERIFICADO POR CÓDIGO — f1_identidad.py:12]

CICLO →
- DEFINIR: contrato implícito en docstring (medallion/silver, idempotente). Sin spec formal. [VERIFICADO POR CÓDIGO — f1_identidad.py:3-8]
- IMPLEMENTAR: respeta capa 02_IDENTIDAD (no calcula ratios; solo arma entidad/instrumento). [VERIFICADO POR CÓDIGO]
- VERIFICAR: sin tests de unidad para la lógica de puente; la cobertura se reporta como stdout (gaps AR sin fy, ADR sin cik). [VERIFICADO POR CÓDIGO — f1_identidad.py:110-114]
- CERTIFICAR: sin certificación formal; es pre-condición no certificada del pipeline. [NO DETERMINABLE — no hay evidencia de certificación]
- OBSERVACIÓN DE CAPA: decide es_financiera derivando del sector (clasificación semántica) dentro de una etapa de IDENTIDAD → mezcla 02_IDENTIDAD con CLASIFICACIÓN. [VERIFICADO POR CÓDIGO — f1_identidad.py:62]

HOY → Reconstruye dim_entity/dim_instrument (DROP+CREATE) resolviendo el puente cuit/cik/ticker desde fuentes medallion old y reporta cobertura en stdout. Corre como paso 1 del pipeline y también se conoce como "s01_identity" en el engine de forma DUPLICADA. [VERIFICADO POR CÓDIGO — censo EXISTE duplicado: scripts/engine/s01_identity.py y identity_v1; este es la variante SQLite]
[OBJETIVO] → Degradar a fuente legacy: la identidad canónica de la arquitectura es identity_v1 (engine, con assertion/evidence/puente G5 y prohibición de decidir en silencio). Este script hereda bugs conocidos (p.ej. el caso BMA no resuelto, ver f024_bma.py) y decide es_financiera por heurística.
[HOY] [VERIFICADO POR CÓDIGO]

DEPENDENCIAS → DB:screener.screener; DB:screener.adr_ratios; DB:screener.empresas; DB:screener.fiscal_calendar; DB:screener.mapa_entidades; env SCREENER_DB.

CONTRATO → INPUT: screener/adr_ratios/empresas/fiscal_calendar/mapa_entidades (tablas fuente ya pobladas); OUTPUT: dim_entity + dim_instrument; PRECONDICIONES: tablas fuente existentes; POSTCONDICIÓN: 2 tablas reconstruidas, cada entidad con ticker_canonico UNIQUE y grupo válido (CHECK grupo IN byma_only/adr/sp500); INVARIANTES: I-008 (DROP+CREATE idempotente), I-001 RAW no aplica (no toca RAW); PROVENANCE: I-006 AUSENTE (no registra de qué fuente/fila salió cada dim_entity — no hay source_ref/sha).

RIESGOS →
- No registra provenance de identidad (I-006): no se puede rastrear de qué fila fuente salió cada entidad. [VERIFICADO POR CÓDIGO — tabla dim_entity sin columna source_ref, f1_identidad.py:17-27]
- Mezcla capa CLASIFICACIÓN con IDENTIDAD: es_financiera derivada por string "financ" en sector. [VERIFICADO POR CÓDIGO — f1_identidad.py:62]
- Ruta relativa data/screener.db: depende del CWD (rompe determinismo de ejecución si se corre desde otro dir). [VERIFICADO POR CÓDIGO — f1_identidad.py:12]
- Duplicado de dominio con identity_v1/s01_identity: dos implementaciones del mismo puente sin fusión → riesgo de divergencia. [VERIFICADO POR CÓDIGO — censo ENG017 y CER001; este script coexiste]
- default fy=12 silencioso para AR sin fiscal year (puede fabricar período equivocado). [VERIFICADO POR CÓDIGO — f1_identidad.py:56, :73]

DECISIÓN → (FASE 1: NO ejecutar nada) REVIEW. Planificar: convergencia hacia identity_v1; documentar/eliminar el default de fy y el fallback por sector; añadir provenance de fila fuente.

EVIDENCIA →
- VERIFICADO POR CÓDIGO: f1_identidad.py:12 (DB env+default relativo); :15-39 (DROP+CREATE dim_entity/dim_instrument); :43-54 (fuentes adr/fcal/emp/nombre); :60-75 (leer screener, esfin derivada de sector :62); :77-96 (insert or ignore); :110-114 (reporte de gaps).
- VERIFICADO POR CÓDIGO: ausencia de source_ref en dim_entity → I-006 no presente.
- NO DETERMINABLE: cobertura real de coherencia del puente (sin test).

ESTADO: PASS_WITH_WARNINGS (funciona e idempotente, pero sin provenance, mezcla clasificación, y duplicado del dominio).
