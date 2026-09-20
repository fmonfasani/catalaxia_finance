# Ficha: E2E — e2e_orchestrator.py (+ e2e_producto, idempotencia, mutación)

### COMPONENTE: e2e_orchestrator.py

#### Identificación
- Path: `scripts/engine/e2e_orchestrator.py`
- Tipo: orquestador (subprocess s00→s04, run_id compartido)
- Entry point: `__main__` → `raise SystemExit(main())` (s02:201-patrón; e2e:201)
- Capa primaria: C10 VALIDACIÓN (orquestación con gates) / EJECUCIÓN
- Plano primario: CONTROL + EJECUCIÓN
- Estado: PRODUCTIVO PROBABLE (tests E2E; sin cron)
- Evidencia: `[CÓDIGO]` STAGES + subprocess.run:124; `[TEST]` test_e2e_orchestrator (+integration); `[EJECUCIÓN]` py_compile OK; `--help` sale 1 sin efectos (argparse-level, §17)

#### Responsabilidad
- Debería/hace: crear o reutilizar `engine.runs` (PIPELINE_VERSION e2e-sec-edgar-v1), ejecutar los 5 stages como subprocess propagando `ENGINE_E2E_RUN_ID`, abortar ante BLOCK/fail, exit 0/1. Sin diferencias.
- STAGES fijos: s00_smoke, s01_identity, s02_fetch_ypf, s03_parse_ypf, s04_normalize (YPF-only por filenames).

#### Inputs / Outputs
- In: `.env`, `engine.runs` (historial/reuso), args `--run-id`, `--mode FAST`. Out: `engine.runs` (INSERT/UPDATE estado), logs stdout, exit code.

#### Writers / Readers
- Writers: `engine.runs` (único writer de corridas E2E). Readers: c11, tests.

#### Dependencias
- IMPORT engine.db/config · SUBPROCESS ×5 (sys.executable + script path) · READ/WRITE_DB engine.runs · ENV ENGINE_E2E_RUN_ID (propagación) · EXECUTION_ORDER fijo.

#### Capa / Planos
CAPA PRIMARIA = C10 (orquestación validada). Secundaria C9. DATOS no; CONTROL sí; EJECUCIÓN sí; INFRA no.

#### Provenance / Validación / Idempotencia
- Provenance PARCIAL-propia (el run agrupa; el detalle vive en cada stage) — COMPLETA por composición.
- Validación: continúa solo si PASS; reuso de run existente verificado contra `engine.runs` (e2e:87-96).
- Idempotencia PARCIAL (delega en stages; re-correr re-ejecuta stages idempotentes).

#### Destructividad
- Ninguna propia (no borra; crea runs).

#### Errores
- Propaga exit codes de stages; error si run_id inexistente. Sin retry entre stages (re-lanzamiento manual con --run-id). Riesgo medio-bajo.

#### Seguridad / Producción
- Sin secretos; ejecuta intérprete local con paths del repo (sin shell=True verificado en el extracto: `subprocess.run` con lista). PRODUCTIVO PROBABLE (sin cron).

#### Contrato / Doc-vs-código / Ocultas / Ownership / Duplicación / Riesgo
- Contratos: INPUT/OUTPUT/STATE IMPLEMENTADOS; ERROR PARCIAL; PROVENANCE PARCIAL; IDEMPOTENCIA PARCIAL.
- Sin divergencias. Oculta: cada stage debe estar en `scripts/engine/` con ese nombre (acoplamiento por path).
- Ownership coherente con 03 §10. Duplicación 05 G15 (vs run_pipeline): D1/D7 — CONFIRMA (mismo mecanismo, distinto dominio).
- **Riesgo: R2 — MEDIO** (punto único de orquestación SEC; sin retry; YPF-only hardcodeado por STAGES).

### COMPONENTE: e2e_producto.py (anexo, TEST/auditoría)
- Solo lectura (declara no escribir DB); cadena EMPRESA→...→PROVENANCE sobre 8 tickers; lee ratio_defs/ratio_inputs + market_*; escribe `outputs/docs/fase_*`. PRODUCTIVO: NO (TEST). Riesgo R1 (read-only; verificado por declaración + imports de lectura).

### COMPONENTES: idempotencia_engine.py / mut_f054_f055.py (anexo, TEST)
- Re-ejecutan S03/S04 (N veces / mutado `_mutado_tmp.py`). Cubiertos por f050/f054/f055 (42 passed). TEST. Riesgo R0 (harness).
