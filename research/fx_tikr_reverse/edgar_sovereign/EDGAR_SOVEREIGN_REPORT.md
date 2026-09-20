# EDGAR ARGENTINA SOVEREIGN BONDS — FX EVIDENCE RESEARCH
Rama `feature/fx-research-engine` · 2026-09-15 · `research/fx_tikr_reverse/edgar_sovereign/`
Capas: FUENTES/RAW = filings + FTS · IDENTIDAD = TABLA 1 · PARSED = evidence.jsonl ·
NORMALIZED/ECONOMIC FACTS = TABLAS 2,5,6 · FINANCIAL MODEL = TABLAS 3,4 ·
PROVENANCE = .meta.json + columnas provenance · VALIDACIÓN = engine_tests (37 passed) ·
CERTIFICACIÓN = este informe (investigación, NO veredicto TIKR).

## HOY (evidencia encontrada, VERIFICADO POR FUENTE SEC) vs OBJETIVO (universo 2001–2026)

HOY = 11 documentos en 9 accessions + 40 ventanas FTS (36+4 reintento). OBJETIVO =
cobertura total del universo §2 (ver gaps J). Nada fuera de HOY se afirma.

## Respuestas 1–17

1. **Instrumentos con evidencia a nivel filing**: AL30, GD30, GD35, GD38, GD41
   (ISIN verificados), BONCER, LECAPS/LEFIS (narrativa), BODEN 2007/2008/2011/2013/2012,
   BOCON Prov/Prev, PAR/DISCOUNT/CUASIPAR pesos. Sólo mención: trust-AL30 (BBVA),
   canje-2020 (18-K/A). Sin documento revisado: LETES, LEBAC, BONCER-precio,
   AL29/GD29, AL35/GD35-precio, AL38/AE38/GD38-precio, AL41, GD46, GLOBAL otros.
2. **Filings**: GGAL 20-F 2024 + exhibit4_4 · Macro 20-F 2024 · CEPU 6-K 2023-12-05 ·
   Telecom 6-K 2024-11-11 · SUPV 6-K 2026-05-27 · BBVA 6-K ex99-1 2026-08-10 ·
   Argentina 18-K 2008-02-20 + 18-K/A 2020-09-14 · Banco Rio 6-K 2003-04-22.
3/4/5/6. **Fechas/valores/moneda/mercado**: TABLA 2 (9 obs.): 4 precios ARS de
   cierre 2023-11-30 (GD30 328.50, GD35 295.01, GD41 297.80, GD38 358.99 por 1 VN;
   mercado NO_DETERMINABLE — plaza no nombrada); 2 duales (V05, V06); 1 carrying
   AL30; 1 fair-value agregado BONCER; 1 nominal soberano 2006.
7. **¿Valor ARS?** Sí: V01–V04, V05 (reserva), V06, V07.
8. **¿Valor USD?** Sí: V05 (nominal US$145.6M), V06 (US$36M y componentes).
9. **¿Precio?** Sí ARS (V01–V04). Ningún precio USD de instrumento en EDGAR revisado.
10. **¿Fair value?** Agregado BONCER (V08, sin precio); AL30 a costo amortizado/ORI
    (V07). Fair value ≠ market price (no se convierte).
11. **¿Operación USD→ARS?** NO_EVIDENCE_FOUND (TABLA 4, fila CX00 explícita).
12. **¿FX explícito?** Sí, 10 registros (TABLA 5): BCRA referencia 1032.50/808.4833/
    177.1283 (GGAL), A3500 1078.38/102.75 (Macro), oficial 366→800→808→1032,
    mercado 1172.80 (bandas 1000–1400), BNA vendedor 2023-11-30 (fuente+fecha, valor
    NO_DETERMINABLE en el filing), oficial Ps.1.40 ene–feb 2002 (18-K).
13/14. **¿FX implícito calculable?** Dos, con fórmulas y reparos (§15):
    FX01 = 37157/36 = **1032.14** ARS/USD (posición neta, millones redondeados,
    banda ±~15; el filing usa 1032.50 para trasladar);
    FX02 = 115725101466/145602795 = **794.79** ARS por USD-1-nominal
    (base carrying, NO es FX de mercado). CEPU: NO calculable sólo-EDGAR (falta pata USD).
