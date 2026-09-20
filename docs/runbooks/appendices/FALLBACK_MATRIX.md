# MATRIZ DE FALLBACKS

**Sólo se listan fallbacks que existen en el código.** Donde no hay ninguno, la
fila lo dice y no propone uno.

Clasificación pedida por el sprint:

| clase | significado |
|---|---|
| **F0** | reintento transitorio (mismo método, otra vez) |
| **F1** | fallback automático (otro método, sin intervención) |
| **F2** | reproceso de etapa |
| **F3** | intervención humana |

---

## Matriz

| etapa | falla | método primario | fallback 1 | fallback 2 | fallback 3 | reintentos | backoff | condición terminal | log | acción del operador |
|---|---|---|---|---|---|---|---|---|---|---|
| **S00** | migración falla | `apply_migrations` vía admin | — | — | — | 0 | — | excepción; corrida `ABORTED` | `engine.runs`, stdout | F3 · revisar credenciales admin |
| **S01** | catálogo SEC ausente | `load_sec_catalog` | — | — | — | 0 | — | check `C-S01-004` en FAIL | `report` | F3 · sembrar catálogo |
| **S02** | HTTP 429 | `Fetcher.get` | **F0** reintento | — | — | **3** (`max_attempts`) | **`[2, 5, 10]` s** | agotados los 3 | `download_log.http_status` | F3 si persiste: esperar |
| **S02** | HTTP 500/502/503/504 | ídem | **F0** reintento | — | — | 3 | `[2, 5, 10]` s | ídem | ídem | ídem |
| **S02** | HTTP 4xx (≠429) | ídem | **ninguno** — el código corta explícitamente | — | — | **0** | — | inmediata | `download_log` | F3 · revisar la URL/el emisor |
| **S02** | timeout | `connect=10 s`, `read=180 s` | **F0** | — | — | 3 | `[2, 5, 10]` s | tras 3 | `download_log` | F3 |
| **S02** | artefacto **crítico** falla | — | **ninguno** | — | — | 0 | — | `SystemExit("BLOCK: submissions crítica falló")` | stdout | F3 · reintentar la etapa más tarde |
| **S02** | RAW corrupto en disco | re-lectura y SHA (`C-S02-002`) | — | — | — | 0 | — | check en FAIL | `report` | **F2** · borrar el archivo y re-correr S02 |
| **S03** | mismo input ya procesado | `find_checkpoint` | **F1 · checkpoint hit**: reutiliza y sale | — | — | — | — | — | `engine.checkpoints` | ninguna: es el camino feliz |
| **S03** | lote nuevo no reproduce filings previos con hechos (F13) | `decidir_reemplazo` | **ninguno** — cero `DELETE`/`INSERT`, se conserva el `parsed.*` anterior íntegro | — | — | 0 | — | gate `BLOCK` (`C-S03-010`) | `report`, `S03_VALIDATION.json` clave `reemplazo` | ninguna: es el comportamiento correcto — conseguir el lote completo y re-correr |
| **S03** | SHA de un input no coincide | `C-S03-002` | — | — | — | 0 | — | gate `BLOCK` | `report` | **F2** · volver a S02 |
| **S03** | statement timeout | — | — | — | — | 0 | — | excepción | stdout | F3 · subir `ENGINE_STATEMENT_TIMEOUT_MS` |
| **S04** | S03 no reproducible | `C-S04-001` recalcula `hash_out` | — | — | — | 0 | — | gate `BLOCK` | `report` | **F2** · volver a S03 |
| **S04** | verificación previa | `--dry-run` | — | — | — | — | — | — | `report` con `SKIP` | preventivo, no correctivo |
| **C3** | rate limit CNV | `RateLimiter(DEFAULT_DELAYS)` | **F0** espera por host | — | — | ver `attempts` | por host | `C-C3-005` | `cnv_download_log.attempts` | — |
| **C3** | artefacto duplicado | `duplicate_of` | **F1** se referencia el original | — | — | — | — | `C-C3-009` | `cnv_download_log` | ninguna |
| **C3** | hash CNV ≠ calculado | `C-C3-008` (**no bloqueante**) | — | — | — | 0 | — | queda en `WARN` | `hash_cnv_match` | **hoy nunca ocurre**: `hash_cnv` es NULL en las 4.005 filas (`SG-02`) |
| **CNV job5** | sin `FechaCierre` | — | **ninguno** | — | — | **0** | — | `_mark_done(guid)` — **permanente** | sólo el contador `err` en stdout | **F3** · detectarlo a mano; no hay reintento posible sin editar la tabla DONE |
| **CNV job5** | `< 5` conceptos | — | **ninguno** | — | — | 0 | — | ídem | ídem | ídem |
| **CNV job5** | corrida interrumpida | `_mark_done` + `--max` | **F0** re-correr salta lo hecho | — | — | — | — | — | stdout | volver a correr |
| **ratios** | falta un insumo | — | **ninguno** — se marca `NOT_CALCULABLE` | — | — | 0 | — | el ratio no se publica | `derived.ratio.status` + `motivo` | ninguna: es el comportamiento correcto |
| **C12** (F12) | sin destino de publicación definido (`ENGINE_PUBLISH_SOURCE`) | `run_e2e_certified.py` | **ninguno** — declara `SKIPPED` explícito | — | — | — | — | `exit 0`, `publish_skipped=true` | report JSON de la cadena | ninguna: decisión de integración diferida por la ADR de F12, no una falla |
| **run_e2e_certified** (F12) | otra instancia de la cadena ya corriendo | `pg_try_advisory_lock` | **ninguno** — aborta con `exit 3` | — | — | 0 | — | lock ocupado | stdout | F3 · esperar a que termine la otra corrida |

---

## Las cinco reglas que un fallback no puede romper

El sprint las fija y conviene contrastarlas contra lo que hay:

| regla | ¿se cumple hoy? |
|---|---|
| **No ocultar un error** | **No en CNV legacy.** `_mark_done` tras un fallo oculta el error de forma permanente (`CNV-EX-001`) |
| **No cambiar el significado del dato en silencio** | Se cumple. Ningún fallback sustituye un valor por otro |
| **No sustituir una fuente sin registrarlo** | Se cumple: no hay sustitución de fuente en ninguna etapa |
| **No alterar una definición para obtener coincidencia** | Se cumple. Los ratios sin insumo van a `NOT_CALCULABLE`, no a un valor aproximado |
| **No continuar después de `BLOCKED`** | Se cumple en el engine: cada etapa exige gate `PASS` de la anterior |
| **Todo fallback produce un log** | **No en CNV legacy**: el descarte sólo incrementa un contador en memoria |

---

## Resumen honesto

**Los fallbacks reales del sistema son cuatro:**

1. **Reintento HTTP con backoff** en `engine/fetch.py` — 3 intentos,
   `[2, 5, 10]` s, sólo 429/5xx.
2. **Checkpoint hit en S03** — evita reprocesar input idéntico.
3. **Rate limiting por host en C3** — `RateLimiter` con delays por host.
4. **Guarda de no-reemplazo en S03 (F13)** — `decidir_reemplazo` evita
   perder provenance cuando el lote nuevo no reproduce el anterior; a
   diferencia de los otros tres (evitan trabajo repetido o esperan),
   ésta evita **pérdida de datos**.

**No hay** fallback de fuente alternativa, ni de parser alternativo, ni
cuarentena, ni reproceso automático de etapa. Donde una etapa falla, la
recuperación es humana y está en `RECOVERY_PROCEDURES.md`.
