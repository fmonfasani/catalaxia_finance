# METR FY2025 — LAS DIEZ PREGUNTAS SOBRE LOS 66 NO_INPUT

**Fecha:** 2026-09-02 · read-only · sin implementar nada.

---

## 1 · ¿Cuántos son realmente extraction gaps?

**Tres.** El dato está en el documento y el parser no lo mapea:

| código | etiqueta | valor RAW | TIKR | docs |
|---|---|--:|--:|--:|
| `2210300` | AJUSTE DE CAPITAL | 346.707 | 346.707 | 56/56 |
| `2211300` | INTERESES NO CONTROLANTES | 1.880 | 1.880 | 27/56 |
| `3011100` | OTROS INGRESOS | 10.002 | 10.002 | 44/56 |

Los tres coinciden al peso. **Corrigen una afirmación del informe anterior**,
que daba la minoritaria por inexistente en CNV.

Y fuera del universo de los 66 hay un cuarto código con el mismo carácter:
`8000002 TOTAL PATRIMONIO NETO DEL EJERCICIO ANTERIOR = 829.478`, en 51 de 56
documentos. Con él el ROE da 14,804 % = TIKR exacto.

---

## 2 · ¿Cuántos son derivables?

**Diez**, pero sólo **cuatro** con los datos de hoy, y en forma parcial:

| derivable ahora | estado |
|---|---|
| MetroENERGY · Revenue, Operating Income, Net Income, Assets | **parcial**: `CONSOLIDADO − INDIVIDUAL` da MetroENERGY **+ eliminaciones**, no cada uno |

Los otros seis están bloqueados:

- **cinco por el capex**: Free Cash Flow, Levered FCF Margin, Unlevered FCF
  Margin, `(EBITDA−Capex)/Interés`, `Net Debt/(EBITDA−Capex)`;
- **uno es circular**: `Current Unearned Revenue` = Payables − AP de TIKR;
  sólo se deriva conociendo el dato que se quiere reproducir.

---

## 3 · ¿Cuántos requieren comparativos?

**Cuatro.** Uno es un comparativo propiamente dicho y tres son el mismo dato
faltante:

| métrica | qué falta |
|---|---|
| Cash Beginning | la caja de apertura **re-expresada** a moneda de dic-2025. **No está en el RAW**: se buscó y ningún código tiene un valor cercano a 160.859 |
| Book Value / Share · Tangible BV / Share · Cash Flow per Share | el **número de acciones en circulación** |

---

## 4 · ¿Cuántos no están publicados por CNV?

**Treinta y cuatro** — el 52 % de los 66. Se buscó en los **76 códigos** que
aparecen en los documentos de METR y no hay equivalente.

Se concentran en tres sitios:

- **13** en el desglose del flujo de efectivo — la CNV publica tres subtotales;
- **11** en el desglose del balance — está en las **notas**, que no se descargan;
- **4** en las eliminaciones de consolidación;
- **6** en partidas del resultado y ratios que dependen de ellas.

---

## 5 · ¿Cuántos parecen TIKR-specific?

**Cuatro** `TIKR_NORMALIZATION` (EBT excl. unusual, EBITA Margin, FFO/Interés,
FFO/Deuda) más **once** `SEMANTIC_AMBIGUITY`, donde existe un código CNV que
**no equivale** al renglón de TIKR.

En total **quince métricas (23 %)** donde la diferencia no es de Catalaxia sino
de cómo TIKR arma su superficie normalizada.

---

## 6 · Los cinco gaps de mayor impacto

| # | gap | métricas | dificultad |
|---|---|--:|---|
| **1** | **desglose del flujo de efectivo** (capex y demás) | **18** | alta — no está en el EEFF resumido |
| **2** | **desglose del balance** (notas contables) | **11** | alta — otra fuente |
| **3** | **extraer los 3 códigos + el comparativo** | **3 (+ROE)** | **baja — el dato ya está descargado** |
| **4** | **desglose de la deuda financiera** | 4 | media |
| **5** | **número de acciones** | 3 | media — otra fuente |

**El #3 es el único que no requiere descargar nada nuevo.**

---

## 7 · ¿Cuáles se resuelven sin modificar el modelo?

**Los tres EXTRACTION_GAP más el comparativo de patrimonio.** El modelo
canónico ya tiene todo lo necesario: `entity_id`, `period_kind`, `unit_measure`,
`econ_key`, `fact_key`, perímetro. Es agregar cuatro entradas al mapa de
códigos del parser.

Y el comparativo tiene además el modelo listo: `measurement_date` y `econ_key`
—de W-1.2 y W-1.3— ya distinguen dos mediciones del mismo período, que es
justamente lo que un comparativo re-expresado necesita.

---

## 8 · ¿Cuáles requieren nueva extracción?

| | |
|---|---|
| **del RAW ya descargado** | los 3 códigos + `8000002`. Sin red |
| **de las notas contables** | 11 renglones del balance. Requiere descargar otro documento |
| **del estado de flujos completo** | 13 renglones. Ídem |
| **de otra fuente** | acciones en circulación, dividendos, precio |

---

## 9 · ¿Cuáles requieren nueva lógica derivada?

**Cuatro**, y sólo después de resolver la extracción:

- `Free Cash Flow` = CFO − Capex → después del gap #1;
- los tres márgenes y ratios que dependen del FCF;
- las cuatro de segmentos MetroENERGY → después de las eliminaciones;
- `Total Debt` con la definición de TIKR → después del gap #4.

Ninguna es lógica nueva de modelo: son fórmulas sobre insumos que hoy no
existen.

---

## 10 · ¿Cuáles NO deberían implementarse?

**Veintiséis métricas.** No por dificultad, sino porque implementarlas exigiría
inventar una equivalencia:

| | n | por qué |
|---|--:|---|
| `SEMANTIC_AMBIGUITY` | 11 | existe un código relacionado con **otro valor**. Mapearlos sería casarlos por nombre |
| `TIKR_NORMALIZATION` | 4 | criterio propio de TIKR, no deducible del benchmark |
| eliminaciones de consolidación | 4 | la CNV no las publica; derivarlas por residuo mezclaría todo lo no extraído |
| "Other Current/Long-Term Assets/Liabilities" | 4 | derivables **por residuo**, pero un residuo no es un concepto |
| `Current Unearned Revenue` | 1 | derivación circular |
| Book Value/Share y afines usando `Capital` | 2 | `Capital` = 569 coincide con las acciones de TIKR, pero **es el capital social, no el número de acciones** |

> Los dos últimos son la misma trampa que `ResultadosNoAsignados`: un número que
> coincide no prueba que el concepto coincida.

---

## Cierre

De los 66:

```
 3  se arreglan leyendo mejor lo que ya está descargado
 4  se arreglan con el comparativo, que también está descargado (el ROE ya lo prueba)
34  requieren una fuente que hoy no bajamos (notas, flujo detallado)
26  NO deberían implementarse
```

**El 5 % de los gaps se cierra sin salir del disco. El 52 % necesita otra
fuente. El 39 % no debería tocarse.**
