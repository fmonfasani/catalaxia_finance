# F-038 — TRAZA PERSISTENTE DE UNA CORRIDA DE MARKET

**Fecha:** 2026-08-28

---

## 0. F-038 estaba mal planteado

F-038 se abrió con esta afirmación mía:

> «M23 corrió el 2026-08-28 pero no dejó ninguna fila en `market_raw_runs`.
> Un auditor que consulte la base concluye que la corrida no existió.»

**Es falsa.** M23 registró **591 filas** en `market_raw_runs`, bajo
`stage_run_id = 'smoke-real-2026-08-28'`, cubriendo los **584** instrumentos del
universo. La traza siempre estuvo ahí.

Lo que falló fue la auditoría: consulté `catalaxia-db` (5432, producción), donde
Market **no escribe por diseño** — es exactamente lo que impone F-001, cerrado en
el ciclo 7. M23 escribe en `catalaxia-engine-dev` (5433), que es donde corresponde.

Es la **segunda vez en este proyecto** que cometo el mismo error de inferencia.
La primera fue concluir «M23 no se ejecutó» porque no estaba en la tabla que miré.
La corrección de aquella vez fue: *«no está en la tabla» ≠ «no ocurrió»*. Esta vez
la variante fue: *«no está en la base que miré» ≠ «no está registrado»*. El patrón
es idéntico: tomar el alcance de mi consulta como el alcance del universo.

**La causa raíz no es de Market. Es de método: auditar sin declarar primero contra
qué instancia se audita.**

---

## 1. AS-IS (verificado, no supuesto)

```
instancia    catalaxia-engine-dev  ·  127.0.0.1:5433
tabla        market_raw_runs
lote         stage_run_id = 'smoke-real-2026-08-28'
filas        591   sobre 584 instrumentos distintos
             577 SUCCESS   (todas con sha256, ninguna con row_count NULL)
              14 FAILED    (ninguna con sha256) sobre 7 instrumentos
```

### Reconciliación contra el reporte JSON

| reporte `m23-full-2026-08-28.json` | base | ✓ |
|---|---|---|
| `universo_total` 584 | 584 instrumentos distintos | ✓ |
| `SUCCESS` 567 + 10 saltados por *resume* | 577 SUCCESS | ✓ |
| `FAILED` 7 | 7 instrumentos, 14 filas (2 intentos c/u) | ✓ |
| los 7: `DGCE.BA SATS CAAP.BA VIST.BA GGALB.BA SUPVB.BA YPFLUZ.BA` | los mismos 7 | ✓ |

**La base es más completa que el reporte.** El JSON muestra el estado final; la
tabla conserva además la ronda de reintentos (14 filas FAILED sobre 7
instrumentos). Para un auditor, la base es la mejor fuente, no la peor.

### Verificación de integridad contra el filesystem

Muestra aleatoria de **40 filas SUCCESS**: el `sha256` de la base recalculado
sobre `data/raw/market/<instrument_id>/<run_id>/history.csv`.

```
COINCIDEN = 40   ·   FALTA_ARCHIVO = 0   ·   MISMATCH = 0
```

La corrida es reconstruible desde la base **sin leer el reporte**.

---

## 2. ¿Hace falta una bitácora nueva? No — y tampoco un fix de persistencia

`market_raw_runs` ya es el mecanismo correcto y **ya funciona**. El escritor real
es `scripts/market/m2_fetch_engine.py`, en dos puntos:

- **L199** — el instrumento falló: fila `FAILED` con `row_count = 0`, sin `sha256`.
- **L526 `_registrar_run()`** — el instrumento terminó: fila con hashes, fechas y cobertura.

Ambos con `ON CONFLICT (run_id) DO NOTHING` y `conn.commit()` por instrumento.

**No se toca el código de Market.** No hay defecto que corregir ahí.

---

## 3. TO-BE — lo que el contrato declara

