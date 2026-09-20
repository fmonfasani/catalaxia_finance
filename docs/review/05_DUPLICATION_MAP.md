# 05 — Duplication Map REAL

**Relevamiento global — Paso 5.** Mapa de duplicación SEMÁNTICA (no nominal) cruzando 01+02+03+04 con inspección directa. Cada afirmación lleva `[VERIFICADO POR CÓDIGO]`, `[VERIFICADO POR TEST]`, `[VERIFICADO POR EJECUCIÓN]` o `[NO-DETERMINABLE]`. Este documento NO es un DELETE PLAN: no se decide eliminación, merge ni reemplazo.

Regla: NOMBRE SIMILAR ≠ CÓDIGO SIMILAR ≠ FUNCIÓN SIMILAR ≠ DATOS EQUIVALENTES ≠ RESPONSABILIDAD DUPLICADA ≠ SUSTITUIBLES. D3/D4/D5 requieren evidencia. "Duplicado" no es sinónimo de "redundante".

---

## 1. Resumen

- **Duplicación semántica confirmada (D3) en 2 grupos**: identidad (`identity.*` vs `identity_v1.*`, mismo concepto "quién es este emisor", sin bridge) y hechos económicos SQLite-vs-PG (`facts` vs `derived.fact`, con `fact_financials` como tercera vía CNV-legacy).
- **Duplicación de pipeline (D5) con diferencias reales**: P-SCR-UPDATE vs P-SCR-ALL vs P-SCR-SCREENER generan el mismo `screener` pero con distinto alcance (subset 72 + incremental vs universo + flags vs phases por import) y distinto assemble (rebuild omite `s9_guards_yfinance`, run_all lo incluye) — equivalencia parcial, no sustitución directa.
- **Cuatro motores de ratios sobre cuatro dominios distintos** (D2 parcial, no D3): `calcular_ratios_base` (facts SQLite), `ratio_engine` (derived.fact + market PG), `f4_ratios` (fact_financials legacy), `s2_ratios_cnv` (cnv_estados_norm). Mismo concepto, distinta fuente y distinta salida → complementarios por dominio (D8), no equivalentes.
- **Lo que parecía duplicado y no lo es** (§22): RAW vs PARSED, identidad vs instrumento vs símbolo, validación vs certificación, cálculo de ratio vs materialización, `screener` vs `screener_gold` (producto vs legacy sin lector), `ingesta_log` vs `ingest_log` (mecanismo vs diagnóstico).
- **FX sin duplicación real**: `dolarito_cotizaciones` (histórico crudo, API autenticada) vs `dolares` (curada de referencia, 2 escritores) son capas distintas (D8); la conversión ARS→USD vive dispersa (byma/b4 con flags de mezcla temporal, `_mep.py`, `s3_precios`) sin motor central — hueco, no duplicación.

## 2. Criterio de duplicación

| Código | Significado | Barra de evidencia |
|---|---|---|
| D0 | NO DUPLICADO | — |
| D1 | SIMILITUD NOMINAL (solo nombre) | código inspeccionado |
| D2 | DUPLICACIÓN FUNCIONAL PARCIAL (solapa en parte) | inputs/outputs comparados |
| D3 | DUPLICACIÓN SEMÁNTICA (mismo concepto, distinta implementación) | concepto + productor + consumidor + capa demostrados |
| D4 | DUPLICACIÓN DE DATOS (mismo dato en dos stores) | escritores/lectores y contenido comparados |
| D5 | DUPLICACIÓN DE PIPELINE (mismo output por otro camino) | orden + inputs + outputs comparados |
| D6 | DUPLICACIÓN DE PUBLICACIÓN (mismo destino por dos vías) | destino y mecanismo comparados |
| D7 | LEGACY/PARALELO (generación anterior conviviendo) | caller productivo ausente + vía vigente identificada |
| D8 | COMPLEMENTARIO (parte distinta del mismo todo) | función diferenciada demostrada |
| D9 | NO-DETERMINABLE | evidencia insuficiente (no es "muerto") |

Sustituibilidad (§20): S0 NO SUSTITUIBLE · S1 PARCIAL · S2 CON ADAPTACIÓN · S3 POTENCIALMENTE SUSTITUIBLE · S4 NO-DETERMINABLE. Es input del Paso 7, no decisión.

## 3. Clasificación

