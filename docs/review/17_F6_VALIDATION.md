# 17 — F6 Validation C10 (sistema + ejecución)

C10 = VALIDACIÓN (consume evidencia; no calcula datos, no certifica, no publica). Solo DEV. Evidencia `[CÓDIGO]`/`[TEST]`/`[EJECUCIÓN]`/`[NO DETERMINABLE]`.

## Inventario y autoridad (PASO 1)

C10 AUTHORITY: gates S00–S04 + c3 (`GateStatus`/`assert_transition`/`StageReport`) — deciden PASS/BLOCK por etapa `[CÓDIGO]`; m4 `gates_*` + `veredicto` PASS/WARN/FAIL consumido por m5 — autoridad del dominio market (único WARN con consumidor real) `[CÓDIGO]`. C10 SUPPORT: job7 (limpia suspects), `30_validaciones` (insumo, no bloqueo), suites informativas (validar_suite/o2_/gate_roe: registran, rol bloqueante ND). LEGACY: f-series gates (sin caller). C11 (c11, 40_certificar como atestación de dominio) NO son C10 — separación verificada por código y por el contrato (certifican, no validan).

## Contrato C10 (PASO 2)

INPUT (run_ids SEC + CIKs + tickers + scope) · OUTPUT (veredicto PASS/WARN/BLOCK + invariantes con evidencia) · INVARIANTS (§matriz) · GATES (cada uno: id, scope, input, rule, result, evidence, run via stage_runs, timestamp/version `c10_evaluate_v1`) · EVIDENCE (stage_runs/checkpoints/tablas, reproducible) · BLOCKING (gate≠PASS, identidad irresoluble/duplicada, provenance incompleta, dangling>0, orphans, bridge roto, mezcla issuer/instrument/price, precios ausentes) · WARN (solo CNV_SCOPE: motor sin runs DEV). Tipos: STRUCTURAL (separación, schema), DATA (gates, precios), IDENTITY (resolución/duplicados), PROVENANCE (source/checkpoint/orphans/dangling), CROSS-SOURCE (bridge, no-overwrite). Sin reglas C11.

## Matriz de invariantes (PASO 3)

C1 fuente identificable (fetch_log/download_log) · C2 identidad resoluble + CIK consistente · C3 RAW existe/hash estable/no destructivo · C4 parsed consistente/sin corrupción · C5 V1 resuelve + cero orphans · C6 facts con provenance · C9 provenance completa · cross: issuer≠instrument≠price, bridge válido, cero orphan bridge, cero overwrite · control: stage_runs completos + gates deterministas. Severidad: BLOCK salvo CNV_SCOPE=WARN. Evidencia: queries en `c10_evaluate.py`.

## Gap S03 (PASO 4): BLOCKER CONDICIONAL

s03-replace + re-parse vacío ⇒ dangling (90.398 medidos dos veces, curados con re-run) ⇒ regla `NO_DANGLING` implementada: dangling>0 → C10 BLOCK (probado). Como diseño operacional sigue GAP R7.x (no auto-resuelto; mitigación futura: no reemplazar si 0 filings). Impacto cross-source: directo (provenance) — por eso bloquea cuando se manifiesta.

## 32 fallos (PASO 5): sin impacto C10, sin arreglos

`derived.ratio` vacía×19 (ninguna regla C10 exige la tabla) · C3 no ejecutado×3 → cubierto por CNV_SCOPE=WARN (consistente, no BLOCK) · links CNV ausentes×1 → idem · lote market específico×5 (traza de test, no invariante) · universo stale×2 (mantenimiento de tests, autodeclarado) · orden×1 (pasa aislado). Ninguno es violación del sistema; ninguno bloquea certificación de runs con evidencia (demostrado: CERTIFICADA vigentes). No se convirtió ausencia de fixture en fallo C10.

## Implementación (PASO 6): `scripts/engine/c10_evaluate.py` (nuevo, ~300 líneas, SOLO LECTURA)

Necesidad demostrada: ninguna pieza respondía determinísticamente por el conjunto (c11 responde por corrida motor; nada cubre cross-source/orfans/dangling/bridges). Reglas puras + `StageReport`/`stage_runs` existentes + contratos deterministas; sin pipeline nuevo, sin duplicar C11, sin tocar publisher/identidad/RAW/facts. WARN con consumidor honesto (operador/publicación futura; C11 no lo exige — verificado abajo).

## Tests A–P (18/18) + ejecución (PASO 7/8, DEV localhost:5433)

PASS (sec/market/cross) · WARN (all: solo CNV_SCOPE) · BLOCK (run cb2a7fd5 S01-BLOCK) · D/E (CIK fantasma) · F (decide puro + vivo 0) · G (ticker fantasma BLOCK; YPFD/KO PASS — hallazgo: canónico `YPF` no existe, el NYSE mapea a YPFD vía venue) · H (decide puro) · I/J (run incompleto/BLOCK con evidencia) · K (agregación pura) · L (determinismo sin timestamp) · M (conteos iguales pre/post) · N/O (canales C11/C12 ausentes en el evaluador) · P (≡M) · C10-PASS→CERTIFICADA existe · C10-BLOCK→NEGADA existe (motivo explícito). Artefacto: `outputs/docs/fase_c10/eval_f6.json` (WARN). Nota shell: listas con comas van entrecomilladas en PowerShell.

## C10→C11 (PASO 9)

PASS→CERTIFICADA (runs YPF/KO vigentes) · BLOCK→NEGADA (`cb2a7fd5`, motivo C10 insuficiente; +1 fila DEV explícita) · WARN→C11 no bloquea (mismo run YPF CERTIFICADA con WARN de alcance: C11 solo exige su evidencia; determinado y demostrado, no asumido). C11 intacto (código).

## No-touch (PASO 10) y matrices (§11)

Producción/RAW/facts/Market/CNV 0 escrituras (evaluador sin writes — verificado por grep + M) · Identity sin escrituras (sin backfills) · C11/C12/publisher/legacy código intacto · regresión 186/0 (12 suites). Matrices: AUTHORITY (motor/market/C11/no-autoridades) · INVARIANTE→GATE (9 reglas) · GATE→EVIDENCE (queries) · RESULTADO→DECISIÓN (agregación) · 32→IMPACTO (tabla §32-fallos) · NO-TOUCH (verificaciones).
