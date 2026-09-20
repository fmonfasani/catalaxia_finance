# CONTRATO DE DATOS — Fundación robusta (DRAFT v0, 2026-07-14)

> Este documento es un **contrato**, no una sugerencia. Toda implementación futura se mide
> contra esto. Si algo no cumple el contrato, no se guarda en la base.

## Principio rector
**El dato es nuestro mayor capital.** Cuando un dato se guarda en la base, ya tiene que ser
**íntegro, coherente, consistente y completo**. No se persiste basura para "arreglarla después".
La fundación es **robusta, sistemática, reproducible y trazable**.

## Prompt original del usuario (verbatim, para no perder intención)
> Quiero algo robusto, sistemático, reproducible, trazable. La mayor cantidad de datos (tags),
> tanto en tags como en fechas/trimestres. Trimestres Y anuales, independientemente de si están
> listadas en la SEC o en BYMA — ya sea fuente SEC EDGAR o CNV. Los datos normalizados para ser
> lo más similares a investing (no idénticos, sino comparables: tener en cuenta el fundamento
> financiero — ej. millones vs miles; algunos ratios anulan la unidad por la división, pero hay
> ratios donde importa). Una vez con la base, correr un cron/job para actualizar: ~500 acciones
> USA y ~75 de Argentina. Precios: BYMA en pesos Y en dólares CCL (dos precios); los ADR tienen
> precio real en USD y precio en BYMA (ARS) — investigar si usamos CCL para que sean comparables.
> Automatizar las descargas de SEC EDGAR y BYMA (empresas US y ADR argentinos que cotizan en US),
> y herramientas para job/cron/scripts para descargar sistemáticamente todos los EEFF de la CNV.
> Comparar todos los tickers, ver cuál está actualizado (EEFF trimestral o anual), actualizar lo
> que falta y actualizar la tabla con el pre-procesamiento correspondiente para que el dato sea
> de calidad investing, íntegro y comparable. Que cuando se guarde el dato ya sea íntegro,
> coherente, consistente y completo.

---

## 1. Alcance de datos
- **Universo:** ~500 US (S&P 500) + ~75 argentinas (byma_only + ADR argentinos). Incluir ADR
  argentinos que cotizan en US (Galicia, Pampa, Telecom, YPF, etc.).
- **Fuentes:** SEC EDGAR (XBRL, US-GAAP/IFRS) **y** CNV (AIF, normas CNV). Se trae el
  dato **exista donde exista**, sin importar en qué mercado cotiza. Si una empresa está en ambas,
  se guardan ambas y se reconcilian.
  - ⚠️ **La moneda NO se asume por fuente.** Verificado (2026-07-14): **11 de 13 ADR argentinos
    reportan a la SEC en ARS** (GGAL, TEO, BBAR, SUPV, LOMA, TGS, IRSA, CEPU, CRESY, BMA, EDN);
    solo YPF y Vista van en USD. Incluso dentro de una misma empresa hay facts en ARS y en USD.
    → La moneda se lee **por-fact** del `unit` del XBRL. Nunca asumir "SEC = USD".
- **Cobertura temporal:** la máxima disponible. **Trimestral Y anual**, todos los períodos.
- **Tags:** la mayor cantidad posible. Se guardan **todos los tags crudos** + una **capa canónica**
  mapeada (no se descarta granularidad).

## 2. Arquitectura por capas (medallion)
| Capa | Qué | Reglas |
|---|---|---|
| **raw / bronze** | Tal cual la fuente | Inmutable. Con accession/docid, **hash**, timestamp de descarga, moneda, escala, form. Trazabilidad total |
| **parsed / silver** | Normalizado con contratos | Identidad única por entidad, unidad/escala explícita, moneda, período, vintage de reexpresión |
| **derived / gold** | Conceptos canónicos + ratios | Comparable a investing. Todo derivado rastreable a su raw |

## 3. Normalización (comparabilidad "investing")
- **Unidad/escala explícita** (millones vs miles): factor guardado, nunca adivinado. *(Ver anomalía
  real: GCLA con valores de 10³ a 10¹⁵ mezclados — esto no puede volver a pasar.)*
- **Moneda (RESUELTO Q2):** los financials se guardan en su **valor crudo, en la moneda que
  declara el propio dato** (`unit` del XBRL en SEC; ARS en CNV). **NO se asume por fuente** — SEC
  ADR argentinos son mayormente ARS (ver §1). **No** se atan a una unidad fija:
  la unidad/escala de comparación se determina **ticker a ticker según cómo lo muestra investing**
  (investigar caso por caso, especialmente los de BYMA; los de SEC van todos en USD). El raw se
  persiste con precisión completa (valor exacto) + metadato de escala; la comparación normaliza.
- **Identidad canónica:** un ticker/entidad por CUIT (AR) / CIK (US). **Fin del keying por razón
  social** (hoy los ADR están como "Pampa Energía S A" y los byma_only como ticker → rompe joins).
- **Vintage de reexpresión:** registrar `fecha_reexpresion` (inflación AR hace que trimestres
  viejos diverjan; el más reciente es el "verdadero").
