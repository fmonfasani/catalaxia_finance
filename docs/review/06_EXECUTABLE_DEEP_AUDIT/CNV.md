# Ficha: CNV — run_update, run_all, run_screener, jobs v2 (+v1)

### COMPONENTE: run_update.py — P-SCR-UPDATE (cron productivo)

#### Identificación
- Path: `scripts/tickets/screener/run_update.py` · Orquestador FASE 3 · Capa C7 (orquesta C3–C12) · Planos EJECUCIÓN+CONTROL+DATOS
- Entry: `__main__` con `--daily/--monthly/--quarterly/--annual/--quiet`; exit = nº errores (:782)
- Estado: **PRODUCTIVO CONFIRMADO** (cron setup_vps.sh + logs upd_20260709 + artefactos)

#### Responsabilidad
- daily: yfinance precios/52w/market_cap 571 tickers (<5 min, idempotente). monthly: IPC INDEC (datos.gob.ar, serie 145.3..., overwrite `ipc_nacional.csv`). quarterly: EDGAR incremental (lastFiled vs fecha_facts) + CNV subset 72 cuits (job2→3→4→5_v2, resume-safe) + rebuild s0→s8→s5. annual: sec_adr_ratios vs 20-F nuevo. Código = documentación del header.

#### Inputs/Outputs/Writers
- In: yfinance, requests (EDGAR/CNV/datos.gob.ar), `construir_base.descargar_empresa`, `_raw_inmutable.*`, env SCREENER_DB, args de modo.
- Out/tablas: `precios`, `facts/empresas` (incremental), `cnv_estados*` (vía jobs), `screener` + export (vía rebuild), `ipc_nacional.csv`, `ingesta_log`, `upd_*.log`.
- Writers directos + delegados (subprocess/`__import__`); destructividad delegada (DROPs de etapas hijas).

#### Dependencias / Capa / Planos / Provenance / Validación / Idempotencia
- IMPORT dinámico (`__import__` rebuild) + SUBPROCESS jobs (cwd=CNV_JOBS) + yfinance/requests + sqlite3.
- CAPA PRIMARIA C7 (mezcla contractual de orquestador). Provenance PARCIAL (logs + ingesta; sin run_id motor). Validación: propaga errores (exit=errores), no certifica. Idempotencia PARCIAL (daily idempotente; quarterly incremental con resume-safe).

#### Errores / Seguridad / Producción / Riesgo
- Errores por etapa con traceback en log; exit code = conteo (monitoreable por cron). Sin retries propios (sleep en jobs).
- Seguridad: HTTP (SEC/CNV/datos.gob.ar/yfinance); jobs CNV con `verify=False` (heredado al quarterly) → **hallazgo R3-parcial** (ver §21 índice). Sin secretos hardcodeados.
- PRODUCTIVO CONFIRMADO. **Riesgo: R3 — ALTO** (orquestador productivo + red externa + TLS deshabilitado en jobs + escrituras multi-tabla; mitigado por logs/exit codes, sin mitigar TLS).

### COMPONENTE: run_all.py — P-SCR-ALL (ALTERNATIVO)
- EXTRACT (construir_base + jobs job1→7 + sec_adr_ratios) → TRANSFORM (calcular+precios, orden obligatorio) → ASSEMBLE (s0..s9) → EXPORT (s5). Flags --skip/--only/--offline/--with-cnv-fresh/--force-refresh. Manifest `_run_manifest`. Sin cron/caller productivo → ALTERNATIVO. Misma destructividad delegada. Riesgo R2 (manual, universo completo).

### COMPONENTE: run_screener.py — P-SCR-SCREENER (ALTERNATIVO)
- 6 phases por `__import__` (s0/s2/s3/s4/s6/s7/s8/s5) con gates entre fases. Sin subprocess CNV (usa lo extraído). ALTERNATIVO. Riesgo R2.

### COMPONENTES: job5_v2_extract_eeff.py / job6_v2_reparse_div.py (+ v1, jobs 1–4, 7, 8)
- job5_v2: extrae EEFF del portal CNV → `cnv_estados_v2`; resume-safe por `data/log_job5_v2_done.txt` (GUIDs procesados; re-procesa si HTML existe pero no está en DONE); sleep trottling; `requests ... verify=False` **(TLS deshabilitado, :264)**; CLI --cuits/--max/--sleep/--rango.
- job6_v2: reparse dividendos → `cnv_dividendos`.
- v1 (job5/job6 sin _v2): misma CLI/tablas, sin caller productivo (solo docstring build_subset) → LEGACY paralelo (D7).
- jobs 1–4 (universo/download/formtype/clasificar), job7 (validación + DELETE suspects acotado), job8 (doc_meta), build_subset (subset 72): etapas con cwd=CNV_JOBS obligatorio (paths relativos) — dependencia oculta de directorio.
- Provenance: DONE-file + manifest (PARCIAL; sin hash — asimetría vs c3 `hash_cnv`).
- Idempotencia: PARCIAL (resume-safe; re-fetch posible).
- Destructividad: job7 DELETE `cnv_estados/suspect` (acotado, regenerable).
- Tests: `_test_v2.py` (unitario de parsing, TEST EXISTE). Producción: vía run_all/run_update → PRODUCTIVO PROBABLE (v2), LEGACY (v1).
- Riesgo: **R3** job5_v2/job2 (red + verify=False + escritura productiva); R1 resto.

### Veredicto auditoría CNV especial
- C3 produce: RAW CNV + manifest + provenance PG. v1 produce: (legacy, sin caller). v2 produce: `cnv_estados_v2` + `cnv_dividendos` (producto). Consumen: s0/s2 (v2) ; auditoría (c3). RAW CNV: c3 (RawStore) + job2 (fs). Estados: job4/job5_v2/job7. Facts CNV→SQLite: construir_base? no — CNV facts viven en `cnv_estados*` (03 §2.4). Al producto llegan vía rebuild/assemble (quarterly confirmado).
- Fallos DONE: el DONE-file marca **éxito de procesamiento**, no de calidad (un GUID con HTML vacío queda DONE si se registró — verificar ante Paso 7 si existe validación de contenido; `parse/factor_unidad` existe en `_test_v2`, cobertura parcial).
- v1/v2: v2 vigente en todos los caminos productivos; v1 sin caller → D7 CONFIRMADA.
