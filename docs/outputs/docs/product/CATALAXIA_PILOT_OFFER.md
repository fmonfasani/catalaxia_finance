# CATALAXIA — propuesta de piloto

**Versión 1.0 · 2026-09-01**
Piloto acotado y verificable. Todo lo que sigue existe hoy; nada está proyectado.

---

## 1. Qué problema resuelve este piloto

Que el cliente pueda **tomar cualquier número de una pantalla y llegar al
documento que lo respalda**, sin pedírnoslo y sin confiar en nuestra palabra.

El piloto no busca demostrar cobertura. Busca demostrar que el mecanismo de
auditabilidad funciona sobre datos reales, y dejar al cliente en condiciones de
decidir si le sirve extenderlo a su universo.

---

## 2. Alcance

### Emisores — 8

| | emisor | mercado | moneda | métricas disponibles |
|---|---|---|---|---:|
| 1 | Apple Inc. | NASDAQ | USD | **4/4** |
| 2 | Microsoft Corp. | NASDAQ | USD | **4/4** |
| 3 | NVIDIA Corp. | NASDAQ | USD | **4/4** |
| 4 | YPF S.A. | NYSE / BYMA | USD | 3/4 |
| 5 | Transportadora de Gas del Sur | NYSE / BYMA | ARS | **4/4** |
| 6 | Central Puerto S.A. | NYSE / BYMA | ARS | 3/4 |
| 7 | Grupo Financiero Galicia | NYSE / BYMA | ARS | 2/4 |
| 8 | Macro Bank Inc. | NYSE / BYMA | ARS | 1/4 |

Los dos bancos entran **a propósito**, aunque su cobertura sea pobre: son el
caso donde el sistema muestra sus límites con honestidad en vez de rellenarlos.
Un piloto que sólo mostrara Apple y NVIDIA sería una demo, no una prueba.

### Métricas — 4

| métrica | ventana | cobertura |
|---|---|---|
| EPS (básico reportado) | `FY` | 8/8 |
| P/B (patrimonio de la controladora) | `PIT` | 6/8 |
| P/E | **`FY`** | 6/8 |
| EV/Sales | `FY` | 5/8 |

Más consulta directa de **21 conceptos contables** (ingresos, patrimonio,
efectivo, deuda, activo, pasivo, resultado neto, EPS, acciones y otros) con la
misma procedencia.

### Fuentes

| fuente | qué aporta |
|---|---|
| SEC EDGAR (XBRL) — 20-F y 10-K | estados contables, con hash por archivo |
| Mercado | precio de cierre diario por instrumento |
| Identity V1 | qué entidad es cada emisor y qué instrumento le pertenece |

Ninguna otra. Sin estimaciones, sin consenso, sin agregadores de terceros.

### Período

El **último ejercicio fiscal completo** de cada emisor:

```
Apple      2025-09-27      YPF, TGS, CEPU, GGAL, BMA   2025-12-31
Microsoft  2026-06-30      NVIDIA                       2026-01-25
```

Sin series históricas en este piloto. El modelo de datos las soporta —cada celda
lleva `period_end`, `valid_from` y `valid_to`—; lo que falta es reprocesar los
ejercicios anteriores, que es trabajo de ingesta.

---

## 3. Formato de entrega

### a) Conjunto de datos

Un archivo **JSON autocontenido** (≈130 KB) con las 32 celdas y su cadena de
procedencia completa: insumos, tags elegidos, cadenas de fallback consultadas,
identificadores de hechos de origen, números de presentación ante la SEC,
nombres de archivo y hashes SHA-256.

Regenerable con un comando, y verificable contra los archivos públicos de la SEC
sin intervención nuestra.

### b) Superficie de consulta

Interfaz de línea de comandos que devuelve JSON, con seis dimensiones:

```
--ticker / --cik     empresa
--ratio              métrica
--period             período
--window             ventana temporal
--currency           moneda
--status             estado
--provenance         cadena completa
--fundamental        concepto contable directo
```

### c) Documentación

- **Contrato de producto** — qué se entrega, qué no se promete, límites medidos
- **Registro de verificación** — la reproducción independiente de las 32 celdas

### d) Sesión de verificación

Una reunión donde **el cliente elige** empresa y número, y lo seguimos en vivo
hasta el archivo de la SEC. Sin salidas preparadas.

### Lo que NO incluye

- interfaz web o endpoint HTTP (especificados, no construidos — ver §7)
- integración con sistemas del cliente
- actualización automática programada
- las capas históricas del proyecto, que sirven otros números sin procedencia

---

## 4. Procedencia — qué se compromete

Para **toda celda calculada**, sin excepción:

1. cada insumo contable cita sus hechos de origen;
2. cada uno existe y es **del mismo emisor** — verificado, no declarado;
3. cada uno viene con el SHA-256 del archivo tal como se descargó;
4. el tag usado pertenece a la cadena de fallback declarada del concepto;
5. la celda dice qué fórmula y qué versión de fórmula la produjo.

