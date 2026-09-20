# scripts/tickets/screener/run_update.py — FICHA DEEP AUDIT

> FORMATE OBLIGATORIO. Cada afirmación lleva clase de evidencia:
> VERIFICADO POR CÓDIGO · VERIFICADO POR TEST · VERIFICADO POR EJECUCIÓN · NO DETERMINABLE.

CAPA →
PRIMARIA: 13_ORQUESTACION / PLANO EJECUCIÓN (orquestador de jobs periódicos). [VERIFICADO POR CÓDIGO — monorepo de modos --daily/--monthly/--quarterly/--annual/--rebuild en main() run_update.py:668-755; census SCRB021]. Es un orquestador CROSS-CAPAS, no una capa única del harness de 12.
SECUNDARIAS: 01_FUENTES (yfinance/EDGAR/CNV/IPC) [VERIFICADO POR CÓDIGO — run_update.py:85-109, 220-306, 341-361]; 03_RAW (descarga/gestión de crudos) [VERIFICADO POR CÓDIGO — 293-300]; 10_VALIDACION (stateness/count checks) [VERIFICADO POR CÓDIGO — 311-322, 364-392, 469-545]; 12_PUBLICACION (rebuild del screener que la API sirve) [VERIFICADO POR CÓDIGO — 562-599].

PLANOS →
- DATOS: SQLite `data/screener.db` multi-tabla (screener, precios, ratios, empresas, cnv_estados_v2) [VERIFICADO POR CÓDIGO — DB=ROOT/data/_os.environ.get("SCREENER_DB","screener.db") run_update.py:39]; CSV ipc_nacional (OVERWRITE) [run_update.py:197-203]; archivos de estado/log JSON y txt (cnv_last_status.json, log_job5_v2_done.txt, upd_*.log) [run_update.py:40, 332, 383-391, 496-503]; RAW EDGAR companyfacts/submissions en `data/raw` [run_update.py:293-300].
- CONTROL: respeta SCREENER_DB para apuntar a copia de prueba [comentado run_update.py:36-39]; rate-limit SEC (10 r/s, sleep) [275]; reintentos+backoff CNV [341-361]; DIFERIMIENTO (si CNV caído no arrastra dato viejo silencioso) [424-435, 505-545]; verificación de conteo tras extracción [529-535]; logging persistente por corrida [60-78].
- EJECUCIÓN: entrypoint CLI argparse; ThreadPoolExecutor (6 workers precios / 10 EDGAR) con as_completed (orden no determinista, filas independientes) [138-142, 265-275]; subprocess a jobs CNV (job2/job3/job4/job5_v2) [419-519]; larga cadena s0→s8→s5 [562-581].
- INFRA: SQLite local; red a yfinance/SEC/CNV/datos.gob.ar; subprocess a scripts legacy; sin contenedor/checkpoint de pipeline.

CICLO →
- DEFINIR: modos periódicos documentados en header [VERIFICADO POR CÓDIGO — run_update.py:1-19].
- IMPLEMENTAR: acopla EXTRACCIÓN + RAW + PARSING + RATIOS + PUBLICACIÓN en UN solo script [VERIFICADO POR CÓDIGO].
- VERIFICAR: validaciones de conteo/staleness intra-script, pero SIN tests unitarios propios ni gate formal del harness [NO DETERMINABLE — no hay test_ en census/evidence para run_update].
- CERTIFICAR: NO DETERMINABLE — no emite certificación; solo logs y conteos.

HOY → Ejecuta todos los updates periódicos del screener legacy en un único monolito: refresca precios yfinance (--daily), IPC INDEC→overwrite CSV (--monthly), incremental EDGAR (detect→re-download→recompute) + CNV subset discovery via subprocess (--quarterly), ratios ADR (--annual), y rebuild completo s0→s8→s5 (--rebuild/--quarterly). Escribe directamente en screener.db y sobrescribe artifacts. [VERIFICADO POR CÓDIGO]
OBJETIVO → Bajo la arquitectura del harness, cada fase de capa (fetch→raw→parse→normalize→ratio→publish) debería ser un ejecutable desacoplado con gates y checkpoints (estilo runner engine s00-s04), y este script quedar reducido a un disparador/orquestador que respete las invariantes I-001/I-006/I-008 y use la capa CNV/identity canónica. [VERIFICADO POR CÓDIGO — comparativa con engine/s0x y census ENG016-020]

