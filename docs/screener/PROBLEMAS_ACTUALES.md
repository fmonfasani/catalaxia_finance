# Problemas actuales del screener — mapa de situación

> Inventario completo de problemas **abiertos** del screener v2 (72 empresas argentinas),
> cruzado por ratio / tipo de dato / fuente / scope. Sirve para saber dónde estamos parados
> y priorizar. Ver contexto en [RETOMAR_AQUI.md](RETOMAR_AQUI.md).

Última actualización: 2026-07 (post fix PER + validación cruzada "doble-nelson").

---

## ✅ Ya resueltos (contexto — no requieren acción)
- **Unidad MILES/Millones de $** (el bug que causaba la staleness) → `factor_unidad()`.
- **Staleness** 16/72 → 1/72.
- **PER** roto (era `market_cap/NI` con shares inconsistentes) → recalculado **per-share**.
- **Payout year-alignment** (inflaba, ej. TXAR 149%) → ventana 12m alineada al cierre fiscal.
- **Clave cruzada** (cik=CUIT vs BYMA-*) → v2 usa claves canónicas.
- **CAGR vintage** (mezcla de reexpresión NIC 29) → deflactado por IPC INDEC (CAGR real).

---

## 1. Por RATIO (los 13)

| Ratio | Estado | Problema abierto |
|---|---|---|
| Precio · Máx/Mín 52s · difs | ✅ | 3 sin precio (BOLT_2, PATA_2, _ADR_8309) |
| **PER** | 🟡 arreglado | depende de `shares = NI/EPS` (inestable en algunos); cob. 33/72 |
| **Deuda/EBITDA** | ✅ converge | bancos no confiables (plantilla financiera) |
| **EPS anual** | 🟡 | _ADR_0580 EPS roto (implica 258 billones de acciones) |
| **CAGR EPS 5y** | 🟡 real | CAGR_EPS ≠ CAGR_NI en 40/72 (shares cambian); cob. 46/72 |
| **Margen Neto / ROE** | 🟡 calc sano | referencia `CNV_*` rota (no validable); bancos off |
| **FCF/CE** | 🟡 | CF_Op/NI > 10x en 6 entidades; INVJ/DOME/VALO sin CF |
| **Payout** | 🟡 | cash-basis aprox, 34/72, sin cross-validación |

---

## 2. Por TIPO DE DATO

| Tipo de dato | Problema | Ratios que toca |
|---|---|---|
| **Acciones (shares)** | derivadas de NI/EPS → inestables en 40/72; _ADR_0580 absurdo | P/B, P/S, PER, EPS |
| **Ratios pre-calc CNV (`CNV_*`)** | **rotos** — muestran valores del v1 (TXAR 85%, BHIP 307%). Inservibles como ancla de validación | validación de ROE/ROA/Margen |
| **Flujos de caja (CF)** | faltan en INVJ/DOME/VALO; CF_Op/NI anómalo (NI≈0 probable) | FCF/CE |
| **Ventas (Revenue)** | _ADR_2807 = 80K (corrupto) | Margen, P/S |
| **Balance (stocks)** | identidades OK salvo 7 (casi todas ADR) | ROE, P/B, D/EBITDA |
| **Dividendos** | parcial, cash-basis, sin cross-source | Payout |
| **Precio / market cap** | market_cap de yfinance con shares inconsistentes (sorteado con per-share) | PER, P/B, P/S |

---

## 3. Por FUENTE

| Fuente | Estado / problema |
|---|---|
| **CNV (fundamentales)** | Unidad ✅. **Pero:** bancos usan plantilla financiera distinta (ROE/Margen off); `CNV_*` pre-calc rotos; template sin columna comparativa ni fecha de reexpresión |
| **yfinance (precios + algún dividendo)** | shares del market_cap inconsistentes; 3 sin precio; moneda ADR (USD vs ARS) |
| **EDGAR (US/ADR)** | existe pero **NO unificado** con el screener argentino |
| **Cruce de fuentes** | payout CNV vs yfinance = **0 pares** solapados (no se pueden cruzar) |

