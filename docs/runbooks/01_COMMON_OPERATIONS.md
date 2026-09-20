# 01 · OPERACIONES COMUNES

Todo lo que se usa en los dos pipelines. Se ejecuta desde la raíz del repo.

---

## 1 · Verificación de entorno (OBLIGATORIA antes de cada E2E)

Ejecutá los cinco comandos en orden. Si alguno no da lo esperado, **abortá**.

### 1.1 Docker

```bash
docker ps --format "{{.Names}}\t{{.Ports}}"
```

Esperado: `catalaxia-engine-dev` con `127.0.0.1:5433->5432/tcp` y
`catalaxia-db` con `127.0.0.1:5432->5432/tcp`.

Si falta `catalaxia-engine-dev`: `RECOVERY_PROCEDURES.md` caso 2.

### 1.2 Destino del engine

```bash
python -c "from engine.config import load_settings; s=load_settings(); print(s.describe())"
```

Esperado: `... @127.0.0.1:5433/<base> mode=FAST prod=False`.

**`prod=True` ⇒ ABORTAR.** El guard EXT-010 de `engine/config.py` normalmente
lo impide lanzando `RuntimeError`; si lo ves en `True` es porque alguien puso
`ENGINE_ALLOW_PROD=1`. Quitá esa variable.

### 1.3 Base y esquemas

```bash
docker exec catalaxia-engine-dev psql -U catalaxia -d catalaxia -tAc \
  "SELECT string_agg(nspname,',' ORDER BY nspname) FROM pg_namespace \
   WHERE nspname IN ('engine','identity_v1','fetch_raw','parsed','derived','market')"
```

Esperado (base de engine completa): `derived,engine,fetch_raw,identity_v1,parsed`.
`market` aparece sólo si Market está instalado.

Si faltan esquemas, la base no tiene las migraciones: §3.

### 1.4 Producción intacta (línea base)

```bash
docker exec catalaxia-db psql -U catalaxia -d catalaxia -tAc \
  "SELECT string_agg(nspname,',') FROM pg_namespace \
   WHERE nspname NOT LIKE 'pg_%' AND nspname<>'information_schema'"
```

Esperado: **`public`** y nada más. Producción no tiene `parsed` ni `derived`;
si los tuviera, algo escribió donde no debía → `RECOVERY_PROCEDURES.md` caso 20.

### 1.5 Huella de `screener.db`

```bash
stat -c '%y %s' data/screener.db
```

Anotá el resultado. Al terminar el E2E tiene que ser **idéntico**, salvo que
hayas corrido a propósito una etapa del camino legacy de CNV (que sí escribe
ahí).

---

## 2 · Variables de entorno

Se leen en `engine/config.py` (`load_settings`), y **`.env` de la raíz del repo
se combina con el entorno del proceso — el entorno gana**.

**No hace falta exportar la contraseña.** El repo tiene un archivo `.env` con
`POSTGRES_PASSWORD`, que es de donde salen `ENGINE_DB_PASSWORD` y
`ENGINE_ADMIN_DB_PASSWORD` por defecto. Si el comando de §1.2 imprime la línea
esperada, el `.env` está bien y no tenés que tocar nada.

Si **no** existe `.env` (instalación nueva), crealo en la raíz con al menos:

```
POSTGRES_PASSWORD=<la contraseña del contenedor catalaxia-engine-dev>
```

Sin eso, la conexión falla con `password authentication failed`, no con un
mensaje que mencione el `.env`.

| variable | default | qué hace |
|---|---|---|
| `ENGINE_DB_HOST` | `127.0.0.1` | host |
| `ENGINE_DB_PORT` | `5433` | **5432 dispara EXT-010** |
| `ENGINE_DB_NAME` | `catalaxia` | base |
| `ENGINE_DB_USER` | `catalaxia_engine` | usuario de aplicación, **no** superusuario (F-025) |
| `ENGINE_DB_PASSWORD` | `POSTGRES_PASSWORD` | contraseña |
| `ENGINE_ADMIN_DB_USER` | `catalaxia` | usuario para DDL |
| `ENGINE_ADMIN_DB_PASSWORD` | `POSTGRES_PASSWORD` | |
| `ENGINE_MODE` | `FAST` | sólo `FAST`, `FULL`, `AUDIT`; otro valor ⇒ `ValueError` |
| `ENGINE_ALLOW_PROD` | `0` | `1` desactiva EXT-010. **No usar en DEV local.** Excepción declarada: el servicio `engine` de `docker-compose.yml` (F12) lo fija en `"1"` a propósito — ahí el puerto 5432 dentro del compose **es** el destino productivo del VPS, no un accidente (ver `docs/review/26_F12_ARCHITECTURE_DECISION.md`) |
| `ENGINE_STATEMENT_TIMEOUT_MS` | `120000` | timeout de sentencia (F-028) |

Ejemplo de invocación con destino explícito (recomendado siempre):

```bash
ENGINE_DB_NAME=catalaxia ENGINE_DB_PORT=5433 python scripts/engine/s00_smoke.py
```

---

## 3 · Migraciones