Se aplica D0–D9 + S0–S4 a cada grupo de las §4–§18. La matriz principal (§19) consolida; los falsos duplicados van a §22 (no se mezclan con D3–D6).

## 4. Componentes similares

### 4.1 Orquestadores (run_all / run_update / run_screener / run_pipeline / e2e_orchestrator)

| A | B | Responsabilidad | Equivalencia | Clasificación |
|---|---|---|---|---|
| run_all | run_update rebuild | generar `screener`+export | mismo output, distinto alcance/orden (subset+incremental vs universo; rebuild omite s9) | D5 con diferencias (§10) |
| run_all | run_screener | generar `screener`+export | mismo output; CNV por subprocess vs todo por `__import__` | D5 con diferencias |
| run_update | run_pipeline | pipeline completo | distinto output (`screener` vs `screener_gold`), distinto store-uso, distinta época | D7 (legacy/paralelo), no D5 |
| e2e_orchestrator | run_all | orquestar cadena | distinto dominio (PG-SEC-YPF vs SQLite-multi-fuente), distinto producto | D0 (distinta responsabilidad) |
| e2e_orchestrator | run_pipeline | orquestar por subprocess | mismo mecanismo, distinto dominio/época | D1/D7 (similitud mecánica, no semántica) |

### 4.2 Publicadores (s5 / sync / migrate / publicar_v2)

| A | B | Equivalencia | Clasificación |
|---|---|---|---|
| sincronizar_a_produccion | migrate_sqlite_to_pg | ambos SQLite→PG; sync cubre 7 tablas en reemplazo, migrate copia TODAS en TRUNCATE+swap (solapa en las 7) | D6 parcial (solape real en 7 tablas) + D8 (migrate es único camino a `screener`) |
| publicar_screener_v2 | migrate | distinta tabla destino (`screener_v2` vs `screener`) | D8 (complementarios), no D6 |
| s5_exportar | sync/migrate | distinto destino (CSV fs vs PG) | D8 |
| materia_prima sync | sincronizar_a_produccion | materia_prima PRODUCE (silver/validaciones), sync TRANSPORTA — confusión nominal posible | D0 (producir ≠ transportar) |

### 4.3 Reportes (StageReport vs dict legacy de s04)

- `engine.report.StageReport` (usado por s00–s03, c3, c11) vs dict `report` legacy en s04 (persistido directo a `stage_runs.report`) `[CÓDIGO]`. Misma responsabilidad (reporte de etapa), distinto contrato → **D2** (duplicación funcional parcial del mecanismo de reporte). No es D3: el contenido cumple el mismo contrato C10 (`code{git_commit,parser_version,script}` tras el fix).

### 4.4 `engine/s03.py` vs `s03_parse_ypf.py`

- `engine/s03.py` (librería, importa xbrlparse+fetch) sin ningún import desde scripts; `s03_parse_ypf.py` importa `engine.xbrlparse` directo `[CÓDIGO]`. No hay dos implementaciones vivas en uso → **D0** (no duplicación; un módulo sin consumidor, ver 03 §16).

## 5. Datos duplicados (panorama)

Detalle por dominio en §6–§9. Anticipos: identidad D3; hechos D3/D4 según par; ratios D2+D8 (no D3 global); publicación D6 parcial + D8 + un legacy huérfano.

## 6. Identity

`identity.*` (v0) vs `identity_v1.*` (v1) — **D3 DUPLICACIÓN SEMÁNTICA** `[CÓDIGO]`:

| Dimensión | v0 (`identity.*`) | v1 (`identity_v1.*`) |
|---|---|---|
| Concepto | quién es este emisor (entidad + identificadores) | el mismo |
| Claves | entity/identifier (SEC catalog, tickers solo en identifiers) | entity_key opaco, identifier, instrument, instrument_symbol |
| Autoridad | s01_identity (writer único) | convención append-only (múltiples writers) |
| Provenance | parcial (sin assertions) | assertions/reviews/conflicts + bridges CIK↔LEI |
| Escritores | s01 | c3_identity_link, backfills, pilots, f024 |
| Consumidores | s03 (`resolve_por_cik`) | c3_validation, benches, f024 |
| Bridge v0↔v1 | **no existe** | **no existe** |

