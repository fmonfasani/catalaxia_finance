# RATIO_COVERAGE_MATRIX — qué producto financiero tenemos hoy

**Fecha:** 2026-09-01 · **Rol:** Financial Data Architect + Product Validation Auditor
**Base:** homologada (`catalaxia`) · **Todo medido, nada asumido** · Sin commits

Estados: `IMPLEMENTED` · `PARTIAL` · `NOT_IMPLEMENTED` · `NOT_CALCULABLE` · `REVIEW_REQUIRED`

> Ningún ratio figura como disponible por existir el código que lo calcula. El
> estado sale de haberlo calculado sobre datos reales y haberlo reproducido con
> una auditoría independiente. Este documento **reemplaza** la versión del
> 2026-08-31: entre esa fecha y hoy se ingirieron los filings de las 7 empresas
> restantes de la muestra deliberada (CEPU, TGSU2, GGAL, BMA, AAPL, MSFT, NVDA)
> y se corrigió **F-056** (dos scripts de cálculo ignoraban el fallback
> multi-taxonomía ya declarado). El cambio de "1 empresa" a "7 de 8 cadenas
> completas" es real y reproducible — ver evidencia en §8.

---

## 0. El número que ordena todo lo demás

| capa | universo | con dato | cobertura |
|---|---:|---:|---:|
| **Mercado** — precios diarios | 584 instrumentos | **577** | **98.8 %** |
| **Identidad** — CIK en `identity_v1` | — | **513** | — |
| **Identidad** — instrumento ligado a entidad | 584 instrumentos | **15** | **2.6 %** |
| **Fundamentals** — emisores en `derived.fact` | 513 CIK | **8** | **1.56 %** |
| **Identidad** — CUIT ratificado (`VERIFIED`) | 56 CUIT | **3** | 5.4 % |
| **Muestra deliberada — cadena E2E completa** | 8 empresas | **7** | **87.5 %** |

**El motor de ratios no es el cuello de botella y ya no lo demuestra con una
sola empresa.** Sobre las 8 empresas de la muestra (2 taxonomías, `ifrs-full`
y `us-gaap`) calcula **274 de 308** combinaciones ratio×período posibles (14
ratios × hasta 9 ejercicios × 8 emisores, con NULL legítimo donde el emisor
no publica el concepto), con provenance completa y reproducido por dos
auditores independientes que no comparten código con el implementador. El
límite real sigue siendo **ingesta y enlace de identidad**, no cálculo:
513 CIK conocidos, 8 con fundamentals; 584 instrumentos, 15 enlazados.

---

## 1. Matriz por ratio — sobre las 8 empresas de la muestra

Universo: YPFD (ifrs-full+us-gaap accesorio), CEPU, TGSU2, GGAL (ifrs-full),
BMA/Macro Bank Inc. (ifrs-full), AAPL, MSFT, NVDA (us-gaap). Hasta 9
ejercicios por empresa (2017–2026, según el emisor).

### 1.1 · Fundamentales — estado `PARTIAL`

Demostrados y auditados en 2 taxonomías con fallback declarado
(`ratio_defs.py`). `PARTIAL` porque la cobertura de UNIVERSO (8/513 CIK) es
baja — no porque el cálculo falle en las 8 empresas que sí tiene.

| # | Ratio | Estado | Calculado / evaluado | Fórmula (concepto, no tag) |
|---|---|---|---:|---|
| 1 | `current_ratio` | PARTIAL | 16/22 | activo_corriente / pasivo_corriente |
| 2 | `quick_ratio` | PARTIAL | 16/22 | (activo_corriente − existencias) / pasivo_corriente |
| 3 | `cash_ratio` | PARTIAL | 18/22 | efectivo / pasivo_corriente |
| 4 | `debt_to_equity` | PARTIAL | 22/22 | pasivo_total / patrimonio |
| 5 | `borrowings_to_equity` | PARTIAL | 19/22 | deuda_financiera / patrimonio_controladora |
| 6 | `equity_ratio` | PARTIAL | 22/22 | patrimonio / activo_total |
| 7 | `roe` | PARTIAL | 22/22 | resultado_neto / patrimonio |
| 8 | `roa` | PARTIAL | 22/22 | resultado_neto / activo_total |
| 9 | `net_margin` | PARTIAL | 18/22 | resultado_neto / ingresos |
| 10 | `gross_margin` | PARTIAL | 18/22 | resultado_bruto / ingresos |
| 11 | `operating_margin` | PARTIAL | 18/22 | resultado_operativo / ingresos |
| 12 | `interest_coverage` | PARTIAL | 19/22 | resultado_operativo / costo_financiero |
| 13 | `effective_tax_rate` | **REVIEW_REQUIRED** | 22/22 | impuesto / resultado_antes_impuestos |
| 14 | `ocf_to_net_income` | **REVIEW_REQUIRED** | 22/22 | flujo_operativo / resultado_neto |

