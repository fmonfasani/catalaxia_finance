# 12 — F0 Evidencia R7.2 (solo lectura; cero modificaciones)

| Gap | Evidencia | Método | Resultado | Fase afectada | Gate |
|---|---|---|---|---|---|
| equivalencia numérica ratios | motor-PG redondea `round(valor,6)` + `ratio_key` (ratio_engine:278,422,454,469); SQLite-motores sin redondeo verificado; claves distintas (cik-fila vs ratio_key vs cuit) | grep código + 06 RATIOS | PENDING_EVIDENCE (diseño M5 vigente; tolerancia TBD) | R7.8 | informe M5 |
| screener_hist writer | 0 apariciones en `*.py`/`*.sql`/docs salvo lectura api:215/229 | grep exhaustivo | PENDING_EVIDENCE (hueco confirmado) | R7.1/R7.10 | resolver o retirar lectura |
| lectores legacy | `tickers`: 0 lectores; `descargas_log`: solo copia migrate (lectores PG ND); `screener_gold`/`fact_ratios`/`derived.ratio`/boletín/CSV: 0 lectores | grep código | PENDING_EVIDENCE (confirma 08-C/D; `descargas_log` con downstream) | R7.12 | censo + ventana |
| HTTP retries | motor `engine.fetch.Fetcher`: max_attempts=3, backoff [2,5,10], timeouts 10/180, catch RequestException (fetch.py:19-56); `engine.cnv.client`: retry/backoff/rate-limit por host + retryable-status (client.py:1-97); jobs (job2/job5_v2): solo sleep, sin retry | lectura código | VERIFICADO POR CÓDIGO (motor SÍ reintenta; jobs NO) — resuelve ND de 06 para motor | R7.2 | documentado |
| TLS | `verify=False`/bypass en ~50 sitios: demo, dolares, pipeline/fetch_dgce, cnv scripts (job5 v1+v2, job6 v1, diag/cedear/jpm); `engine/` SIN ocurrencias (defaults requests) | grep código | VERIFICADO POR CÓDIGO (jobs/legacy sin TLS; motor con default) | R7.2/R7.6 | ADAPT jobs (no en F1) |
| API auth | sin Depends/APIKey/OAuth/Bearer; solo CORS `allow_origins=["*"]` (api:18,35-37) | lectura código | VERIFICADO POR CÓDIGO (API pública sin autenticación) — resuelve ND de 06 | R7.2 | decidir auth fuera de F1 |
| VPS cron | `setup_vps.sh:127-151` define cron.d + compose; corridas locales 09/07/2026 en horario manual | lectura + logs | VERIFICADO (definición) + ND (actividad actual del VPS) | — | ND aceptado |
| runtime legacy | jobs v1: sin caller (solo docstrings); f-series: caller único run_pipeline + menciones solo-comentario (c11:15 no-acople, s2a:29 antecedente); migrate: único writer PG `screener` (uso ND); publicar_v2: sin lector; catalogo: sin caller; screener_gold: sin lector | grep código | VERIFICADO (textual) + ND (runtime histórico) → sostiene 08 | R7.12 | ventana |
| suites bloqueantes | BLOQUEAN: `assert_transition` gates, job7 (limpia suspects), c11 (certifica); INFORMAN: m4/m5, validar_suite(_edgar), gate_roe, o2_*, 30_validaciones (insumo, no bloqueo), test-suites | lectura código | VERIFICADO POR CÓDIGO (clasificación) | R7.10 | registro único |
| FX coverage | MEP: fetch_dolarito→`dolarito_cotizaciones`→b4/_mep/sync; `dolares` curada 2 writers; CCL/oficial: tipos nominales sin productor | grep + 05 §14 | PARCIAL (MEP verificado; CCL/oficial ND) | R7.11 | serie por tipo |

## Gate F0

Ninguna evidencia contradice precondiciones F1 (el cambio M7 toca solo serialización de reporte s04, sin red/DB-schema/producción; hallazgos TLS/auth/hist son fuera de alcance F1 y quedan registrados). **F0 = PASS_WITH_WARNINGS** (warnings: TLS deshabilitado en jobs, API sin auth, hist sin writer — ninguno bloquea M7). F1 puede continuar. `[EJECUCIÓN]` (greps de este paso; cero escrituras salvo este documento).
