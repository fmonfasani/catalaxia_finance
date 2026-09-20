# 05 · REFERENCIA DE RATIOS

Tres familias, y hay que separarlas porque sus insumos y sus modos de falla son
distintos.

> **Advertencia sobre lo que el pipeline realmente persiste.** En
> `derived.ratio` sólo existen **cuatro** `canonical_id`: `eps`, `pe`, `pb`,
> `ev_sales`. Los **14 ratios contables** definidos en
> `scripts/engine/ratio_defs.py` **no los persiste ninguna etapa del pipeline**:
> los consume únicamente `scripts/engine/matriz_producto.py`, que es un script
> de análisis. `SOFTWARE GAP SG-03`.

---

## 1 · Contabilidad — definidos en `ratio_defs.RATIOS`

Formato de la tabla: `(numerador, a restar, denominador, unidad, publicable)`.

| ratio | fórmula | insumos (conceptos canónicos) | unidad | publicable |
|---|---|---|---|---|
| `current_ratio` | activo corriente / pasivo corriente | `activo_corriente`, `pasivo_corriente` | veces | sí |
| `quick_ratio` | (activo corriente − existencias) / pasivo corriente | + `existencias` | veces | sí |
| `cash_ratio` | efectivo / pasivo corriente | `efectivo` | veces | sí |
| `debt_to_equity` | pasivo total / patrimonio | `pasivo_total`, `patrimonio` | veces | sí |
| `borrowings_to_equity` | deuda financiera / patrimonio controladora | `deuda_financiera`, `patrimonio_controladora` | veces | sí |
| `equity_ratio` | patrimonio / activo total | `patrimonio`, `activo_total` | fracción | sí |
| `roe` | resultado neto / patrimonio | `resultado_neto`, `patrimonio` | fracción | sí |
| `roa` | resultado neto / activo total | `resultado_neto`, `activo_total` | fracción | sí |
| `net_margin` | resultado neto / ingresos | `resultado_neto`, `ingresos` | fracción | sí |
| `gross_margin` | resultado bruto / ingresos | `resultado_bruto`, `ingresos` | fracción | sí |
| `operating_margin` | resultado operativo / ingresos | `resultado_operativo`, `ingresos` | fracción | sí |
| `interest_coverage` | resultado operativo / costo financiero | `resultado_operativo`, `costo_financiero` | veces | sí |
| `effective_tax_rate` | impuesto / resultado antes de impuestos | `impuesto`, `resultado_antes_impuestos` | fracción | **no** |
| `ocf_to_net_income` | flujo operativo / resultado neto | `flujo_operativo`, `resultado_neto` | veces | **no** |

**`publicable = False` no significa "mal calculado".** Significa que el número
es correcto pero no es una métrica de screener sin una banda de sanidad
(`SCREENER_CONTRACT_V1 §6`). `effective_tax_rate` puede ser negativa
legítimamente; `ocf_to_net_income` explota cuando el resultado neto tiende a
cero.

### Cómo se elige el tag de cada concepto

`ratio_defs.CONCEPTOS` mapea concepto → **lista ordenada** de tags, y
`elegir_concepto` toma **el primero presente**. El tag elegido queda en la
provenance: saber cuál de los candidatos se usó es parte del resultado.

Ejemplo: `patrimonio` prueba en orden `Equity`,
`EquityAttributableToOwnersOfParent`, `StockholdersEquity`,
`StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest`.

### Salvedad semántica que el propio código documenta

`deuda_financiera` mapea a `Borrowings` (IFRS),
`DebtLongtermAndShorttermCombinedAmount` y `LongTermDebt` (US-GAAP).
**No son el mismo perímetro**: `Borrowings` abarca deuda corriente y no
corriente; `LongTermDebt` es la de largo plazo incluida su porción corriente y
no incluye papel comercial de corto plazo. Se usa igual por ser el equivalente
más cercano, **y el tag empleado queda en la provenance para que la diferencia
sea visible, no tapada**.

---

## 2 · Mercado y valuación

`ratio_defs.RATIOS_MERCADO = ("pe", "market_cap", "price_to_book")`.
En `derived.ratio` aparecen como `pe`, `pb`, `ev_sales`.

