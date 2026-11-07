"""Stage credited released-data reproduction results, comparisons and figure exports.

This helper copies completed outputs into a new review directory. It never fits
models, changes source concentrations, creates manuscripts or publishes to GitHub.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile


REPRODUCTION_TABLES = [
    'annual_precipitation_diagnostic.csv', 'blh_associations.csv', 'blh_deciles.csv',
    'final_vs_source_checks.csv', 'merra_26_candidate_vif.csv', 'merra_vif_diagnostic.csv',
    'meteorology_and_so2_intercomparison.csv', 'meteorology_calendar_season_sensitivities.csv',
    'numeric_summary.csv', 'paper_vs_reproduced.csv', 'pearson_correlation.csv',
    'pm25_intercomparison.csv', 'pm25_native_3hour_sensitivity.csv',
    'pollutant_calendar_month_climatology.csv', 'pollutant_local_hour_climatology.csv',
    'pollutant_monthly_time_series.csv', 'pollutant_notebook_season_sensitivity.csv',
    'pollutant_paper_table3_season_sensitivity.csv', 'quality_and_provenance.json',
    'released_vs_paper_season_counts.csv', 'source_merra_total_mass_sensitivity.csv',
]
COMPARISON_TABLES = ['analysis_manifest.json', 'block_uncertainty.json',
                     'daily_alignment_sensitivity.csv', 'monthly_matched_coverage.csv', 'reference_metrics.csv']
REPRODUCTION_FIGURES = ['blh_association', 'correlation', 'data_quality',
                        'pm25_cross_source', 'pollutant_climatology', 'workflow']
COMPARISON_FIGURES = ['independent_reference_comparison', 'matched_monthly_comparison']


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def publish(reproduction, comparison, map_dir, destination):
    quality = json.loads((reproduction / 'quality_and_provenance.json').read_text())
    agreement = json.loads((comparison / 'analysis_manifest.json').read_text())
    if quality['release_sha256'] != agreement['source_hashes']['HyAQMet.csv']:
        raise ValueError('Reproduction and comparison used different releases')
    if not quality['source_git_provenance']['all_supplied_source_files_match']:
        raise ValueError('Native source files do not match their inspected Git commit')
    records = []

    def copy(source, relative):
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        records.append({'path': relative, 'sha256': digest(target), 'bytes': target.stat().st_size})

    for name in REPRODUCTION_TABLES:
        copy(reproduction / name, 'results/reference/release/' + name)
    for name in COMPARISON_TABLES:
        copy(comparison / name, 'results/reference/observed_comparison/' + name)
    for source, names in [(reproduction, REPRODUCTION_FIGURES), (comparison, COMPARISON_FIGURES)]:
        for name in names:
            for extension in ['png', 'svg', 'pdf']:
                filename = name + '.' + extension
                copy(source / filename, 'figures/reference/' + filename)
    for extension in ['png', 'svg', 'pdf']:
        copy(map_dir / ('study_area.' + extension), 'figures/study_area.' + extension)
    copy(map_dir / 'map_manifest.json', 'data/maps/map_manifest.json')
    record = {'source_release_doi': '10.5281/zenodo.20705735',
              'source_paper_doi': '10.1002/gdj3.70111',
              'release_sha256': quality['release_sha256'],
              'source_git_provenance': quality['source_git_provenance'],
              'source_values_modified': False,
              'reproduction_is_not_original_dataset_creation': True,
              'PDF_scope': 'Single scientific figures only; no manuscript PDF',
              'publisher_sha256': digest(Path(__file__)), 'exports': records}
    (destination / 'results/reference/export_manifest.json').write_text(json.dumps(record, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['reproduction', 'comparison', 'map', 'output']:
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Choose a new output directory')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.reference-assets-', dir=args.output.parent) as temp:
        staging = Path(temp) / 'publication'
        staging.mkdir()
        publish(args.reproduction, args.comparison, args.map, staging)
        staging.rename(args.output)
    print(args.output)


if __name__ == '__main__':
    main()
