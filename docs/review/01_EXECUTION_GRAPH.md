# 01 — Grafo de ejecución REAL del repositorio

**Relevamiento global — Paso 1.** Documenta el grafo real de ejecución del proyecto completo, con clasificación por nodo y evidencia. Las afirmaciones se marcan con uno de: `[VERIFICADO POR CÓDIGO]`, `[VERIFICADO POR TEST]`, `[VERIFICADO POR EJECUCIÓN]`, `[NO-DETERMINABLE]`.

Este documento es un **índice y grafo de ejecución**, no un plan de acción. No contiene decisiones de borrado/movimiento/refactor (no aplican reglas de mutación). El censo `catalaxia_censo_py_master.csv` (616 filas) se usó solo como índice de existencia; su columna de decisión NO se utilizó como evidencia.

---

## 1. Resumen

- El repositorio contiene **890 archivos `.py`** en todo el árbol. La lógica de negocio vive en `scripts` (483), con paquete reutilizable `engine/` raíz (10 módulos: `config, db, fetch, hashout, identity, identity_v1, report, s03, states, xbrlparse`) + `api/main.py` (1) + `scripts/deploy` (1).
- Mecánica global verificada: **208 archivos** con `if __name__ == "__main__"`, **158** con `def main(`, **56** con `argparse`. Eso define la población de *invocables potenciales*.
- Existen **tres familias de pipelines** que convergen en los mismos artefactos finales:
  1. **Motor SEC-EDGAR** (`scripts/engine`): cadena canónica `s00 → s01 → s02 → s03 → s04` orquestada por `e2e_orchestrator.py`, más fetch CNV en motor (`c3_cnv_fetch.py`) y capas de calidad (`c11_certificar.py`, `ratio_engine.py`).
  2. **Screener CNV** (`scripts/tickets`): dos ensambles de FASE 4 que compiten — `run_all.py` (canónico, moldea subprocess a `cnv/jobs`) y `run_screener.py` (phases por `__import__`) — más `run_update.py` de FASE 3 que es el **cron productivo**.
  3. **Pipeline consolidado legacy** (`scripts/pipeline`): 14 pasos orquestados por `run_pipeline.py` (y `e2e_ticker.py`), que converge al mismo `data/screener_export.csv`.
- **Convergencia de escritura principal**: `data/screener.db` (SQLite) recibe escrituras de las tres familias. `engine.checkpoints` (PostgreSQL) es el punto convergente del motor `s00–s04 + c3`.
- **Divergencia documentación↔código detectada**: los runbooks referencian `python scripts/engine/c4_cnv_adapter.py`, pero **ese archivo no existe** en el árbol `[NO-DETERMINABLE]` (ver sección 13).

---

## 2. Grafo global

```
[CRON prod: /etc/cron.d/catalaxia]
   │ run_update.py --daily/--monthly/--quarterly/--annual   [CÓDIGO: setup_vps.sh]
   ▼
run_update.py ──► EDGAR (construir_base/calcular_ratios_base/_caducidad)
      ├──► CNV subprocess: job2_download → job3_formtype → job4_clasificar → job5_v2_extract_eeff
      └──► rebuild: s0 → … → s8 → s5   ──► data/screener_export.csv

run_all.py (FASE 4, canónico manual)
   EXTRACT ► construir_base + CNV job1…job7 + sec_adr_ratios
   TRANSFORM ► calcular_ratios_base + precios_y_valuacion  (siempre juntos)
   ASSEMBLE ► s0→s2→s3→s4→s6→s7→s8→s9
   EXPORT ► s5 → data/screener_export.csv

e2e_orchestrator.py (E2E_orchestrator, SEC)
   s00_smoke → s01_identity → s02_fetch_ypf → s03_parse_ypf → s04_normalize
      │   c/u: engine.checkpoints → engine.stage_runs(report en s04) → derived.fact
      ▼
c11_certificar.py  (C10/C11, lee stage_runs + derived.fact)
ratio_engine.py    (--persist → derived.ratio)
      ▼
[publicación] s5_exportar → data/screener_export.[csv|json]
   → sincronizar_a_produccion.py → PostgreSQL prod (screener/screener_hist)
   → api/main.py (SOLO lectura)

[legacy] run_pipeline.py → f1_identidad, fix_mapeo, f2_reextract_batch, f2_adr,
   fix_escala_anchor, fix_single_doc, fix_manual, f3b_from_reextract, f4_ratios,
   fix_escala_mcap, gate_autoreporte, validar_suite, f5_screener, f6_sec

[market] m2_fetch_engine → market_raw_{files,runs} → m4_quality → market_data_quality
   → m5_golden_case → market_price_daily → m19_apply_schema / m6_scale

[CNV motor] c3_cnv_fetch.py → fetch_raw.cnv_{download_log,artifact,presentation}
   + engine.checkpoints
```

