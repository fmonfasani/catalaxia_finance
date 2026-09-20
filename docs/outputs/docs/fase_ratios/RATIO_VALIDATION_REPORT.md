# RATIO_VALIDATION_REPORT — Fase F: comparación cálculo propio vs. dato publicado vs. cálculo alternativo

**Fecha:** 2026-09-01 · **Rol:** Financial Data Architect + Product Validation Auditor
**Universo:** YPFD, CEPU, TGSU2, GGAL, BMA, AAPL, MSFT, NVDA (muestra deliberada del encargo)
**TIKR/benchmarks externos:** no se usan como autoridad primaria (regla del encargo). Ver §5.

Este reporte responde la Fase F: ¿el cálculo propio coincide con el dato que
el propio emisor publicó, con un cálculo alternativo, y consigo mismo entre
lecturas? Cada comparación cita su evidencia, no una afirmación.

---

## 0. Resumen

| verificación | método | resultado |
|---|---|---|
| cálculo propio vs. dato publicado por el emisor | EPS reportado vs. `resultado_neto/acciones_promedio` | **8/8 empresas, dif. máx. 0.12%** |
| identidad contable independiente del ratio | `Activo = Pasivo + Patrimonio` | **8/8 empresas, desvío 0.0000%** |
| identidad contable independiente del ratio | `Ingresos − Costo de ventas = Resultado bruto` | **6/6 empresas con los 3 conceptos, desvío 0.00%** |
| cálculo alternativo (segundo camino) | P/E: `precio/EPS` vs. `(precio×acciones)/resultado_neto` | 2/2 ejercicios comparables, dif. ≤ 0.36% — **camino parcialmente independiente, ver §2** |
| reproducibilidad por un auditor que no comparte código | recalcular cada ratio con Decimal, sin importar `engine.*` | **274/274 reproducidos, 0 divergentes** |
| consistencia entre lecturas (determinismo) | hash de todos los insumos, dos lecturas consecutivas | **idéntico** |
| unidad y período | mezcla de monedas, cruce de filings, comparativos colados | **0 casos en 274 ratios** |
| benchmark externo (secundario) | investing.com | **no disponible para esta muestra** — ver §5 |

---

## 1. Cálculo propio vs. dato publicado por el emisor

El único caso donde el sistema tiene **dos fuentes genuinamente distintas**
para el mismo número es el EPS: el tag que el emisor publica directamente
(`eps_basico`) contra `resultado_neto / acciones_promedio`, reconstruido de
dos facts separados. Verificado con dos scripts independientes:

**`ratios_multipath.py`** (YPF, 9 ejercicios 2017–2025):

```
periodo      reportado      derivado    dif %   veredicto
2025-12-31       -2.11       -2.1074    0.12%   COINCIDE
2024-12-31        5.99        5.9884    0.03%   COINCIDE
2023-12-31       -3.35       -3.3493    0.02%   COINCIDE
2022-12-31        5.67        5.6722    0.04%   COINCIDE
2021-12-31        0.65        0.6547    0.72%   COINCIDE
2020-12-31     -177.42     -177.4246    0.00%   COINCIDE
2019-12-31      -86.85      -86.8488    0.00%   COINCIDE
2018-12-31       98.43       98.3457    0.09%   COINCIDE
2017-12-31       31.43       31.4295    0.00%   COINCIDE
```

**`audit_provenance_ratios.py`** (las 8 empresas de la muestra, último
ejercicio, script independiente — no importa `ratio_defs` ni ningún módulo
del implementador, declara su propia tabla de tags candidatos):

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

**8/8 empresas, en ambas taxonomías (`ifrs-full` y `us-gaap`), dif. máxima
0.12%.** El residuo no es discrepancia de datos: es el redondeo del EPS
publicado a 2 decimales sobre un cálculo que trae más precisión. Esto
verifica de un solo golpe: (a) que `acciones_promedio` es efectivamente el
denominador que el emisor usó, (b) que el numerador (`resultado_neto`) es el
que corresponde, y (c) que los cinco nombres distintos de tag de EPS
(`BasicEarningsLossPerShare`, `BasicAndDilutedEarningsPerShare`,
`BasicAndDilutedEarningsLossPerShare`, `EarningsPerShareBasic`,
`IncomeLossFromContinuingOperationsPerBasicShare`) designan la misma
magnitud en las dos taxonomías.

## 2. Cálculo alternativo — P/E, y por qué su independencia es solo parcial

`RATIOS_MULTIPATH.md` documenta esto en detalle; resumen:

| camino | fórmula | comparte con el otro camino |
|---|---|---|
| A | `precio / EPS_reportado` | — |
| B | `(precio × acciones_a_fecha) / resultado_neto` | precio, y el resultado neto (a través del EPS, verificado en §1) |

Coinciden dentro del 0.36% en los dos ejercicios comparables de YPF (2024,
2022). **Esto no es una segunda evidencia fuerte**: A y B comparten dos de
sus tres insumos, así que si `resultado_neto` estuviera mal extraído, los
dos caminos darían el mismo número equivocado. La prueba más honesta es que
**fallan juntos** en 2023 y 2025 (resultado neto negativo → ambos
NOT_CALCULABLE por la misma causa). Lo único que la coincidencia confirma de
verdad es que el conteo de acciones usado en B es consistente con el EPS de
A — no que el resultado neto subyacente sea correcto. Esa verificación
(resultado neto vs. estado contable) es la de §1, no la de este apartado.

