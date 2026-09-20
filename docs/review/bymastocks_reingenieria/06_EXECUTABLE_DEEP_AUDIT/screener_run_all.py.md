# scripts/tickets/screener/run_all.py — FICHA DEEP AUDIT

> FORMATO OBLIGATORIO. Cada afirmación lleva clase de evidencia:
> VERIFICADO POR CÓDIGO · VERIFICADO POR TEST · VERIFICADO POR EJECUCIÓN · NO DETERMINABLE.

CAPA →
PRIMARIA: ORQUESTADOR transversal (01_FUENTES → 02_NORMALIZED → 04_PARSED → 08_RATIOS → 10_VALIDACION → 11_CERTIFICACION → 12_PUBLICACION). [VERIFICADO POR CÓDIGO — run_all.py:9-22, 176-205]  
SECUNDARIAS: NO aplica a una sola capa: es el conductor E2E `EXTRACT → TRANSFORM → ASSEMBLE → EXPORT` que invoca ~17 módulos. No es una capa de dominio, es un plano de EJECUCIÓN. [VERIFICADO POR CÓDIGO]

PLANOS →
- DATOS: DB `data/screener.db` (run_all.py:49); EXTRACT baja EDGAR (construir_base us/adr) + ADR (sec_adr_ratios) + CNV discovery bajo `--with-cnv-fresh`; EXPORT llama `s5_exportar` → `data/screener_export.csv`; manifiesto en `data/logs/runs/<run_id>.manifest.json` (run_all.py:302-315). [VERIFICADO POR CÓDIGO]
- CONTROL: manifiesto G4 con git sha, args, resultado por stage y hash del snapshot pre-run (run_all.py:38-39, 299-317). Verificación final: espera 572 filas en `screener` pero es solo ADVERTENCIA, no gate (run_all.py:294-295). NO hay gates que frenen etapas ante FAILED (RIESGOS 1).
- EJECUCIÓN: orquestador con argparse y main guard (run_all.py:324-325); log por corrida `data/logs/runall_*.log` (run_all.py:60-75); `time.sleep(1.2)` entre fases por lock SQLite (run_all.py:209); flags `--skip-extract/--skip-transform/--offline/--only/--force-refresh/--with-cnv-fresh` (run_all.py:224-232). [VERIFICADO POR CÓDIGO]
- INFRA: SQLite local + filesystem + RED (EDGAR, CNV, yfinance/ADR); timeouts (CNV jobs timeout=1800s); `_cnv_reachable()` guarda CNV (run_all.py:100-107). [VERIFICADO POR CÓDIGO]

CICLO →
- DEFINIR: reconstrucción E2E desde scratch, idempotente, con manifiesto reproducible (run_all.py:3-42). [VERIFICADO POR CÓDIGO]
- IMPLEMENTAR: 4 stages en orden canónico (run_all.py:253); invalidación por fecha (nunca "si ya tengo, salto") en EDGAR (run_all.py:10-13, 120-126). [VERIFICADO POR CÓDIGO]
- VERIFICAR: chequeo final de conteo 572 NO es vinculante (solo warn, run_all.py:294-295); no aborta si un stage falla (RIESGOS 1). [VERIFICADO POR CÓDIGO]
- CERTIFICAR: el manifiesto etiqueta la corrida (reproducibilidad) pero no certifica datos; certificación delegada a s7/s8 (validar_suite/guards). [VERIFICADO POR CÓDIGO]

HOY → Orquesta FASE 4 end-to-end: EXTRACT (EDGAR companyfacts con invalidación por fecha + ADR + CNV opcional) → TRANSFORM (calcular_ratios_base + precios_y_valuacion, deben ir SIEMPRE juntos) → ASSEMBLE (s0→s2→s3→s3b→s3c→s4→s6→s7→s7b→s7c→s8→s9 + cedear/jpm/instrumentos) → EXPORT (s5 → data/screener_export.csv). Registra manifiesto de corrida con resultado por stage y hash del snapshot. Sin fallback de datos CNV: solo se re-descubre con `--with-cnv-fresh`; si está caído se reusa cache `cnv_estados_v2`. [VERIFICADO POR CÓDIGO — run_all.py:114-215]
[OBJETIVO] → Inyectar GATES reales entre stages y entre fases del assemble (que un FAILED detenga el flujo aguas abajo), convertir el chequeo de 572 filas en un gate opcional y cerrar el mismatch doc/código de `--offline`.
[HOY] [VERIFICADO POR CÓDIGO]

DEPENDENCIAS → DB:screener.db (existencia obligatoria, aborta si no existe run_all.py:244-247); módulos del pipeline: construir_base, sec_adr_ratios, calcular_ratios_base, precios_y_valuacion, s0_normalizar_cnv, s1_bimoneda, s2_ratios_cnv, s3_precios, s3b_precios_historicos, s3c_refrescar_precios, s4_ensamblar, s5_exportar, s6_ajustes, s7_unificar, s7b_eps_base_per, s7c_cagr, s8_calidad, s9_guards_yfinance, cedear_ratios, jpm_adr, instrumentos; `_run_manifest.escribir` (edges_internal línea 341); red EDGAR/CNV/yfinance. [VERIFICADO POR CÓDIGO — run_all.py:123-205, 302]

