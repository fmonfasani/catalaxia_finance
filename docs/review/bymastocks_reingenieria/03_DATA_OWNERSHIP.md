# 03 — DATA OWNERSHIP BYMAStocks
Estado: FASE 1 (auditoría). Evidencia: tabla de escritura por statement SQL (INSERT/UPDATE/DELETE/DROP/ALTER/CREATE) extraída por `scan.py`.

## 1. Definición de ownership

`OWNER(tabla) = set{scripts que escriben la tabla}`. Un propietario correcto es un script (o conjunto con coordinación declarada). Multi-escritor sin orquestación declarada = riesgo de ownership ambiguo.

## 2. Tabla `screener` (la de mayor impacto público)

| Escritor | Tipo stmt |
|---|---|
| scripts/pipeline/fix_manual.py | UPDATE |
| scripts/pipeline/fix_mapeo.py | UPDATE |
| scripts/tickets/screener/cedear_ratios.py | UPDATE |
| scripts/tickets/screener/jpm_adr.py | UPDATE |
| scripts/tickets/screener/s6_ajustes.py | UPDATE |
| scripts/tickets/screener/s7b_eps_base_per.py | UPDATE |
| scripts/tickets/screener/s7c_cagr.py | UPDATE |
| scripts/tickets/screener/s7d_dos_fuentes.py | UPDATE |
| (otros, total 11) | UPDATE |

`VERIFICADO POR CÓDIGO`. 11 escritores directos sobre la tabla que publica la API → **ownership fragmentado**, sin coordinación formal. Fases `s0..s8` regrabcan la tabla (DROP+CREATE) en `run_all/run_screener/run_update`.

## 3. Tablas `identity_v1.*` (canónica de la filosofía del proyecto)

| Tabla | N escritores | Ejemplos |
|---|---|---|
| identity_v1.assertion | 12 | audit_f044, audit_f045, cnv_validation_adversario, f041_reafirmacion, homologacion_final, f044_bench |
| identity_v1.identifier | 7 | audit_f044/45, f041_reafirmacion, homologaciones |
| identity_v1.source | 5 | audit_f044, homologaciones |
| identity_v1.entity | 4 | homologacion_final, homologacion_rutas_prohibidas, tests adversariales |

`VERIFICADO POR CÓDIGO`. **Coherencia**: la mayoría de escrituras están en auditorías/homologaciones (capa 10/11) — sano (no producción de datos). Pero riesgo de contadirección entre adversariales que mutan y asserts que protegen (ver ficha `engine_identity_v1` = PASS_WITH_WARNINGS).

## 4. `engine.stage_runs` (checkpoints planos EJECUCION/CONTROL)

| Escritor | |
|---|---|
| scripts/engine/s00_smoke.py | s01_identity.py | s02_fetch_ypf.py | s03_parse_ypf.py | s04_normalize.py | c3_cnv_fetch.py |

Múltiples escritores sobre la misma tabla de *checkpoints* es **desviación**: `stage_runs` debería tener un solo escritor por corrida (orquestador) o garantizar concurrencia única. `VERIFICADO POR CÓDIGO`. Riesgo de carreras si se lanzan dos orquestaciones en paralelo.

## 5. `empresas` (base de identidad local)

| Escritor | |
|---|---|
| scripts/tickets/cnv/scripts/cargar_argentina_cnv.py | cargar_byma_yfinance.py |
| scripts/tickets/sec_edgar/scripts/construir_base.py | construir_catalogo.py |

`VERIFICADO POR CÓDIGO`. 4 escritores CNV/edgar (capa FUENTES) + API leen `screener` no `empresas`.

## 6. `precios` (3 escritores)

`_refresh_rangos_52w.py`, `_retry52w_ba.py`, `s3c_refrescar_precios.py` → todos CAPA PRECIOS con misma tabla --- coordinación ordinal implícita (precedencia s3c), riesgo bajo pero ownership no declarado.

## 7. `derived.fact` (2 escritores)

`adversario_ratios.py` (banca adversarial, DROP sobre copia) + `test_ratio_engine_ev_sales.py` (test).
Riesgo: test que escribe la misma tabla que un adversarial → fuentes de mutación cruzada. `VERIFICADO POR CÓDIGO`.

## 8. Coincidencias de nombres con riesgo (relacionadas con 02_DEPENDENCY_GRAPH)

- `engine/config.py` + `cnv_ir/config.py`: alojan configs de dos dominos. Riesgo de acoplamiento por nombre.
- `engine/db.py` + `screener/db.py`: deben mantenerse disjuntas.

## 9. Recomendaciones (NO ejecutadas)

1. Asignar ownership formal con un solo "autor canónico" por tabla de datos (screener, identity_v1.*, stage_runs).
2. `stage_runs`: un único orquestador escribiendo checkpoints (evitar carreras).
3. `empresas`: unificar en engine/identity_v1 como fuente de verdad; convertir cargar_* y construir_* en lectores-escribidores coordinados.
4. No usar adversariales para mutar simultáneamente tablas que leen tests (separar una instancia descartable).
5. Momento 3-4 de reingeniería: exigir declaración de ownership en manifest/contrato por tabla.