¿Equivalentes? Representan el mismo concepto real con distinta granularidad (v1 separa instrumento/símbolo/bridge; v0 no). ¿Coexistencia legítima? v1 gobierna CNV, v0 gobierna SEC-motor; ningún consumidor cruza. Clasificación: D3 confirmada, coexistencia operativa actual, sustituibilidad S4 (requiere Paso 7). `empresas` (SQLite, 4 escritores) es una tercera materialización de identidad CNV/EDGAR sin autoridad → D4 parcial con ambas (mismo CUIT/CIK, sin sincronización).

## 7. Economic Facts

| Par | Misma fuente | Misma granularidad | Misma provenance | Consumidor común | Clasificación |
|---|---|---|---|---|---|
| derived.fact (PG) vs facts (SQLite) | sí (EDGAR) | no (fact XBRL con contexto/unidad vs fila por concepto/CIK) | no (completa vs parcial) | no (ratio_engine vs calcular_ratios) | D3 (mismo concepto, distinta etapa: C5/C6-motor vs C6-sqlite) |
| facts vs fact_financials | no (EDGAR vs CNV) | no | no | no | D1/D0 (distinta fuente; solo nombre "fact" en común) |
| fact_financials vs derived.fact | no (CNV vs SEC) | no | no | no | D0 (distinto dominio) |
| demo.db:fact_q vs cualquiera | no (sandbox) | — | — | no | D0 (demo aislado) |

Conclusión: la única D3 real es `derived.fact`↔`facts` (mismo hecho SEC en dos stores). `fact_financials` no duplica a ninguno (es la vía CNV-legacy). Distintas etapas: RAW-SEC→parsed→derived (motor) vs companyfacts→facts (sqlite) son dos cadenas de refinamiento paralelas, no la misma etapa repetida.

## 8. Ratios

Motores (cálculo):

| Motor | Fuente | Salida | Consumidor |
|---|---|---|---|
| calcular_ratios_base | facts+empresas (SQLite) | ratios (DROP+recreate, cik PK) | s4, s6..s9 |
| ratio_engine | derived.fact + market_price_daily (PG) | derived.ratio | [NO-DET] |
| f4_ratios | fact_financials (SQLite) | fact_ratios | [NO-DET] |
| s2_ratios_cnv | cnv_estados_norm + fiscal_calendar (SQLite) | ratios_cnv | s4 |

Mismo concepto ("ratio por emisor/período"), cuatro dominios disjuntos (SEC-sqlite, SEC-PG+market, CNV-legacy, CNV-canónico) → **D2 parcial entre calcular_ratios_base y s2_ratios_cnv** (ambos alimentan `s4`; el resto D8 por dominio). No es D3 global: fuentes, granularidad (cik vs cuit, con/sin IPC-CAGR) y consumidores difieren.

Materializaciones (tablas): `adr_ratios` (ratio oficial 20-F, fuente externa — D8), `cedear_ratios` (CEDEARs — D8), `screener_ratios(_hist)` (histórico publicado — D8), `ratios_ttm`/`per_ttm` (ventana TTM — D8), `ratios_externos` (externos legacy — D7). Ninguna duplica a `ratios`: son cortes distintos (fuente/ventana/historial). Cálculo vs materialización son responsabilidades distintas en todos los casos (ver §22).

## 9. Publication

| Objeto | Rol real | Llega al usuario | Clasificación |
|---|---|---|---|
| screener (SQLite) | staging canónico del ensamble | indirecto (vía s5/sync-lectura) | producto-staging |
| screener_gold (SQLite) | staging del pipeline legacy | no (sin lector) | LEGACY huérfano (D7), no duplica a `screener` en uso |
| screener_hist (PG) | histórico servido por api | sí | producto (writer ND — hueco, no duplicación) |
| screener_v2 (PG) | publicado por publicar_v2 | no (api no lo lee) | publicado-sin-lector (D8 respecto de `screener`, no D6: distinta tabla) |
| silver_norm (SQLite→PG) | normalizado validado | sí (api) | producto (cadena completa) |
| screener_export.csv/.json | export validado por s5 | artefacto en disco (lector ND) | EXPORT |

D6 real solo en: sync-PLAN ↔ migrate (solape en 7 tablas PG, §4.2). `screener` vs `screener_gold` es D7 (no D3): mismo nombre de familia, distinta época, y solo uno tiene lector.

## 10. Pipelines

P-SCR-UPDATE vs P-SCR-ALL vs P-SCR-SCREENER — **D5 con diferencias** (no equivalencia total) `[CÓDIGO]`:

