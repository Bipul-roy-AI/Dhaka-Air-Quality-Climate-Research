# Reproduce the paper and published assets

Run from the repository root in a fresh checkout. Python 3.12 and [uv](https://docs.astral.sh/uv/) are required. The checked-in `requirements.lock` pins dependencies and hashes; do not install the former editable package.

```bash
uv venv --python 3.12 .venv
uv pip sync --python .venv/bin/python --require-hashes requirements.lock
source .venv/bin/activate
mkdir -p artifacts/cache
export XDG_CACHE_HOME="$PWD/artifacts/cache"
export MPLCONFIGDIR="$PWD/artifacts/cache/matplotlib"
python -m unittest discover -s tests -v
```

`requirements.in` declares direct dependencies. Regenerate the lock only when deliberately updating dependencies, then rerun the tests and analyses:

```bash
uv pip compile requirements.in --python-version 3.12 --generate-hashes -o requirements.lock
```

## Acquire and inspect the inputs

Downloads require network access but no API keys. TLS and inspected release checksums remain enabled. The commands below use new output paths and refuse to overwrite existing source exports. Preserve their manifests. If a checksum changes, investigate the changed source rather than bypassing verification.

```bash
python scripts/fetch_public_sources.py --output artifacts/reproduce_sources
python scripts/inspect_public_sources.py \
  --sources artifacts/reproduce_sources --output artifacts/reproduce_normalized
python scripts/fetch_hyaqmet_release.py --output artifacts/reproduce_release

git clone https://github.com/AdityBarua10/HyAQMet.git artifacts/reproduce_native
git -C artifacts/reproduce_native checkout --detach f23ee72d6bbec8a8ab36423295e14f1b8e3d4100
```

The source fetch retrieves the EPA observed-data workbook, Figshare/AirNow mirror ZIP and NASA POWER meteorology for2016–2021. The normalizer extracts observed EPA concentrations only, preserves missing days and checks NASA units/UTC dates. The release fetch verifies the inspected Zenodo HyAQMet archive and extracts its CSV/README. Native source comparisons use the pinned GitHub checkout's `data/` directory, not an unpinned branch tip. NASA POWER is newly acquired model-derived weather, not the legacy climate table.

## Run all four analysis tracks

Use a fresh run directory. Include the mirror ZIP to reproduce the paper's station-day/timezone sensitivity checks; the runner also permits omission for a reduced analysis, which is not the complete paper reproduction.

```bash
python scripts/run_paper_style_analysis.py \
  --release artifacts/reproduce_release/HyAQMet.csv \
  --hyaqmet-source-dir artifacts/reproduce_native/data \
  --epa artifacts/reproduce_normalized/epa_observed_daily_calendar.csv \
  --weather artifacts/reproduce_normalized/nasa_power_embassy_daily_2016_2021.csv \
  --mirror artifacts/reproduce_sources/figshare_airnow_12cities.zip \
  --output artifacts/reproduce_run
```

| Run subdirectory | Script | Scope |
|---|---|---|
| `hyaqmet/` | `analyze_hyaqmet.py` | Released-data QA, climatology, native-source comparisons, VIF and BLH associations |
| `observed/` | `analyze_observed_reference.py` | Observed EPA coverage, temporal structure, trend/episode and weather-context diagnostics |
| `weather/` | `analyze_observed_weather.py` | Calendar-adjusted weather associations, date/lag sensitivities and bounded retrospective prediction |
| `reference/` | `validate_hyaqmet_reference.py` | Paired reanalysis–observed comparisons and independent hourly-mirror date sensitivities |

`RUN_COMPLETE.json` appears only after all four subprocesses succeed and records input/script hashes. Per-track CSVs, figures, methods and findings retain their own interpretation limits. Calendar months are primary; the paper Table 3 and notebook/released season definitions are both reported as sensitivities, not silently substituted or chosen by favorable results.

All prediction results are retrospective. The primary weather extension uses conservative lag-2 UTC weather; lag-1 weather is a separately labelled overlapping-day conditional benchmark. Missing observed targets are never imputed for scoring. Daily averaging QA, full-record timezone conventions and publication latency remain incompletely verified. These analyses do not certify operational forecasting, causality, health effects or independent accuracy of every reanalysis field.

## Publish the curated assets

The publisher reads one completed four-track run and stages selected figures/results in a **new** directory. It does not publish to GitHub or overwrite the paper's checked-in assets.

```bash
python scripts/publish_paper_assets.py \
  --run artifacts/reproduce_run --output artifacts/reproduce_assets
```

Inspect the staged files and manifest before deliberately refreshing the checked-in assets. The following commands **replace** curated figures/results and rebuild the PDF from the root manuscript. PDF generation additionally requires Pandoc, XeLaTeX and the DejaVu Serif/DejaVu Sans Mono fonts; they are outside the Python lock.

```bash
cp artifacts/reproduce_assets/figures/* figures/
cp artifacts/reproduce_assets/results/* results/
pandoc README.md --standalone --pdf-engine=xelatex \
  -V mainfont='DejaVu Serif' -V monofont='DejaVu Sans Mono' \
  -V geometry:margin=0.8in -V fontsize=10pt -o paper.pdf
```

Exact image/PDF bytes can vary with graphics or document toolchains; compare numerical tables, input hashes, case counts and scientific conclusions. The analysis runner and asset publisher do not themselves build the PDF.

## Repository layout and history

- `README.md`: manuscript and headline results; `paper.pdf`: its generated PDF.
- `figures/`, `results/`: curated published assets; `scripts/`, `tests/`: reproducible code and scientific checks.
- `requirements.in`, `requirements.lock`: declared and hash-pinned Python environment.
- `artifacts/`: ignored acquisitions, native checkout and complete run outputs; not committed source data.

Older phase folders, the former package and historical audit material are recoverable from Git commit `273f9aae0b2e93c8e15c5ea1613112e8559f3671`. They are not inputs to this reproduction. No uploaded mixed-provenance historical archive is required for these four tracks.
