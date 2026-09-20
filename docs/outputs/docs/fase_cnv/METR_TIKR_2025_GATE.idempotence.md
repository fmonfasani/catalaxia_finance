# METR_TIKR_2025_GATE

Accession: d96fd259-c5ce-431f-8e14-17af592b99f9
Date: 2026-09-02
Prepared by: Catalaxia reconciliation agent

Gate Summary:
- Overall status: CLOSED WITH EXCEPTIONS
- Unresolved metrics: `OperatingIncome` (UNRESOLVED), `CapEx` (CATALAXIA_MISSING_INPUT)
- Adopted proxies recorded: `FreeCashFlow` (ADOPTED_PROXY via `CF_Inversion`)

Files supporting this gate:
- Fact matrix: [outputs/docs/fase_cnv/METR_TIKR_2025_FACT_MATRIX_DETAILED.csv](outputs/docs/fase_cnv/METR_TIKR_2025_FACT_MATRIX_DETAILED.csv)
- Provenance ledger: [outputs/docs/fase_cnv/METR_TIKR_2025_PROVENANCE.csv](outputs/docs/fase_cnv/METR_TIKR_2025_PROVENANCE.csv)
- Report: [outputs/docs/fase_cnv/METR_TIKR_2025_REPORT.md](outputs/docs/fase_cnv/METR_TIKR_2025_REPORT.md)

Per-metric decisions (canonical → decision → rationale / provenance):

- Revenue: MATCH_EXACT → canonical value 1,217,305,000,000 ARS; evidence printed in CNV HTML; provenance file recorded.

- NetIncome: MATCH_EXACT → canonical value 132,483,000,000 ARS; printed evidence and SHA recorded.

- OperatingIncome: UNRESOLVED → canonical consolidated 196,311,000,000 ARS; segment-level sum from raw iXBRL = 370,373,218,000 ARS (see `OperatingIncome_segmented_sum` in provenance). Aritmética verificada; no dimensional/perimeter match found yet; decision: remain `UNRESOLVED` pending contextual/dimension reconciliation. Provenance: [outputs/docs/fase_cnv/METR_TIKR_2025_PROVENANCE.csv](outputs/docs/fase_cnv/METR_TIKR_2025_PROVENANCE.csv) (row `OperatingIncome_segmented_sum`). Raw evidence: [data/raw/engine/CIK0001717161/filings/000129281426002446/cepuform20f_2025.htm](data/raw/engine/CIK0001717161/filings/000129281426002446/cepuform20f_2025.htm#L44102-L44108).

- EBITDA: MATCH_EXACT → canonical 256,694,000,000 ARS; provenance recorded.

- Cash / Assets / Equity / Liabilities: MATCH_EXACT → values verified in balance-sheet check; evidence in provenance ledger.

- CapEx: CATALAXIA_MISSING_INPUT → CNV does not expose explicit `PaymentsToAcquirePropertyPlantAndEquipment` tags; `CF_Inversion` aggregates investments. Recommendation: retain missing-input classification until explicit CapEx facts available. Provenance: note in provenance ledger and `METR_TIKR_2025_FACT_MATRIX_DETAILED.csv`.

- FreeCashFlow: ADOPTED_PROXY → derived = `CF_Operativo` + `CF_Inversion` = 30,309,000,000 ARS. Adoption recorded as issue `ISSUES/FCF_PROXY_ADOPTION_2026-09-02.md` and in provenance ledger.

Decision rationale and acceptance criteria:
- All `MATCH_EXACT` items have printed/raw evidence with normalized values recorded in `METR_TIKR_2025_PROVENANCE.csv`.
- Derived items include explicit derivation notes and classification (`MATCH_DERIVED`, `ADOPTED_PROXY`) in the fact matrix.
- `UNRESOLVED` items remain open when arithmetic evidence conflicts with canonical values and contextual/dimensional reconciliation is incomplete.

Actions required to close gate fully:
1. Perform dimension/context reconciliation for `OperatingIncome` (compare `METR_E2E_FACT_MATRIX.csv` contextRefs and raw iXBRL contexts; check for alternate consolidated facts).  
2. Obtain explicit CapEx facts (preferred) or a reliable breakdown of `CF_Inversion` to disambiguate investments vs. other cash flows.  
3. Run adversarial checks and idempotence runs to ensure reproducibility.

Gate approver (next step): assign a reviewer to verify unresolved items and accept/reject adopted proxies.

Signed-off: reconciliation agent (automated)

Generated files touched by this run:
- outputs/docs/fase_cnv/METR_TIKR_2025_FACT_MATRIX_DETAILED.csv
- outputs/docs/fase_cnv/METR_TIKR_2025_PROVENANCE.csv
- outputs/docs/fase_cnv/METR_TIKR_2025_REPORT.md

Date of generation: 2026-09-02
