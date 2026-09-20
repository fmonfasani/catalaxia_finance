# RATIOS_MULTIPATH — cuántos caminos independientes hay realmente

**Fecha:** 2026-08-31 · Evidencia: `multipath.json`, `scripts/engine/ratios_multipath.py`

Regla del ciclo: **dos caminos no cuentan como independientes si dependen del
mismo dato subyacente sin documentarlo.** Este documento aplica esa regla a cada
ratio prioritario y dice, para cada par de caminos, qué comparten.

---

## 1. Resumen

| ratio | caminos posibles | independientes de verdad | equivalentes | dónde dejan de serlo |
|---|---:|---:|---|---|
| **EPS** | 2 | **2** | sí (9/9, dif ≤ 0.72 %) | si cambia el conteo de acciones usado |
| **P/E** | 2 | **1.5** | sí (dif 0.36 %) | comparten precio y resultado neto |
| **ROE** | 2 | 1 | — | el segundo camino usa el mismo `ProfitLoss` |
| **market cap** | 3 | 1 | **no** | tres conteos de acciones distintos |
| **margen neto** | 1 | 1 | — | no hay segundo camino con los facts actuales |

---

## 2. EPS — el único caso con dos caminos genuinamente independientes

| camino | fórmula | origen |
|---|---|---|
| **A** | tag `BasicEarningsLossPerShare` (y sus dos nombres previos) | **declarado** por el emisor en el XBRL |
| **B** | `ProfitLoss / WeightedAverageShares` | **derivado** de otros dos facts |

Son independientes porque A es un hecho publicado y B se construye con dos hechos
distintos. Que coincidan es información real, no una tautología.

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

**Qué prueba:** que `WeightedAverageShares` es efectivamente el denominador del
EPS publicado, que `ProfitLossAttributableToOwnersOfParent` es el numerador que
usa el emisor, y que los **tres nombres distintos** del tag de EPS designan la
misma magnitud. Nada de eso se dedujo del nombre.

**Dónde dejarían de coincidir:** si se sustituyera `WeightedAverageShares` por
`EntityCommonStockSharesOutstanding`, la diferencia pasaría de 0.72 % a ~0.35 %
sistemático en YPF — y a mucho más en un emisor que emita durante el ejercicio.

**Residuo de 0.72 % en 2021:** el EPS publicado viene redondeado a dos decimales
(0.65) y el derivado no (0.6547). Sobre un valor chico, el redondeo pesa. No es
discrepancia de datos.

---

## 3. P/E — dos caminos, media independencia

| camino | fórmula | insumos |
|---|---|---|
| **A** | `precio / EPS_reportado` | precio, EPS |
| **B** | `(precio × acciones) / ProfitLoss` | precio, acciones, resultado neto |

```
ejercicio 2024:  A = 8.43        B = 8.46      dif 0.36 %
ejercicio 2022:  A = 8.90        B = 8.91      dif 0.11 %
ejercicio 2025:  A = NO_CALCULABLE   B = NO_CALCULABLE   (ambos, misma causa)
ejercicio 2023:  A = NO_CALCULABLE   B = NO_CALCULABLE   (ambos, misma causa)
```

### Lo que comparten

- **el precio** — idéntico en los dos;
- **el resultado neto** — B lo usa directo, A lo usa a través del EPS, que se
  calcula con él (probado en §2).

Lo único no compartido es el conteo de acciones. **Por eso la concordancia del
0.36 % confirma poco:** verifica que el conteo de acciones es consistente, no que
el P/E sea correcto. Si `ProfitLoss` estuviera mal extraído, **los dos caminos
darían el mismo número equivocado**.

**La demostración más clara** es el ejercicio 2025: ambos caminos devuelven
`NOT_CALCULABLE` simultáneamente, por el mismo motivo (resultado negativo). Dos
caminos que fallan juntos ante la misma causa no son dos evidencias.

### Un tercer camino que sí sería independiente

`P/E = precio / (ProfitLoss / WeightedAverageShares)` no agrega nada: es B con
otro conteo. Un camino realmente independiente exigiría un EPS de **otra fuente**
(CNV, o el EPS que publica el mercado), y hoy no está ingerido.

### El factor que hay que mirar antes de dividir

El precio de `MKT:84` es el **ADR**, el EPS es **por acción subyacente**. Si el
ratio del ADR no fuera 1:1, dividir directo daría un P/E mal por ese factor.

```
identity_v1.instrument MKT:84  ratio_underlying = 1.00
20-F 2025 (0001193125-26-126363)  "Class D share"     ratio 1
```

Dos fuentes coinciden. **No es así para el resto de la muestra**: CEPU 10:1,
GGAL 10:1, TGS 5:1. El cálculo divide por `ratio_underlying`; si faltara, el
resultado quedaría `NOT_CALCULABLE` en vez de dividir asumiendo 1.

---

## 4. Market cap — tres caminos que NO son equivalentes

| conteo | 2025 | market cap a 50.48 USD |
|---|---:|---:|
| `WeightedAverageShares` | 391.952.016 | 19.784 e9 |
| `EntityCommonStockSharesOutstanding` | 393.312.793 | 19.852 e9 |
| `NumberOfSharesOutstanding` | (9 ejercicios) | — |

**No son tres caminos al mismo número: son tres números distintos.** El promedio
ponderado no es un stock y no debe usarse para market cap. El tag `dei` lleva la
fecha de **carátula del filing**, que es posterior al cierre del ejercicio.

**Regla adoptada:** market cap usa un conteo a fecha, nunca el promedio
ponderado. El promedio ponderado se reserva para el EPS.

---

## 5. ROE — el segundo camino es aparente

| camino | fórmula |
|---|---|
| A | `ProfitLossAttributableToOwnersOfParent / Equity` |
| B | `EPS × acciones / Equity` |

B se expande a `(ProfitLoss/WeightedAverageShares) × acciones / Equity`, que es A
multiplicado por un cociente de conteos ≈ 1. **No es un camino independiente: es
A con pasos de más.** Se documenta para que nadie lo cuente como validación
cruzada.

---

## 6. Conclusión

De los ratios prioritarios, **sólo el EPS tiene hoy dos caminos genuinamente
independientes**, y los dos coinciden en 9/9 ejercicios. El P/E tiene dos
caminos que comparten dos de tres insumos. El market cap tiene tres fórmulas
que dan tres resultados distintos y exigen elegir, no promediar.

La consecuencia práctica: **la validación cruzada del P/E no sustituye a
verificar `ProfitLoss` contra el estado contable**. Ese control queda pendiente y
no se cuenta como hecho.
