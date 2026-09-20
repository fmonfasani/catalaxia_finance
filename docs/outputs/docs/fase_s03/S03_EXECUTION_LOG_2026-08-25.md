# S03 — Bitácora de ejecución real, 2026-08-25

Complementa (no reemplaza) `S03_PARSE_REPORT.md` y `S03_VALIDATION.json`, que son
el output auto-generado por el propio script en la corrida ganadora. Este
documento registra lo que esa corrida sola no cuenta: los bugs encontrados y
corregidos en el camino, y la verificación independiente hecha además del gate
auto-reportado.

Baseline: `catalaxia-baseline-2026-08-25`, commit `444ee1a`. Alcance: exclusivamente
S03 (SEC/EDGAR). No se tocó Market ni CNV.

## 1. Punto de partida

`tests/test_s03_xbrlparse.py`: 17 PASS, 1 FAIL
(`TestInstance::test_contexto_dimensional_explicito`). S03 nunca se había
ejecutado contra RAW real de S02.

## 2. Fix del test (causa raíz confirmada de forma independiente)

El fixture del test declaraba `xmlns:xbrldi="http://xbrl.org/2005/xbrldt"` en sus
elementos `explicitMember`/`typedMember` — esa es la URI de **xbrldt** (namespace
de taxonomía/hipercubos, usado en linkbases de definición), no de **xbrldi**
(namespace de instancia, el que de verdad marca miembros de dimensión dentro de
un `<xbrli:scenario>`). Confirmado leyendo `engine/xbrlparse.py`: `XBRLDT_NS`
y `XBRLDI_NAMESPACES` están definidos y usados correctamente — el parser nunca
tuvo el bug, era un typo de copy-paste en el fixture. Fix: cambiar la URI del
fixture a `http://xbrl.org/2006/xbrldi` (la que usan los filings reales de YPF).
Cero cambios en `engine/xbrlparse.py`.

Resultado: **18/18 tests** (el total real siempre fue 18, no 20 — el número "20"
que traía el brief no coincide con `pytest --collect-only`; se señala en vez de
repetirlo sin más).

## 3. Bugs encontrados al intentar la corrida real (no en el test, en el script)

Los cuatro fueron descubiertos ejecutando, no por inspección previa. Ninguno es
un cambio de interfaz/contrato; todos son finalización de una edición
interrumpida o gaps de rendimiento operativo, dentro del alcance de S03.

| # | Bug | Síntoma | Fix |
|---|---|---|---|
| 1 | `try:` sin `except`/`finally` en `main()` de `scripts/engine/s03_parse_ypf.py` | `SyntaxError`, el script no arrancaba | Cerrado con `raw.commit()` en el `try`, `except: raw.rollback(); raise`, `finally: raw.close()` |
| 2 | 3 llamadas a `insert_many(conn, ...)` con `conn` indefinida (debía ser `cur`, el cursor psycopg2 crudo) | Habría fallado con `NameError` al llegar a esas líneas | Reemplazado por `cur` en las 3 (companyfacts_compare, pre_xbrl_filings, parse_errors) |
| 3 | Plantilla `JSONB_TEMPLATES["parsed.units"]` con 10 placeholders `%s` para 11 columnas (`UNIT_COLS`); `["parsed.pre_xbrl_filings"]` con 15 para 14 | `TypeError: not all arguments converted during string formatting` en el primer INSERT de `parsed.units` | Corregidas ambas plantillas (verificado programáticamente contra el largo real de cada tupla de columnas antes de tocar el código) |
| 4 | Resumen `outcomes` (un `dict`) escrito directo en una celda de Excel vía `ws.append([k, v])` | `ValueError: Cannot convert {...} to Excel` en `write_outputs()`, después de que el parseo+insert ya había commiteado bien | `j(v) if isinstance(v, (dict, list)) else v` |
| 5 | `NOT EXISTS` correlacionado de `parsed.facts` contra `parsed.contexts`/`parsed.units` (check C-S03-006) sin índice compuesto que lo soporte | `psycopg2.errors.QueryCanceled: canceling statement due to statement timeout` (el timeout de 120s es deliberado, de un incidente previo de S01 — no se tocó) sobre ~67k facts | Migración aditiva `migrations/engine/006_s03_context_unit_indexes.sql` (2 índices compuestos) + `ANALYZE parsed.facts, parsed.contexts, parsed.units` antes de las queries de validación (sin esto el planner no usaba el índice nuevo recién insertado) |

Verificado en aislado antes de comprometerse a otra corrida completa (~7 min):
con los índices + `ANALYZE`, la query de `dangling_ctx`/`dangling_unit` bajó de
>120s (timeout) a 0.41s / 0.12s sobre los 67.084 facts ya commiteados de una
corrida previa.

