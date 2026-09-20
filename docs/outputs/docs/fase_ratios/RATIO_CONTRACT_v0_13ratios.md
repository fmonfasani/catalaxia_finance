# RATIO_CONTRACT — contrato formal de los 13 ratios del encargo

**Fecha:** 2026-09-01 · **Rol:** Financial Data Architect + Product Validation Auditor
**Ámbito:** capa de cálculo (`derived.fact` → ratio). No toca SEC/CNV/Market. Sin commits.

Este documento fija, por concepto, la única definición legítima de cada ratio
antes de calcularlo. Donde el sistema ya calcula algo distinto de este
contrato, se dice explícitamente en la fila y queda registrado como deuda, no
como excepción silenciosa.

Fuente de verdad del código: `scripts/engine/ratio_defs.py` (mapa concepto →
tags candidatos) + `scripts/engine/e2e_producto.py` / `ratios_inventario.py`
(resolución de P/E y de los fundamentales). Los doce campos de este contrato
responden, para cada ratio, las doce preguntas del encargo (concepto, datos,
filing, facts, unidad, período, fórmula, NULL, signo, acciones, taxonomía,
evidencia).

---

## 0. Reglas que aplican a los 13 por igual

1. **NULL es un resultado, no un error.** Prohibido rellenar con 0, guion,
   promedio de sector o valor del ejercicio anterior. Cada NULL lleva un
   motivo legible (§3 de `SCREENER_CONTRACT_V1.md`).
2. **Un ratio combina facts de un solo filing.** Numerador y denominador
   deben compartir `accession_number`. Auditado: control D2 de
   `ratios_auditoria.py`, 0 cruces en 274 ratios calculados.
3. **Un ratio no mezcla monedas.** Si el numerador y el denominador (o el
   precio y el EPS) están en monedas distintas, el resultado es NULL con
   motivo — nunca se convierte con un FX no declarado.
4. **El concepto manda, no el tag.** Cada concepto declara una lista
   ordenada de tags candidatos (`CONCEPTOS` en `ratio_defs.py`); el orden ES
   la regla de fallback. Cuál tag se usó queda en la provenance de la celda,
   nunca se pierde detrás del nombre del concepto.
5. **La pertenencia de un tag a un concepto es una declaración, no una
   inferencia por parecido de nombre.** Donde hay una segunda ruta al mismo
   número, se verifica con aritmética independiente antes de asumir la
   equivalencia (ver `RATIOS_MULTIPATH.md` y `audit_provenance_ratios.py`,
   que valida por **identidad contable** — Activo=Pasivo+Patrimonio,
   EPS=Resultado/Acciones — no por coincidencia de nombres).
6. **Selección de período.** Cada 20-F/10-K trae hasta tres años
   comparativos del mismo hecho. Se toma el año **principal** del filing
   (`report_period == instant_date/end_date`); los comparativos se
   descartan. Auditado: control D3.
7. **Taxonomía declarada, no asumida.** `ifrs-full` y `us-gaap` conviven en
   la misma tabla (`derived.fact`); la taxonomía de cada filing sale de los
   namespaces del propio documento (`taxonomia_de()`), nunca del país o del
   formulario.

---

## 1. Current Ratio

| campo | valor |
|---|---|
| **Concepto** | liquidez de corto plazo: cuánto activo corriente cubre cada unidad de pasivo corriente |
| **Fórmula** | `activo_corriente / pasivo_corriente` |
| **Numerador** | concepto `activo_corriente` → tags `CurrentAssets` (ifrs-full) / `AssetsCurrent` (us-gaap) |
| **Denominador** | concepto `pasivo_corriente` → tags `CurrentLiabilities` (ifrs-full) / `LiabilitiesCurrent` (us-gaap) |
| **Período** | año principal del filing; instant (foto a la fecha de cierre) |
| **Unidad** | veces (adimensional) |
| **Signo** | ambos operandos deben ser ≥ 0 por definición contable; no se fuerza el signo, se deja que la identidad A=P+PN lo contraste (§Fase G) |
| **NULL cuando** | falta cualquiera de los dos tags en el período; monedas distintas; denominador = 0 |
| **Fallback** | orden de la tabla de arriba; el primer tag presente gana, se registra en provenance |
| **Prohibido** | promediar corriente+no corriente para simular el total; usar el activo/pasivo TOTAL como sustituto |
| **Provenance** | `accession_number`, `tag` elegido, `currency`, `report_period` de cada operando |
| **Evidencia** | `ratios_calculados.json` — CEPU 1.77, TGSU2 NULL (falta `CurrentAssets`/`AssetsCurrent` en 2025), AAPL 0.89, NVDA 3.91 |

