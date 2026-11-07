# Phase 2 results summary — archival exports

**Status:** Historical computations retained for traceability. They have not been re-established as valid inference on a homogeneous independent monitoring record. The previously reported 9,459-day input count is an archival description, not a verified count of independent quality-controlled observations.

## Archived statistics

- The saved analysis reported increasing trends for PM2.5, PM10, NO2, SO2, ozone and AQI. Their environmental interpretation and significance remain **unverified** because source construction, serial/seasonal dependence and the executable original pipeline have not been resolved.
- Saved Pearson correlations include PM2.5–PM10 **0.992**, PM2.5–AQI **0.962** and PM2.5–SO2 **0.878**. These describe the archived series; AQI is derived from pollutants and is not an independent validation target.
- Saved PCA component shares are **60.47%, 22.90% and 10.41%** (93.78% total). They are not evidence of emission-source attribution or independent measurement accuracy.
- Saved Pettitt outputs report PM2.5/AQI change points in 2009 and NO2 in 2010. Their p-values do not authenticate physical change points in a record with unresolved construction history. The separately identified 4 August 2022 source boundary must be audited explicitly.

## Repaired workflow

Original CSV exports remain unchanged. New reconstruction and baseline outputs are generated separately through the pipeline described in the [root README](../../README.md). Computational repair does not make the archived trend tests validated by association. A source-consistent rerun with explicit estimators, quality/coverage rules, temporal uncertainty and independently justified claims is needed before replacing them.

See [repair scope and required data](../../research_docs/REPAIR_PLAN_AND_DATA_REQUIREMENTS.md).
