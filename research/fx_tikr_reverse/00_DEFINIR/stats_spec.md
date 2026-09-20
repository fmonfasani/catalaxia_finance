# Especificación estadística — REQ-FX-007
# + Comparación — REQ-FX-008 (definición; la ejecución vive en scripts/compare_stats.py)

version: stats-v1.0.0

## 1. Unidad de análisis (fijada antes de ver resultados)

Para cada `period_id` (target trimestral) y cada métrica TIKR con par ARS↔USD:

```
FX_implicito(métrica, período) = ARS(métrica, período) / USD(métrica, período)
```

Sólo métricas con ambos lados > 0 y en la misma base (mismo FY/publicación).
Exclusiones pre-registradas (por H2, VERIFICADO POR EJECUCIÓN sobre METR):
`EBITDA` (no reconcilia internamente), `Promedio ponderado de acciones` (artefacto
de conversión), múltiplos publicados no reconstruibles. Toda exclusión adicional
post-hoc está PROHIBIDA; si aparece una anomalía nueva se reporta como ANOMALY y
no se elimina del N sin nueva versión de esta spec.

## 2. Estadísticos obligatorios por período (REQ-FX-007)

Sobre el vector {FX_implicito(m) : m ∈ métricas incluibles del período}, con N =
nº de métricas incluibles (NO nº de empresas; la extensión multi-emisora agregará
dimensión entidad después):

- N, mean (aritmética), median, mode, trimmed mean (10 % por cola), MAD
  (median absolute deviation, con constante 1,4826 para consistencia normal),
  IQR (Q3−Q1), standard deviation (muestral, ddof=1; si N<2 → NULL),
  CV (sd/mean; si mean=0 → NULL).
- mode: valor más frecuente exacto; si no hay repetición → NULL + NO_MODE
  (no se inventa por redondeo; tolerancia de redondeo declarada aparte: TIKR
  redondea a millón → banda de ±0,3 % documentada en H1).
- Todos los estadísticos se computan sobre valores en ARS por USD, sin log.

Implementación: `scripts/stats.py` (pura, sin red, sin BD). Tests: N=1, valores
idénticos (sd=0, CV=0), vector vacío (todo NULL + EMPTY_VECTOR), mode sin
repetición.

## 3. Comparación — REQ-FX-008

Candidatos (6 columnas separadas, jamás promediadas entre sí):

```
A3500 | OFICIAL | MEP_DIRECTA | CCL_DIRECTA | MEP_RECONSTRUIDA | CCL_RECONSTRUIDA
```

Cada una observada con OBS-V1 (target_dates.csv) + su observation_date/lag.

Métricas de desvío por (período, candidato), calculadas sobre el MEDIAN implícito
(robusto; el mean se reporta como sensibilidad):

```
rel_err = (median_implicito − candidato) / candidato
abs_rel_err = |rel_err|
```

Se reporta además el desvío por métrica individual (para detectar que un candidato
gana sólo por promediación).

## 4. REQ-FX-006 · No imputación

- Celda FX ausente (sin publicación en ventana, pata faltante, settlement mismatch)
  → NULL + null_reason tipificado (NO_PUBLICATION_IN_WINDOW, MISSING_LEG,
  SETTLEMENT_MISMATCH, EXCLUDED_ANOMALY, NO_MODE, EMPTY_VECTOR…).
- Prohibido: forward-fill desde futuro, interpolación, copiar otro candidato,
  arrastrar trimestre anterior. El N por período refleja SÓLO celdas observadas.
- Test `test_no_imputation` falla si algún pipeline escribe un número sin provenance
  completa o rellena un NULL silenciosamente.

## 5. Sensibilidades pre-registradas (no deciden, se reportan)

- S1 AVG5: candidato como media de 5 publicaciones ≤ target (ventana 10 días).
- S2 mean-vs-median del implícito.
- S3 con/sin métricas de balance (sólo resultado si el flujo difiere del stock).
