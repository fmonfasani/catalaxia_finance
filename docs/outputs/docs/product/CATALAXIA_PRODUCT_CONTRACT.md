# CATALAXIA — contrato de producto

**Versión 1.0 · 2026-09-01 · vertical slice**
Este documento es el compromiso: lo que Catalaxia entrega, con qué respaldo, y qué **no** promete.

---

## 1. Qué ofrece Catalaxia

Ratios financieros de emisores argentinos y estadounidenses **con procedencia
verificable hasta el documento original**.

Para cada número entregado, el cliente puede llegar —sin salir del sistema y sin
pedirnos nada— al archivo que el emisor presentó ante la SEC, con su hash
SHA-256.

Lo que se entrega no es «un ratio». Es una **celda** con doce campos:

```json
{
  "canonical_id": "ev_sales",
  "value": 11.29879,
  "unit": "veces",
  "status": "CALCULADO",
  "period_end": "2025-09-27",
  "window": "FY",
  "denominator_basis": "n/a",
  "currency": "USD",
  "formula_version": "ev_sales_v1",
  "formula": "(market_cap + deuda_financiera - efectivo) / ingresos",
  "provenance_status": "COMPLETA",
  "motivo": null
}
```

Un consumidor que muestre sólo `value` está descartando la mitad del producto.
El mismo `11,30` con otra ventana temporal es **otro hecho**, no el mismo dato
actualizado.

---

## 2. Qué fuentes utiliza

| fuente | qué aporta | cómo entra |
|---|---|---|
| **SEC EDGAR** (XBRL) | estados contables: 20-F y 10-K | descarga con hash por archivo → parseo → normalización |
| **Mercado** | precio de cierre diario por instrumento | `market_price_daily` |
| **Identity V1** | qué entidad es cada emisor, y qué instrumento le pertenece | `entity_key` opaco + *assertions* con evidencia |

Todo lo entregado sale de esas tres. **No hay estimaciones, no hay consenso de
analistas, no hay datos de terceros agregadores.**

### Lo que queda explícitamente fuera

Catalaxia arrastra tres capas históricas —un pipeline SQLite, un screener
publicado y una API v2— que sirven otros números. **No forman parte de este
contrato.** No tienen procedencia verificable y pueden discrepar de lo que acá
se entrega. Ver §8.

---

## 3. Qué métricas están disponibles

Cuatro. No más.

| métrica | fórmula | unidad | ventana | versión |
|---|---|---|---|---|
| **EPS** | EPS básico reportado por el emisor | moneda/acción | `FY` | `eps_v1` |
| **P/B** | (precio ÷ ratio ADR) ÷ (patrimonio de la controladora ÷ acciones) | veces | `PIT` | `pb_v1` |
| **P/E** | (precio ÷ ratio ADR) ÷ EPS | veces | **`FY`** | `pe_v1` |
| **EV/Sales** | (capitalización + deuda financiera − efectivo) ÷ ingresos | veces | `FY` | `ev_sales_v1` |

Además, consulta directa de **conceptos contables** (ingresos, patrimonio,
efectivo, deuda, activo, pasivo, resultado neto y otros 14) con la misma
procedencia.

### Sobre las decisiones de definición

Donde una métrica admite más de una definición válida, la elegida está
declarada y queda en la procedencia de cada celda:

- **P/B usa el patrimonio de la controladora**, no el total. El accionista
  compra esa participación; incluir minoritarios abarata el múltiplo de
  holdings y bancos sin que el comprador tenga derecho sobre esa parte.
- **P/E con EPS ≤ 0 no se publica.** Un P/E negativo se lee como «barato»
  cuando significa lo contrario. Es la convención del IAMC.
- **«Ingresos» no es un tag: es un concepto** con cinco tags candidatos en
  orden declarado. La celda dice cuál se usó y cuáles se consultaron.

---

## 4. Qué períodos están disponibles

| ventana | significa | disponible |
|---|---|---|
| `FY` | último ejercicio fiscal completo | **sí** |
| `PIT` | saldo de balance a la fecha de cierre | **sí** |
| `TTM` | doce meses móviles | **no** |
| `Q`, `YTD` | trimestre, acumulado | **no** |

**El P/E de Catalaxia es FY, no TTM**, y la celda lo declara en `window`. El
estándar de la industria es TTM. Mientras el motor no sepa agregar cuatro
trimestres, se publica FY con la etiqueta correcta en lugar de TTM con la
etiqueta equivocada.

