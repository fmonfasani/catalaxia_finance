# 18 — Estado pre-F7 (baseline, solo lectura)

F6 cerrado (STEP_17 PASS, NEXT_PHASE=F7). Solo lectura + este documento.

- Git HEAD `2993918` rama `fix/ttm-ratios-cnv`; F6 agrega `c10_evaluate.py`, `test_f6_validation.py`, `17_*`, `fase_c10/` (untracked). `[EJECUCIÓN: git]`.
- C11 actual: `c11_certificar.py` (453 líneas) con INV1 (única escritura `engine.certifications`), INV3 (veredicto+hash deterministas), INV6 (idempotencia ON CONFLICT DO NOTHING + re-lectura), INV2 (no-acoples). `cert_hash` = sha256(canónico(rule, run_id, pipeline_version, run_status, etapas_declaradas_ordenadas, stages[{id,state,gate,report}])) — sin reloj/azar; checkpoints vía report.content. `certification_id` = `c11-{run_id}` determinista. CLI `--run-id/--mode/--rule/--json-output` (default: último terminal). `[CÓDIGO]`.
- `engine.certifications`: 458+ filas DEV (CERTIFICADA YPF/KO + NEGADA cb2a + fixtures)._runs/stages/checkpoints de F4/F5 intactos. `[EJECUCIÓN]`.
- C10 evaluator (F6) verde; StageReport/`stage_runs` vigentes; runs YPF (`875b6d83…`) y KO (`6e3cf30c…`, `9a5d4205…` sin certificar) disponibles. `[EJECUCIÓN]`.
- C12 publisher + tests F2/F3; producción/legacy intactos; gaps vigentes (M5, hist-writer, TLS/auth, cron-VPS, runtime legacy).
- Veredicto: PROCEED (F7: auditoría + tests + certificaciones DEV explícitas; sin tocar C10/C12/datos).
