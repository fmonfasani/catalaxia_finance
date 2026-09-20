# CATALAXIA — demo de cliente · 5 minutos

**Todo se ejecuta en vivo. Ninguna salida está preparada.**

> **Antes de empezar.** Verificar `load_settings()` → puerto **5433**. Es la
> superficie canónica. El screener y la API que corren en 5432 sirven las capas
> históricas del proyecto: **no se muestran en esta demo y no están cubiertos
> por lo que se promete acá.**

---

## 00:00 — El problema · 45 s

**Sin pantalla.**

> «Un analista toma un múltiplo de una terminal y su comité le hace tres
> preguntas que no puede responder.
>
> **¿De dónde salió?** La terminal da el resultado, no el camino. Reconstruirlo
> es trabajo manual de horas.
>
> **¿Qué período es?** "P/E 42" no dice si el denominador es el último ejercicio
> anual o doce meses móviles. Son números distintos y la etiqueta casi nunca lo
> aclara.
>
> **¿Y esta celda en cero?** Puede significar que la empresa no tiene deuda, o
> que no encontraron el dato. Se ven igual, y sólo una es un hecho.
>
> En emisores argentinos se agrava: dos taxonomías contables, dos monedas,
> ajuste por inflación, ADR con distinta relación de conversión, y tickers que
> chocan con papeles estadounidenses.
>
> Les voy a mostrar cómo se ven esas tres preguntas cuando tienen respuesta.»

---

## 00:45 — La empresa · 45 s

```bash
ratio_api --ticker AAPL
```

```json
{ "entity_key": "E01M13XBSM8ZWPXACZAG2H149JX",
  "nombre": "Apple Inc.",
  "cik": "0000320193",
  "ratios": [ ... 4 métricas ... ] }
```

> «Primero: **el ticker no es la identidad.** "AAPL" se resolvió siguiendo el
> instrumento hasta la entidad, y esa entidad tiene un CIK con una afirmación
> verificada detrás.
>
> Parece un detalle. No lo es: en este proyecto hubo un momento en que precios
> de Coursera aparecían como argentinos porque el ticker coincidía. Si un ticker
> resolviera a dos entidades, esto devuelve un error en lugar de elegir una.»

---

## 01:30 — Los fundamentals · 45 s

```bash
ratio_api --ticker AAPL --fundamental ingresos
```

```
tag_elegido       RevenueFromContractWithCustomerExcludingAssessedTax
value             416.161.000.000 USD    ·  FY 2025-09-27
cadena_evaluada   [Revenue, RevenueFromContractsWithCustomers,
                   RevenueFromContractWithCustomerExcludingAssessedTax,
                   RevenueFromContractWithCustomerIncludingAssessedTax, Revenues]
provenance_status COMPLETA
source_files      aapl-20250927.htm · aapl-20250927_htm.xml
```

> **«"Ingresos" no es una etiqueta: es un concepto con cinco etiquetas
> candidatas, en orden declarado.** Apple usa la tercera; un emisor argentino
> bajo IFRS usaría la primera.
>
> Y la celda dice **cuál se usó y cuáles se consultaron**. Eso permite verificar
> que la búsqueda fue exhaustiva y no que alguien buscó un solo nombre y se dio
> por vencido.»

---

## 02:15 — El ratio · 45 s

```bash
ratio_api --ticker AAPL --ratio ev_sales
```

```json
{ "canonical_id": "ev_sales", "value": 11.29879, "unit": "veces",
  "status": "CALCULADO", "period_end": "2025-09-27", "window": "FY",
  "currency": "USD", "formula_version": "ev_sales_v1",
  "provenance_status": "COMPLETA" }
```

> «Ningún número viaja solo. Van con él el período, **la ventana temporal**, la
> moneda y la versión exacta de la fórmula.
>
> Miren `window: FY`. Es el último ejercicio fiscal, no doce meses móviles. El
> estándar de la industria es TTM y nosotros todavía no lo hacemos. Podríamos
> publicar esto llamándolo TTM y nadie se daría cuenta. **Preferimos el número
> con la etiqueta correcta antes que la etiqueta que ustedes esperan.**
>
> Es la misma decisión que hace que las celdas vacías digan por qué.»

---

## 03:00 — La procedencia · 60 s

**El momento central de la demo. Pedir que elijan el número.**

```bash
ratio_api --ticker AAPL --ratio ev_sales --provenance
```

```
ingresos    RevenueFromContractWithCustomerExcludingAssessedTax  416.161.000.000 USD
deuda       LongTermDebt                                          90.678.000.000 USD
efectivo    CashAndCashEquivalentsAtCarryingValue                 35.934.000.000 USD
acciones    CommonStockSharesOutstanding                          14.773.260.000
precio      314,579987 USD · 2026-08-27

capitalización  = 314,579987 × 14.773.260.000     = 4.647.371.938.747,62
valor empresa   = + 90.678.000.000 − 35.934.000.000 = 4.702.115.938.747,62
EV/Sales        = 4.702.115.938.747,62 / 416.161.000.000 = 11,29879   ✓

accession   0000320193-25-000079
            sec.gov/Archives/edgar/data/320193/...
archivos    aapl-20250927.htm · aapl-20250927_htm.xml
SHA-256     e1076735f1c81bc9… · 274361a794f84b24…
```

