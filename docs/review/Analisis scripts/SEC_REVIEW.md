# SEC / EDGAR — AUDIT REVIEW

Auditor: **CIAA** · Ciclo **AUDIT-02** · Baseline `444ee1a`
Objeto: **S03 Parse XBRL**, checkpoint `971ce5d999a2499b-s03`, run `971ce5d999a2499ba6af136cb2c87569`

## VEREDICTO

**PASS_WITH_WARNINGS** — primera auditoría de SEC. En AUDIT-01 el workstream no calificaba
(S03 implementado, test fallando, sin corrida real). Hoy califica y **la evidencia se sostiene
íntegramente**, con una imprecisión de conteo y un defecto de manejo de fallos.

---

## Conteos — los cuatro exactos

Verificados contra `catalaxia`@5433, no contra el reporte:

```
                      declarado    real       
parsed.link_relations   146.028   146.028   ✓
parsed.facts             67.084    67.084   ✓
parsed.contexts          23.478    23.478   ✓
parsed.units                369       369   ✓
parsed.parse_errors           —         0
parsed.concepts               —    13.412
```

`link_relations = 146.028` confirma que el fix de persistencia funcionó: el log registra que
antes era **0**. La cadena de linkbases dejó de perderse en silencio, que era el riesgo
material de esta etapa.

## Gate y encadenamiento

```
gate     : PASS · 9/9 checks · ningún NO-PASS
verdict  : READY_FOR_S04
input    : S02_fetch run_id 33d234463f4341af9ad4931c67a3c561
totals   : 27 filings esperados = 27 procesados
           PARSED_XBRL 9 · PRE_XBRL 18 · REJECTED 0
           custom_tags 10.216 · standard_tags 3.196 · unique_tags 8.221
```

La cadena **EXPECTED → DISCOVERED → SELECTED → PARSED → PERSISTED** cierra: 27 esperados,
27 procesados, 0 rechazados, 0 errores de parseo. Los 18 `PRE_XBRL` son filings antiguos sin
XBRL — clasificados, no descartados. **No hay pérdida silenciosa.**

`input_checkpoint` apunta al run real de S02, de modo que el encadenamiento entre etapas es
verificable y no declarativo.

## Tests — 18/18 por corrida propia

```
python -m pytest tests/test_s03_xbrlparse.py -q
18 passed in 1.72s
```

El test que bloqueaba en AUDIT-01 (`test_contexto_dimensional_explicito`) pasa. **No audité
cómo se resolvió** el dilema de namespace `xbrldt` vs `xbrldi` documentado en el estado —
está fuera de lo que el gate exige y la suite está en verde.

## Fix `ON CONFLICT` — verificado, con una corrección propia

El log declara el fix como
`ON CONFLICT (stage_id, input_hash, code_version, contract_version) DO UPDATE`.

Mi primera consulta a `pg_constraint` mostró **sólo** la PK sobre `checkpoint_id`, lo que en
PostgreSQL haría fallar esa sentencia. **Mi sospecha era infundada:**

```
ux_checkpoints_reuse | CREATE UNIQUE INDEX ... ON engine.checkpoints
                       USING btree (stage_id, input_hash, code_version, contract_version)
```

Un índice único satisface `ON CONFLICT` aunque no respalde una constraint formal, y
`pg_constraint` no lo lista. **El fix es real.** Resultado verificado: `engine.checkpoints`
tiene **exactamente 1 fila** para `S03_parse`, apuntando al run ganador — el upsert reemplazó
en vez de duplicar o chocar.

## Determinismo — sostenido, con limitación declarada por el propio worker

El log documenta la comparación entre la corrida que commiteó y crasheó (`973b7e9e…`) y la
ganadora (`a1a37b19…`): **idénticos filing por filing** en los 27 accession numbers.

Y declara su propia limitación, que es lo que le da crédito: `parsed.*` hace `DELETE FROM`
sin filtrar al inicio de cada corrida (diseño *replace-all*, `S03_DESIGN.md` §4), así que la
comparación se hizo **contra el stdout de ambas corridas**, no contra dos snapshots
simultáneos. Confirmado en la base: los 67.084 facts llevan un único `run_id`.

Que el worker exponga esa limitación en vez de presentarla como equivalencia plena es
exactamente la conducta que esta auditoría busca.

---

## Hallazgos

### F-009 (MEDIUM) — cinco corridas sin estado terminal

De **8 `run_id` distintos**, sólo 3 alcanzaron `CHECKPOINTED`. Cinco quedaron en `RUNNING`,
**sin `FAILED`**:

```
e004ed88…  READY -> RUNNING                                          24-ago 21:37
e65a3c6a…  READY -> RUNNING                                          25-ago 04:13
eccd5fb3…  READY -> RUNNING                                          25-ago 04:17
b4a2b220…  READY -> RUNNING                                          25-ago 04:26
973b7e9e…  READY -> RUNNING                                          25-ago 04:36
a1a37b19…  READY -> ... -> CHECKPOINTED                              25-ago 04:47
f8b8c389…  READY -> ... -> CHECKPOINTED                              25-ago 13:41
971ce5d9…  READY -> ... -> CHECKPOINTED                              25-ago 13:56
```

`S00_bootstrap` y `S01_identity` **sí** registran `FAILED` (9 filas cada uno): la máquina de
estados contempla el fallo, S03 no la usa en su camino de aborto. Consecuencia:
`stage_runs` no permite distinguir *"corriendo ahora"* de *"murió en silencio"*.

### Imprecisión de conteo — "4 ejecuciones completas deterministas"

La base muestra **3** CHECKPOINTED. La cuarta es defendible como la corrida que commiteó
`parsed.*` y crasheó antes del checkpoint (`973b7e9e…`, la que el log usa justamente para
comparar determinismo). No es una afirmación falsa, pero **8 corridas iniciadas, 3
terminales** es un cuadro distinto del que sugiere "4 ejecuciones completas".

---

## Lo que no se auditó

- **S04 no se ejecutó** (prohibido por alcance) y no se evaluó su preparación más allá del
  `verdict: READY_FOR_S04` que declara el gate.
- **No se verificó pérdida de dimensiones a nivel fact.** El gate declara `dim_facts` en sus
  totales y `parse_errors=0`, pero no recalculé la extracción dimensional contra el XBRL
  crudo. Es la verificación más costosa de esta etapa y queda pendiente para un ciclo con
  foco en S03 profundo.
- **La resolución del namespace `xbrldi`/`xbrldt`** — con qué criterio se cerró.

## Evidencia consultada

- `catalaxia`@5433 · `parsed.{facts,contexts,units,link_relations,concepts,parse_errors}`,
  `engine.{stage_runs,checkpoints}`, `pg_indexes`
- `outputs/docs/fase_s03/{S03_VALIDATION.json, S03_MANIFEST.json, S03_EXECUTION_LOG_2026-08-25.md}`
- `tests/test_s03_xbrlparse.py` (corrida propia)
