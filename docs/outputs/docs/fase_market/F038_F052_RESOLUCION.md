# F-038 y F-052 — resolución (ciclo de homologación MARKET, 2026-09-01)

## F-038 — REGISTRADO por CIAA · resuelto aquí como error de metodología, no de Market

**Texto original del auditor** (`docs/review/FINDINGS.md`): *"M23 no persiste sus
corridas en `market_raw_runs`"* — evidencia citada: la tabla "sigue con 20 filas
`golden-*` sobre 2 instrumentos (83 y 84)".

**Esa observación es exacta — pero solo describe producción.** Comparación directa,
lado a lado, ambas bases, hecha en esta sesión:

```
PRODUCCIÓN  catalaxia-db:5432      → 10 stage_run_id "golden*", 20 filas, 2 instrumentos (83/84)
DEV         catalaxia-engine-dev:5433 → stage "smoke-real-2026-08-28": 577 SUCCESS + 14 FAILED
                                         (7 instrumentos × 2 intentos) = 591 filas, 584 instrument_id distintos
```

`market_db.describe()` sin ninguna variable de entorno seteada devuelve
`localhost:5432/catalaxia prod=True` — **el default de todo el tooling de Market es
producción**. M23 se corrió deliberadamente contra DEV (5433), por instrucción
explícita del owner. Cualquier chequeo de `market_raw_runs` que no fije `DB_PORT=5433`
a mano cae en producción y encuentra, correctamente, solo las 20 filas del golden case
— exactamente lo que describe F-038.

**Conclusión**: F-038, tal como está escrito, es la misma clase de error que el propio
auditor se autocorrigió una vez en ese mismo hallazgo ("confundí *no está en la tabla*
con *no ocurrió*") — acá el patrón se repite un nivel más abajo: *no está en ESTA base*
se leyó como *no está persistido en ninguna base*. `market_raw_runs` **sí** persiste
cada corrida de M23, con estado y hashes, exactamente como pide el `required_action`
del finding — en DEV, que es donde M23 corrió.

**No se propone cerrar F-038 unilateralmente** (la regla del proyecto es que un finding
se cierra contra su auditor, no por declaración del owner) — se entrega esta evidencia
para que el auditor lo re-evalúe. Lo que sí se registra como recomendación real: nada
en `market_raw_runs` ni en el JSON de reporte declara explícitamente contra qué
`host:port` corrió — un consumidor no tiene forma de saberlo sin `docker ps` o sin leer
el comando. Ver recomendación al final.

## F-052 — no existía todavía; se registra aquí con evidencia fresca

Ningún archivo del repo mencionaba F-052 antes de este ciclo (grep completo, 0
resultados). El enunciado del ciclo lo anticipaba con precisión quirúrgica: *"No
considerar un hash como contenido. Separar: hash correcto; artefacto disponible;
artefacto custodiado."* — es exactamente lo que se encontró.

**Hallazgo, verificado en esta sesión (2026-09-01)**: `data/raw/market/` **no existe en
el filesystem**. Ni el directorio raíz ni ninguno de los subdirectorios por instrumento.

```
$ find data/raw -maxdepth 1
data/raw/catalogo_edgar
data/raw/engine
data/raw/submissions
   -- "market" ausente
$ python -c "import m2_fetch_engine as eng; print(eng.RAW_BASE.exists())"
False
```

Esto contradice directamente la propia evidencia que F-038 citó el 2026-08-28-29:
*"data/raw/market/ 577 directorios por instrumento · 1154 archivos desde el 27-08"* —
esos archivos existían entonces (verificados con SHA256 exacto por una auditoría
independiente ese mismo día) y **ya no existen ahora**.

**Lo que SÍ sigue intacto**: la base de datos DEV. Cada fila de `market_raw_runs` para
`stage_run_id='smoke-real-2026-08-28'` sigue con su `sha256`, `run_id`, `batch_hash`,
`request_parameters` — un hash **correcto en el momento en que se calculó**, pero hoy
**sin artefacto disponible** contra el cual re-verificarlo. No hay backup: se revisó
`data/backups/` (solo snapshots de BYMA de otro proyecto, del 22 de agosto) y una
búsqueda de zip/tar con "market" o "raw" en el nombre en todo el repo — ninguno.

**No se determinó la causa exacta** — no hay que fabricar una: entre el 28-08 y hoy
corrieron múltiples ciclos de release (`v1.0.0`, `v1.0.1`, cierre de F-048/F-049) con
actividad de git documentada (`git reflog`) que incluye pruebas explícitas de "desde
una base limpia" (texto propio de F-049) y de `git checkout v1.0.0`. `data/raw/market/`
está en `.gitignore` — nunca estuvo versionado — así que cualquier operación de limpieza
de archivos no rastreados durante esas pruebas (de otro workstream, no de Market) pudo
barrerlo como daño colateral. Es la explicación más consistente con la evidencia
disponible, no una confirmación.

**Clasificación pedida por el ciclo, aplicada**:

| | Estado |
|---|---|
| Hash correcto (al momento de escribirse) | **SÍ** — verificado por una auditoría independiente el 28-08, 10/10 coincidencias exactas |
| Artefacto disponible (hoy) | **NO** — 0 archivos en `data/raw/market/` |
| Artefacto custodiado | **NO** — sin backup, sin réplica, sin ningún rastro fuera de la base de datos |

**F-052 se registra: severity HIGH, workstream MARKET.** No es un defecto de
integridad de datos (la base de precios `market_price_daily` sigue completa e íntegra
— los precios en sí no se perdieron, solo la evidencia RAW cruda que los respaldaba).
Es un defecto de **custodia**: el RAW existía, fue verificado, y desapareció sin que
ningún mecanismo del proyecto lo protegiera ni lo detectara hasta esta auditoría.

**required_action**: (a) decidir un mecanismo de retención real para
`data/raw/market/` (fuera del working tree gitignoreado — un bucket, un volumen
separado, o versionado explícito de al menos los RAW ya certificados); (b) considerar
si el `auditar_raw_huerfano()` de F-013 debería invertirse: además de detectar RAW en
disco sin fila en la base, debería poder detectar **filas en la base sin RAW en disco**
— el caso exactamente inverso, que es el que ocurrió acá y que la herramienta actual no
cubre.

## Recomendación transversal para ambos

Ni `market_raw_runs` ni el JSON de `m6_scale.py --json-out` registran explícitamente
`host:port` de destino. Agregar ese campo (aunque sea derivado de
`market_db.destino()` al momento de la corrida) habría hecho F-038 auto-evidente sin
necesitar esta reconstrucción manual, y es una pieza de provenance que falta: *"contra
qué base corrió esto"* es tan parte de la trazabilidad como *"con qué versión de
yfinance"*.
