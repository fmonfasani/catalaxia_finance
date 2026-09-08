# 19 — Estado pre-F8 (baseline, solo lectura)

F7 cerrado (STEP_18 PASS, NEXT_PHASE=F8). Solo lectura + este documento.

- Git HEAD `5b20266` (rama movió: reorganización docs) rama `fix/ttm-ratios-cnv`; F7 agrega `test_f7_certification.py` + `18_*` (untracked). `[EJECUCIÓN: git]`.
- Componentes: C10 (`c10_evaluate.py`, 9 invariantes, solo-lectura) · C11 (`c11_certificar.py` + `engine.certifications`) · C12 (publisher staging + gate; s5/sync/migrate/api intactos). Contratos: C10→C11 (PASS→puede, BLOCK→no, WARN→puede con alcance, ausente→no) vigentes. `[CÓDIGO]`.
- Últimos E2E reales: `ffcbf97a…`, `feba6dbe…`, `fd57f77a…` (OK; actividad DEV concurrente de rama). YPF/KO golden con CERTIFICADA. `[EJECUCIÓN]`.
- No-terminales: solo fixtures `test-c11-contract` con padres terminales (residuo de diseño de tests NEGADA, no F-009 vivo: cero runs RUNNING). c11/C10 usan max(id) por etapa+run → sin confusión. `[EJECUCIÓN]`.
- Staging: 7 publicaciones (5 rolled_back). Gaps abiertos: S03-replace (BLOCKER condicional), M5, hist-writer, TLS/auth, cron-VPS, runtime legacy. DEV Docker local; producción intacta.
- Veredicto: PROCEED (E2E YPF fresco + cadena C10→C11→C12 staging).
