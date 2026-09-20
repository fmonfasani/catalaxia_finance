# FASE B — enlace instrumento ↔ entidad del universo de demostración

**Fecha:** 2026-08-31 · Regla aplicada: sin ticker como identidad, sin nombre,
sin legacy, sin joins heurísticos. Lo que no es demostrable queda
`REVIEW_REQUIRED`.

---

## 1. Resultado

| ticker | instrumentos | enlace en `identity_v1.instrument` | entidad | estado |
|---|---|---|---|---|
| YPFD | 83 (BUE/ARS), 84 (NYSE/USD, ADR 1:1) | sí | YPF SOCIEDAD ANONIMA | **OK** |
| CEPU | 80 (BUE/ARS), 81 (NYSE/USD, ADR 10:1) | sí | CENTRAL PUERTO S.A. | **OK** |
| TGSU2 | 65 (BUE/ARS), 66 (NYSE/USD, ADR 5:1) | sí | TRANSPORTADORA DE GAS DEL SUR S.A. | **OK** |
| GGAL | 71 (BUE/ARS), 72 (NYSE/USD, ADR 10:1) | sí | GRUPO FINANCIERO GALICIA S.A. | **OK** |
| AAPL | 86 | sí | Apple Inc. | **OK** |
| MSFT | 402 | sí | MICROSOFT CORP | **OK** |
| NVDA | 422 | sí | NVIDIA CORP | **OK** |
| **BMA** | **584 (BUE/ARS)** | **no** | Macro Bank Inc. | **REVIEW_REQUIRED** |

**7 de 8 con enlace. BMA no, y no se fuerza.**

## 2. El caso BMA, en detalle

### Lo que sí está demostrado

El CIK de la entidad tiene una assertion **VERIFIED**, con fuente primaria:

```
id_type CIK · id_value 0001347426 · status VERIFIED · method REGISTRY
resolved_by proc:f024_bma
evidence    SEC company_tickers company_tickers_2026-08-23.json:
            cik_str=1347426 ticker=BMA
```

Es decir: **SEC declara que el ticker `BMA` corresponde al CIK 1347426**.

### Lo que NO está demostrado

`company_tickers.json` mapea el ticker **de la especie listada en EE.UU.** — el
ADR en NYSE. El instrumento 584 de Market es otra cosa:

```
instrument_id 584 · ticker_canonico BMA · venue_ticker BMA
exchange BUE · country AR · currency ARS · security_type ordinaria
source dim_instrument · entity_id 572
```

Es la **acción ordinaria que cotiza en BYMA, en pesos**. Que el ADR de Banco
Macro en NYSE se llame `BMA` no demuestra que esta especie de BYMA pertenezca a
esa entidad: es el mismo símbolo en dos mercados distintos.

**Ésa es exactamente la trampa que el sistema ya conoce**: los "precios basura"
de un ciclo anterior eran colisiones de ticker entre BYMA y EE.UU. Aceptar el
enlace por coincidencia de símbolo sería repetirla.

### Lo que se buscó y no existe

| vía | resultado |
|---|---|
| `identity_v1.instrument` para MKT:584 | **no hay fila** |
| `identity_v1.instrument_symbol` | 23 filas, ninguna de MKT:584 |
| `market_instruments.entity_id = 572` | **no existe la tabla** a la que apuntaría |
| `market_symbol_mappings` | `BMA.BA` → BUE/ARS, fuente `dim_instrument` — es el mapeo del **proveedor de precios**, no una afirmación de identidad |
| CUIT de Banco Macro en `identity_v1` | **no tiene** |
| Un ADR de BMA en Market | **no existe** — Market sólo tiene la especie BUE |

Ninguna de esas vías es una fuente que afirme «esta especie es de esta entidad».

## 3. Consecuencia adoptada

BMA **no queda fuera del producto**: queda partido según lo que está demostrado.

| qué | estado | por qué |
|---|---|---|
| Fundamentals (los 14 ratios contables) | **calculados** | dependen sólo del CIK, y el CIK está `VERIFIED` contra fuente SEC |
| P/E, market cap, price/book | **NULL** | dependen de atribuirle **este precio** a **esta entidad**, que es justo lo no demostrado |

El motivo queda escrito en cada celda:

> los instrumentos ['584'] no tienen fila en `identity_v1.instrument`. El CIK
> está demostrado (SEC), pero nada demuestra que ESTA especie cotizante sea de
> esa entidad: sin eso, atribuirle el precio sería un join por ticker. Los
> ratios de mercado quedan NULL.

## 4. Qué haría falta para cerrarlo

Cualquiera de estas tres, en orden de solidez:

1. **Una fuente de BYMA/CNV** que ligue la especie `BMA` (ordinaria, ARS) al
   CUIT de Banco Macro, más un bridge CUIT↔CIK ratificado. Es el camino que
   YPF, CEPU y TGS ya tienen.
2. **El 20-F de Banco Macro**, que declara en carátula las especies listadas y
   su relación con las ordinarias (ratio del ADR). Está al alcance: el emisor ya
   fue ingerido (CIK 0001347426, 8.737 facts).
3. **Una ratificación humana** con la evidencia citada, como las tres de F-041.

Ninguna se hizo en este ciclo: las tres exigen una fuente que no está ingerida o
una decisión humana, y el encargo pide no forzar la resolución.

## 5. Nota sobre los otros siete

Los 15 enlaces existentes de `identity_v1.instrument` provienen de
`proc:migracion_009` y `proc:identity_backfill`, todos con assertion
`LEGACY_IMPORT` en estado **`CANDIDATE`** — ninguno `VERIFIED`.

Es decir: **el enlace instrumento↔entidad de todo el universo es de grado
candidato**, no ratificado. Para los siete alcanza para operar el screener
—están declarados, versionados y con autor— pero conviene decirlo en vez de
presentarlos como demostrados. BMA no es peor que los otros por estar en
`REVIEW_REQUIRED`: es que ni siquiera tiene el candidato.