---

## 3. Pipelines productivos demostrados

| # | Pipeline | Nodos | Evidencia |
|---|----------|-------|-----------|
| P1 | **SEC EDGAR E2E orquestado** | `e2e_orchestrator.py` → s00 → s01 → s02 → s03 → s04 → `c11_certificar` | `[VERIFICADO POR TEST]` `test_e2e_orchestrator.py` (26 passed junto a `test_c11_contract.py`); `[VERIFICADO POR EJECUCIÓN]` `docs/review/R4_E2E_ORCHESTRATOR_EVIDENCIA.md` |
| P2 | **Screener FASE 3 productivo (cron)** | `run_update.py` (--daily --monthly --quarterly --annual) | `[VERIFICADO POR CÓDIGO]` `scripts/setup_vps.sh:127-151` (cron.d) + run_update |
| P3 | **Screener FASE 4 canónico** | `run_all.py` (EXTRACT→TRANSFORM→ASSEMBLE→EXPORT) | `[VERIFICADO POR CÓDIGO]` run_all.py (CNV_JOBS, flags) |
| P4 | **CNV E2E motor** | `c3_cnv_fetch.py` (Discovery→Fetch→RAW→Manifest→Provenance→Checkpoint) | `[VERIFICADO POR CÓDIGO]` c3_cnv_fetch.py; `[VERIFICADO POR EJECUCIÓN]` runbook 03_CNV_E2E_RUNBOOK |
| P5 | **Market E2E** | `m2_fetch_engine` → `m4_quality` → `m5_golden_case` (+`m19_apply_schema`, `m6_scale`) | `[VERIFICADO POR CÓDIGO]` escrituras market_raw_runs/market_price_daily/market_data_quality |
| P6 | **Ratio engine** | `ratio_engine.py --persist` → `derived.ratio` | `[VERIFICADO POR CÓDIGO]` ratio_engine.py (F-061, insumos vía ratio_inputs.sql_insumos) |
| P7 | **Publicación** | `s5_exportar` → `sincronizar_a_produccion.py` → `api/main.py` | `[VERIFICADO POR CÓDIGO]` s5_exportar (OUT data/screener_export.csv), sincronizar_a_produccion (sin TRUNCATE ciego), api (lee screener/screener_hist) |
| P8 | **Recalculo por emisor (calidad)** | `reparse_universo.py` (F-054, 8 CIKS) y `e2e_producto.py` (SOLO LECTURA, muestra 8 tickers → outputs/docs/fase_*) | `[VERIFICADO POR CÓDIGO]` ambos scripts; `[VERIFICADO POR EJECUCIÓN]` artefactos en outputs/docs/fase_producto, fase_ratios |

## 4. Pipelines alternativos

| # | Pipeline | Relación con el principal | Evidencia |
|---|----------|---------------------------|-----------|
| A1 | `run_screener.py` (phases `__import__`) | Ensamble FASE 0/2/3/4 paralelo a `run_all.py`, sin subprocess CNV | `[VERIFICADO POR CÓDIGO]` |
| A2 | `run_pipeline.py` (14 pasos f-series) | Family legacy consolidada que converge en el mismo export | `[VERIFICADO POR CÓDIGO]` PASOS definidos; activación actual `[NO-DETERMINABLE]` |
| A3 | `e2e_ticker.py` | Variante ticker por emisor del pipeline legacy | `[VERIFICADO POR CÓDIGO]` |
| A4 | `idempotencia_engine.py`, `mut_f054_f055.py` | Re-run S03/S04 (N veces / mutado) — auditoría, no producción | `[VERIFICADO POR CÓDIGO]`; `[VERIFICADO POR TEST]` f050/f054/f055 (42 passed, 2 skipped, 1 xfail) |
| A5 | `demo_txar/` (23 scripts), `docs/_research`: sandbox de demostración, aislado del flujo productivo | `[NO-DETERMINABLE]` alcance en prod; `[VERIFICADO POR CÓDIGO]` autocontenido |