---

## 2. Quick Ratio

| campo | valor |
|---|---|
| **Concepto** | liquidez inmediata: activo corriente sin existencias, sobre pasivo corriente |
| **Fórmula** | `(activo_corriente − existencias) / pasivo_corriente` |
| **Numerador** | `activo_corriente` (ver Current Ratio) **menos** concepto `existencias` → tags `Inventories` (ifrs-full) / `InventoryNet` (us-gaap) |
| **Denominador** | `pasivo_corriente` (igual que Current Ratio) |
| **Período** | igual que Current Ratio |
| **Unidad** | veces |
| **Signo** | la resta puede dar negativa si `existencias > activo_corriente`; se publica el valor negativo, no se trunca a 0 |
| **NULL cuando** | falta `activo_corriente`, `pasivo_corriente` **o** `existencias`; monedas distintas entre los tres; denominador = 0 |
| **Fallback** | el término a restar tiene su propia cadena de fallback, independiente de la del numerador principal |
| **Prohibido** | asumir existencias = 0 cuando el tag no aparece (una empresa de servicios sin inventario NO es lo mismo que "el dato falta"; hoy el sistema **no distingue** los dos casos — ver §6 limitaciones) |
| **Provenance** | igual que Current Ratio + tag y valor del término restado |
| **Evidencia** | control de auditoría específico: al agregar este ratio, el auditor independiente (que recalcula **sin** la resta) marcó 9 divergencias hasta que se le declaró la forma compuesta — ver `CICLO_ESTADO_FINAL.md` §2. Prueba de que el control rechaza, no solo aprueba. |

---

## 3. Gross Margin

| campo | valor |
|---|---|
| **Concepto** | rentabilidad bruta sobre ventas |
| **Fórmula** | `resultado_bruto / ingresos` |
| **Numerador** | concepto `resultado_bruto` → tag `GrossProfit` (compartido por las dos taxonomías) |
| **Denominador** | concepto `ingresos` → `Revenue`, `RevenueFromContractsWithCustomers`, `RevenueFromContractWithCustomerExcludingAssessedTax`, `RevenueFromContractWithCustomerIncludingAssessedTax`, `Revenues` |
| **Período** | año principal, duration (ejercicio completo, no un trimestre suelto) |
| **Unidad** | fracción |
| **Signo** | puede ser negativo (costo de ventas > ingresos); se publica |
| **NULL cuando** | falta `GrossProfit` (empresas que no lo desglosan, típico en bancos) o `ingresos`; ingresos = 0 |
| **Fallback** | `GrossProfit` no tiene fallback propio: si el emisor no lo reporta, el ratio no se deriva de ingresos−costo salvo verificación explícita (ver Fase G, `audit_provenance_ratios.py` control E3, que sí reconstruye `ingresos − costo_de_ventas` como prueba de identidad, no como fuente del dato publicado) |
| **Prohibido** | derivar `GrossProfit` restando un `costo_de_ventas` inferido y publicarlo como si fuera el dato del emisor; eso es una FILA DISTINTA de evidencia y debe marcarse `DERIVADO`, no `CALCULADO` |
| **Provenance** | tag, moneda, período, accession |
| **Evidencia** | GGAL y CEPU (bancos/financieras): `GrossProfit` ausente → NULL, coherente con que las financieras no tienen "costo de ventas" |

---

## 4. Operating Margin

| campo | valor |
|---|---|
| **Concepto** | rentabilidad del negocio antes de intereses e impuestos |
| **Fórmula** | `resultado_operativo / ingresos` |
| **Numerador** | concepto `resultado_operativo` → `ProfitLossFromOperatingActivities` (ifrs-full) / `OperatingIncomeLoss` (us-gaap) |
| **Denominador** | `ingresos` (igual que Gross Margin) |
| **Período** | año principal, duration |
| **Unidad** | fracción |
| **Signo** | puede ser negativo |
| **NULL cuando** | falta el numerador o el denominador; monedas distintas; ingresos = 0 |
| **Fallback** | orden declarado arriba |
| **Prohibido** | usar EBIT calculado (`ProfitLossBeforeTax + costo_financiero`) como sustituto silencioso de `resultado_operativo` publicado — son dos números distintos y el contrato exige declarar cuál se usó |
| **Provenance** | tag, moneda, período, accession |
| **Evidencia** | AAPL 0.4691, MSFT 0.4678, NVDA 0.6038, YPFD 0.0943 (2025, USD) |

