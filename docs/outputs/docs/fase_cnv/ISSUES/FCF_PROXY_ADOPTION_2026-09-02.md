### Issue: Adoption of CF_Inversion as CapEx proxy (Free Cash Flow adoption)

- Accn: d96fd259-c5ce-431f-8e14-17af592b99f9
- Date opened: 2026-09-02
- Opened by: user (accepted proxy)

Summary
-------
The CNV extraction (`CF_Inversion`) aggregates investing cash flows and does not expose explicit `PaymentsToAcquirePropertyPlantAndEquipment` facts. The user accepted using `CF_Inversion` (absolute value) as a proxy for CapEx for reporting and ratio calculations. This issue records the decision and links to affected artifacts.

Decision
--------
- Adopted proxy: `CapEx_proxy = abs(CF_Inversion)` (58.733 MM ARS).
- Free Cash Flow adopted for reporting: `FCF = CF_Operativo + CF_Inversion = 30.309 MM ARS`.

Files modified
--------------
- `outputs/docs/fase_cnv/METR_TIKR_2025_FACT_MATRIX_DETAILED.csv` (FreeCashFlow marked `ADOPTED_PROXY` and derived ratios added)
- `outputs/docs/fase_cnv/METR_TIKR_2025_PROVENANCE.csv` (entries `FreeCashFlow_proxy`, `FreeCashFlow_adoption`, ratio provenance)
- `outputs/docs/fase_cnv/METR_TIKR_2025_GAPS.csv` (CapEx flagged `PROXY_ACCEPTED`; derived ratio placeholders updated)
- `outputs/docs/fase_cnv/METR_TIKR_2025_REPORT.md` (section describing adoption and impact)

Rationale
---------
- No explicit CapEx tags found in canonical METR facts for this accession.
- Proxy provides immediate ability to compute FCF-dependent ratios needed for analysis.
- Adoption is explicitly recorded with provenance and will be reverted if more granular data becomes available.

Next actions
------------
1. Flag for review: when detailed investing cash flow breakdown becomes available, re-evaluate and, if necessary, recompute FCF and dependent ratios.
2. Run adversarial checks to ensure derived ratios remain robust if alternative CapEx definitions are supplied.
3. Record reviewer and closure outcome here.

Status
------
OPEN — adoption recorded; awaiting reconciliation if new data arrives. User accepted proxy on 2026-09-02.
