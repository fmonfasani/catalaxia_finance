# SCREENER_CONTRACT_V1 — primer contrato del screener

**Fecha:** 2026-08-31 · **Estado: PROPUESTO** — no implementado en UI
**Precondición para publicar:** ver §8. Hoy **no se cumple**.

Este contrato define qué es una fila del screener, qué puede contener y qué está
prohibido que contenga. Está escrito contra lo que el sistema **demostró**
calcular, no contra lo que podría calcular.

---

## 1. Grano de la fila

**Una fila = una entidad × un ejercicio.** No un instrumento: CEPU, GGAL, TGSU2 y
YPFD tienen dos instrumentos cada uno (local y ADR) y **una sola** entidad.
Publicar por instrumento duplicaría cada empresa argentina.

Clave: `(entity_key, report_period)`. `entity_key` es la clave opaca de
`identity_v1` (ULID), nunca el ticker ni el CIK.

Por defecto el screener muestra **el ejercicio más reciente disponible por
entidad**, que no es necesariamente el mismo año para todas.

---

## 2. Columnas

### 2.1 · Identidad — siempre presentes, nunca NULL

| columna | origen |
|---|---|
| `entity_key` | `identity_v1.entity` |
| `nombre` | `identity_v1.entity.preferred_name` |
| `ticker` | `market_instruments.ticker_canonico` |
| `cik` | `identity_v1.identifier` (`id_type='CIK'`) |
| `cuit` | ídem, sólo si la assertion está `VERIFIED`; si no, NULL |

### 2.2 · Mercado

| columna | regla |
|---|---|
| `precio` | último cierre del instrumento elegido (§4) |
| `moneda_precio` | de `market_price_daily.currency`, nunca inferida |
| `fecha_precio` | `trading_date` de ese cierre |
| `mercado` | `exchange` |

### 2.3 · Fundamentales — las doce publicables

`current_ratio`, `quick_ratio`, `cash_ratio`, `debt_to_equity`,
`borrowings_to_equity`, `equity_ratio`, `roe`, `roa`, `net_margin`,
`gross_margin`, `operating_margin`, `interest_coverage`.

`effective_tax_rate` y `ocf_to_net_income` quedan **fuera** (REVIEW_REQUIRED, §6).

### 2.4 · Mercado × fundamentales

`pe`, `market_cap`.

### 2.5 · Contexto del ejercicio — obligatorias

| columna | por qué es obligatoria |
|---|---|
| `report_period` | sin ejercicio, un ratio no significa nada |
| `moneda_reporte` | YPF cambia ARS→USD en 2022: comparar entre monedas es un error |
| `accession` | el filing del que salió cada valor |
| `filing_date` | cuándo se publicó |

---

## 3. NULL — la regla central

> **Una celda vacía es un resultado válido. Un valor inventado, no.**

- `NULL` es el **único** relleno permitido. Prohibido: 0, guion, "N/D", el valor
  del ejercicio anterior, el promedio del sector, un valor estimado.
- Cada `NULL` lleva un `motivo` legible, accesible por celda.
- Motivos observados hoy: `falta numerador: ninguno de [...] en <periodo>`,
  `monedas distintas: X vs Y`, `denominador T = 0`, `EPS = -2.11 <= 0`,
  `EPS en USD y no hay precio en esa moneda`.
- **El orden por una columna manda los `NULL` al final**, en las dos direcciones.
  Un `NULL` no es ni el mayor ni el menor.
- **Un filtro numérico excluye los `NULL`.** `roe > 0.1` no devuelve filas sin ROE.
  El contador de resultados debe decir cuántas filas quedaron fuera por falta de
  dato, separado de las que quedaron fuera por no cumplir el filtro.

---

## 4. Cuál precio se usa

Regla, en orden:

1. Si el ratio combina precio con un fact contable, **se usa el instrumento cuya
   moneda coincide con la del fact**. Sin coincidencia → `NULL` con motivo. No se
   convierte con un FX no declarado.
2. Al dividir por un EPS por acción subyacente, el precio del ADR se divide por
   `ratio_underlying` de `identity_v1.instrument`. Si falta → `NULL`.
3. Columnas de sólo precio: se muestran **por instrumento**, con su mercado y
   moneda a la vista.

---

## 5. Períodos

- Un ratio combina facts **de un solo filing**. Prohibido cruzar numerador de un
  ejercicio con denominador de otro. (Auditado: control D2, 0 cruces.)
- Cada 20-F trae tres años comparativos. Se toma **el año principal**
  (`report_period == instant_date/end_date`); los comparativos se descartan.
- El `pe` combina un precio de **hoy** con un ejercicio **cerrado**. La fila debe
  mostrar las dos fechas. Un P/E histórico exige el precio de la fecha del
  ejercicio y **no está implementado**.

---

## 6. REVIEW_REQUIRED

Un ratio entra en `REVIEW_REQUIRED` cuando el cálculo es correcto y el resultado
no es publicable. Se **muestra el valor** con marca visible, y **no participa de
filtros ni de orden**.

Casos definidos:

| condición | ejemplo medido |
|---|---|
| denominador cambia de signo entre ejercicios | `ocf_to_net_income` = −6.0036 (YPF 2025) |
| resultado fuera de banda de sanidad | `effective_tax_rate` = 1.8780 (188 %) |
| dos caminos independientes difieren > 5 % | ninguno hoy |

Bandas de sanidad: **pendientes de definir**. Hasta entonces los dos ratios
quedan fuera del screener.

---

## 7. Provenance accesible por celda

Cada celda con valor debe poder responder, sin salir de la pantalla:

```
valor      0.8702
fórmula    CurrentAssets / CurrentLiabilities
insumos    CurrentAssets = 4.556e9 USD · CurrentLiabilities = 5.236e9 USD
período    2025-12-31
fuente     SEC EDGAR 20-F · accession 0001193125-26-126363 · filed 2026-03-26
moneda     USD
```

Para celdas con precio se agrega instrumento, mercado, `trading_date` y
`ratio_underlying`. Para `NULL`, el motivo en lugar del valor.

---

## 8. Precondiciones para publicar — **hoy no se cumplen**

| # | condición | estado |
|---|---|---|
| 1 | ≥ 20 entidades con cadena completa | **NO** — hay **7** (actualizado 2026-09-01, ver `RATIO_COVERAGE_MATRIX.md`; era 1 el 2026-08-31) |
| 2 | enlace instrumento→entidad ≥ 90 % | **NO** — **15/584 = 2.6 %** |
| 3 | auditoría independiente en verde | **SÍ** — 17/17 |
| 4 | 100 % de celdas con provenance | **SÍ** — 126/126 |
| 5 | 0 valores inventados | **SÍ** — control B1 |
| 6 | bandas de sanidad definidas | **NO** |

**Las condiciones 1 y 2 son las que faltan, y las dos son de ingesta.** El
contrato de cálculo está cumplido; el de cobertura no.

---

## 9. Fuera de alcance de V1

Sin UI compleja, sin ranking compuesto ni score propietario, sin comparables de
sector (una entidad no hace sector), sin proyecciones, sin datos intradiarios,
sin ratios que exijan D&A, capex o dividendos (§1.4 de la matriz).
