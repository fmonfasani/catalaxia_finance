# 🔄 Flujo General: De Datos Crudos a Dashboard

## Diagrama Simplificado

```
                    📥 ENTRADA
                       ↓
         cedears_con_cik.json
        (mapeo BYMA ↔ SEC ↔ CIK)
        (295 CIKs, 422 tickers BYMA)
            ↓
    ┌───────┴────────────────────┬─────────────────┐
    ↓                            ↓                 ↓
┌─────────────────┐      ┌──────────────┐  ┌────────────────┐
│  PASO 3         │      │   PASO 4     │  │                │
│  SEC EDGAR      │      │  yfinance    │  │                │
│  XBRL           │      │              │  │                │
│                 │      │              │  │                │
│ 295 empresas    │      │ 295 tickers  │  │                │
│ × 0.15s/req     │      │ × 0.2s/req   │  │                │
│ = 45 seg        │      │ = 60 seg     │  │                │
└────────┬────────┘      └──────┬───────┘  │                │
         │                      │          │                │
         ↓                      ↓          │                │
   financials_sec/          precios.json   │                │
   (1 JSON/empresa)                        │                │
   • 10-K, 10-Q histórico                  │                │
   • Todas las métricas GAAP               │                │
   • TTM listo para calcular               │                │
                                           │                │
         └───────────────────┬─────────────┘                │
                             ↓                             │
┌───────────────────────────────────────────────────────────┤
│                   PASO 5                                  │
│             Calcular Ratios                              │
│                                                           │
│  Input:  financials_sec/ + precios.json + cedears.json   │
│  Output: seguimiento.csv + seguimiento.json              │
│                                                           │
│  Cálculos:                                                │
│  • TTM para Revenue, NetIncome, CFO, CapEx, Dividendos  │
│  • PER = Precio / EPS_TTM                                │
│  • Margen Neto = NetIncome_TTM / Revenue_TTM             │
│  • ROE_5y = CAGR(NetIncome/Equity)                       │
│  • FCF = CFO − CapEx                                      │
│  • Deuda/EBITDA (2 variantes)                            │
│  • Payout = Dividendos / NetIncome_TTM                   │
└───────────────────────────────────────────────────────────┘
                             ↓
                    📤 SALIDA
                    seguimiento.csv
               (1 fila per BYMA ticker)
               (60 columnas)
```

## Las 5 Tablas PostgreSQL

Cuando los scripts corren en producción (con FastAPI/Jobs), los datos van a estas tablas:

| Tabla | Escrita por | Descripción |
|-------|-------------|-------------|
| `cedears` | Setup inicial | Maestro: ticker, CIK, nombre, exchange |
| `precios_raw` | Job 1A (Paso 4) | Crudos de yfinance: precio, 52w, shares |
| `financials_raw` | Job 1B (Paso 3) | Crudos de SEC: 1 fila per datapoint |
| `ratios` | Job 2 (Paso 5) | Calculados: PER, EPS, margen, ROE, etc. |
| `jobs` / `job_errores` | Todos | Auditoría: progreso, errores, timestamps |

## Independencia de los Jobs

**Clave:** Los 3 pasos pueden correr **completamente independientes**:

- **Job 1A (Paso 4)** — Descargar precios
  - Frecuencia: Diaria (22:00 UTC)
  - Depende de: Nada
  - Produce: precios_raw

- **Job 1B (Paso 3)** — Descargar financials
  - Frecuencia: Semanal (lunes 6:05 UTC)
  - Depende de: Nada
  - Produce: financials_raw

- **Job 2 (Paso 5)** — Calcular ratios
  - Frecuencia: Después de Job 1B (lunes 7:00 UTC) O manual en cualquier momento
  - Depende de: precios_raw + financials_raw (puede tener cualquier antigüedad)
  - Produce: ratios

**Caso de uso:** Si descubres que una fórmula de PER es incorrecta:
1. Editas el código de Job 2
2. Corre Job 2 (5 segundos)
3. Toda la tabla ratios se actualiza
4. **Cero requests a SEC o yfinance**

---

**Próximos pasos:** Lee los documentos individuales en `docs/SCRIPT_XX.md` para detalles de cada paso.
