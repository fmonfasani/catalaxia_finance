# METR_5Y_DEMO — Metrogas S.A., cinco ejercicios E2E

**Estado del gate: `PASS_WITH_WARNINGS`.**
Los doce criterios del gate se cumplen. Las advertencias son dos y están
cuantificadas: una familia entera de ratios (FCF) no es calculable porque la
fuente no publica capex, y dos guardas de tests de sprints anteriores quedaron
en rojo por un cambio que este sprint sí tenía que hacer. Ninguna bloquea.

| | |
|---|---|
| emisor | Metrogas S.A. · CUIT 30657863676 · `entity_id` `CUIT:30657863676` |
| instrumento | `METR.BA` (BYMA), moneda ARS verificada |
| ejercicios | FY2021, FY2022, FY2023, FY2024, FY2025 — los cinco cierres anuales completos |
| perímetro | CONSOLIDADO en los cinco, declarado y evidenciado |
| DB del demo | `metr5y` @ 5433 (aislada; producción y la homologada intactas) |
| salidas | `METR_5Y_DEMO.xlsx` · `METR_5Y_DEMO.csv` (5 filas × 137 columnas) |

---

## 1. Años seleccionados

Se pidieron 2021–2025 y los cinco están completos, así que no hubo que
reemplazar ninguno. Cada uno es un período independiente: `report_period`
propio, `accn` propio, `measurement_date` propio, `econ_key` propio. No se
solapan ni se derivan uno de otro.

| FY | cierre | documento (`accn`) | escala declarada | `measurement_date` |
|---|---|---|---|---|
| 2021 | 2021-12-31 | `24a37877-f995…` | `ars@1e3` | 2021-12-31 |
| 2022 | 2022-12-31 | `3178ddb6-9ce4…` | `ars@1e6` | 2022-12-31 |
| 2023 | 2023-12-31 | `04c91836-c648…` | `ars@1e6` | 2023-12-31 |
| 2024 | 2024-12-31 | `89e96a2b-946e…` | `ars@1e6` | 2024-12-31 |
| 2025 | 2025-12-31 | `d96fd259-c5ce…` | `ars@1e6` | 2025-12-31 |

FY2021 declara la escala en **miles** y los otros cuatro en **millones**. El
modelo normaliza a ARS absolutos y conserva la escala declarada en la
provenance de cada celda: la diferencia queda visible, no aplanada.

### FY2021 tiene dos ocurrencias, y se resolvieron sin descartar ninguna