CONTRATO →
- INPUT: flags CLI + estado de `data/screener.db` (+ raw cache para skip-extract).
- OUTPUT: `screener` poblada (meta 572 filas), `data/screener_export.csv`, manifiesto `<run_id>.manifest.json` (git sha, args, resultado por stage, hash snapshot pre-run), log `runall_<ts>.log`.
- PRECONDICIONES: `data/screener.db` existe (run_all.py:244-247); para EXTRACT completo, conectividad EDGAR/CNV/ADR; para `--skip-extract`, raw cache (facts+cnv en DB).
- POSTCONDICIONES: tabla `screener` reconstruida (idempotente, cada stage recrea su salida); producto exportado; corrida trazada por manifiesto.
- INVARIANTES: I-001 RAW inmutable (preservado: extract usa raw cache/download sin re-bajar lo ya presentado); I-006 PROVENANCE (manifiesto con git sha + hash snapshot + resultado por stage; PARCIAL — no registra hash de cada tabla intermedia); I-007 DETERMINISMO (depende de cada módulo; el orquestador no garantiza byte-repro por los `today()` internos de fases como gen_screener_html); I-008 IDEMPOTENCIA (sí: cada stage reconstruye su salida, run_all.py:24). [VERIFICADO POR CÓDIGO]

RIESGOS →
1. Sin GATES reales entre stages: `stage_*` llaman `_run_module` y siguen aunque el resultado sea FAILED (run_all.py:78-97, 206-209); solo hay resumen final + `sys.exit(1 if n_fail>0)` (run_all.py:321). Un fallo en s4 (ensamblar AR) deja que s6/s7/s8 corran sobre datos incompletos y que el EXPORT s5 publiquen un `screener_export.csv` con filas faltantes, sin detener el flujo (P0). [VERIFICADO POR CÓDIGO — run_all.py:206-215, 257-272, 321]
2. Chequeo de 572 filas solo como ADVERTENCIA (run_all.py:294-295): un universo corto se exporta y manifiesta de todos modos como exitoso (P1). [VERIFICADO POR CÓDIGO]
3. Mismatch doc/código en `--offline`: docstring dice "transform solo si hay red" (run_all.py:33) pero el código solo fija `skip_extract=True` y corre transform igual (run_all.py:235-237), pudiendo producir ratios con datos desactualizados/sin red (P2). [VERIFICADO POR CÓDIGO]
4. TRANSFORM frágil por acoplamiento no atómico: `calcular_ratios_base` DROPEA `per` y `precios_y_valuacion` la recrea; el orquestador avisa si el segundo falla (run_all.py:165-167) pero no aborta y puede quedar `ratios` sin `per` corrompiendo s6/s7 (P1). [VERIFICADO POR CÓDIGO — run_all.py:159-167]
5. Sin manejo de fallo de CNV como dato: si CNV está caído solo se registra SKIP en extract (run_all.py:150-152) y ASSEMBLE usa `cnv_estados_v2` cacheado sin validar antigüedad; no hay fallback con aviso duro (P1). [VERIFICADO POR CÓDIGO]
6. `--only <stage>` puede correr sobre DB no reconstruida (p.ej. `--only export` con `screener` vacía) sin gate de precondición por stage (P2). [VERIFICADO POR CÓDIGO — run_all.py:254-272]

DECISIÓN → (FASE 1: NO EJECUTAR NADA) **KEEP con revisión** (censo: KEEP). Acción a planificar: añadir gates (abort/recovery) entre stages y entre fases del assemble basados en `FAILED`; promocionar el chequeo 572 a gate opcional; alinear doc/código de `--offline`; validar antigüedad del cache CNV.

EVIDENCIA →
- VERIFICADO POR CÓDIGO: run_all.py:9-22 (orden canónico); :78-97 (_run_module captura FAILED sin abortar); :100-107 (_cnv_reachable); :123-152 (EDGAR invalidación por fecha + CNV under with_cnv_fresh); :159-167 (transform acoplado con aviso); :176-209 (fases assemble + sleep lock); :235-237 (offline→skip_extract); :244-247 (aborta sin DB); :294-295 (warn 572); :299-321 (manifiesto + exit code).
- VERIFICADO POR EJECUCIÓN: CENSO PIP030 (corrida E2E FASE 4, reconstrucción base; manifiesto generado).
- NO DETERMINABLE: test de gates (no existen); comportamiento exacto en un caso real de FAILED intermedio.

ESTADO: **DECISION_REQUIRED** (orquestación sólida con manifiesto, pero sin gates: un FAILED intermedio puede publicar un producto incompleto como exitoso — P0).

