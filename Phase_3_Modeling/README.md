# Phase 3 — archived models and rebuilt retrospective evaluation

## Status of historical files

The existing `data/` split CSVs and `results/` predictions/metrics are preserved historical exports. They are **not the repaired benchmark**. They split 2000–2020 training, 2021–2023 validation and 2024–2025 test, spanning different source regimes.

A chronological split alone does not prevent leakage. Audit findings include full-record monthly climatology in anomaly features, same-month weather/satellite predictors without issue-time availability, and an imputed December 2025 test target. Saved metric arithmetic can be reproduced from predictions, but the original fitting/preprocessing pipeline was absent. Random Forest and XGBoost already appear in archived metrics; they are not unimplemented future extensions.

The historical “attribution” files encode an environmental-feature design, **not causal attribution**. Feature importance or SHAP does not resolve confounding or establish effects of weather, emissions or climate change.

## Rebuilt pilot

Use the pipeline from the repository root:

```bash
python -m dhaka_air_quality --input /path/to/original.csv --output artifacts/rebuilt
```

The original ZIP is also supported. Follow the [root README](../README.md) for installation and optional inputs. Rebuilt outputs are written separately; no historical score is silently replaced.

The bounded evaluation uses complete months within the selected later archive regime, not a pooled 26-year record. Only September 2022–October 2025 supplies 38 complete later-regime months in the uploaded archive. November is truncated; December has no raw target. Acquisition/generation method, units and operational latency remain unverified, so the run is an **exploratory rolling one-step retrospective evaluation**, not deployment-ready forecasting or independent ambient validation.

Compare persistence, seasonal-naive and training-only calendar climatology with a small fixed regularized-regression pilot. Calendar lags must refer to actual preceding calendar months, never jump missing periods. Target lags and optional meteorological inputs are backward-looking. Fit learned preprocessing inside each training fold, avoid full-record anomalies, and evaluate candidates on matched available dates with sample counts. The original test has already been inspected and must not be presented as a newly untouched holdout.

A real operational forecast additionally needs a defined issue time/horizon and evidence that each lagged concentration or weather input was published by that time. If the target is a model-derived product, the claim is product prediction/emulation. Independent station records are needed to assess actual ambient concentration accuracy.

See [repair plan and data requirements](../research_docs/REPAIR_PLAN_AND_DATA_REQUIREMENTS.md) before interpreting results or expanding the model set.
