# CATALAXIA — ratios financieros con procedencia verificable

**Versión 1.0 · vertical slice · 2026-09-01**

Catalaxia calcula un número pequeño de ratios y, para cada uno, puede mostrar de
qué documento salió. **No es un reemplazo de TIKR ni pretende serlo**: TIKR
publica cientos de métricas sobre miles de empresas. Acá hay cuatro ratios sobre
ocho emisores. Lo que sí hay, y no es habitual, es que cada celda se pueda
seguir hasta el archivo que la SEC publicó, con su hash.

---

## 1. Qué ratios están disponibles

| ratio | fórmula | unidad | ventana | versión |
|---|---|---|---|---|
| **EPS** | EPS básico reportado por el emisor | moneda por acción | `FY` | `eps_v1` |
| **P/B** | (precio ÷ ratio ADR) ÷ (patrimonio de la controladora ÷ acciones) | veces | `PIT` | `pb_v1` |
| **P/E** | (precio ÷ ratio ADR) ÷ EPS | veces | **`FY`** | `pe_v1` |
| **EV/Sales** | (capitalización + deuda financiera − efectivo) ÷ ingresos | veces | `FY` | `ev_sales_v1` |

Y nada más. Cualquier otro ratio que aparezca en pantallas antiguas del proyecto
viene de las superficies legacy, que **no** tienen procedencia verificable.

### Cobertura actual

```
eps       8/8 emisores
pb        6/8
pe        6/8
ev_sales  5/8
```

| emisor | período | moneda | EPS | P/B | P/E | EV/Sales |
|---|---|---|---:|---:|---:|---:|
| Apple Inc. | 2025-09-27 | USD | 7,49 | 63,03 | 42,00 | 11,30 |
| MICROSOFT CORP | 2026-06-30 | USD | 18,00 | 8,48 | 28,06 | 11,36 |
| NVIDIA CORP | 2026-01-25 | USD | 4,93 | 35,23 | 46,24 | 25,65 |
| YPF S.A. | 2025-12-31 | USD | −2,11 | 1,84 | — | 1,60 |
| TRANSPORTADORA DE GAS DEL SUR | 2025-12-31 | ARS | 559,09 | 2,19 | 16,29 | 4,51 |
| CENTRAL PUERTO S.A. | 2025-12-31 | ARS | 230,61 | 1,29 | 9,39 | — |
| GRUPO FINANCIERO GALICIA | 2025-12-31 | ARS | 132,48 | — | 51,93 | — |
| Macro Bank Inc. | 2025-12-31 | ARS | 452,75 | — | — | — |

Cada guion tiene un motivo escrito. Ver §4.

---

## 2. Qué período representa cada número

Esto es lo que más se malinterpreta en los productos financieros, así que va
primero y explícito.

| ventana | significa |
|---|---|
| `FY` | **el último ejercicio fiscal completo.** No es TTM. |
| `PIT` | *point in time* — un saldo de balance a la fecha del cierre |
| `TTM` | doce meses móviles — **Catalaxia no lo soporta todavía** |

### El P/E de Catalaxia es FY, no TTM

```
AAPL   precio  314,58 USD  (2026-08-27)
       EPS       7,49 USD  (ejercicio cerrado el 2025-09-27)
       P/E  =   42,00      window = FY
```

El precio es de hoy; el EPS es del ejercicio anual cerrado hace once meses.
**Un P/E TTM daría otro número.** El estándar de la industria es TTM, y el
contrato interno también lo declara canónico — pero el motor no sabe sumar
cuatro trimestres, así que publica FY y **lo dice en la columna `window`**.

La regla que se aplicó fue: antes que un número con la etiqueta equivocada,
un número con la etiqueta correcta.

### Los ratios mixtos declaran las dos mitades

`P/B` combina un precio de hoy con un patrimonio del cierre. Por eso la celda
lleva también `denominator_basis`:

```
CLOSING   el saldo al cierre del período
AVERAGE   promedio entre apertura y cierre
n/a       el denominador también es de flujo
```

---

## 3. Cómo se lee una celda

