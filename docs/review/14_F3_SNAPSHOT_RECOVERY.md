# 14 — F3 Snapshot/Recovery R7.3 (contrato + auditoría + ejecución)

## Contrato operacional R7.3 (definición)

SNAPSHOT (qué/cómo se preserva) · RECOVERY (restauración verificada) · ROLLBACK (operación) · PROVENANCE (registro) — responsabilidades separadas, mismo componente físico (`publisher.py`).

1. Estado publicable A = tabla `staging.<t>` promovida por swap verificado (conteo == staged > 0) con fila en `_publications`.
2. Publicación B = nuevo swap sobre A; A pasa a `staging.<t>__prev__<stamp>` intacta.
3. El snapshot preserva: nombre inequívoco (`__prev__<AAAAMMDDHHMMSS>`), hash de fidelidad total (md5 sobre filas completas JSON, NULL≠''), conteo, schema (nombres+tipos), PKs usadas, publicación origen.
4. Identificación: tabla `__prev__` + columnas `restored_snapshot`/`snapshot_hash`/`snapshot_rows` en `_publications`.
5. Hash/conteo registrados al momento del swap (no reconstruibles a posteriori).
6. Rollback permitido solo con snapshot verificado (filas>0, schema igual, hash==registrado, conteo==registrado).
7. Sin snapshot: BLOCK:NO_SNAPSHOT, salvo NOOP idempotente (vivo coincide con alguna publicación registrada).
8. Snapshot corrupto/incompleto: BLOCK (EMPTY/SCHEMA_MISMATCH/COUNT_MISMATCH/HASH_MISMATCH); target intacto.
9. Target faltante con snapshot válido: se recrea desde el snapshot (recovery, no fallo).
10. Provenance del rollback: `rolled_back=TRUE` + `rolled_back_at` + `restored_snapshot` (antes solo flag).
11. Nunca target vacío: verificación pre (snapshot>0) + post (conteo==esperado>0) en una transacción (fallo ⇒ rollback transaccional, target intacto).
12. Idempotencia: mismo input→mismo hash (swap convergente); rollback repetido→NOOP si el vivo coincide con historia.
13. Evidencia de recuperación exacta: digest post == `snapshot_hash` registrado + conteo == `snapshot_rows`.

## Auditoría F2 vs R7.3 (PASO 2)

| Requisito | F2 | Veredicto |
|---|---|---|
| snapshot `__prev__` | existía (rename en swap) | CUBIERTO |
| hash/conteo del snapshot | no registrados | NO CUBIERTO → implementado |
| rollback básico | existía (ciego) | CUBIERTO PARCIAL → verificado |
| provenance rollback | solo flag | CUBIERTO PARCIAL → timestamp+snapshot |
| target protection | regex + staging-only | CUBIERTO |
| missing snapshot | BLOCK | CUBIERTO (extendido a NOOP) |
| corrupted snapshot | sin verificación | NO CUBIERTO → `verify_snapshot` |
| repeated rollback | BLOCK siempre | CUBIERTO PARCIAL → NOOP idempotente |
| rollback idempotence | n/a | NO CUBIERTO → implementado |
| failure during recovery | n/a | NO CUBIERTO → recreación + post-check |
| residuos `__new__` en BLOCK | quedaban | NO CUBIERTO → drop en BLOCK |
| digest solo-PK | membresía, no fidelidad | CUBIERTO PARCIAL → full-row JSON |

Conclusión: gaps reales y acotados → implementación mínima justificada (sin recovery engine separado; todo en `publisher.py`).

## Implementación mínima (PASO 3, solo `publisher.py`)

1. `_publications`: +`rolled_back_at`, `restored_snapshot`, `pk_columns`, `snapshot_hash`, `snapshot_rows` (ADD COLUMN IF NOT EXISTS; staging-only).
2. `content_digest` full-row (md5 sobre `row_to_json`, orden por PK) — fidelidad total.
3. `verify_snapshot(target, prev, pks, exp_hash, exp_rows)` — 4 BLOCKs específicos.
4. `rollback`: verificación previa + recreación si falta target + NOOP por historia + provenance completa.
5. DROP de `__new__` en todo retorno BLOCK post-build (cero residuos ambiguos).
`[CÓDIGO]` (diff: solo publisher.py + tests; regresión 96/0 intacta).

## Ejecución real DEV (PASO 5; host 127.0.0.1:5433, allow_prod=false)

Secuencia CLI A(500)→snapshot→B(100)→verify→rollback→A exacta (hash `897b829e…` restaurado) → rollback repetido NOOP. Sabotajes: vaciado→BLOCK:EMPTY; DROP COLUMN→SCHEMA_MISMATCH; DELETE 1 fila→COUNT_MISMATCH; UPDATE valor→HASH_MISMATCH (detectada gracias al digest full-row); DROP target→recreación; en todos, target intacto y nunca vacío. `[EJECUCIÓN]`.
Matriz A–O: 12 tests `test_f3_recovery.py` PASS + 12 F2 intactos + regresión 96/0. `[TEST]`+`[EJECUCIÓN]`.

## No-touch gate (PASO 6)

Código: toda escritura de `publisher.py` confinada a `staging.*` (verificado por grep: únicos destinos + `information_schema` lectura; `_drop_quiet` solo invocado con `STAGING_SCHEMA`). `[CÓDIGO]`.
Empírico: producción 0 escrituras (solo DEV); C11 código intacto (certificaciones +15 = fixtures sintéticas de la suite de regresión autorizada, runs hex aleatorios, DEV); C10 intacto; RAW intacto (cero descargas en F3); legacy intacto (sin ediciones). `[EJECUCIÓN]`.
STOP no requerido (ninguna escritura fuera de staging).

## Matrices

REQUISITO|EVIDENCIA|RESULTADO: 13 puntos del contrato → todos con evidencia `[CÓDIGO]`+`[TEST]`+`[EJECUCIÓN]` (tabla anterior + suites).
COMPONENTE|CAMBIO|CAPA|PLANO|JUSTIFICACIÓN: `publisher.py` (hardening rollback/provenance/digest; C12; D+C+E; gaps reales) · `test_f3_recovery.py` (nuevo, 12 tests) · `test_f2_publisher.py` (1 assert alineado al digest full-row; corrección de test, no de código) · resto intacto.