15. **Evidencia primaria**: URLs SEC + fragmentos exactos en TABLAS 2/3/5 y
    `parsed/evidence.jsonl` (281 ventanas) + RAW íntegro en `raw/filings/`.
16. **Utilizables para Catalaxia**: X01–X08/X10 (tasas de referencia oficiales con
    fecha — calibración/validación de series); V01–V04 (pata ARS fechada con ISIN —
    lista para cruzar con pata USD secundaria marcada); E3b (fórmula contractual
    Implicit Exchange Rate GD30/AL30 — metodología de mercado); T1 (ISIN/legislación).
17. **NO utilizables y por qué**: TABLA 6 (6): menciones sin valores, agregados sin
    precio, nominales (face≠price), queries sin documento revisado.

## Output ejecutivo A–L

- **A.** Filings revisados: 11 documentos / 9 accessions (+40 ventanas FTS).
- **B.** Instrumentos con evidencia filing-level: 15 (TABLA 1).
- **C.** Con precio: 4 (V01–V04, ARS).
- **D.** Con USD+ARS: 2 (V05 carrying, V06 posición).
- **E.** Con FX explícito: 10 registros (8 valores + 1 fuente-fechada + 1 histórico).
- **F.** Con FX implícito calculable: 2 (FX01 posición, FX02 carrying).
- **G.** Cross-market: 0 (declarado, no silencio).
- **H.** Período cubierto: 2002 (tasa 1.40) · 2003–2008 (BODEN/deuda) · 2020 (canje, mención) ·
  2023-11-30 (precios) · 2024-2026 (20-F/6-K). Gaps: 2004–2007 EEFF, 2009–2019
  profundo, 2020–2022 precios, AL29/GD29/AL35/AL38/GLOBAL-otros.
- **I.** Mejores evidencias: (1) GGAL Implicit Exchange Rate (fórmula contractual
  VWAP ARS/VWAP USD GD30/AL30 + ISINs ARARGE3209S6/US040114HS26);
  (2) CEPU 4 precios ARS con fecha+ISIN; (3) GGAL/Macro tasas BCRA/A3500 fechadas;
  (4) Telecom dual nominal-reserva; (5) 18-K 2008 (stock BODEN + 1:1/1.40).
- **J.** Gaps: prospectos 424B2/F-3 soberanos (CUSIP/cupón/ISIN por emisión);
  LETES/LEBAC/LECAP/BONCER precio-nivel; 2009–2019; pata USD de V01–V04;
  plaza de “closing of operations” CEPU; valor tasa BNA 2023-11-30.
- **K.** NO_DETERMINABLE: plaza CEPU; tasa BNA numérica; market price USD en EDGAR;
  cross-market; ISIN/CUSIP/FIGI no citados (NULL, no inferidos); correlación con
  metodología TIKR (fuera de alcance de este informe).
- **L.** Recomendaciones: (1) prospectos soberanos 424B2/F-3 (identidad completa
  por emisión incl. AL29/GD29/AL35/38/41/46); (2) top-hits LETES/LEBAC/BONCER
  2015–2019; (3) 20-F bancarios 2009–2019 (BODEN/BONAR holdings + FX);
  (4)does 18-K 2021–2024 (stock post-canje); (5) cruzar V01–V04 con USD
  secundario marcado (fuera de EDGAR); (6) verificar plaza CEPU contra aviso BYMA.

## Calidad y reglas (§14–§18)

QC por observación en TABLA 2 (vocabulario cerrado; notas en `caveats`).
Provenance §15 por cálculo en TABLA 3 (valores fuente + fórmula + filings).
Distinciones §6 respetadas: fair≠market (V07/V08 no promovidos), face≠price (V09),
EDGAR≠cotización EEUU (ningún print USD de mercado afirmado), AL30≠AL30D
(identidad por ISIN/rol, no por nombre). Faltantes = NO_DETERMINABLE.
Reproducir: `scripts/fts_sweep.py` → `dl_filings.py` → `extract.py` →
`build_tables.py` → `pytest engine_tests/ tests/` (37 passed).