> Una corrida de Market está **registrada** cuando, para cada instrumento
> procesado, existe una fila en `market_raw_runs` con su estado terminal, sus
> hashes y su `stage_run_id` común — de modo que un auditor pueda reconstruir el
> lote desde la base y cotejarlo contra el filesystem sin leer el reporte.
>
> Y: **toda auditoría de Market declara primero contra qué instancia consulta.**
> Market escribe en `catalaxia-engine-dev` (5433). `catalaxia-db` (5432) sólo
> tiene las 10 filas `golden-*` del 24-25 de agosto y **no debe** recibir
> escrituras de Market (F-001).

### Campos mínimos por instrumento

`run_id` (PK), `stage_run_id`, `entity_id`, `instrument_id`, `ticker_canonico`,
`source`, `source_version`, `request_parameters`, `fetched_at_utc`, `status`.
Cuando el fetch produjo datos: `row_count`, `min_date`, `max_date`, `bytes`, `sha256`.

### Relación lote ↔ instrumentos ↔ artefactos

```
stage_run_id (lote)  ->  N filas
  run_id (un intento) ->  1 fila + data/raw/market/<iid>/<run_id>/{history.csv,meta.json}
```

Un instrumento reintentado produce **varias** filas con `run_id` distinto — eso
es correcto y es la razón de que 591 > 584.

### Estados terminales

`SUCCESS | EMPTY | PARTIAL | FAILED` (CHECK preexistente). **No hay `RUNNING`**:
la fila se escribe cuando el instrumento termina. Un instrumento que nunca
terminó no deja fila, y el faltante se ve comparando contra el universo del lote.

### Idempotencia y crash

`run_id` lleva timestamp y es PK; re-registrar es `DO NOTHING`. Cada instrumento
hace `commit` al terminar: un crash a mitad deja las filas de lo ya procesado y
ninguna de lo que falta. El `resume` (`m6_scale.ya_exitosos`) se apoya
precisamente en eso — y por eso los 10 saltados aparecen como SUCCESS.

### Cómo un auditor reconstruye una corrida

```sql
-- contra 5433, NO contra 5432
SELECT stage_run_id, count(*), count(DISTINCT instrument_id),
       count(*) FILTER (WHERE status='SUCCESS'),
       min(fetched_at_utc), max(fetched_at_utc)
  FROM market_raw_runs GROUP BY 1;
```
y coteja cada `sha256` contra su `history.csv`.

---

## 4. Invariantes (`migrations/market/025`)

`ck_estado_coherente_con_artefacto`:

1. Toda fila `SUCCESS` tiene `sha256` **y** `row_count`.
2. Ninguna fila `FAILED` declara `sha256`.
3. `EMPTY` / `PARTIAL` quedan libres: son estados de cobertura parcial.

**`row_count` NO se exige NULL en `FAILED`.** La primera versión de este
constraint lo exigía, y habría **roto la próxima corrida de M23**: el escritor
real inserta `0`, que es el dato correcto — se pidió y no vino nada. El error se
detectó al contrastar el constraint contra las filas reales, no contra mi idea de
ellas. `VALIDATE CONSTRAINT` pasa sobre las 591 filas de M23.

**No se registra nada retrospectivamente**: no hace falta, la corrida ya está
registrada por sí misma.

---

## 5. Qué se corrige de verdad

| | |
|---|---|
| Código de Market | **nada** — funciona |
| Datos de M23 | **nada** — íntegros y verificados |
| `market_raw_runs` | un CHECK que declara la invariante que ya cumplía |
| Documentación | el AS-IS de F-038, que era falso |
| **Método de auditoría** | **declarar la instancia antes de concluir una ausencia** |

## 6. Ataques que deben fallar

Estado fuera del CHECK · `SUCCESS` sin `sha256` · `SUCCESS` sin `row_count` ·
`FAILED` con `sha256` · duplicar un `run_id` · una fila cuyo `sha256` no coincide
con el disco · borrar la traza de un lote.