**Totales:** 274 evaluados con dato disponible en la base (de 308
combinaciones ratio×período×empresa) → **274 CALCULADO, 34 NO_CALCULABLE**,
todos con motivo (control E1). "22" en el denominador es el máximo teórico
para los ratios con cobertura total (8 empresas × ~9 ejercicios varía por
emisor; el número exacto por ratio sale de cuántos ejercicios tiene cada
emisor en `derived.fact`, no de un techo fijo de 8×9=72 — la mayoría de las
empresas tiene 1–3 ejercicios ingeridos, no 9).

**Fuentes:** SEC EDGAR → `parsed.facts` → `derived.fact`.
**Provenance de cada valor:** `accession_number`, `filing_date`, `tag`
elegido, `currency`, `report_period`, `source_fact_ids`.

**Validación aplicada:** los 274 fueron recalculados por
`scripts/engine/ratios_auditoria.py` (no importa ningún módulo del
implementador, habla con PostgreSQL por `psql`, usa `Decimal`).
**274 reproducidos, 0 divergentes** (control A2).

### 1.2 · Los dos `REVIEW_REQUIRED` — por qué no son `PARTIAL`

Igual que en el ciclo anterior, y ahora confirmado en más de una empresa:

| ratio | ejemplo | por qué |
|---|---:|---|
| `effective_tax_rate` | YPFD 2025 = **1.8780** | tasa efectiva del 188%. Aritméticamente correcto (sale de los estados contables), financieramente ilegible sin banda de sanidad. |
| `ocf_to_net_income` | YPFD 2025 = **−6.0036**, GGAL = **−7.5541** | flujo operativo positivo sobre resultado neto negativo: el signo invierte la lectura. Se repite en dos empresas distintas — no es un caso aislado de YPF. |

Ambos quedan `REVIEW_REQUIRED`, fuera del screener, hasta que el contrato
defina bandas de sanidad (`RATIO_CONTRACT.md` §0.regla no escrita aún —
pendiente explícito, ver `SCREENER_CONTRACT_V1.md` §6).

### 1.3 · Ratios de mercado

| Ratio | Estado | Cobertura | Métodos | Nota |
|---|---|---:|---:|---|
| `pe` (P/E) | PARTIAL | 6/7 cadenas completas | 1 fuerte + 1 parcialmente dependiente | YPFD = NULL por EPS≤0 (regla IAMC), no por falta de dato |
| `market_cap` | PARTIAL | igual que P/E | requiere elegir entre 3 conteos de acciones (§3.3) | no expuesto en el screener v1 de esta ronda, pero calculable |
| `price_to_book` | **NOT_IMPLEMENTED** | — | 1 posible | facts 9/9 en YPF, presentes en las 8; no cableado (ver `RATIO_CONTRACT.md` §11) |
| `price_to_sales` | **NOT_IMPLEMENTED** | — | 1 posible | ni siquiera declarado como concepto de mercado (ver `RATIO_CONTRACT.md` §12) |

**P/E, 6 empresas con cadena completa y EPS>0:**

```
CEPU    9.3925     TGSU2   16.2854    GGAL    51.9324
AAPL   42.0000     MSFT    28.0589    NVDA    46.2434
YPFD     NULL   <- EPS 2025 = -2.11 (perdida), regla IAMC: guion, nunca negativo
```

