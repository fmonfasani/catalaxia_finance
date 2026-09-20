# FX TIKR Reverse — scripts de cierre

Ejecutar desde la raíz del proyecto:

```bash
python fx_reverse_finish_scripts/01_contract.py
python fx_reverse_finish_scripts/02_build_quarterly_panel.py
python fx_reverse_finish_scripts/03_tikr_quarterly_stats.py
python fx_reverse_finish_scripts/04_backtest.py
python fx_reverse_finish_scripts/05_acceptance_gate.py
```

O todo junto:

```bash
python fx_reverse_finish_scripts/06_run_all.py
```

## Outputs

- `00_DEFINIR/fx_acceptance_contract.json`
- `normalized/fx_panel_normalized.csv`
- `outputs/tikr_quarterly_fx_stats.csv`
- `outputs/fx_tikr_backtest_detail.csv`
- `outputs/fx_tikr_backtest_summary.csv`
- `outputs/fx_acceptance_matrix.csv`

Importante: el script no afirma qué metodología propietaria usa TIKR.
Produce evidencia reproducible para contrastar A3500, oficial, MEP, CCL y
series reconstruidas.
