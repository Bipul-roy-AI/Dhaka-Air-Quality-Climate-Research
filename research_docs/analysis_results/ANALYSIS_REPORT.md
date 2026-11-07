# Dhaka air quality: paper-style analysis report

## Scope and evidence

This report consolidates actual computations following the useful diagnostics in *HyAQMet: Hourly Air Quality and Meteorology Dataset for Dhaka*, with additional independent-reference comparison and a bounded prediction experiment. It is an analysis report, not a peer-reviewed manuscript or a claim that a globally optimal method has been found. The original archive, final Zenodo release, observed embassy record and reanalysis meteorology remain separate evidence types. No author notebook was executed blindly, no source values were silently corrected, and original study exports remain unchanged.

| Analysis track | Input and period | Role |
|---|---|---|
| HyAQMet reproduction | Final Zenodo20705735 CSV;2017–2022;52,584 hourly rows ×42 fields | Released regional reanalysis diagnostics; native CAMS is3-hourly before interpolation |
| Observed-reference analysis | EPA DOI10.23719/1528454;2016–2021;2117 daily values on2192dates | Measured point-station series; published figure-support data, not original hourly QA logs |
| Weather association/prediction | NASA POWER/MERRA2;2016–2021;2192UTC days | Newly documented model-derived weather, not recovered original ERA5 |
| Independent-reference comparison | HyAQMet versus EPA,2017–2021 | Conditional daily pairing with time-basis and geographic-support sensitivities |
| Original user archive | MendeleyV2;2000–November2025 | Previously rebuilt/audited separately; mixed provenance, not used as a26-year measured target |

The supplied study's objective is refined to: what seasonal patterns are supported by observed Dhaka PM2.5, how well do regional products agree with it, and does available meteorology add predictive value beyond calendar and pollutant persistence? The data determine the allowed claim. A raw timestamp or a complete reanalysis archive is not an independent observation.

## 1. Observed pollution patterns and coverage

The observed series has **2117 of 2192 days**, coverage **96.58%**, with75missing days left missing. Available-day PM2.5 mean is **87.18 µg/m³**, median **60.71**, and maximum **340.79**. These describe a point monitor and its valid published days, not population-wide personal exposure.

Winter(DJF) mean is **172.02 µg/m³** and June–September mean **33.53**, a **5.13×** contrast. Conventional windows DJF/MAM/JJAS/ON have3/3/4/2 months, so counts and coverage accompany pooled summaries. Calendar months are primary. Both the paper's stated six-season scheme and the released HyAQMet scheme are retained as labelled sensitivities rather than silently choosing between contradictory definitions.

**2068 of 2117observed days(97.69%)** exceed15 µg/m³. This is the WHO 2021 daily benchmark applied retrospectively; it is not an AQI calculation, legal compliance assessment, annual standard or health-outcome estimate. Missing-day exceedances are unknown. The pooled available-day95th percentile is212.77 µg/m³. There are56strict-exceedance runs; the longest **observed uninterrupted** run is6 days. Missing days censor possible real episodes and break the recorded runs. The threshold was estimated descriptively over the whole series, not prospectively selected for prediction.

[Coverage/annual/month/season tables, episodes and methods](observed/methods_findings.md). Figures: [coverage](observed/observed_daily_and_coverage.png), [climatology](observed/observed_monthly_and_seasonal.png).

## 2. Short-period trend and uncertainty

Monthly means require at least75% of full calendar-day coverage:69 of 72 months qualify; April2018,May2020 and September2021 do not. The coverage rule is a declared exploratory screen, not a verified station QA rule. Subtract each calendar month's eligible median and fit Theil–Sen slope against elapsed months/12.

The fitted slope is **0.677 µg/m³/year**. The1000-replicate 12-month residual moving-block interval is **[-0.166,1.533]**; the6-month sensitivity also spans zero. Thus these calculations do **not establish an increasing trend**. Six years are inadequate for a climate-change attribution claim. Intervals condition on a fixed estimated seasonal profile, approximately stationary residual blocks and observed coverage; they do not cover all instrument, missingness or seasonal-estimation uncertainty. No iid Mann–Kendall p-value was substituted for dependence-aware inference.

[Trend inputs and both block lengths](observed/season_adjusted_trend_intervals.csv).

## 3. Meteorological associations and collinearity

Daily NASA values are UTC; the published station-day convention is incompletely documented. Nominal date joins and weather-date shifts−1/0/+1 are therefore reported as sensitivities, not selected for the most favorable result. Pearson/Spearman coefficients and lags0–7 are exploratory: there is no optimal-lag claim or causal interpretation from this screen.

