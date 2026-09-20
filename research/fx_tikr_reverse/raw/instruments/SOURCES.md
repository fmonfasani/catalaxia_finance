# Fuentes históricas de instrumentos — PRIORIDAD 3 (investigación registrada)
# Fecha: 2026-09-15 · AGENTE 02 · Clasificación: VERIFICADO POR FUENTE salvo nota.

## 1. Taxonomía de settlement (Argentina, verificada por fuente)

| Sufijo / plaza | Significado | Fuente |
|---|---|---|
| (sin sufijo), `48hs`, `T+2`→`T+1` | Liquidación normal BYMA (desde 2024: T+1; antes T+2/48hs) | BYMA newsroom "reduces settlement cycle" (VERIFICADO POR FUENTE) |
| `CI` | Contado inmediato (T+0) | BYMA; tablas con AL30 vs AL30C(CI) vs AL30D(24/48hs) (VERIFICADO POR FUENTE) |
| `D` (AL30D, GD30D) | Especie en dólares, liquidación local → pata USD del **MEP** | valordolarblue AL30 + Cohen especie (VERIFICADO POR FUENTE) |
| `C` (AL30C, GD30C) | Especie en dólares cable → pata USD del **CCL** | argen_bonds AL30C "Dolar Cable" + valordolarblue (VERIFICADO POR FUENTE) |
| NYSE T+1 | Acción/ADR en EEUU (GGAL, YPF, PAM) | estándar mercado (NO DETERMINABLE fino aquí; se declara UNDECLARED si el vendor no lo dice) |

Fórmulas (instrumental_spec.md, congelado):
- FX_MEP = ARS_PRICE(AL30) / USD_LOCAL_PRICE(AL30D), mismo settlement.
- FX_CCL = ARS_PRICE(AL30) / USD_CABLE_PRICE(AL30C) o ADR: P_ARS×ratio/P_USD.

## 2. Universo instrumental mínimo

| instrument | tickers (ARS / USD-local / USD-cable) | market | ISIN | estado |
|---|---|---|---|---|
| BONAR 2030 | AL30 / AL30D / AL30C | BYMA | NOT_VERIFIED (no inventado) | registry listo, precios pendientes |
| GLOBAL 2030 | GD30 / GD30D / GD30C | BYMA+exterior | NOT_VERIFIED | idem |
| GGAL ADR | GGAL.BA / GGAL ×10 | BYMA/NASDAQ | NOT_VERIFIED | idem |
| YPF ADR | YPFD.BA / YPF ×1 | BYMA/NYSE | NOT_VERIFIED | idem |
| PAMP ADR | PAMP.BA / PAM ×25 | BYMA/NYSE | NOT_VERIFIED | idem |

ISIN: se deja `null + NOT_VERIFIED` en todos (P3 exige ISIN *si existe*; inventar
un ISIN violaría "no inventar datos"). Verificación contra catálogo BYMA/CNV
queda como REQUIRED_FIX.

## 3. Fuentes históricas evaluadas

| Fuente | Cobertura | Auth | Settlement declarado | Veredicto uso |
|---|---|---|---|---|
| BYMA DataLens EOD (fixed_income/equity/indices) | histórico oficial | SÍ (client_id/secret ausentes) | SÍ (por especie+plazo) | AUTH_REQUIRED (byma_status.py) |
| BYMA OMS streaming | tiempo real | SÍ (keys ausentes) | SÍ | AUTH_REQUIRED |
| yfinance (.BA + ADR) | ~diaria, gratis | NO | NO (close sin plazo) | viable con settlement=UNDECLARED → NO_DECIDE en primario (instrumental §4) |
| Rava (CSVs en data/dolar/rava) | MEP/CCL/A3500 vendor | NO | NO | secundaria, cruce, NO primaria |
| dolarito/dolarapi/criptoya | spot actual | NO | parcial | secundaria, sin historia quarterly propia |
| BCRA APIs | A3500 + minorista | NO | N/A (referencia) | PRIMARIA (este engine) |

## 4. Schema `instrument_quote` (una fila por pata — P3)

```
instrument | ticker | isin | date | market | settlement | currency | price |
volume | source | source_url | retrieved_at | sha256
```

Implementado en `engine/instruments.py` (registry + validador). La ingesta de
precios históricos queda instrumentada pero con status PENDING_AUTH/PENDING_SOURCE:
ninguna fila de precio se inventa para rellenar.