DEPENDENCIAS → DB:screener.db (screener, precios, ratios, empresas, cnv_estados_v2); API:yfinance; SEC:data.sec.gov (submissions/companyfacts); CNV:www.cnv.gov.ar, aif2.cnv.gov.ar; datos.gob.ar (IPC); scripts internos: construir_base, calcular_ratios_base, sec_adr_ratios; subprocess: jobs CNV job2..job5_v2; filesystem:data/raw, data/ipc_nacional.csv, data/logs.

CONTRATO → INPUT: flags --daily|--monthly|--quarterly|--annual|--rebuild|--quiet. OUTPUT: DB actualizada + logs upd_YYYYMMDD.log + cnv_last_status.json + ipc_nacional.csv. PRECONDICIONES: screener.db con tablas/CIKs sembradas; red a fuentes; SCREENER_DB opcional para aislar. POSTCONDICIONES: precios refrescados (INSERT OR REPLACE), ratios reconstruidos, CNV incremental aplicado o diferido, screener rebuilt. INVARIANTES VIOLADAS/PARCIALES: I-001 RAW INMUTABLE VIOLADO — borra físicamente crudos para forzar re-descarga (run_update.py:297-300 "delete stale cache to force re-download"). I-008 IDEMPOTENCIA: parcial (precios INSERT OR REPLACE idempotente; IPC overwrite no versionado; rebuild no transaccional). I-007 DETERMINISMO: parcial (as_completed no determinista en orden, pero por-fila). PROVENANCE (I-006): parcial — logs de corrida, pero sin fingerprint/vinculación formal dato↔fuente.

RIESGOS →
1. VIOLACIÓN I-001 RAW INMUTABLE: borra `raw/companyfacts/CIK#.json` y `raw/submissions/CIK#.json` para forzar re-descarga. Esto destruye el RAW previo (la "verdad") — contradice el principio 2 de la filosofía y el invariante RAW inmutable. [VERIFICADO POR CÓDIGO — run_update.py:297-300]
2. Monolito cross-capa: un único script hace fetch+descarga+parse+ratio+publish+red, rompiendo la separación de responsabilidades del harness; un cambio en una fase arrastra todo. [VERIFICADO POR CÓDIGO — estructura global]
3. --monthly DESCARTABLE silenciosamente: sobrescribe ipc_nacional.csv sin versionado ni backup (capa 03/05 derivado destruye el anterior). [VERIFICADO POR CÓDIGO — run_update.py:197-203]
4. Rebuild no transaccional y sin gate: encadena fases s0→s5; si una falla, marca OK=parcial y CONTINÚA (no aborta/rollback), pudiendo publicar screener a medio construir. [VERIFICADO POR CÓDIGO — run_update.py:582-598]
5. Verificación de producción por conteo únicamente (CNV extracción y rebuild): el propio código admite que conteo=sí no implica contenido correcto (ver hallazgo documentado en sincronizar: 572==572 pero columnas vacías). [VERIFICADO POR CÓDIGO — run_update.py:529-535, 630-631]
6. subprocess a jobs CNV legacy duplicando lógica con discovery.py canónico; divergencia de clasificación. [VERIFICADO POR CÓDIGO — run_update.py:325-337 vs engine/cnv/discovery.py; census CNVX038/039]

DECISIÓN → (FASE 1: NO ejecutar nada). REVIEW (prioridad alta). Planificar: (a) detener el borrado de RAW (I-001) y versionar descargas en data/raw/ con fingerprint; (b) desacoplar el monolito en fases con gates, o acotarlo a orquestador que delegue en ejecutables de capa; (c) transaccionalidad/rollback del rebuild; (d) no sobreescribir ipc sin versionar; (e) migrar CNV subset a la cadena discovery canónica.

EVIDENCIA → VERIFICADO POR CÓDIGO: run_update.py:39 (SCREENER_DB); :85-162 (upd_precios, INSERT OR REPLACE 152-157); :172-206 (upd_ipc overwrite 197-203); :220-278 (upd_edgar_detect, rate limit 275); :281-308 (re_download_edgar, BORRADO RAW 297-300); :311-322 (recompute ratios); :341-361 (retry CNV); :364-392 (staleness/status); :394-559 (cnv_discovery_subset, diferimiento 539-545); :562-599 (rebuild, continue-on-fail 582-598); :668-755 (main flags, exit 1 si errors 755). VERIFICADO POR TEST: NO DETERMINABLE (sin tests unitarios propios). VERIFICADO POR EJECUCIÓN: NO DETERMINABLE. NO DETERMINABLE: certificación de las tablas de salida.

ESTADO: DECISION_REQUIRED (viola I-001 borrando RAW, monolito cross-capa, sin transaccionalidad ni gates; requiere acción planificada antes de uso en producción).