Temperature–PM2.5 Pearson correlation is−0.755 unadjusted and−0.077 after calendar-month adjustment; pressure changes from+0.736 to+0.068. Much of those raw associations is shared seasonality. Month-adjusted RH, wind and rain correlations are approximately−0.328,−0.260 and−0.184. These residual associations do not identify effects of interventions or isolate emissions.

The six meteorological variables have substantial thermodynamic redundancy: maximum centered VIF 267.72. Omitting dewpoint while retaining temperature/RH reduces the retained-set maximum to4.49. This fixed physical choice is not tuned on test performance. Descriptive VIF and residualization use inspected data; predictive preprocessing is fitted separately within training folds.

[Association, lag, alignment and VIF results](weather/findings.md).

## 4. Conditional one-day prediction experiment

The experiment uses2016–2017 as initial training, monthly expanding refits in2018–2021, fixed Ridge alpha1, target lags1/7/365 and annual sine/cosine. Each fold fits its own median imputer and scaler. Targets are never imputed, calendar gaps remain gaps, and the historical dates are retrospectively inspected—not a newly untouched test.

An hourly AirNow mirror supports the EPA local-date convention for part of2019–2020:523 of 530 paired daily means match within0.0001 µg/m³ using local labels, versus3under UTC day grouping. This is evidence for the convention, not full-record QA certification or another independent station. Under a local midnight issue, previous-UTC-day weather can extend six hours into the target day. Therefore the primary weather extension uses **lag two**, chosen from that information-timing prerequisite rather than its score. Lag-one weather is retained only as an overlapping-day conditional benchmark. Even lag-two does not establish actual provider or station publication latency.

Identical common-case2020–2021 comparisons:

| Model | Days | MAE,µg/m³ | RMSE,µg/m³ | R² |
|---|---:|---:|---:|---:|
| Previous-day persistence | 670 | 19.90 | 29.51 | 0.815 |
| Training-only calendar climatology | 670 | 25.56 | 37.00 | 0.709 |
| 365-day seasonal baseline | 670 | 34.10 | 49.26 | 0.484 |
| Ridge: PM lags + calendar | 670 | 18.84 | 27.74 | 0.836 |
| Ridge + conservative lag-two weather | 670 | 18.77 | 27.48 | 0.839 |

The primary weather model's RMSE improvement over the core is small. On the **697 paired core/weather days** (distinct from670all-model common days), weather-minus-core RMSE is **-0.325 µg/m³**, with30-day block interval **[-0.810,0.382]**. Its MAE interval also spans zero. **Added weather benefit is not established in the later period under this conservative design.** The apparently better lag-one result must not be sold as an available-input forecast. Earlier2018–2019 diagnostics differ and are retained; neither period was used for hyperparameter/lag selection.

[Full predictions, yearly scores and paired uncertainty](weather/findings.md). These results are conditional hindcasts, not deployment or universal model-superiority claims.

## 5. Independent-reference comparison of HyAQMet

For1752 paired2017–2021 days, nominal BST-day CAMS versus the embassy reference gives **r=0.897**, **bias=+16.15 µg/m³**, **MAE=24.98** and **RMSE=34.23**. Bias is regional model minus point-monitor reference. The30-day block interval for bias is approximately[+11.74,+20.75], conditional on this pairing. High correlation does not remove the positive concentration difference or spatial-support mismatch.

For monthly means calculated on identical available reference days and at least75% reference-day coverage,57 months qualify; r=0.955 and RMSE24.59 µg/m³. Seasonal errors differ: post-monsoonON bias is approximately+42.59 µg/m³; pooled performance should not hide that heterogeneity. BST/UTC daily aggregation and calendar shifts−1/0/+1 remain in the tables. They are sensitivity analyses, not a fitted timezone correction. Exact full-record daily QA and averaging rules remain unresolved, and the regional product does not represent an individual station's footprint exactly.

[Reference metrics, pairing sensitivity, uncertainty and hourly mirror check](reference/findings.md). This extends the paper's literature-level comparison with an actual paired published-observation diagnostic; it is not a certificate of every source field or every year.

## 6. HyAQMet final-release reproduction and discrepancies

