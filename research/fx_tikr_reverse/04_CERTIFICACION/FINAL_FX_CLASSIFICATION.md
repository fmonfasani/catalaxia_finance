# FINAL_FX_CLASSIFICATION — AGENTE 04 (Independent Certifier)

Fecha: 2026-09-15

```
TIKR_FX_METHOD      = UNKNOWN
TIKR_FX_CONFIDENCE  = 0.00
TIKR_FX_EVIDENCE    = insuficiente para certificar cualquier metodologia
                       (quarterly, POC 2023-Q3..2026-Q2)
```

## Fundamento (resumen ejecutivo)

De los 6 candidatos definidos en el encargo (A3500, OFICIAL, MEP, CCL,
MEP_RECONSTRUCTED, CCL_RECONSTRUCTED), solo **2 tienen datos primarios reales
con provenance verificable** (A3500, OFICIAL) y **ninguno de los 6 fue
efectivamente comparado contra TIKR**, porque:

1. El script de comparacion (`tikr_fx_compare.py`) es un stub que aborta por
   diseño, sin excepción.
2. MEP y CCL directos dependen de BYMA, que exige credenciales no
   provistas (`AUTH_REQUIRED`).
3. MEP y CCL reconstruidos dependen de precios de instrumentos (AL30, GD30,
   GGAL, YPF, PAMP) que no existen en el sandbox — el código de reconstrucción
   está listo y es correcto, pero no tiene insumo.
4. El benchmark TIKR mismo (los 12 valores objeto de estudio) no tiene una
   fuente primaria citable dentro del sandbox: su provenance dice
   "encargo, fixture externo, no medido aquí".

Esto **confirma de forma independiente** el veredicto que ya había emitido
AGENTE 03 en `outputs/CERTIFICATION.md` (`UNKNOWN`, `D=0 < quorum 8`). No es
una corrección — es una segunda medición, con acceso a material adicional que
el reporte interno no citaba explícitamente (`raw/`, `Perplexity/`), que
llega a la misma conclusión por caminos parcialmente distintos.

## Por qué no HYBRID, ni A3500, ni OFICIAL

Existe evidencia contextual (E-H1-METR-ANUAL, ver EVIDENCE_MATRIX.csv) de que,
a nivel **anual** y para **una sola emisora** (Metrogas), el FX implícito de
TIKR se aproxima al mayorista/A3500 con desvío bajo (0,0%-0,3%). Es tentador
usar esto para inclinar el veredicto hacia A3500. El proyecto mismo, en su
`decision_criteria.md` §4, prohíbe explícitamente ese atajo: la evidencia
anual "no vota" porque no es evidencia quarterly, y el propio benchmark del
que sale (`TIKR_METR_BENCHMARK_ARS_USD.xlsx`) tiene anomalías internas
documentadas que lo descalifican como oráculo.

Esta auditoría **respeta esa regla pre-registrada** y no la sortea. Ceder a
la tentación de anunciar "probablemente A3500" con base en 5 puntos anuales
de una sola empresa sería exactamente el tipo de inferencia-convertida-en-hecho
que el mandato de este certificador prohíbe.

## Qué haría falta para una clasificación distinta de UNKNOWN

Ver sección 9 de `CERTIFICATION_REPORT.md` y `BLOCKERS.csv` (B-01 a B-04).
En síntesis: ejecutar el comparador real contra un fixture TIKR con fuente
primaria y contra al menos 3 de las 4 series MEP/CCL con datos, alcanzando
D≥8 de los 12 períodos POC, sin mover ningún umbral de `decision-v1.0.0`
después de ver esa tabla.

## Statement de certificación

**NO SE CERTIFICA ninguna metodología.** El resultado correcto y auditable
hoy es `UNKNOWN`, con confianza `0.00`, por insuficiencia de evidencia — no
por evidencia contradictoria ni por fallo de la metodología de decisión, que
está correctamente diseñada para este mismo escenario.
