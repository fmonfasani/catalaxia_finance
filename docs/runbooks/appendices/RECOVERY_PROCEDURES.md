# PROCEDIMIENTOS DE RECUPERACIÓN

20 casos. Cada uno: **DETECTAR → LOG → RECUPERACIÓN AUTOMÁTICA → VERIFICAR →
REANUDAR → CONDICIÓN TERMINAL**.

Donde no hay recuperación automática, lo dice. No se inventa una.

---

### 1 · PostgreSQL caído

**Detectar** `psycopg2.OperationalError: connection refused`, o
`docker exec … psql` falla. · **Log** stdout. · **Automática** ninguna.
**Manual** `docker start catalaxia-engine-dev`; esperar a que acepte
conexiones. **Verificar** `01_COMMON_OPERATIONS.md` §1.2. **Reanudar** re-correr
la etapa; si era S03, el checkpoint la resuelve. **Terminal** si el contenedor
no arranca, revisar `docker logs catalaxia-engine-dev`.

### 2 · Docker caído

**Detectar** `docker ps` falla o no lista los contenedores. · **Automática**
ninguna. **Manual** arrancar Docker Desktop, después
`docker start catalaxia-engine-dev catalaxia-db`. **Verificar** los dos
contenedores con sus puertos. **Reanudar** desde la etapa que falló.

### 3 · Puerto incorrecto

**Detectar** `RuntimeError: EXT-010: el engine apunta al puerto de produccion
(5432)`. · **Automática** **sí, y es la correcta**: el guard aborta antes de
conectar. **Manual** `ENGINE_DB_PORT=5433`; quitar `ENGINE_ALLOW_PROD`.
**Verificar** `s.describe()` con `prod=False`. **Terminal** ninguna: el guard
nunca deja pasar.

### 4 · Proceso interrumpido (Ctrl-C, cierre de terminal)

**Detectar** corrida en `RUNNING` sin proceso vivo:
```bash
docker exec catalaxia-engine-dev psql -U catalaxia -d catalaxia -c \
  "SELECT run_id, mode, started_at, round(EXTRACT(epoch FROM (now()-started_at))/3600,1) horas \
     FROM engine.runs WHERE status='RUNNING' AND started_at < now() - INTERVAL '6 hours'"
```
**Log** `engine.runs`. · **Automática** **parcial**: `run_scope` tiene el cierre
en `finally`, así que una excepción deja la corrida en `ABORTED`. Un `kill -9`
no ejecuta el `finally` y la deja en `RUNNING` para siempre (es la causa de
F-009). `engine/db.py::corridas_huerfanas` las **detecta** al arrancar una
etapa, pero **no las cierra**. **Manual** re-correr la etapa; la corrida vieja
queda huérfana. **Terminal** las huérfanas se acumulan; no hay comando para
limpiarlas. `SOFTWARE GAP SG-11`.

### 5 · Máquina reiniciada

Combinación de 2 y 4. Arrancar Docker, verificar entorno, buscar huérfanas,
re-correr desde la última etapa con gate `PASS`:
```bash
docker exec catalaxia-engine-dev psql -U catalaxia -d catalaxia -c \
  "SELECT stage_id, max(started_at) FROM engine.stage_runs \
    WHERE gate_status='PASS' GROUP BY 1 ORDER BY 2 DESC"
```

### 6 · RAW incompleto

**Detectar** `C-S02-002` o `C-S03-002` en FAIL. · **Automática** ninguna.
**Manual** borrar el/los archivos faltantes o corruptos y re-correr S02.
**Verificar** que el check pase. **Reanudar** S03 (el `input_hash` cambió, así
que reprocesa: es lo correcto).

### 7 · SHA mismatch

**Detectar** SEC: `C-S02-002` / `C-S03-002`. CNV: `C-C3-008`, **no bloqueante y
hoy inerte** (`hash_cnv` NULL en 4.005/4.005 filas, `SG-02`). · **Automática**
ninguna. **Manual** borrar el archivo y re-descargar. **No edites el hash
almacenado para que coincida.** **Terminal** si el mismatch persiste tras
re-descargar, el origen cambió: hay que decidirlo, no taparlo.

### 8 · HTTP 429

**Detectar** `download_log.http_status = 429`. · **Automática** **sí**:
`engine/fetch.py`, 3 intentos, backoff `[2, 5, 10]` s. **Manual** si agota los
3: esperar y re-correr S02. **Verificar** `C-S02-004` (cortesía) en PASS.
**Terminal** **no corras dos S02 en paralelo**: `C-S02-004` va a fallar y la
IP puede quedar limitada. **Log gap**: `download_log` **no registra cuántos
intentos hubo** (`LOG GAP 2`).

### 9 · HTTP 5xx

Igual que 8: reintento automático en `500, 502, 503, 504`. Cualquier otro
status **no se reintenta** — el código corta explícitamente.

### 10 · Timeout

**Detectar** excepción de `requests`. · **Automática** **sí**, mismo mecanismo;
`connect=10 s`, `read=180 s`. **Manual** si es sistemático, revisar la red.
**Distinto** del timeout de PostgreSQL: ver caso 18.

### 11 · Fallo de parser

**Detectar** SEC: `C-S03-001` (conciliación) y `rejected_by_reason` en el
report. CNV: **no hay detección**; sólo el contador `err` de `job5`.
**Automática** ninguna. **Manual** SEC: leer `rejected_by_reason`, identificar
el filing, decidir. CNV: **el GUID queda marcado en
`data/log_job5_v2_done.txt` y no se reintenta**; para reprocesarlo hay que
sacar esa línea del archivo. **Terminal** en CNV, sin registro del motivo no
hay diagnóstico posible sin abrir el HTML (`SG-04`).