- **Structure reproduced:**52,584×42; no expected-hour gaps or missing numeric cells. Forty-two columns include timestamps/encodings/labels, not42independent physical measurements. Native3-hour CAMS model fields supply17,528 source values; interpolation cannot create independent hourly evidence or resolve sharp sub-three-hour spikes.
- **Climatology/correlations:** calendar-month/local-hour pollutant summaries, both six-season definitions, full numeric descriptive tables and product-field correlations are exported. These are regional reanalysis patterns.
- **Season discrepancy:** released labels disagree with paperTable3 at **13,968 hours**, while matching the notebook's alternative dates. Codes are1–6 in the release versus0–5 in the paper. No single conflicting six-season definition is used as the primary contract.
- **VIF before/after:** source26candidate columns and published13retained columns are tested with centered/intercept and notebook-style uncentered conventions. Centered maximum VIF falls from about430,024 to25.27; retained13are below100 but are not generally free of collinearity. This is a diagnostic of the published sets, not reproduction of an optimal selection algorithm or endorsement of100as a universal cutoff.
- **PM proxy caution:** CAMS PM2.5 mean102.333 µg/m³ versus37.402for the sum of four retained MERRA components. The sum is a component proxy, not a complete independently measured PM2.5 total. The raw source's labelled total is separately compared. BLH-scaled variants, with and without a50m floor, remain constructed sensitivities. They do not establish calibration or source apportionment.
- **BLH check:** direct hourly Pearson is **-0.4904**, versus−0.65 printed in the paper. Daily correlation is−0.5069 and within-year/month daily residual correlation−0.2020. This does not reproduce the printed−0.65 under a direct calculation on the downloaded release; the reason remains unresolved. The lowest/highest BLH-decile PM contrast **3.036×** does reproduce the approximate threefold narrative. Physical plausibility is not causal identification.
- **Precipitation concern survives the final release:** `precip_mm` exactly equals the source extract in all52,584 rows. Summing it as an hourly water amount yields20,142–33,893mm/year, a strong accumulation-versus-rate warning. No corrected rainfall series is certified without original NetCDF and provider interval/reset metadata. The corresponding rain intercomparison is diagnostic and suspect, not a physically validated bias estimate.
- **Upstream conversion caveat:** public extraction code applies a fixed air-density conversion to gases and requests pressure-level fields, whereas the paper describes collocated pressure/temperature conversion. Raw NetCDF verification was not available; gas comparisons retain their supplied labels and do not certify an upstream correction.
- **Solar correction is present downstream:** final maximum983.657 W/m², with no01–04BST values above0.01; the raw-source cumulative field is transformed. This reproduces a useful consistency check, not every radiometric accuracy requirement.

[Complete final-release findings](hyaqmet/findings.md), [source checks](hyaqmet/final_vs_source_checks.csv), [VIF 26](hyaqmet/merra_26_candidate_vif.csv), [BLH](hyaqmet/blh_association.png).

## 7. What this supports and what remains open

The defensible current findings are a pronounced observed seasonal cycle, uncertain short-period trend, strong seasonal confounding of some weather correlations, limited evidence for incremental timing-safe weather skill in2020–2021, and substantial regional-product/point-reference differences. The original mixed archive cannot establish a validated26-year measured-pollution trend. Its post-boundary source fingerprints should be presented as model-product evidence; earlier acquisition/generation remains unresolved.

No health outcomes, causal effects of lockdowns/emissions/climate, intra-urban risk maps, emission source apportionment, or universal best algorithm were estimated. Re-running authenticated original CDS/ADS/NASA NetCDF acquisition was not performed; we analysed deposited releases and identified reference data. The final-release rain concern and paper/release season disagreement remain open. The user selected reporting both six-season definitions as separate sensitivity analyses; calendar months remain primary.

Remaining scientific work is to verify full-record station-day QA/latency and original upstream extraction metadata, resolve the accumulation issue from native metadata, evaluate spatial-support sensitivity, and register any genuinely prospective validation period. It is appropriate to write these as limitations, not manufacture missing evidence. A formal novelty claim or journal-ready manuscript requires a broader closest-work review and researcher decisions.

## Files, provenance and reproducibility

Four result folders contain tables, figures, predictions, uncertainty and per-track methods. Source inputs are hashed; Zenodo ZIP md5/SHA256 and final CSV hash are recorded in `../source_metadata/hyaqmet_release_manifest.json`. The wrapper `scripts/run_paper_style_analysis.py` reproduces all four tracks in a fresh directory. `ANALYSIS_FIGURES.pdf` provides a portable summary and figure collection; this Markdown file supplies the detailed methods and interpretation. Standalone PNGs and numeric CSVs are retained for export. See `REPRODUCE.md` for complete acquisition and analysis commands. Original inputs and historical project tables are preserved.

Sources: [HyAQMet GitHub](https://github.com/AdityBarua10/HyAQMet), [dataset DOI10.5281/zenodo.20705735](https://doi.org/10.5281/zenodo.20705735), [paper DOI10.1002/gdj3.70111](https://doi.org/10.1002/gdj3.70111), [EPA data DOI10.23719/1528454](https://doi.org/10.23719/1528454), [AirNow mirror DOI10.6084/m9.figshare.12687695.v2](https://doi.org/10.6084/m9.figshare.12687695.v2), [original archive DOI10.17632/9j447cynb9.2](https://doi.org/10.17632/9j447cynb9.2), and the exact NASA POWER requests in the source manifests. Credit original data creators; these new analyses do not transfer authorship of their datasets.