| Dimensión | UPDATE-rebuild | ALL | SCREENER |
|---|---|---|---|
| Inputs CNV | subset 72 cuits (job2→5_v2) | universo job1→7 | (usa lo ya extraído; sin subprocess CNV) |
| Inputs EDGAR | incremental (lastFiled vs fecha_facts) | full + cache/flags | (usa lo ya construido) |
| Assemble | s0,s2,s3,s4,s6,s7,s8,s5 (**omite s9**) | s0,s2,s3,s4,s6,s7,s8,s9,s5 | s0,s2,s3,s4,s6,s7,s8,s5 |
| Output | `screener` + export | `screener` + export | `screener` + export |
| Consumidor | mismo (s5/sync) | mismo | mismo |
| Schedule | cron quarterly | manual | manual |

Mismo output nominal, distinto alcance y un paso de diferencia (s9 guards yfinance). Sustituibilidad S1 (parcial): ALL puede regenerar lo de UPDATE en universo completo, pero no replica el incremental subset. e2e_orchestrator vs run_pipeline: D0 (§4.1).

## 11. CNV

Por función (ingestión/parsing/normalización/validación/extracción/publicación):

| Función | MOTOR (c3) | JOBS (v2) | LEGACY (v1/serie 01..07) | Pilotos |
|---|---|---|---|---|
| Ingestión | CNV API → RawStore + fetch_raw.cnv_* | job2_download → RAW fs | 30_descargar_eeff, extract_*_masivo | cnv_pilot2 |
| Parsing | validate + manifest | job3_formtype, job5_v2_extract | job5_extract (v1) | — |
| Normalización | (no normaliza a estados; preserva RAW) | job4_clasificar → cnv_estados | serie 20.x formtypes | — |
| Validación | checkpoint/idempotencia `007` | job7_validar (DELETE suspects) | auditorías 01/03 | cnv_validation_* |
| Extracción | (vía jobs) | job5_v2/job6_v2 | job5/job6 v1 | — |
| Publicación | (no publica) | (vía assemble) | — | — |

Duplicaciones: job5 v1 vs v2 y job6 v1 vs v2 — misma CLI, mismas tablas destino, solo v2 invocada por caminos productivos → **D7** (v1 paralela sin caller productivo; riesgo D4 si ambas corrieran). MOTOR vs JOBS: **D8** (motor preserva RAW con provenance PG; jobs extraen a SQLite para el producto) — no D3: distinto output y consumidor. LEGACY serie 01..07 vs jobs: D7 (auditorías/descargas previas a jobs v2).

## 12. SEC

- E2E PG (s00→s04, golden YPF) vs SQLite (`construir_base`→facts→ratios): mismo origen (EDGAR), distinto store, distinta granularidad, distinto consumidor → **D2 parcial** (solapan en "hechos SEC materializados") con D8 por cadena (la PG tiene C9/C11; la SQLite alimenta el producto).
- YPF-specific (s01/s02/s03 golden) vs genérico (s04/ratio_engine/c11): **D0** — no son dos implementaciones de lo mismo sino alcance distinto (golden case vs arquitectura con `--cik`/`--run-id`).
- `construir_catalogo` vs `construir_base`: ambos escriben `empresas` (el primero con DROP) → **D4** (mismo dato, dos writers, §16 riesgo).
- e1_adr_xbrl (análisis XBRL de hechos posteriores, research) vs sec_adr_ratios (ratio oficial 20-F productivo): **D8** (investigación vs producción).

## 13. Market

Mapa por rol (no confundir INSTRUMENTO/SÍMBOLO/PRECIO/FX/EMISOR):

| Objeto/componente | Rol | Clasificación vs parecidos |
|---|---|---|
| market_raw_files/runs | RAW Yahoo versionado | D0 vs precios (fuente, no consumo) |
| market_price_daily | canónico market PG | D8 vs `precios` (SQLite screener): distinto store/consumidor; mismo concepto → D2 parcial nominal, no D3 (ver abajo) |
| market_snapshots | snapshot por corrida (m2) | D8 (foto, no serie) |
| market_instruments | instrumento canónico PG | D0 vs símbolos |
| market_symbol_mappings | mapeo símbolo→instrumento (+venue f014) | D8 vs instruments (mapeo ≠ entidad) |
| dim_instrument (SQLite) | instrumento legacy del pipeline | D2 parcial vs market_instruments (m1 lo lee para mapear) |
| precios (SQLite) | precio de producto (yfinance directo) | D2 parcial vs market_price_daily: mismo concepto, distinta cadena (producto usa yfinance, no market_*) — coexistencia sin sincronización |
| precios_diarios | histórico diario (s3b) | D8 vs precios (serie vs foto) |
| m1/m2/m4/m5 | mapeo/fetch/calidad/golden | D0 entre sí (etapas distintas) |
| s3_precios / precios_y_valuacion | precios del producto (subset CNV / universo + valuación) | D2 (ambos escriben `precios` por yfinance; distinto alcance) |