Se entrega **el último ejercicio de cada emisor**. No hay series históricas
todavía, aunque el modelo de datos las soporta: cada celda lleva `period_end` y
`valid_from`/`valid_to`.

---

## 5. Qué significa *provenance*

`provenance_status: COMPLETA` significa que **cada insumo contable** de esa
celda cumple, verificado en el momento de servir:

1. cita al menos un identificador de hecho de origen;
2. cada uno existe en la capa parseada;
3. la fila apuntada es **del mismo emisor** — no de otro;
4. viene con el SHA-256 del archivo tal como se descargó de la SEC;
5. el tag usado pertenece a la cadena de fallback declarada del concepto.

`PARCIAL`: algún insumo no cumple alguna. `AUSENTE`: la celda no cita ningún
insumo contable — sólo ocurre en celdas `NOT_CALCULABLE` que se cortaron antes
de resolver el primero.

**Invariante medido: las 25 celdas `CALCULADO` del universo tienen `COMPLETA`.
Ninguna excepción.**

### La cadena, entera

```
valor mostrado → celda → insumos → hecho normalizado → punteros de origen
              → hecho parseado → filing (accession SEC) → archivo + SHA-256
```

El precio y los valores derivados (capitalización, valor de empresa) no llevan
cadena XBRL porque no salen de un filing. Están declarados aparte, con su
instrumento y fecha de cotización, y no cuentan para el estado.

---

## 6. Qué significa `NOT_CALCULABLE`

**No es cero. No es un error.** Es una respuesta con motivo.

Un cero afirmaría un hecho falso («esta empresa no tiene deuda»). Un error diría
que el sistema se rompió. `NOT_CALCULABLE` dice: *no puedo afirmar este número,
y acá está por qué.*

Es estructural, no una convención: la base impide que exista una celda
`NOT_CALCULABLE` con valor **o sin motivo**.

### Tres familias, distinguibles por el motivo

**a) Falta un dato.**
```
"sin fact para el concepto 'deuda_financiera' en 2025-12-31;
 candidatos consultados: ['Borrowings',
 'DebtLongtermAndShorttermCombinedAmount', 'LongTermDebt']"
```
Nombra el concepto **y la cadena completa consultada**: el cliente puede
verificar que la búsqueda fue exhaustiva y no un descuido.

**b) Una regla financiera lo impide.**
```
"REGLA: EPS = -2.11 <= 0 (ejercicio con perdida). El P/E queda sin valor por
 decision financiera, no por falta de dato: el EPS esta y su provenance tambien"
```
Acá `provenance_status` sigue siendo `COMPLETA`. El dato está; lo que no se
publica es el múltiplo.

**c) La identidad no alcanza.**
```
"la entidad no tiene instrumento ligado: atribuirle un precio seria un join
 por ticker"
```
Hay precios con ese ticker. Lo que no hay es **prueba** de que esa especie
cotizante pertenezca a esa entidad.

---

## 7. Cobertura conocida

**Ocho emisores. Cuatro métricas. 32 celdas: 25 calculadas, 7 no calculables con
motivo.**

| emisor | período | moneda | EPS | P/B | P/E | EV/Sales |
|---|---|---|---:|---:|---:|---:|
| Apple Inc. | 2025-09-27 | USD | 7,49 | 63,03 | 42,00 | 11,30 |
| Microsoft Corp. | 2026-06-30 | USD | 18,00 | 8,48 | 28,06 | 11,36 |
| NVIDIA Corp. | 2026-01-25 | USD | 4,93 | 35,23 | 46,24 | 25,65 |
| YPF S.A. | 2025-12-31 | USD | −2,11 | 1,84 | — | 1,60 |
| Transportadora de Gas del Sur | 2025-12-31 | ARS | 559,09 | 2,19 | 16,29 | 4,51 |
| Central Puerto S.A. | 2025-12-31 | ARS | 230,61 | 1,29 | 9,39 | — |
| Grupo Financiero Galicia | 2025-12-31 | ARS | 132,48 | — | 51,93 | — |
| Macro Bank Inc. | 2025-12-31 | ARS | 452,75 | — | — | — |

```
eps       8/8      ev_sales  5/8
pe        6/8      pb        6/8
```

