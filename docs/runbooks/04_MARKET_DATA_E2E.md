# 04 · DATOS DE MERCADO — E2E

Los precios no vienen del pipeline contable. Son otra fuente, otras tablas y
otro ciclo de vida.

---

## 1 · Estado

Market **está instalado y tiene datos reales**:

| tabla | filas |
|---|---:|
| `market_price_daily` | 4.799.938 |
| `market_corporate_actions` | 51.917 |
| `market_data_quality` | 8.322 |
| `market_fetch_log` | 601 |
| `market_instruments` | 584 |
| `market_symbol_mappings` | 584 |

Lo que **no** funciona es el enlace con el pipeline contable: ver §5.

## 2 · Instalación del esquema

Market tiene **dos** mecanismos, y hay que conocer los dos:

1. **`scripts/market/m19_apply_schema.py`** aplica `market_schema.sql`
   consolidado, **sin versionado**. Es el que crea las tablas.
2. **`migrations/market/*.sql`** (tres archivos: `012_rol_market_readonly.sql`,
   `013_venue_ticker.sql`, `025_f038_invariantes_corrida.sql`) los aplica el
   runner de `engine/db.py`, **después** de los de engine.

**El orden importa y hay una trampa documentada (F-051):** las migraciones de
`market/` se **saltan sin error** si la tabla que necesitan no existe. El mapa
está en `engine/db.py::MARKET_REQUIERE`:

| migración | tabla que exige |
|---|---|
| `012_rol_market_readonly.sql` | ninguna (sólo roles/GRANTs) |
| `013_venue_ticker.sql` | `market_instruments` |
| `025_f038_invariantes_corrida.sql` | `market_raw_runs` |

Si corrés el runner **antes** de `m19_apply_schema.py`, las dos últimas se
saltan en silencio y `ck_estado_coherente_con_artefacto` (F-038) nunca llega a
una base limpia. **Orden correcto:**

```bash
python scripts/market/m19_apply_schema.py
ENGINE_DB_NAME=catalaxia ENGINE_DB_PORT=5433 python scripts/engine/s00_smoke.py
```

Verificá:
```bash
docker exec catalaxia-engine-dev psql -U catalaxia -d catalaxia -c \
  "SELECT filename FROM engine.schema_migrations WHERE filename LIKE 'market/%'"
```
Esperado: las tres. Si faltan `013` y `025`, invertiste el orden.

## 3 · Descarga

```bash
python scripts/market/m2_fetch_engine.py --limit 10 --json-out /tmp/market.json
```

| argumento | default | qué hace |
|---|---|---|
| `--instruments` | todos | lista de tickers separados por coma |
| `--limit` | sin tope | máximo de instrumentos |
| `--stage` | `batch` | etiqueta de la corrida |
| `--no-snapshot` | off | no escribe snapshot |
| `--json-out` | — | vuelca el reporte de la corrida |

Registro: `market_fetch_log`, `market_raw_runs`, `market_raw_files`.

## 4 · Calidad

```bash
python scripts/market/m4_quality.py
python scripts/market/m5_golden_case.py
```

Resultados en `market_data_quality` (8.322 filas observadas).

## 5 · El problema estructural

**`market_instruments.entity_id` es un entero legacy** (`58`, `59`, `60`…),
mientras que el engine usa `entity_id` namespaced (`CIK:0000904851`,
`CUIT:30657863676`). Son dos espacios de identificadores distintos y **no hay
tabla puente**.

```bash
docker exec catalaxia-engine-dev psql -U catalaxia -d catalaxia -c \
  "SELECT count(*) instrumentos, \
          count(*) FILTER (WHERE entity_id ~ '^(CIK|CUIT|LEI):') namespaced \
     FROM market_instruments"
```

Consecuencia directa: **ningún ratio que combine precio y contabilidad se puede
construir de forma trazable para un emisor arbitrario.** Es la causa de que
`derived.ratio` tenga 36 filas y 9 emisores, en un universo de 584
instrumentos.

`SOFTWARE GAP SG-10`. Es la remediación de mayor impacto del plan
(`RUNBOOK_READINESS_REPORT.md` §18).

## 6 · Reglas al usar un precio

1. **Un precio pertenece a un instrumento, no a una empresa.** Registrá
   `instrument_id`.
2. **La moneda es la del venue.** `currency` en `market_instruments`.
3. **`venue_ticker` ≠ `ticker_canonico`.** Para pedir precio se usa
   `venue_ticker`. Confundirlos trae el precio de otra empresa: es un modo de
   falla ya observado con colisiones de tickers BYMA/EEUU.
4. **ADR:** aplicar `ratio_adr` una sola vez, o ninguna si se cancela. Ver
   `02A_SEC_EDGAR_ADR_ANNEX.md` §4.
5. **Sin precio ⇒ `NOT_CALCULABLE`.** Nunca sustituir por otra fecha, otro
   instrumento u otro proveedor sin registrarlo.