- **RECPAM doble variante:** cada concepto afectado por RECPAM (NIC-29) se materializa en 2 —
  `incluye_recpam=true` (reportado) y `false` (neto del efecto). Ver `CONCEPTOS_canonicos.md §F`.
- **Conceptos canónicos:** set de ~40 (Revenue, COGS, GrossProfit, OpInc, EBITDA, D&A, EBIT,
  IntExp, PretaxIncome, Tax, NetIncome, Assets, CurrentAssets, Equity, Liabilities, Debt, Cash,
  CFO/CFI/CFF, EPS, shares…) + **ratios derivados** (PER, ROE, ROA, márgenes, D/E, EV/EBITDA…),
  mapeados desde SEC tags y CNV conceptos. *(Propuesta a revisar — Q5.)*

## 4. Precios (RESUELTO Q3)
- **only-byma:** `precio_ars` (BYMA) + `precio_usd = precio_ars / CCL`.
  - **CCL de mercado (RESUELTO):** con el bono **AL30 y AL30C** (Contado Con Liqui usa AL30C, NO
    AL30D que es MEP). Se descargan de Yahoo Finance. Se computa como pesos-por-USD (~$/USD) y se
    valida el resultado contra el CCL de referencia del día.
- **ADR argentino:** `precio_adr_usd` (real, NYSE/Nasdaq, Yahoo) + `precio_ars` (BYMA) +
  **CCL implícito propio** = `(precio_ars × ratio_adr) / precio_adr_usd`.
  - `ratio_adr` (RESUELTO): **ya existe en la tabla `adr_ratios`** (13, con source_url del 20-F).
- **US no-ADR (S&P 500):** `precio_usd` real (Yahoo Finance).
- **CCL** es el puente de comparabilidad cross-mercado: dos tipos → **CCL de mercado (AL30)** para
  only-byma, **CCL implícito por instrumento** para ADR.
- Método de CCL y `ratio_adr`: documentado y versionado.

## 5. Automatización (jobs / cron)
- **Descarga automatizada** SEC EDGAR (US + ADR argentinos) y CNV (EEFF AR).
- **Detección de frescura:** por cada ticker, saber cuál es el último EEFF (trimestral/anual)
  presentado, y **bajar solo lo que falta** (idempotente, sin re-descargar todo).
- **Pre-procesamiento en la ingesta:** el dato se guarda **ya** normalizado y validado.
- **Cadencia y deployment:** [Q4].

## 6. Validación (gates de calidad — nada entra sin pasar)
- **Contratos de esquema:** tipos, unidades explícitas, no-nulos donde corresponde.
- **Detección de anomalías:** escalas mezcladas, fechas fuera de trimestre (ej. 2024-11-08),
  saltos imposibles, Revenue negativo, duplicados.
- **Golden tests:** empresas de referencia que DEBEN reconciliar (ej. DGCU2, METR, AGRO).
- **Reconciliación automática vs investing** como control continuo.

## 7. Reproducibilidad / trazabilidad
- **Un comando** reconstruye todo desde `raw`.
- Cada dato derivado **rastreable** hasta su fuente (accession/docid + tag + timestamp + hash).
- **Log de ingesta** completo (qué, cuándo, hash, status).

---

## DECISIONES (estado)
- **Q1 — Backend DB:** ✅ **PostgreSQL**.
- **Q2 — Moneda/unidad:** ✅ Raw en moneda nativa (ARS de CNV, USD de SEC); unidad/escala **por
  ticker según investing** (no fija). *(Abre Q2b.)*
- **Q3 — Precios y CCL:** ✅ Ver sección 4. *(Abre Q3b, Q3c.)*
- **Q4 — Cadencia:** ✅ **Precios diario (post-cierre) + fundamentals disparados por nuevo filing.**

## DECISIONES (segunda ronda — RESUELTO)
- **Q3c — CCL:** ✅ **AL30 / AL30C** (Contado Con Liqui; AL30C). Descarga de Yahoo. Se
  valida que dé pesos-por-USD.
- **Q3b — `ratio_adr`:** ✅ **ya existe en `adr_ratios`** (no re-armar).
- **Q6 — Fuente de verdad ADR argentinos:** ✅ **SEC primaria** (más tags, mismo ARS) + CNV valida.
  *(Motivo: cuando SEC y CNV difieren para la misma empresa, hay que saber cuál se muestra; se
  muestra la más completa y la otra sirve de control.)*
- **Deploy:** ✅ **VPS más adelante** — no bloquea. Prioridad ahora: el **script del job**, no el deploy.

## Lo que hago yo (no requiere respuesta del usuario)
- **Q5 — Set canónico de ~40 conceptos + ratios** (propuesta a revisar).
- **Q2b — Escala por ticker:** **ticker por ticker contra investing**, viendo qué unidad usa cada
  uno (tarea de relevamiento, como la carga de `ratios_externos`/`eerr_externos`).

*Contrato v1: quedan pendientes solo las propuestas mías (Q5, Q2b) para revisión. Lo demás cerrado.*