| ratio | fórmula | insumos | condición `NOT_CALCULABLE` |
|---|---|---|---|
| `eps` | resultado neto / acciones promedio | `resultado_neto`, `acciones_promedio` | falta cualquiera |
| `pe` | precio / EPS | **precio**, fecha, **instrumento**, `eps_basico` | **falta el precio** ⇒ `NOT_CALCULABLE`; **nunca sustituir por otro precio** |
| `pb` | precio / valor libro por acción | precio, instrumento, `patrimonio`, acciones | ídem |
| `ev_sales` | enterprise value / ingresos | market cap, deuda, efectivo, `ingresos` | ídem |

**La regla del precio, textual:** si falta el precio, el ratio es
`NOT_CALCULABLE`. **Nunca** se sustituye en silencio por el precio de otra
fecha, de otro instrumento ni de otro proveedor. Sustituirlo sin registrarlo
viola la regla 3 de `appendices/FALLBACK_MATRIX.md`.

**Para emisores con ADR:** antes de calcular cualquiera de estos, leé
`02A_SEC_EDGAR_ADR_ANNEX.md` §4. Precio del ADR con EPS de la ordinaria da un
P/E inflado por `ratio_adr` (hasta 25× en PAMP).

### Estado observado

```
canonical_id | CALCULADO | NOT_CALCULABLE
-------------+-----------+----------------
 eps         |     todos |              0
 pe          |     mayor |          algunos
 pb          |     mayor |          algunos
 ev_sales    |     mayor |          algunos
```

36 filas en total, 9 emisores. La razón de fondo por la que no hay más está en
`02A` §3: el enlace instrumento↔emisor no está resuelto (`SG-10`).

---

## 3 · Ratios que publica la propia CNV

Además de los calculados, la CNV **publica sus propios ratios** como conceptos
del plan de cuentas (`8000009` y siguientes). En los datos canónicos aparecen
con prefijo `CNV_`:

```
CNV_apalancamiento     CNV_cobertura_intereses   CNV_deuda_fin_ebitda
CNV_ebitda_costos_fin  CNV_endeudamiento         CNV_liquidez
CNV_margen_neto        CNV_prueba_acida          CNV_roa
CNV_roe                CNV_rotacion_activos      CNV_solvencia
```

**Sirven como control independiente**: si el ratio que calcula Catalaxia y el
que publica el emisor difieren, hay que explicar por qué antes de publicar. No
se ajusta la fórmula para que coincidan.

Unidad: `xbrli:pure`.

---

## 4 · Cuándo un ratio es `NOT_CALCULABLE`

Cinco condiciones, todas con causa explícita en `derived.ratio.motivo`:

1. **Falta un insumo.** El concepto no existe para ese emisor/período.
2. **Denominador cero.**
3. **Períodos incompatibles.** Numerador y denominador de períodos distintos.
   Un flujo anual sobre un saldo trimestral no es un ratio.
4. **Unidades incompatibles.** Ver §5.
5. **Falta el precio** (sólo mercado/valuación).

**`NOT_CALCULABLE` es un resultado válido y es el correcto.** No se rellena con
un valor aproximado, ni con el del período anterior, ni con el de un comparable.

---

## 5 · Salvedades de unidad y período

- **Unidad.** Numerador y denominador deben compartir `unit_measure`. Un
  monetario sobre un adimensional no es un ratio. El vocabulario es
  `iso4217:ARS` / `iso4217:USD`, `xbrli:pure`, `iso4217:<CCY>/xbrli:shares`.
- **Escala.** La escala **no** está en `decimals` (que es una aserción de
  precisión), está en `unit_ref` (p. ej. `ars@1e6`). Dividir por `10^decimals`
  es un error.
- **Período.** Un `DURATION` y un `INSTANT` se combinan (es lo normal en ROA),
  pero el flujo debe **cerrar** en la fecha del saldo.
- **IAS 29 (emisores argentinos).** Cada cifra está expresada en el poder
  adquisitivo de **su** cierre (`measurement_date`). Combinar dos cifras con
  `measurement_date` distinto suma pesos de momentos distintos. Es la
  restricción menos intuitiva y la que más silenciosamente rompe un ratio.
- **CNV acumula YTD.** Los flujos van desde el inicio del ejercicio, no del
  trimestre. Un "Q3" de la CNV son nueve meses.