**Los bancos quedan pobres, y es del modelo contable, no del motor:** Galicia y
Macro no publican `Revenue` bajo ninguno de los cinco tags de la cadena.

---

## 8. Limitaciones

| | |
|---|---|
| **No hay TTM** | todas las métricas de flujo son `FY`. El P/E no es comparable contra una fuente que publique TTM |
| **Ocho emisores** | el límite es la ingesta de estados contables, no el cálculo |
| **Cuatro métricas** | faltan ROE, ROIC, márgenes, deuda/EBITDA, liquidez, FCF, dividendos |
| **Ninguna métrica con EBITDA** | EBITDA no existe como tag XBRL: se construye, y hay 12 candidatos de amortización con semánticas distintas. Hasta decidir cuál, no se publica ningún múltiplo que dependa de él |
| **Sin series históricas** | se entrega el último ejercicio de cada emisor |
| **Capitalización con acciones de carátula** | el conteo lleva la fecha de portada del filing, no la del cierre |
| **Precio de hoy contra balance de meses atrás** | inherente a todo múltiplo; acá queda registrado en la procedencia en vez de taparse |
| **Interfaz de línea de comandos** | no hay endpoint HTTP ni interfaz web para esta superficie. Ver §10 |
| **Las capas históricas siguen publicando otros números** | y pueden discrepar. No están cubiertas por este contrato |

---

## 9. Qué NO promete Catalaxia

Explícito, para que nadie lo asuma por omisión:

- **No** es un reemplazo de TIKR, Bloomberg, FactSet ni Refinitiv.
- **No** tiene cobertura completa de ratios ni de empresas.
- **No** entrega datos en tiempo real. Los precios son de cierre diario.
- **No** publica estimaciones, proyecciones, consenso de analistas ni precios objetivo.
- **No** ofrece P/E TTM. El P/E es FY y está etiquetado como tal.
- **No** garantiza que los números coincidan con otros proveedores: las
  diferencias de definición y de ventana son reales y están documentadas.
- **No** respalda con este contrato los números de sus capas históricas.
- **No** es asesoramiento de inversión.

---

## 10. Garantías que sí se dan

| garantía | cómo está verificada |
|---|---|
| Una métrica nunca consume datos de otra entidad | regla de pertenencia sobre la procedencia; **0 violaciones en 135.077 punteros** |
| Una métrica nunca mezcla monedas | numerador y denominador deben coincidir; si no, `NOT_CALCULABLE` |
| Nunca hay una división por cero | denominador cero o de signo inválido ⇒ `NOT_CALCULABLE` con el concepto nombrado |
| Recalcular no duplica ni sobrescribe | idempotencia por clave; un insumo distinto cierra la celda y abre otra |
| Cambiar una fórmula no reescribe el histórico | `formula_version` es parte de la identidad de la celda |
| El período nunca queda implícito | `window` es parte de la clave: una celda sin ventana no existe |
| Toda celda calculada tiene procedencia completa | 25/25, verificado al servir |

### Verificación independiente

Un proceso que **no comparte una sola línea de código** con el motor rehace las
25 celdas desde los insumos persistidos y compara:

```
25/25 valores reproducidos    peor desvío relativo 1,59e-7
13/13 controles OK            tolerancia declarada 1,0e-6
```

El desvío es el redondeo a seis decimales que se aplica al guardar.

---

## 11. Superficie de acceso

**Hoy:** interfaz de línea de comandos que devuelve JSON, sobre PostgreSQL.

```bash
ratio_api --ticker AAPL                            # todas las métricas
ratio_api --ticker AAPL --ratio ev_sales --provenance
ratio_api --ticker AAPL --fundamental ingresos
ratio_api --universo --provenance                  # el conjunto completo
```

Seis dimensiones de consulta: `--ticker`/`--cik`, `--ratio`, `--period`,
`--window`, `--currency`, `--status`.

**Formato de entrega para un piloto:** un JSON autocontenido con las 32 celdas y
su procedencia completa (≈130 KB), regenerable con un comando y verificable
contra los archivos de la SEC.

**Lo que no existe todavía:** endpoint HTTP e interfaz web para esta superficie.
Especificado en la propuesta de piloto; no construido.

---

*Motor y contrato técnico: `outputs/docs/fase_ratios/`. Este documento gobierna
lo que se promete a un cliente; ante discrepancia, manda éste.*