## 5. Invocables sin evidencia de ejecución

Nodos con `__main__`/entrypoint pero sin invocador, runbook ni test que los alcancen confirmado (lista representativa; ver secciones 9–10 para detalle):

- `scripts/tickets/cnv/scripts/*` (secuencia 01_mapear_cik … 07_generar_estadisticas y helpers `calcular_ratios_base`, `construir_catalogo`, `flags_calidad`) — invocada por run_all/run_update por `__import__` parcialmente; no todos tienen call-site.
- `scripts/engine/fundamentals_universo.py` — docstring indica "conduce S02→S03→S04 por emisor"; call-site `[NO-DETERMINABLE]`.
- `scripts/engine/homologacion_slice.py`, `release_baseline.py`, `cnv_pilot2.py` — targets de subprocess no confirmados.
- `scripts/tickets/screener/crear_pdf_guia.py`, `actualizar_seguimiento.py`, `gen_screener_html.py` — utilitarios con entrypoint, sin orquestador.
- `scripts/pipeline/scoreboard.py`, `triangulacion.py` — utilitarios de verificación, sin orquestador.
- `scripts/docgen/build.py`, `scripts/docgen/cli.py` — generadores, invocación manual.

`[NO-DETERMINABLE]` en todos los casos anteriores salvo donde se indica `[VERIFICADO POR CÓDIGO]` (la existencia del entrypoint sí está verificada).

## 6. Dead ends (sin salida productiva evidente)

- `_legacy/` raíz: 0 archivos `.py` (solo referencia histórica).
- `_research/`: archivos `.py` no encontrados en el nivel raíz (contenido `[NO-DETERMINABLE]`).
- `data/logs/runs/`: 0 manifests encontrados (directorio vacío o ausente) → el manifest-run log documentado no tiene artefactos `[VERIFICADO POR EJECUCIÓN]`.
- Import de `_raw_inmutable` existe en `run_update.py` (archivar/restaurar/registrar) y en `run_all.py` (inmutabilidad); sin módulo `_raw_inmutable` visible en el listado de `scripts/engine` (los 64 items listados no lo incluyen) → `[NO-DETERMINABLE]` (puede ser módulo de otro nivel).

## 7. Tests, auditorías y pilotos

- **Tests**: 32 archivos `test_*.py`: 27 en `tests/` + 5 en árbol `scripts` `[VERIFICADO POR EJECUCIÓN]`.
- **Suite ejecutada en el relevamiento**: `test_c11_contract.py` + `test_e2e_orchestrator.py` → **26 passed**; `test_f050_lifecycle_s00_s02.py`, `test_f054_aislamiento_emisores.py`, `test_f055_equivalencia_contextos.py` → **42 passed, 2 skipped, 1 xfailed** `[VERIFICADO POR EJECUCIÓN]`.
- `tests/test_runbook_operability.py`: verifica docstring/runbooks contra regex `python ((scripts|engine)/[\w/]+\.py)` y matríz `outputs/runbook/RUNBOOK_READINESS_MATRIX.csv` `[VERIFICADO POR CÓDIGO]`.
- **Certificación**: `c11_certificar.py` (C10/C11, validación de evidencia y emisión de certificación a `engine.certifications`). `[VERIFICADO POR TEST]` vía test_c11_contract; `[VERIFICADO POR EJECUCIÓN]` docs/review/R2/R3/R4_*_CERTIFICACION/EVIDENCIA.
- **Pilotos**: `cnv_pilot2.py` (piloto CNV) `[NO-DETERMINABLE]` invocación; `mut_f054_f055.py` + `idempotencia_engine.py` (auditoría F-054/F-055).

---

## 8. SEC (EDGAR)

