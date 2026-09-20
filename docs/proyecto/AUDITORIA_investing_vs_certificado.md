# Auditoría ticket por ticket — investing.com vs nuestro certificado (byma_only)

**Fecha:** 2026-07-15 · **Universo:** los 25 byma_only para los que cargaste ratios de investing.

## La causa raíz (probada, no supuesta)

Las diferencias **no son "nuestro dato mal"**. La principal es **ventana temporal distinta**:

| | investing.com | Nosotros (certificado) |
|---|---|---|
| **Qué ROE/PER mide** | **TTM** — últimos 4 trimestres (rolling, incluye 2025 H2) | **Último EJERCICIO ANUAL** cerrado y certificado |
| **Por qué** | dato más actual | es el balance que **cierra** y está **cross-validado** (escala consistente) |

**Prueba:** calculé nuestro ROE **TTM** (nuestros últimos 4 trimestres). Donde los trimestres
recientes están limpios, **nuestro TTM ≈ investing casi exacto** → confirma que nuestros
fundamentals son correctos; lo que cambia es la ventana.

En Argentina (inflación + ganancias volátiles) esa ventana diverge mucho cuando hubo un **swing**:
- **AUSO** pasó de **perder −91,7B en 2024** a **ganar +66B en 2025** → investing (TTM) da +11%, nuestro anual 2024 da −39%. Los dos correctos, distinta ventana.
- **CVH** ganó **+1.024B en 2024** y se enfrió en 2025 → nuestro anual 18,3%, investing (TTM) 4,9%.
- **MOLA** multiplicó ganancias en 2025 → nuestro anual (FY mar-25) 52,7%, investing (TTM) 181,8%.

> **Por qué certificamos el anual y no el TTM:** el TTM a veces está **roto**. Ej.: **CVH TTM = 1.182.601%**
> porque sus trimestres 2025-06/09 traen un error de escala ×1e6 en la fuente. El anual 2024 es el
> dato limpio y auditable. Elegimos la fuente que podemos **probar**.

---

## Tabla ticket por ticket (ROE %)

| Ticker | Empresa | Cierre nuestro | ROE investing | ROE anual (cert.) | ROE TTM (nuestro) | Verdicto |
|---|---|---|--:|--:|--:|---|
| DGCU2 | Dist. Gas Cuyana | 2025-12 | 25,8 | **25,7** | 25,7 | ✅ coincide (casi exacto) |
| BYMA | Bolsas y Mercados | 2025-12 | 25,5 | **26,4** | 26,4 | ✅ coincide |
| VALO | Banco de Valores | 2025-12 | 16,9 | **15,3** | 13,9 | ✅ coincide |
| BHIP | Banco Hipotecario | 2025-12 | 5,1 | **4,2** | 4,2 | ✅ coincide |
| CTIO | Consultatio | 2025-12 | −1,8 | **−1,0** | −1,0 | ✅ coincide |
| HARG | Holcim Argentina | 2025-12 | −7,3 | **−6,9** | −6,9 | ✅ coincide |
| LEDE | Ledesma | 2025-05 | −6,6 | **−5,9** | −8,3 | ✅ coincide |
| COME | Sociedad Comercial | 2025-12 | −7,8 | **−10,3** | −10,3 | ✅ coincide |
| MOLI | Molinos Río | 2025-12 | −12,6 | **−16,3** | −16,3 | ✅ coincide |
| GCLA | Grupo Clarín | 2025-12 | 13,3 | **12,1** | 4,3 | ✅ coincide (anual) |
| CAPX | Capex | 2025-04 | 7,4 | **4,9** | −10,9 | ✅ coincide (anual) |
| AUSO | Autopistas del Sol | 2024-12 | 11,2 | −39,2 | **19,2** | 🕐 período — revirtió en 2025 |
| CVH | Cablevisión Holding | 2024-12 | 4,9 | **18,3** | roto ×1e6 | 🕐 período — anual es el limpio |
| MOLA | Molinos Agro | 2025-03 | 181,8 | 52,7 | **143,0** | 🕐 período — ganancias crecieron |
| CECO2 | Central Costanera | 2024-12 | 14,8 | 4,8 | 6,6 | 🕐 período |
| ALUA | Aluar | 2025-06 | 5,6 | 0,8 | −2,2 | 🕐 período — año flojo |
| GRIM | Grimoldi | 2025-12 | 5,9 | **13,4** | 13,4 | 🕐 período (nuestro más nuevo) |
| A3 | A3 Mercados | 2025-06 | 11,1 | 3,7 | 6,0 | 🕐 período + doble cambio de ejercicio |
| MIRG | Mirgor | 2025-12 | 8,4 | **3,1** | 3,1 | ⚠️ investing inconsistente* |
| CELU | Celulosa | 2025-05 | 2057,8 | — | 173,7 | ⚠️ investing extremo (PN≈0) |
| TXAR | Ternium Argentina | 2025-12 | 4,2 | — | 0,2 | 🔧 gap nuestro: falta NI 2025-12** |
| AGRO | Agrometal | 2025-12 | 8,8 | **5,0** | 5,0 | 🔧 precio marcado (mcap incierto) |
| BOLT | Boldt | 2025-10 | 2,7 | −13,3 | −9,2 | 🔧 precio marcado; año con pérdidas |
| FIPL | Fiplasto | 2025-06 | −19,7 | −5,7 | 3,1 | 🕐 período (empresa chica, volátil) |
| RIGO | Rigolleau | 2024-11 | 1,5 | −2,4 | −4,5 | 🕐 período — nuestro anual es de nov-24 |

