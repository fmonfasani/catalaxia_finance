# FX TIKR CLOSEOUT — AGENTE 04

## Qué hacer

Copiar esta carpeta dentro de:

research/fx_tikr_reverse/scripts/closeout/

y ejecutar desde la raíz del repositorio:

```powershell
python research/fx_tikr_reverse/scripts/closeout/07_RUN_ALL.py
```

## Decisiones que DEBÉS congelar

Editar `00_DECISION_CONFIG.py` ANTES de ejecutar:

```python
"reference_sources": ["A3500", "OFICIAL"]
```

Es la decisión principal del POC actual.

No cambiar:

```python
"missing_policy": "NO_FILL"
"winner_policy": "NO_WINNER"
```

## Qué resuelve

1. Audita provenance del fixture TIKR.
2. Ejecuta comparación real TIKR vs referencias.
3. Calcula MAE/RMSE/mediana/error relativo.
4. Ejecuta análisis de robustez.
5. Genera matriz de validación.
6. Genera gate de certificación.

## Qué NO hace

No declara que TIKR use A3500, Oficial, MEP o CCL.

Aunque una serie tenga error extremadamente pequeño:

```text
EMPIRICAL_MATCH
```

no equivale a:

```text
PROPRIETARY_METHOD_PROVEN
```

## Outputs

```text
outputs/
├── input_manifest.json
├── tikr_provenance_audit.json
├── tikr_fx_comparison_detail.csv
├── tikr_fx_comparison_summary.csv
├── tikr_fx_comparison.json
├── tikr_fx_robustness.csv
├── validation_matrix.csv
└── CERTIFICATION_GATE.json
```

## Estado esperado inicialmente

Es perfectamente válido obtener:

```text
TIKR_FX_METHOD = UNKNOWN
confidence = 0.00
```

si la provenance primaria del fixture no puede ser demostrada.

Eso significa que el engine está funcionando pero falta evidencia de entrada.

## Siguiente decisión después de ejecutar

Si `tikr_provenance_audit.json` devuelve:

```text
NO_PRIMARY_SOURCE_FOUND
```

no inventar provenance. Conseguir el workbook/archivo original de TIKR y volver a ejecutar.

Si devuelve:

```text
SOURCE_FOUND_CANDIDATE
```

hacer binding manual de cada valor:

period → file → sheet → cell/row → value → sha256

antes de certificar.
