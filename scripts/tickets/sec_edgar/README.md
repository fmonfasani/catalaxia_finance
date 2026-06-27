# SEC EDGAR — pipeline de datos oficiales US + ADRs

Todo lo que viene de **SEC EDGAR** (companyfacts XBRL): S&P 500 + ADRs, ratios, valuación.

```
sec_edgar/
├── scripts/   pipeline (01-07 validación + construir_/calcular_/precios_/flags_)
├── datos/     json/csv: company_tickers, financials_sec/, precios_*, ratios_tickets, tickets_*
└── db/        (la base real está en /data/screener.db)
```

## Scripts (orden)
- **01-05**: pipeline de validación vs Investing (Tickets.xlsx)
- **06-07**: solapas de cálculo/estadísticas
- **construir_catalogo / construir_base**: catálogo 8.021 + facts (GAAP+IFRS)
- **calcular_ratios_base / precios_y_valuacion / flags_calidad**: ratios + PER + flags

Ver `../README.md` (índice) y `../../../docs/screener/` (documentación).
