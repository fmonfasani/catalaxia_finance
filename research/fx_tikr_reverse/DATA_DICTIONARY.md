# DATA_DICTIONARY.md — FX engine (AGENTE 02, rama `feature/fx-research-engine`)

Convenciones: `NULL` = ausente con `null_reason`/`status` (jamás 0 ni arrastrado).
Fechas ISO `YYYY-MM-DD`. Montos ARS por USD salvo `currency` en quotes.

## 1. `raw/bcra/a3500/YYYY-MM-DD.json` (envelope, 1 por día consultado)

| Campo | Tipo | Descripción |
|---|---|---|
| `meta.source` | str | `BCRA-estadisticas-cambiarias-v1.0` |
| `meta.fx_type` | str | `A3500` |
| `meta.source_url` | str | GET exacto (`.../Cotizaciones?fecha=YYYY-MM-DD`) |
| `meta.retrieved_at` | str | ISO-8601 UTC de descarga |
| `meta.source_date` | str | día consultado (= nombre archivo) |
| `meta.sha256` | str | SHA256 del `payload` canónico (claves ordenadas, UTF-8) |
| `meta.http_status` | int | 200 (otro → FETCH_ERROR, sin archivo) |
| `meta.collector/engine/git_commit` | str | versiones para reproducibilidad |
| `payload` | obj | respuesta BCRA íntegra (`results.fecha\|None`, `detalle[]`) |
| `parsed_hint.usd_tipoCotizacion` | float\|null | USD `tipoCotizacion` si >0 (días sin rueda → null) |

## 2. `raw/bcra/oficial/snapshot_<día>.html` + `.meta.json`

HTML íntegro del POST `cierre-de-cotizaciones-resultado/` (`moneda=2`); meta con
`source_url` (+`[POST moneda=2]`), `retrieved_at`, `source_date=snapshot-<día>`,
`sha256` del HTML, `http_status`. Nota: `venta` = vendedor minorista (canónico).

## 3. `parsed/bcra_oficial.csv`

| Columna | Tipo | Descripción |
|---|---|---|
| `source_date` | date | día de la rueda (PK, único) |
| `compra` | float | minorista comprador |
| `venta` | float | minorista vendedor (canónico OFICIAL) |
| `provenance_id` | str | `bcra-oficial:<fecha>:<sha12>` del snapshot |

## 4. `raw/byma/<producto>.status.json` (MEP, CCL, Dollar_Index, CCL_Index)

`{source, producto, endpoint, docs, status: AUTH_REQUIRED\|NOT_AVAILABLE, reason,
source_url, retrieved_at, source_date, sha256: null, collector, git_commit,
action_requerida}`. Sin precios: con auth ausente no hay dato que persistir.

## 5. `raw/instruments/SOURCES.md` + `engine/instruments.py` REGISTRY

Registry por especie: `instrument, ticker, isin(null)+isin_status(NOT_VERIFIED),
market, settlement, currency, rol[, ratio, par]`.
Quote (`instrument_quote`, 1 fila por pata): `instrument, ticker, isin, date,
market∈{BYMA,NYSE,NASDAQ,EXTERIOR}, settlement∈{CI,24hs,48hs,T+1,T+2,UNDECLARED},
currency∈{ARS,USD,USD_CABLE}, price(>0), volume, source, source_url,
retrieved_at, sha256`. `validate_quote()` → `(ok, null_reason)` con
`MISSING_*|BAD_*|ZERO_OR_NEGATIVE_PRICE`.

## 6. `parsed/universe.csv` (26 filas: 2020-Q1→2026-Q2)

`period, target_date, eff_a3500, lag_a3500, status_a3500, eff_oficial,
lag_oficial, status_oficial, universe_version`. `eff_*` = última publicación
≤ target con lag ≤5 (`OBS-V1`); si no hay → vacío + `NO_PUBLICATION_IN_WINDOW`.
`target_date` se conserva siempre (sin reemplazo silencioso).

## 7. `normalized/fx_reference.parquet` (+ espejo `.csv`) — P6 exacto

| Columna | Tipo | Descripción |
|---|---|---|
| `date` | date | **target_date** del quarter |
| `period` | str | `YYYY-QN` |
| `source` | str | `BCRA-estadisticas-cambiarias-v1.0` \| `BCRA-minorista-serie-cierre` |
| `instrument` | str | `N/A` (referencia no operable) |
| `fx_type` | str | `A3500` \| `OFICIAL` |
| `fx_value` | float\|null | referencia del día efectivo (null + reason en provenance si sin dato) |
| `volume` | null | N/A en referencias |
| `settlement` | str | `N/A` en referencias |
| `provenance_id` | str | `bcra-a3500:<eff>:lag<L>:<sha12>` \| `<prov-oficial>:lag<L>` \| `...:NULL:<reason>` |

52 filas (26×2). Filas MEP/CCL se agregan sólo con quotes validados (hoy: ninguna).

## 8. `fixtures/tikr_fx_12.csv` (fixture externo P8, no medición)

`period, target_date, tikr_fx, fixture_version, provenance(encargo-AGENTE02-P8)`.
12 filas verbatim (2023-Q3 349.97 … 2026-Q2 1483.70). No participa en `fx_reference`.

## 9. Estadística extendida (`engine/stats_ext.py::describe_ext`)

`describe()` congelado (N, mean, median, mode, trimmed_mean, MAD×1,4826, IQR,
sd ddof=1, CV, null_reasons) + `p10, p25, p75, p90` (interpolación lineal tipo
exclusive; N=1 → repiten el valor; N=0 → null + `EMPTY_VECTOR`).
