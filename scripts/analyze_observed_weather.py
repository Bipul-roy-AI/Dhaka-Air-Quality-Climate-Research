"""Conditional EPA-observed/NASA POWER association and daily hindcast analysis.

EPA daily averaging QA remains undocumented. Independent mirror matching supports
BST dates in part of the record, while NASA daily dates are UTC. Lag2 weather is
the conservative primary timing branch; lag1 is an overlapping-day benchmark.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

WEATHER = ['T2M', 'T2MDEW', 'RH2M', 'WS10M', 'PRECTOTCORR', 'PS']
PREDICTOR_WEATHER = ['T2M', 'RH2M', 'WS10M', 'PRECTOTCORR', 'PS']
UNITS = dict(T2M='degC', T2MDEW='degC', RH2M='percent', WS10M='m/s', PRECTOTCORR='mm/day', PS='kPa')


def load_daily(epa: Path, weather: Path) -> pd.DataFrame:
    e = pd.read_csv(epa); w = pd.read_csv(weather)
    for frame, date_column in [(e, 'date'), (w, 'date_utc')]:
        frame.index = pd.to_datetime(frame[date_column], errors='raise')
        if frame.index.hasnans or frame.index.duplicated().any():
            raise ValueError('Daily input dates must be nonmissing and unique')
        if not frame.index.equals(frame.index.normalize()):
            raise ValueError('Daily input labels must be midnight dates')
        if frame.index.tz is not None:
            raise ValueError('Use the explicitly documented naive daily date labels')
    e = e[['pm25_ugm3']].apply(pd.to_numeric, errors='raise')
    w = w[WEATHER].apply(pd.to_numeric, errors='raise')
    # Known public API fill values are missing, not zero rain/concentration.
    w = w.replace(-999, np.nan)
    if (e.pm25_ugm3.dropna() < 0).any():
        raise ValueError('Negative observed PM2.5 requires QA before analysis')
    if not np.isfinite(e.pm25_ugm3.dropna()).all():
        raise ValueError('Nonfinite observed PM2.5')
    w = w.replace([np.inf, -np.inf], np.nan)
    calendar = pd.date_range(e.index.min(), e.index.max(), freq='D')
    return e.join(w, how='left').reindex(calendar)


def aligned_pair(frame, column, alignment_shift_days=0, weather_lag_days=0):
    """At target d pair weather dated d + shift - lag (not shift in rows)."""
    series = frame[column].copy()
    series.index = series.index - pd.Timedelta(days=alignment_shift_days) + pd.Timedelta(days=weather_lag_days)
    return pd.concat([frame.pm25_ugm3.rename('pm25_ugm3'), series.rename(column)], axis=1, sort=True).dropna()


def adjusted_residuals(pair, adjustment):
    if adjustment == 'raw':
        return pair
    month = pd.get_dummies(pair.index.month, prefix='month', drop_first=True, dtype=float)
    month.index = pair.index
    matrix = [np.ones((len(pair), 1)), month.to_numpy()]
    if adjustment == 'year_and_calendar_month':
        year = pd.get_dummies(pair.index.year, prefix='year', drop_first=True, dtype=float)
        matrix.append(year.to_numpy())
    elif adjustment != 'calendar_month':
        raise ValueError('Unknown adjustment')
    design = np.column_stack(matrix)
    values = pair.to_numpy(dtype=float)
    residual = values - design @ np.linalg.lstsq(design, values, rcond=None)[0]
    return pd.DataFrame(residual, index=pair.index, columns=pair.columns)


def association_tables(frame):
    rows = []
    for shift in [-1, 0, 1]:
        for lag in range(8):
            for column in WEATHER:
                pair = aligned_pair(frame, column, shift, lag)
                for adjustment in ['raw', 'calendar_month', 'year_and_calendar_month']:
                    residual = adjusted_residuals(pair, adjustment)
                    for method in ['pearson', 'spearman']:
                        coefficient = residual.iloc[:, 0].corr(residual.iloc[:, 1], method=method) if len(pair) > 2 else np.nan
                        rows.append(dict(weather=column, unit=UNITS[column], alignment_shift_days=shift,
                                         weather_lag_days=lag, adjustment=adjustment, method=method,
                                         n=len(pair), correlation=coefficient))
    return pd.DataFrame(rows)


def vif_table(frame):
    rows = []
    for label, columns in [('all_six', WEATHER), ('omit_dewpoint', PREDICTOR_WEATHER)]:
        values = frame[columns].dropna()
        standardized = (values - values.mean()) / values.std(ddof=0)
        for column in columns:
            y = standardized[column].to_numpy()
            x = np.column_stack([np.ones(len(values)), standardized.drop(columns=column).to_numpy()])
            residual = y - x @ np.linalg.lstsq(x, y, rcond=None)[0]
            denominator = float(residual @ residual)
            total = float(y @ y)
            vif = total / denominator if denominator > 1e-12 else np.inf
            rows.append(dict(feature_set=label, weather=column, unit=UNITS[column], n=len(values), VIF=vif))
    return pd.DataFrame(rows)


def features_for_prediction(frame):
    """Calendar-day shifts preserve missing dates. No current weather/target."""
    frame = frame.reindex(pd.date_range(frame.index.min(), frame.index.max(), freq='D'))
    f = pd.DataFrame(index=frame.index)
    for lag in [1, 7, 365]:
        f[f'pm25_lag_{lag}'] = frame.pm25_ugm3.shift(lag)
    phase = (frame.index.day_of_year - 1) / np.where(frame.index.is_leap_year, 366, 365)
    f['annual_sin'] = np.sin(2 * np.pi * phase)
    f['annual_cos'] = np.cos(2 * np.pi * phase)
    for column in PREDICTOR_WEATHER:
        f[f'{column}_lag_1'] = frame[column].shift(1)
        f[f'{column}_lag_2'] = frame[column].shift(2)
    return f


def metric_table(predictions):
    models = sorted(predictions.model.unique())
    output = []
    for period, part in [('validation_2018_2019', predictions[predictions.date.between('2018-01-01', '2019-12-31')]),
                         ('retrospective_test_2020_2021', predictions[predictions.date.between('2020-01-01', '2021-12-31')]),
                         *[(str(year), predictions[predictions.date.str.startswith(str(year))]) for year in range(2018, 2022)]]:
        wide = part.pivot(index='date', columns='model', values='prediction').reindex(columns=models)
        common = wide.index[wide.notna().all(axis=1)]
        for model in models:
            for sample_set in ['available_cases', 'common_cases']:
                values = part[part.model.eq(model)].dropna(subset=['prediction'])
                if sample_set == 'common_cases': values = values[values.date.isin(common)]
                error = values.prediction - values.observed
                n = len(values); denominator = ((values.observed - values.observed.mean()) ** 2).sum()
                output.append(dict(period=period, model=model, sample_set=sample_set, n=n,
                                   MAE=float(error.abs().mean()) if n else np.nan,
                                   RMSE=float(np.sqrt((error ** 2).mean())) if n else np.nan,
                                   bias=float(error.mean()) if n else np.nan,
                                   R2=float(1 - (error ** 2).sum() / denominator) if n > 1 and denominator > 0 else np.nan))
    return pd.DataFrame(output)


def predict_daily(frame, first_prediction='2018-01-01', alpha=1.0):
    """Monthly expanding refits; daily observed lags support rolling 1-step use.

    Nominal issue time is preceding day end; actual EPA/NASA publication latency
    is unknown, so this cannot establish a deployable operational forecast.
    """
    frame = frame.reindex(pd.date_range(frame.index.min(), frame.index.max(), freq='D'))
    feature = features_for_prediction(frame)
    core = ['pm25_lag_1', 'pm25_lag_7', 'pm25_lag_365', 'annual_sin', 'annual_cos']
    expanded = core + [f'{w}_lag_1' for w in PREDICTOR_WEATHER]
    safe_expanded = core + [f'{w}_lag_2' for w in PREDICTOR_WEATHER]
    result = []
    for origin in pd.date_range(pd.Timestamp(first_prediction), frame.index.max(), freq='MS'):
        train_dates = frame.index[(frame.index < origin) & frame.pm25_ugm3.notna()]
        if origin < frame.index.min() + pd.DateOffset(years=2) or len(train_dates) < 365:
            continue
        test_dates = frame.index[(frame.index >= origin) & (frame.index < origin + pd.offsets.MonthBegin(1)) & frame.pm25_ugm3.notna()]
        if not len(test_dates): continue
        y = frame.loc[train_dates, 'pm25_ugm3']
        climatology = y.groupby(y.index.month).mean()
        predictions = {
            'persistence': feature.loc[test_dates, 'pm25_lag_1'].to_numpy(),
            'seasonal_naive_365': feature.loc[test_dates, 'pm25_lag_365'].to_numpy(),
            'calendar_month_climatology': np.array([climatology.get(d.month, np.nan) for d in test_dates]),
        }
        for name, columns in [('ridge_calendar_lags', core), ('ridge_calendar_lags_weather', expanded), ('ridge_calendar_lags_weather_safe2', safe_expanded)]:
            model = make_pipeline(SimpleImputer(strategy='median', keep_empty_features=True), StandardScaler(), Ridge(alpha=alpha))
            model.fit(feature.loc[train_dates, columns], y)
            predictions[name] = model.predict(feature.loc[test_dates, columns])
        for model, values in predictions.items():
            for date, value in zip(test_dates, values):
                result.append(dict(date=date.strftime('%Y-%m-%d'), model=model, observed=float(frame.at[date, 'pm25_ugm3']),
                                   prediction=float(value), refit_date=origin.strftime('%Y-%m-%d'),
                                   training_end=train_dates.max().strftime('%Y-%m-%d'), n_train=len(train_dates),
                                   nominal_issue_date=(date - pd.Timedelta(days=1)).strftime('%Y-%m-%d'),
                                   timezone_alignment='BST_supported_in_mirror_window_full_record_QA_unverified', evaluation=('overlapping_day_conditional_benchmark' if model == 'ridge_calendar_lags_weather' else 'timing_conservative_retrospective_one_day_hindcast'),
                                   weather_lag_days=(1 if model == 'ridge_calendar_lags_weather' else 2 if model == 'ridge_calendar_lags_weather_safe2' else 0),
                                   primary_weather_branch=(model == 'ridge_calendar_lags_weather_safe2')))
    return pd.DataFrame(result)


def weather_interval_timing(target_date, lag_days):
    """Compare NASA UTC daily interval with preceding-midnight BST issue.

    This checks interval availability, not provider publication latency.
    """
    target = pd.Timestamp(target_date).normalize()
    weather_day = target - pd.Timedelta(days=lag_days)
    interval_end = weather_day.tz_localize('UTC') + pd.Timedelta(days=1)
    issue = target.tz_localize('Asia/Dhaka')
    return dict(weather_date=weather_day.strftime('%Y-%m-%d'),
                source_interval_end_utc=interval_end.isoformat(), nominal_issue_bst=issue.isoformat(),
                hours_after_issue=max(0., (interval_end - issue).total_seconds()/3600))


def weather_benefit_bootstrap(predictions, repetitions=1000, seed=20261107):
    rows = []
    for period, start, end in [('validation_2018_2019', '2018-01-01', '2019-12-31'), ('retrospective_test_2020_2021', '2020-01-01', '2021-12-31')]:
        part = predictions[predictions.date.between(start, end)]
        if part.empty:
            continue
        wide = part.pivot(index='date', columns='model', values='prediction')
        y = part.groupby('date')['observed'].first()
        for weather_model in ['ridge_calendar_lags_weather_safe2', 'ridge_calendar_lags_weather']:
            if weather_model not in wide:
                continue
            paired = pd.DataFrame({'observed': y, 'core': wide.ridge_calendar_lags, 'weather': wide[weather_model]})
            paired.index = pd.to_datetime(paired.index)
            paired = paired.reindex(pd.date_range(start, end, freq='D'))
            ce = (paired.core - paired.observed).to_numpy(); we = (paired.weather - paired.observed).to_numpy()
            finite = np.isfinite(ce) & np.isfinite(we)
            for block_days in [7, 30]:
                rng = np.random.default_rng(seed + block_days)
                mae_samples, rmse_samples = [], []
                n_calendar = len(paired)
                for _ in range(repetitions):
                    starts = rng.integers(0, n_calendar - block_days + 1, size=int(np.ceil(n_calendar / block_days)))
                    indices = np.concatenate([np.arange(i, i + block_days) for i in starts])[:n_calendar]
                    keep = indices[finite[indices]]
                    if len(keep):
                        mae_samples.append(float(np.mean(np.abs(we[keep])) - np.mean(np.abs(ce[keep]))))
                        rmse_samples.append(float(np.sqrt(np.mean(we[keep] ** 2)) - np.sqrt(np.mean(ce[keep] ** 2))))
                for metric, samples, point in [('MAE', mae_samples, np.mean(np.abs(we[finite])) - np.mean(np.abs(ce[finite]))),
                                               ('RMSE', rmse_samples, np.sqrt(np.mean(we[finite] ** 2)) - np.sqrt(np.mean(ce[finite] ** 2)))]:
                    lo, hi = np.quantile(samples, [.025, .975])
                    rows.append(dict(period=period, weather_model=weather_model, primary_weather_branch=weather_model.endswith('safe2'), block_days=block_days, metric=metric, n_pairs=int(finite.sum()),
                                     weather_minus_core=float(point), ci95_lower=float(lo), ci95_upper=float(hi),
                                     repetitions=repetitions, sign='negative favors weather', inference='conditional paired descriptive uncertainty; no model selection'))
    return pd.DataFrame(rows)


def figures(associations, metrics, output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    data = associations[associations.alignment_shift_days.eq(0) & associations.weather_lag_days.eq(0) & associations.method.eq('pearson')]
    table = data.pivot(index='weather', columns='adjustment', values='correlation').reindex(index=WEATHER, columns=['raw','calendar_month','year_and_calendar_month'])
    fig, ax = plt.subplots(figsize=(8, 4.5), layout='constrained')
    image = ax.imshow(table.to_numpy(), cmap='RdBu_r', vmin=-1, vmax=1, aspect='auto')
    ax.set_yticks(range(len(table)), table.index); ax.set_xticks(range(len(table.columns)), ['Raw','Month-adjusted','Year + month adjusted'], rotation=15)
    for i in range(len(table)):
        for j in range(len(table.columns)): ax.text(j, i, f'{table.iloc[i,j]:.2f}', ha='center', va='center')
    ax.set_title('PM₂.₅–weather Pearson associations\nNominal dates; full-record daily alignment/QA unresolved')
    fig.colorbar(image, ax=ax); fig.savefig(output/'weather_correlation_heatmap.png', dpi=180); plt.close(fig)
    fig, axes = plt.subplots(2, 3, figsize=(11, 6), sharex=True, sharey=True, layout='constrained')
    for ax, weather in zip(axes.flat, WEATHER):
        for shift in [-1, 0, 1]:
            part = associations[associations.weather.eq(weather) & associations.alignment_shift_days.eq(shift) & associations.adjustment.eq('calendar_month') & associations.method.eq('pearson')]
            ax.plot(part.weather_lag_days, part.correlation, label=f'date shift {shift:+d}', marker='o', markersize=3)
        ax.axhline(0, color='gray', lw=.5); ax.set_title(weather); ax.set_xlabel('Weather lag, days'); ax.set_ylabel('Month-adjusted r')
    axes.flat[0].legend(fontsize=8);fig.suptitle('Exploratory lag screen; direction is association, not causation')
    fig.savefig(output/'weather_lag_sensitivity.png', dpi=180);plt.close(fig)
    scored = metrics[metrics.period.eq('retrospective_test_2020_2021') & metrics.sample_set.eq('common_cases')]
    fig, ax = plt.subplots(figsize=(10, 4.5), layout='constrained')
    labels = {'calendar_month_climatology':'Training-month climatology','persistence':'Previous-day persistence','seasonal_naive_365':'Previous-year day','ridge_calendar_lags':'Ridge calendar + PM lags','ridge_calendar_lags_weather':'Ridge + lag1 weather (overlap benchmark)','ridge_calendar_lags_weather_safe2':'Ridge + lag2 weather (primary)'}
    ax.barh(scored.model.map(labels), scored.RMSE, color=['#397153' if m.endswith('safe2') else '#3e6b89' for m in scored.model])
    ax.set_xlabel('RMSE, µg/m³; identical observed dates');ax.set_title('2020–2021 retrospective diagnostics\nWeather safe2 primary; lag1 overlaps possible target hours')
    fig.savefig(output/'daily_model_comparison.png', dpi=180);plt.close(fig)


def run(epa, weather, output, bootstrap_repetitions=1000):
    if output.exists():
        raise ValueError('Output directory already exists; choose a new path to preserve previous analyses')
    frame = load_daily(epa, weather)
    output.mkdir(parents=True)
    associations = association_tables(frame); vif = vif_table(frame)
    prediction = predict_daily(frame); metrics = metric_table(prediction)
    uncertainty = weather_benefit_bootstrap(prediction, repetitions=bootstrap_repetitions)
    associations.to_csv(output/'associations_and_lags.csv', index=False);vif.to_csv(output/'weather_vif.csv', index=False)
    prediction.to_csv(output/'daily_predictions.csv', index=False);metrics.to_csv(output/'daily_metrics.csv', index=False)
    uncertainty.to_csv(output/'weather_increment_uncertainty.csv', index=False)
    figures(associations, metrics, output)
    manifest = dict(epa_sha256=hashlib.sha256(epa.read_bytes()).hexdigest(), weather_sha256=hashlib.sha256(weather.read_bytes()).hexdigest(),
                    calendar_days=len(frame), observed_target_days=int(frame.pm25_ugm3.notna().sum()), missing_target_days=int(frame.pm25_ugm3.isna().sum()),
                    date_range=[str(frame.index.min().date()), str(frame.index.max().date())], weather_units=UNITS,
                    association_alignment='weather_date = EPA nominal date + shift - lag; shifts -1/0/+1 all reported',
                    association_adjustment='descriptive residual correlations after calendar-month or year+calendar-month fixed effects; fit on inspected pairs, not predictive preprocessing',
                    prediction_alignment='nominal shift0; lag2weather PRIMARY conservative for UTC/BST daily intervals; lag1weather overlapping-day conditional benchmark only',
                    timing_evidence='Parent mirror cross-check supports BST-labelled EPA means in2019-Jun2020; full-record convention remains incompletely verified. NASA lag1 UTC daily interval ends06BST on targetday, after00BST nominal issue; lag2 ends06BST precedingday.',
                    interval_timing_examples={'lag1':weather_interval_timing('2020-01-02',1),'lag2':weather_interval_timing('2020-01-02',2)},
                    weather_choice='retain T2M,RH2M,WS10M,PRECTOTCORR,PS; omit thermodynamically redundant dewpoint from ridge, show VIF for both sets',
                    ridge_alpha=1.0, refit='expanding monthly; each training fold strictly before refit month; daily observed lag updates',
                    target_imputation=False, validation='2018-2019', retrospective_test='2020-2021; already inspected, not untouched',
                    uncertainty='paired calendar moving blocks 7 and30days, seed20261107, percentile95%; no model selection',
                    limitations=['EPA BST alignment supported by independent mirror in part of record; full-record timezone/QA not established. NASA dates UTC.',
                                 'NASA POWER/MERRA2 meteorology is model-derived, not original ERA5.',
                                 'Observed-data provenance does not establish independent reference-grade QA or exact daily completeness.',
                                 'Actual source publication latency unverified; results are conditional hindcasts, not operational forecasts.',
                                 'Lag screen exploratory and multiple comparisons uncorrected; no causal effect or optimal lag claim.',
                                 'The bootstrap is descriptive conditional uncertainty for these fitted forecasts; no causal interpretation.'])
    (output/'methods.json').write_text(json.dumps(manifest, indent=2)+'\n')
    current = metrics[metrics.period.eq('retrospective_test_2020_2021') & metrics.sample_set.eq('common_cases')]
    lines = ['# Observed PM₂.₅ and NASA weather: conditional analysis', '',
             'Independent hourly-mirror matching supports BST-labelled EPA means in part of the record; full-record QA/time conventions remain incompletely verified. NASA dates are UTC. Weather lag2 is the prespecified conservative primary branch. Lag1 weather is an overlapping-day conditional benchmark, not a forecast-available weather input.', '',
             f'Calendar days: {len(frame)}; observed PM₂.₅ days: {frame.pm25_ugm3.notna().sum()}; missing targets preserved: {frame.pm25_ugm3.isna().sum()}.', '',
             '## Prespecified methods', '',
             'All six weather fields are examined descriptively with Pearson/Spearman correlations, calendar-month residual adjustment, year+month fixed-effect adjustment, and exploratory lags0–7. Weather date offsets−1/0/+1 are all retained; none is selected as best. No IID significance p-values are asserted.', '',
             'VIF is computed on standardized complete-case weather. Ridge omits dewpoint while retaining temperature and relative humidity to reduce known thermodynamic redundancy; this is a declared physical choice, not tuned VIF thresholding. Data-derived anomalies are not inputs.', '',
             'Prediction uses fixed Ridge alpha1.0, target lags1/7/365 and annual sine/cosine. The primary weather extension adds lag2 T,RH,wind,rain and pressure: NASA UTC lag1 daily values extend to06BST on targetday, six hours beyond a midnightBST issue. A separate lag1 overlapping-day benchmark is retained and must not be described as forecast-available. Lag2 was chosen from the interval prerequisite, not its score. Calendar gaps are preserved; targets are never imputed. Median imputation/scaling fit separately within each monthly expanding training fold. Initial training is2016–2017; daily observed lag updates make this rolling one-day, not a multi-day batch forecast.', '',
             'Prediction uses nominal date alignment; all−1/0/+1 weather-date sensitivities remain descriptive. Primary lag2 avoids daily-interval overlap under both UTC and BST conventions, but does not establish actual release latency. EPA daily PM lag1 publication timing also remains unverified. No operational forecasting claim is made.', '',
             '## 2020–2021 common-case retrospective diagnostics', '', '| Model | n | MAE | RMSE | Bias | R² |', '|---|---:|---:|---:|---:|---:|']
    for row in current.itertuples(): lines.append(f'| {row.model} | {row.n} | {row.MAE:.3f} | {row.RMSE:.3f} | {row.bias:.3f} | {row.R2:.3f} |')
    lines += ['', 'Unmatched available-case metrics and yearly metrics are in daily_metrics.csv. Compare the common-case rows for cross-model rankings. Weather-increment uncertainty instead uses paired core/weather predictions and preserves missing calendar dates in7/30-day block bootstrap; negative deltas favor weather. No candidate/lag is selected from these retrospectively inspected dates.', '',
              '## Limits and next evidence', '',
              'Verify the EPA full-record averaging rule, valid-hour threshold and QA flags; verify NASA daily interval and actual release latency before any deployment claim. Report the complete weather-date-shift sensitivity, not only the most favorable coefficient. Residual season adjustment and predictive importance do not identify causal meteorological effects. No input file or legacy result is modified.', '']
    lines += ['## Observed conditional findings', '']
    nominal = associations[associations.alignment_shift_days.eq(0) & associations.weather_lag_days.eq(0) & associations.method.eq('pearson')]
    for column in WEATHER:
        row = nominal[nominal.weather.eq(column)].set_index('adjustment')
        lines.append(f'- {column}: raw Pearson r={row.loc["raw", "correlation"]:.3f}; month-adjusted r={row.loc["calendar_month", "correlation"]:.3f}; year+month-adjusted r={row.loc["year_and_calendar_month", "correlation"]:.3f}.')
    lines += ['', 'The large attenuation of temperature and pressure correlations after calendar adjustment shows that their raw associations are largely shared seasonal structure. Residual associations remain conditional/descriptive, not causal effects.', '',
              f'All-six weather maximum VIF is {vif.loc[vif.feature_set.eq("all_six"), "VIF"].max():.2f}; omitting dewpoint lowers the retained-set maximum to {vif.loc[vif.feature_set.eq("omit_dewpoint"), "VIF"].max():.2f}.', '',
              '### Paired weather increment uncertainty', '',
              '| Period | Weather branch | Block days | Metric | Paired days | Weather minus core | 95% interval |',
              '|---|---|---:|---|---:|---:|---|']
    for row in uncertainty.itertuples():
        lines.append(f'| {row.period} | {row.weather_model} | {row.block_days} | {row.metric} | {row.n_pairs} | {row.weather_minus_core:.3f} | [{row.ci95_lower:.3f}, {row.ci95_upper:.3f}] |')
    lines += ['', 'Negative deltas favor the weather extension. These paired case sets differ from the all-model common-case table, because persistence/seasonal baselines can be missing when previous observations are absent. Interpret the primary safe2 branch separately from the overlapping-day lag1 benchmark; use the prespecified branch and its intervals regardless of which score looks more favorable. The intervals condition on fitted models, nominal alignment and inspected historical data.', '']
    (output/'findings.md').write_text('\n'.join(lines))
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--epa', type=Path, required=True);parser.add_argument('--weather', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True);parser.add_argument('--bootstrap-repetitions', type=int, default=1000)
    args = parser.parse_args()
    if args.bootstrap_repetitions < 100: parser.error('Use at least100 bootstrap repetitions')
    print(json.dumps(run(args.epa, args.weather, args.output, args.bootstrap_repetitions), indent=2))


if __name__ == '__main__': main()
