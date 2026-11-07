# Observed PM₂.₅ and NASA weather: conditional analysis

Independent hourly-mirror matching supports BST-labelled EPA means in part of the record; full-record QA/time conventions remain incompletely verified. NASA dates are UTC. Weather lag2 is the prespecified conservative primary branch. Lag1 weather is an overlapping-day conditional benchmark, not a forecast-available weather input.

Calendar days: 2192; observed PM₂.₅ days: 2117; missing targets preserved: 75.

## Prespecified methods

All six weather fields are examined descriptively with Pearson/Spearman correlations, calendar-month residual adjustment, year+month fixed-effect adjustment, and exploratory lags0–7. Weather date offsets−1/0/+1 are all retained; none is selected as best. No IID significance p-values are asserted.

VIF is computed on standardized complete-case weather. Ridge omits dewpoint while retaining temperature and relative humidity to reduce known thermodynamic redundancy; this is a declared physical choice, not tuned VIF thresholding. Data-derived anomalies are not inputs.

Prediction uses fixed Ridge alpha1.0, target lags1/7/365 and annual sine/cosine. The primary weather extension adds lag2 T,RH,wind,rain and pressure: NASA UTC lag1 daily values extend to06BST on targetday, six hours beyond a midnightBST issue. A separate lag1 overlapping-day benchmark is retained and must not be described as forecast-available. Lag2 was chosen from the interval prerequisite, not its score. Calendar gaps are preserved; targets are never imputed. Median imputation/scaling fit separately within each monthly expanding training fold. Initial training is2016–2017; daily observed lag updates make this rolling one-day, not a multi-day batch forecast.

Prediction uses nominal date alignment; all−1/0/+1 weather-date sensitivities remain descriptive. Primary lag2 avoids daily-interval overlap under both UTC and BST conventions, but does not establish actual release latency. EPA daily PM lag1 publication timing also remains unverified. No operational forecasting claim is made.

## 2020–2021 common-case retrospective diagnostics

| Model | n | MAE | RMSE | Bias | R² |
|---|---:|---:|---:|---:|---:|
| calendar_month_climatology | 670 | 25.559 | 37.003 | -4.874 | 0.709 |
| persistence | 670 | 19.897 | 29.511 | 0.199 | 0.815 |
| ridge_calendar_lags | 670 | 18.839 | 27.740 | -0.710 | 0.836 |
| ridge_calendar_lags_weather | 670 | 18.661 | 26.925 | -1.060 | 0.846 |
| ridge_calendar_lags_weather_safe2 | 670 | 18.769 | 27.478 | -1.153 | 0.839 |
| seasonal_naive_365 | 670 | 34.096 | 49.259 | -5.551 | 0.484 |

Unmatched available-case metrics and yearly metrics are in daily_metrics.csv. Compare the common-case rows for cross-model rankings. Weather-increment uncertainty instead uses paired core/weather predictions and preserves missing calendar dates in7/30-day block bootstrap; negative deltas favor weather. No candidate/lag is selected from these retrospectively inspected dates.

## Limits and next evidence

Verify the EPA full-record averaging rule, valid-hour threshold and QA flags; verify NASA daily interval and actual release latency before any deployment claim. Report the complete weather-date-shift sensitivity, not only the most favorable coefficient. Residual season adjustment and predictive importance do not identify causal meteorological effects. No input file or legacy result is modified.

## Observed conditional findings

- T2M: raw Pearson r=-0.755; month-adjusted r=-0.077; year+month-adjusted r=-0.085.
- T2MDEW: raw Pearson r=-0.859; month-adjusted r=-0.357; year+month-adjusted r=-0.345.
- RH2M: raw Pearson r=-0.616; month-adjusted r=-0.328; year+month-adjusted r=-0.318.
- WS10M: raw Pearson r=-0.464; month-adjusted r=-0.260; year+month-adjusted r=-0.261.
- PRECTOTCORR: raw Pearson r=-0.440; month-adjusted r=-0.184; year+month-adjusted r=-0.172.
- PS: raw Pearson r=0.736; month-adjusted r=0.068; year+month-adjusted r=0.072.

The large attenuation of temperature and pressure correlations after calendar adjustment shows that their raw associations are largely shared seasonal structure. Residual associations remain conditional/descriptive, not causal effects.

All-six weather maximum VIF is 267.72; omitting dewpoint lowers the retained-set maximum to 4.49.

### Paired weather increment uncertainty

| Period | Weather branch | Block days | Metric | Paired days | Weather minus core | 95% interval |
|---|---|---:|---|---:|---:|---|
| validation_2018_2019 | ridge_calendar_lags_weather_safe2 | 7 | MAE | 703 | -0.890 | [-1.561, -0.169] |
| validation_2018_2019 | ridge_calendar_lags_weather_safe2 | 7 | RMSE | 703 | -1.274 | [-2.028, -0.501] |
| validation_2018_2019 | ridge_calendar_lags_weather_safe2 | 30 | MAE | 703 | -0.890 | [-1.619, -0.094] |
| validation_2018_2019 | ridge_calendar_lags_weather_safe2 | 30 | RMSE | 703 | -1.274 | [-1.847, -0.278] |
| validation_2018_2019 | ridge_calendar_lags_weather | 7 | MAE | 703 | -0.973 | [-1.670, -0.202] |
| validation_2018_2019 | ridge_calendar_lags_weather | 7 | RMSE | 703 | -1.824 | [-2.682, -0.947] |
| validation_2018_2019 | ridge_calendar_lags_weather | 30 | MAE | 703 | -0.973 | [-1.808, 0.032] |
| validation_2018_2019 | ridge_calendar_lags_weather | 30 | RMSE | 703 | -1.824 | [-2.558, -0.729] |
| retrospective_test_2020_2021 | ridge_calendar_lags_weather_safe2 | 7 | MAE | 697 | -0.107 | [-0.693, 0.602] |
| retrospective_test_2020_2021 | ridge_calendar_lags_weather_safe2 | 7 | RMSE | 697 | -0.325 | [-0.949, 0.439] |
| retrospective_test_2020_2021 | ridge_calendar_lags_weather_safe2 | 30 | MAE | 697 | -0.107 | [-0.468, 0.541] |
| retrospective_test_2020_2021 | ridge_calendar_lags_weather_safe2 | 30 | RMSE | 697 | -0.325 | [-0.810, 0.382] |
| retrospective_test_2020_2021 | ridge_calendar_lags_weather | 7 | MAE | 697 | -0.224 | [-0.820, 0.465] |
| retrospective_test_2020_2021 | ridge_calendar_lags_weather | 7 | RMSE | 697 | -0.880 | [-1.432, -0.063] |
| retrospective_test_2020_2021 | ridge_calendar_lags_weather | 30 | MAE | 697 | -0.224 | [-0.649, 0.443] |
| retrospective_test_2020_2021 | ridge_calendar_lags_weather | 30 | RMSE | 697 | -0.880 | [-1.222, -0.238] |

Negative deltas favor the weather extension. These paired case sets differ from the all-model common-case table, because persistence/seasonal baselines can be missing when previous observations are absent. Interpret the primary safe2 branch separately from the overlapping-day lag1 benchmark; use the prespecified branch and its intervals regardless of which score looks more favorable. The intervals condition on fitted models, nominal alignment and inspected historical data.
