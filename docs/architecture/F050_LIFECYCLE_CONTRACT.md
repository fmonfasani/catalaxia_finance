# CONTRATO — F-050 · LIFECYCLE DE S00, S01 Y S02

**Fecha:** 2026-08-31 · **Escrito antes de modificar código.**
**Alcance:** exclusivamente el ciclo de vida de la corrida en esas tres etapas.
No toca parsing, fetch, gates, contratos de datos ni resultados funcionales.

---

## 0. El defecto, reproducido

Durante el E2E de v1.0.1, dos fallos reales dejaron **3 corridas en `RUNNING`** sobre
la instalación limpia: S01 abortó por `FileNotFoundError`, S02 murió por `timeout`.

```
s00_smoke.py      start_run L31   finish_run L107   run_scope=0
s01_identity.py   start_run L118  finish_run L203   run_scope=0
s02_fetch_ypf.py  start_run L209  finish_run L420   run_scope=0
s03_parse_ypf.py                                    run_scope   (F-031)
s04_normalize.py                                    run_scope
c3_cnv_fetch.py                                     run_scope   (F-040)
```

Entre `start_run` y `finish_run` hay 76, 85 y 211 líneas respectivamente. Cualquier
excepción en ese tramo deja la fila en `RUNNING` para siempre.

**S02 tiene además una ruta explícita de salida sin cierre**: `raise SystemExit` en la
L245 cuando la submissions crítica falla.

## 1. Rutas de ejecución a cubrir

| ruta | S00 | S01 | S02 |
|---|---|---|---|
| éxito (`gate PASS`) | `finish_run("OK")` | `finish_run("OK")` | `finish_run("OK")` |
| gate `BLOCK` | `finish_run("BLOCKED")` | `finish_run("BLOCKED")` | `finish_run("BLOCKED")` |
| **`raise SystemExit` temprano** | — | — | **L245, sin cierre** |
| **excepción no controlada** | **sin cierre** | **sin cierre** | **sin cierre** |
| **interrupción (SIGINT/kill)** | **sin cierre** | **sin cierre** | **sin cierre** |

Las tres últimas son el defecto.

## 2. El mecanismo: el mismo que ya está probado

`run_scope()` (`engine/db.py:153`) cierra en un `finally`:

- excepción → `ABORTED` con `finished_at`, y **la excepción se propaga**;
- salida limpia → el status que el cuerpo fijó en `run.status`, o `OK` por defecto;
- captura `BaseException`, así que cubre `SystemExit` y `KeyboardInterrupt`.

**No se crea un mecanismo nuevo.** Es literalmente el patrón de F-031 (S03) y F-040
(C3), aplicado a las tres etapas que quedaron fuera.

## 3. La forma del cambio

Idéntica en las tres, y ya validada dos veces:

```python
def main() -> int:
    ...configuración, engine, migraciones...          # antes de abrir la corrida
    with edb.run_scope(engine, settings, PIPELINE_VERSION) as run:
        print(f"[run] run_id={run.run_id} ...")
        return _correr(engine, settings, run, ...)

def _correr(engine, settings, run, ...) -> int:
    """Cuerpo de la etapa. Fija `run.status`; NUNCA llama a finish_run."""
```

Reglas:

1. **`finish_run` desaparece del cuerpo.** La etapa *declara* (`run.status`); el cierre
   lo hace `run_scope` en su `finally`. Dos dueños del cierre es lo que produjo F-049.
2. **`start_run` desaparece.** Lo abre `run_scope`.
3. **Nada más cambia**: ni el orden de las operaciones, ni los gates, ni los reportes,
   ni los valores de retorno.
4. **`corridas_huerfanas()` al arrancar**, como hace C3 desde F-040: si el pipeline
   dejó huérfanas, hay que verlo antes de generar más.

## 4. Lo que NO se hace

- **No se cierran las corridas históricas** de la base homologada. No las hay: tiene
  `RUNNING = 0`. Las 3 del E2E vivían en una base descartable ya eliminada.
- No se borra ni se falsifica ninguna corrida.
- No se toca `run_scope` — funciona y está mutado.
- No se toca S03, S04 ni C3.

## 5. Banco adversario

| | escenario | resultado exigido |
|---|---|---|
| A1 | fallo antes de comenzar el procesamiento | `ABORTED` + `finished_at` |
| A2 | fallo durante el procesamiento | `ABORTED` + `finished_at` |
| A3 | fallo después del checkpoint | `ABORTED` + `finished_at` |
| A4 | gate `BLOCK` | `BLOCKED` + `finished_at` |
| A5 | excepción inesperada | `ABORTED` + `finished_at` |
| A6 | `SystemExit` temprano (S02 L245) | `ABORTED` + `finished_at` |
| A7 | `KeyboardInterrupt` | `ABORTED` + `finished_at` |

**Y la mutación obligatoria**: al revertir una etapa al patrón viejo, el escenario
correspondiente debe volver a dejar `RUNNING`. Sin esa dependencia causal demostrada,
el test no prueba la garantía.

## 6. Criterio de cierre

`RUNNING = 0` tras ejercitar los 7 escenarios sobre las tres etapas, verificado por
una auditoría que consulte PostgreSQL directamente y no reutilice el código del
implementador.
