# Rebuilt run report

**Status: computational reconstruction and retrospective pilot; independent observational validation remains unresolved.**

- Input: `Bangladesh Air Quality Index (AQI) Dataset (2000–2 (1).zip`; selected city: Dhaka.
- Rebuilt observed months: 311; complete months: 310; eligible later-regime exploratory months: 38.
- Missing months are not fabricated. Earlier/mixed/partial months remain visible for audit and excluded from the primary pilot.
- Temporal semantics: naive archive timestamps, timezone unknown. Rolling prediction is retrospective and assumes preceding inputs have become available; operational release timing has not been established.
- Baseline and fixed-regularization models use backward calendar lags and fold-local preprocessing. Archived full-period anomalies are excluded.
- Results do not establish a measured 2000–2025 pollution trend, causation, health effects, or universal model superiority.
- Read `evaluation_audit.json` for fold/sample limitations and `metrics.csv` for common-case comparisons. A small short-period pilot is not a final untouched-test experiment.

Source attribution: {'doi': '10.17632/9j447cynb9.2', 'status': 'User-provided Mendeley V2 attribution corroborated by public metadata; no fresh provider-file byte match or instrument validation', 'licence': 'CC BY 4.0', 'measurement_validated': False}. See research_docs/source_metadata for public provenance metadata for the inspected reference input; station/product identities, segment units and pre-2022 acquisition/generation remain unverified.

See `archive_reconciliation.csv` when supplied for changes versus legacy tables. Original repository CSVs and original input files have not been overwritten.
