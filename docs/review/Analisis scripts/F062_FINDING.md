# F-062 — "NO HAY TAG DE D&A" ERA INCORRECTO: EL DATO EXISTE, SOLO NO ESTÁ DECLARADO COMO CONCEPTO

**Detectado:** 2026-09-01, Fase A (inventario) del encargo de producto
**Severidad: MEDIUM** (corrección de clasificación, no un riesgo activo)
**Estado: CORREGIDO — solo la clasificación; no se implementó EV/EBITDA**

---

## 1. El hallazgo

`RATIO_COVERAGE_MATRIX.md` y `RATIO_CONTRACT.md` (versión del 2026-09-01,
ciclo anterior) afirmaban:

> `ev_ebitda` | NOT_CALCULABLE | no hay tag de D&A: ni
> `DepreciationAndAmortisationExpense` ni la variante larga IFRS aparecen en
> `derived.fact`.

Es incorrecto. Consulta directa a `derived.fact` (2026-09-01, este ciclo)
sobre las 8 empresas de la muestra:

| empresa | tags de D&A presentes (muestra) |
|---|---|
| BMA | `DepreciationAndAmortisationExpense` (el tag EXACTO que se dijo ausente), `AdjustmentsForDepreciationAndAmortisationExpense` |
| YPFD | `AdjustmentsForDepreciationExpense`, `AdjustmentsForAmortisationExpense`, `AmortisationExpense` |
| CEPU | `AdjustmentsForDepreciationExpense`, `AdjustmentsForAmortisationExpense`, `DepreciationOfPropertyPlantAndEquipment` |
| TGSU2 | `AdjustmentsForDepreciationAndAmortisationExpense`, `DepreciationExpense`, `DepreciationPropertyPlantAndEquipment` |
| GGAL | `AdjustmentsForDepreciationAndAmortisationExpenseAndImpairmentLoss...`, `DepreciationAmortisationAndImpairmentLoss...` |
| AAPL | `DepreciationDepletionAndAmortization`, `Depreciation` |
| MSFT | `DepreciationAmortizationAndOther`, `AmortizationOfIntangibleAssets` |
| NVDA | `DepreciationDepletionAndAmortization`, `AmortizationOfIntangibleAssets` |

**Las 8 tienen al menos un candidato.** El error del ciclo anterior fue
buscar un único nombre de tag (`DepreciationAndAmortisationExpense`, que de
hecho SÍ existe — pero solo en BMA) sin declarar la cadena de fallback que
el resto del contrato ya usa para todos los demás conceptos.

## 2. Por qué no se corrige implementando EV/EBITDA

El encargo de este ciclo prohíbe implementar ratios nuevos fuera de lo
explícitamente autorizado, y elegir el tag correcto de D&A no es trivial:
los candidatos tienen semánticas distintas —

- `AdjustmentsFor...` son partidas de **conciliación del estado de flujo de
  efectivo** (el D&A que se sube de vuelta al resultado neto para llegar al
  flujo operativo): la semántica correcta para reconstruir EBITDA desde el
  resultado operativo.
- `Depreciation`/`DepreciationExpense`/`DepreciationPropertyPlantAndEquipment`
  a veces son el **gasto del ejercicio** en el estado de resultados, y a
  veces son la **depreciación acumulada** del balance
  (`AccumulatedDepreciation...`) — dos magnitudes completamente distintas
  (flujo vs. stock) que aparecieron mezcladas en la búsqueda por palabra
  clave de este hallazgo y que un futuro contrato tendría que separar con
  cuidado.

Confundir stock con flujo daría un EBITDA con el orden de magnitud
equivocado — exactamente el tipo de error que el encargo pide no cometer
("no asumir que un ratio está correcto porque el número parece
razonable"). Se registra la corrección de clasificación (dato existe →
NO_IMPLEMENTADO en vez de NOT_CALCULABLE) y se deja pendiente, explícito,
para cuando se autorice el trabajo de contrato correspondiente.

## 3. Corrección aplicada

`RATIO_CONTRACT.md` §13 y `RATIO_COVERAGE_MATRIX.md` actualizados
(2026-09-01) para reflejar: EV/EBITDA es `NO_IMPLEMENTADO` (falta código,
no falta dato), con la lista de candidatos de D&A y la advertencia de
stock-vs-flujo dejada explícita para el próximo ciclo.

## 4. Lección

"No hay dato" y "no busqué el dato con la cadena de fallback correcta" se
parecen mucho en el resultado (`NOT_CALCULABLE`) y son afirmaciones muy
distintas. La primera es un límite de ingesta; la segunda es un límite de
declaración de conceptos, y se corrige sin tocar la base. Vale la pena
haber tratado el "ningún tag de D&A" del ciclo anterior con la misma regla
que el resto del encargo pide para todo lo demás: verificar, no asumir por
lo que dice un documento previo.