- **Cadena canónica** (scripts/engine): `s00_smoke` → `s01_identity` → `s02_fetch_ypf` → `s03_parse_ypf` → `s04_normalize`. Efectos verificados en código:
  - s00: `engine.checkpoints` (INSERT + ON CONFLICT ux_checkpoints_reuse) `[CÓDIGO]`
  - s01: `engine.checkpoints` `[CÓDIGO]`; identidad vía `engine/identity.py`, `engine/identity_v1.py` `[CÓDIGO]`
  - s02: `fetch_raw.download_log` + `engine.checkpoints` `[CÓDIGO]`
  - s03: `parsed.*` (facts/contexts) + `engine.checkpoints` `[CÓDIGO]`
  - s04: `derived.fact` (ON CONFLICT fact_key), `derived.normalize_conflict`, `engine.stage_runs` (report JSONB), `engine.checkpoints` `[CÓDIGO]`
- **Orquestación**: `e2e_orchestrator.py` (STAGE_ID E2E_orchestrator, propagación de `ENGINE_E2E_RUN_ID` por subprocess) `[CÓDIGO]` `[TEST]`.
- **Scripts EDGAR de tickets (`scripts/tickets/sec_edgar/scripts`, 14)**: `01_mapear_cik, 02_descargar_datos, 03_calcular_ratios, 04_generar_reporte, 05_comparar_investing, 06_generar_calculos_edgar, 07_generar_estadisticas, calcular_ratios_base.py, construir_base.py, construir_catalogo.py, e1_adr_xbrl.py, flags_calidad.py, precios_y_valuacion.py, sec_adr_ratios.py`. `construir_base`/`calcular_ratios_base`/`precios_y_valuacion`/`sec_adr_ratios` son nodos reales del flujo productivo (ver P1/P3) `[CÓDIGO]`.
- **Censores de producción**: `--quarterly` (EDGAR incremental) y `--annual` (sec_adr_ratios vs 20-F) `[CÓDIGO]` run_update.

## 9. CNV

- **Motor CNV (`scripts/engine/c3_cnv_fetch.py`)**: escrituras `fetch_raw.cnv_download_log`, `fetch_raw.cnv_artifact`, `fetch_raw.cnv_presentation` + `RawStore(cuit)` (archivos RAW) + lectura `engine.stage_runs` `[CÓDIGO]`. Runbook 03_CNV_E2E_RUNBOOK `[EJECUCIÓN]`.
- **Jobs CNV (`scripts/tickets/cnv/jobs`, 16)**: `build_subset, job1_universo, job2_download, job3_formtype, job4_clasificar, job5_extract_eeff, job5_v2_extract_eeff, job6_extract_div, job6_v2_reparse_div, job7_validar, job8_doc_meta` + helpers `_check_adr, _check_byma, _check_identity, _diagnostico, _search_adr`.
  - Cadena subprocess de `run_all.py`: job1→job2→job3→job4→job5_v2→job6_v2→job7 (cwd=CNV_JOBS) `[CÓDIGO]`.
  - Cadena de `run_update.py` (--quarterly): job2→job3→job4→job5_v2 `[CÓDIGO]`.
- **Screener (scripts/tickets/screener, 86 py)**: nodos clave `run_update`, `run_all`, `run_screener`, serie `s0_normalizar_cnv … s9_*`, `construir_base`, `calcular_ratios_base`, `precios_y_valuacion`, `s5_exportar`, más `01–08_*` y utilitarios.
- **Metadata CNV (`cnv/metadata`, 4)**: tablas/lookup de apoyo `[NO-DETERMINABLE]` exacto de uso en runtime (incluido lookup de venue-tickers vía `f014_venue_ticker.py` en market).

## 10. Market

- `scripts/market` (15 py): `m0_discovery_yahoo, m1_symbol_mapping, m2_fetch_engine, m4_quality, m5_golden_case, m6_scale, m19_apply_schema, f014_venue_ticker, market_core, market_db, market_source` + 4 tests.
- Escrituras verificadas: `market_raw_files`, `market_raw_runs`, `market_price_daily`, `market_data_quality` + LOG `market_fetch_log` `[CÓDIGO]`.
- Cadena de calidad: `m2_fetch_engine` → `m4_quality` (INSERT market_data_quality) → `m5_golden_case` (relectura y verificación) `[CÓDIGO]`.
- Aplicación de schema de destino y escala: `m19_apply_schema`, `m6_scale` `[CÓDIGO]`.
- Consumido por: `e2e_producto.py` (fase_market), `ratio_inputs.sql_insumos` (market_price_daily), `api/main.py` (vía PG prod) `[CÓDIGO]`.

