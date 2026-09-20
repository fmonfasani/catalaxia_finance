# Reproducibilidad — REQ-FX-010 (runbook del auditor independiente)

version: repro-v1.0.0

## 1. Principio

Un auditor con máquina limpia + este repo + `.env` (sólo secretos) reproduce
matriz, estadísticos, votos y veredicto bit a bit, sin acceso a producción,
sin red salvo descargas declaradas (clase B) y sin intervención manual.

## 2. Comandos (orden fijo)

```powershell
# 0. Aislamiento: jamás tocar producción
$env:SCREENER_DB = "fx_tikr_sandbox.db"   # los scripts FX deben respetarlo o abortar

# 1. Matriz objetivo (clase A: sin red, determinista)
python research/fx_tikr_reverse/scripts/build_target_matrix.py `
  --out research/fx_tikr_reverse/outputs/target_dates.csv
# esperado: 26 filas (2020-Q1..2026-Q2), 12 POC; hash SHA256 publicado en outputs/

# 2. Estadísticos (clase A)
python -m pytest research/fx_tikr_reverse/tests/ -q

# 3. Descargas FX (clase B: con red, idempotentes por (fecha, tipo))
python research/fx_tikr_reverse/scripts/fetch_bcra_a3500.py --from 2020-01-01 --to 2026-06-30
python research/fx_tikr_reverse/scripts/fetch_bcra_oficial.py --from 2020-01-01 --to 2026-06-30
python research/fx_tikr_reverse/scripts/fetch_direct_mep_ccl.py --from 2020-01-01 --to 2026-06-30
python research/fx_tikr_reverse/scripts/reconstruct_mep_ccl.py --from 2020-01-01 --to 2026-06-30
# cada uno: guarda crudo en 01_raw/<fuente>/<fecha>.json + fila normalizada con
# provenance; re-correr no duplica (INSERT OR REPLACE por clave canónica + log).

# 4. FX implícito TIKR (clase A una vez curado el benchmark a RAW)
python research/fx_tikr_reverse/scripts/extract_tikr_fx.py `
  --benchmark data/TIKR_METR_BENCHMARK_ARS_USD.xlsx `
  --out research/fx_tikr_reverse/outputs/tikr_implied_fx.csv

# 5. Comparación + veredicto (clase A)
python research/fx_tikr_reverse/scripts/compare_stats.py `
  --out research/fx_tikr_reverse/outputs/CERTIFICATION.md
```

## 3. Fijación de entorno

- `research/fx_tikr_reverse/requirements-fx.txt`: `openpyxl`, `pytest` (versiones
  fijadas tras primera ejecución verificada; hasta entonces NO DETERMINABLE).
- Todo script imprime `git_commit + script_version + timestamps` y los persiste
  en cada salida (provenance de código, cfr. PROVENANCE_SPECIFICATION §7).
- `outputs/` contiene `MANIFEST.sha256` con hash de cada artefacto + comando que
  lo produjo (MRR de corrida).

## 4. Criterio de aceptación REQ-FX-010

La reproducción es válida si, en máquina limpia: (a) `target_dates.csv` hash
idéntico, (b) tests en verde, (c) `CERTIFICATION.md` con mismo método/confianza/D
y misma tabla de votos (tolerancia 0 salvo timestamps de descarga), (d) ningún
script escribió fuera de `research/fx_tikr_reverse/`.
Hoy: (a)–(b) pendientes de primera ejecución; (c)–(d) NO DETERMINABLES.