---

## 4. Por SCOPE (clasificación por impacto)

### ✅ RESUELTO — `CNV_*` referencia rota
Confirmado (2026-07): el parser de la sección de ratios **mal-asocia los códigos con sus
valores** (ej. TXAR `CNV_margen_neto=0.85` es en realidad la solvencia Eq/As≈0.90, no el
margen 3.3%). Los `CNV_*` son inservibles como ancla. **Decisión: descartados** como ancla
de validación y como fallback de bancos. La fuente de verdad son los **conceptos crudos**
(pasan las identidades contables). Las "100 divergencias vs CNV_*" del doble-nelson NO son
bugs nuestros. Validación real = identidades + DuPont + rangos sanos.

### 🔴 Sistémicos abiertos (afectan a muchos — hay que DECIDIR)
- **Bancos** (BHIP, BPAT, Galicia, Macro, BBVA, Supervielle): plantilla financiera → sus
  fundamentales CNV son poco confiables (ni siquiera tenemos el `CNV_*` como referencia).
  Necesitan parser bank-aware o fuente alternativa (yfinance/EDGAR), flageados.
- **Shares inestables** (CAGR_EPS ≠ CAGR_NI en 40/72) → roza P/B, P/S y CAGR (usan NI/EPS).

### 🟠 Individuales (pocas entidades — limpieza puntual, casi todos ADR-placeholders)
- **_ADR_0580**: shares 258 billones (EPS roto) → valuación basura.
- **_ADR_2807**: Revenue = 80K con GP=67B → dato corrupto.
- **INVJ / DOME / VALO**: falta CF → sin FCF/CE ni payout confiable.
- **CF_Op/NI > 10x**: CTIO (68x), MIRG (13.5x), VALO (16.8x), _ADR_0899 (846x), _ADR_1735 (61x),
  _ADR_8309 (72x) → probablemente NI≈0 (denominador chico).

### 🟡 Limitaciones inherentes (NO son bugs — son decisiones honestas)
- Payout cash-basis parcial (34/72). CAGR requiere ≥5 años de serie (46/72). ADR-placeholders
  sin data CNV. 3 sin precio en yfinance.

### ⚙️ Infraestructura / pendientes
- **DB (754MB) no está en GitHub** → copiar a mano para trabajar en otra máquina.
- **v2 + fix PER commiteados pero SIN pushear.**
- **556 no extraídas** (solo el subset de 72). Pipeline listo con la mini-whitelist.
- **EDGAR (US/ADR) no unificado** con el screener argentino.

---

## Dónde estamos parados (resumen)
**El núcleo está sólido**: fundamentales limpios (identidades cierran, D/EBITDA converge,
EPS_diluido OK), PER arreglado, staleness muerta, CAGR real. Lo que queda:
- **3 temas sistémicos** para decidir (ancla CNV_*, bancos, shares).
- **~6 bugs individuales** para limpiar (casi todos ADR-placeholders).
- **Infraestructura** (push + DB para otra máquina).

Nada rompe el screener; son datos puntuales + decisiones, no un problema de fondo.

## Orden de ataque sugerido
1. ~~Decidir el ancla CNV_*~~ ✅ **HECHO** (descartado — parser de ratios mal-asocia códigos).
2. **Limpiar los ~6 bugs individuales** (ADR-placeholders + CF faltantes) — barato, mejora cobertura. ← siguiente
3. **Bancos**: decidir fuente (yfinance/EDGAR vs parser bank-aware) → flag claro.
4. **Shares/CAGR**: confirmar si es cambio real de acciones o inconsistencia EPS/NI.
5. Recién con eso: (ya pusheado el v2) expansión a las 556 + unificación EDGAR.
