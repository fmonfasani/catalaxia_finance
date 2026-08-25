# Informe de Pre-Certificación — O2/G9

**Fecha:** 2026-08-23
**Alcance:** gates de validación previos a re-certificación de la foto v3.
**Principio rector:** el ticker NO es la identidad (puente CIK ↔ CUIT ↔ ticker vigente); nunca degradar datos certificados.

---

## 1. Veredicto ejecutivo

La **foto certificada v3 sigue siendo la fuente de verdad** y queda intacta.
Los gates bloqueantes corren limpios o con hallazgos puntuales clasificados.
El pipeline M1 legacy (`s2→s4`) quedó **parcheado pero NO ejecutado**: correrlo
hoy habría degradado identidad y precios de los 17 ADRs (ver §2).

| Gate | Resultado | Estado |
|---|---|---|
| Rangos 52w fuera de rango | 91 → **0** | ✅ limpio |
| GATE-AR autoreporte ROE | 66 comparados, 13 desvíos >20% | ⚠️ señal real, listar |
| M3-C1 balance | 5.5% FALLA (CVH estructural) | ⚠️ puntual |
| M3-C2 continuidad YoY | 1.7% FALLA (huecos extracción) | ✅ aceptable |
| M3-C3 EPS dil/básico | 0.3% FALLA (4 casos reales) | ✅ aceptable |
| M3-C4 P&L (no bancos) | 0.3% FALLA (6 casos) | ✅ aceptable |

---

## 2. G9 — Identidad y namespaces (hallazgo principal)

Coexisten **tres namespaces** para las entidades con ADR:

| Namespace | Ejemplo YPF | Dónde vive |
|---|---|---|
| Canónico screener | `YPFD` | `dim_entity.ticker_canonico`, `dim_instrument` (BYMA, ARS) |
| Símbolo yfinance ADR | `YPF` | tabla `precios` (USD), mapa `ADR_YF[cuit]` en s3_precios |
| Clave sintética | `_ADR_9979` | `ratios_cnv.ticker` (generación actual de s2) |

**Hueco detectado antes de ejecutar:** `s4_ensamblar.py` lee `ratios_cnv.ticker`
crudo y resuelve precio con `precios.get(ticker)` sin fallback. Con las claves
`_ADR_XXXX` actuales, una corrida habría:
1. insertado claves sintéticas en `screener` (viola principio de identidad),
2. perdido el 100% de precios/PER/P/B/P/S/52w de los ADRs,
3. perdido el payout desde `facts` (join por ticker también roto).

Evidencia: `screener` tiene **0 filas `_ADR_%`** → s4 nunca corrió contra esta
generación de ratios_cnv; la tabla vigente es de una generación anterior sana.

**Parche aplicado (aditivo, compilado, no ejecutado):**
- `resolver_precio(cuit, ticker)`: prueba clave original → canónico → `ADR_YF`.
- `ticker_out = dim_entity.ticker_canonico` para INSERT y reportes.
- Lookup de dividendos con candidatos canon+ticker.
- Provenance registra `Precio@<símbolo>` cuando difiere del canónico.

**Decisión:** NO ejecutar s4 hasta O3 (consolidación del puente único vía
`dim_entity`/`dim_instrument`). La foto certificada usa su propia capa de
mercado (b4_mercado, consistente por diseño).

---

## 3. O2 — Validaciones ejecutadas

Script: `scripts/tickets/screener/_o2_validaciones.py` (solo lectura de
tablas certificadas; crea únicamente `o2_gate_roe`, `o2_arbitro_roe`,
`o2_m3_checks`). Resumen: `data/precert_o2_summary.json`.

### GATE-AR (autoreporte CNV vs calculado) — bloqueante
66 entidades comparables (ROE calc vs CNV_roe): **13 desvíos >20%**.
Detalle consultable en `o2_gate_roe`. Nota: convive con `gate_roe`
pre-existente (56 filas de corrida anterior) — no se tocó.

