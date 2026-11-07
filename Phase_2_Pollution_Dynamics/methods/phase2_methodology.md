# Phase 2 methodology — archived analysis and repair requirements

**Status:** This describes the historical analysis inventory. The existing result CSVs are preserved exports, not a newly reproduced or source-validated 2000–2025 atmospheric baseline.

## Archived methods

The earlier workflow reports annual aggregation, Mann–Kendall testing, slope estimation, pollutant ratios/correlations, PCA, clustering, episode screening and Pettitt change-point analysis. Complete executable construction and analysis code for these exports was not committed with them. The original archive is mixed in construction and has an identified boundary on **4 August 2022**.

The file `mann_kendall_sen_slope_results.csv` labels a field `linear_slope_per_year`; this is not documentation that a Sen slope was calculated. A future reproducible analysis must name and implement the actual estimator consistently.

## Required interpretation and rerun conditions

- Establish provider, units, timestamps, spatial support and source regimes before estimating atmospheric trends. The period printed on a file does not establish a comparable monitoring record.
- Rebuild unique-time coverage from the original records. Do not count identical Dhaka/Azimpur location series as independent temporal or spatial information; exclude absent/imputed outcomes from observed analyses.
- Analyze documented source regimes separately. A change-point test cannot distinguish a physical change from a construction change by itself. Do not erase the 2022 boundary using an arbitrary offset.
- State valid-coverage rules and calendar aggregation. Flag mixed and partial months; the supplied raw archive ends on 23 November 2025 and contains no December target.
- Reassess seasonal and serial dependence, multiple testing and uncertainty before reporting significance. Historical p-values alone do not establish verified environmental trends.
- Treat PCA and correlations as descriptive. AQI is derived from pollutants and must not serve as an independent pollutant in composition/PCA validation. Record units, standardization and missingness decisions; do not assign emission sources from PCs without independent evidence.
- Define threshold episodes at the native temporal support with complete coverage. A percentile of a mixed-source record is not a stable exposure threshold.

The versioned raw-data reconstruction and retrospective baseline pilot are documented in the [root README](../../README.md). Stronger Phase 2 inference remains conditional on the [source and validation requirements](../../research_docs/REPAIR_PLAN_AND_DATA_REQUIREMENTS.md).
