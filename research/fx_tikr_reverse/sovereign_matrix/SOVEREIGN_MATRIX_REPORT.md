# INFORME FINAL — Sovereign debt + FX research orchestrator

CAPA: cada componente con capa primaria (§16 del encargo; ver §10 Provenance).
PLANOS: DATOS (Discovery/RAW/Parsed/Normalized/Facts) · CONTROL (Provenance/Validación/Certificación) · EJECUCIÓN (scripts + este informe) · INFRAESTRUCTURA (rama feature/fx-research-engine + research_manifest.json).
CICLO: DEFINIR (universo §1 congelado + REQ-001..012 intactos) → CRITERIOS (00_DEFINIR, no tocados) → TESTS (56 passed antes de certificar) → IMPLEMENTAR (scripts reuse+faltantes) → EJECUTAR (81 ventanas FTS, 16 docs) → EVIDENCIA (tablas) → CERTIFICAR (NOT_CERTIFIED, ver §16) → CERRAR (este informe).
HOY: 16 documentos EDGAR en 12 accessions + 81 ventanas FTS + matriz de 9 observaciones + 26 identidades + 14 provenance + 4 cross-checks. Todo lo afirmado abajo sale de ahí.
OBJETIVO: matriz histórica 2001–2026 certificable por celda; lo no alcanzado queda NO_EVIDENCE_FOUND/NO_DETERMINABLE (válido §25), no inventado.
DECISIÓN: CERTIFICATION = NOT_CERTIFIED (matriz incompleta: cross-market 0, USD market 0/104, plaza 0) y TIKR = UNKNOWN (§21, sin inferencia por coincidencia).
EVIDENCIA: raw/fts/*.json (81) + raw/filings/*.htm (16 + metas) + parsed/evidence.jsonl (555) + tables/ + sovereign_matrix/*.csv/*.xlsx/*.parquet + research_manifest.json (SHA256 todo).

## 1. Executive Summary
Se identificaron 26 instrumentos (21 con ISIN/términos verificados), 9 observaciones con valores (4 precios ARS fechados, 2 duales ARS+USD, 1 carrying, 1 fair agregado, 1 nominal), 10 tasas FX explícitas, 2 cocientes implícitos (posición 1032.14, carrying 794.79 — ninguno es FX de mercado), 0 operaciones cross-market, 4 cross-checks SEC↔BCRA ≤0.05%. Nada permite certificar FX de mercado ni método TIKR. Suite 56/56 verde antes de certificar.

## 2. Universe
§1 congelado (25 series) + CAMBIO DE ALCANCE registrados como CANDIDATE (BOPREAL BPOC7/BPOD7, TV24 dólar-linked, New USD 2030/35/38/41/46). AL29/GD29/AL25/GD25: 0 hits (o FTS-gap documentado). GD46: sin hits post-2016.

## 3. Instruments discovered
TABLA1 (15) + extensión fase-2 (11): AL30/GD30/GD35/GD38/GD41 (ISIN), BONCER, LECAP, BODEN 07/08/11/12/13, BOCON, PAR/DISCOUNT/CUASIPAR, BPOC7/BPOD7, TV24, New 2030/35/38/41/46, USD 2021/2022, Discount 2033. CUSIP/FIGI: NULL en todo (ninguno consta en filings revisados — no inferidos).

## 4. Identity coverage
21/25 = 0.84 con ISIN o términos verificados. Equivalencia AL30↔GD30: EQUIVALENT_ECONOMIC (misma emisión, distinta ley/especie; ISIN distintos). Resto de pares local/internacional: CANDIDATE.

## 5. ARS price coverage
1/104 quarters (2023-11-30, CEPU ×4, con ISIN, plaza NO_DETERMINABLE → SUPPORTED).

## 6. USD price coverage
0/104. Ningún precio USD de instrumento en EDGAR revisado (ni prospectos, que dan términos, no prints).

## 7. Explicit FX
10 registros (TABLA5): BCRA 1032.50/808.4833/177.1283, A3500 1078.38/102.75, oficial 366→800→808→1032, mercado 1172.80 (bandas), BNA vendedor (fuente+fecha, valor E-grade), oficial 1.40 (2002).

## 8. Implicit FX
FX01 1032.14 (posición, banda ±~15; filing usa 1032.50) · FX02 794.79 (carrying, no mercado) · FX04 NO_DETERMINABLE (falta pata USD) · FX03 fórmula sin print. Comparabilidad verificada por checklist (fx_observations.csv).

## 9. Cross-market cases
0 casos; 1 falso positivo removido (Ternium chatarra); 1 near-miss clasificado ACCOUNTING_TRANSLATION (GGAL-HSBC). cross_market_cases.xlsx/csv.

## 10. Provenance
14 datos graduados A–E (8×A, 1×B, 2×C, 1×D, 2×E) + cross_validation (4, sin elegir conveniente: +0.50/+0.0333/−0.0317) + 5 artefactos internos marcados (§14). RAW inmutable con sha256+URL+fecha en 97 archivos.

## 11. False positives removed
Ternium (commodity), agregados FVTPL/quoted-price P&L (no son prints), menciones trust-AL30 y canje-2020 (no son evidencia), queries amplias sin documento (no son hallazgos).

## 12. Coverage metrics
coverage_report.json/md: identidad 0.84 · ARS 0.0096 · USD 0.0 · mercado 0.0 · FX explícito 8 fechas · implícito-mercado 0 · cross-market 0 · CERTIFIED 8 celdas (tasas).

## 13. Tests
56 passed (19 §16 nuevos: unicidad, duplicados, fechas, monedas, unidades, nominal-vs-price, fair-vs-price, comparabilidad, div-cero, fórmulas, cross-market, provenance, independencia, artefactos, hash, idempotencia, determinismo, coverage + 37 previos). Ejecutados ANTES de certificar.

## 14. Findings
S-01..S-07 (ver certification_report.md): 3 OBSERVATION, 2 REQUIRED_FIX, 1 OUT_OF_SCOPE, 1 NO_DETERMINABLE. 0 BLOCKER metodológicos.

## 15. Blockers
Ninguno con evidencia reproducible de violación (gaps ≠ BLOCKER §0). Los 3 BLOCKER de AGENTE 04 (comparación TIKR no ejecutada, MEP/CCL sin datos, criterios no versionados en git) exceden este alcance y se heredan como contexto, no se re-abren aquí.

## 16. Certification
NOT_CERTIFIED (motivos §20 en 11_CERTIFICATION/certification_report.md). Celdas CERTIFIED individuales: X01–X08 (tasas con fuente+fecha+valor). V01–V04: SUPPORTED (falta plaza). Resto: PARTIAL/CANDIDATE/NO_DETERMINABLE.

## 17. Remaining NO_DETERMINABLE
Plaza CEPU · tasa BNA numérica · pata USD V01–V04 · GD46/AL25-EDGAR · 5 ventanas FTS-500 · ISINs New Bonds · CUSIP/FIGI · método TIKR.

## 18. Out of scope
Pata USD secundaria · BYMA con credenciales · serie MEP/CCL instrumental con precios · comparación TIKR más allá de UNKNOWN · nuevos instrumentos fuera de CANDIDATE.

## 19. Reproducibility instructions
```
git checkout feature/fx-research-engine
python research/fx_tikr_reverse/sovereign_matrix/scripts/discovery_p2.py
python research/fx_tikr_reverse/edgar_sovereign/scripts/dl_filings.py
python research/fx_tikr_reverse/sovereign_matrix/scripts/dl_phase2.py
python research/fx_tikr_reverse/edgar_sovereign/scripts/extract.py
python research/fx_tikr_reverse/edgar_sovereign/scripts/build_tables.py
python research/fx_tikr_reverse/sovereign_matrix/scripts/build_master.py
python research/fx_tikr_reverse/sovereign_matrix/scripts/provenance_coverage.py
python research/fx_tikr_reverse/sovereign_matrix/scripts/make_outputs.py
python -m pytest research/fx_tikr_reverse/sovereign_matrix/10_VALIDATION/ research/fx_tikr_reverse/engine_tests/ research/fx_tikr_reverse/tests/ -q
```
Red sólo para descargas (clase B, idempotentes); resto clase A determinista. Manifiesto SHA256: sovereign_matrix/research_manifest.json.