### ÁRBITRO 3 vías (calc / CNV / investing.com) — informativo
OK=45 · DESVIO_INVESTING=10 · DISCREPANCIA_CNV=10 · ambos=3 · SIN_ARB=4.
(ratios_externos: 27 filas investing.com, roe en % → /100).

### Checks M3 sobre cnv_reextract (65.560 filas, 72 CUITs)
Particionado por `tipo_balance` (perímetro individual/consolidado).
Ajustes de fidelidad al modelo de datos real, documentados en el script:

- **Cogs/D&A con signo** (convención EDGAR): identidad P&L = `revenue + cogs = gross_profit`.
  Verificado exacto en YPF FY25 (23.240 − 16.849 = 6.391 ✓).
- **Flujos trimestrales des-acumulados** (no YTD): continuidad evaluada
  YoY (mismo trimestre año previo), caída >70% = falla.
- **Bancos excluidos de C4** (intermediación financiera sin COGS semántico): 201 N/A.

| Check | OK | WARN | FALLA | Lectura |
|---|---|---|---|---|
| C1 balance | 1553 | 192 | 102 | CVH sistemático +140–160% (extracción seguros), HAVA +60%. Resto <20%. |
| C2 continuidad YoY | 1235 | — | 21 | Huecos leídos como revenue≈0 (CVH/CAAP −100% exacto), crisis 2019-20. |
| C3 EPS dil/básico | 1545 | — | 4 | Reales: CADO/RIGO/GCDI/CARC (diluido ~10x básico). |
| C4 P&L no-bancos | 1589 | — | 6 | GCDI mezcla de unidades (factor 1000), GCLA bordes, GGAL 48%. |

Informativos: C5 ebitda≈ebit−da → 16% desvío (líneas independientes en la
extracción, no hay identidad derivable). C6 cfo≈ni−da → 78% desvío
(esperable: falta ΔWC para cerrar el arco).

---

## 4. Refresh rangos 52 semanas

Scripts: `_refresh_rangos_52w.py` + `_retry52w_ba.py`.
Solo UPDATE de `year_high/year_low` en la fila más reciente por ticker;
nunca toca precio/mcap ni inserta filas.

- Baseline: **91 tickers fuera de rango** (precio fuera de [ylow, yhigh]).
- Refrescados vía yfinance fast_info: 560 (USD/genéricos) + 101 (locales `.BA`).
- Fallo único: DGCE (sin datos en Yahoo).
- Post-refresh: **0 tickers fuera de rango.**

Los fallos iniciales confirmaron el G9: los sintéticos `_ADR_XXXX` no existen
en Yahoo y los locales ARS requieren sufijo `.BA`.

Log: `data/precert_refresh52w.json`.

---

## 5. Brechas conocidas restantes (para O3)

1. `silver_norm` y `certificacion_nueva` contienen solo TXAR — el suite M3
   original nunca se generalizó a la tabla certificada (este O2 lo cubre
   sobre cnv_reextract como puente).
2. BMA sin balances CNV; CAAP pendiente de descarga 6-K; investing.com de
   carga manual (27 entidades).
3. Fórmula Max52w en s4 usa base precio (`yhigh/precio − 1`) mientras el
   contrato define `(p − h)/h` — harmonizar en O3 antes de unificar capas.
4. Filas residuales en `precios` con claves `_ADR_XXXX` (17) y locales sin
   `.BA` — migración a namespaces canónicos pendiente.
5. Ejecutar s4 parcheado solo tras aprobar consolidación O3.

## 6. Artefactos

- `scripts/tickets/screener/_o2_validaciones.py` (+ tablas `o2_*`)
- `scripts/tickets/screener/_refresh_rangos_52w.py`, `_retry52w_ba.py`
- Patch G9 en `scripts/tickets/screener/s4_ensamblar.py`
- `data/precert_o2_summary.json`, `data/precert_refresh52w.json`
