# Dhaka historical air-quality series: provenance and validation status

**Status: Open investigation (27 October 2026).** This document accompanies, but does not replace, the original project datasets. No original samples or result files were modified.

## 1. What is verified directly from the committed files?

- `Phase_3_Climate_Integration/data/processed/Dhaka_Air_Climate_Feature_Engineered_2000_2025.csv` contains **312 monthly records**, January 2000–December 2025, with a `pm25_mean` column.
- From that CSV, July 2022 has `pm25_mean = 148.01544885780913` and `observations = 744`; August 2022 has `pm25_mean = 29.645290685712364` and `observations = 1392`. September 2022 has `observations = 1440`. These changes may reflect a different input or aggregation regime. The observation counter's meaning (hours, duplicates, stations, sampling coverage) is **not yet established**.
- Annual arithmetic means of the same 12 monthly means are approximately **158.71** in 2021, **119.01** in 2022, and **50.31** in 2023. The abrupt decrease must not be presented as an established environmental decrease.
- Sensor-availability flags in this CSV indicate **267** months with AOD, **271** with LST, and **91** with satellite NO₂ out of 312. These are *presence flags*, not proof of retrieval quality.
- `Phase_3_Modeling/results/split_verification_report.csv` reports chronological splits of 252 train, 36 validation and 24 test months (2000–2020, 2021–2023, 2024–2025).
- `Phase_3_Modeling/results/model_evaluation_metrics.csv` gives precomputed scores. The original model fitting, preprocessing, feature construction and leakage checks are **not fully reproducible from code committed here**.
- The archived Phase 2 annual summary reports 24 `observations` in many earlier years and 48 in recent years. That counter needs a data dictionary before being used as a quality metric.

## 2. Where could the input data have come from?

**Not established:** the repository's full historical pollutant-input lineage, station identity, source retrieval method, API use terms, pollutant units, timestamp/time-zone convention, calibration/quality grading, duplicate treatment and whether early values were generated or interpolated.

Previously supplied ZIP archives included a multi-city hourly dataset with Dhaka records dated back to 2000 and a separate later-period Dhaka series identified as Open-Meteo/CAMS-derived. Preliminary review suggested the late-2022 portion of the two files was very similar. **A verified public provenance record, original data-generation code and statistical matching test have not yet been committed; this is a hypothesis to test, not an established crosswalk.**

### Source types that must remain distinct

| Candidate source | What the source represents | Role |
|---|---|---|
| Bangladesh Department of Environment (DoE) air quality reports | Official monitoring and AQI publications; station/time coverage varies | Future station-level comparison; not yet matched |
| Open-Meteo / CAMS product mentioned in the uploaded supplementary archive | Model-based/derived gridded air-quality information | Possible later-period input; do **not** label as ground measurement |
| [Albab Hasan's Bangladesh District-Level Weather & Pollution Dataset](https://github.com/Albab-Hasan/Bangladesh-District-Level-Weather-Pollution-DataSet) | OpenWeatherMap daily weather and air-quality API outputs for 64 districts, available from August 2025 | **New external comparison candidate, not incorporated in reported results** |
| MODIS AOD/LST and Sentinel-5P NO₂ | Satellite-derived indicators/retrievals with distinct periods and units | Explanatory covariates, not substitute PM2.5 station truth |
| ERA5-Land | Meteorological reanalysis | Climate covariates, not an air-pollution measurement |

The Albab Hasan repository's README documents its OpenWeatherMap endpoints (`/data/3.0/onecall`, `/data/2.5/air_pollution`) and data schema: `date,district,division,lat,lon,temp_c,humidity,pressure,wind_speed,clouds,rain,aqi,pm2_5,pm10,o3,no2,so2,co`. **OpenWeatherMap AQI categories must not be confused with US EPA or DoE AQI scales.** Its available publication start does not provide historical independent validation for 2000–2022.

## 3. Priority scientific verification gates

1. **Recover original acquisition record:** DOI/URL, download date, license, source-version and station/product identifiers for each input file. Compare raw bytes/hashes with previously uploaded archives. Locate any synthetic or imputed values.
2. **Define units and time zones:** PM2.5 mass concentration unit; precipitation aggregation units; satellite NO₂ column units; AQI convention; hourly/daily/monthly computation; missing-value treatment; counting basis for `observations`.
3. **Audit regime boundary:** plot daily and monthly time series around **4 August 2022**, investigate sampling and precision changes, compare distributions pre/post and quantify differences against the original source exports. Do not infer a causal event from the discontinuity alone.
4. **Validate against independent DoE records:** where matching station/time windows exist, perform unit harmonization, timestamp alignment and metrics such as bias, MAE, RMSE, correlation and uncertainty; document any geographic mismatch.
5. **Reassess statistics:** recompute seasonal and trend analyses separately by verified source regime; use appropriate serial-correlation methods and test sensitivity to missingness and multiple hypotheses.
6. **Reproduce models:** commit fitting scripts/notebooks and package environment; train-only imputation/scaling; define forecast information horizon; evaluate persistence and seasonal-naive baselines; report errors by year/regime and reproducibility seed.
7. **Health scope check:** no measured medical or epidemiologic outcome data are available in this repository. Treat health as motivation/exposure relevance, not causal disease attribution.

## 4. Data and result references

- [Source-like remote-sensing/climate table](../Phase_3_Climate_Integration/data/raw/Dhaka_RemoteSensing_Climate_v8_2_2000_2025.csv)
- [Monthly integrated feature table](../Phase_3_Climate_Integration/data/processed/Dhaka_Air_Climate_Feature_Engineered_2000_2025.csv)
- [ML-ready monthly table](../Phase_3_Climate_Integration/data/processed/Dhaka_Air_Climate_ML_Ready_2000_2025.csv)
- [Annual pollution summary](../Phase_2_Pollution_Dynamics/results/annual_pollution_summary.csv)
- [Trend and change-point exports](../Phase_2_Pollution_Dynamics/results/)
- [Model metrics](../Phase_3_Modeling/results/model_evaluation_metrics.csv)
- [Split report](../Phase_3_Modeling/results/split_verification_report.csv)
- [DoE AQI publication page](https://doe.gov.bd/pages/static-pages/6922dfba933eb65569e23b0a)
- [Albab Hasan district daily data](https://github.com/Albab-Hasan/Bangladesh-District-Level-Weather-Pollution-DataSet/tree/main/data)

## 5. Interpretation and release policy

- **Completed:** archived exploratory descriptive and statistical outputs; model metrics; provenance and missingness warning; GitHub/portfolio presentation.
- **Under review:** historical series comparability, original source attribution, unit consistency, independence of comparison sources, statistical inference, forecasting claims, complete executable reproduction.
- **Not claimed:** a verified 2000–2025 DoE ground-observation record; independently validated long-term trend; 2022 pollution collapse; causal effects of climate drivers; independently verified forecast accuracy; quantified individual/public-health burden.

Record evidence and scripts before upgrading any of these claims. Preserve the original CSV exports unmodified until a versioned validated replacement exists.
