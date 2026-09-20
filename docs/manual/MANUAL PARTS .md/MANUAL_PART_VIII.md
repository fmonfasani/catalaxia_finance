# PARTE VIII — MARKET

Los precios no vienen del pipeline contable. Son otra fuente, otras tablas y
otro ciclo de vida — y hoy **no están enlazados** con la contabilidad.

**Estado:** `KNOWN_LIMITATION` (L-5, L-3 parcial).

**Material de base:** `docs/runbooks/04_MARKET_DATA_E2E.md` completo (117
líneas); `docs/manual/MANUAL_SCOPE.md` `L-5`, `C-6`; `outputs/runbook/
RUNBOOK_READINESS_REPORT.md` §18 (`SG-10`).

---

## Paso 1 · Estado del esquema

Market **está instalado y tiene datos reales**, según la siguiente
distribución:

| tabla | filas |
|---|---:|
| `market_price_daily` | 4.799.938 |
| `market_corporate_actions` | 51.917 |
| `market_data_quality` | 8.322 |
| `market_fetch_log` | 601 |
| `market_instruments` | 584 |
| `market_symbol_mappings` | 584 |

Lo que **no** funciona es el enlace con el pipeline contable (Paso 4 de este
capítulo).

---

## Paso 2 · Instalación del esquema — las dos vías y la trampa de orden

Market tiene **dos mecanismos**, y hay que conocer los dos:

1. **`scripts/market/m19_apply_schema.py`** aplica `market_schema.sql`
   consolidado, **sin versionado**. Es el que crea las tablas.
2. **`migrations/market/*.sql`** (`012_rol_market_readonly.sql`,
   `013_venue_ticker.sql`, `025_f038_invariantes_corrida.sql`) los aplica el
   runner de `engine/db.py`, **después** de los de engine.

**`Trampa documentada (F-051)`:** las migraciones de `market/` se **saltan sin
error** si la tabla que necesitan no existe. El mapa está en
`engine/db.py::MARKET_REQUIERE`:

| migración | tabla que exige |
|---|---|
| `012_rol_market_readonly.sql` | ninguna (solo roles/GRANTs) |
| `013_venue_ticker.sql` | `market_instruments` |
| `025_f038_invariantes_corrida.sql` | `market_raw_runs` |

Si el runner corre **antes** de `m19_apply_schema.py`, las dos últimas se
saltan en silencio y `ck_estado_coherente_con_artefacto` (F-038) nunca llega a
una base limpia. **Orden correcto:**

```bash
python scripts/market/m19_apply_schema.py
ENGINE_DB_NAME=catalaxia ENGINE_DB_PORT=5433 python scripts/engine/s00_smoke.py
```

Verificación:

```bash
docker exec catalaxia-engine-dev psql -U catalaxia -d catalaxia -c \
  "SELECT filename FROM engine.schema_migrations WHERE filename LIKE 'market/%'"
```

Esperado: **las tres**. Si faltan `013` y `025`, se invirtió el orden.

---

## Paso 3 · Descarga y calidad

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

Calidad y golden case:

```bash
python scripts/market/m4_quality.py
python scripts/market/m5_golden_case.py
```

Resultados en `market_data_quality` (8.322 filas observadas).

---

## Paso 4 · El problema estructural — por qué la valuación no generaliza

**`market_instruments.entity_id` es un entero legacy** (`58`, `59`, `60`…),
mientras que el engine usa `entity_id` namespaced (`CIK:0000904851`,
`CUIT:30657863676`). Son **dos espacios de identificadores distintos y no hay
tabla puente** — `KNOWN_LIMITATION (L-5)`, `SOFTWARE GAP SG-10`.

Verificación:

```bash
docker exec catalaxia-engine-dev psql -U catalaxia -d catalaxia -c \
  "SELECT count(*) instrumentos, \
          count(*) FILTER (WHERE entity_id ~ '^(CIK|CUIT|LEI):') namespaced \
     FROM market_instruments"
```

**Consecuencia directa:** ningún ratio que combine precio y contabilidad se
puede construir de forma trazable para un emisor arbitrario. Es la causa de
que `derived.ratio` tenga **36 filas y 9 emisores**, en un universo de 584
instrumentos. Es la remediación de mayor impacto del plan
(`RUNBOOK_READINESS_REPORT.md` §18, ítem 4).

**Situación por piloto:**

| piloto | precio | enlace | lectura |
|---|---|---|---|
| YPF | ADR + local | roto (L-5) | valuación puntual sí, generalizable no |
| KO | US simple, sin ADR | roto (L-5) | el contraste directo del Cap. de Ratios |
| METR | **sin instrumento resuelto** | — | ni siquiera hay fila |

---

## Paso 5 · Reglas al usar un precio

1. **Un precio pertenece a un instrumento, no a una empresa.** Registrá
   `instrument_id`.
2. **La moneda es la del venue.** `currency` en `market_instruments`.
3. **`venue_ticker` ≠ `ticker_canonico`.** Para pedir precio se usa
   `venue_ticker`. Confundirlos trae el precio de otra empresa: es un modo de
   falla ya observado con colisiones de tickers BYMA/EEUU.
4. **ADR:** aplicar `ratio_adr` **una sola vez**, o ninguna si se cancela.
   Nunca un precio ARS + un fundamental USD sin conversión (ver anexo ADR §4 y
   la regla de FX MEP).
5. **Sin precio ⇒ `NOT_CALCULABLE`.** Nunca sustituir por otra fecha, otro
   instrumento u otro proveedor sin registrarlo.

---

## GATE de la Parte VIII

Instalación correcta, datos presentes, calidad medida. **No** se puede
construir un múltiplo trazable para un emisor arbitrario hasta que se resuelva
`SG-10` (migrar `market_instruments.entity_id` a namespaced). El capítulo
quedó con `KNOWN_LIMITATION`, no con `PASS`.

**Pendiente `C-6`:** 9 de los 11 scripts de `scripts/market/` no están
documentados — este capítulo cubre `m19`, `m2`, `m4`, `m5` y nada más.

---

*Los conteos de este capítulo son los del `04_MARKET_DATA_E2E.md` en su fecha
de publicación; verificarlos con las consultas del Paso 4 antes de usarlos.*