## 11. Otros dominios

- **API publicación** (`api/main.py`, 1): lee `screener` y `screener_hist` (PostgreSQL prod); endpoints de consulta filtrada. `[CÓDIGO]`.
- **Deploy** (`scripts/deploy/sincronizar_a_produccion.py`): sin TRUNCATE ciego; documenta por qué NO se usa `migrate_sqlite_to_pg.py` (TRUNCATE+INSERT+swap, orden OJO con el ORDEN); referencia `migrations/003_screener_iamc_mep.sql`. `[CÓDIGO]`.
- **Byma** (scripts/byma, 11): descargas/adaptación de datos BYMA; invocación `[NO-DETERMINABLE]`.
- **Carga de externos** (scripts/carga_externos, 7): importadores; invocación `[NO-DETERMINABLE]`.
- **Dólares** (scripts/dolares, 4): precios de dolar; invocación `[NO-DETERMINABLE]`.
- **Materia prima** (scripts/materia_prima, 6): `[NO-DETERMINABLE]`.
- **Docgen** (scripts/docgen, 18 + build/cli): generación de documentación; invocación manual `[NO-DETERMINABLE]`.
- **demo_txar** (23): sandbox de demostración aislado. `[CÓDIGO]`.
- **scratchpad** (54): zona de experimentación, por definición fuera del flujo productivo. `[NO-DETERMINABLE]` (no hay garante de inactividad).

---

## 12. Convergencias de escritura

| Objetivo de escritura | Nodos escritores | Evidencia |
|-----------------------|------------------|-----------|
| `engine.checkpoints` (PG) | s00, s01, s02, s03, s04, c3_cnv_fetch | `[CÓDIGO]` (ON CONFLICT ux_checkpoints_reuse en s00/s03/s04, c3) |
| `engine.stage_runs` (PG) | s04 (report JSONB); leído por c3 y c11 | `[CÓDIGO]` |
| `derived.fact` (PG) | s04 (ON CONFLICT fact_key); leído por ratio_engine/c11 | `[CÓDIGO]` |
| `fetch_raw.*` (PG) | s02 (download_log); c3 (cnv_download_log/cnv_artifact/cnv_presentation) | `[CÓDIGO]` |
| `market_{raw_files,raw_runs,price_daily,data_quality}` (PG) | m2, m4, m5 (+LOG market_fetch_log) | `[CÓDIGO]` |
| **`data/screener.db` (SQLite)** | run_update (CNV job5_v2 + precios), run_all (jobs+transform), run_screener (s0/s2/s3/s4/s6/s7/s9), construir_base, calcular_ratios_base, precios_y_valuacion | `[CÓDIGO]` — **punto convergente principal** |
| **`data/screener_export.csv` / `.json`** | s5_exportar (FASE 3 y 4); consumido por sincronizar_a_produccion → api | `[CÓDIGO]` [+ `[EJECUCIÓN]` artefacto data/screener_export.csv 256KB, 07/10/2026] |
| `outputs/docs/fase_*` | e2e_producto (fase_producto/fase_ratios), reparse_universo (fase_producto); resto de fases escritor exacto en algunos casos `[NO-DETERMINABLE]` | `[EJECUCIÓN]` (49+43+41+30+… artefactos presentes) |
| `data/logs/upd_YYYYMMDD.log` | run_update | `[CÓDIGO]` [+`[EJECUCIÓN]` 32 archivos en data/logs] |
| `engine.certifications` (PG) | c11_certificar | `[CÓDIGO]` |

Relevancia: toda decisión de evolución debe asumir que **screener.db y screener_export.csv son el punto de acople entre las tres familias**; y `engine.checkpoints` lo es para el motor.

## 13. Divergencias funcionales

