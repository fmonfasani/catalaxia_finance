# YPF S.A. — Auditoria FULL de SEC EDGAR (piloto)

**CIK 0000904851 · Ticker ADR: YPF (NYSE) · SIC 2911 · FYE 31-dic**
Fecha: 2026-08-23 · Alcance: universo completo de datos XBRL/iXBRL de los 20-F de YPF.

## Respuesta directa (los numeros concretos)

Para YPF, EDGAR nos permite obtener:

| Metrica | Valor |
|---|---|
| Filings 20-F | **16** (FY2010–FY2025) |
| Filings con XBRL | **9** (FY2017–FY2025) |
| Documentos XBRL parseados | **9** |
| Taxonomias (familias) | **5** (ifrs-full, ypf-custom, dei, srt, us-gaap) |
| Tags unicos | **3019** |
| Tags standard | **555** |
| Tags custom YPF | **2464** |
| Observaciones numericas (filings, sin dedup) | **46111** |
| — con dimensiones | **35482** (77%) |
| Observaciones Company Facts | **5390** |
| Contextos XBRL | **17496** |
| Filas dimensionales | **31565** · 117 ejes · 1133 miembros |
| Unidades | **262** declaradas · 64 medidas distintas (ARS, USD, shares, MMBbls, Bcf, MMBoe…) |
| Relaciones XBRL | **61847** arcs (pre 23380 · cal 2119 · def 20253 · lab 16095) |
| Anios historicos | **2013–2025** via comparativos; filings XBRL FY2017–FY2025 |
| Conceptos utiles para los 13 ratios | **224** candidatos mapeados |
| Lo que usa HOY nuestro extractor | **4 conceptos** de 32 buscados |

## Hallazgo central

El pipeline consume **Company Facts** buscando 32 nombres *us-gaap* dentro del
esquema *ifrs-full*. Solo 4 existen con ese nombre (GrossProfit, ProfitLoss,
Assets, Liabilities): **las otras 28 —Revenue, NetIncome, EPS, Equity, Deuda,
Flujo operativo, Capex, Dividendos— no se descargan**, pese a estar todas en
EDGAR bajo nombres IFRS correctos (`ifrs-full:Revenue`,
`ifrs-full:ProfitLossAttributableToOwnersOfParent`, `ifrs-full:Borrowings`, etc).

Ademas, el **77% de las observaciones del filing es dimensional** (segmentos,
areas, sociedades, moneda funcional): eso **nunca** aparece en Company Facts;
solo se obtiene parseando las instancias XBRL crudas — ya descargadas y
preservadas en `data/raw/edgar_pilot_ypf/`.

## ¿Hay que re-descargar?

**No.** Todo el universo 20-F FY2017–FY2025 ya esta en RAW con SHA256
(ultima filed reflejada en Company Facts: 2026-03-26). Falta **normalizar** lo
descargado (instancias + dimensiones), no volver a bajarlo. Fuera de alcance
EDGAR: precios y maximos/minimos 52 semanas (siguen siendo yfinance).

## Riesgos detectados para la extraccion definitiva

1. **Moneda de presentacion:** ARS hasta 20-F FY2021, USD desde FY2022.
   Mezclar series sin reexpresar = datos falsos.
2. **Layouts variables:** FY2017–FY2020 instancia XML separada; FY2021 solo
   `-xbrl.zip`; FY2022–FY2024 iXBRL `_htm.xml`; **FY2025 linkbases embebidos
   en el .xsd**.
3. **Pre-XBRL:** FY2010–FY2016 sin XBRL (7 filings).
4. **Lag de Company Facts** vs submissions.
5. **6-K sin XBRL financiero**: no hay TTM trimestral estructurado en EDGAR.
6. **Disagregacion creciente:** desde FY2023 el revenue desagregado dimensional
   explota (237–268 facts/anio).

## Entregables

- `data/audits/YPF_EDGAR_FULL_DATA_AUDIT.xlsx` — 18 hojas.
- `data/raw/edgar_pilot_ypf/` — RAW intacto con `_manifest.csv`
  (HTTP status, bytes, SHA256, fecha UTC por archivo).
- Scripts reproducibles en `scratchpad/ypf_edgar_audit/`.
