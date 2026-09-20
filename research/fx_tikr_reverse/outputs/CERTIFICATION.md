# CERTIFICACIÓN INICIAL — FX TIKR (capa 11, fase DEFINIR)

```
TIKR_FX_METHOD = UNKNOWN
TIKR_FX_CONFIDENCE = 0.00
TIKR_FX_EVIDENCE = insuficiente para quarterly
```

Fecha: 2026-09-15 · git: f375090 · pipeline: fx_tikr_reverse DEFINIR-v1.0.0
Producción: NO TOCADA (sandbox `research/fx_tikr_reverse/`).

## 1. Por qué UNKNOWN (evidencia realmente disponible)

| # | Evidencia | Clasificación | Voto |
|---|---|---|---|
| E1 | METR anual FY2021–2025 FX≈mayorista 0,0–0,3 % (5 puntos, 1 emisora, anual) | VERIFICADO POR EJECUCIÓN (recomputado hoy) | contexto, NO vota (decision §4) |
| E2 | Anomalías internas benchmark (EBITDA, acciones/FX, múltiplos 2024) | VERIFICADO POR EJECUCIÓN | invalida uso como oracle |
| E3 | Series quarterly A3500/Oficial primarias, MEP/CCL directas+reconstruidas con OBS-V1 | NO DETERMINABLE (stubs fail-closed) | D=0 < quorum 8 → UNKNOWN por §2 |
| E4 | Matriz 26 períodos / 12 POC + OBS-V1 + stats + criterios congelados | VERIFICADO POR TEST (13 passed) | habilita futuro, no decide hoy |

D (períodos POC decididos) = 0. Quorum exigido = 8. Veredicto forzoso = UNKNOWN.

## 2. Campos de salida (decision §5 — incompletos = no publicable como hallazgo)

- método: UNKNOWN · confianza: 0.00 · D: 0/12 · votos: 12× NO_DATA ·
  mediana errores: NULL · sensibilidades S1–S3: NO DETERMINABLES.

## 3. Hallazgos de esta fase (taxonomía del encargo)

| ID | Severidad | Texto |
|---|---|---|
| F-FX-001 | OBSERVATION | H1 anual sugiere mayorista pero con n=5, 1 emisora, frecuencia anual y anomalías internas: insuficiente para afirmar metodología quarterly. |
| F-FX-002 | REQUIRED_FIX | Faltan series FX primarias BCRA con provenance + reconstrucciones con settlement antes de cualquier veredicto. |
| F-FX-003 | BLOCKER | Prohibido clasificar A3500/OFICIAL/MEP/CCL hasta D≥8 con decision-v1.0.0; todo intento hoy es NO DETERMINABLE. |
| F-FX-004 | IMPROVEMENT | Extender a multi-emisora + quarterly TIKR con raw_hash antes de re-certificar. |

## 4. Próximo gate (IMPLEMENTAR → VERIFICAR)

1. Verificar endpoint BCRA vivo y poblar `01_raw/bcra_*` con provenance completa.
2. Normalizar secundarias (dolarito/dolarapi/Rava) como cruce, sin sustituir primaria.
3. Conseguir benchmarks TIKR quarterly ARS↔USD (mínimo 8 POC con ambas monedas) y
   curarlos a `01_raw/tikr/`.
4. Implementar reconstrucción ADR/bonos con settlement declarado.
5. Ejecutar `tikr_fx_compare.py` real; si D<8 o TIE/NO_DECISION dominan, el resultado
   correcto sigue siendo UNKNOWN/HYBRID (no recalibrar umbrales).

## 5. Provenance de este documento

- Fuentes: `data/TIKR_METR_BENCHMARK_ARS_USD.xlsx` (md5 citado en homologación),
  `scripts/dolares/_dolar.py`, `docs/01-arquitectura.md`, `docs/…IDENTITY…`.
- Código: `build_target_matrix@v1.0.0`, `stats@v1.0.0`, tests 13/13.
- Artefactos: `outputs/target_dates.csv` SHA256
  `534569645d8647c901284f5863642187d93cdfae8cfde9042da3f06375f6f2d6`.
- Criterios: `decision-v1.0.0` congelado 2026-09-15 (no modificar post-resultados).
