# 01 — Arquitectura general

> Fuente original: `Jobs_y_Base_de_Datos.docx` (Mayo 2026)

## Principio fundamental

> **Los datos crudos se guardan siempre. Los cálculos se pueden rehacer sin internet.**

La arquitectura está dividida en **tres capas completamente independientes**:

- Los jobs de descarga **nunca calculan**.
- El job de cálculo **nunca descarga**.
- El frontend **nunca hace ninguna de las dos cosas** — solo lee de PostgreSQL.

Si mañana cambia la fórmula de FCFonCE, o se agrega un ratio nuevo, no es
necesario volver a descargar nada de SEC EDGAR ni de Yahoo Finance. Solo se
corre el Job 2 de nuevo y recalcula todo desde los datos que ya están en la
base de datos.

Los datos crudos de SEC EDGAR son el activo más valioso del proyecto. Una vez
guardados, son permanentes y se pueden consultar en cualquier momento para
cualquier cálculo futuro.

## Las 3 capas

| Capa | Tabla | Quién escribe | Quién lee |
|---|---|---|---|
| 1A — Precios | `precios_raw` | Job 1A (Backend A) | Job 2 |
| 1B — Financials | `financials_raw` | Job 1B (Backend B) | Job 2 |
| 2 — Ratios | `ratios` | Job 2 | FastAPI → Frontend |
| Auditoría | `jobs` + `job_errores` | Todos los jobs | FastAPI → Frontend B |

## Diagrama de flujo

```
                    ┌─────────────┐
                    │   cedears   │  (maestro de tickers)
                    └──────┬──────┘
              ┌────────────┴────────────┐
              ▼                         ▼
      ┌───────────────┐         ┌───────────────────┐
      │   Job 1A       │         │   Job 1B           │
      │ Yahoo Finance  │         │ SEC EDGAR XBRL      │
      └───────┬────────┘         └─────────┬───────────┘
              ▼                            ▼
      ┌───────────────┐         ┌───────────────────┐
      │  precios_raw   │         │  financials_raw     │
      └───────┬────────┘         └─────────┬───────────┘
              └────────────┬───────────────┘
                           ▼
                   ┌───────────────┐
                   │    Job 2       │  (lee ambas, calcula, no descarga nada)
                   └───────┬────────┘
                           ▼
                   ┌───────────────┐
                   │    ratios      │  (única tabla que lee el frontend)
                   └───────┬────────┘
                           ▼
                   ┌───────────────┐
                   │  FastAPI       │  → GET /api/cedears/screener
                   └───────┬────────┘
                           ▼
                   ┌───────────────┐
                   │  Frontend      │  (SWR + React Query, solo lectura)
                   └───────────────┘
```

## Por qué esta arquitectura y no otra

Antes de decidir esto se evaluaron dos opciones:

1. **Guardar solo el resultado calculado** — más simple, pero si cambia una
   fórmula hay que volver a descargar todo desde las fuentes externas.
2. **Guardar todo crudo + capa de cálculo separada** *(elegida)* — el job de
   descarga tarda un poco más en diseñarse, pero el sistema se vuelve
   resiliente a cambios de fórmula y permite auditoría histórica completa.

Para 100 tickers con actualización semanal, la sobrecarga de guardar los datos
crudos es insignificante comparada con el beneficio de nunca depender de
volver a golpear las APIs externas (Yahoo Finance, SEC EDGAR) cada vez que se
ajusta un cálculo.

## Stack base

```
Python 3.11 · FastAPI · PostgreSQL 16 · APScheduler · Playwright · yfinance · requests
Next.js 14 · TypeScript · Tailwind CSS · shadcn/ui · SWR · React Query
```

Ver [`06-decisiones-tecnicas.md`](06-decisiones-tecnicas.md) para el detalle
de cada decisión (TIKR vs SEC EDGAR, modo headed vs headless, etc).