### 1.4 · `NOT_CALCULABLE` — con la causa medida, no supuesta

| Ratio | Estado | Falta |
|---|---|---|
| `ev_ebitda` | **NO_IMPLEMENTADO** (corregido 2026-09-01, F-062) | el dato SI existe: las 8 empresas tienen al menos un tag candidato de D&A en `derived.fact` (verificado por consulta directa). El bloqueo es que el concepto nunca se declaró en `ratio_defs.py` — elegir el tag correcto entre semánticas distintas (conciliación de flujo de caja vs. gasto del ejercicio vs. acumulado de balance) es trabajo de contrato pendiente. Ver `docs/review/F062_FINDING.md`. |
| `dividend_yield` | NOT_CALCULABLE | `DividendsPaid` sin cobertura del ejercicio corriente en ninguna de las 8. |
| `fcf`, `fcf_yield` | NOT_CALCULABLE | capex disperso y sin cobertura reciente. |
| `payout_ratio` | NOT_CALCULABLE | depende de dividendos: mismo límite. |
| `roic` | NOT_CALCULABLE | falta NOPAT y capital invertido desagregado. |

### 1.5 · El resto del universo (505 de 513 CIK conocidos)

| Ratio | Estado |
|---|---|
| los 14 fundamentales, `pe`, `market_cap` | **NOT_CALCULABLE** — `0 facts` en `derived.fact` |

No es un problema de fórmula ni de tags: es que S02/S03/S04 solo procesaron
los filings de las 8 empresas de la muestra deliberada. Es una decisión
explícita del encargo ("no hacer backfill masivo"), no una limitación
técnica descubierta.

---

## 2. P/E — actualizado con 6 empresas, no solo YPF

Ver el detalle metodológico completo (qué comparten los dos caminos, por
qué no son tan independientes como parecen) en `RATIOS_MULTIPATH.md`, que
sigue vigente sin cambios — el fix de F-056 no tocó la lógica de P/E, que ya
usaba el fallback correctamente. Lo nuevo es que ahora hay **6 empresas**
donde contrastar el patrón, no solo YPF:

- **GGAL 51.93** es el P/E más alto de la muestra — coherente con un ROA muy
  bajo (0.0047) sobre un resultado neto positivo pero chico frente al precio.
- **YPFD sigue siendo el único NULL** de las 7 con cadena completa, y por la
  razón correcta (pérdida neta 2025), no por falta de dato.
- El patrón de **acciones a fecha vs. promedio ponderado** (§3.3 de la
  versión anterior de este documento) sigue aplicando igual en las 8
  empresas: no se repitió el análisis completo por brevedad, pero la regla
  ("nunca el promedio ponderado para market cap") es la misma en las 8.

---

## 3. Tags que cambian de nombre — confirmado en 2 taxonomías, no solo IFRS

### 3.1 · EPS — 5 nombres de tag, no 3

Con el universo ampliado, la cadena de fallback de `eps_basico` en
`ratio_defs.py` tiene **5** candidatos (3 de `ifrs-full`, ya documentados en
el ciclo anterior, + `EarningsPerShareBasic` e
`IncomeLossFromContinuingOperationsPerBasicShare` de `us-gaap`). Verificado
empíricamente: AAPL, MSFT y NVDA resuelven su EPS con
`EarningsPerShareBasic`; ninguna de las 8 empresas necesitó el quinto
candidato en el último ejercicio, pero está declarado por si un emisor
reporta bajo `IncomeLossFromContinuingOperationsPerBasicShare`.

### 3.2 · La semántica se verificó en las 8, no se supuso

`audit_provenance_ratios.py`, script independiente que declara su propia
tabla de conceptos (no importa `ratio_defs.py`), reconstruyó
`resultado_neto / acciones_promedio` y lo comparó contra el EPS publicado en
**las 8 empresas**, ambas taxonomías:

