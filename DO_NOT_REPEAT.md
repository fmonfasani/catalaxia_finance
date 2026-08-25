# DO_NOT_REPEAT.md

**Lista normativa de errores ya cometidos y jamás repetibles — Catalaxia Finance**
Derivada de EXTRACTION_KNOWLEDGE_BASE.md §23 (evidencia completa ahí). Última actualización: 2026-08-22.

> **Changelog v1.1 (2026-08-22):** se INTEGRAN (sin reemplazar nada) las reglas EXT-NEW-001…012 derivadas de la auditoría de no-regresión y provenance (ver `EXTRACTION_SPECIFICATION.md` §25). Incidentes nuevos registrados en KB: EXT-053 (yfinance 0.2.50 roto 100% por cambio de API Yahoo), EXT-054 (tickers SEC reciclados GOLD/CHA).

| # | Regla | Violación original |
|---|---|---|
| 1 | Dedup XBRL SIEMPRE por `end`, jamás por `fy` (fy = año del filing) | EXT-003: MRK perdía historia comparativa |
| 2 | Unidad CNV se lee por documento con `factor_unidad()`; nunca constante | EXT-001: MILES/Millones, staleness masivo |
| 3 | Un solo perímetro contable por ratio (`perimetro_preferido`) | EXT-008: NI individual ÷ Revenue consolidado en HAVA/GCLA/GARO |
| 4 | Moneda por-fact; "SEC=USD" está PROHIBIDO como supuesto | EXT-025: 11/13 ADR reportan en ARS |
| 5 | Identidad solo por clave canónica CUIT/CIK; jamás por razón social | EXT-023: ADRs rotos por splits de nombre |
| 6 | `INSERT OR IGNORE` sin log de descartes = prohibido | EXT-002: 13,7% de documentos mutilados en silencio |
| 7 | Toda migración: precondiciones + conteos pre/post; TRUNCATE sin backup probado = prohibido | EXT-004: migración destructiva aprobada en papel |
| 8 | Tablas compartidas exigen contrato de columnas y verificación post-run | EXT-005: regresión borraba columnas `per` |
| 9 | Análisis jamás escribe en producción por default; entornos separados | EXT-010: SCREENER_DB faltante apuntaba a prod |
| 10 | Re-descarga hace MERGE incremental; REPLACE con ventana = prohibido | EXT-007: ventana 6 años borró 1.483 filas |
| 11 | Cache raw = fuente de verdad; refresco por fecha explícita, nunca "si tengo fecha salto" | EXT-019: cache eterno oculta filings nuevos |
| 12 | SEC secuencial + User-Agent real (nombre+email); nunca paralelo | §3.1: HTTP 403 verificado |
| 13 | Escala de shares/unidades validada ANTES de cualquier ratio per-share | EXT-014/050: NMR ×10⁶; DGCE ×1000 |
| 14 | Todo NULL lleva flag/motivo; ante duda NULL, nunca parche cross-fuente | Política yfinance-only |
| 15 | Ratios pre-calculados de terceros (`CNV_*`) prohibidos sin auditar parser propio | EXT-051: margen TXAR era solvencia |
| 16 | TTM con `period_ref` y calendario fiscal propio; diciembre asumido = bug garantizado | EXT-034/041: 8 empresas no-calendario |
| 17 | Auditoría define expectativa esperada ANTES de ejecutar | EXT-036: falsos huecos reportados |
| 18 | Snapshot/hash de fuentes antes de pipeline pesado | Filosofía snapshot SHA256 (b0) |
| 19 | DERIVED sin lineage citable no entra al gold | §14: "¿de qué partidas saliste?" |
| 20 | Corrección manual → script/regla esa misma semana, o se pierde | §20 doctrina del proyecto |

**Señales de alarma temprana** (cualquiera de estas = detener y auditar):
- Conteo de filas cambia sin explicación tras una carga.
- Un ratio cambia >10% entre corridas sin cambio de datos subyacente.
- Un valor cabe en la columna pero su magnitud es absurdamente distinta a la serie (×10, ×1000).
- Un doc viejo contradice al nuevo y ninguno tiene marca de deprecación.

---

## Reglas EXT-NEW (v1.1 — integradas de EXTRACTION_SPECIFICATION.md §25)

| ID | Regla | Incidente que la originó |
|---|---|---|
| EXT-NEW-001 | La huella nace en el dato crudo y viaja con él hasta la publicación; no se construye solo para el ratio final | 11 gaps de provenance (accn/decimales/parser_version perdidos entre capas) |
| EXT-NEW-002 | Identidad ≠ Clasificación: columnas separadas, jamás inferidas una de otra | EXT-006 precios cruzados + prefijos BYMA-* no clasificables |
| EXT-NEW-003 | Tres planos temporales separados y validados automáticamente: dato / fuente / pipeline | fecha_facts pisada (EXT-019), ultimo_periodo falso (EXT-037) |
| EXT-NEW-004 | El conteo nunca es validación suficiente: columnas, valores, NULLs, hashes, distribución | EXT-002 ("84k filas consistentes" con 13,7% docs mutilados), EXT-004 |
| EXT-NEW-005 | Toda corrección registrada: raw_value+rule+reason+corrected_value+at+by. Jamás corrección silenciosa | Reparación EXT-007 (posible solo por raw cache); correcciones manuales históricas |
| EXT-NEW-006 | Fuente secundaria jamás parchea un primario faltante; contraste conserva ambos valores + diferencia | Rol de investing manual / IAMC / Comafi |
| EXT-NEW-007 | Al publicar doc nuevo, el viejo se marca DEPRECATED/SUPERSEDED en su primera línea | Contradicciones #7 (migración destructiva aprobada en papel) y #11 |
| EXT-NEW-008 | Toda corrida concilia expected→downloaded→parsed→rejected→normalized→derived→published, con explicación por brecha | EXT-036 falsos huecos; whitelist job5 630/2.145 silenciosa |
| EXT-NEW-009 | Estándar de admisión bloqueante para fuentes nuevas (12 requisitos, SPEC §2.2) | BYVA/TIKR descartadas, scraping investing fallido, TipoDeDocumento ausente |
| EXT-NEW-010 | Investigar anomalías SOLO con taxonomía A–E (fuente/extractor/normalización/cálculo/publicación); no mezclar niveles | Confusiones recurrentes diagnosticando PER_2PATH, NIC-29, TXAR |
| EXT-NEW-011 | Dependencia externa puede romperse sin aviso: versión fijada + guard de sanidad antes de aceptar datos | EXT-053: yfinance==0.2.50 falló 77/77 tickers por cambio de API de Yahoo |
| EXT-NEW-012 | Mapping ticker→CIK exige revisión manual explícita ante discrepancia; ticker jamás es identidad | EXT-054: GOLD y CHA reciclados por SEC a empresas distintas |

**Segunda señal de alarma agregada**: script "terminó sin excepción" pero cobertura cayó (ver EXTRACTION_CHECKLIST.md FASE 5).