Después de cada fix se re-corrió `pytest tests/test_s03_xbrlparse.py` — se
mantuvo en 18/18 en las 5 iteraciones (ninguno de los fixes tocó
`engine/xbrlparse.py`).

## 4. Corrida ganadora

- **run_id**: `a1a37b1986a14f8c900b86d11b1630f8` · git `444ee1ad0e1b092c79ce055ded0b993fbc55822d`
- **Input**: checkpoint S02 `run_id=33d234463f4341af9ad4931c67a3c561` (gate PASS
  original, 171/171 archivos re-verificados sha256 en esta corrida, 0 corruptos)
- **Migraciones aplicadas en esta sesión**: `005_c3_cnv_fetch.sql` (de otro
  workstream, aplicada automáticamente por `apply_migrations()` al conectar —
  no la escribió esta sesión) y `006_s03_context_unit_indexes.sql` (esta)
- **Duración**: 415.4s de parseo puro; ~10m19s de punta a punta según
  `engine.stage_runs` (incluye conexión, migraciones, ANALYZE, checks)
- **Filings**: 27/27 esperados=procesados. 9 `PARSED_XBRL` (FY2017–FY2025), 18
  `PRE_XBRL` (FY2001–FY2016, correctamente declarados, 0 hechos inventados)
- **Totales**: 67.084 facts (51.421 dimensionales, 15.663 sin dimensión) · 23.478
  contexts · 369 units · 13.412 concepts (10.216 custom, 3.196 estándar) · 0
  errores de parseo
- **Gate**: `PASS` (9/9 checks, C-S03-001..009) → `READY_FOR_S04`
- **Checkpoint**: `engine.checkpoints` → `('S03_parse', 'a1a37b1986a14f8c-s03', 2026-08-25T04:57:56Z)`.
  `engine.stage_runs` confirma la máquina de estados completa:
  READY→RUNNING→VALIDATING→PASSED→CHECKPOINTED, `gate_status='PASS'` en la fila
  final.
- **Outputs**: `S03_YPF_PARSE_AUDIT.xlsx` (24,2 MB), `S03_PARSE_REPORT.md`,
  `S03_VALIDATION.json`, `S03_MANIFEST.json` — todos en
  `outputs/docs/fase_s03/`.

## 5. Verificación independiente (no auto-reportada por el script)

No se declaró éxito solo por el `exit code 0` ni por el JSON que el propio
script imprime. Verificado aparte, con queries propias:

1. **`engine.stage_runs`/`engine.checkpoints` leídos directo** (no solo el
   stdout del script) — confirman CHECKPOINTED con gate PASS de forma
   independiente del reporte JSON.
2. **Determinismo**: comparados los conteos por filing entre la corrida que
   llegó a commitear pero crasheó después (`973b7e9eb7db4a7eba4200200c521fa9`,
   antes de agregar los índices) y la corrida ganadora
   (`a1a37b1986a14f8c900b86d11b1630f8`) — **idénticos, filing por filing**:
   mismos facts/contexts/units/relations en cada uno de los 27 accession
   numbers, con el mismo input y el mismo código de parseo (los fixes entre
   ambas corridas fueron todos posteriores al parseo/insert, nunca tocaron
   `engine/xbrlparse.py` ni la lógica de extracción). Nota: `parsed.*` solo
   retiene la última corrida (`DELETE FROM` sin filtrar por `run_id` al
   principio de cada corrida — diseño "replace-all" documentado en
   `S03_DESIGN.md` §4), así que la comparación se hizo contra el log de stdout
   de ambas corridas, no contra dos snapshots simultáneos en la DB.
3. **Spot-check de un fact dimensional real**: `RevenueFromSaleOfOilAndGasProducts`
   (taxonomía `ifrs-full`), USD 89.000.000, `dim_count=2` (segmento Upstream ×
   eje de consolidación), cadena de provenance completa (`source_kind`,
   `source_file=d95578d20f.htm`, `source_hash`, `accession_number`) — un hecho
   real de un filing real, no un placeholder.
4. **Spot-check de un contexto dimensional real**: dimensión explícita
   preservada correctamente (`ypf:AcquisitionCostOfTreasurySharesMember` sobre
   `ifrs-full:ComponentsOfEquityAxis`, `typed=False`, `dim_count=1` consistente
   con el array).
5. **Provenance**: 0 violaciones sobre 67.084 facts (check C-S03-003), y
   confirmado a mano en el spot-check anterior.
6. **Integridad referencial**: 0 `context_id`/`unit_ref` colgantes sobre 67.084
   facts (check C-S03-006, re-verificado con la query aislada antes de la
   corrida completa).