## 14. Multimoneda / FX

Solo relevamiento (no implementar):

| Objeto | Qué representa | Productor | Consumidor |
|---|---|---|---|
| dolarito_cotizaciones | histórico crudo MEP/CCL/oficial (fecha, compra/venta, ts_ms) | dolares/fetch_dolarito_historico (API autenticada, `DOLARITO_AUTH_CLIENT`) | byma/b4 (MEP pareado/estimado), validar_suite_edgar, screener/_mep |
| dolares | curada de referencia (fecha,tipo,valor,cruce,fuente,es_referencia) | actualizar_dolares + materia_prima/10b (2 writers, INSERT OR REPLACE) | sync PLAN, valuaciones |
| ipc_nacional.csv | índice INDEC (no FX, insumo de CAGR real) | run_update monthly (datos.gob.ar) | s2 (CAGR), recompute_ttm |

¿Duplicación? `dolarito_cotizaciones` vs `dolares`: **D8** (crudo histórico vs curada de referencia; el DDL de materia_prima lo declara así). Conversión ARS→USD: dispersa en byma/b4 (`precio_usd`, `mep_pareado`, `mezcla_temporal`), `_mep.py` (cobertura desde 2018-10-29), `s3_precios` (+FX subset) — **sin motor central**: hueco de arquitectura (D0, falta información: fuente oficial por fila en `dolares` es `fuente`, sin contrato verificado). CCL/oficial: columnas/tipos nominales sin productor verificado → D9.

## 15. Provenance

Mecanismos comparados:

| Mecanismo | Dominio | Equivale a | Clasificación |
|---|---|---|---|
| run_id + stage_runs + checkpoints | motor PG | — (único con idempotencia transaccional) | base (D0) |
| hashes (sha256/canonical, hashout, fact_key, ratio_key) | transversal | entre sí por función | D8 (cada uno en su capa: archivo, fila, ratio) |
| manifests (cnv_artifact, _run_manifest) | CNV / FASE 4 | stage_runs del motor | D2 (misma función, distinto dominio) |
| ingesta_log (mecanismo) | screener/EDGAR | checkpoints del motor | D2 (misma función, sin transacción) |
| ingest_log (diagnóstico) | demo/CNV-meta | ingesta_log | D1 (nombre parecido, función distinta) |
| upd_*.log + outputs/docs | corridas screener | manifests | D8 (log humano vs manifest máquina) |
| validaciones/certificacion_nueva | materia_prima | certifications c11 | D2 (certificación por dominio; solo la segunda alimenta api vía sync) |

Ningún mecanismo reemplaza a otro globalmente: son capas complementarias por dominio (D8) con dos solapes funcionales (D2).

## 16. Validation / Certification

VALIDACIÓN ≠ CERTIFICACIÓN (evidencia por mecanismo):

| Mecanismo | Qué hace | Dónde registra | Es certificación |
|---|---|---|---|
| gates s00–s04/c3 (`assert_transition`) | bloquea avance de etapa | stage_runs/checkpoints | no (es C10) |
| job7_validar | limpia suspects CNV | cnv_estados(_suspect) | no |
| m4_quality / m5_golden | calidad market + caso dorado | market_data_quality / XLSX | no |
| validacion_suite(_edgar), gate_roe, o2_* | suites por dominio | tablas suite | no (bloqueo real ND) |
| 30_validaciones (9 cruces) | valida silver_norm | validaciones | no (insumo de certificación) |
| c11 → engine.certifications | certifica corrida | certifications + boletín | **sí (C11 motor)** |
| 40_certificar → certificacion_nueva | certifica período | certificacion_nueva → sync → PG | **sí (C11 materia_prima)** |

Equivalencias: job7≈m4≈suites por función (validar en su dominio) → D2 entre validadores del mismo nivel, D8 entre niveles. c11 vs 40_certificar: D2 (dos certificadores por dominio; solo el segundo llega a publicación).