**No hay un comando de migración separado.** Las aplica
`engine.db.apply_migrations`, que los propios scripts de etapa invocan al
arrancar. Aplica en orden determinista: primero `migrations/engine/*.sql`,
después `migrations/market/*.sql`, cada carpeta ordenada por nombre.

Verificar qué se aplicó:

```bash
docker exec catalaxia-engine-dev psql -U catalaxia -d catalaxia -c \
  "SELECT filename, applied_at FROM engine.schema_migrations ORDER BY filename DESC LIMIT 10"
```

Dos detalles que confunden si no se saben:

- El registro acepta **dos formatos**: nombre desnudo (`008_identity_v1.sql`,
  bases anteriores a F-051) y con carpeta (`engine/008_identity_v1.sql`). Ambos
  cuentan como aplicada.
- Las migraciones de `market/` **se saltan sin error** si la tabla que
  necesitan no existe (`MARKET_REQUIERE` en `engine/db.py`). No es una falla:
  se aplicarán cuando Market esté instalado.

---

## 4 · Mirar corridas y etapas

### Corridas recientes

```bash
docker exec catalaxia-engine-dev psql -U catalaxia -d catalaxia -c \
  "SELECT run_id, mode, status, pipeline_version, started_at, finished_at \
     FROM engine.runs ORDER BY started_at DESC LIMIT 10"
```

`status` es `RUNNING`, `OK`, `BLOCKED` o `ABORTED`. `ABORTED` lo escribe el
`finally` de `run_scope` cuando el cuerpo levanta una excepción.

### Etapas de una corrida

```bash
docker exec catalaxia-engine-dev psql -U catalaxia -d catalaxia -c \
  "SELECT stage_id, state, prev_state, gate_status, gate_reasons, started_at \
     FROM engine.stage_runs WHERE run_id='<RUN_ID>' ORDER BY started_at"
```

### El reporte completo de una etapa

```bash
docker exec catalaxia-engine-dev psql -U catalaxia -d catalaxia -tAc \
  "SELECT jsonb_pretty(report) FROM engine.stage_runs \
    WHERE run_id='<RUN_ID>' AND report IS NOT NULL ORDER BY started_at DESC LIMIT 1"
```

Cómo leerlo: `appendices/LOG_CATALOG.md` §2.

### Corridas huérfanas

`engine/db.py` expone `corridas_huerfanas(engine, horas=6.0)`: corridas en
`RUNNING` sin actividad reciente. Las etapas la llaman al arrancar.
Consulta manual equivalente:

```bash
docker exec catalaxia-engine-dev psql -U catalaxia -d catalaxia -c \
  "SELECT run_id, mode, started_at, \
          round(EXTRACT(epoch FROM (now()-started_at))/3600,1) AS horas \
     FROM engine.runs WHERE status='RUNNING' \
      AND started_at < now() - INTERVAL '6 hours' ORDER BY started_at"
```

Qué hacer con ellas: `RECOVERY_PROCEDURES.md` caso 4.

---

## 5 · Cómo leer un gate

`engine/states.py` define exactamente tres: **`PASS`**, **`WARNING`**, **`BLOCK`**.

| gate | exit code del script | qué significa | qué hacer |
|---|---|---|---|
| `PASS` | `0` | todos los checks bloqueantes pasaron | seguí a la etapa siguiente |
| `WARNING` | según el script (ver cada runbook) | hay observaciones no bloqueantes | leé `gate_reasons`; podés seguir |
| `BLOCK` | `1` | un check bloqueante falló | **no sigas**; ERROR_CATALOG |

`engine/report.py::StageReport.validate()` impone tres reglas que conviene
conocer porque explican fallas al cerrar una etapa:

1. Campos obligatorios no vacíos → si falta uno: `Reporte incompleto…`
2. **`checks` no puede estar vacío**: *"terminó sin excepción nunca es PASS"*.
3. **Conciliación**: `expected == parsed + rejected`. Si no cierra, la etapa
   levanta `Conciliacion invalida` aunque no haya habido ningún error.

---

## 6 · Convención de nombres de etapa — cuidado

En `engine.stage_runs` conviven **`C3_CNV_fetch`** y **`C3_CNV_FETCH`**. No son
la misma etapa para la base: son dos claves distintas. La variante en mayúsculas
tiene 120 transiciones y **ningún reporte ni gate**. Al consultar, usá siempre
el `stage_id` exacto que declara el script (`STAGE_ID` en su cabecera), y si
buscás histórico completo de CNV usá `upper(stage_id)='C3_CNV_FETCH'`.

Registrado como `SOFTWARE GAP SG-06`.

---

## 7 · Evidencia que hay que guardar de toda corrida

Guardá siempre estos cuatro, en un directorio con la fecha:

1. **`run_id`** de la corrida.
2. La salida de consola completa del comando.
3. El `report` JSON de cada etapa (§4).
4. `hash_out` de cada etapa, para comparar entre corridas.

Sin el `run_id` no se puede reconstruir nada después: es la clave de
`engine.runs`, `engine.stage_runs`, `engine.checkpoints` y de las tablas de
descarga.
