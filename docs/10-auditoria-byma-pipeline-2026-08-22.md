# Auditoría pipeline BYMA-only v3 — 2026-08-22

> Generado por `scripts/byma/b8_reporte.py`. Numeros vivos desde `data/byma_pipeline.db`. Nada hardcodeado.

## Cadena de custodia

| Etapa | Script | Producto | Verificacion |
|---|---|---|---|
| E1 | snapshot_byma.py | snapshot inmutable en backups/ | SHA256 fuente=copia; logical-check OK (header cambia por design de SQLite) |
| E2 | b0_universo.py | byma_universo | 73 entidades clasificadas |
| E2 | b1_partidas.py | partidas_norm | 85,370 filas normalizadas |
| E3 | b2_escala.py | anomalias | 234 detectadas (NO corrige nada) |
| E3 | b3_ttm.py | ratios+balances TTM | TTM directo en 68 empresas |
| E4 | b4_mercado.py | mercado_byma | difs 52w verificadas: 56/56 OK |
| E5 | b5_metricas.py | metricas (formula+inputs) | 13 metricas con provenance |
| E5 | b6_validacion_mat.py | validacion_mat | OK=221 WARN=8 INFO=19 FAIL=10 |
| E6 | b7_certificacion.py | certificacion | 487 CERTIFIED / 72 NOT_CERTIFIED |

## Universo y mercado

- Entidades universo: **73** — con dato de mercado: **56** (todos byma_only via ARS x MEP pareado mismo vintage)
- Staleness declarado: VIEJO x56
- Gap conocido: 17 entidades sin match de mercado (tickers formato BYMA GGALB vs empresas.ticker_ppal GGAL). Pendiente E7+: mapa ADR.

## Anomalias detectadas (no corregidas)

| check | severidad | n |
|---|---|---|
| ESCALA_JUMP | ALTA | 178 |
| ROE_EXTREMO | MEDIA | 22 |
| EBITDA_MARGEN | MEDIA | 14 |
| MARGEN_NETO | ALTA | 9 |
| IDENTIDAD | ALTA | 5 |
| ROA_EXTREMO | MEDIA | 4 |
| ROE_EXTREMO | ALTA | 2 |

Top empresas por anomalias ALTA: CVH (23), GCLA (18), GCDI (15), BHIP (11), HAVA (10).

## Hallazgos PER_2PATH (misma ventana, desvio >10%)

El EPS declarado no cuadra con NI_ttm/mcap en 10 empresas. Hipotesis a verificar: splits no reflejados en EPS_basico, basico vs diluido, NI atribuible. Caso extremo DGCE factor ~1000 (soscha escala).

## Certificacion final

- **487 metricas CERTIFIED** / 72 NOT_CERTIFIED (22 empresas afectadas)

| Empresa | Metricas bloqueadas (motivo en tabla certificacion) |
|---|---|
| A3 | per,deuda_ebitda,eps_anual,margen_neto,roe_5y,fcf_market_cap |
| AGRO | per,eps_anual |
| ALUA | per,eps_anual |
| BHIP | per,margen_neto,roe_5y,fcf_market_cap |
| BYMA | per,eps_anual |
| CADO | per,deuda_ebitda,margen_neto,roe_5y,fcf_market_cap |
| CECO2 | per,deuda_ebitda,margen_neto,roe_5y,fcf_market_cap |
| CGPA2 | per,deuda_ebitda,eps_anual,margen_neto,roe_5y,fcf_market_cap |
| CTIO | margen_neto |
| CVH | deuda_ebitda,roe_5y,fcf_market_cap |
| DGCE | per,eps_anual |
| ECOG | per,eps_anual |
| EDSH | margen_neto |
| FIPL | margen_neto,roe_5y,fcf_market_cap |
| GARO | deuda_ebitda,margen_neto,roe_5y,fcf_market_cap |
| GCDI | margen_neto,roe_5y,fcf_market_cap |
| GCLA | per,deuda_ebitda,margen_neto,roe_5y,fcf_market_cap |
| HAVA | per,deuda_ebitda,margen_neto,roe_5y,fcf_market_cap |
| LONG | per,deuda_ebitda,margen_neto,roe_5y,fcf_market_cap |
| MIRG | per,eps_anual |
| MOLA | per,eps_anual |
| SEMI | per,eps_anual |

## Decisiones de definicion documentadas

- PER = mcap_ars / NI_ttm_ars (mismo vintage MEP; moneda se cancela). VERIFICADO que screener."MarketCapUSD" esta en ARS.
- EPS anual = ultimo cierre fiscal completo (no TTM: falta shares outstanding).
- ROE 5Y = promedio de ROE anuales ultimos <=5 cierres (>=3 requeridos).
- CAGR EPS nominal sin deflactar (flag NOMINAL_sin_deflactar; IPC pendiente).
- FCF = CFO_ttm + CFI_ttm; flag si CFI>0.
- Payout heredado del v2 con payout_source como provenance.

## Pendientes para certificar al 100%

1. Resolver los 10 casos PER_2PATH (inspeccion manual de splits/dilucion).
2. Mapa de tickers ADR para las 17 empresas sin mercado.
3. Refresh de precios/MEP (staleness 44-54 dias).
4. Deflactar CAGR EPS por IPC.
5. Resolucion de anomalías IDENTIDAD (3 empresas) y ESCALA masiva (CVH/GCLA/GCDI).