1. **Documentado pero inexistente**: runbooks citan `python scripts/engine/c4_cnv_adapter.py`; `Test-Path` y búsqueda recursiva no encuentran el archivo. `[VERIFICADO POR CÓDIGO]` (ausencia verificada); clasificación de impacto `[NO-DETERMINABLE]`.
2. **Dos ensambles de FASE 4**: `run_all.py` (CNV vía subprocess a `cnv/jobs`) vs `run_screener.py` (todo por `__import__`). Ambos convergen en screener.db; no se verificó igualdad byte a byte de salida. `[CÓDIGO]`.
3. **Dos familias engine vs pipeline**: motor `s00–s04` (PG) y legacy `f1…f6` (SQLite) corren en paralelo y convergen en el mismo export. Convivencia intencional según docs; alcance de solapamiento `[NO-DETERMINABLE]`.
4. **run_update (producción cron) ≠ run_all (canónico manual)**: cadenas CNV distintas (job2→job3→job4→job5_v2 vs job1→…→job7); flags distintos (--with-cnv-fresh, --force-refresh vs solo subset rebuilt). `[CÓDIGO]`.
5. **e2e_producto "SOLO LECTURA"** vs él resto del motor que sí escribe. Es un nodo aislado de evaluación, no de carga. `[CÓDIGO]`.

## 14. Evidencia utilizada

- `[VERIFICADO POR CÓDIGO]`: lecturas estáticas de scripts/engine (s00–s04, c3, c11, e2e_orchestrator, ratio_engine, e2e_producto, reparse_universo, idempotencia, mut), scripts/pipeline/run_pipeline, scripts/tickets/screener (run_update, run_all, run_screener, s5_exportar), scripts/market (m2/m4/m5/m19/m6), scripts/deploy/sincronizar_a_produccion, api/main.py, scripts/setup_vps.sh (cron).
- `[VERIFICADO POR TEST]`: ejecución real de `test_c11_contract.py`, `test_e2e_orchestrator.py` (26 passed) y `test_f050`, `test_f054`, `test_f055` (42 passed, 2 skipped, 1 xfailed); inventario de 32 archivos `test_*.py`; `test_runbook_operability.py`.
- `[VERIFICADO POR EJECUCIÓN]`: `data/screener_export.csv` (256 KB, 07/10/2026), `outputs/docs/fase_*` (fase_cnv 127, fase_s04 49, fase_identity 43, fase_ratios 41, fase_market 30, …), `data/logs` (32 archivos), `data/*.db` (screener, byma_pipeline, demo*, *historico), `data/raw/{catalogo_edgar,engine,submissions}`, `docs/review/R2/R3/R4_*_{EVIDENCIA,CERTIFICACION}.md`, `outputs/runbook/RUNBOOK_READINESS_MATRIX.csv`, censo `docs/review/censo_assets/` (616 filas py + no_py + xlsx).
- `[NO-DETERMINABLE]`: invocación runtime de los nodos de las secciones 5, 11 y parte de 8/9 (targets no confirmados con call-site, grafo de `fundamentals_universo`, `homologacion_slice`, `release_baseline`, `cnv_pilot2`, y el escritor exacto de ciertos `outputs/docs/fase_*`).

---

## Conteos finales

- **Nodos `.py` censados**: 890 totales (scripts 483, scratchpad 54, docs 32, tests 27, engine-raíz 10+/, backend 5, api 1, _research 3, _legacy 0).
- **Entrypoints potenciales**: 208 archivos con `if __name__ == "__main__"`; 158 con `def main(`; 56 con `argparse`.
- **Pipelines productivos demostrados**: 8 (P1–P8).
- **Pipelines alternativos**: 5 (A1–A5).
- **Nodos invocables sin evidencia de ejecución confirmada**: lista no exhaustiva en sección 5; conteo exacto `[NO-DETERMINABLE]` (se requiere un grep call-site por nodo, fuera del alcance de Paso 1).
- **Convergencias de escritura**: 9 identificadas (sección 12); divergencias: 5 (sección 13).
- **Archivos creados**: 1 — `docs/review/01_EXECUTION_GRAPH.md`.
- **Evidencia usada**: 1 × `[CÓDIGO]`, 1 × `[TEST]`, 1 × `[EJECUCIÓN]`, 1 × `[NO-DETERMINABLE]` (leyenda detallada en sección 14).