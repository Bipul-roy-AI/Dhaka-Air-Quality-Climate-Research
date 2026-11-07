"""Conditional paired reanalysis–station comparison with date sensitivity.

Uses observed EPA station daily values as the point reference, not another
reanalysis. All daily alignments are retained; none is chosen by its score.
The separate inspect_station_day.py checks hourly-mirror averaging conventions.
"""
from pathlib import Path
import argparse
import hashlib
import json
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

plt.rcParams.update({'pdf.fonttype': 42, 'ps.fonttype': 42, 'svg.fonttype': 'none',
                     'font.family': 'DejaVu Sans', 'font.size': 10})


def metrics(frame):
    d = frame[['observed', 'model']].replace([np.inf, -np.inf], np.nan).dropna()
    if d.empty:
        return dict(n=0, bias=np.nan, MAE=np.nan, RMSE=np.nan, Pearson_r=np.nan,
                    Spearman_rho=np.nan, R2=np.nan)
    error = d.model - d.observed
    denominator = ((d.observed - d.observed.mean()) ** 2).sum()
    return dict(n=len(d), bias=float(error.mean()), MAE=float(error.abs().mean()),
                RMSE=float(np.sqrt((error ** 2).mean())),
                Pearson_r=float(d.observed.corr(d.model)) if len(d) > 1 else np.nan,
                Spearman_rho=float(spearmanr(d.observed, d.model).statistic) if len(d) > 1 else np.nan,
                R2=float(1 - (error ** 2).sum()/denominator) if denominator > 0 else np.nan)


def model_daily(data, basis='BST', min_hours=18):
    """Aggregate release's explicit BST hour labels without guessing station days."""
    if not 1 <= min_hours <= 24:
        raise ValueError('Daily coverage must be between 1 and24 hours')
    d = data[['ts', 'cams_pm25_ugm3']].copy()
    timestamps = pd.to_datetime(d.ts, errors='raise')
    if timestamps.isna().any() or timestamps.duplicated().any():
        raise ValueError('Missing or duplicate release hour')
    if timestamps.dt.tz is not None:
        raise ValueError('Release ts must be the documented timezone-naive BST labels')
    timestamps = timestamps.dt.tz_localize('Asia/Dhaka')
    if basis == 'UTC':
        timestamps = timestamps.dt.tz_convert('UTC')
    elif basis != 'BST':
        raise ValueError('Unknown daily basis')
    d.index = timestamps
    values = pd.to_numeric(d.cams_pm25_ugm3, errors='raise').where(lambda x: np.isfinite(x) & x.ge(0))
    daily = values.resample('D').agg(['mean', 'count'])
    daily.index = daily.index.tz_localize(None)
    daily.loc[daily['count'] < min_hours, 'mean'] = np.nan
    return daily.rename(columns={'mean': 'model', 'count': 'model_hours'})


def monthly_common_pairs(pairs, min_coverage=.75):
    """Average both sources on exactly the same matched days; retain coverage."""
    d = pairs[['observed', 'model']].replace([np.inf, -np.inf], np.nan).dropna()
    mean = d.resample('MS').mean()
    mean['matched_days'] = d.observed.resample('MS').count()
    mean['expected_days'] = mean.index.days_in_month
    mean['coverage'] = mean.matched_days/mean.expected_days
    mean['eligible'] = mean.coverage.ge(min_coverage)
    return mean


def block_uncertainty(pairs, block=30, reps=1000, seed=726):
    # Full calendar windows retain gaps instead of compressing missing dates.
    if pairs.index.duplicated().any():
        raise ValueError('Duplicate paired date')
    full = pairs[['observed', 'model']].sort_index()
    full = full.reindex(pd.date_range(full.index.min(), full.index.max(), freq='D'))
    values_array = full.to_numpy(float)
    n = len(values_array)
    rng = np.random.default_rng(seed)
    values = {k: [] for k in ['bias', 'MAE', 'RMSE', 'Pearson_r']}
    if n < block:
        return {}
    for _ in range(reps):
        starts = rng.integers(0, n-block+1, size=int(np.ceil(n/block)))
        indices = np.concatenate([np.arange(start, start+block) for start in starts])[:n]
        draw = values_array[indices]
        draw = draw[np.isfinite(draw).all(axis=1)]
        if len(draw) < 3:
            continue
        error = draw[:, 1] - draw[:, 0]
        coefficients = dict(bias=error.mean(), MAE=np.abs(error).mean(),
                            RMSE=np.sqrt(np.mean(error**2)),
                            Pearson_r=np.corrcoef(draw[:, 0], draw[:, 1])[0, 1])
        for key, value in coefficients.items():
            if np.isfinite(value):
                values[key].append(float(value))
    return {key: dict(lower=float(np.quantile(draw, .025)), upper=float(np.quantile(draw, .975)), draws=len(draw))
            for key, draw in values.items() if draw}