---

## 5. Net Margin

| campo | valor |
|---|---|
| **Concepto** | rentabilidad neta final sobre ventas |
| **Fórmula** | `resultado_neto / ingresos` |
| **Numerador** | concepto `resultado_neto` → `ProfitLossAttributableToOwnersOfParent`, `ProfitLoss` (ifrs-full) / `NetIncomeLoss` (us-gaap) / `ProfitLossAttributableToOwnersOfParentDiluted` |
| **Denominador** | `ingresos` |
| **Período** | año principal, duration |
| **Unidad** | fracción |
| **Signo** | puede ser negativo (pérdida neta) |
| **NULL cuando** | falta el numerador o el denominador; monedas distintas; ingresos = 0 |
| **Fallback** | `ProfitLossAttributableToOwnersOfParent` antes que `ProfitLoss` a secas: el primero excluye interés minoritario, que es lo que corresponde a la valuación por acción del controlador |
| **Prohibido** | usar `ProfitLoss` (incluye minoritarios) en un emisor con minoritario material sin declarar el cambio de perímetro |
| **Provenance** | tag, moneda, período, accession |
| **Evidencia** | YPFD **−0.0448** (2025, pérdida), CEPU 0.3156, AAPL 0.2692 |

---

## 6. ROE

| campo | valor |
|---|---|
| **Concepto** | retorno sobre el patrimonio de los accionistas controladores |
| **Fórmula** | `resultado_neto / patrimonio` |
| **Numerador** | `resultado_neto` (igual que Net Margin) |
| **Denominador** | concepto `patrimonio` → `Equity`, `EquityAttributableToOwnersOfParent` (ifrs-full) / `StockholdersEquity`, `StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest` (us-gaap) |
| **Período** | resultado = duration del ejercicio; patrimonio = instant al cierre del **mismo** ejercicio (no promedio con el inicial — ver §6 limitaciones) |
| **Unidad** | fracción |
| **Signo** | patrimonio negativo (recompras agresivas) invierte el signo del ROE sin que sea "buena" rentabilidad — **REVIEW_REQUIRED si patrimonio ≤ 0**, no se publica como CALCULADO liso |
| **NULL cuando** | falta el numerador o denominador; monedas distintas; patrimonio = 0 |
| **Fallback** | orden declarado arriba |
| **Prohibido** | promediar patrimonio inicial y final sin declarar el cambio de fórmula (hoy el sistema usa patrimonio de **cierre**, no promedio — es una convención declarada, no la única posible) |
| **Provenance** | tag, moneda, período, accession de cada operando |
| **Evidencia** | 22/22 calculados en la muestra de 8 (0 NO_CALCULABLE) tras el fix de taxonomía — ver §7 |

---

## 7. ROA

| campo | valor |
|---|---|
| **Concepto** | retorno sobre el activo total |
| **Fórmula** | `resultado_neto / activo_total` |
| **Numerador** | `resultado_neto` |
| **Denominador** | concepto `activo_total` → tag único `Assets` (compartido por las dos taxonomías) |
| **Período** | resultado = duration; activo = instant al cierre |
| **Unidad** | fracción |
| **Signo** | activo total no debería ser negativo por construcción contable; si lo fuera, es un error de dato, no un ROA válido |
| **NULL cuando** | falta el numerador; activo = 0 |
| **Fallback** | `Assets` no tiene alternativa: si no está, no hay ROA |
| **Prohibido** | usar activo corriente como sustituto de activo total |
| **Provenance** | igual que ROE |
| **Evidencia** | AAPL 0.3118, NVDA 0.5806, YPFD −0.0281 |

---

## 8. Debt/Equity