El corpus trae **dos documentos** para FY2021 CONSOLIDADO: `24a37877` (#2860477)
y `5b4d69bf` (#2860327). Los 76 conceptos coinciden **valor por valor**; lo
único que cambia es el nombre de un adjunto (*Memoria completa 31.12.21.pdf*
contra *MetroGAS Memoria 31.12.21.pdf*).

Las dos ocurrencias se cargaron y se compararon. Como no hay ninguna diferencia
económica, **la elección de versión no puede alterar ningún número publicado**,
y se deja constancia en vez de inferir cuál supersede a cuál. No se usó el
ordinal de presentación para decidir: W-1.3A.2 mostró que el ordinal mayor es
tanto el consolidado como el separado según el emisor, así que no ordena nada.

---

## 2. Perímetro

No se mezcla. Todo el demo es CONSOLIDADO y el modelo lo verifica por
ejercicio: si dos celdas vinieran de contextos distintos, el control
`perimetro sin mezcla` falla.

Además del campo declarado se resuelve el **perímetro evidenciado** a partir
del nombre de los adjuntos, porque W-1.3A.2 demostró que `TipoBalance` puede
rotular igual un consolidado y un separado:

| FY | declarado | evidenciado | evidencia |
|---|---|---|---|
| 2021 | CONSOLIDADO | CONSOLIDADO | `Estado Contable_1221_CON.pdf` |
| 2022 | CONSOLIDADO | CONSOLIDADO | `Estados Financieros_1222_CON.pdf` |
| 2023 | CONSOLIDADO | CONSOLIDADO | `Estados Financieros_1223_CON.pdf` |
| 2024 | CONSOLIDADO | CONSOLIDADO | `Estados Financieros_1224_CON.pdf` |
| 2025 | CONSOLIDADO | CONSOLIDADO | `Estados Financieros_1225_CON.pdf` |

Coinciden los cinco. METR no presenta el patrón peligroso de Longvie o BYMA.

---

## 3. Cobertura de fundamentals

De los 31 conceptos del modelo, **29 se resuelven en los cinco ejercicios**.
Los dos que no:

| concepto | estado | motivo |
|---|---|---|
| `capex` | **AUSENTE EN LA FUENTE** | la CNV no publica un código de capex; el grupo `3xxxxxx` no lo desagrega |
| `fcf` | **NO DERIVABLE** | `FCF = CFO − capex`, y sin capex el derivado no existe |

`existencias` merece una nota: METR declara `Inventory` con **guion** de 2022 en
adelante. Eso es un **cero declarado**, no un dato ausente (semántica F-063), y
por eso el `quick_ratio` sí se calcula esos años. Distinguir las dos cosas es lo
que hace la diferencia entre un ratio correcto y uno faltante.

---

## 4. Los cinco años, en ARS y en USD MEP

Cifras en millones. Los ARS de cada año están en el poder adquisitivo de **su**
cierre (IAS 29) y **no son comparables entre sí**; la columna USD es la que
permite compararlos.

| | 2021 | 2022 | 2023 | 2024 | 2025 |
|---|---:|---:|---:|---:|---:|
| **Revenue** ARS | 55.671 | 107.128 | 328.264 | 925.090 | 1.217.305 |
| **Revenue** USD | 281,4 | 326,7 | 329,9 | 790,4 | 822,1 |
| **EBITDA** ARS | 898 | 7.806 | 21.354 | 187.752 | 256.694 |
| **EBITDA** USD | 4,5 | 23,8 | 21,5 | 160,4 | 173,4 |
| **Net income** ARS | −4.369 | 5.814 | 96.355 | 156.628 | 132.483 |
| **Net income** USD | −22,1 | 17,7 | 96,8 | 133,8 | 89,5 |
| **Equity** USD | 87,7 | 120,6 | 219,5 | 538,7 | 648,6 |
| **Market cap** USD | 111,1 | 178,7 | 439,2 | 1.353,9 | 978,9 |
| **EV** USD | 171,0 | 202,4 | 440,9 | 1.287,3 | 998,1 |

El contraste está en el CAGR 2021→2025:

| métrica | CAGR ARS | CAGR USD |
|---|---:|---:|
| Revenue | **116,24 %** | **30,73 %** |
| EBITDA | 311,22 % | 148,60 % |
| Patrimonio | 172,77 % | 64,91 % |

Los 116 % de "crecimiento" de ventas en pesos son, en su mayor parte,
inflación. Sin la capa USD el demo contaría otra historia.

---

## 5. FX MEP — regla única y reproducible

**Regla:** `USD_MEP = ARS / MEP(última rueda ≤ fecha de cierre del ejercicio)`.

Se aplica igual a stocks y a flujos, y el fundamento es que bajo IAS 29 el
estado **entero** ya está expresado en el poder adquisitivo de la fecha de
cierre: no hay motivo para convertir el flujo a un tipo promedio y el saldo al
de cierre, porque ambos están medidos en la misma fecha.

No se usó dólar oficial ni CCL.

| FY | fecha MEP | MEP (ARS/USD) | desfase vs cierre |
|---|---|---:|---:|
| 2021 | 2021-12-30 | 197,80 | 1 día |
| 2022 | 2022-12-30 | 327,94 | 1 día |
| 2023 | 2023-12-29 | 995,00 | 2 días |
| 2024 | 2024-12-30 | 1.170,41 | 1 día |
| 2025 | 2025-12-30 | 1.480,74 | 1 día |

Fuente: `dolarito`, serie MEP diaria, leída de `screener.db` en `mode=ro` e
ingestada en `market.fx_rate` con hash por cotización. El desfase es siempre el
fin de semana o feriado del 31-12: no hay rueda ese día.

---

## 6. Mercado

**Precio**: `precios_diarios` en producción cubre sólo 2026-07-09 .. 2026-08-21,
así que **no alcanza para ningún cierre 2021–2025**. Se bajó la historia de
`METR.BA` de yfinance (1.267 ruedas, 2020-11-02 .. 2026-01-14) a `market.price`,
con hash por rueda. Se baja una sola vez; la segunda corrida la reutiliza.

**Guarda de moneda**: se verifica que el instrumento declare ARS antes de
ingestar una sola fila. `METR` sin sufijo en yfinance es otro emisor, y ese
error valdría tres órdenes de magnitud en el market cap.

| FY | fecha precio | precio ARS | precio USD | desfase |
|---|---|---:|---:|---:|
| 2021 | 2021-12-30 | 38,60 | 0,1951 | 1 día |
| 2022 | 2022-12-30 | 103,00 | 0,3141 | 1 día |
| 2023 | 2023-12-29 | 768,00 | 0,7719 | 2 días |
| 2024 | 2024-12-30 | 2.785,00 | 2,3795 | 1 día |
| 2025 | 2025-12-30 | 2.547,50 | 1,7204 | 1 día |

Precio y fundamentals **nunca** se cruzan sin etiquetar: cada fila lleva
`mkt_price_fecha`, `mkt_mep_fecha` y `mkt_dias_desfase_precio`.

### Acciones — la CNV no las publica

Se usan dos caminos independientes y se reconcilian:

* **`Capital`** — capital social nominal, valor par $1. Es constante
  (569.171.000 en 2021, 569.000.000 después) mientras `AjusteDeCapital` lleva
  aparte la reexpresión IAS 29, lo que confirma que es el nominal. Es un valor
  **reportado**, y es el que se publica.
* **`NetIncome / EPS_basico`** — el promedio ponderado implícito en el EPS que
  el emisor declaró. Es el **control**.

Los dos coinciden dentro del 0,58 %–2,52 %, y la diferencia tiene explicación:
uno es el recuento de cierre y el otro un promedio ponderado, y el EPS se
calcula sobre resultado atribuible a los propietarios. Veredicto `CLOSE` en los
cinco años.

**EV** = market cap + deuda financiera total − efectivo. La deuda financiera
total se arma sumando `DebtCurrent` + `DebtNonCurrent`, porque la CNV no publica
el total.

---

## 7. Ratios

El registry declara **38 ratios**. Por ejercicio se calculan entre 24 y 31.

| categoría | ratios | estado |
|---|---|---|
| crecimiento | revenue, ebitda, net income, eps, fcf, + CAGR | 4 de 5 (fcf no) |
| márgenes | gross, ebitda, operating, net, fcf | 4 de 5 (fcf no) |
| retornos | roe, roa, roic, roce | 4 de 4 |
| apalancamiento | debt/equity, debt/ebitda, net debt/ebitda, interest coverage, fcf/debt, ocf/debt | 5 de 6 |
| liquidez | current, quick, cash | 3 de 3 |
| flujo | fcf yield, fcf/ni, ocf/ni, price/cfo | 2 de 4 |
| valuación | pe, p/b, p/s, p/fcf, ev/revenue, ev/ebit, ev/ebitda, fcf/ev | 6 de 8 |
| eficiencia | asset turnover, effective tax rate, equity ratio | 3 de 3 |

**24 ratios se calculan en los cinco años.** Otros 7 en algunos años, y 7 en
ninguno.

### Ratios no calculables, con motivo

| ratio | años | motivo |
|---|---|---|
| `fcf_growth`, `fcf_margin`, `fcf_to_debt`, `fcf_yield`, `fcf_to_net_income`, `price_to_fcf`, `fcf_to_ev` | los 5 | `INPUT_AUSENTE_EN_LA_FUENTE: capex` |
| `pe` | 2021 | `NO_SIGNIFICATIVO`: EPS = −7,72 ≤ 0 |
| `ev_to_ebit`, `interest_coverage`, `roic` | 2021 | `NO_SIGNIFICATIVO`: EBIT = −2.159 M ≤ 0 |
| `effective_tax_rate` | 2021 | `NO_SIGNIFICATIVO`: resultado antes de impuestos = −616 M ≤ 0 |
| `eps_growth`, `net_income_growth` | 2021, 2022 | `NO_SIGNIFICATIVO`: base del ejercicio anterior ≤ 0 |

Las bandas de sanidad son **declarativas**, viven en el registry y no en el
evaluador. Un PER con EPS negativo es aritméticamente válido y económicamente
vacío: se publica un guion, que es la convención IAMC que el proyecto ya usa.
Un crecimiento medido desde una base negativa —METR pasa de −4.369 M a
+5.814 M en FY2022— daría "−229 %", que es ruido.

### Valuación, los cinco años

| | 2021 | 2022 | 2023 | 2024 | 2025 |
|---|---:|---:|---:|---:|---:|
| EPS (ARS) | −7,72 | 9,96 | 167,65 | 271,38 | 229,62 |
| P/E | — | 10,34 | 4,58 | 10,26 | 11,09 |
| P/B | 1,27 | 1,48 | 2,00 | 2,51 | 1,51 |
| P/S | 0,39 | 0,55 | 1,33 | 1,71 | 1,19 |
| EV/Revenue | 0,61 | 0,62 | 1,34 | 1,63 | 1,21 |
| EV/EBITDA | 37,68 | 8,50 | 20,55 | 8,02 | 5,76 |
| EV/EBIT | — | 39,22 | 65,54 | 10,36 | 7,53 |
| ROE | −0,25 | 0,15 | 0,44 | 0,25 | 0,14 |
| ROIC | — | 0,015 | 0,050 | 0,131 | 0,123 |
| ROCE | −0,04 | 0,02 | 0,02 | 0,20 | 0,17 |
| Net debt/EBITDA | 13,20 | 0,99 | 0,08 | −0,42 | 0,11 |
| Current ratio | 0,46 | 0,43 | 0,42 | 0,82 | 1,34 |

---

## 8. EPS y PER — método explícito

**EPS**: se usa el **EPS reportado por el emisor** (`EPS_basico`), que es la
primera prioridad de la consigna. No hace falta caer al fallback
NI/acciones porque el dato existe en los cinco ejercicios.

**EPS Growth** = `EPS(t) / EPS(t−1) − 1`, con la banda de base positiva.

**P/E, dos caminos**:

1. `precio / EPS reportado`
2. `market cap / NetIncome`

| FY | camino 1 | camino 2 | desvío | veredicto |
|---|---:|---:|---:|---|
| 2021 | — | −5,03 | — | `INCOMPARABLE` (EPS ≤ 0) |
| 2022 | 10,34 | 10,08 | 2,6 % | `CLOSE` |
| 2023 | 4,58 | 4,54 | 1,0 % | `CLOSE` |
| 2024 | 10,26 | 10,12 | 1,4 % | `CLOSE` |
| 2025 | 11,09 | 10,94 | 1,4 % | `CLOSE` |

La diferencia es del mismo orden que la diferencia de acciones (0,6–2,5 %) y
tiene la misma causa: el camino 2 usa el recuento de cierre y el EPS usa el
promedio ponderado. **No se forzó ninguna coincidencia.**

---

## 9. Reconciliación multi-método

35 comparaciones: **8 `MATCH`, 20 `CLOSE`, 3 `INCOMPARABLE`, 4 `ANOMALY`.**

La CNV publica sus propios ratios (`CNV_roe`, `CNV_roa`, …), lo que da un
segundo camino auditado y gratuito. El emisor no documenta su fórmula, pero se
puede **inferir de la evidencia**: contra `PatrimonioAperturaEjercicio` queda
claro que usa el **promedio del ejercicio**, no el saldo de cierre.

| FY | NI / patrimonio promedio | `CNV_roe` publicado |
|---|---:|---:|
| 2023 | 0,5642 | 0,56 |
| 2025 | 0,1480 | 0,15 |

Se compara contra esa base —la del emisor— y no contra la del modelo, porque
comparar bases distintas produce una diferencia que no informa nada.

### Anomalía: los ratios publicados por el emisor no reconcilian en 2021 y 2022

| FY | métrica | modelo (base promedio) | publicado | desvío |
|---|---|---:|---:|---:|
| 2021 | ROE | −0,2236 | −0,03 | 645 % |
| 2021 | ROA | −0,0483 | −0,01 | 383 % |
| 2022 | ROE | 0,1586 | 0,29 | 45 % |
| 2022 | ROA | 0,0371 | 0,07 | 47 % |

Desde FY2023 reconcilian (`CLOSE`/`MATCH`); en FY2021 y FY2022 **no lo hacen
con ninguna base razonable** —ni cierre, ni apertura, ni promedio—. Es
consistente con que la CNV amplió su juego de ratios publicados en 2023:
`CNV_prueba_acida`, `CNV_rotacion_activos` y `CNV_cobertura_intereses` sólo
existen de 2023 en adelante.

**No se corrigió ni se ocultó.** Queda etiquetado `ANOMALY`. Afecta únicamente
al ratio que publica el emisor, no a los ratios del modelo, que se calculan
desde los hechos y reconcilian entre sí.

Los 3 `INCOMPARABLE` son `asset_turnover` 2021–2022 (el emisor no publicaba
`CNV_rotacion_activos` todavía) y el P/E 2021.

---

## 10. Provenance E2E

**289 celdas, 31 ratios, 0 eslabones rotos, 5/5 documentos con sha256 del RAW.**
`METR_5Y_DEMO_PROVENANCE.csv` trae una fila por celda con toda la cadena
resuelta. Un derivado sobre otro derivado se sigue **recursivamente** hasta
tocar hechos canónicos: `deuda_neta` → `deuda_financiera_total` → `DebtCurrent`
+ `DebtNonCurrent`.

Ejemplo real, EV/EBITDA de FY2025:

```
ratio            ev_to_ebitda = 5,7577
formula          m.ev / c.ebitda
  -> concepto    ebitda
  -> tag         EBITDA          (elegido por la cadena de fallback del registry)
  -> qname       cnv:EBITDA
  -> valor       256.694.000.000  unit_ref ars@1e6  measurement_date 2025-12-31
  -> context     CONSOLIDADO|DURATION|2025-01-01|2025-12-31|2025-12-31
  -> entity_id   CUIT:30657863676
  -> fact_key    cd65d303f911d8667c16ae7f3ceb868b1997fcc9bd41305be5c08e75b65e0dcc
  -> econ_key    aeecde6f4210b6c8c4f41751a4567beb24bf9588f8d1c7a37acaa81ab6441966
  -> parsed      fact_id 3749
  -> ocurrencia  d96fd259-c5ce-431f-8e14-17af592b99f9
  -> documento   .../eeff_html/d96fd259-....html
  -> sha256      460d167241febbe3a3be8142c44be60c6c5eebfd4dc76c53a71b3dfca9b6b191

  cadena de mercado
  -> price       2.547,50 ARS   fecha 2025-12-30   fuente yfinance
  -> MEP         1.480,74       fecha 2025-12-30   fuente dolarito
  -> hash FX     8f8888f73b3b3fe1e4079b7aa4ab8807eb956522c85801b9d79ccfee9c15b1ea
```

---

## 11. Pipeline — qué entró y qué quedó afuera

| etapa | n | explicación |
|---|---:|---|
| expected | 286 | guids de METR en `whitelist_eeff.csv` |
| downloaded | 286 | con HTML en el RAW |
| parsed | 60 | documentos de los que salió al menos un código con valor |
| **rejected** | **226** | HTTP 200 **sin datos financieros**: son cáscaras del visor, no documentos |
| normalized | 58 | `cnv_estados_norm` colapsa 2 documentos y 152 filas por su PK económica |
| canonical | 4.648 | `parsed.facts` = filas de `cnv_estados_v2`, sin pérdida |
| derived | 4.648 | `derived.fact` vigentes, con `econ_key` y `measurement_date` |
| published | 471 | hechos de los 5 FY CONSOLIDADO que alimentan el demo |

Dos diferencias que hay que explicar y no esconder:

**286 → 60.** Los 226 rechazados no son un fallo de descarga: el visor de la CNV
devuelve 200 con una página sin datos. HTTP 200 ≠ documento financiero válido.

**60 → 58 en `normalized`.** `cnv_estados_norm` tiene la PK económica y colapsa
ocurrencias antes de que la capa canónica pueda verlas. **El demo no pasa por
ahí**: se ingestó desde `cnv_estados_v2` (PK `(accn, concepto)`), de modo que
las 4.648 filas y los 60 documentos llegan enteros al canónico y el colapso lo
decide la capa canónica con evidencia. De los 60, 56 están en la lista de
producción y 4 sólo en la amplia —uno de ellos es la segunda ocurrencia de
FY2021.

---

## 12. Controles de calidad

**55 controles, 55 PASS, 0 FAIL, 0 WARN, 0 SKIP** (11 por ejercicio):

| control | qué compara |
|---|---|
| activo = corriente + no corriente | identidad contable, tolerancia 1e-6 |
| pasivo = corriente + no corriente | idem |
| activo = pasivo + patrimonio | idem |
| bruto = ingresos + costo | coherencia del estado de resultados (el costo viene en negativo) |
| ebitda = ebit − D&A | coherencia del cálculo del emisor |
| moneda homogénea | una sola moneda por ejercicio |
| escala declarada única | una sola `unit_ref` por ejercicio |
| perímetro sin mezcla | un solo `context_id` de perímetro |
| `measurement_date` = cierre | IAS 29 |
| precio alineado al cierre | ≤ 5 días |
| MEP alineado al cierre | ≤ 5 días |

**Idempotencia** — verificada en dos niveles:

* re-ingesta canónica: `0 insertados · 4.648 reusados`, digest
  `9134ba5fc0849c34db66494c324f25b4` antes y después;
* salidas: los 5 archivos **byte-idénticos** entre dos corridas
  (`METR_5Y_DEMO.csv` md5 `b58079cd02750bf1db04ac8c7aa4f7af`).

**Reconstruible desde checkpoints**: la ingesta lleva
`input_checkpoint_id = c4-30657863676` y `run_id` por corrida. Se reconstruyó de
cero (drop + create + migraciones + ingesta + mercado + modelo) y da lo mismo.

---

## 13. Arquitectura — dónde está la frontera

Requisito: *METR CNV alimenta el mismo Financial Model que SEC; el Ratio Engine
consume Economic Facts, no conoce CNV.* Cómo se cumple:

1. **CNV entra por la misma puerta que IFRS y US-GAAP.** `ratio_defs.CONCEPTOS`
   ya mapeaba concepto económico → tags candidatos para dos taxonomías. Se
   agregó una tercera declarando `CONCEPTOS_CNV`. **No hay un motor de ratios
   CNV**; hay 23 tags más y 14 conceptos nuevos en el registry.
2. **Los tags CNV se apendan al final de cada cadena.** El orden es la regla de
   fallback, así que un filing us-gaap encuentra su tag antes de llegar a
   éstos. **Verificado, no supuesto**: 780 resoluciones SEC comparadas contra el
   literal original del archivo, **0 cambiadas**.
3. **El Financial Model es la frontera.** `d2_metr5y_model.py` lee
   `derived.fact` y `market.*`. El evaluador recibe un modelo y una expresión
   del registry: no lee `cnv_estados_*` ni tiene una sola rama por fuente.
4. **Ocurrencias.** Se ingesta desde la tabla con PK de ocurrencia; el canónico
   agrupa por `econ_key` y, si un `econ_key` tiene más de una ocurrencia,
   compara valores. Iguales → constancia. Distintos → `OCURRENCIAS_EN_CONFLICTO`
   y no se publica. Nunca se infiere supersesión por ordinal. `econ_key` no
   lleva `value` ni `es_nil`.

---

## 14. Hallazgos y correcciones del sprint

Cuatro defectos que encontró el propio demo y se corrigieron:

1. **La tasa impositiva efectiva usaba `abs()`.** Con eso, el **beneficio**
   fiscal de FY2023 (+45.386 M sobre 50.969 M) se leía como un cargo del 89 % y
   arrastraba el ROIC a 0,003. La CNV firma los gastos en negativo: el cargo es
   `−impuesto`. Corregido, ROIC 2023 pasa a 0,050.
2. **`es_nil` se trataba como dato ausente.** F-063 estableció que el guion de
   la CNV es un **cero declarado**. Con la semántica corregida, el
   `quick_ratio` de 2022–2025 pasa de no calculable a calculable.
3. **La ingesta perdía ocurrencias** porque el adapter leía `cnv_estados_norm`.
   Se hizo configurable la tabla origen (`CNV_TABLA`), con el default intacto
   para no alterar ningún gate anterior.
4. **La provenance seguía un solo nivel de derivación** y dejaba `deuda_neta`
   sin cadena. Ahora baja recursivamente: 5 eslabones rotos → 0.

---

## 15. Bloqueos y advertencias que quedan

| # | qué | impacto | estado |
|---|---|---|---|
| 1 | La CNV no publica **capex** | 7 ratios de la familia FCF no calculables en ningún año | **límite de la fuente**, no del software. Necesita otra fuente, fuera del alcance |
| 2 | `CNV_roe`/`CNV_roa` de FY2021–2022 no reconcilian | ninguno sobre los ratios del modelo | documentado como `ANOMALY` |
| 3 | 2 guardas de tests en rojo | ninguno funcional | `test_w13a_occurrence_audit.py` y `test_w13a2_multiissuer_audit.py::test_el_ratio_engine_no_fue_tocado` detectaron que este sprint modificó `ratio_defs.py`. **La guarda hizo su trabajo**: era de sprints de sólo-auditoría, y éste no lo es. No se tocaron para que pasen |
| 4 | 3 tests de `test_f038_traza_corrida.py` en rojo | ninguno | **previo a este sprint**: drift de datos en la DB `catalaxia` (601 filas contra 591 esperadas del lote M23). Este sprint nunca escribió ahí |
| 5 | `precios_diarios` de producción cubre 44 días | ninguno en el demo | se bajó la historia a `market.price` en la DB del demo. Producción no se tocó |

---

## 16. Gate

| # | criterio | resultado |
|---|---|---|
| 1 | 5 FY completos | ✅ 2021–2025 |
| 2 | cada FY como período independiente | ✅ `accn`, `econ_key` y `measurement_date` propios |
| 3 | ARS y USD MEP disponibles | ✅ 29 de 31 conceptos en ambas monedas |
| 4 | market histórico alineado por fecha | ✅ desfase 1–2 días, siempre etiquetado |
| 5 | EPS y EPS Growth calculados donde los inputs permiten | ✅ EPS los 5 años; growth 3, con motivo en los otros 2 |
| 6 | P/E, P/B, P/S, EV/EBITDA y demás | ✅ 24 ratios en los 5 años, 31 en 2023–2025 |
| 7 | ratios imposibles con motivo explícito | ✅ 44 celdas, cada una con motivo tipificado |
| 8 | sin mezcla de perímetros | ✅ control por ejercicio, 5/5 PASS |
| 9 | sin mezcla silenciosa de monedas/unidades | ✅ controles de moneda y escala, 10/10 PASS |
| 10 | provenance E2E | ✅ 289 celdas, 0 eslabones rotos |
| 11 | segunda ejecución idempotente | ✅ digest y salidas byte-idénticas |
| 12 | reconstruible desde checkpoints | ✅ reconstruido de cero, mismo resultado |

**`PASS_WITH_WARNINGS`** — los doce criterios se cumplen; las advertencias son
las cinco de §15 y ninguna bloquea.

---

## Artefactos

| archivo | contenido |
|---|---|
| `METR_5Y_DEMO.xlsx` | 5 filas × 137 columnas, agrupadas y coloreadas por bloque + 4 hojas |
| `METR_5Y_DEMO.csv` | lo mismo, plano |
| `METR_5Y_DEMO_PROVENANCE.csv` | 289 celdas con la cadena completa |
| `METR_5Y_DEMO_CHECKS.csv` | 55 controles |
| `METR_5Y_DEMO_RECONCILIACION.csv` | 35 comparaciones multi-método |
| `METR_5Y_DEMO_NO_CALCULABLES.csv` | 44 celdas con motivo tipificado |
| `METR_5Y_DEMO_CAGR.json` | CAGR 2021–2025 en ARS y USD |

Scripts (worktree `catalaxia-cnvmig`):
`scripts/engine/d1_metr5y_market.py` · `d2_metr5y_model.py` ·
`d3_metr5y_provenance.py`, más el registry en `scripts/engine/ratio_defs.py`.

Reproducción completa:

```bash
docker exec catalaxia-engine-dev psql -U catalaxia -d postgres \
  -c "DROP DATABASE IF EXISTS metr5y;" -c "CREATE DATABASE metr5y OWNER catalaxia;"
export ENGINE_DB_NAME=metr5y
python -c "from engine.config import load_settings; from engine.db import *; apply_migrations(get_admin_engine(load_settings()))"
CNV_TABLA=cnv_estados_v2 CNV_SQLITE=data/metr_f063.db \
  python scripts/engine/c4_cnv_adapter.py --cuit 30657863676 --persist
python scripts/engine/d1_metr5y_market.py
python scripts/engine/d2_metr5y_model.py
python scripts/engine/d3_metr5y_provenance.py
```