## 17. Capas

| Caso | Evaluación |
|---|---|
| s03 (parse + gates + lectura identidad) | RESPONSABILIDAD MEZCLADA (C4+C10+C2-lectura) documentada, sin duplicación |
| s04 (normalize + stage_runs + hashout) | RESPONSABILIDAD MEZCLADA (C5+C9) documentada |
| run_all/run_update (EXTRACT→EXPORT en un ejecutor) | RESPONSABILIDAD MEZCLADA por diseño (orquestador, no duplicación) |
| s0 (normaliza CNV) vs s2 (ratios CNV) vs s4 (ensambla) | SEPARACIÓN CORRECTA (C5/C8/C7) |
| c11 vs 40_certificar (dos C11) | DUPLICACIÓN D2 por dominio (no mezcla) |
| StageReport vs dict s04 | D2 del mecanismo (misma capa C9) |
| calcular_ratios_base (lee facts + escribe ratios) | SEPARACIÓN CORRECTA (C8 puro) |

## 18. Planos

- CONTROL: checkpoints/stage_runs (motor) vs manifests/logs (screener) → D2 funcional, D8 por dominio; ningún controlador duplica a otro globalmente.
- EJECUCIÓN: subprocess (e2e, run_pipeline, jobs CNV) vs `__import__` (run_all/run_screener/rebuild) → D2 del mecanismo de ejecución con trade-off documentado (aislamiento vs velocidad); no son sustituibles 1:1 sin cambiar contratos (S2 como máximo).
- DATOS: ver §6–§9.
- INFRAESTRUCTURA: `.env`+engine.config (motor) vs `SCREENER_DB`+paths relativos (screener) vs guarda F-001 (market) → D8 (tres regímenes de config, sin solape).

## 19. Matriz de duplicaciones

| Grupo | Componentes | Concepto | Tipo | Equivalencia | Diferencia | Owner | Producto | Provenance | Estado | Evidencia |
|---|---|---|---|---|---|---|---|---|---|---|
| G1 | identity.* vs identity_v1.* | quién es el emisor | D3 | mismo concepto | granularidad, autoridad, consumidores | dividido | motor (ambos) | v1 completa | ambos vigentes | [CÓDIGO] |
| G2 | derived.fact vs facts | hecho SEC | D3 | mismo origen | granularidad, store, provenance | s04 / construir_base | motor / screener | completa / parcial | ambos vigentes | [CÓDIGO] |
| G3 | UPDATE vs ALL vs SCREENER | generar screener | D5 | mismo output nominal | alcance, s9, mecanismo CNV | cron / manual | sí (UPDATE) | parcial | vigentes | [CÓDIGO]+[EJECUCIÓN] |
| G4 | 4 motores de ratios | ratio por emisor | D2+D8 | concepto | fuente, salida, consumidor | 4 owners | parcial (2/4) | mixta | vigentes | [CÓDIGO] |
| G5 | sync PLAN vs migrate | SQLite→PG | D6 parcial | 7 tablas solapadas | resto de tablas, mecanismo | deploy | sí | ausente | vigentes | [CÓDIGO] |
| G6 | job5/6 v1 vs v2 | extracción CNV | D7 | misma CLI/tablas | solo v2 en caminos productivos | jobs | vía v2 | manifest | v1 paralela | [CÓDIGO] |
| G7 | screener vs screener_gold | ensamble | D7 | nombre de familia | época, lector (uno huérfano) | run_all / pipeline | solo screener | parcial / ausente | gold legacy | [CÓDIGO] |
| G8 | market_price_daily vs precios | precio | D2 parcial | concepto | cadena (market_* vs yfinance), consumidor | m2 / precios_y_val | motor / screener | parcial | vigentes | [CÓDIGO] |
| G9 | c11 vs 40_certificar | certificación | D2 | función | dominio, llegada a publicación | c11 / materia_prima | solo 2ª | completa / cadena | vigentes | [CÓDIGO] |
| G10 | StageReport vs dict s04 | reporte etapa | D2 | contrato C10 | mecanismo | engine.report / s04 | motor | completa | vigentes | [CÓDIGO] |
| G11 | construir_base vs construir_catalogo | empresas | D4 | misma tabla | DROP vs incremental | — | base | parcial | catalogo legacy-riesgo | [CÓDIGO] |
| G12 | s3_precios vs precios_y_valuacion | precios producto | D2 | misma tabla, misma fuente | alcance (subset vs universo+valuación) | s3 / sec_edgar | sí | parcial | vigentes | [CÓDIGO] |
| G13 | dolarito_cotizaciones vs dolares | FX | D8 | dominio | crudo vs curada | dolares/ / materia_prima | vía valuación | parcial | vigentes | [CÓDIGO] |
| G14 | subprocess vs __import__ | ejecución | D2 | lanzar etapas | aislamiento, cwd, velocidad | orquestadores | — | logs | vigentes | [CÓDIGO] |
| G15 | e2e_orchestrator vs run_pipeline | orquestar | D1/D7 | mecanismo | dominio, época, producto | engine / legacy | e2e parcial | completa / ausente | pipeline legacy | [CÓDIGO]+[TEST] |
| G16 | ingesta_log vs ingest_log | log de ingesta | D1 | nombre | mecanismo vs diagnóstico | _raw_inmutable / varios | auditoría | sí (es prov.) | vigentes | [CÓDIGO] |
| G17 | publicar_v2 vs migrate | publicar a PG | D8 | destino PG | distinta tabla | publicar / deploy | no / parcial | ausente | vigentes | [CÓDIGO] |
| G18 | e1_adr_xbrl vs sec_adr_ratios | ADR | D8 | dominio ADR | research vs producción | — / sec_edgar | solo 2º | parcial | vigentes | [CÓDIGO] |