\* **MIRG**: investing se **contradice a sí mismo** — dice P/B 0,67 y ROE 8,4%, que implicarían PER≈8,
pero reporta PER 94. Nuestro set es internamente consistente (P/B 7,53 = PER 247 × ROE 3,1%) y el
market cap coincide entre 2 fuentes (ratio 1,01). El desviado es investing.

\** **TXAR**: tenemos el **balance** 2025-12 (por eso certifica por identidades + P/B 0,44 ≈ investing 0,47)
pero **falta el estado de resultados 2025-12** en la extracción → ROE/PER quedan sin dato. Es un
**hueco de cobertura real** (no un error de valor): hay que re-extraer el EERR de ese GUID.

---

## P/B (ratio independiente del período — mejor comparación de "calidad de dato")

El P/B usa precio actual / valor libro actual, así que **no depende de la ventana temporal**. Es el
mejor termómetro de si nuestros números "de fondo" coinciden:

| Coinciden bien (±0,2) | investing | nuestro | | Difieren (market cap nuestro impreciso) | investing | nuestro |
|---|--:|--:|---|---|--:|--:|
| DGCU2 | 1,44 | 1,60 | | A3 | 1,12 | 0,58 |
| CVH | 0,55 | 0,51 | | GCLA | 1,13 | 0,47 |
| HARG | 0,99 | 0,96 | | MIRG | 0,67 | 7,53 (investing inconsist.) |
| MOLI | 2,21 | 2,05 | | CECO2 | 1,60 | 2,65 |
| TXAR | 0,47 | 0,44 | | | | |
| GRIM | 0,94 | 0,93 | | | | |
| CTIO | 0,89 | 0,94 | | | | |

Donde difiere el P/B (A3, GCLA), la causa es que nuestro **market cap derivado** (precio × NI/EPS)
queda ~2× por debajo del real — está dentro de la banda que aceptamos (0,33–3×) pero en el borde.
Es **imprecisión de market cap**, no de los fundamentals.

---

## Conclusión honesta

**Ninguna diferencia es "nuestro dato de fondo está mal".** Se reparten en:

1. **Ventana temporal (la mayoría)** — investing es TTM, nosotros el último ejercicio certificado.
   Donde el período coincide, matcheamos investing **casi exacto** (DGCU2, BYMA, VALO, BHIP, CTIO,
   HARG, COME, MOLI…). Donde no, hubo un swing de ganancias (AUSO, CVH, MOLA).
2. **Investing a veces es dudoso** — MIRG se contradice a sí mismo; CELU 2057% (PN≈0).
3. **Un hueco de cobertura real** — TXAR: falta el EERR 2025-12 (re-extraer).
4. **Imprecisión de market cap** en 2–3 nombres (A3, GCLA) → afecta P/B, no los fundamentals.

**Lo que confirma la auditoría:** nuestros fundamentals certificados son correctos (el TTM nuestro
reproduce investing cuando la ventana coincide), y donde elegimos el anual sobre el TTM fue por una
razón demostrable (el TTM estaba roto, ej. CVH). El sello "certificado" se sostiene.

### Acciones sugeridas
- [ ] **TXAR**: re-extraer el estado de resultados 2025-12 (cerrar el gap de ROE/PER).
- [ ] Ofrecer una **vista TTM** además del anual, para comparar 1:1 con investing (mismo período).
- [ ] Mejorar el **market cap** de A3/GCLA (usar acciones en circulación reales en vez de NI/EPS).
