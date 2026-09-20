# CATÁLOGO DE CHECKPOINTS

## 1 · El único checkpoint real: S03

**Nombre.** `S03_parse` (constante `STAGE_ID` en `engine/s03.py:29`).

**Ubicación.** Tabla `engine.checkpoints`, creada por
`migrations/engine/001_s00_bootstrap.sql`:

```sql
CREATE TABLE IF NOT EXISTS engine.checkpoints (
    checkpoint_id    TEXT PRIMARY KEY,
    stage_id         TEXT NOT NULL,
    run_id           TEXT NOT NULL REFERENCES engine.runs(run_id),
    input_hash       TEXT NOT NULL,
    code_version     TEXT NOT NULL,
    contract_version TEXT NOT NULL,
    artifact_ref     TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX ux_checkpoints_reuse
    ON engine.checkpoints (stage_id, input_hash, code_version, contract_version);
```

**Contenido.** La clave de reutilización es la tupla del índice único:
`(stage_id, input_hash, code_version, contract_version)`.

**Input digest.** `engine/s03.py::input_hash`:

```python
h = sha256(entity_id)
for r in sorted(files_ok, key=lambda x: x["raw_path"]):
    h.update(f"|{r['raw_path']}={r['sha256']}")
```

Es decir: **entidad + cada (ruta, sha256) de los crudos consumidos**, ordenado
por ruta. Cambiar un solo byte de un crudo cambia el hash.

**Output digest.** Dos, distintos:

- `output_hash(fact_rows_count, digests)` — resumen del volumen.
- **`hash_out` (`engine/hashout.py`, spec `hashout-v2`)** — el que importa. Es
  sensible al **contenido** (los campos semánticos entran al digest de fila) e
  **insensible al orden** (los hashes de fila se ordenan antes de agregar), y
  es **reconstruible** por un tercero desde la base.

  La v1 era `sha256(json({cantidades de filas}))` y no distinguía contenido:
  tres corridas con datos distintos —una de ellas la que corrigió el parser de
  unidades y cambió 44 unidades y 436 hechos— declararon el **mismo** hash
  (F-029). Por eso `C-S04-001` **recalcula** `hash_out` en vez de creerle al
  declarado.

**Estado.** No hay columna de estado. Que exista la fila **es** el estado: el
checkpoint se escribe al final de una etapa que pasó.

**Timestamp.** `created_at`.

**Cómo se valida.** `engine/s03.py::find_checkpoint`:

```sql
SELECT checkpoint_id, run_id, created_at FROM engine.checkpoints
 WHERE stage_id=:s AND input_hash=:h AND code_version=:c AND contract_version=:ct
```

Si devuelve fila, la etapa **reutiliza y sale sin reprocesar**.

**Cómo se reanuda.** Volviendo a ejecutar el mismo comando. No hay bandera.

**Cuándo NO se puede reanudar.** Cuando cambia cualquiera de los tres ejes:

| cambia | efecto |
|---|---|
| un crudo de S02 (o su SHA) | `input_hash` distinto ⇒ reprocesa |
| el código del parser | `code_version` distinto ⇒ reprocesa |
| el contrato (`CONTRACT_VERSION = "parsed-v2"`) | reprocesa |

Consultarlo:
```bash
docker exec catalaxia-engine-dev psql -U catalaxia -d catalaxia -c \
  "SELECT stage_id, left(input_hash,16) AS input, code_version, contract_version, \
          created_at FROM engine.checkpoints ORDER BY created_at DESC LIMIT 10"
```

---

## 2 · Checkpoints de las demás etapas

| etapa | ¿escribe en `engine.checkpoints`? | qué usa en su lugar |
|---|---|---|
| **S00** | no | ninguno; es barata, se re-corre |
| **S01** | **sí, condicional** | inserta `(stage_id=S01_identity, artifact_ref="pg://identity.entities")` **solo si** el gate no es `BLOCK` **y** la corrida no es parte de un E2E (`ENGINE_E2E_RUN_ID` sin setear — decisión R4: sin checkpoints individuales dentro de un E2E). No se usa para reutilización por input (S01 siempre re-siembra); es registro de evidencia, no un mecanismo de "checkpoint hit" como S03 |
| **S02** | no | los archivos en disco + SHA: si el crudo ya está y verifica, no se re-descarga |
| **S03** | **sí** | el único con reutilización real por input (`find_checkpoint`) |
| **S04** | **id derivado** | imprime `checkpoint <run_id[:16]>-s04`, pero **no escribe fila** en `engine.checkpoints` |
| **C3 CNV** | **sí** | cierra etapa con `checkpoint_id` (ver `c3_cnv_fetch.py:566`) |
| **CNV job5** | **no** — tabla propia | marca cada GUID como hecho (`_mark_done`); no hay hash de input ni de output |
| **ratios** | no | versionado por `valid_to` |
| **C10/C11/C12** | no (F12) | C11 tiene su propia idempotencia: `engine.certifications`, `ON CONFLICT (run_id) DO NOTHING` — un acta por `run_id`, nunca se reescribe |

### El checkpoint de S04 es aparente

S04 imprime una línea `checkpoint <run_id[:16]>-s04` y usa
`input_checkpoint_id` en el reporte, pero **no inserta en `engine.checkpoints`**.
Consecuencia: **S04 no tiene reutilización por input**. Volver a correrlo
reprocesa siempre.

No es un defecto de corrección —S04 escribe con versionado temporal y no
duplica— pero sí un hueco de operación: en un universo grande, re-correr S04 no
tiene atajo. `SOFTWARE GAP SG-09`.

### El "checkpoint" de job5 no es un checkpoint

`_mark_done(guid)` marca el documento como procesado **sin distinguir éxito de
fracaso**. Un documento que falló queda marcado igual que uno que salió bien.
No hay `input_hash`, así que si el HTML cambia no se reprocesa; y no hay
`output_hash`, así que no se puede comparar entre corridas.

**Es un registro de "ya lo vi", no un checkpoint.** Ver `ERROR_CATALOG.md`
`CNV-EX-001`.

---

## 3 · No existe `--resume`

Se buscó en todo `engine/` y `scripts/engine/`: **ninguna etapa acepta
`--resume`** ni equivalente. La única mención está en un mensaje de
`scripts/engine/audit_pre_homologacion.py:211`, que habla de una bandera que no
existe.

La reanudación real es:

1. **S03** — automática por checkpoint hit.
2. **S02** — parcial: los crudos ya presentes se verifican en vez de bajarse.
3. **job5** — por `_mark_done` + `--max`, con la salvedad de arriba.
4. **El resto** — no hay reanudación: se vuelve a correr la etapa entera.

`RUNBOOK GAP RG-02`.
