# 05 — DUPLICATION MAP BYMAStocks
Estado: FASE 1 (auditoría). Marcamos candidatos de duplicación semántica SIN ejecutar nada. Conclusión sin inferencia: se señala SI hay evidencia de solapamiento; la fase MERGE/DELETE requiere pasos 1-10 de la regla de seguridad.

## 1. Duplicación declarada en censo

El censo (censo_py_master.csv) declaró `duplicacion`/`duplicado_de` en 266 filas (fila de duplicación). Aquí refinamos con evidencia de código y shared ownership.

## 2. Duplicados por nombre de archivo (posible copia literal o fork)

| Nombre | Caminos | Observación |
|---|---|---|
| **ratios.py** | backend/calculators/ratios.py · docs/calculos-financieros/codigo-referencia/ratios.py | ref de doc vs código producción → verificar semántica |
| **sec_edgar.py** | backend/fetchers/sec_edgar.py · docs/calculos-financieros/codigo-referencia/sec_edgar.py | igual arriba |
| **02_descargar_datos.py** | docs/calculos-financieros/codigo-referencia/02_descargar_datos.py · scripts/tickets/sec_edgar/scripts/02_descargar_datos.py | ticket + ref |
| **03_calcular_ratios.py** | docs/codigo-referencia/03_calcular_ratios.py · scripts/tickets/sec_edgar/scripts/03_calcular_ratios.py | ticket + ref |
| **03_descargar_financials_sec.py** | _research/scripts/03_descargar_financials_sec.py · docs/calculos-financieros/codigo-referencia/03_descargar_financials_sec.py | research + ref |
| **05_calcular_ratios.py** | _research/scripts/05_calcular_ratios.py · docs/calculos-financieros/codigo-referencia/05_calcular_ratios.py | research + ref |
| **07_calcular_ratios.py** | docs/codigo-referencia/07_calcular_ratios.py · scripts/screener/07_calcular_ratios.py | script screener + ref |
| **config.py** | engine/config.py · scripts/tickets/cnv/scripts/cnv_ir/config.py | **riesgo alto acoplamiento** |
| **db.py** | engine/db.py · scripts/tickets/screener/db.py | **riesgo alto acoplamiento** |
| **discovery.py** | engine/cnv/discovery.py · scripts/tickets/cnv/scripts/cnv_ir/discovery.py | doble descubridor CNV |
| **_diag_db.py** | tickets/cnv/_diag_db.py · tickets/screener/_diag_db.py | duplicado de diagnostico |
| **_diagnostico.py** | tickets/cnv/jobs/_diagnostico.py · tickets/screener/_diagnostico.py | duplicado |

`VERIFICADO POR CÓDIGO`. `__init__.py` y `conftest.py` son vacíos/test-infra (no duplicación semántica).

**IMPORTANTE**: que dos archivos compartan nombre NO implica que sean duplicados. Necesitamos el diff real en fase MERGE (9).

## 3. Duplicación de dominio (mismo dato en dos implementaciones) — detectado por deep audit

| Dominio | Versión canónica | Versión legacy/dup | Riesgo |
|---|---|---|---|
| Identidad | engine/identity_v1.py | f1_identidad.py + construir_base/construir_catalogo (tickets/sec_edgar) | divergencia de entidad |
| Ratios | scripts/engine/ratio_engine / ratio_inputs / ratio_defs | f4_ratios.py | dos cálculos del mismo ratio |
| Pipeline | engine s00..s04 | scripts/pipeline/f1..f6 | dos flujos |
| Screener build | fases s0..s8 | run_pipeline f5_screener | dos caminos a `screener` |
| SEC fetch | engine/s02/03 | scripts/tickets/sec_edgar/scripts/descarga | dos extractores EDGAR |

`VERIFICADO POR CÓDIGO` (fichas deep audit de f1, f4, f6, run_all, identity_v1).

## 4. Escritores compartidos (ownership duplicado ya cubierto en 03)

Tablas con 2+ escritores (siempre riesgo de duplicación de lógica): identity_v1.assertion (12), screener (11), identity_v1.identifier (7), stage_runs (6), identity_v1.source (5), identity_v1.entity (4), empresas (4), precios (3), derived.fact (2). `VERIFICADO POR CÓDIGO`.

## 5. Duplicación funcional puntual ya señalada en auditoría previa (fuente: censo + AUDITORIA_FASE_1)

- `10b_actualizar_mep_hoy.py` (scripts/market) duplica `actualizar_dolares.py` (scripts/dolares).
- `carga_estados_investing_10empresas.py` incompleta (2/10) duplica `carga_investing_10_full.py` → MERGE_REPLACE.
- `_research/schema/001_initial_schema.sql` = duplicado de `migrations/001_initial_schema.sql`.

## 6. Conclusión de la fase duplicación

- Priority para MERGE (fase 9): identidad (identity_v1 vs f1), ratios (ratio_engine vs f4), pipeline (engine vs legacy), screener build.
- Priority para DELETE (fase 8): duplicados nominales en docs/codigo-referencia (si diff 100 %), tickets `_diag_*`/`_diagnostico`.
- **Nada se ejecuta ahora.** Cada ítem requiere: diff real, dependencias reales, consumidores, impacto, alternativas, plan de migración, verificación, certificación (regla de seguridad).