| campo | valor |
|---|---|
| **Concepto** | apalancamiento total: pasivo total sobre patrimonio |
| **Fórmula** | `pasivo_total / patrimonio` |
| **Numerador** | concepto `pasivo_total` → tag único `Liabilities` |
| **Denominador** | `patrimonio` (igual que ROE) |
| **Período** | instant al cierre, ambos del mismo filing |
| **Unidad** | veces |
| **Signo** | patrimonio negativo da D/E negativo — **no significa desapalancado**, significa lo contrario. REVIEW_REQUIRED si patrimonio ≤ 0. |
| **NULL cuando** | falta cualquiera de los dos; patrimonio = 0 |
| **Fallback** | orden declarado |
| **Prohibido** | confundir con `borrowings_to_equity` (solo deuda financiera, no todo el pasivo) — son dos ratios distintos que el sistema ya diferencia; no intercambiar sus nombres |
| **Provenance** | tag, moneda, período, accession |
| **Evidencia** | 22/22 calculados; GGAL 4.8855 (banco, apalancamiento alto es estructural del negocio, no señal de riesgo por sí solo) |

---

## 9. EPS (Earnings Per Share)

| campo | valor |
|---|---|
| **Concepto** | resultado neto atribuible por acción ordinaria |
| **Fórmula (método 1, PRIORITARIO)** | tag publicado directamente por el emisor: concepto `eps_basico` → `BasicEarningsLossPerShare` (2023-2025) / `BasicAndDilutedEarningsPerShare` (2021-2022) / `BasicAndDilutedEarningsLossPerShare` (2017-2020) / `EarningsPerShareBasic` (us-gaap) / `IncomeLossFromContinuingOperationsPerBasicShare` |
| **Fórmula (método 2, VERIFICACIÓN)** | `resultado_neto / acciones_promedio`, con `acciones_promedio` = concepto → `WeightedAverageShares` (ifrs) / `WeightedAverageNumberOfSharesOutstandingBasic` (us-gaap) / `WeightedAverageNumberOfSharesOutstandingBasicAndDiluted` |
| **Período** | duration del ejercicio |
| **Unidad** | moneda del filing / acción (no siempre USD: YPF reportó en ARS hasta 2021) |
| **Signo** | negativo en ejercicio con pérdida; se publica, nunca se trunca a 0 |
| **NULL cuando** | ningún tag del método 1 presente Y el método 2 no puede reconstruirse (falta `resultado_neto` o `acciones_promedio`) |
| **Fallback** | el tag del EPS **cambia de nombre entre ejercicios** — con un solo tag la cobertura cae de 9 a 3 ejercicios en YPF. La cadena de 5 candidatos es obligatoria, no opcional. Ver [[eps-tag-cambia-nombre]]. |
| **Prohibido** | usar `EntityCommonStockSharesOutstanding` (circulación a fecha de **carátula**, tag `dei`) o `NumberOfSharesOutstanding` (circulación a cierre) como denominador del EPS — ninguno de los dos es el promedio ponderado que el emisor usó. Mover uno por otro desplaza el EPS ~0.35% en YPF y mucho más en un emisor que emitió acciones en el ejercicio. |
| **Provenance** | tag, moneda, accession, y — cuando se usa el método 2 — los dos tags que lo componen |
| **Evidencia** | **verificado, no supuesto**: método 1 vs método 2 coinciden en **9/9 ejercicios de YPF**, diferencia máxima 0.72% (el residuo es redondeo del valor publicado a 2 decimales). Detalle en `RATIOS_MULTIPATH.md` §2. |

---

## 10. P/E (Price/Earnings)

| campo | valor |
|---|---|
| **Concepto** | cuántos años de resultado actual paga el precio de mercado |
| **Fórmula** | `precio / ratio_underlying / EPS` |
| **Numerador** | precio de cierre del instrumento cuya **moneda coincide con la del EPS**; si el precio es de un ADR, se divide por `ratio_underlying` de `identity_v1.instrument` (p.ej. CEPU 10:1, GGAL 10:1, TGS 5:1, YPF 1:1) antes de dividir |
| **Denominador** | EPS (ver ratio 9), método 1 con fallback a método 2 |
| **Período** | **mixto y declarado como tal**: precio de HOY, EPS del último ejercicio CERRADO. No es un P/E histórico. Un P/E histórico exige precio a la fecha del ejercicio y **no está implementado**. |
| **Unidad** | veces |
| **Signo** | **regla IAMC**: si EPS ≤ 0, el resultado es NULL (guion), nunca un P/E negativo. Un P/E negativo no tiene lectura financiera útil y se presta a leerse como "barato". |
| **NULL cuando** | EPS ≤ 0; EPS y precio en monedas distintas sin instrumento que las empate; falta `ratio_underlying` (no se asume 1); ningún instrumento con precio en la moneda del EPS |
| **Fallback** | ninguno adicional: P/E depende de EPS, que ya trae su propio fallback (ratio 9) |
| **Prohibido** | convertir moneda con un FX no declarado para forzar el cálculo; usar el EPS diluido donde el contrato pide básico sin decirlo |
| **Camino alternativo** | `(precio × acciones_a_fecha) / resultado_neto` — **NO es independiente de verdad**: comparte precio y resultado neto con el camino principal, y ambos fallan juntos cuando el resultado neto es negativo. Documentado en `RATIOS_MULTIPATH.md` §3 para que nadie lo cuente como segunda evidencia. |
| **Provenance** | precio, fecha del precio, instrumento, `ratio_underlying`, EPS, tag del EPS, accession |
| **Evidencia** | CEPU 9.39, TGSU2 16.29, AAPL 42.00, MSFT 28.06, NVDA 46.23, GGAL 51.93, **YPFD NULL** (EPS 2025 = −2.11, pérdida) |

