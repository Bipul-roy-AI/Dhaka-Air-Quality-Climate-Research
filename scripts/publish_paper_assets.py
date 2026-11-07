"""Select the manuscript's tables and figures from a completed four-track run.

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
    'figures/05_reference_agreement.png': 'reference/independent_reference_comparison.png',
    'figures/06_release_quality.png': 'hyaqmet/data_quality.png',
    'results/annual_pm25.csv': 'observed/annual_statistics.csv',
    'results/monthly_pm25.csv': 'observed/calendar_month_statistics.csv',
    'results/seasonal_pm25.csv': 'observed/four_season_statistics.csv',
    'results/trend.csv': 'observed/season_adjusted_trend_intervals.csv',
    'results/weather_correlations.csv': 'weather/associations_and_lags.csv',
    'results/reference_metrics.csv': 'reference/reference_metrics.csv',
    'results/reference_alignment.csv': 'reference/daily_alignment_sensitivity.csv',
    'results/precipitation_diagnostics.csv': 'hyaqmet/annual_precipitation_diagnostic.csv',
    'results/season_definition_comparison.csv': 'hyaqmet/released_vs_paper_season_counts.csv',
    'results/merra_vif_candidates.csv': 'hyaqmet/merra_26_candidate_vif.csv',
    'results/merra_vif_retained.csv': 'hyaqmet/merra_vif_diagnostic.csv',
    'results/quality_checks.json': 'hyaqmet/quality_and_provenance.json',
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
    if manifest['status'] != 'all_four_tracks_completed':
        raise ValueError('All four analysis tracks must finish before publication')
    for target, source in FILES.items():
        destination = out / target
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(run / source, destination)
    metrics = pd.read_csv(run / 'weather/daily_metrics.csv')
    metrics = metrics.loc[metrics.model.isin(PRIMARY_MODELS)].copy()
    metrics.to_csv(out / 'results/models.csv', index=False)
    increment = pd.read_csv(run / 'weather/weather_increment_uncertainty.csv')
    increment.loc[increment.weather_model.eq('ridge_calendar_lags_weather_safe2')].to_csv(
        out / 'results/weather_increment.csv', index=False)
    for definition, filename in [
        ('paper', 'pollutant_paper_table3_season_sensitivity.csv'),
        ('release', 'pollutant_notebook_season_sensitivity.csv'),
    ]:
        frame = pd.read_csv(run / 'hyaqmet' / filename, header=[0, 1], index_col=0)
        frame.columns = ['_'.join(column) for column in frame.columns]
        frame.index.name = 'season'
        frame.to_csv(out / f'results/seasonal_{definition}_definition.csv')
    common = metrics.loc[
        metrics.period.eq('retrospective_test_2020_2021') & metrics.sample_set.eq('common_cases')
    ].set_index('model').loc[list(PRIMARY_MODELS)]
    if len(common) != 5 or common.n.nunique() != 1:
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
    fig.text(.5, .01, 'Conditional hindcasts; the incremental weather-skill interval spans zero.', ha='center', fontsize=9)
    fig.tight_layout(rect=(0, .04, 1, .94))
    fig.savefig(out / 'figures/04_prediction.png', dpi=200)
    plt.close(fig)
    provenance = {
        'run': manifest,
        'observed': json.loads((run / 'observed/analysis.json').read_text()),
        'weather': json.loads((run / 'weather/methods.json').read_text()),
        'reference': json.loads((run / 'reference/analysis_manifest.json').read_text()),
        'reference_block_uncertainty': json.loads((run / 'reference/block_uncertainty.json').read_text()),
        'sources': {
            'epa': 'https://doi.org/10.23719/1528454',
            'nasa_power': 'https://power.larc.nasa.gov/api/temporal/daily/point',
            'nasa_request': {'latitude': 23.796374, 'longitude': 90.424614,
                             'start': '20160101', 'end': '20211231', 'time_standard': 'UTC',
                             'parameters': 'T2M,T2MDEW,RH2M,WS10M,PRECTOTCORR,PS', 'community': 'AG'},
            'hyaqmet_release': 'https://doi.org/10.5281/zenodo.20705735',
            'hyaqmet_native_repository': 'https://github.com/AdityBarua10/HyAQMet',
            'hyaqmet_native_commit': 'f23ee72d6bbec8a8ab36423295e14f1b8e3d4100',
            'airnow_mirror': 'https://doi.org/10.6084/m9.figshare.12687695.v2',
        },
        'presentation': 'Primary weather branch only in model table/figure; lag-one conditional sensitivity remains in full run.',
        'publisher_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
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
