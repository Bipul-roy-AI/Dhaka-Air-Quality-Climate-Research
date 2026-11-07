# Phase 3 — climate integration: source audit and repaired workflow

## Preserved historical files

The existing monthly source-like/processed CSVs, figures and `results/phase3_2_3_results/` and `results/phase3_2_4_results/` are archived outputs. They include satellite AOD/LST/NO2, reanalysis meteorology, pollution summaries, correlations, seasonal summaries, lags and VIF diagnostics. Their presence is not evidence that the complete extraction and transformation chain has been reproduced.

## Source and unit qualifications

- Legacy documentation describes ERA5-Land, whereas `scripts/era5_extraction_cdsapi.py` is a template requesting ERA5 single levels. It is not verified as the script that produced the monthly table. Recover the actual product, version, grid/area, request and native metadata before claiming a resolved source.
- The `rainfall_mm` field's aggregation meaning remains unverified. A rate, mean daily accumulation and monthly total require different treatment; do not infer the meaning from the column label. Verify native accumulation intervals and reset conventions before applying conversions.
- Satellite availability varies: AOD appears in 267/312 archived months, LST in 271 and satellite NO2 in 91, starting June 2018. Do not invent pre-sensor observations or treat imputed histories as measurements.
- Raw `-999` missing-value sentinels must be distinguished from valid concentrations. Product retrieval QA masks and extraction footprints still require provenance.
- Regional model/reanalysis fields, satellite columns and station concentrations have different spatial/vertical support. Another related model product is an intercomparison source, not independent ground truth.

## Repaired processing

The new pipeline, documented in the [root README](../README.md), rebuilds pollution aggregation from the original upload with unique-time counts, coverage, boundary and partial-month flags. Original outputs are preserved. The known 4 August 2022 construction boundary remains explicit; it is not automatically interpreted as an atmospheric change or statistically erased.

Historical anomaly columns use calendar-month means over the full record, including held-out periods. Do not reuse them in repaired predictive evaluation. Any learned climatology, imputation, scaling or feature selection must use training-fold data only. For a forecast, same-month observed weather or satellite data are unavailable before the month ends; define issue time, reporting latency and permitted lags. The bounded rebuilt pilot is retrospective and makes its timing limits explicit.

HyAQMet is useful for documenting native source extracts, units, time alignment and spatial support, but its public precipitation/solar processing and conversion descriptions require independent verification before adoption. Its interpolated hourly values are not additional independent observations, and its 2017–2022 regional data cannot validate the user's entire historical archive.

The [repair plan and source requirements](../research_docs/REPAIR_PLAN_AND_DATA_REQUIREMENTS.md) separates code fixes from unresolved provider, station, unit and independent-validation evidence. Correlation, partial correlation and VIF remain descriptive/model diagnostics; none establishes causal environmental attribution.