---

## 11. P/B (Price/Book)

| campo | valor |
|---|---|
| **Concepto** | precio de mercado sobre valor libro del patrimonio por acción |
| **Fórmula** | `(precio / ratio_underlying) / (patrimonio_controladora / acciones_a_fecha)`, equivalente a `market_cap / patrimonio_controladora` |
| **Numerador** | precio del instrumento en la moneda del patrimonio, ajustado por `ratio_underlying` |
| **Denominador** | concepto `patrimonio_controladora` (`EquityAttributableToOwnersOfParent` / `Equity` / `StockholdersEquity`) dividido por `acciones_circulacion` **a fecha** (nunca el promedio ponderado — ese es el error documentado en market cap, ver ratio de abajo) |
| **Período** | precio de hoy, patrimonio del último cierre |
| **Unidad** | veces |
| **Signo** | patrimonio ≤ 0 → NULL (mismo criterio que ROE/D-E: un P/B "negativo" no es un P/B bajo, es indefinido) |
| **Estado actual** | **NOT_IMPLEMENTED.** Los facts de `patrimonio_controladora` están 9/9 en YPF y presentes en las 8 empresas de la muestra; **no hace falta ingesta nueva**. No se implementó en este ciclo para no calcular un ratio nuevo antes de fijar este contrato (regla del encargo). Queda como el paso de menor esfuerzo para el próximo ciclo. |
| **Prohibido** | usar el patrimonio TOTAL (incluyendo minoritario) contra un precio que solo representa al controlador |
| **Provenance (cuando se implemente)** | igual esquema que P/E |
| **Evidencia** | ninguna: no calculado |

---

## 12. P/S (Price/Sales)

| campo | valor |
|---|---|
| **Concepto** | precio de mercado sobre ingresos por acción |
| **Fórmula** | `market_cap / ingresos` |
| **Numerador** | `market_cap` = precio (ajustado por `ratio_underlying`) × `acciones_circulacion` a fecha |
| **Denominador** | concepto `ingresos` (igual que Gross/Operating/Net Margin) |
| **Período** | precio de hoy, ingresos del último ejercicio duration |
| **Unidad** | veces |
| **Signo** | ingresos ≤ 0 no ocurre por definición contable salvo error de dato; si ocurriera, NULL |
| **Estado actual** | **NOT_IMPLEMENTED.** `RATIOS_MERCADO` en `ratio_defs.py` declara `pe`, `market_cap`, `price_to_book` — **P/S no está ni siquiera declarado como concepto de mercado**. Es deuda de contrato, no solo de código: antes de calcularlo hay que fijar aquí la misma regla de "acciones a fecha, no promedio" que ya rige P/E y P/B. |
| **Prohibido** | usar `acciones_promedio` (el denominador del EPS) para construir el market cap del numerador — es el error ya documentado en `RATIOS_MULTIPATH.md` §4 |
| **Provenance (cuando se implemente)** | igual esquema que P/E |
| **Evidencia** | ninguna: no calculado |

---

## 13. EV/EBITDA