def save_figure(figure, output, name):
    for extension in ['png', 'svg', 'pdf']:
        figure.savefig(output/f'{name}.{extension}', dpi=600, bbox_inches='tight')
    plt.close(figure)


def run(release, epa, output, bootstrap_reps=1000):
    if output.exists():
        raise ValueError('Choose a new output directory')
    if bootstrap_reps < 20:
        raise ValueError('At least20 bootstrap replicates are required')
    raw = pd.read_csv(release)
    station = pd.read_csv(epa, parse_dates=['date']).set_index('date')
    if station.index.hasnans or station.index.duplicated().any():
        raise ValueError('Missing or duplicate station date')
    ref = pd.to_numeric(station.pm25_ugm3, errors='raise').where(lambda x: np.isfinite(x) & x.ge(0))
    calendar = pd.date_range('2017-01-01', '2021-12-31', freq='D')
    rows, daily_outputs = [], []
    primary = None
    for basis in ['BST', 'UTC']:
        daily = model_daily(raw, basis)
        for shift in [-1, 0, 1]:
            shifted = daily.copy()
            shifted.index = shifted.index + pd.Timedelta(days=shift)
            pair = pd.DataFrame({'observed': ref.reindex(calendar), 'model': shifted.model.reindex(calendar)})
            rows.append(dict(model_daily_basis=basis, model_calendar_shift_days=shift, **metrics(pair)))
            detail = pair.copy()
            detail['model_daily_basis'] = basis
            detail['model_calendar_shift_days'] = shift
            daily_outputs.append(detail)
            if basis == 'BST' and shift == 0:
                primary = pair
    if not metrics(primary)['n']:
        raise ValueError('No matched observed reference days')
    output.mkdir(parents=True)
    pd.DataFrame(rows).to_csv(output/'daily_alignment_sensitivity.csv', index=False)
    pd.concat(daily_outputs).rename_axis('date').to_csv(output/'paired_daily_all_alignments.csv')
    months = monthly_common_pairs(primary)
    months.to_csv(output/'monthly_matched_coverage.csv')
    summaries = [dict(scope='nominal_BST_daily', **metrics(primary)),
                 dict(scope='nominal_BST_monthly_ge75pct_reference_days', **metrics(months.loc[months.eligible]))]
    for year, group in primary.groupby(primary.index.year):
        summaries.append(dict(scope=f'year_{year}', **metrics(group)))
    for season, month_numbers in [('DJF', [12, 1, 2]), ('MAM', [3, 4, 5]), ('JJAS', [6, 7, 8, 9]), ('ON', [10, 11])]:
        summaries.append(dict(scope='conventional_'+season, **metrics(primary.loc[primary.index.month.isin(month_numbers)])))
    pd.DataFrame(summaries).to_csv(output/'reference_metrics.csv', index=False)
    uncertainty = {str(block): block_uncertainty(primary, block, bootstrap_reps) for block in [7, 30]}
    (output/'block_uncertainty.json').write_text(json.dumps(uncertainty, indent=2)+'\n')
    matched = primary.dropna()
    figure, axes = plt.subplots(2, 1, figsize=(10.5, 7), layout='constrained')
    axes[0].plot(primary.index, primary.observed, color='#25313d', lw=.6, label='Published Embassy daily observations')
    axes[0].plot(primary.index, primary.model, color='#b24e27', alpha=.75, lw=.6, label='CAMS daily mean, BST')
    axes[0].legend(fontsize=9, frameon=False)
    axes[0].set_ylabel('PM₂.₅ (µg/m³)')
    axes[0].set_title('Paired regional-reanalysis / point-monitor comparison, 2017–2021')
    axes[1].scatter(matched.observed, matched.model, s=7, alpha=.22, color='#326e85', rasterized=True)
    limit = float(matched.max().max())
    axes[1].plot([0, limit], [0, limit], color='#444444', ls='--', lw=1, label='1:1')
    axes[1].set_xlabel('Embassy observed PM₂.₅ (µg/m³)')
    axes[1].set_ylabel('Regional CAMS PM₂.₅ (µg/m³)')
    axes[1].legend(frameon=False)
    for axis in axes:
        axis.spines[['top', 'right']].set_visible(False)
    save_figure(figure, output, 'independent_reference_comparison')
    figure, axis = plt.subplots(figsize=(10.5, 4), layout='constrained')
    paired_months = months.loc[months.eligible]
    axis.plot(paired_months.index, paired_months.observed, color='#25313d', label='Embassy matched-day mean')
    axis.plot(paired_months.index, paired_months.model, color='#b24e27', label='CAMS: same matched days')
    axis.legend(frameon=False)
    axis.set_ylabel('PM₂.₅ (µg/m³)')
    axis.set_title('Monthly comparison: identical paired days and ≥75% daily coverage')
    axis.spines[['top', 'right']].set_visible(False)
    save_figure(figure, output, 'matched_monthly_comparison')
    metadata = {
        'assumption': 'Nominal release BST calendar days compared with EPA date labels. UTC and ±1day sensitivity retained without selecting the best alignment from scores. Separate station-day checks support BST in part of the record; full-period averaging QA remains unresolved.',
        'comparison_type': 'Conditional paired observed-point-reference / regional-reanalysis comparison; different spatial supports, not calibration or operational/causal validation.',
        'comparison_period': '2017-01-01 through2021-12-31',
        'primary_alignment': 'Prespecified BST daily means, shift0',
        'shift_definition': 'Model date labels are shifted by the reported number of calendar days before pairing.',
        'primary_metrics': metrics(primary),
        'bootstrap': 'Moving calendar blocks of7/30days; conditional sampling intervals, not measurement/model-structural uncertainty.',
        'bootstrap_replicates': bootstrap_reps, 'minimum_model_daily_hours': 18,
        'minimum_monthly_paired_coverage': .75,
        'monthly_mean_support': 'Both model and observation use the same paired days, not their separate available-day averages.',
        'figure_exports': '600dpi PNG; editable SVG text; PDF TrueType42 text with rasterized dense scatter only',
        'source_hashes': {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in [release, epa]},
        'analysis_value_added': 'Timestamp-paired observed station comparison beyond aggregate literature benchmarks; not a claim to have validated every variable or independent information source.',
    }
    (output/'analysis_manifest.json').write_text(json.dumps(metadata, indent=2, allow_nan=False)+'\n')
    primary_metrics = metadata['primary_metrics']
    (output/'findings.md').write_text(
        '# Conditional paired station-reference comparison\n\n'
        f"Matched daily cases: {primary_metrics['n']}. Nominal BST bias {primary_metrics['bias']:.3f}, RMSE {primary_metrics['RMSE']:.3f}, MAE {primary_metrics['MAE']:.3f}µg/m³; Pearson r {primary_metrics['Pearson_r']:.3f}. Bias is model minus reference.\n\n"
        f"{metadata['assumption']}\n\n"
        'Both monthly means use identical paired days with≥75% calendar coverage. Seven- and30-day bootstrap intervals condition on pairing and do not resolve QA or regional-versus-point representativeness. Correlation alone does not establish accurate absolute concentrations. No held-out forecast, bias calibration, causal attribution or health-outcome analysis was performed.\n\n'
        'This adds timestamp-matched observed-reference evaluation to the source paper’s aggregate literature comparisons; its interpretation remains limited to the checked target, window and spatial supports. Station-day mirror checks are run separately by inspect_station_day.py, not duplicated here.\n')
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--release', type=Path, required=True)
    parser.add_argument('--epa', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--bootstrap-reps', type=int, default=1000)
    args = parser.parse_args()
    result = run(args.release, args.epa, args.output, args.bootstrap_reps)
    print(json.dumps(result['primary_metrics'], indent=2))


if __name__ == '__main__':
    main()
