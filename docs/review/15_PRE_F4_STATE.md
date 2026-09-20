# 15 — Estado pre-F4 (baseline)

Solo lectura + este documento. F3 cerrado (STEP_14 PASS, NEXT_PHASE=F4).

- Git HEAD `2993918` rama `fix/ttm-ratios-cnv`; F2/F3 agregan (untracked): `publisher.py`, `test_f2/f3_publisher/recovery.py`, `13_*`/`14_*`. Resto según 12_PRE (rama concurrente intacta). `[EJECUCIÓN: git]`.
- Stages: s00–s04 + e2e_orchestrator (YPF-golden s01–s03; s04 genérico). Golden YPF = CIK 0000904851 verificado en DEV (2 E2E PASS + C11 CERTIFICADA, Paso 12). `[EJECUCIÓN]`.
- Identity V0 (s01, `identity.*`) + V1 (`identity_v1.*`, assertions); s04 exige V1 (gate C-S04-004). `[CÓDIGO]`.
- RAW SEC (YPF submissions/companyfacts, `fetch_raw.download_log` 748 filas históricas), `parsed.facts` 67.084, `derived.fact` 47.930 (convergentes 0 duplicados). `[EJECUCIÓN]`.
- Control: 998 runs, 2.982 stage_runs, 145 checkpoints, 458 certificaciones (histórico + fixtures). `[EJECUCIÓN]`.
- Publisher staging + tests F2/F3 verdes (STEP_13/14 PASS). DEV 127.0.0.1:5433 `allow_prod=False`; producción intacta.
- Veredicto: PROCEED (alcance R7.4/C2–C5, solo-DEV).
