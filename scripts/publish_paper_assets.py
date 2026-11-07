"""Select the manuscript's tables and figures from a completed observed-PM/weather study run.

Usage: python scripts/publish_paper_assets.py --run artifacts/run --output artifacts/paper
The destination must be new. No raw inputs or existing publication files change.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd


FILES = {
    'figures/01_seasonality.png': 'observed/observed_monthly_and_seasonal.png',
    'figures/02_trend.png': 'observed/observed_annual_and_adjusted_trend.png',
    'figures/03_weather_associations.png': 'weather/weather_correlation_heatmap.png',
    'figures/05_daily_coverage.png': 'observed/observed_daily_and_coverage.png',
    'results/observed_summary.json': 'observed/analysis.json',
    'results/annual_pm25.csv': 'observed/annual_statistics.csv',
    'results/monthly_pm25.csv': 'observed/calendar_month_statistics.csv',
    'results/seasonal_pm25.csv': 'observed/four_season_statistics.csv',
    'results/monthly_coverage.csv': 'observed/monthly_coverage_and_trend_inputs.csv',
    'results/episodes.csv': 'observed/pooled_p95_episodes.csv',
    'results/trend.csv': 'observed/season_adjusted_trend_intervals.csv',
    'results/weather_correlations.csv': 'weather/associations_and_lags.csv',
    'results/weather_vif.csv': 'weather/weather_vif.csv',
}
OPTIONAL_FILES = {
    'results/six_season_sensitivity.csv': 'observed/six_season_sensitivity.csv',
    'results/six_season_release_sensitivity.csv': 'observed/six_season_release_sensitivity.csv',
}

PRIMARY_MODELS = {
    'persistence': 'Previous-day\npersistence',
    'calendar_month_climatology': 'Calendar\nclimatology',
    'seasonal_naive_365': '365-day\nbaseline',
    'ridge_calendar_lags': 'Ridge: PM lags\n+ calendar',
    'ridge_calendar_lags_weather_safe2': 'Ridge + lag-two\nweather',
}


def publish(run, out):
    manifest = json.loads((run / 'RUN_COMPLETE.json').read_text())
    if manifest['status'] != 'all_study_tracks_completed':
        raise ValueError('The observed-PM/weather study run must finish before publication')
    tracks = [record['track'] for record in manifest['analyses']]
    if len(tracks) != len(set(tracks)) or not {'observed', 'weather'}.issubset(tracks) or not set(tracks).issubset({'observed', 'weather', 'station_day'}):
        raise ValueError('Unexpected or missing study analysis tracks')
    if any(record['status'] != 'completed' for record in manifest['analyses']):
        raise ValueError('Every declared study track must be completed')
    if ('mirror' in manifest['input_sha256']) != ('station_day' in tracks):
        raise ValueError('Station-day track and mirror input must agree')
    for target, source in FILES.items():
        destination = out / target
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(run / source, destination)
    for target, source in OPTIONAL_FILES.items():
        if (run / source).is_file():
            shutil.copyfile(run / source, out / target)
    if 'station_day' in tracks:
        shutil.copyfile(run / 'station_day/station_day_sensitivity.csv', out / 'results/station_day_sensitivity.csv')
    metrics = pd.read_csv(run / 'weather/daily_metrics.csv')
    metrics = metrics.loc[metrics.model.isin(PRIMARY_MODELS)].copy()
    metrics.to_csv(out / 'results/models.csv', index=False)
    increment = pd.read_csv(run / 'weather/weather_increment_uncertainty.csv')
    increment.loc[increment.weather_model.eq('ridge_calendar_lags_weather_safe2')].to_csv(
        out / 'results/weather_increment.csv', index=False)
    common = metrics.loc[
        metrics.period.eq('retrospective_test_2020_2021') & metrics.sample_set.eq('common_cases')
    ].set_index('model').loc[list(PRIMARY_MODELS)]
    if len(common) != 5 or common.n.nunique() != 1 or common.n.iloc[0] <= 0:
        raise ValueError('Primary comparison requires five models on identical cases')
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.7), sharey=True)
    colors = ['#8498ab', '#a9b5c2', '#c3ccd4', '#3182a0', '#087f8c']
    for ax, metric in zip(axes, ['MAE', 'RMSE']):
        bars = ax.barh(list(PRIMARY_MODELS.values()), common[metric], color=colors)
        ax.bar_label(bars, fmt='%.2f', padding=3, fontsize=9)
        ax.set_xlim(0, common[metric].max() * 1.2)
        ax.set_xlabel(f'{metric} (µg/m³; lower is better)')
        ax.spines[['top', 'right']].set_visible(False)
    axes[0].invert_yaxis()
    fig.suptitle(f'Retrospective prediction, 2020–2021: {int(common.n.iloc[0])} common days')
    primary_interval = increment.loc[increment.weather_model.eq('ridge_calendar_lags_weather_safe2') & increment.period.eq('retrospective_test_2020_2021') & increment.block_days.eq(30) & increment.metric.eq('RMSE')]
    interval_spans_zero = len(primary_interval) == 1 and primary_interval.ci95_lower.iloc[0] <= 0 <= primary_interval.ci95_upper.iloc[0]
    note = ('Conditional hindcasts; the incremental weather-skill interval spans zero.' if interval_spans_zero else 'Conditional hindcasts; source publication timing remains unverified.')
    fig.text(.5, .01, note, ha='center', fontsize=9)
    fig.tight_layout(rect=(0, .04, 1, .94))
    fig.savefig(out / 'figures/04_prediction.png', dpi=200)
    plt.close(fig)
    provenance = {
        'run': manifest,
        'observed': json.loads((run / 'observed/analysis.json').read_text()),
        'weather': json.loads((run / 'weather/methods.json').read_text()),
        'sources': {
            'epa': 'https://doi.org/10.23719/1528454',
            'nasa_power': 'https://power.larc.nasa.gov/api/temporal/daily/point',
            'nasa_request': {'latitude': 23.796374, 'longitude': 90.424614,
                             'start': '20160101', 'end': '20211231', 'time_standard': 'UTC',
                             'parameters': 'T2M,T2MDEW,RH2M,WS10M,PRECTOTCORR,PS', 'community': 'AG'},
        },
        'presentation': 'Primary weather branch only in model table/figure; lag-one conditional sensitivity remains in full run.',
        'publisher_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    if 'station_day' in tracks:
        provenance['station_day'] = json.loads((run / 'station_day/analysis.json').read_text())
        provenance['sources']['airnow_mirror'] = 'https://doi.org/10.6084/m9.figshare.12687695.v2'
    (out / 'results/provenance.json').write_text(json.dumps(provenance, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Choose a new output directory')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.paper-assets-', dir=args.output.parent) as temp:
        staging = Path(temp) / 'publication'
        staging.mkdir()
        publish(args.run, staging)
        staging.rename(args.output)
    print(f'Manuscript assets written to {args.output}')


if __name__ == '__main__':
    main()
