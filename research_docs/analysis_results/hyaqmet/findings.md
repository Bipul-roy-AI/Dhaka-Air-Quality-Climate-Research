# HyAQMet final-release descriptive reproduction

Input SHA256 `420f59fd7e7cd527f1475b309411f27cb8ce4085490ca5daba4e1c517e0c4649`. Read 52,584 rows and 42 columns from final Zenodo CSV; source extracts were separately checked. Timestamp labels are BST/UTC+6 per released README, not inferred from concentration patterns. Primary climatology uses calendar months. All computations retain original released values; no source repair, imputation or station calibration was performed.

## Structural and physical checks

- Expected-hour gaps: 0; unexpected hours: 0; missing cells: 0 numeric cells.
- CAMS PM2.5>PM10 rows: 0; BLH<=0 rows: 0.
- Final solar maximum: 983.657W/m²; 01–04BST nighttime rows above0.01W/m²: 0.
- `final_vs_source_checks.csv` quantifies which public-source fields match. Precipitation remains unchanged relative to the source extract, while the final solar field is transformed. Annual sums of the released ERA5 precipitation field are 20,142.1–33,893.5mm **if interpreted as hourly water amounts**; the suspect accumulation semantics survive in the released field. This is not a validated corrected rainfall total. Original NetCDF and provider conventions are needed before deaccumulation.

## Season-definition conflict: exposed, not resolved

Released labels disagree with paper Table3 at 13,968 hours and with the public notebook date rules at 0 hours. Released codes are [1, 2, 3, 4, 5, 6]; paper states0–5. Table3 extends Monsoon through15October and gives Autumn/LateAutumn approximately one month each; notebook/release use approximately two-month seasons beginning15February/April/June/August/October/December. Separate sensitivity tables preserve both definitions. The user selected reporting both definitions as separate sensitivity analyses. Calendar months remain primary; neither conflicting six-season scheme is silently preferred.

## Inter-product particulate comparison

CAMS mean PM2.5=102.333µg/m³; MERRA component-sum mean=37.402µg/m³. The component sum is BC+OC+SO4+dust, not a chemically complete independently measured PM2.5 reference. Median BLH=324.121m; 7,164 hours have BLH<50m. For CAMS minus unscaled MERRA sum, bias=64.932µg/m³ and RMSE=90.036. Dividing a surface mass proxy by BLH is a constructed sensitivity transformation, not an independently validated calibration; raw-BLH and50m-floor variants are both reported. Identical units do not remove differing spatial support or model construction. Full seasonal and native3h metrics are in CSV files.

## BLH association

The paper reports overall Pearson r=−0.65 (§3.6,p11), whereas the final released columns reproduce hourly unadjusted r=-0.4904; daily r=-0.5069; daily within-year-month-demeaned r=-0.2020. Lowest/highest BLH-decile CAMS mean ratio=3.036. Association and physical plausibility do not identify a causal effect. Interpolated hours and serial dependence do not create independent samples; no independent-hour significance claim is made.

## VIF and meteorology

Both standard centered/intercept VIF and the public notebook's uncentered/no-intercept calculation are reported for the13 retained MERRA columns and, separately, the original26 numeric source candidates in `merra_26_candidate_vif.csv`. Published retention is mapped explicitly by source/release column name; it is not selected anew by a threshold. Before/after high/infinite VIF counts are recorded in `quality_and_provenance.json`; the numerical dependence flag uses residual SSE≤SST×10⁻¹². Their difference matters; VIF100 is not used as a universal selection rule or proof of collinearity removal. Meteorology comparisons use labelled°C/hPa/m/s fields where available, but the ERA5 precipitation comparison is marked suspect due to accumulation semantics. No original upstream units/conversion metadata is independently revalidated from raw NetCDF.

## Outputs and limits

CSV summaries cover every released numeric field, calendar-month/local-hour pollutant climatologies, both season sensitivities, correlations, VIF, source field identity, precipitation diagnostics, PM variants and BLH checks. Figures are standalone PNGs. This is a reproducible final-release audit/intercomparison, not external validation or causal/health attribution. Parent analysis separately handles independent EPA monitor matching. No source values are silently corrected and no better forecast claim follows from these descriptive tables.
