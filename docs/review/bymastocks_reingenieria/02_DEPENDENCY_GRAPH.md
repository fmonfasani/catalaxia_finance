# 02 — DEPENDENCY GRAPH BYMAStocks
Estado: FASE 1 (auditoría). Evidencia: escaneo estático de imports (2822 filas import, 470 aristas internas resueltas sobre 616 archivos).

## 1. Hubs más importados (dependencias estructurales)

| Inbound | Módulo | Nota |
|---|---|---|
| 67 | `engine/config.py` | configuración base |
| 67 | `scripts/tickets/cnv/scripts/cnv_ir/config.py` | *duplicado de engine/config?* (mismo nombre, subtree CNV_IR) |
| 41 | `engine/db.py` | acceso DB |
| 41 | `scripts/tickets/screener/db.py` | *segundo db.py* |
| 19 | `scripts/demo_txar/_demo.py` | demo TXAR |
| 14 | `scripts/tickets/screener/_foco.py` | utilidades screener |
| 11 | `engine/identity_v1.py` | identidad canónica |
| 11 | `scripts/tickets/cnv/scripts/cnv_ir/catalogo_ir.py` | catalogo CNV-IR |
| 10 | `scripts/market/market_db.py` | market DB |
| 9 | `engine/states.py` | estados engine |
| 9 | `scripts/engine/ratio_inputs.py` | inputs ratios |
| 8 | `scripts/market/market_source.py` | fuentes market |
| 6 | `scripts/engine/ratio_defs.py` | definiciones ratios |
| 6 | `scripts/market/market_core.py` | core market |

`VERIFICADO POR CÓDIGO` — aristas reales resueltas por `resolve_module` (imports→archivos).

## 2. Dependencias duplicadas por nombre (nominalmente iguales)

| Nombre | Caminos | Riego |
|---|---|---|
| config.py | engine/config.py y scripts/tickets/cnv/scripts/cnv_ir/config.py | dos configs que pueden divergir |
| db.py | engine/db.py y scripts/tickets/screener/db.py | dos accesos DB (engine=PG, screener=sqlite) |
| discovery.py | engine/cnv/discovery.py y scripts/tickets/cnv/scripts/cnv_ir/discovery.py | dos descubridores CNV |
| _diag_db.py | tickets/cnv/_diag_db.py y tickets/screener/_diag_db.py | duplicado |
| _diagnostico.py | tickets/cnv/jobs/_diagnostico.py y tickets/screener/_diagnostico.py | duplicado |

**NO se deducen como idénticos por nombre**: requieren inspección (fase MERGE). Solo se marca el riesgo de acoplamiento por coincidencia nominal.

## 3. Grupo pipeline (legacy) — dependencias de contrato implícitas

- `run_pipeline.py` secuencia f1..f6 **[VERIFICADO POR CÓDIGO — main.py loop / deep audit]**
- `f4_ratios` asume `f3` dejó datos normalizados mismos unidades **[AUDITORIA_PREVIA + deep audit]**
- `schema_v1.sql` es dependencia estructural implícita del pipeline **[AUDITORIA_PREVIA]**
- `gen_screener_html.py` y `api/main.py` consumen la misma tabla `screener`

## 4. Grupo engine (canónico) — dependencias

- `engine/manifest.yaml` declara `pipeline_version: s0-bootstrap-v1` y `contract_versions` **[VERIFICADO POR CÓDIGO]**
- `engine/db.py` (41 in) y `engine/config.py` (67 in) son la base; `engine/identity_v1.py` (11), `engine/s03.py`, `engine/report.py` (5), `engine/xbrlparse.py` (5)
- Los scripts `scripts/engine/s01..s04` dependen de `engine/states.py`, `engine/manifest.yaml`, `engine/db.py`

`engine/states.py` y `engine/report.py` proveen checkpoints/manifiestos de corrida (función transversal de plano EJECUCION/CONTROL). **[VERIFICADO POR CÓDIGO]**

## 5. Dependencias de datos (tablas escritas por MULTIPLES scripts = acoplamiento de ownership)

| Tabla | N escritores | Ejemplos |
|---|---|---|
| identity_v1.assertion | 12 | identificador+assertions (audit f044/f045, homologaciones, adversariales) |
| screener | 11 | tickets s6/s7b/s7c/s7d, jpm_adr, cedear_ratios, fix_manual, fix_mapeo |
| identity_v1.identifier | 7 | audit/homologacion/bench |
| engine.stage_runs | 6 | s00..s04, c3_cnv_fetch |
| identity_v1.entity | 4 | homologación + tests |
| empresas | 4 | cargar_argentina_cnv, cargar_byma_yfinance, construir_base, construir_catalogo |
| precios | 3 | _refresh_rangos_52w, _retry52w_ba, s3c_refrescar_precios |
| derived.fact | 2 | adversario_ratios + test_ratio_engine_ev_sales |

`VERIFICADO POR CÓDIGO`. Multi-escritor sobre tabla = riesgo de ownership ambiguo, divergencia y pérdida de provenance (I-006).

## 6. Elipsis / hubs de cabecera

- Los 2 `config.py` y los 2 `db.py` son **acoplamiento nominal alto riesgo**: si se rotan caminos o se cambia uno pueden romperse decenas de importadores sin error estático.

## 7. Consumidores de api/main.py

- Endpoints v2 consumen `screener` y `screener_hist`.
- Endpoints v1 legacy consumen `silver_norm`, `validaciones`, `certificacion_nueva`, `mep_actual`.
- **[NO DETERMINABLE]** ningún test de contrato fija las 45 columnas como estabilidad pública.

## 8. Hallazgos

1. Doble base de acceso (`engine/db.py` + `screener/db.py`) sobre mundos distintos (PG vs SQLite) → separación de responsabilidad correcta pero riesgosa por proximidad nominal.
2. 3 dominios paralelos (engine, pipeline, screener tickets) compiten por las mismas tablas lógicas `screener` y `identity_v1.*`.
3. `engine/config.py` (67 in) es el hub vital: cualquier cambio es de alto impacto.
4. No hay un único grafo de dependencias versionado; verificar en fase 2 que cada script declare `PRIMARY_LAYER` para romper la ambigüedad.