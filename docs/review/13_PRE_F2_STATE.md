# 13 — Estado pre-F2 (baseline FASE 2)

Solo lectura + este documento. F1 cerrado (STEP_12 PASS_WITH_WARNINGS, NEXT_PHASE=F2).

- Rama `fix/ttm-ratios-cnv` @ `2993918`; `s04_normalize.py` M (hunks F1 + rama); `test_c11_contract.py` untracked extendido; 12_*.md presentes. Resto del árbol según 12_PRE (trabajo concurrente de rama, intacto). `[EJECUCIÓN: git]`.
- DB DEV: 127.0.0.1:5433/`catalaxia`, usuario `catalaxia_engine`, `allow_prod=False`. Schemas: derived, engine, fetch_raw, identity, identity_v1, parsed, public (+sistema). Sin schema staging (se creará solo-DEV en F2). `[EJECUCIÓN]`.
- Producción: sin acceso ni cambios (abstención; solo DEV local). Publishers (migrate/sync/s5/publicar_v2/api) y cron intactos (sin tocar desde Paso 12). C11 y `engine.certifications` intactos (solo lectura en F2).
- Migraciones existentes intactas (032/033/034 untracked, manifest modificado — no tocar).
- Aislamiento staging↔producción: hosts/usuarios distintos por configuración (DEV localhost:5433 vs prod SSH/docker según sync); F2 opera exclusivamente en DEV. Veredicto: PROCEED (staging aislable; si apareciera duda de destino: DETENER).
