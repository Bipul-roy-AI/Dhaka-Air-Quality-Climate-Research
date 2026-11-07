# Rebuilt dataset dictionary

One row is one calendar month within the observed timestamp span for exactly the requested city. Empty internal months retain missing targets and zero coverage. Dates are month-start labels in the archive's unresolved naive timestamp convention; they have not been asserted to be UTC or Bangladesh Standard Time.

- `pm25_mean`, `pm25_max`, other pollutant means: aggregated reported fields. Units remain unverified; no arbitrary unit conversion or source-break correction is applied.
- `unique_hours`: distinct available city timestamps, never summed over duplicate locations.
- `valid_pm25_hours`: finite nonnegative PM2.5 observations contributing to the target.
- `expected_hours`: calendar days × 24, with timezone unknown. Duplicate clock hours require resolution before applying this convention to a timezone with DST.
- `coverage_fraction`: valid PM2.5 hours / expected calendar hours.
- `complete_month`: complete temporal and valid-PM2.5 coverage, as implemented in data.py.
- `source_regime`: earlier_unverified, mixed boundary month, or later_unverified. The boundary is a data-construction audit flag, not a physical changepoint.
- `primary_eligible`: computational exploratory cohort flag (complete month wholly within the later source regime); it does not certify source validity.
- `target_imputed_by_pipeline`: always false; this pipeline never imputes targets. `upstream_imputation_status` remains unknown because the deposited archive does not supply generation/imputation provenance.
- QA counts: retain physical-range/order flags for inspection. Flagging is not evidence of fabrication. Source units are not repaired using these flags.
- Raw climate columns: retained only from the supplied monthly covariate export; -999 and unavailable retrievals become missing, not zero.
- Archived anomaly columns, archived targets/counts and archived lags are never used as model inputs.
- Prediction lags and preprocessing: generated inside evaluation.py with calendar-aware lags and training-fold-only transforms; current-month covariates are not prediction inputs.

No absent final month is fabricated; no monthly target is forward-filled. Annual summaries are descriptive means of monthly reported values, not validated ambient annual exposure. Metrics inherit unresolved target units.
