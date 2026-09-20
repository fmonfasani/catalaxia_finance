# PARTE XV — TROUBLESHOOTING

Respuesta operativa a incidentes reales y un procedimiento reproducible para la
pregunta más frecuente en producción: **"¿por qué este documento no tiene
datos?"**.

**Estado:** `PARCIAL` — catálogo sí, árbol de diagnóstico por escribir.

**Material de base:** `docs/runbooks/appendices/RECOVERY_PROCEDURES.md`
completo (207 líneas); `FALLBACK_MATRIX.md` completo;
`ERROR_CATALOG.md`; `docs/runbooks/03_CNV_E2E_RUNBOOK.md` ("Diagnóstico
documento por documento"); `appendices/GOLDEN_RUNS.md` §3.

---

## Paso 1 · Las piezas del diagnóstico

**1. Los códigos de error reales.** El `ERROR_CATALOG.md` documenta 9 códigos
con check en el código (p. ej. `EXT-010`, `CNV-EX-001/002`, `ENG-TIMEOUT-001`)
**con etiquetas de runbook**. El catálogo dice quién los emite y cómo se leen.

**`KNOWN_LIMITATION (L-14)`:** **9 códigos para 374 scripts.** La cobertura del
catálogo es parcial; un incidente bien puede no tener código y quedarse en
stderr.

**2. Las cinco reglas que un fallback no puede romper** (`FALLBACK_MATRIX.md`):

| regla | ¿se cumple hoy? |
|---|---|
| No ocultar un error | **No en CNV legacy** — `_mark_done` tras un fallo lo oculta de forma permanente (`CNV-EX-001`) |
| No cambiar el significado del dato en silencio | Sí |
| No sustituir una fuente sin registrarlo | Sí |
| No alterar una definición para obtener coincidencia | Sí — los ratios sin insumo van a `NOT_CALCULABLE` |
| No continuar después de `BLOCKED` | Sí en el engine |
| Todo fallback produce un log | **No en CNV legacy** — solo un contador en memoria |

**3. La verdad sobre los fallbacks.** Los **reales** son tres, y nada más:
reintento HTTP con backoff `[2, 5, 10]` s (solo 429/5xx), checkpoint hit en
S03, y rate limiting por host en C3. **No hay** fuente alternativa, ni parser
alternativo, ni cuarentena, ni reproceso automático de etapa. Donde una etapa
falla, la recuperación es humana y está abajo.

---

## Paso 2 · Los 20 casos de recuperación

Esquema único por caso: **DETECTAR → LOG → RECUPERACIÓN AUTOMÁTICA →
VERIFICAR → REANUDAR → CONDICIÓN TERMINAL**. Donde no hay recuperación
automática, **se dice**, no se inventa. Los cinco que más se ven:

| n | caso | detectar | automática | manual |
|---|---|---|---|---|
| 3 | **Puerto incorrecto** | `RuntimeError: EXT-010: …produccion (5432)` | **sí, y es la correcta**: aborta antes de conectar | `ENGINE_DB_PORT=5433`; quitar `ENGINE_ALLOW_PROD` |
| 4 | **Proceso interrumpido** | corrida `RUNNING` sin proceso vivo (consulta de 6 h) | **parcial**: excepción → `ABORTED`; `kill -9` → `RUNNING` para siempre (`SG-11`) | re-correr la etapa; la vieja queda huérfana |
| 7 | **SHA mismatch** | SEC `C-S02-002`/`C-S03-002`; CNV `C-C3-008`, no bloqueante e inerte (`SG-02`) | ninguna | borrar el archivo y re-descargar. **No edites el hash almacenado** |
| 8/9 | **HTTP 429 / 5xx** | `download_log.http_status` | **sí**: 3 intentos, `[2, 5, 10]` s | si agota: esperar y re-correr S02. **No corras dos S02 en paralelo** |
| 12 | **Conflicto de identidad** | `C-S01-001/002`, `C-S04-004`, `SystemExit("BLOCK identidad")` | ninguna, **y está bien**: la identidad no se resuelve sola | abrir `identity.identifier_reviews`. **Nunca cierres una review a mano** (`C-C3-007`) |
| 20 | **Apuntar a producción por accidente** | `s.describe()`; `pg_namespace` debe decir solo `public` | **sí**, `EXT-010`, salvo `ENGINE_ALLOW_PROD=1` | si ya pasó: **pará todo**; `unset ENGINE_ALLOW_PROD`; documentá; compará con backup; **no reviertas a mano** |

Otros casos: PostgreSQL caído, Docker caído, máquina reiniciada, RAW
incompleto, timeout, fallo de parser, hecho duplicado, conflicto de contexto,
unidad faltante, período faltante, falta un insumo de ratio, checkpoint
corrupto / statement timeout, descarga interrumpida.

**Lo que no existe** (`RECOVERY_PROCEDURES.md`, cierre): cuarentena (`SG-08`),
cierre automático de huérfanas (`SG-11`), `--resume` en ningún script,
reintento de un CNV descartado (hay que editar `data/log_job5_v2_done.txt` a
mano), reconciliación descargado→procesado (`SG-04`).

---

## Paso 3 · El caso obligatorio — la calibración

**Documento CNV #3277363** (GUID `e04ceaf3-154a-4a37-96be-40496f91e2db`),
METR 30/09/2024 CONSOLIDADO: el CONSOLIDADO de ese trimestre falta en los
datos mientras el INDIVIDUAL está. **Antes de generalizar el árbol a cualquier
documento, hay que reproducir exactamente esta salida** (`GOLDEN_RUNS.md` §3,
comando completo incluido).

Respuestas verificadas (se reproducen con el script de diagnóstico):

```
1. publicado por CNV : 3 filas en cnv_filings            → SÍ
2. descubierto       : 1                                 → SÍ
3. seleccionado      : True (whitelist tiene 286 EEFF)   → SÍ
4. descargado        : True 152,335 bytes                → SÍ
5. sha256 calculado  : 66292affe…                       → no determinable:
                    ninguna tabla guarda el SHA contra el cual compararlo (SG-02)
6. en RAW            : True                              → SÍ
7. parsea            : 69 codigos; 38 conceptos          → SÍ, perfectamente
8. filas cnv_estados_v2 / _norm : 0 / 0                  → NO
9. procesado por job5: False (DONE tiene 2457 GUIDs)     → NO — nunca fue procesado
10. ¿por qué?         → la corrida de extracción nunca llegó a él (rango [r0:r1]
                      acotado por --max; sin reconciliación descargado→procesado)
```

**9 de 10 preguntas respondidas.** La única que no se puede responder es la
validez del SHA (`SG-02`). El dato clave: **la causa de la ausencia no es un
error, es una corrida incompleta que nadie detecta** (`SG-04`) — la razón
principal por la que el gate final del sprint no es `PASS`.

---

## Paso 4 · El árbol de diagnóstico (a escribir)

Catálogo y caso resuelto **sí existen**; el árbol generalizado **no**. La
plantilla ya está en la tabla de 7 situaciones de la Parte IX (Paso 5), y el
criterio de corte queda definido por el caso de calibración:

1. Reproducir la salida de `GOLDEN_RUNS.md` §3 **tal cual** (verificación).
2. Generalizar parametrizando por GUID/CUIT.
3. Exigir que un "nunca procesado" se distinga de un "el parser lo descartó"
   solo por `data/log_job5_v2_done.txt`.

**`KNOWN_LIMITATION (L-1, L-3, L-6, L-9):`** sin `--resume` la reanudación es
manual; no hay rollback fuera de Market; el descarte CNV no deja motivo; y
226/286 documentos METR son cáscaras — un conteo de archivos no es conteo de
documentos.

---

## GATE de la Parte XV

**PARCIAL, no completo:** no todos los incidentes que el operador va a
enfrentar están en el catálogo (9 códigos / 374 scripts, `L-14`), y el árbol
generalizado sigue por escribir. Un incidente está "resuelto" cuando se
registró: dónde se detectó, qué se hizo, qué no se hizo y por qué.

---

*Reproducir el caso #3277363 no será válido cuando el SHA quede persistible
(`SG-02` cerrado): la respuesta 5 cambiará de "no determinable" a un valor.*