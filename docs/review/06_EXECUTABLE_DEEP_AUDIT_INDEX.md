# 06 — Executable Deep Audit INDEX

Índice y matrices del Paso 6. Fichas en `docs/review/06_EXECUTABLE_DEEP_AUDIT/`: S00, S01, S02, S03, S04, E2E, C3, C11, IDENTITY, CNV, MARKET, RATIOS, PUBLICATION (+ este índice). Cada afirmación: `[CÓDIGO]`/`[TEST]`/`[EJECUCIÓN]`/`[NO-DETERMINABLE]`.

## Componentes auditados (ficha completa)

| Componente | Archivo | Capa | Plano | Estado | Riesgo |
|---|---|---|---|---|---|
| s00_smoke | S00.md | C10 | CONTROL | PRODUCTIVO PROBABLE | R1 |
| s01_identity | S01.md | C2 | DATOS | PRODUCTIVO PROBABLE (YPF) | R2 |
| s02_fetch_ypf | S02.md | C3 | DATOS+EJEC. | PRODUCTIVO PROBABLE (YPF) | R2 |
| s03_parse_ypf | S03.md | C4 | DATOS | PRODUCTIVO PROBABLE (YPF) | R2 |
| s04_normalize | S04.md | C5 | DATOS+CONTROL | PRODUCTIVO PROBABLE | R2 |
| e2e_orchestrator (+e2e_producto, idempotencia, mut) | E2E.md | C10 | CONTROL+EJEC. | PROBABLE / TEST anexos | R2 / R1 / R0 |
| c3_cnv_fetch (+identity_link, backfills) | C3.md | C3 | DATOS+EJEC. | PRODUCTIVO PROBABLE | R2 |
| c11_certificar (+StageReport/gates, 40_certificar, suites) | C11.md | C11 | CONTROL | PRODUCTIVO PROBABLE | R1 (R2 p/40) |
| engine/identity (v0) | IDENTITY.md | C2 | DATOS | PRODUCTIVO PROBABLE | R2 |
| engine/identity_v1 (v1) | IDENTITY.md | C2 | DATOS | PRODUCTIVO PROBABLE | R2 |
| run_update | CNV.md | C7 | EJEC.+CONTROL | **PRODUCTIVO CONFIRMADO** | **R3** |
| run_all / run_screener | CNV.md | C7 | EJECUCIÓN | ALTERNATIVO | R2 |
| job5_v2 / job6_v2 (+v1, jobs 1-4,7,8) | CNV.md | C3/C4/C10 | DATOS+EJEC. | PROBABLE / LEGACY v1 | **R3** / R1 |
| m2_fetch_engine | MARKET.md | C3 | DATOS | PRODUCTIVO PROBABLE | R2 |
| m1_symbol_mapping | MARKET.md | C3 | DATOS | PRODUCTIVO PROBABLE | R2 |
| m4_quality / m5_golden (+m6/m19/base) | MARKET.md | C10 | DATOS | PROBABLE / TEST | R1 |
| s3_precios / precios_y_valuacion | MARKET.md | C8 | DATOS | PRODUCTIVO PROBABLE | R2 |
| FX (dolares, _mep, b4) | MARKET.md | C6 | DATOS | PROBABLE / hueco motor | R2 |
| 4 motores ratios + materializadores | RATIOS.md | C8 | DATOS | CONFIRMADO ×2 / PROBABLE / LEGACY | R2/R1 |
| s5_exportar | PUBLICATION.md | C12 | DATOS | **PRODUCTIVO CONFIRMADO** | R1 |
| sincronizar_a_produccion | PUBLICATION.md | C12 | DATOS+EJEC. | PRODUCTIVO PROBABLE | **R3** |
| migrate_sqlite_to_pg | PUBLICATION.md | C12 | DATOS | PRODUCTIVO PROBABLE | **R4** |
| publicar_screener_v2 (+cagr_roe) | PUBLICATION.md | C12 | DATOS | NO-DETERMINABLE (uso) | R1 |
| api/main.py | PUBLICATION.md | C12 | DATOS | **PRODUCTIVO CONFIRMADO** | R2 |

## Componentes no auditados (motivo)