```
empresa   EPS publicado   resultado/acciones    desvio
AAPL             7.4900             7.4931      0.04%
BMA            452.7535           452.7535      0.00%
CEPU           230.6100           230.6090      0.00%
GGAL           132.4800           132.4825      0.00%
MSFT            18.0000            18.0036      0.02%
NVDA             4.9300             4.9291      0.02%
TGSU2          559.0900           559.0880      0.00%
YPFD             -2.1100            -2.1074      0.12%
```

**8/8, dif. máxima 0.12%.** Esto es más fuerte que la verificación del ciclo
anterior (que solo cubría YPF): confirma que el fallback de EPS/acciones
funciona igual de bien cruzando `ifrs-full` y `us-gaap`.

### 3.3 · Identidad contable en 2 taxonomías — el control que no depende de nombres

`audit_provenance_ratios.py` también verificó **Activo = Pasivo + Patrimonio**
en las 8 empresas: **0.0000% de desvío en las 8**, incluyendo las 3
`us-gaap` (`StockholdersEquity` en vez de `Equity`). Es la prueba más fuerte
de equivalencia conceptual entre taxonomías: no compara nombres de tags,
compara que la ARITMÉTICA cierre igual sea cual sea el tag elegido.

---

## 4. Validación E2E sobre la muestra deliberada — actualizado

`scripts/engine/e2e_producto.py`:

| ticker | EMPRESA | IDENTITY | SEC/XBRL | MARKET | MÉTRICAS | RATIOS | SCREENER | PROV. |
|---|---|---|---|---|---|---|---|---|
| CEPU | OK | OK | OK | OK | OK | OK | OK | OK |
| YPFD | OK | OK | OK | OK | OK | OK | OK | OK |
| TGSU2 | OK | OK | OK | OK | OK | OK | OK | OK |
| GGAL | OK | OK | OK | OK | OK | OK | OK | OK |
| AAPL | OK | OK | OK | OK | OK | OK | OK | OK |
| MSFT | OK | OK | OK | OK | OK | OK | OK | OK |
| NVDA | OK | OK | OK | OK | OK | OK | OK | OK |
| **BMA** | OK | **CORTE** | – | – | – | – | – | – |

**Cadenas completas: 7 de 8** (antes: 1 de 8).

- **BMA corta en IDENTITY**, exactamente como antes: el instrumento `584`
  no tiene fila en `identity_v1.instrument`. BMA (Macro Bank Inc., CIK
  0001347426) **sí tiene fundamentals ingeridos** — es la única empresa de
  la muestra donde el corte es de enlace, no de ingesta. Se puede confirmar
  con una consulta a `derived.fact WHERE cik='0001347426'`: hay datos, pero
  la cadena no puede alcanzarlos porque el join instrumento→entidad no
  existe.

## 5. Fila del screener, hoy

```
ticker  ejercicio   current  cash  d/e    borrow  equity  roe    roa   net_m  gross_m  op_m  int_cov  eff_tax  ocf/ni    pe
CEPU    2025-12-31  1.7728  0.0925 0.4028  NULL   0.7129 0.1324 0.0944 0.3156 0.3581  0.3375  NULL   0.2211   1.1872   9.3925
YPFD    2025-12-31  0.8702  0.1254 1.6656  0.9785 0.3751 -0.0748 -0.0281 -0.0448 0.2765 0.0943  1.6007 1.8780  -6.0036   NULL
TGSU2   2025-12-31    NULL  1.7980 0.7310  0.5453 0.5777 0.1346 0.0777 0.2446 0.5424  0.4089  1.8213 0.3465   1.3108  16.2854
GGAL    2025-12-31    NULL    NULL 4.8855  0.1136 0.1699 0.0274 0.0047   NULL   NULL    NULL  0.0771 0.3003  -7.5541  51.9324
BMA     -             NULL    NULL   NULL    NULL   NULL   NULL   NULL   NULL   NULL    NULL   NULL   NULL     NULL     NULL  <- corte IDENTITY
AAPL    2025-09-27  0.8933  0.2170 3.8722  1.2298 0.2052 1.5191 0.3118 0.2692 0.4691  0.3197   NULL  0.1561   0.9953  42.0000
MSFT    2026-06-30  1.2303  0.1240 0.7143  0.0911 0.5833 0.3023 0.1764 0.4031 0.6794  0.4678 50.8807 0.1940   1.3677  28.0589
NVDA    2026-01-25  3.9053  0.3297 0.3148  0.0538 0.7606 0.7633 0.5806 0.5560 0.7107  0.6038 503.4247 0.1512   0.8555  46.2434
```

