# Observed-reference descriptive analysis

Source: supplied EPA-hosted embassy daily calendar, 2016-01-01–2021-12-31. The source date mapping uses its caption and1-based day index; original monitor QA and exact daily averaging timezone remain unverified. This is not a reanalysis target. Missing values remain missing; no daily target interpolation or filling was performed.

## Actual results

- Calendar days:2192; observed:2117; missing:75; coverage:96.58%.
- Available-day PM₂.₅ mean:87.18µg/m³; median:60.71; maximum:340.79.
- Days strictly above15µg/m³:2068/2117 (97.69% of observed days). The15 benchmark is the WHO2021 daily value applied retrospectively, not AQI, legal compliance or a health-outcome estimate. Missing-day exceedances are unknown.
- Pooled available-day95th percentile:212.77µg/m³. Strictly-above-threshold episodes:56; longest observed uninterrupted run:6days. Gaps/missing days interrupt runs. This threshold is descriptive and estimated from the whole period, not a prospectively selected alarm threshold.
- Eligible monthly means:69/72 using≥75%of full calendar days. Excluded:2018-04, 2020-05, 2021-09.
- Season-adjusted Theil–Sen slope:0.677µg/m³/year.12-month residual-block bootstrap95%interval:[-0.166,1.533];6-month sensitivity:[-0.588,2.027]. Each uses1000replicates with a fixed reproducibility seed. Do not interpret these six-year results as climate-change attribution or a definitive trend-significance claim.

## Methods and interpretation

Annual/month/season tables use available daily values and report observed/missing denominators. The month plot additionally shows equal-year means of eligible monthly means to expose coverage/weighting sensitivity. Four seasons areDJF/MAM/JJAS/ON; these windows have3/3/4/2months. The exact paperTable3six-season boundaries are a paper-definition sensitivity analysis, also unequal in duration; this does not assert agreement with the final release's season labels. Calendar-month summaries are primary. Seasons are pooled; no independent equal-length seasonal replicates are implied.

Trend inputs are monthly daily-mean concentrations with≥75%coverage. Subtract the median eligible monthly mean for each calendar month. FitTheil–Sen slope to the residual versus actual elapsed calendar months/12. For uncertainty, center residuals around the fitted trend, sample moving blocks of12months (and6for sensitivity) only from completely eligible contiguous calendar windows, concatenate draws, and place residuals on the original eligible observation times. Refit slope for1000replicates unless CLI override is used. This preserves within-block dependence without bridging excluded months. Intervals assume approximately stationary residuals and hold the estimated seasonal profile fixed; they do not propagate all seasonal-estimation, missingness, source QA, endpoint or monitor-interval uncertainty. Coverage≥75%does not guarantee unbiased missingness. No iid Mann–Kendall p-value or independent-row CI is claimed.

NASA POWER/MERRA-2 weather coverage is documented separately. Calendar-date coincidence does not establish daily averaging-interval alignment with embassy observations. No causal weather effects or aligned daily pollutant-weather validation are estimated in this script. Final analysis requires confirming the embassy averaging interval and source QC documentation.

All generated outputs are reproducible from the identified input hashes. Existing output directories are refused. Original inputs and legacy results remain unchanged.
