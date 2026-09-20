# Certification report — sovereign debt + FX matrix (AGENTE 10/11)
Rama `feature/fx-research-engine` · 2026-09-15 · `sovereign_matrix/11_CERTIFICATION/`

## Certification gate (§20)

```
CERTIFICATION = NOT_CERTIFIED
```

Motivos (todos reproducibles, ninguno subjetivo):

1. **Cross-market coverage = 0** (TABLA 4 + `cross_market_cases.csv`): REQ-008
   exige ambos mercados para certificar cross-market; no existe el caso.
2. **USD market prices = 0/104 quarters**: sin pata USD no hay FX de mercado
   certificable (REQ-005); los 2 cocientes existentes son posición/carrying.
3. **Market venue = 0**: V01–V04 sin plaza nombrada → SUPPORTED, nunca CERTIFIED (§17).
4. **Ventanas FTS con HTTP 500** (5): cobertura Discovery incompleta en esos
   queries (E-grade, reintentables).
5. **TIKR (§21)**: sin precios trimestrales de instrumentos no hay comparación
   posible → CONSISTENT/INCONSISTENT = UNKNOWN en todo; inferir método por
   coincidencia está prohibido y no se hizo.

## Requisitos REQ-001..012 (auditoría propia)

| REQ | Estado | Evidencia |
|---|---|---|
| 001 identidad verificable | PASS (26 instrumentos; ISIN sólo si consta) | 02_IDENTITY/instrument_master.csv + test_isin |
| 002 provenance por valor | PASS | provenance_matrix.csv (14) + .meta.json por filing |
| 003 tipo de precio | PASS | TIPO_DE_PRECIO en 9/9 filas master |
| 004 fecha por precio | PASS | FECHA ISO en 9/9 |
| 005 comparabilidad ARS/USD | PASS (incluye veredictos negativos) | fx_observations.csv (1 COMPARABLE-posición, 1 NO_COMPARABLE, 1 NO_DET) |
| 006 fórmula reproducible | PASS | TABLA3 + fx_observations (37157/36, 115725101466/145602795 verificados por test) |
| 007 dos inputs identificados | PASS | fuente_1/fuente_2 (+NO_EVIDENCE_FOUND donde falta) |
| 008 cross-market ambos mercados | NOT_APPLICABLE (0 casos; declarado) | cross_market_cases.csv CX00 |
| 009 sin artefactos internos | PASS | internal_artifacts.csv (5) + test dedicado |
| 010 puede concluir UNKNOWN | PASS | este veredicto + TIKR UNKNOWN |
| 011 criterios intactos | PASS | 00_DEFINIR/* y scripts/stats.py sin modificar (git diff vacío) |
| 012 reconstruible desde fuente | PASS | URL+fragmento+RAW por fila; suite 56 passed |

## Hallazgos clasificados

| ID | Sev | Texto |
|---|---|---|
| S-01 | OBSERVATION | CEPU aporta 4 precios ARS fechados con ISIN (mejor pata ARS del estudio). |
| S-02 | OBSERVATION | GGAL define contractualmente Implicit Exchange Rate GD30/AL30 (metodología, no print). |
| S-03 | OBSERVATION | Cross-checks SEC↔BCRA: +0.50/+0.0333/−0.0317 (≤0.05%, consistentes; vintage por aclarar). |
| S-04 | REQUIRED_FIX | Reintentar 5 ventanas FTS-500; revisar top-hits LETES/LEBAC/BONCER/isin_arg. |
| S-05 | REQUIRED_FIX | Prospectos 424B2 soberanos post-2020 para ISINs New Bonds (hoy NULL). |
| S-06 | OUT_OF_SCOPE | Pata USD secundaria para V01–V04 (fuera de EDGAR; si se usa, marcar B-grade). |
| S-07 | NO_DETERMINABLE | Plaza CEPU, tasa BNA numérica, GD46/AL25-EDGAR, método TIKR. |

Ningún BLOCKER metodológico: sin violaciones de invariantes con evidencia
reproducible; los gaps son celdas NO_EVIDENCE_FOUND/NO_DETERMINABLE válidas (§25).
