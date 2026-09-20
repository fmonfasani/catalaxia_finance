# 15 — F4 Multiemisor SEC (YPF + KO)

Pipeline genérico SEC + YPF como Golden Case, demostrado con segundo emisor real (KO). Solo DEV (127.0.0.1:5433, allow_prod=false). Sin forks, sin deletes, sin tocar producción/C11-C12/publisher/legacy/CNV/Market. Evidencia `[CÓDIGO]`/`[TEST]`/`[EJECUCIÓN]`/`[NO DETERMINABLE]`.

## 1. Matriz de generalización (PASO 1)

| Componente | Genérico (ya) | YPF-specific | Parametrizable → parametrizado en F4 |
|---|---|---|---|
| s00_smoke | todo (sin marcas YPF) | nada | n/a |
| s01_identity | maquinaria stage + 3 checks catálogo | `resolve_golden_ypf` + `check_golden_ypf` (nombre/tickers) | **SÍ**: `--cik` nuevo; genérico usa `resolve_por_cik` (existe en engine.identity); expected 4→3 |
| s02_fetch_ypf | Fetcher, gates, `--cik/--forms/--max-filings` (ya existían) | default GOLDEN_CIK, `SCOPE_RULE` label, lookup S01 por global | **SÍ**: lookup con cik explícito (cero cambio de conducta); SCOPE ya dinámico |
| s03_parse_ypf | parse XBRL, parsed.*, gates, `--cik/--min-xbrl` (ya existían) | default GOLDEN_CIK, default volumen 9, `S03_YPF_PARSE_AUDIT.xlsx` fijo | **SÍ**: filename por CIK (evita overwrite cruzado); defaults intactos |
| s04_normalize | todo (resuelve por identity_v1) | nada | n/a |
| e2e_orchestrator | maquinaria + prod-guard | STAGES sin argv (siempre YPF efectivo) | **SÍ**: `--cik/--forms/--min-xbrl` + `extra_por_stage` (defaults = conducta YPF idéntica) |

NO parametrizable (correctamente): gates golden YPF (quedan como caso), LEGACY_FORBIDDEN_CIKS (seguridad genérica), StageReport/contratos, idempotencia ON CONFLICT.

## 2. Segundo emisor (PASO 2): KO — The Coca-Cola Company, CIK 0000021344

Justificación con evidencia: precedente golden-run KO en git (`3e85c10`, 45.113 facts/17 filings sin tocar core, base aislada) `[EJECUCIÓN-histórica]`; RAW presente (`data/raw/engine/CIK0000021344`); identidad resuelta en v0 (`CIK:0000021344`/`COCA COLA CO`) y v1 (`E01M1W68XDCYY7AS1STHXKH084Z`) `[EJECUCIÓN]`; contraste estructural (10-K doméstico USD vs 20-F extranjero; consumo vs energía); complejidad mínima para la prueba.

## Contrato multiemisor (PASO 3) y diseño (PASO 4)

`scripts/engine/issuers.py` (SOLO DATOS, sin imports de lógica): `{issuer_key, legal_name, cik, jurisdiction, identifiers[], forms[], min_xbrl, golden}` para YPF (20-F, min 9) y KO (10-K, min 5). Separación: IDENTIDAD (identity.*) / CONFIG (issuers) / PARSING (stages). Diseño: funciones comunes + config + Golden tests; `run(emisor=X)` sin `sXX_ko.py` (test O lo prohíbe).

## 3. Cambios de código

`issuers.py` (nuevo, ~60 líneas) · `s01_identity.py` (+argparse `--cik`, rama genérica, expected dinámico) · `s02_fetch_ypf.py` (cik explícito en lookup; 2 líneas) · `s03_parse_ypf.py` (xlsx por CIK; 2 líneas) · `e2e_orchestrator.py` (+3 args, tabla `extra_por_stage`, import issuers). Mantenimiento de tests exigido por convergencia (ver §7): `_run_cert()` dinámico en test_f2/f3 (fin del treadmill de run_id fijo) + J2 multi-run. Lógica financiera, C6/C7/C8, publisher, C10/C11/C12: intactos. `[CÓDIGO]`.

## 4. Tests (A–O, 17/17 PASS) + 5. Ejecución DEV

- YPF E2E post-cambio PASS (`875b6d83…`, 47.930 facts) `[EJECUCIÓN]` (A).
- KO E2E ×3 PASS (`6e3cf30c…`, `682c102c…`, `97ea2aaf…`, `9a5d4205…` restore): S01→S04 gates PASS (B–E); CIK exacto (F); entity_key `E01M1W68…` (G); provenance completa `source_fact_ids`+`input_checkpoint_id` 100% (H); 0 orphans (I); idempotencia hash_out idéntico `eedb7af3…` + 0 duplicados (J); convergencia último-escritor multi-run (J2); cero mezcla (KO⇄YPF) + RAW KO propio (K); config inválida/CIK inexistente → BLOCK exit 1 (L/M); filing inexistente → cadena bloquea (N, ver nota); C11 CERTIFICADA en runs KO (05c14727, 658b8160) + restore (C11 test).
- Nota N: la versión e2e-live del test demostró el bloqueo pero su s03 con 0 filings reemplazó parsed-KO (diseño preexistente delete+insert por entidad, s03:454) huerfanizando 90.398 punteros; se restauró con re-run (dangling 0) y el test quedó en versión s02 no-destructiva. Hallazgo GENERIC GAP (no KO-específico) registrado en §10. `[EJECUCIÓN]`+`[TEST]`.

## 6. Provenance / 7. Idempotencia / 8. Contaminación

Provenance KO completa (H) con checkpoints E2E + `stage_runs.report` + C11. Idempotencia: hash_out idéntico entre corridas consecutivas + convergencia sin duplicados (J/J2). Contaminación: cero hechos cruzados, RAW por directorio CIK, identidad 1+1 entidades KO, resolve genérico solo-lectura (s01/s02 sin writes salvo catálogo idempotente preexistente). `[EJECUCIÓN]`+`[TEST]`.

## 9. No-touch gate

Producción 0 escrituras (localhost + allow_prod=false) · RAW-YPF intacto (append-only, sin unlink) · V0 sin contaminación (resolve solo-lectura, 1 entidad KO) · V1 sin duplicados · C10 intacto (código) · C11 intacto (código; +certificaciones DEV de corridas F4, necesarias y explícitas) · C12/publisher intactos · legacy/CNV/Market intactos · regresión 159 passed/1 skipped(preexistente)/1 xfailed, 0 failed (incl. f054 de nuevo verde tras restore). `[EJECUCIÓN]`+`[CÓDIGO]`.

## 10. Gaps restantes + matriz YPF vs KO

Gaps: (1) s03-replace huerfaniza provenance ante re-parse vacío (GENERIC GAP, diseño 016; mitigación futura R7.x, p.ej. no reemplazar si 0 filings); (2) equivalencia numérica cross-emisor ND (fuera de F4); (3) matriz de industrias como objetivo (solo YPF+KO en F4).
Matriz: jurisdicción AR/US-ADR vs US · filing 20-F vs 10-K · CIK 0000904851/0000021344 · identidad v0+v1 ambas · RAW 67.084/90.398 parsed rows · NORMALIZED 47.930/45.113 facts (KO coincide con precedente) · provenance completa ambas · idempotencia ambas · gates PASS ambas.
