# docs/screener/ — Documentación del Screener

Documentación del **screener financiero** (base de datos de ratios desde SEC
EDGAR + yfinance). El sistema que corre vive en `scripts/tickets/` y puebla
`data/screener.db`.

> **Estado (jun 2026):** funcional. 8.021 empresas catalogadas, **553 con ratios
> completos** (S&P 500 + ADRs ARG/BRA/LatAm), GAAP+IFRS unificados, con flags de
> calidad.

---

## Por dónde empezar

| Orden | Documento | Para qué |
|-------|-----------|----------|
| 1 | **COMIENZA_AQUI.md** ⭐ | puerta de entrada — el mapa de todo |
| 2 | **../../scripts/tickets/README.md** | guía operativa: scripts, base de datos, cómo correrlo |
| 3 | **GUIA_SEC_EDGAR_PARA_DEVS.md** | de cero: acciones, balances, SEC EDGAR, XBRL, ratios (§13 = el sistema) |
| 4 | **ESPEC_TAGS_RATIOS.md** | los ~40 tags core + ~45 ratios; §7 = mapeo GAAP↔IFRS implementado |
| 5 | **DIAGNOSTICO_INVESTING_vs_EDGAR.md** | la validación: por qué EDGAR≈Investing + los 10 fixes |

## Otros documentos

- **FUENTES_DATOS_ACCIONES_ARGENTINA_BYMA.md** — de dónde sale cada dato de las
  acciones argentinas (con la corrección: la mayoría de los ADRs ARG están en
  EDGAR como IFRS).
- **GUIA_COLABORADORES.md** — guía para contribuir al proyecto.
- **PLAN_SCREENER_218_ACCIONES.md** — plan original (referencia histórica).
- **INSTRUCCIONES_DESCARGA_MANUAL.md** — descarga manual de BYMADATA (alternativa).
- **GUIA_SEC_EDGAR_PARA_DEVS.pdf** — versión PDF de la guía.
- **failed_investing_scraping/** — intentos fallidos de scraping de Investing
  (referencia de por qué se usa EDGAR).

## Documentación de cálculos

Las fórmulas detalladas y el código de referencia de la investigación están en
**`../calculos-financieros/`**.

---

## El sistema en una imagen

```
SEC EDGAR + yfinance ──► data/screener.db
                          ├─ empresas (8.021)   catálogo: sector, país, tamaño
                          ├─ facts (4,6M)       series GAAP+IFRS, 6 años
                          ├─ ratios (553)       ~35 ratios + valuación + flags
                          └─ precios (553)      market cap + FX
```

Validado contra Investing.com: PER mediana 1,3%, ROE 0,4%, márgenes ~0%.
