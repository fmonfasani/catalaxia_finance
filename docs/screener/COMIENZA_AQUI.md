# 🚀 COMIENZA AQUÍ

Punto de entrada al **screener financiero**: una base de datos de ratios de
acciones que cotizan en EE.UU. (S&P 500 + ADRs), armada con datos oficiales de
**SEC EDGAR** + precios de **yfinance**.

> **Estado:** funcional. 8.021 empresas catalogadas, **553 con ratios completos**
> (S&P 500 + ADRs ARG/BRA/LatAm), unificando US-GAAP e IFRS. Junio 2026.

---

## ¿Qué es esto en una frase?

Bajamos los estados financieros oficiales de la SEC, calculamos ~35 ratios por
empresa con una metodología validada (error mediano ~1% vs Investing.com), y los
dejamos en una base de datos consultable con SQL, marcando dónde no confiar.

---

## El recorrido recomendado (de mayor a menor nivel)

1. **`../../scripts/tickets/README.md`** ⭐
   Cómo funciona el pipeline completo, los scripts, la base de datos y cómo
   correrlo. **Empezá acá si vas a tocar código.**

2. **`GUIA_SEC_EDGAR_PARA_DEVS.md`**
   De cero absoluto: qué es una acción, un balance, SEC EDGAR, XBRL, y cómo se
   arma cada ratio. **Para entender el dominio sin saber finanzas.**

3. **`ESPEC_TAGS_RATIOS.md`**
   Los ~40 tags core (XBRL us-gaap **+** ifrs-full) y los ~45 ratios que se
   pueden construir, con cobertura medida por sector.

4. **`DIAGNOSTICO_INVESTING_vs_EDGAR.md`**
   La validación: por qué EDGAR-GAAP reproduce Investing, los 10 bugs que
   encontramos y arreglamos (el del `fy`, el TTM rodante, etc.), con números.

5. **`../calculos-financieros/`**
   Fórmulas detalladas de cada ratio + código de referencia de la investigación.

---

## El sistema, de un vistazo

```
SEC EDGAR (companyfacts) ──┐
                           ├─► data/screener.db  (SQLite, Postgres-ready)
yfinance (precios) ────────┘     │
                                 ├─ empresas (8.021)   catálogo: sector, país, tamaño
                                 ├─ facts (4,6M)       series GAAP+IFRS, 6 años
                                 ├─ ratios (553)       ~35 ratios + valuación
                                 ├─ precios (553)      market cap + FX
                                 └─ + flags de calidad
```

5 capas: **catálogo → facts → ratios → precios → flags**. Cada una es un script en
`scripts/tickets/`.

---

## Decisiones técnicas clave

| Pregunta | Respuesta | Por qué |
|----------|-----------|---------|
| ¿Investing.com (scraping)? | ❌ NO | frágil, bloqueos, números raros (ver `failed_investing_scraping/`) |
| ¿SEC EDGAR? | ✅ SÍ | API oficial, gratis, datos validados (~99% en lo que importa) |
| ¿yfinance? | ✅ SÍ | precios diarios + 52w + market cap (en USD, también para ADRs) |
| ¿GAAP e IFRS juntos? | ✅ SÍ | mapeo canónico unifica `NetIncomeLoss`/`ProfitLoss`, etc. |
| ¿SQLite o Postgres? | SQLite ahora | cero setup; migrable a Postgres (`pgloader`) sin reescribir |
| ¿Estimar datos faltantes? | ❌ NUNCA | si falta un componente, el ratio es NULL |

---

## Probarlo en 1 minuto (si la base ya está construida)

```bash
sqlite3 data/screener.db "
  SELECT ticker, per, roe, deuda_ebitda
  FROM ratios WHERE grupo='sp500' AND flags IS NULL
  AND per BETWEEN 0 AND 15 AND roe>0.20 ORDER BY per LIMIT 10;"
```

Para **construir la base desde cero**, ver `scripts/tickets/README.md` §2.

---

## Estado y próximos pasos

- ✅ S&P 500 + ADRs ARG/BRA/LatAm con ratios + valuación + flags.
- ⏳ Cola larga US (~7.458) vía el `companyfacts.zip` masivo de SEC.
- ⏳ Fase 2: historia completa (hoy: últimos 6 años).
- ⏳ Capa de export/dashboard (replicar el `Seguimiento_original.xlsx`).

---

**Nota histórica:** la carpeta `failed_investing_scraping/` y los docs en
`calculos-financieros/` son referencia de la investigación previa. El sistema que
**funciona hoy** vive en `scripts/tickets/` + `data/screener.db`.
