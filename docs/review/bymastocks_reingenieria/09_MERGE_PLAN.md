# 09 — MERGE PLAN (candidatos, SIN ejecutar) — BYMAStocks

> Fase 1: solo candidatos priorizados con evidencia. Ningún MERGE se ejecuta. Aplica la misma regla de 10 pasos.

## 1. Prioridad alta (duplicación de dominio → produce divergencia de datos)

| Ítem | Versión a conservar | Versión a absorber | Evidencia | Riesgo si no se fusiona |
|---|---|---|---|---|
| M1 Identidad | engine/identity_v1.py | scripts/pipeline/f1_identidad.py · tickets/sec_edgar/construir_{base,catalogo} | deep audit + 02/03 | dos entidades para la misma compañía |
| M2 Ratios | scripts/engine/ratio_engine (+ratio_inputs, ratio_defs) | scripts/pipeline/f4_ratios.py | deep audit | ratios distintos para el mismo período |
| M3 Pipeline | engine s00..s04 | scripts/pipeline/f1..f6 | deep audit + 01 | dos "verdades" de ETL |
| M4 Sec fetch | engine s02/s03/xbrlparse | scripts/tickets/sec_edgar/scripts/02_descargar_datos.py | scan | doble extractor EDGAR |

`VERIFICADO POR CÓDIGO`.

## 2. Prioridad media

| Ítem | Candidatos | Motivo |
|---|---|---|
| M5 db.py | engine/db.py + screener/db.py | si se unifica el modelo de acceso, ambos en uno |
| M6 config.py | engine/config.py + cnv_ir/config.py | mismo rol, dos dominios |
| M7 discovery | engine/cnv/discovery.py + cnv_ir/discovery.py | dos descubridores CNV |
| M8 screener build | run_all fases s0..s8 + run_pipeline f5_screener | dos caminos a la tabla screener |

## 3. Prioridad baja (limpieza tras lleva a git)

| Ítem | Candidatos |
|---|---|
| M9 dolar | scripts/market/10b_actualizar_mep_hoy.py ← scripts/dolares/actualizar_dolares.py |
| M10 investing | carga_estados_investing_10empresas.py (incompleta) ← carga_investing_10_full.py |

## 4. Checklist MERGE (se completa en fase 9)

| Ítem | 1 dep | 2 ownership | 3 dup sem | 4 comportamiento | 5 consumidores | 6 impacto | 7 alternativa | 8 plan mig | 9 verif | 10 cert | DECISIÓN |
|---|---|---|---|---|---|---|---|---|---|---|---|
| M1 | PEND | PEND | PEND | PEND | PEND | PEND | PEND | PEND | PEND | PEND | NO |

## 5. Conclusión

MERGE es fase 9. 10 candidatos registrados; los de prioridad alta son los que hoy producen riesgo real de divergencia de datos. Los M5-M7 dependen de decisión de arquitectura (unificar acceso a datos, no solo nombre).