| Componente | Motivo |
|---|---|
| f-series pipeline (f1..f6, fixes) | LEGACY sin caller; ownership ya fijado en 03; ficha completa no justificada (riesgo heredado R2 por escritura en `screener`) |
| demo_txar/*, byma/*, carga_externos/*, docgen/* | DEMO/dominio-aislado/infra; cubiertos por producto (04 §12) y ownership (03) |
| pilots (cnv_pilot2, homologacion_*, benches) | PILOTO/TEST; riesgo acotado, sin escritura productiva |
| engine/db.py, config.py, fetch.py, hashout.py, xbrlparse.py | librerías auditadas por uso en fichas (contrato + consumidores); sin ficha propia por ser transversales ya cubiertos en 02 §2.1/§11 |

## Auditoría SEC especial (§9 del encargo)

Run lifecycle (runs + E2E run_id compartido), stage_runs, checkpoints ux, hash_in/out (sha256 RAW, fact_key, hashout), CIK (golden 0000904851 en s01–s03; genérico por `--cik`/entity_key en s04/ratio), identity V0 (s01/s03) + V1 (s04/ratio/c3), RAW→PARSED→NORMALIZED, provenance completa, gates C10 por stage, C11 por c11. Probado: e2e+f050/f054/f055+s03_xbrlparse+s04_normalize (68 passed acumulados). No probado: reintentos HTTP (s02/c3), TLS motor, comparación numérica cross-motores. Golden YPF ≠ arquitectura genérica: s01–s03 golden; s04/ratio/c11 genéricos; e2e YPF-only por STAGES.

## Auditoría C10/C11/C12 (§15)

Quién valida: gates stages + job7 + m4/m5 + suites + o2_* + 30_validaciones. Quién certifica: c11 (motor, sin consumidor en publicación) y 40_certificar (materia_prima, vía sync a PG). Quién publica: s5, sync, migrate, publicar_v2, api. Gates entre etapas: `assert_transition` (motor), exit codes + logs (screener), transacciones PLAN (sync), swap (migrate). **Ruptura actual**: certificación del motor no alimenta publicación; `screener_hist` sin writer; PG `screener` solo vía migrate desaconsejado.

## Tests (§16)

TEST EXISTE+PASA: e2e_orchestrator(+integration), c11_contract, f050, f054, f055, s03_xbrlparse, s04_normalize, ratio_engine_ev_sales, identity_v1, backfill_cik_adversarial, cnv_authority, cnv_identity_link, engine_cnv, engine_run_lifecycle, f032, f035, f038, f040, f041, f051, f061, hashout, market_prod_guard, market tests (4), r2_secretos, r3_raw_inmutable, runbook_operability. TEST NO EXISTE (unitario directo): calcular_ratios_base, s2_ratios_cnv, f4_ratios, sync, migrate, api, run_update/run_all (cobertura indirecta vía artefactos/logs). Sin TEST FALLA registrados en las suites corridas (pasos 1–5).

## Ejecución controlada (§17)

| COMMAND | ENVIRONMENT | DATABASE | RESULT | ARTIFACT | SIDE EFFECTS |
|---|---|---|---|---|---|
| `python3 -m py_compile` ×25 ficheros auditados | local, sin env | ninguna | 25/25 OK | .pyc en `__pycache__` (artefacto menor, no versionado) | ninguno funcional |
| `python3 scripts/engine/e2e_orchestrator.py --help` | local | ninguna (falla en argparse antes de DB) | exit 1, traceback argparse | ninguno | ninguno |
| suites pasos 1–5 (c11+e2e 26 passed; f050/f054/f055 42 passed/2 skip/1 xfail) | local | test DB | PASS | logs de pytest | ninguno en prod |
| lecturas `sqlite_master` data/*.db | local RO (`mode=ro`) | SQLite local | inventario §2.11 de 03 | ninguno | ninguno |

NO ejecutado contra producción. NO ejecutados pipelines completos (innecesario: evidencia previa suficiente). Clasificación: todo lo anterior `[EJECUCIÓN]`; resto de fichas `[CÓDIGO]`+`[TEST]`.

## Matriz final (§19)

| Componente | Capa | Plano | Estado | Owner | Writers | Consumers | Provenance | Idempotencia | Destructividad | Seguridad | Riesgo | Duplicación | Sustituibilidad | Evidencia |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| s00 | C10 | CONTROL | PROBABLE | engine | s00 | e2e,c11 | COMPLETA | VERIFICADA | ninguna | R0 | R1 | — | — | TEST |
| s01 | C2 | DATOS | PROBABLE | s01 | s01 | s03 | COMPLETA | VERIFICADA | ninguna | R0 | R2 | G1 D3 | S4 | TEST |
| s02 | C3 | DATOS+EJEC | PROBABLE | s02 | s02 | s03 | COMPLETA | PARCIAL | ninguna | R1(TLS-ND) | R2 | G-constr_base D2 | S4 | TEST |
| s03 | C4 | DATOS | PROBABLE | s03 | s03 | s04,ratio,c11 | COMPLETA | VERIFICADA | reset seq. | R0 | R2 | G-eng.s03 D0 | — | TEST |
| s04 | C5 | DATOS+CTRL | PROBABLE | s04 | s04 | ratio,c11 | COMPLETA | VERIFICADA | DO UPDATE | R0 | R2 | G10 D2 | S3 | TEST+EJEC |
| e2e_orch | C10 | CTRL+EJEC | PROBABLE | engine | e2e | c11,tests | COMPUESTA | PARCIAL | ninguna | R0 | R2 | G15 D1/D7 | — | TEST |
| c3 | C3 | DATOS+EJEC | PROBABLE | c3 | c3 | audit,c3_link | COMPLETA | VERIFICADA | filtro ruido | R1(TLS-ND) | R2 | 05§11 D8 | — | TEST |
| c11 | C11 | CONTROL | PROBABLE | c11 | c11 | boletín,tests | COMPLETA | VERIFICADA | ninguna | R0 | R1 | G9 D2 | S0 | TEST |
| identity v0 | C2 | DATOS | PROBABLE | s01 | s01 | s03 | PARCIAL | det. | ninguna | R0 | R2 | G1 D3 | S4 | TEST |
| identity v1 | C2 | DATOS | PROBABLE | convención | link,backfills | s04,ratio,c3 | COMPLETA | append-only | RESOLVED reviews | R0 | R2 | G1 D3 | S4 | TEST |
| run_update | C7 | EJEC+CTRL | CONFIRMADO | cron | +jobs,etapas | s5,sync,api(ind) | PARCIAL | PARCIAL | delegada | R3(verify=False) | R3 | G3 D5 | S1 | EJEC |
| run_all/all-screener | C7 | EJEC | ALTERNATIVO | manual | +jobs,etapas | s5 | PARCIAL | PARCIAL | delegada | R1 | R2 | G3 D5 | S1 | CÓDIGO |
| job5_v2/job6_v2 | C3/C4 | DATOS+EJEC | PROBABLE | jobs | jobs | s0/s2 | PARCIAL | resume-safe | DELETE suspects(j7) | R3(verify=False) | R3 | G6 D7 | S3 | CÓDIGO |
| m2 | C3 | DATOS | PROBABLE | market | m2 | m4,ratio,e2e_p | PARCIAL | no-refetch | ninguna | R0 | R2 | — | — | TEST |
| m1 | C3 | DATOS | PROBABLE | market | m1 | m2 | PARCIAL | PARCIAL | ninguna | R0 | R2 | G8 D2 | S0 | TEST |
| m4/m5 | C10 | DATOS | PROBABLE/TEST | market | m4 | m5,humano | PARCIAL | n/a | ninguna | R0 | R1 | — | — | TEST |
| precios-motores | C8 | DATOS | PROBABLE | s3/sec_edgar | 2 writers | s4 | PARCIAL | PARCIAL | ninguna | R0 | R2 | G12 D2 | S1 | EJEC |
| ratios-motores | C8 | DATOS | CONF×2/PROB/LEG | 4 owners | 4 | s4/ND | mixta | DROP-recreate | DROP | R0 | R2/R1 | G4 D2+D8 | S0 | EJEC |
| s5 | C12 | DATOS | CONFIRMADO | run_all | s5 | ND + disco | AUSENTE-fil | VERIFICADA | overwrite artefacto | R0 | R1 | G17 D8 | — | EJEC |
| sync | C12 | DATOS+EJEC | PROBABLE | deploy | sync | PG,api | AUSENTE | transacción | reemplazo 7t | R2(SSH/shell) | R3 | G5 D6 | S1 | CÓDIGO |
| migrate | C12 | DATOS | PROBABLE | deploy | migrate | PG:screener,api | AUSENTE | swap+precond | TRUNCATE | R1 | R4 | G5 D6 | S0 | CÓDIGO |
| publicar_v2 | C12 | DATOS | ND-uso | publicar | publicar_v2 | ND | AUSENTE | dry-run | CREATE+INSERT | R0 | R1 | G17 D8 | — | CÓDIGO |
| api | C12 | DATOS | CONFIRMADO | producto | —(lee) | usuarios | n/a | n/a | ninguna | R2(auth-ND) | R2 | — | — | CÓDIGO |

## Matriz de contratos (§20)

| Componente | Input | Output | State | Error | Provenance | Idempotencia | Contrato |
|---|---|---|---|---|---|---|---|
| s00 | IMPL | IMPL | IMPL | PARCIAL | IMPL | IMPL | IMPL |
| s01 | IMPL | IMPL | IMPL | IMPL | IMPL | IMPL | IMPL |
| s02 | IMPL | IMPL | IMPL | PARCIAL | IMPL | PARCIAL | PARCIAL |
| s03 | IMPL | IMPL | IMPL | IMPL | IMPL | IMPL | IMPL |
| s04 | IMPL | IMPL | IMPL | PARCIAL | IMPL | IMPL | IMPL |
| e2e_orchestrator | IMPL | IMPL | IMPL | PARCIAL | PARCIAL | PARCIAL | PARCIAL |
| c3 | IMPL | IMPL | IMPL | PARCIAL | IMPL | IMPL | IMPL |
| c11 | IMPL | IMPL | IMPL | IMPL | IMPL | IMPL | IMPL |
| identity v0/v1 | IMPL | IMPL | IMPL | IMPL/PARCIAL | PARCIAL/IMPL | IMPL | PARCIAL/IMPL |
| run_update | IMPL | IMPL | PARCIAL | IMPL(exit=errores) | PARCIAL | PARCIAL | PARCIAL |
| run_all/screener | IMPL | IMPL | PARCIAL | PARCIAL | PARCIAL | PARCIAL | PARCIAL |
| jobs v2 | IMPL | IMPL | PARCIAL(DONE-file) | PARCIAL | PARCIAL | PARCIAL | PARCIAL |
| market m1/m2/m4 | IMPL | IMPL | IMPL | PARCIAL | PARCIAL | PARCIAL | PARCIAL |
| ratios motores | IMPL | IMPL | PARCIAL | ND | PARCIAL | PARCIAL(DROP) | PARCIAL |
| s5 / sync / migrate / publicar_v2 / api | IMPL | IMPL | IMPL/PARCIAL | PARCIAL/IMPL | AUSENTE | IMPL/PARCIAL | PARCIAL |

## Matriz de incumplimientos (§21)

| Nivel | Componente | Regla afectada | Evidencia | Impacto | Requiere modificación futura |
|---|---|---|---|---|---|
| CRÍTICO | migrate_sqlite_to_pg | C12 publica con TRUNCATE en prod siendo único camino a PG `screener` | código + 03§11 + 04§8 | tabla vacía ante fallo de INSERT | SÍ (Paso 7) |
| CRÍTICO | api + (ausencia) | C12 sirve `screener_hist` sin producer | api:215/229 + grep cero writers | dato sin provenance ni owner | SÍ (Paso 7) |
| ALTO | job5_v2/job2_download (+run_update quarterly) | infra/seguridad: `verify=False` en HTTP productivo | job5_v2:264 | MITM / integridad de RAW CNV | SÍ (Paso 7) |
| ALTO | run_update | ejecuta red+escrituras multi-tabla sin reintento propio | código :782 | fallo parcial silencioso-por-etapa (mitigado por logs) | SÍ (Paso 7) |
| ALTO | sincronizar_a_produccion | reemplazo en PG prod sin dry-run verificado + shell=True + SSH | código | escritura prod irreversible por tabla | SÍ (Paso 7) |
| MEDIO | s01/s02/s03 | arquitectura genérica vs golden hardcodeado | GOLDEN_CIK + gates | techo multiemisor (regla: no generalizar ahora) | SÍ (Paso 7+, no ahora) |
| MEDIO | s02/c3 | reintentos HTTP no verificados | extractos | fragilidad ante red | SÍ (Paso 7) |
| MEDIO | s04 | cobertura mínima de excepts | s04:90 | error no clasificado aborta corrida | SÍ (Paso 7) |
| MEDIO | 40_certificar | C11 sin run_id motor | código | certificación no cruzable con c11 | SÍ (Paso 7) |
| BAJO | s04 dict vs StageReport | uniformidad C10 mecánica | 05 G10 | mantenimiento doble | SÍ (Paso 7) |
| BAJO | api auth | superficie HTTP con auth no verificada | extracto | acceso | SÍ (Paso 7) |
| BAJO | e2e --help exit 1 | UX operativa | §17 | confusión operador | SÍ (Paso 7) |

## Matriz de decisiones futuras (§22) — todo "NO DECIDIDO"

| Hallazgo | Posible acción futura | Evidencia | Dependencias | Paso |
|---|---|---|---|---|
| migrate TRUNCATE único camino | REWRITE CANDIDATE (publicador con staging) | §21 CRÍTICO | api, PG prod | 7 |
| screener_hist sin writer | REVIEW (origen + backfill o retirar lectura) | api:215/229 | api | 7 |
| verify=False jobs | ADAPT (TLS + reintentos) | job5_v2:264 | run_update quarterly | 7 |
| sync sin dry-run | ADAPT | código sync | PG prod | 7 |
| identidad v0/v1 | MERGE CANDIDATE (con bridge) o KEEP dual | IDENTITY.md | s01/s03/s04/ratio/c3 | 7 |
| facts vs derived.fact | MERGE CANDIDATE o KEEP por dominio | 05 G2 | motores ratios | 7 |
| UPDATE/ALL/SCREENER | MERGE CANDIDATE (unificar rebuild) | 05 G3 | cron, s9 | 7 |
| run_pipeline/f-series | ARCHIVE CANDIDATE (tras migrar dim_instrument) | 04 §7 | market m1 | 7–10 |
| job5/6 v1, construir_catalogo | ARCHIVE CANDIDATE | 05 G6/G11 | jobs v2, empresas | 7–10 |
| screener_gold/fact_ratios | DELETE CANDIDATE (huérfanos) o ARCHIVE | 04/05 | ninguno verificado | 7–10 |
| engine/s03.py | ARCHIVE CANDIDATE (sin consumidor) | 05 §4.4 | ninguno | 7–10 |
| s04 dict → StageReport | ADAPT | 05 G10 | c10 | 7 |

## Informe final

- CAPA: todos los componentes con CAPA PRIMARIA declarada en fichas (§23 cumplido; mezclas C9/C10 en stages documentadas como contractuales).
- PLANOS: DATOS/CONTROL/EJECUCIÓN/INFRA evaluados por ficha.
- CICLO: relevamiento 01→06 completo y cruzado (contradicciones 04 §21 registradas).
- HOY: 24 pipelines (04), 18 grupos duplicación (05), 30 objetos ownership (03), 89 aristas dependencia (02).
- OBJETIVO (Paso 7): con este índice puede responder qué conservar/adaptar/fusionar/eliminar/archivar/reemplazar, en qué orden y con qué riesgos.
- DECISIÓN: **ninguna tomada** (todas las acciones futuras "NO DECIDIDO").
- EVIDENCIA: `[CÓDIGO]` mayoritaria, `[TEST]` 68+ passed acumulados, `[EJECUCIÓN]` artefactos/logs/25×py_compile, `[NO-DETERMINABLE]` explícito (§ siguiente).
- Archivos creados: 14 (13 fichas + este índice) en `docs/review/06_EXECUTABLE_DEEP_AUDIT/`.
- Componentes auditados: 40+ (tabla inicial). Pendientes con motivo: f-series legacy, dominios aislados, pilots, librerías transversales (tabla inicial).
- Hallazgos críticos: 2 (§21). Conflictos confirmados: herencia de 03 §16 + 05 §21 (identidad dual, hechos duales, `empresas` 4 writers, sync↔migrate, hist sin writer).
- Riesgos: R4 ×1 (migrate), R3 ×3 (run_update, jobs red, sync), R2 ×mayoría stages/motores, R1/R0 resto.
- NO-DETERMINABLE: reintentos HTTP (s02/c3), TLS motor, comparación numérica cross-ratios, lectores de derived.ratio/fact_ratios/screener_gold/screener_v2/boletín/CSV, writer de screener_hist, auth api, bloqueo real de suites, alcance runtime de legacy (catálogo/pipeline), cron VPS activo.
- Pruebas ejecutadas: suites pasos 1–5 (68 passed) + py_compile 25/25 + --help e2e (exit 1).
- Ejecuciones realizadas: solo no-destructivas (tabla §17). Side effects: `.pyc` en `__pycache__` (menor, no versionado).
- Conclusión: el sistema productivo real (cron screener + publicación) convive con un motor certificado sin llegada a usuario y con publicadores de riesgo (migrate TRUNCATE, sync reemplazo, jobs sin TLS). Todo registrado para el Paso 7 sin tomar decisiones.