### 12 · Conflicto de identidad

**Detectar** `C-S01-001` (duplicados), `C-S01-002` (discrepancias),
`C-S04-004` (CIK sin entidad), o en C3 `SystemExit("BLOCK identidad […]")`.
**Automática** ninguna, **y está bien**: la identidad no se resuelve sola.
**Manual** abrir/actualizar `identity.identifier_reviews`. **Nunca cierres una
review a mano para destrabar una corrida** — `C-C3-007` existe justamente para
detectarlo. **Terminal** hasta resolver la identidad, la etapa no avanza.

### 13 · Hecho duplicado

**Detectar** violación de PK en `derived.fact` (`fact_key`) o `C-C3-009`.
**Automática** en C3, `duplicate_of` referencia el original. **Manual** un
`fact_key` repetido significa mismo `(entity_key, accn, qname, context_id,
unit_measure)`: es el mismo hecho, no un duplicado espurio. **Verificar**
`derived.v_fact_pertenencia`. **Ojo:** en el camino legacy de CNV la PK de
`cnv_estados_v2` es económica (`cuit, concepto, period_end, fecha_reexpresion,
tipo_balance`) y **no incluye `accn`**: dos documentos del mismo período
compiten por la misma fila.

### 14 · Conflicto de contexto

**Detectar** `C-S03-006` (colgantes) o `C-S04-003` (contradictorios).
**Automática** ninguna. **Manual** volver a S03. **Terminal** no continuar a
S04: un contexto contradictorio hace que el período del hecho sea ambiguo.

### 15 · Unidad faltante

**Detectar** `C-S03-006` (unidades colgantes); en el modelo canónico,
`unit_measure` vacío. **Automática** ninguna. **Manual** revisar `parsed.units`
y el parser de unidades. **Terminal** un hecho sin unidad no entra en ningún
ratio: `NOT_CALCULABLE`.

### 16 · Período faltante

**Detectar** `DURATION` sin `start_date`/`end_date`, o `INSTANT` con
`start_date`. **Automática** ninguna. **Manual** **no inventes el
`start_date`.** Si el documento no lo declara y no se puede derivar del cierre
de ejercicio del propio emisor, el hecho se excluye con causa. **Terminal**
excluido, nunca completado a ojo.

### 17 · Falta un insumo de ratio

**Detectar** `derived.ratio.status = 'NOT_CALCULABLE'` con su `motivo`.
**Automática** ninguna, **y es el comportamiento correcto**. **Manual**
conseguir el insumo por la vía normal (nueva ingesta). **Terminal** **nunca**
sustituir el insumo por otro período, otro instrumento u otro proveedor.

### 18 · Checkpoint corrupto / statement timeout

**Detectar** `canceling statement due to statement timeout`, o `C-S04-001` en
FAIL (el `hash_out` de S03 no se recalcula igual). **Automática** ninguna.
**Manual** timeout: subir `ENGINE_STATEMENT_TIMEOUT_MS` (F-028: tras un
replace masivo las estadísticas del planner quedan viejas). Checkpoint que no
reproduce: **volver a correr S03**; no fuerces S04. **Terminal** si S03 no es
reproducible dos veces seguidas, hay un no-determinismo en el parser: pará y
reportalo.

### 19 · Descarga interrumpida

**Detectar** archivo en disco con tamaño menor al esperado, o `C-S02-002` /
`C-C3-002` en FAIL al re-leer el disco. **Automática** ninguna. **Manual**
borrar el archivo parcial y re-correr la etapa de fetch. **Verificar** el check
de integridad en PASS. **Nota** en CNV, `C-C3-004` detecta el caso en que se
guardó una página de error como si fuera un artefacto válido.

### 20 · Apuntar a producción por accidente

**Detectar** — hacelo **antes** de que pase:
```bash
python -c "from engine.config import load_settings; s=load_settings(); print(s.describe())"
docker exec catalaxia-db psql -U catalaxia -d catalaxia -tAc \
  "SELECT string_agg(nspname,',') FROM pg_namespace \
    WHERE nspname NOT LIKE 'pg_%' AND nspname<>'information_schema'"
```
Producción debe decir **`public`** y nada más. Si aparecen `parsed`, `derived`,
`engine` o `fetch_raw`, **algo escribió donde no debía**.

**Automática** **sí**: EXT-010 aborta antes de conectar, salvo que alguien haya
puesto `ENGINE_ALLOW_PROD=1`. Además `c3_cnv_fetch.py` y el adaptador canónico
tienen guard propio por `db_name`.

**Manual, si ya pasó:**
1. **Pará todo.** No corras nada más.
2. `unset ENGINE_ALLOW_PROD`.
3. Documentá qué corriste, con qué `run_id` y a qué hora.
4. Comparalo contra el backup **antes** de tocar nada.
5. **No intentes revertir a mano** sin saber exactamente qué se escribió.

**Terminal** una escritura en producción no se "recupera" corriendo más
comandos: se restaura desde backup.

---

## Lo que no existe

| mecanismo | estado |
|---|---|
| Cuarentena | **no existe** (`SG-08`) |
| Cierre automático de corridas huérfanas | **no existe**: se detectan, no se cierran (`SG-11`) |
| `--resume` | **no existe** en ningún script |
| Reintento de un documento CNV descartado | **no existe**: hay que editar `data/log_job5_v2_done.txt` a mano |
| Reconciliación descargado → procesado | **no existe** (`SG-04`) |