## 20. Matriz de sustituibilidad

| Grupo | A → B | Clase | Por qué |
|---|---|---|---|
| G1 | v0 → v1 (o inversa) | S4 | distinta granularidad/consumidores; sin bridge; requiere Paso 7 |
| G2 | facts → derived.fact (o inversa) | S4 | distinta granularidad/provenance/consumidores |
| G3 | ALL → UPDATE-rebuild | S1 | regenera output en universo completo pero pierde incremental-subset y schedule |
| G3 | SCREENER → UPDATE-rebuild | S1 | mismo output; pierde subprocess-aislado de CNV |
| G4 | cualquiera → otro motor | S0 | dominios disjuntos (fuente/salida/consumidor distintos) |
| G5 | migrate → sync (7 tablas) | S1 | sync cubre las 7 con reemplazo; no cubre el resto ni `screener` |
| G5 | sync → migrate | S0 | migrate es único camino a PG `screener`; mecanismos incompatibles (reemplazo vs swap) |
| G6 | v1 → v2 | S3 | misma CLI/tablas; v2 ya es la vía vigente (sustitución de hecho en caminos productivos) |
| G7 | gold → screener | S0 | gold sin lector ni schedule; screener es el producto |
| G8 | precios → market_price_daily | S0 | el producto consume yfinance, no market_* |
| G9 | c11 → 40_certificar | S0 | dominios y consumidores distintos |
| G10 | dict s04 → StageReport | S3 | mismo contrato C10; cambio mecánico acotado (no se hace en este paso) |
| G11 | catalogo → base | S3 | base ya es la vía productiva; catalogo con DROP es riesgo |
| G12 | s3_precios → precios_y_valuacion | S1 | cubre universo+valuación; pierde foco subset-CN |
| G14 | __import__ → subprocess | S2 | requiere aislar cwd/env por etapa (jobs CNV lo exigen) |

## 21. Conflictos

| # | Conflicto | Clasificación |
|---|---|---|
| 1 | G1: dos autoridades de identidad sin bridge | CONFIRMADO |
| 2 | G2: mismo hecho SEC en dos stores sin sincronización | CONFIRMADO |
| 3 | G11: dos writers de `empresas` (uno con DROP) | CONFIRMADO (riesgo de pisada) |
| 4 | G5: dos publicadores SQLite→PG solapados en 7 tablas | CONFIRMADO (solape de escritura) |
| 5 | G3: tres generadores de `screener` (divergencia de alcance s9/subset) | RIESGO |
| 6 | G12+G8: tres escritores/cadenas de precio (`precios` ×2 + `market_price_daily`) | RIESGO |
| 7 | G6: v1/v2 escriben mismas tablas si ambas corrieran | RIESGO (latente; v1 sin caller productivo) |
| 8 | G9: dos certificaciones, solo una llega a publicación | RIESGO (barrera incompleta, ver 04 §17) |

## 22. Falsos duplicados