> «Ésta es la cadena entera: valor → celda → insumos → hecho normalizado →
> punteros → hecho parseado → presentación ante la SEC → archivo con su hash.
>
> Ese *accession* es una URL pública. **Pueden abrirla ahora, sin nosotros.** El
> hash es del archivo tal como lo descargamos: si la SEC lo cambia, lo sabemos.
>
> Y hagamos la cuenta acá mismo con una calculadora.»

*(Hacerla. Toma quince segundos y es lo que se recuerda de la reunión.)*

**Si preguntan «¿cómo sé que no lo calcularon para la demo?»:**

```bash
homologacion_slice
```
```
25/25 valores reproducidos · peor desvío 1,59e-7 · 13/13 controles OK
```

> «Ese verificador no comparte una sola línea con el motor: habla directo con la
> base y reescribe las fórmulas desde el contrato. Si compartieran código,
> compartirían el error.»

---

## 04:00 — `NOT_CALCULABLE` · 30 s

**Los dos casos. Son distintos y ahí está el punto.**

```bash
ratio_api --ticker CEPU --ratio ev_sales
```
```
value: null · NOT_CALCULABLE
"sin fact para el concepto 'deuda_financiera' en 2025-12-31;
 candidatos consultados: [Borrowings, DebtLongtermAndShorttermCombinedAmount,
 LongTermDebt]"
```

```bash
ratio_api --ticker YPFD --ratio pe
```
```
value: null · NOT_CALCULABLE · provenance_status: COMPLETA
"REGLA: EPS = -2,11 <= 0 (ejercicio con pérdida). El P/E queda sin valor por
 decisión financiera, no por falta de dato: el EPS está y su procedencia también"
```

> **«No es cero y no es un error. Es una respuesta.**
>
> Un cero diría que Central Puerto no tiene deuda. Eso sería inventar un hecho.
> Lo que decimos es qué concepto faltó y qué candidatos buscamos.
>
> El segundo es distinto: la procedencia está **completa**. El EPS está, con su
> archivo. Y aun así no publicamos el múltiplo, porque YPF cerró con pérdida y
> un P/E negativo se lee como "barato" cuando significa lo contrario. Es la
> convención del IAMC.
>
> Del conjunto actual, siete de treinta y dos celdas están así. **Prefiero
> mostrarles siete huecos explicados que treinta y dos números de los que no
> puedo responder.»**

---

## 04:30 — El piloto · 30 s

```bash
ratio_api --universo --ratio eps
```

> «Ocho emisores, cuatro métricas: EPS, P/B, P/E y EV/Sales. Veinticinco celdas
> calculadas con procedencia completa y siete dichas con su motivo.
>
> **No es un reemplazo de TIKR ni de Bloomberg, y no lo vendemos así.** Ellos
> tienen cientos de métricas sobre miles de empresas. Nosotros cuatro sobre
> ocho, auditables.
>
> El piloto son cuatro semanas. Les entregamos el conjunto completo en un
> archivo, con toda la procedencia, y **la segunda semana la auditan ustedes
> solos** — que es exactamente lo que el producto dice que se puede hacer.
>
> Si al final aparece un límite que no les habíamos declarado, el piloto falla
> aunque todo lo demás funcione. Ése es el criterio que más nos importa.
>
> ¿Qué emisores les interesarían?»

---

## Guion de tiempos

| | | seg | acumulado |
|---|---|---:|---:|
| 00:00 | problema | 45 | 0:45 |
| 00:45 | empresa | 45 | 1:30 |
| 01:30 | fundamentals | 45 | 2:15 |
| 02:15 | ratio | 45 | 3:00 |
| 03:00 | **procedencia** | 60 | 4:00 |
| 04:00 | `NOT_CALCULABLE` | 30 | 4:30 |
| 04:30 | piloto | 30 | **5:00** |

**Si hay que recortar:** sacar 01:30 (fundamentals). **Nunca** recortar 03:00.

---

## Preguntas difíciles

**«¿Por qué sólo ocho empresas?»**
> El límite es la ingesta de estados contables, no el cálculo. Hay 513 entidades
> identificadas y 584 instrumentos con precio; con estados contables
> normalizados, ocho. Ampliar es trabajo de ingesta, con plazo estimable.

**«¿Por qué el P/E no es TTM?»**
> Porque el motor todavía no agrega trimestres. Publicamos FY con la etiqueta
> correcta. Es lo primero de la hoja de ruta, y hasta que exista, nuestro P/E no
> es comparable contra una fuente que publique TTM.

**«¿Y ROE, márgenes, deuda?»**
> Definidos en el contrato técnico, no implementados. Cuatro de ellos dependen
> de EBITDA, que no existe como etiqueta contable: hay doce candidatos de
> amortización con significados distintos y esa decisión está abierta. Preferimos
> no publicarlos antes de tomarla.

**«¿Esto reemplaza a TIKR?»**
> No, y sería el argumento equivocado. Son productos distintos: ellos cobertura,
> nosotros auditabilidad. Si necesitan cientos de métricas sobre miles de
> empresas, TIKR. Si necesitan justificar de dónde salió un múltiplo ante un
> comité, esto.

**«¿Cómo sé que los números son correctos?»**
> Recalculándolos. Están todos los insumos publicados. Y hay un verificador
> independiente que ya lo hace sobre las 25 celdas: 25/25, con un desvío de
> 1,59e-7, que es el redondeo a seis decimales.

**«Vi otro screener suyo con más empresas.»**
> Sí, y es una capa anterior del proyecto que sigue funcionando. **No tiene
> procedencia verificable** y puede discrepar de esto. No está cubierta por lo
> que les estoy ofreciendo, y prefiero decirlo antes de que lo descubran.