## 3. Identidades contables — la verificación que SÍ es independiente

`audit_provenance_ratios.py` no compara nombres de tags: reconstruye
identidades contables que deben cumplirse **sea cual sea la taxonomía**, con
un script que declara su propia tabla de conceptos por separado (no importa
`ratio_defs.py`).

**Activo = Pasivo + Patrimonio**, las 8 empresas, ambas taxonomías:

```
empresa taxonomia     A = P + PN     desvio
AAPL    us-gaap       OK            0.0000%
BMA     ifrs-full     OK            0.0000%
CEPU    ifrs-full     OK            0.0000%
GGAL    ifrs-full     OK            0.0000%
MSFT    us-gaap       OK            0.0000%
NVDA    us-gaap       OK            0.0000%
TGSU2   ifrs-full     OK            0.0000%
YPFD    IFRS+US-GAAP  OK            0.0000%
```

**Ingresos − Costo de ventas = Resultado bruto**, en las 6 empresas que
publican los tres conceptos (BMA y GGAL son bancos, no tienen "costo de
ventas" — ausencia correcta, no falla): desvío 0.00% en las 6.

Estas dos identidades no dependen de que el auditor haya adivinado el mismo
tag que el implementador: si el implementador hubiera elegido
`AssetsNoncurrent` en vez de `Assets`, o `NetIncomeLoss` en vez de
`ProfitLossAttributableToOwnersOfParent`, la identidad se habría roto. Que
cierre en 8/8 es evidencia semántica, no léxica.

## 4. Reproducibilidad y consistencia interna

`ratios_auditoria.py` — auditor que habla con PostgreSQL por `psql`, usa
`Decimal` en vez de `float`, y no importa ningún módulo del implementador:

| control | resultado |
|---|---|
| A1/A2 · cada ratio recalculado desde `derived.fact` coincide con el publicado | **274/274, 0 divergentes** |
| B1 · todo insumo existe en `derived.fact` con ese valor exacto | 0 sin respaldo |
| C1/C2 · toda accession citada existe; todo fact derivado tiene accession y `source_fact_ids` | 0 huérfanos |
| D1 · ningún ratio mezcla monedas | 0 mezclados |
| D2 · numerador y denominador del mismo filing | 0 cruces |
| D3 · la regla de período descarta comparativos | confirmado (9 principales de 27 filas de `Assets` en YPF) |
| E1/E2/E3 · NULL y NO_CALCULABLE siempre con motivo; P/E con EPS≤0 nunca negativo | 0 sin motivo |
| G1 · el conjunto de insumos es idéntico entre dos lecturas consecutivas | hash idéntico |

**Nota de proceso:** dos controles de este mismo auditor (H1, H2) quedaron
en FALLA en la primera corrida de este ciclo — no porque algo se hubiera
roto, sino porque comparaban contra un número (`== 1`) congelado de cuando
la muestra tenía una sola cadena completa. Se corrigieron para comparar
contra lo que `e2e_producto.py` declara en cada corrida, no contra un
literal. Ver §6.

## 5. Benchmark externo — por qué no se usa en este reporte

El repo tiene un cruce previo contra investing.com
(`comparacion_edgar_investing_NUEVA.csv`, de un ciclo de trabajo anterior a
este motor), pero **cubre un universo distinto** (GS, IBN, INFY y otros) y
**no incluye ninguna de las 8 empresas de esta muestra deliberada**
(verificado: 0 coincidencias). Forzar una comparación con datos de otras
empresas sería fabricar evidencia. Este reporte se apoya en las
verificaciones internas de §1–§4, que son más fuertes que un benchmark
externo de todos modos: comparan contra el **propio filing** del emisor,
no contra un tercero que puede tener su propio criterio TTM/FY. Si se
incorpora investing.com o TIKR para esta muestra en un ciclo futuro, debe
entrar como lo pide el encargo: **benchmark secundario**, nunca autoridad.

## 6. Lo que este ciclo corrigió para poder escribir este reporte

Dos defectos se encontraron *validando* la Fase D/F, no antes:

- **F-056** — `ratios_inventario.py` y `e2e_producto.py` declaraban sus
  propias listas de tags, solo-IFRS, en vez de usar el fallback de
  `ratio_defs.py`. Efecto: 0/9 ratios en AAPL/MSFT/NVDA pese a tener los
  facts completos. Corregido: ambos scripts ahora construyen su tabla de
  fundamentales desde `ratio_defs.CONCEPTOS`/`RATIOS`.
- **F-057** — el parser `sql()` de los dos auditores independientes perdía
  el último campo de la última fila cuando venía NULL (bug de
  `str.strip()` sobre el separador `\x1f`, que Python trata como
  whitespace). Corregido en los dos scripts.

Detalle completo en `docs/review/F056_FINDING.md` y `F057_FINDING.md`.
