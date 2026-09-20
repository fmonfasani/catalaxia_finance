# CATALAXIA

### Ratios financieros que se pueden auditar hasta el documento original

---

## PROBLEMA

Un analista toma un múltiplo de una terminal y no puede responder tres preguntas
que su comité sí le va a hacer:

**¿De dónde salió este número?** Las terminales entregan el resultado, no el
camino. Reconstruirlo es una tarea manual de horas por empresa.

**¿Qué período representa?** «P/E 42» no dice si el denominador es el último
ejercicio anual o doce meses móviles. Son números distintos, y la etiqueta rara
vez lo aclara.

**¿Por qué esta celda está vacía —o peor, en cero?** Un cero puede significar
«la empresa no tiene deuda» o «no encontramos el dato». Los dos casos se ven
igual, y sólo uno es un hecho.

En emisores argentinos el problema se agrava: dos taxonomías contables, dos
monedas, ajuste por inflación, ADR con distinta relación de conversión, y
tickers que colisionan con papeles estadounidenses.

---

## SOLUCIÓN

Catalaxia entrega cada ratio como una **celda auditable**: el valor viene con su
período, su ventana temporal, su moneda, la versión exacta de la fórmula, y una
cadena de procedencia que llega hasta el archivo que el emisor presentó ante la
SEC, con su hash SHA-256.

Y cuando un número no se puede afirmar, **lo dice con el motivo** en lugar de
rellenarlo con un cero.

---

## CÓMO FUNCIONA

```
SEC EDGAR (XBRL)  →  descarga con hash  →  parseo  →  normalización
                                                          ↓
Identity: qué entidad es, qué instrumento le pertenece  →  motor de ratios
                                                          ↓
Mercado: precio de cierre por instrumento             →  celda + procedencia
```

Tres decisiones de diseño que sostienen todo lo demás:

**La identidad es opaca, no un ticker.** Cada emisor tiene una clave interna
respaldada por una afirmación con evidencia. Un ticker nunca se usa para unir
datos: `TGS` en Nueva York y `TGSU2` en Buenos Aires son el mismo emisor, y
`CEPU` puede ser dos instrumentos distintos.

**Cada insumo debe demostrar que le pertenece al emisor.** Antes de entrar a un
cálculo, todo dato prueba —por su propia procedencia— que viene del mismo
emisor, del mismo filing y del mismo concepto. La regla no menciona ningún
nombre ni ningún ticker.

**Una métrica no existe sin su ventana temporal.** El período es parte de la
identidad del dato, no una etiqueta que se agrega después.

---

## EJEMPLO

```
Apple Inc. · EV/Sales = 11,29879 veces · FY 2025-09-27 · USD · ev_sales_v1
```

Abriendo la celda:

```
ingresos    RevenueFromContractWithCustomerExcludingAssessedTax   416.161.000.000 USD
deuda       LongTermDebt                                           90.678.000.000 USD
efectivo    CashAndCashEquivalentsAtCarryingValue                  35.934.000.000 USD
acciones    CommonStockSharesOutstanding                           14.773.260.000
precio      314,579987 USD · 2026-08-27

capitalización = 314,579987 × 14.773.260.000    = 4.647.371.938.747,62
valor empresa  = + 90.678.000.000 − 35.934.000.000 = 4.702.115.938.747,62
EV/Sales       = 4.702.115.938.747,62 / 416.161.000.000 = 11,29879
```

Y hasta el papel:

```
accession   0000320193-25-000079   (sec.gov/Archives/edgar/data/320193/...)
archivos    aapl-20250927.htm · aapl-20250927_htm.xml
SHA-256     e1076735f1c81bc9… · 274361a794f84b24…
```

Y el caso opuesto, YPF:

```
P/E = —   NOT_CALCULABLE   provenance COMPLETA
"REGLA: EPS = -2,11 <= 0 (ejercicio con pérdida). El P/E queda sin valor por
 decisión financiera, no por falta de dato: el EPS está y su procedencia también"
```

---

## DIFERENCIAL

**Procedencia hasta el documento, no hasta el proveedor.** No decimos «fuente:
SEC». Damos el archivo, el hash y el número de presentación. El cliente puede
verificar sin pedirnos nada.

**El período es explícito y forma parte del dato.** Nuestro P/E dice `FY`
porque es FY. No lo llamamos TTM.

**Los huecos se declaran.** Siete de las 32 celdas del conjunto actual son
`NOT_CALCULABLE`, cada una con su motivo: qué concepto faltó y qué candidatos se
consultaron. Ningún cero inventado.

**Aislamiento entre emisores, demostrado.** Encontramos y cerramos un defecto
por el que datos de una empresa podían aparecer bajo otra. Hay una prueba que le
quita la protección al sistema y verifica que la contaminación vuelve: si no
volviera, la protección la estaría dando otra cosa.

**Verificación independiente.** Un proceso que no comparte código con el motor
reproduce las 25 celdas calculadas desde los insumos guardados: **25/25, con un
desvío máximo de 1,59e-7** —el redondeo a seis decimales.

---

## PILOTO

**8 emisores · 4 métricas · 32 celdas · procedencia completa en las 25 calculadas.**

Apple, Microsoft, NVIDIA, YPF, TGS, Central Puerto, Grupo Galicia, Banco Macro.
EPS, P/B, P/E (FY) y EV/Sales.

Entrega: un archivo JSON autocontenido con las 32 celdas y su cadena de
procedencia, regenerable con un comando, más una sesión de verificación donde el
cliente elige cualquier número y lo seguimos hasta el archivo de la SEC.

Detalle en `CATALAXIA_PILOT_OFFER.md`.

---

## LIMITACIONES

Escritas acá para que nadie las asuma por omisión:

- **Ocho emisores**, no quinientos. El límite es la ingesta de estados
  contables, no el cálculo.
- **Cuatro métricas.** Faltan ROE, ROIC, márgenes, deuda/EBITDA, liquidez, FCF
  y dividendos.
- **No hay TTM.** Todas las métricas de flujo son del último ejercicio anual.
- **Ninguna métrica que dependa de EBITDA**, porque EBITDA no existe como
  etiqueta contable: hay que construirlo, y esa decisión sigue abierta.
- **Los bancos quedan con cobertura pobre** (2 de 4 métricas, y 1 de 4 en un
  caso): no publican «ingresos» bajo ninguna de las etiquetas estándar. Es del
  modelo contable del sector.
- **Sin series históricas**: el último ejercicio de cada emisor.
- **Sin interfaz web ni API HTTP** para esta superficie todavía: hoy es línea de
  comandos y entrega en archivo.
- **Precios de cierre diario**, no en tiempo real.

Catalaxia **no** es un reemplazo de TIKR ni de Bloomberg, no tiene cobertura
completa, no entrega datos en tiempo real y no publica estimaciones. Es una
vertical delgada donde cada número es auditable.

---

## NEXT STEP

Una demo de cinco minutos donde el cliente elige la empresa y el número, y lo
seguimos hasta el archivo original. Si el enfoque le sirve, definimos el
alcance del piloto sobre sus emisores de interés — sabiendo que ampliar la
cobertura es trabajo de ingesta, con plazo estimable.

*Documento de referencia técnica: `CATALAXIA_PRODUCT_CONTRACT.md`.*