**Ningún valor viaja solo.** La respuesta mínima de la API es:

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
  "motivo": null,
  "publicable": true
}
```

Un consumidor que muestre sólo `value` está tirando la mitad de la información.
`window`, `currency` y `formula_version` son parte del número, no metadatos
opcionales: el mismo `11,30` con otra ventana es **otro hecho**.

---

## 4. Qué significa `NOT_CALCULABLE`

**`NOT_CALCULABLE` no es cero y no es un error.** Es una respuesta con motivo.

Un cero diría «esta empresa no tiene deuda». Un error diría «el sistema se
rompió». `NOT_CALCULABLE` dice «no puedo afirmar este número, y acá está por
qué».

Hay **dos familias**, distinguibles por el motivo:

### 4.1 · Falta un dato

```json
{
  "canonical_id": "ev_sales",
  "value": null,
  "status": "NOT_CALCULABLE",
  "motivo": "sin fact para el concepto 'deuda_financiera' en 2025-12-31;
             candidatos consultados: ['Borrowings',
             'DebtLongtermAndShorttermCombinedAmount', 'LongTermDebt']"
}
```

Central Puerto no publica ninguno de los tres tags de deuda financiera. El
motivo nombra **el concepto y la cadena completa que se consultó**, así que se
puede verificar que la búsqueda fue exhaustiva y no un descuido.

Rellenar ese hueco con cero sería inventar que la empresa no tiene deuda.

### 4.2 · Una regla financiera lo impide

```json
{
  "canonical_id": "pe",
  "value": null,
  "status": "NOT_CALCULABLE",
  "provenance_status": "COMPLETA",
  "motivo": "REGLA: EPS = -2.11 <= 0 (ejercicio con perdida). El P/E queda sin
             valor por decision financiera, no por falta de dato: el EPS esta
             y su provenance tambien"
}
```

YPF cerró 2025 con pérdida. Un P/E negativo es aritméticamente calculable y
financieramente ilegible: se lee como «barato» cuando significa lo contrario.
Es la convención del IAMC y de la práctica argentina.

Nótese que `provenance_status` sigue siendo `COMPLETA`: **el dato está, la
cadena está, y aun así no se publica el múltiplo.** Ésa es la diferencia con el
caso anterior.

### 4.3 · Un tercer caso: la identidad no alcanza

Macro Bank no tiene instrumento ligado en `identity_v1.instrument`:

```
"motivo": "la entidad no tiene instrumento ligado en identity_v1.instrument:
           atribuirle un precio seria un join por ticker"
```

Hay precios con el ticker «BMA». Lo que no hay es **prueba** de que esa especie
cotizante sea de esa entidad. Unirlos por ticker es exactamente el error que
produjo, en una etapa anterior del proyecto, que precios de Coursera se
mostraran como argentinos. Ver [`colision-tickers-byma-us`].

---

## 5. Qué significa `provenance_status: COMPLETA`

Que **cada insumo contable** de la celda cumple, verificado al servir:

1. cita al menos un `source_fact_id`;
2. cada uno existe en `parsed.facts`;
3. la fila apuntada es **del mismo emisor** (`parsed_cik == cik`);
4. viene con el `sha256` del archivo que la ingesta descargó de la SEC;
5. el tag usado pertenece a la cadena de fallback declarada del concepto.

`PARCIAL` significa que algún insumo no cumple alguna. `AUSENTE`, que la celda
no cita ningún insumo contable.

El precio y los valores derivados (capitalización, valor de empresa) no llevan
cadena XBRL porque no salen de un filing: salen de `market_price_daily` y de
una cuenta. Están declarados aparte y no cuentan para el estado.

### Por qué las listas de hashes son listas

El 47 % de los hechos normalizados se apoya en **más de una** fila de
`parsed.facts` — el mismo dato aparece repetido en varios estados del mismo
filing. Guardar un solo archivo dejaba fuera la mitad de la evidencia. Por eso
`source_files` y `source_hashes` son listas.

---

## 6. Cómo se reproduce un valor

Cualquiera puede rehacer la cuenta con los insumos que la propia celda publica.
Ejemplo con Apple:

```bash
python scripts/engine/ratio_api.py --ticker AAPL --ratio ev_sales --provenance
```

```
ingresos    RevenueFromContractWithCustomerExcludingAssessedTax   416.161.000.000 USD
deuda       LongTermDebt                                           90.678.000.000 USD
efectivo    CashAndCashEquivalentsAtCarryingValue                  35.934.000.000 USD
acciones    CommonStockSharesOutstanding                           14.773.260.000
precio      314,579987 USD · instrumento 86 · 2026-08-27 · ratio_adr 1
```

```
market_cap = 314,579987 / 1 × 14.773.260.000 = 4.647.371.938.747,62
EV         = 4.647.371.938.747,62 + 90.678.000.000 − 35.934.000.000
           = 4.702.115.938.747,62
