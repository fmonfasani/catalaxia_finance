# FX DATA ENGINEERING — AGENTE 02 (rama `feature/fx-research-engine`)

Infraestructura reproducible BCRA → RAW → PARSED → NORMALIZED + preparación
MEP/CCL instrumental para los quarters objetivo. **No emite conclusión sobre
qué FX utiliza TIKR** (eso corresponde a otro agente con `decision-v1.0.0`,
congelado en `00_DEFINIR/` y NO modificado aquí).

## Estructura (todo bajo `research/fx_tikr_reverse/`; producción intacta)

```
00_DEFINIR/            criterios congelados (NO TOCAR — AGENTE 02 no los cambia)
engine/                bcra_a3500.py · bcra_oficial.py · byma_status.py ·
                       instruments.py · reconstruct.py · universe.py ·
                       normalize.py · stats_ext.py · tikr_fixture.py · common.py
raw/bcra/a3500/        156 JSON (uno por día consultado, envelope + payload)
raw/bcra/oficial/      snapshot_<día>.html + .meta.json (serie 2010→hoy)
raw/byma/              4 status.json (AUTH_REQUIRED, sin credenciales inventadas)
raw/instruments/       SOURCES.md (investigación P3; ISIN NOT_VERIFIED)
parsed/                bcra_oficial.csv · universe.csv
normalized/            fx_reference.parquet (canónico) + .csv (espejo)
fixtures/              tikr_fx_12.csv (fixture P8, verbatim del encargo)
engine_tests/          18 tests (11 ejes del encargo)
scripts/stats.py       CONGELADO (sólo lectura desde stats_ext.py)
```

## Ejecución (orden fijo, idempotente)

```powershell
git checkout feature/fx-research-engine
python research/fx_tikr_reverse/engine/bcra_a3500.py --targets research/fx_tikr_reverse/00_DEFINIR/target_dates.csv --window 5
python research/fx_tikr_reverse/engine/bcra_oficial.py
python research/fx_tikr_reverse/engine/byma_status.py
python research/fx_tikr_reverse/engine/tikr_fixture.py
python research/fx_tikr_reverse/engine/universe.py
python research/fx_tikr_reverse/engine/normalize.py
python -m pytest research/fx_tikr_reverse/engine_tests/ research/fx_tikr_reverse/tests/ -q
```

Re-correr es seguro: RAW jamás se sobrescribe (`EXISTS_IDENTICAL`/`VERSIONED`),
los pasos clase A son deterministas bit a bit (ver `test_pipeline_clase_a_determinista`).

## Reglas del agente

- Rama exclusiva: `feature/fx-research-engine`. Criterios de aceptación intactos.
- RAW inmutable; sin imputación (NULL + `null_reason`); sin forward-fill.
- BYMA sin credenciales → `AUTH_REQUIRED`, nunca inventadas.
- ISIN no verificado → `null + NOT_VERIFIED`, nunca inventado.
- `date` en normalized = `target_date` (la efectiva vive en `universe.csv` + provenance).
- Detalle de columnas: `DATA_DICTIONARY.md`. Cadena de custodia: `PROVENANCE.md`.
  Evidencia de la corrida: `RUN_REPORT.md`.
