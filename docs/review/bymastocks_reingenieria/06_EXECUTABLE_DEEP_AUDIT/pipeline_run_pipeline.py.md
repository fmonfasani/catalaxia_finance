# scripts/pipeline/run_pipeline.py — FICHA DEEP AUDIT

> FORMATO OBLIGATORIO. Cada afirmación lleva clase de evidencia:
> VERIFICADO POR CÓDIGO · VERIFICADO POR TEST · VERIFICADO POR EJECUCIÓN · NO DETERMINABLE.

CAPA →
PRIMARIA: EJECUCIÓN (orquestador/runner del pipeline de 14 pasos). [VERIFICADO POR CÓDIGO — subprocess encadena f1→f6 run_pipeline.py:26-42]
SECUNDARIAS: 09_PROVENANCE apenas tocada por resumen; 10_VALIDACION / 11_CERTIFICACION delegadas a pasos. No es capa de datos ni calculo: es el plano EJECUCION puro. [VERIFICADO POR CÓDIGO]

PLANOS →
- DATOS: NO procesa datos directamente; dispara cada paso vía subprocess y captura stdout. Escribe solo stdout de resumen. Indirectamente orquesta la construcción de screener_gold vía PASOS. [VERIFICADO POR CÓDIGO — run_pipeline.py:31-37]
- CONTROL: aborta en el PRIMER paso con error (sys.exit(1)) — sin salto ni parcialidad; imprime stderr[-500:] del paso fallido. NO tiene gates ni validación de transiciones entre etapas: si un paso "pasa" (returncode 0) se avanza, sin verificar invariantes. [VERIFICADO POR CÓDIGO — run_pipeline.py:35-36]
- EJECUCIÓN: entrypoint `python scripts/pipeline/run_pipeline.py` (línea de comando desde raíz); orden FIJO declarado en PASOS; subprocess hereda env + fuerza PYTHONIOENCODING=utf-8; retries/timeouts AUSENTES (sin parámetro); recuperación = re-correr el comando. [VERIFICADO POR CÓDIGO — run_pipeline.py:24-42]
- INFRA: SQLite vía .env SCREENER_DB que los pasos resolucionan; sin Docker; sin red; sin secretos en este archivo (ninguna credencial hardcodeada aquí). [VERIFICADO POR CÓDIGO — este archivo no contiene credenciales ni conexión]

CICLO →
- DEFINIR: contrato de orden NO formal; solo el docstring declara "cada paso reproducible, idempotente" y lista el orden (run_pipeline.py:3-23). No hay spec externa del pipeline. [VERIFICADO POR CÓDIGO]
- IMPLEMENTAR: respeta capa EJECUCIÓN (no calcula nada él mismo), pero NO registra etapa/checkpoint/estado (endurece nada; no hay stage_runs ni checkpoints a diferencia del runner del engine s00-smoke). [VERIFICADO POR CÓDIGO — ausencia de engine.db/stage_runs]
- VERIFICAR: sin tests asociados en repo. [VERIFICADO POR CÓDIGO — ausencia]
- CERTIFICAR: la certificación de producto la delega a pasos (validar_suite), pero el orquestador no registra certificación formal propia; solo imprime líneas con CERTIFICADO/SUITE del output. [VERIFICADO POR CÓDIGO — run_pipeline.py:44-46]

HOY → Corre los 14 pasos del camino real SQLite (f1_identidad … f6_sec) en secuencia determinista, aborta al primer error y resume la validación final + screener en stdout. NO incluye f3_normalizar_cnv (quemado como documenta el docstring); usa f3b_from_reextract. [VERIFICADO POR CÓDIGO — PASOS run_pipeline.py:26-28 lista 'f3b_from_reextract' y no 'f3_normalizar_cnv'; docstring run_pipeline.py:14]
[OBJETIVO] → El runner del engine (S00-S04) ya implementa este rol con stage_runs + checkpoints + gate + transiciones de estado (estados PASSED→CERTIFIED) e idempotencia por hash. Hoy run_pipeline es el enjambre legacy de subprocess sin gobierno de corridas.
[HOY] [VERIFICADO POR CÓDIGO]

DEPENDENCIAS → subprocess:scripts/pipeline/*.py (f1_identidad, fix_mapeo, f2_reextract_batch, f2_adr, fix_escala_anchor, fix_single_doc, fix_manual, f3b_from_reextract, f4_ratios, fix_escala_mcap, gate_autoreporte, validar_suite, f5_screener, f6_sec); env SCREENER_DB (via pasos); data/raw eef fications (fetch_dgce.py pre-requisito declarado en docstring).

CONTRATO → INPUT: estado previo de screener.db (tablas fuente ya llenas) + discrecionalidad de orden en PASOS; OUTPUT: screener_gold poblado + resumen en stdout; PRECONDICIÓN: eeff_html descargado y facts/screener cargados (docstring); POSTCONDICIÓN: screener_gold construido si todos los pasos retornan 0; INVARIANTE: I-008 IDEMPOTENCIA delegada a cada paso (el orquestador mismo no garantiza nada: si un paso no es idempotente, re-correr rompe); PROVENANCE: I-006 no la registra el orquestador (ausencia de I-006 a este nivel).

RIESGOS →
- Sin checkpoints/stage_runs: si falla paso 9 de 14, no queda registro de qué quedó hecho; re-correr re-ejecuta todo (no resume). [VERIFICADO POR CÓDIGO — run_pipeline.py:41-42; ausencia de estado persistente]
- La detección de error es SOLO returncode + cola de stderr: un paso que "pasa" pero produce datos inválidos avanza igual (no hay gate de contenido). [VERIFICADO POR CÓDIGO — run_pipeline.py:35-37]
- Aborto inmediato (sys.exit(1)) sin diferenciar error transitorio de estructural → no hay retry; requiere intervención humana. [VERIFICADO POR CÓDIGO — run_pipeline.py:36]
- Solo imprime resumen; no persiste evidencia de ejecución (run_id, timestamps, git_commit) → auditoría retrospectiva NO DETERMINABLE. [VERIFICADO POR CÓDIGO — ausencia]

DECISIÓN → (FASE 1: NO ejecutar nada) KEEP. Planificar: migrar la orquestación al runner canónico con stage_runs/checkpoints (engine/s00_smoke.py) y deprecar este enjambre legacy.

EVIDENCIA →
- VERIFICADO POR CÓDIGO: run_pipeline.py:24 (HERE); :26-28 (PASOS con f3b, sin f3_normalizar_cnv); :29-37 (run subprocess, aborto sys.exit(1) :36); :41-46 (orden + resumen validación); ausencia de settlement persistente.
- VERIFICADO POR CÓDIGO: no registra run_id ni estado (contraste: engine/db.py stage_runs+checkpoints, censo ENG016/s00_smoke.py:36-41).
- NO DETERMINABLE: si cada paso es realmente idempotente en la práctica (depende de cada script).

ESTADO: BLOCKED (orquestador sin gobierno de corridas; duplicado del runner canónico del engine).
