# 14 — Estado pre-F3 (baseline)

Solo lectura + este documento. F2 cerrado (STEP_13 PASS, NEXT_PHASE=F3).

- Git HEAD `2993918` rama `fix/ttm-ratios-cnv`; F2 agrega (untracked): `scripts/engine/publisher.py`, `tests/test_f2_publisher.py`, `13_*.md`. Resto según 12_PRE (rama concurrente intacta). `[EJECUCIÓN: git]`.
- DB DEV 127.0.0.1:5433/`catalaxia`, `allow_prod=False`, rol app. Schema `staging` con: `_publications`, `f2_cli` (contenido A restaurado), `f2_cli__bad__*` (residuo rollback), `f2_cli__new__*` (residuo de publish bloqueado — ver auditoría), `f2_cli__prev__*`. `[EJECUCIÓN]`.
- Publicaciones registradas: 3 filas (f2_demo×tests, f2_cli×CLI); todas con `rolled_back=TRUE` (el rollback marca todas las filas del target; sin timestamp de cuándo — ver auditoría). Certificaciones: 443 filas (histórico). C10: runs Paso 12 con gates PASS. `[EJECUCIÓN]`.
- C11, RAW, publishers legacy, cron, producción: intactos, sin acceso de escritura (abstención).
- Baseline hashes/conteos: `derived.fact` run `0d9a29…` = 47.930 filas (convergentes, 0 duplicados); contenido A staging `f2_cli` hash `25d585e1…` (verificado Paso 13).
- Veredicto: PROCEED (staging aislable en DEV; F3 solo-DEV).
