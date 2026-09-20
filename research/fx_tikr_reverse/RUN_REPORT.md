# RUN_REPORT.md — corrida AGENTE 02 (2026-09-15, rama `feature/fx-research-engine`)

Ejecutor: AGENTE 02 · git `f375090` · `pyarrow 25.0.1` · `pandas 3.0.1`.
Alcance: P1–P8 + 11 ejes de test. **Sin conclusión sobre el FX de TIKR**
(este reporte entrega datos de referencia; el veredicto es de otro agente).

## 1. Comandos y resultado

| Paso | Comando | Resultado |
|---|---|---|
| P1-A3500 | `engine/bcra_a3500.py --targets 00_DEFINIR/target_dates.csv --window 5` | 156 días consultados, 156 ok (`CREATED`), 107 con USD>0 (resto: fines de semana/feriados sin publicación) |
| P1-OFICIAL | `engine/bcra_oficial.py` | 3951 filas, rango 2010-06-01→2026-09-14 |
| P2-BYMA | `engine/byma_status.py` | MEP/CCL/Dollar_Index/CCL_Index = AUTH_REQUIRED |
| P8-fixture | `engine/tikr_fixture.py` | 12 filas |
| P5-universo | `engine/universe.py` | 26 períodos, A3500 OK 26/26, OFICIAL OK 26/26 |
| P6-normalize | `engine/normalize.py` | 52 filas, 52 con valor |
| Tests | `pytest engine_tests/ tests/` | **31 passed (18+13)** |

## 2. Hashes (verificación del auditor)

| Artefacto | SHA256 |
|---|---|
| `normalized/fx_reference.parquet` | `52ED5B5C2BA73CDCF2F460ABE9C0355458C2CAC0E051D73CE1725FF1D1AAC39C` |
| `parsed/universe.csv` | `7180591A54D78A82ECC534EE29877D3496FF2523BEB1A023A5E9A682E69973B0` |
| `parsed/bcra_oficial.csv` | `2B07F17D4EB3816F6213248276AF9626B7600A9D15AE31A758C00E24491A5D3D` |
| `fixtures/tikr_fx_12.csv` | `AE02BADA72DBE628CBDBB4C04EED323666514C21D2C56DB76BA3E7155080BB51` |

RAW: `raw/bcra/a3500/` 156 JSON (cada uno con `meta.sha256` recalculable);
`raw/bcra/oficial/snapshot_2026-09-15.html` (sha `b2e8b8ae…`, 3951 filas).

## 3. Referencias por quarter (entrega, no veredicto)

| period | target | eff_A3500(lag) | A3500 | eff_OFICIAL(lag) | OFICIAL | tikr_fx (fixture) |
|---|---|---|---|---|---|---|
| 2023-Q3 | 2023-09-30 | 2023-09-29 (1) | 349.95 | 2023-09-29 (1) | 365.60 | 349.97 |
| 2023-Q4 | 2023-12-31 | 2023-12-29 (2) | 808.45 | 2023-12-29 (2) | 847.11 | 808.46 |
| 2024-Q1 | 2024-03-31 | 2024-03-27 (4) | 858.00 | 2024-03-27 (4) | 901.63 | 857.22 |
| 2024-Q2 | 2024-06-30 | 2024-06-28 (2) | 912.00 | 2024-06-28 (2) | 950.42 | 911.50 |
| 2024-Q3 | 2024-09-30 | 2024-09-30 (0) | 970.50 | 2024-09-30 (0) | 1004.94 | 968.50 |
| 2024-Q4 | 2024-12-31 | 2024-12-31 (0) | 1032.00 | 2024-12-30 (1) | 1060.28 | 1030.50 |
| 2025-Q1 | 2025-03-31 | 2025-03-31 (0) | 1074.00 | 2025-03-31 (0) | 1103.73 | 1073.10 |
| 2025-Q2 | 2025-06-30 | 2025-06-30 (0) | 1205.00 | 2025-06-30 (0) | 1217.87 | 1204.50 |
| 2025-Q3 | 2025-09-30 | 2025-09-30 (0) | 1380.00 | 2025-09-30 (0) | 1406.79 | 1379.70 |
| 2025-Q4 | 2025-12-31 | 2025-12-31 (0) | 1455.00 | 2025-12-30 (1) | 1479.28 | 1451.00 |
| 2026-Q1 | 2026-03-31 | 2026-03-31 (0) | 1382.00 | 2026-03-31 (0) | 1409.48 | 1382.00 |
| 2026-Q2 | 2026-06-30 | 2026-06-30 (0) | 1482.00 | 2026-06-30 (0) | 1502.09 | 1483.70 |

Serie completa 2020-Q1→2026-Q2 en `normalized/fx_reference.parquet` (52 filas).
La columna `tikr_fx` se reproduce aquí sólo como cotejo visual del fixture; la
comparación formal y el veredicto NO pertenecen a este agente.

## 4. Pendientes declarados (no silenciados)

| ID | Severidad | Texto |
|---|---|---|
| E-P2 | REQUIRED_FIX | BYMA MEP/CCL/índices: proveer `BYMA_CLIENT_ID/SECRET` en `.env` y re-ejecutar `byma_status.py` → collector EOD real. |
| E-P3 | REQUIRED_FIX | ISIN de AL30/GD30/ADR: contrastar contra catálogo BYMA/CNV antes de publicar quotes (hoy `NOT_VERIFIED`). |
| E-P4 | OBSERVATION | `reconstruct.py` implementado y testeado (6/6 controles) pero sin quotes históricos → 0 filas MEP/CCL reconstruidas en `fx_reference` (correcto: no inventar). |
| E-P7 | OBSERVATION | `stats_ext` añade P10/P25/P75/P90 sin alterar `scripts/stats.py` congelado (criterios REQ-FX-007/009 intactos). |

## 5. Verificación de no-regresión

- `00_DEFINIR/*` y `scripts/stats.py` sin modificar (criterios congelados intactos).
- Producción intacta: ningún write fuera de `research/fx_tikr_reverse/`
  (guardia `assert_in_sandbox` + test dedicado).
- Rama: todo el trabajo en `feature/fx-research-engine`.
