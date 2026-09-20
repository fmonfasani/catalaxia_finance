# Criterios de decisión pre-registrados — REQ-FX-009
# CONGELADO en DEFINIR. Prohibido modificar tras observar comparaciones.
# Cualquier cambio exige nueva versión + motivo + re-ejecución completa.
# Objetivo: impedir que la metodología se adapte a los resultados.

version: decision-v1.0.0
frozen: 2026-09-15

## 1. Voto por período (sobre MEDIAN del FX implícito; mean sólo sensibilidad S2)

Entradas por período: abs_rel_err de los 6 candidatos + distancias entre candidatos.

1.1 Si el ganador `min(abs_rel_err) > 1,0 %` → voto = `NO_DECISION`
   (ningún candidato explica el período; señal de HYBRID/UNKNOWN, no de forzar).

1.2 Indistinguibilidad: si `|candA − candB| / candB < 1,0 %`, A y B son
   indistinguibles ese período. Si ganador y runner-up son indistinguibles →
   voto = `TIE{ganador, runner-up[, ...]}` (no discrimina; no cuenta como victoria
   exclusiva). Justificación: A3500 vs OFICIAL convergen en 2025 (~1,8 % y menos);
   exigir discriminación imposible fabricaría precisión falsa.

1.3 Margen: si distinguibles pero `(runner_up_err − winner_err) < 0,50 pp`
   (puntos porcentuales de error relativo) → voto = `WEAK_{ganador}`
   (cuenta para quorum pero con peso 0,5; ver §3).

1.4 En otro caso → voto = `{ganador}` con fuerza 1.

1.5 Celdas con settlement UNDECLARED o N<2 métricas incluibles → voto máximo
   `WEAK_*`, nunca victoria plena. Celdas NULL no votan.

## 2. Quorum y veredicto global (12 períodos POC)

- D = nº de períodos POC con voto decisivo o débil (excluye NO_DECISION y TIE
  totalmente irresoluble). TIE entre {A,B} suma 0,5 a cada uno.
- Si D < 8 (quorum 2/3) → `TIKR_FX_METHOD = UNKNOWN` (evidencia insuficiente),
  sin importar el ranking. Clasificación de hallazgo: NO DETERMINABLE.
- Si D ≥ 8, sea w1 el candidato con más peso, w2 el segundo:
  - w1_peso / D ≥ 0,75 y w1 pleno (no sólo WEAK) en ≥ 6 períodos → candidato w1.
  - 0,60 ≤ w1_peso / D < 0,75 → candidato w1 con confianza degradada un nivel.
  - Si w1 y w2 tienen cada uno ≥ 0,30 × D en subperíodos distintos con victorias
    plenas → `HYBRID` (describe régimen, p.ej. A3500→MEP; prohibido promediar).
  - Resto → `UNKNOWN`.

## 3. Confianza (pre-registrada, no ajustable post-hoc)

```
TIKR_FX_CONFIDENCE = (w1_peso / D) × cobertura × precisión
  cobertura  = D / 12
  precisión  = 1 − min(median(abs_rel_err_w1 sobre D), 0,05) / 0,05 × 0,25
             (0,75 si error mediano 1 %+; 1,0 si error 0 %)
```

Niveles publicados (función de la fórmula + condiciones duras):

| Nivel | Condición dura |
|---|---|
| STRONG | D ≥ 10, w1_peso/D ≥ 0,80, mediana abs_err w1 ≤ 0,50 %, margen ≥ 1 pp en ≥ 6 períodos |
| MODERATE | D ≥ 8, w1_peso/D ≥ 0,60, mediana abs_err w1 ≤ 1,0 % |
| LOW | veredicto con D ≥ 8 pero sin condiciones MODERATE |
| — | si no hay veredicto: método UNKNOWN, confianza numérica igualmente reportada como 0,00–0,39 (no publicable como hallazgo) |

## 4. Reglas anti-oracle y anti-ajuste

- H1 (METR anual ≈ mayorista) NO vota: es contexto, no evidencia quarterly.
- Ningún umbral se mueve tras ver la tabla de desvíos. Si los datos caen en zona
  TIE/NO_DECISION, la respuesta correcta es UNKNOWN/HYBRID, no recalibrar.
- RECONSTRUIDA sólo puede ganar si cumple instrumental_spec §4 (settlement
  declarado, patas mismo día); si no, el voto cae a su contraparte DIRECTA o a
  NO_DECISION.
- Sensibilidades S1–S3 se publican en apéndice; si contradicen al primario
  (ganador distinto en ≥ 3 períodos), la confianza baja un nivel automáticamente.

## 5. Salidas posibles (cerradas)

`A3500 | OFICIAL | MEP | CCL | MEP_RECONSTRUCTED | CCL_RECONSTRUCTED | HYBRID | UNKNOWN`
Etiquetas MEP/CCL sin sufijo = serie DIRECTA. Toda salida incluye
`{método, confianza, D, tabla de votos por período, mediana de errores, sensibilidades}`.
Sin estos 6 campos la certificación es inválida.