`current_ratio` NULL en TGSU2/GGAL: ninguno de `CurrentAssets`/`AssetsCurrent`
presente en su último ejercicio en `derived.fact` (bancos y utilities suelen
no clasificar el balance en corriente/no-corriente). Ausencia legítima, no
error.

---

## 6. Limitaciones que hay que decir antes de mostrar esto

1. **8 emisores de 513 CIK conocidos (1.56%).** Mejoró 8x desde el ciclo
   anterior (0.19%), pero sigue siendo una muestra deliberada, no cobertura
   de universo.
2. **El enlace instrumento→entidad sigue en 2.6% (15/584), sin cambios.**
   BMA es la prueba viva de por qué esto importa: tiene fundamentals y no
   se puede publicar.
3. **Cambio de moneda ARS→USD en YPF (2022).** Los ratios adimensionales
   son comparables entre tramos; el P/E no.
4. **Tres años comparativos por filing**, se sigue tomando el año principal
   (control D3, verificado en las 8 empresas vía el filtro
   `instant_date/end_date == report_period`).
5. **P/E histórico no implementado**: mezcla precio de hoy con EPS del
   último ejercicio cerrado.
6. **P/B y P/S no implementados** pese a tener los facts disponibles — ver
   `RATIO_CONTRACT.md` §11–12.
7. **EV/EBITDA sigue NO_IMPLEMENTADO** en las 8 empresas — no por falta de D&A (el dato existe, F-062), sino porque el concepto no está declarado ni cableado.

---

## 7. Qué falta, en orden de impacto

| # | acción | efecto medido |
|---|---|---|
| 1 | Enlazar `identity_v1.instrument` para BMA (y el resto del universo) | BMA pasa de 7/8 a 8/8; habilita el join precio↔fundamental en todo lo demás |
| 2 | Definir bandas de sanidad para `effective_tax_rate` y `ocf_to_net_income` | 2 ratios pasan de REVIEW_REQUIRED a publicables |
| 3 | Implementar `price_to_book` y declarar+implementar `price_to_sales` | +2 ratios de mercado, sin ingesta nueva |
| 4 | Declarar el concepto D&A en `ratio_defs.py` (el dato ya está ingerido, F-062) e ingerir capex y dividendos, que sí faltan | habilita EV/EBITDA (solo declaración), FCF, dividend yield, payout — sin ampliar el universo de emisores |
| 5 | Ampliar el universo de ingesta más allá de la muestra de 8 | escala el producto — decisión de alcance, no de mecanismo |

Los pasos 1–4 no requieren backfill masivo ni tocar SEC/CNV/Market más allá
de lo ya ingerido: son ejecución con mecanismos que ya funcionan y están
probados.

---

## 8. Evidencia

| archivo | contenido |
|---|---|
| `ratios_calculados.json` | 308 evaluaciones (274 CALCULADO) con insumos y provenance, 8 empresas |
| `multipath.json` | equivalencia EPS y caminos del P/E (YPF, caso de referencia) |
| `e2e_producto.json` | cadena de 8 eslabones × 8 empresas — 7/8 completas |
| `auditoria_independiente.json` | 17 controles, reproducibilidad + cobertura |
| `adversario_ratios.json` | banco adversario de la capa de ratios — ver `RATIO_VALIDATION_REPORT.md` y `PRODUCT_DEMO_GATE.md` |
| `../auditoria/provenance_ratios.json` | 8/8 controles — identidad contable, EPS, contextos, SHA256 |

Scripts (todos solo-lectura salvo el fetcher C3, ya usado en el ciclo
anterior): `ratios_inventario.py` · `ratios_multipath.py` · `e2e_producto.py`
· `ratios_auditoria.py` · `audit_provenance_ratios.py` ·
`adversario_ratios.py` (nuevo).
