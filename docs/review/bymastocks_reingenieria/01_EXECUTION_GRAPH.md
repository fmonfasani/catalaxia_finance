# 01 — EXECUTION GRAPH (mapa real de ejecución) — BYMAStocks
Estado: FASE 1 (auditoría). Nada modificado. Evidencia: escaneo estático de 616 `.py` en el árbol principal.

## 0. Metodología y evidencia

- Inventario: `git ls-files` + barrido de disco (616 `.py` exactos, 0 desvíos vs censo).
- `VERIFICADO POR CÓDIGO` salvo donde se indica: cada afirmación proviene de leer fuentes y del escaneo automatizado `scan.py`.
- Headers / shapes semánticos corroborados con 13 fichas de DEEP AUDIT en `06_EXECUTABLE_DEEP_AUDIT/` y con la auditoría previa `AUDITORIA_FASE_1.md`.

## 1. Realidad de repositorio

| Metalos | n | estado |
|---|---|---|
| Código `.py` en árbol principal | 616 | = censo (0 desvíos) |
| de los cuales **trackeados por git** | 363 | **253 sin commit (41 %)** |
| entrypoints (tienen `__main__`/main) | 238 | 42 con subprocess/scheduler (orquestadores) |

Brecha de tracking por directorio:
- `scratchpad/` 54 untracked (100 %); `scripts/` 173 untracked (173/478 = 36 %); `docs/` 14; raíz 5; `tests/` 7.
- Consecuencia crítica: parte significativa del sistema vive fuera del control de versiones → NO reproducible ni auditable en git. **[VERIFICADO POR CÓDIGO — git ls-files]**

## 2. Punto de entrada real descubierto

Hay **4 familias de ejecución** (no una sola):

1. **Api** — `api/main.py` (v2, endpoints /screener, /hist, /grupos, /stats) + `/v1` legacy. Entrypoint: `uvicorn main:app`. Lee PostgreSQL.
2. **Screener tickets** — `scripts/tickets/screener/run_all.py`, `run_screener.py`, `run_update.py` (orquestadores que reconstruyen `screener.db` fases s0..s8). Se registran en Task Scheduler (`setup_scheduler.ps1`).
3. **Engine canónico** — `scripts/engine/s00_smoke..s04_normalize` + `engine/*` (config, db, identity_v1, s03, fetch, states, report). Orquestado por `engine/manifest.yaml` (versión `s0-bootstrap-v1`).
4. **Pipeline legacy** — `scripts/pipeline/run_pipeline.py` (ejecuta f1..f6). Auditoría previa lo listaba como orquestador principal, pero **el deep audit muestra f3_normalizar_cnv como muerto/No invocado**; el dominio del engine canónico lo superpone.

## 3. Orquestadores detectados (42)

Top representativo:
- `scripts/demo_txar/run_demo.py` + `run_antes.py` + `run_despues.py` (variantes).
- `scripts/deploy/sincronizar_a_produccion.py` y `deploy.py` (deploy = infra + escritura a prod).
- `scripts/engine/release_baseline.py`, `release_clasificar.py`, `screener_auditoria.py`, `homologacion_*`, `cnv_negative_pilot.py`, `cnv_incidente_forense.py`, `adversario_ratios.py`, `audit_f049/f054_f055`.
- `scripts/tickets/screener/run_all.py`, `run_update.py`, `_run_manifest.py`.
- `scripts/pipeline/run_pipeline.py`, `script_carga_externos/loader.py`.

## 4. Gráfo de ejecución real (resumen)

```text
[SCHEDULER] setup_scheduler.ps1  ─────►  run_update.py ─► fases s0..s8 ─► screener.db
                                                  ▲
[SCHEDULER?] run_all.py ──► run_screener.py ──────┘ (rebuild: DROP+CREATE)

[ENGINE] manifest.yaml ─► s00_smoke ─► s01_identity ─► s02_fetch ─► s03_parse ─► s04_normalize
        (engine/identity_v1.py, db.py, config.py, states.py, xbrlparse.py)

[PIPELINE LEGACY] run_pipeline.py ─► f1_identidad → f2_adr → f3_normalizar_cnv → f4_ratios → f5_screener → f6_sec
        (parcialmente supuesto; f3 dead, f6 = DECISION_REQUIRED)

[API] uvicorn main:app ─► POSTGRES (screener, screener_hist, silver_norm, validaciones, certificacion_nueva)
        └── [SIN GATE] publica v2 incluso si la capa de certificación no fue satisfactoria
```

## 5. Gap de ejecución (contra arquitectura oficial)

| Etapa ciclo | Estado real | Evidencia |
|---|---|---|
| DEFINIR | Contratos solo para engine (F0xx, S04, identity_v1) | docs/architecture (VERIFICADO POR CÓDIGO) |
| IMPLEMENTAR | 3 implementaciones paralelas del mismo dominio (engine vs pipeline vs screener tickets) | deep audit |
| VERIFICAR | Tests dispersos (tests/ 22, market/tests, docgen/tests); sin suite unificada por capa | evidencia escaneo |
| CERTIFICAR | Sin gate global real de certificación en la cadena de publicación | run_all: FAILED no detiene; api no exige certificación |

Gap clave **[VERIFICADO POR CÓDIGO]**:
- `api/main.py` publica sin verificar estado de CERTIFICACIÓN previa (I-… → la capa 12 no gatea sobre 10+11).
- `run_all.py` no detiene el flujo ante un FAILED (check de 572 filas es solo warning).
- `run_update.py` borra RAW (violación I-001) para forzar re-descarga (run_update.py:297-300).

## 6. Conclusiones

1. El "único entry point" no existe: conviven 4 familias. Es la causa raíz de divergencia.
2. Falta certificación global de la cadena de publicación (12 → 10+11 no gatea).
3. Solo el engine canónico tiene contrato y manifest versionado; el resto no.
4. El 41 % del código no está en git; es imprescindible fijar baseline de tracking antes de reingeniería.