## 6. Continuación (mismo día): cierre de `link_relations`

Pedido de continuar el cierre de S03. Se resolvió el hallazgo #1 de la sección
anterior (no el #2, que sigue correspondiéndole a S04 — ver más abajo).

**Fix**: `rel_row()` pasó a recibir un tercer parámetro `src_hash` (sha256 del
archivo de linkbase — `sha256_bytes(mdata)` para miembros de zip,
`r["sha256"]` para linkbases sueltas, el mismo patrón ya usado para las
instancias); se agregó el `insert_many(cur, "parsed.link_relations", REL_COLS,
res["rel_rows"])` faltante en `main()`, junto a los inserts de facts/contexts/
units. `parsed.link_relations` no tiene columnas JSONB, así que no hace falta
tocar `JSONB_TEMPLATES`.

Al re-correr con este fix apareció un **bug distinto, preexistente**, no
causado por el cambio: el `INSERT INTO engine.checkpoints` final es un INSERT
plano sin manejo de conflicto, y la restricción única `ux_checkpoints_reuse`
(`stage_id, input_hash, code_version, contract_version`) — que por diseño
(`STAGE_GRAPH.md` §4: "re-corrida con input+code+contract sin cambios ⇒ NO
reprocesa, checkpoint hit") debería tratar una re-corrida idéntica como un
hit, no como un error — hacía que la re-corrida (mismo `S02` de entrada, mismo
`code_version="engine-v1"` estático) chocara contra el checkpoint ya
registrado por la corrida anterior y abortara con `UniqueViolation`, **dentro
de la misma transacción que además actualiza `engine.stage_runs`**: al
abortar, esa actualización también se revertía, dejando la corrida sin
`gate_status` ni `report` registrados (aunque el parseo y el insert de
`parsed.*`, hechos en una transacción psycopg2 separada y ya commiteada, sí
habían quedado bien). Fix: `ON CONFLICT (stage_id, input_hash, code_version,
contract_version) DO UPDATE` sobre el mismo checkpoint, apuntando al `run_id`
más nuevo — consistente con que `parsed.*` ya es replace-all por diseño.

Verificado tras el fix, en la corrida ganadora final (`run_id
971ce5d999a2499ba6af136cb2c87569`, mismos totales que las corridas anteriores
— 67.084 facts, 23.478 contexts, 369 units, gate PASS 9/9):

- `SELECT count(*) FROM parsed.link_relations` = **146.028** (antes: 0).
  Spot-check de una relación CALCULATION real: `ifrs-full_CurrentLiabilities`
  → `ifrs-full_CurrentTaxLiabilitiesCurrent`, weight=1.0, con `source_file`
  y `source_hash` poblados.
- `engine.checkpoints` para `stage_id='S03_parse'`: **exactamente 1 fila**,
  apuntando al run_id de esta corrida — el upsert reemplazó al anterior en vez
  de duplicar o chocar.
- `engine.stage_runs` para esta corrida: `state='CHECKPOINTED'`,
  `gate_status='PASS'`, `finished_at` poblado.
- `pytest tests/test_s03_xbrlparse.py` sigue en 18/18 (ninguno de los dos
  fixes tocó `engine/xbrlparse.py`).

## 7. Hallazgo NO corregido (documentado, no maquillado)

**Check C-S03-007 (comparación CompanyFacts vs filing) pasa, pero su bucket
"ambos" da sistemáticamente 0.** Causa confirmada: `companyfacts_index()`
arma qnames en formato corto (`dei#EntityCommonStockSharesOutstanding`)
mientras el parser de instancias arma qnames con la URI completa de namespace
(`http://fasb.org/srt/2018-01-31#Future...`) — nunca van a matchear por
igualdad de string aunque sea el mismo concepto. El check sigue siendo válido
según su propia definición (produce filas, cubre la unión de conceptos), pero
no cumple su propósito de contraste real entre las dos fuentes. No se tocó:
cambiar la normalización de qname es una decisión de S04 (ahí es donde se
define "concepto canónico"), no de S03, que por diseño preserva tal cual
llega cada fuente.

## 8. Veredicto final de esta sesión

Los 6 criterios de éxito del brief original están cumplidos con evidencia
verificable de forma independiente, **y además** el único hallazgo que era
razonablemente corregible dentro del alcance de S03 (persistencia de
`link_relations`) quedó cerrado, incluyendo un segundo bug preexistente que
apareció en el camino (checkpoint upsert). Estado final: **CHECKPOINTED /
VALIDATED**, con un solo hallazgo pendiente (§7) que pertenece a S04, no a
S03.