**COMPONENTES QUE PARECEN DUPLICADOS PERO NO LO SON** (con evidencia):

1. RAW vs PARSED (`fetch_raw`/`RAW fs` vs `parsed.*`/`cnv_estados`): etapas distintas con transformación XBRL/clasificación en el medio `[CÓDIGO]`.
2. IDENTIDAD vs INSTRUMENTO vs SÍMBOLO (v1: entity vs instrument vs instrument_symbol): niveles distintos del modelo; f024/benches los tratan por separado `[CÓDIGO]`.
3. VALIDACIÓN vs CERTIFICACIÓN (job7/m4/suites vs c11/40_certificar): solo los segundos emiten objetos de certificación consumibles `[CÓDIGO]`.
4. MARKET RAW vs MARKET PRICE (raw_files vs price_daily): fuente versionada vs serie canónica derivada por m2 `[CÓDIGO]`.
5. Cálculo vs materialización de ratio (funciones `calcular_*` vs tablas `ratios*`): responsabilidades distintas; cada motor tiene ambas `[CÓDIGO]`.
6. `screener` vs `screener_gold`: producto vigente vs legacy sin lector — coexistencia nominal, no equivalencia `[CÓDIGO]`.
7. Producir vs transportar (materia_prima vs sincronizar): confusión nominal posible; funciones disjuntas `[CÓDIGO]`.
8. `construir_base` vs `construir_catalogo` como "builders EDGAR": el segundo es catálogo legacy con DROP; no son dos implementaciones vigentes `[CÓDIGO]`.
9. `api` vs exports (CSV): dos superficies de producto distintas (HTTP vs archivo), no dos publicaciones de lo mismo `[CÓDIGO]`.

## 23. NO-DETERMINABLE

- Si `ratios` (SQLite) y `derived.ratio` (PG) coinciden numéricamente para el mismo CIK (comparación no ejecutada).
- Si P-SCR-ALL y P-SCR-SCREENER producen byte-equivalencia con UPDATE-rebuild (no comparado).
- Contenido/fuente de CCL y oficial por fila en `dolares` (tipos nominales sin productor verificado).
- Si job5/6 v1 se ejecutaron alguna vez en este entorno.
- Si `screener_export.csv` y PG `screener` contienen las mismas filas (export vs migrate no comparados).
- Alcance real de `e1_adr_xbrl` (research vs uso puntual).

## 24. Evidencia

- `[VERIFICADO POR CÓDIGO]`: comparación semántica de motores (fuentes/salidas en §8), Tablas G1–G18, CLI v1/v2 idéntica, PLAN sync vs migrate, FX (fetch_dolarito_historico:14/44/77, b4_mercado:50-116, _mep.py:24/45), GOLDEN vs genérico (04 §3), rebuild vs assemble (run_update:589-623).
- `[VERIFICADO POR TEST]`: e2e (26), f050/f054/f055 (42), market tests — fijan contratos, no equivalencias.
- `[VERIFICADO POR EJECUCIÓN]`: logs quarterly, artefactos fase_s04/export/DBs; ninguna comparación numérica A-vs-B ejecutada (ver §23).
- `[NO-DETERMINABLE]`: §23 + celdas marcadas.

## 25. Conteos finales

- Grupos de duplicación: 18 (G1–G18).
- Duplicaciones confirmadas: D3 ×2 (G1, G2) · D4 ×1 (G11) · D5 ×1 (G3) · D6 ×1 (G5 parcial) · D2 ×7 (G4, G8, G9, G10, G12, G14, +validadores §16) · D7 ×3 (G6, G7, G15) · D1 ×2 (G15-parte, G16).
- Duplicaciones parciales (D2): 7 grupos.
- Pipelines duplicados: 1 grupo D5 (3 caminos, con diferencias).
- Datos duplicados: D3 ×2, D4 ×1, D2 ×3 (precios, ratios-motores, provenance-mecanismos).
- Falsos duplicados: 9 (§22). Complementarios (D8): 6 (G4-parte, G13, G17, G18, FX-interno, provenance-niveles).
- Sustituibilidad: S0 ×5 · S1 ×4 · S2 ×1 · S3 ×3 · S4 ×2 (§20).
- Conflictos: 8 (4 confirmados, 4 riesgos).
- NO-DETERMINABLE: 6 ítems.
- Principales hallazgos: §1 (5 bullets). Evidencia: §24.