EV/Sales   = 4.702.115.938.747,62 / 416.161.000.000 = 11,29879
```

Y hasta el documento:

```
source_fact_ids  [148013, 148327, 148938, 149030, 149144, 149458, 150069, 150161]
source_files     aapl-20250927.htm · aapl-20250927_htm.xml
source_hashes    e1076735f1c81bc9… · 274361a794f84b24…
accession        0000320193-25-000079
                 https://www.sec.gov/Archives/edgar/data/320193/...
```

**Homologación independiente**: `scripts/engine/homologacion_slice.py` rehace las
25 celdas calculadas sin importar el motor —habla con PostgreSQL por `psql` y
reescribe las fórmulas desde el contrato— y compara.

```
25/25 reproducidas · peor desvío relativo 1,59e-7 · tolerancia 1e-6
```

El desvío es el redondeo a seis decimales que el motor aplica al persistir.

---

## 7. Limitaciones actuales

Sin adornos.

| | |
|---|---|
| **No hay TTM** | El motor no agrega períodos. Todos los ratios de flujo son `FY`. El P/E no es comparable contra una fuente que publique TTM. |
| **Ocho emisores** | No 500, no 5.000. El límite es la ingesta de fundamentals, no el cálculo. |
| **Cuatro ratios** | De los 17 prioritarios del contrato interno. Faltan ROE, ROIC, márgenes, deuda, liquidez, FCF, dividendos. |
| **Ningún ratio con EBITDA** | EBITDA no existe como tag XBRL: se construye, y hay 12 candidatos de amortización con semánticas distintas. Hasta que se decida cuál, no se publica ningún múltiplo que dependa de él. |
| **Bancos con cobertura pobre** | Galicia y Macro no publican `Revenue` bajo ninguno de los cinco tags de la cadena. No es un defecto del motor: es el modelo contable del sector. |
| **La capitalización usa el conteo de acciones de carátula** | El tag `dei` lleva la fecha de portada del filing, no la del cierre. Para emisores con recompras activas hay un desfase. |
| **Un precio de hoy contra un balance de hace meses** | Inherente a todo múltiplo; acá queda registrado en la provenance (`trading_date` vs `period_end`) en vez de taparse. |
| **Las superficies legacy siguen publicando otros números** | El screener HTML y la API v2 sirven ratios de las capas antiguas, que **no** tienen procedencia verificable. Coexisten; no son esto. |

### Lo que este producto no es

No es paridad con TIKR. No es cobertura completa de ratios. No es un dato de
mercado en tiempo real. Es una vertical delgada donde **cada número se puede
auditar hasta el documento original**, y donde lo que no se puede afirmar
aparece como `NOT_CALCULABLE` con su motivo en lugar de como un cero.

---

## 8. Garantías que el sistema sí da

| garantía | cómo se verifica |
|---|---|
| Un ratio nunca consume hechos de otra entidad | guarda de pertenencia F-061 sobre `source_fact_ids`; 0 violaciones en 135.077 punteros |
| Un ratio nunca mezcla monedas | numerador y denominador deben coincidir; si no, `NOT_CALCULABLE` |
| Nunca hay una división por cero | denominador 0 o de signo inválido ⇒ `NOT_CALCULABLE` con el concepto nombrado |
| Recalcular no duplica ni sobrescribe | idempotencia por `ratio_key`; un insumo distinto cierra la fila con `valid_to` y abre otra |
| Cambiar una fórmula no reescribe el histórico | `formula_version` participa de la identidad |
| El período nunca queda implícito | `window` es parte de la clave; una celda sin ventana no existe |

---

*Interfaz: `scripts/engine/ratio_api.py`. Motor: `scripts/engine/ratio_engine.py`.
Contrato completo: `RATIO_CONTRACT.md`. Homologación: `DAY4_VERTICAL_SLICE_GATE.md`.*