| campo | valor |
|---|---|
| **Concepto** | valor de la empresa (deuda neta incluida) sobre resultado antes de intereses, impuestos, depreciación y amortización |
| **Fórmula** | `(market_cap + deuda_financiera − efectivo) / EBITDA`, con `EBITDA = resultado_operativo + depreciación_y_amortizacion` |
| **Estado actual** | **CORREGIDO 2026-09-01 (F-062): NO_IMPLEMENTADO, no NOT_CALCULABLE.** La afirmación anterior ("ningún tag de D&A en `derived.fact`") era incorrecta: las 8 empresas de la muestra tienen al menos un candidato de D&A (verificado por consulta directa — ver `docs/review/F062_FINDING.md`). El bloqueo real es que EV/EBITDA nunca se declaró como concepto en `ratio_defs.py`; no hay código, no que falte el dato. **No se implementa en este ciclo**: los candidatos tienen semánticas distintas (partidas de conciliación de flujo de caja vs. gasto del ejercicio vs. depreciación acumulada de balance) y elegir mal daría un EBITDA con el orden de magnitud equivocado — es trabajo de contrato, no de ejecución. |
| **Prohibido** | aproximar EBITDA con `resultado_operativo` solo (omitiendo D&A) y publicarlo bajo el nombre EV/EBITDA — es un ratio distinto (`EV/EBIT`) y debe llamarse así si se publica; usar un tag de depreciación ACUMULADA de balance (stock) donde corresponde el GASTO del ejercicio (flujo) — son magnitudes distintas |
| **Camino de habilitación** | declarar el concepto `d_y_a` en `ratio_defs.CONCEPTOS` con la cadena de fallback correcta (candidatos por empresa en F-062_FINDING.md), decidiendo explícitamente cuál semántica (conciliación de CF vs. gasto del ejercicio) es la que corresponde a EBITDA. No requiere ingesta nueva: los tags ya están en `derived.fact`. |
| **Provenance (cuando se implemente)** | market_cap (con su propia cadena), deuda_financiera, efectivo, resultado_operativo, D&A — cinco insumos, cinco procedencias |
| **Evidencia** | ninguna: no calculado. Ver `RATIO_COVERAGE_MATRIX.md` §1.4. |

---

## Resumen de estado

| # | ratio | estado | cobertura medida (8 empresas, 9 ejercicios c/u) |
|---|---|---|---:|
| 1 | Current Ratio | IMPLEMENTADO | 16/22 |
| 2 | Quick Ratio | IMPLEMENTADO | 16/22 |
| 3 | Gross Margin | IMPLEMENTADO | 18/22 |
| 4 | Operating Margin | IMPLEMENTADO | 18/22 |
| 5 | Net Margin | IMPLEMENTADO | 18/22 |
| 6 | ROE | IMPLEMENTADO | 22/22 |
| 7 | ROA | IMPLEMENTADO | 22/22 |
| 8 | Debt/Equity | IMPLEMENTADO | 22/22 |
| 9 | EPS | IMPLEMENTADO (2 métodos, verificados 9/9) | ver §9 |
| 10 | P/E | IMPLEMENTADO (1 camino fuerte + 1 camino débil) | 6/7 cadenas completas (YPFD = NULL por regla IAMC) |
| 11 | P/B | **NOT_IMPLEMENTED** | 0 — facts disponibles, falta cablear |
| 12 | P/S | **NOT_IMPLEMENTED** | 0 — ni siquiera declarado el concepto de mercado |
| 13 | EV/EBITDA | **NOT_IMPLEMENTADO** | 0 — falta declarar el concepto; el dato SI existe (corregido F-062) |

Cobertura de fundamentales (columna 2) recalculada tras corregir **F-056**
(ver §7): antes del fix, `current_ratio`..`ocf_to_net_income` daban **0/9** en
las tres empresas US-GAAP porque el script de inventario declaraba sus
propias listas de tags solo-IFRS en vez de usar el fallback de
`ratio_defs.py`. Detalle completo en `RATIO_VALIDATION_REPORT.md` §1.

---

## Ratios ya implementados fuera de la lista del encargo

El sistema también calcula `cash_ratio`, `borrowings_to_equity`,
`equity_ratio`, `interest_coverage`, `effective_tax_rate` y
`ocf_to_net_income`. Los primeros cuatro siguen exactamente las mismas reglas
de este contrato (concepto → tags → fallback → NULL con motivo). Los últimos
dos están **implementados pero marcados `publicable=False`** en
`ratio_defs.RATIOS`: el cálculo es correcto y aun así no es una métrica de
screener sin una banda de sanidad (`effective_tax_rate` = 188% en YPF 2025,
`ocf_to_net_income` = −6.0 cuando el resultado neto es negativo — el signo
invierte la lectura). Quedan en `REVIEW_REQUIRED`, fuera del screener, hasta
que el contrato defina esas bandas. Ver `SCREENER_CONTRACT_V1.md` §6.