**Estado actual: 25 de 25 celdas calculadas con procedencia completa.**

Y una verificación que no depende de nuestra palabra: un proceso que no comparte
código con el motor reproduce las 25 celdas desde los insumos guardados.

```
25/25 reproducidas · peor desvío relativo 1,59e-7 · tolerancia 1,0e-6
```

---

## 5. Duración

**Cuatro semanas.**

| semana | |
|---|---|
| 1 | entrega del conjunto de datos y la documentación; sesión de verificación |
| 2 | el cliente audita por su cuenta las celdas que elija |
| 3 | revisión conjunta: discrepancias, definiciones, qué faltó |
| 4 | informe de cierre y decisión sobre extender o no |

La semana 2 es la que importa: **es el cliente auditando solo**, que es
exactamente lo que el producto promete que se puede hacer.

---

## 6. Criterios de aceptación

Verificables, no opinables. El piloto se considera exitoso si:

| # | criterio | cómo se mide |
|---|---|---|
| **A1** | Toda celda calculada llega al documento original | el cliente elige N celdas al azar y las sigue hasta el archivo de la SEC; **objetivo 100 %** |
| **A2** | Los valores se reproducen a mano | el cliente recalcula desde los insumos publicados; **tolerancia 1e-6 relativo** |
| **A3** | Ninguna celda vacía sin explicación | las 7 `NOT_CALCULABLE` nombran el concepto faltante y la cadena consultada |
| **A4** | Ningún dato de un emisor aparece bajo otro | el cliente verifica que el emisor de cada archivo citado coincide con el de la celda |
| **A5** | El período nunca es ambiguo | toda celda declara `window`; ninguna dice `TTM` |
| **A6** | Reproducibilidad | recalcular el conjunto dos veces da los mismos valores y no duplica registros |
| **A7** | Los límites declarados son los reales | no aparece ninguna limitación que no esté en el contrato de producto |

**A7 es el criterio más importante.** Si durante el piloto surge un límite que
no habíamos declarado, el piloto falla aunque los otros seis pasen. La propuesta
de valor es la honestidad sobre lo que el sistema sabe y no sabe; una sorpresa
la invalida.

---

## 7. Qué haría falta para pasar de piloto a producto

En orden de dependencia, con lo que cada uno desbloquea:

| # | | desbloquea |
|---|---|---|
| 1 | **TTM** — agregación de cuatro trimestres | comparabilidad de todas las métricas de flujo contra cualquier fuente externa |
| 2 | **Ingesta a escala** | cobertura más allá de 8 emisores; hay 513 entidades identificadas y 584 instrumentos con precio, pero sólo 8 con estados contables normalizados |
| 3 | **Decisión sobre EBITDA** | EV/EBITDA, deuda/EBITDA, margen EBITDA — hoy bloqueadas porque EBITDA no existe como etiqueta contable y hay 12 candidatos de amortización con semánticas distintas |
| 4 | **Endpoint HTTP + interfaz** | consumo directo por el cliente sin intermediarios |
| 5 | **Series históricas** | evolución temporal; el modelo ya lo soporta, falta reprocesar |

Ninguno está prometido en este piloto.

---

## 8. Estructura de pricing — para discutir

**Sin precio definitivo.** No hay evidencia de mercado suficiente para fijarlo, y
ponerle un número a un piloto de ocho empresas sería inventar una referencia.

Tres estructuras posibles, para conversar:

**a) Piloto pago a costo simbólico, acreditable.** El cliente paga un monto
acotado por las cuatro semanas, que se descuenta íntegro si contrata. Sirve para
medir compromiso real sin que el precio sea la conversación.

**b) Piloto sin cargo, con compromiso de tiempo.** El cliente no paga; se
compromete a las horas de auditoría de la semana 2 y a una devolución escrita.
Lo que obtenemos es la validación del enfoque.

**c) Precio por cobertura, después del piloto.** Por emisor y por métrica
mantenida, con la ingesta como el componente real de costo. Requiere saber qué
universo necesita el cliente.

**Recomendación:** **(b)** para los primeros dos o tres clientes. Con ocho
emisores y cuatro métricas, lo que necesitamos no es facturación sino saber si
la auditabilidad es un diferencial por el que alguien pagaría — y eso se
aprende de la devolución, no del cobro.

---

## 9. Lo que este piloto no es

- No es una prueba de cobertura. Son ocho empresas.
- No es una comparación contra TIKR, Bloomberg o cualquier otro proveedor:
  las definiciones y las ventanas difieren, y esas diferencias son reales.
- No es una integración. No toca los sistemas del cliente.
- No es asesoramiento de inversión.
- No incluye los números de las capas históricas del proyecto, que no tienen
  procedencia verificable.

---

*Referencias: `CATALAXIA_PRODUCT_CONTRACT.md` (compromiso técnico),
`CATALAXIA_CUSTOMER_DEMO.md` (guion de la sesión).*
