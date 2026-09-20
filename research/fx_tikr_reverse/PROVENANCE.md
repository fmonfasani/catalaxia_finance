# PROVENANCE.md — FX engine (AGENTE 02, rama `feature/fx-research-engine`)

Cadena exigida por celda: fuente → descarga → RAW → parse → normalización →
publicación, con responsable y versión en cada eslabón. RAW inmutable; toda
corrección = archivo nuevo versionado (common.py::write_raw_noreplace).

## 1. Fuentes (primarias primero)

| Dato | Fuente primaria | Acceso | Auth | Estado |
|---|---|---|---|---|
| A3500 | BCRA API Estadísticas Cambiarias v1.0 (`api.bcra.gob.ar/.../Cotizaciones`) | GET JSON | no | VERIFICADO POR EJECUCIÓN 2026-09-15 |
| OFICIAL minorista | BCRA serie histórica cierre (`/cierre-de-cotizaciones-resultado/`, POST `moneda=2`, metodología Com. B 9791) | POST HTML | no | VERIFICADO POR EJECUCIÓN 2026-09-15 |
| MEP/CCL/Dollar Index/CCL Index | BYMA DataLens/OMS | API | **requerida, ausente** | AUTH_REQUIRED (raw/byma/*.status.json) |
| Precios ARS/USD/cable | BYMA EOD (oficial) / yfinance (UNDECLARED) | API | mixto | PENDING (registry listo, sin precios inventados) |
| TIKR 12 FX | encargo P8 (fixture) | — | — | fixture externo, no evidencia |

## 2. Eslabones y artefactos

```
BCRA API/POST ──(collector+meta)──▶ raw/bcra/a3500/*.json | raw/bcra/oficial/snapshot_*.html
        │ sha256 + source_url + retrieved_at + http_status + collector + git_commit
        ▼
parsed/bcra_oficial.csv (provenance_id por fila) + RAW A3500 directo
        ▼
parsed/universe.csv (target_date + eff_* + lag + status, OBS-V1, universe@v1.0.0)
        ▼
normalized/fx_reference.parquet/.csv (52 filas, provenance_id por fila, normalize@v1.0.0)
        ▼
RUN_REPORT.md (hashes + conteos de esta corrida)
```

- Cada RAW A3500: `meta.{source_url,retrieved_at,source_date,sha256,http_status}` ✔
  (test `test_raw_a3500_hash_coherente` recalcula el sha).
- Cada fila normalizada: `provenance_id` con fecha efectiva + lag + sha12 ✔.
- BYMA: status con endpoint + docs + motivo + acción requerida ✔ (sin precios fantasma).
- Instrumentos: `validate_quote()` exige 13 campos + `source*retrieved_at*sha256` ✔.
- Reconstrucción: cada día conserva `legs[]` (instrumento, fx parcial, reason, flags)
  + `reconstruct_version` ✔.
- Fixture TIKR: `provenance=encargo-AGENTE02-P8`, separado de `fx_reference` ✔
  (TIKR nunca es fuente de FX).

## 3. Reproducibilidad (clase A salvo descargas)

- Descargas (clase B): re-ejecutables, idempotentes por `source_date`
  (`EXISTS_IDENTICAL`, nunca UPDATE).
- `universe.py → normalize.py`: deterministas bit a bit sobre el mismo RAW
  (test `test_pipeline_clase_a_determinista`).
- Versiones fijadas: collectors `bcra_a3500/oficial@v1.0.0`, `universe/normalize/
  reconstruct/stats_ext@v1.0.0`, `pyarrow 25.0.1`, `pandas 3.0.1`, git `f375090`.
- Auditor: comandos en `README_ENGINE.md`; admiración: nada escribe fuera de
  `research/fx_tikr_reverse/` (test `test_sandbox_rechaza_fuera`).
