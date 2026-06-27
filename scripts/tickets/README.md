# scripts/tickets — pipelines de datos financieros

Organizado en **dos grandes grupos** por fuente de datos. Cada uno separa
**scripts / datos (json,csv) / db**.

```
scripts/tickets/
├── sec_edgar/          ← datos oficiales US + ADRs (SEC EDGAR, XBRL)
│   ├── scripts/        pipeline 01-07 + construir_/calcular_/precios_/flags_
│   ├── datos/          json/csv (company_tickers, financials_sec, ratios_tickets, …)
│   └── db/             (la base real está en /data/screener.db)
│
├── cnv/                ← estados argentinos BYMA-only (CNV / IR / yfinance)
│   ├── scripts/        cnv_ir/ (proyecto principal) + cnv_auto + parsers + experimentales
│   ├── datos/          cnv_empresas.xlsx
│   └── db/             (la base real está en /data/screener.db; tabla cnv_estados)
│
└── README.md           (este índice)
```

## Los dos grupos

| Grupo | Qué | Empezar por |
|-------|-----|-------------|
| **sec_edgar/** | S&P 500 + ADRs desde EDGAR: catálogo, facts GAAP+IFRS, ratios, valuación, flags | `sec_edgar/README.md` |
| **cnv/** | Argentinas BYMA-only: estados oficiales (CNV aif2 / IR / 6-K) + yfinance | `cnv/README.md` → `cnv/scripts/cnv_ir/README.md` |

## La base de datos

Una sola base compartida: **`/data/screener.db`** (raíz del repo, gitignoreada, ~700 MB).
Los scripts la encuentran solos (buscan la carpeta `data/` hacia arriba — son
independientes de dónde estén ubicados). Tablas: `empresas`, `facts`, `ratios`,
`precios`, `cnv_estados`.

## Documentación

`../../docs/screener/` — guías, diagnóstico EDGAR vs Investing, especificación de
tags/ratios, bitácora y decisiones, pipeline CNV.
