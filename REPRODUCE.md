# Reproduce the study and published assets

Run from the repository root in a fresh checkout. Python 3.12 and [uv](https://docs.astral.sh/uv/) are required. Install the checked-in hash-pinned environment:

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

## Acquire and inspect the study inputs

Downloads require network access but no API keys. TLS and inspected checksums remain enabled. These commands use new output paths and preserve original exports. Investigate a changed checksum rather than bypassing verification.

```bash
python scripts/fetch_public_sources.py --output artifacts/reproduce_sources
python scripts/inspect_public_sources.py \
  --sources artifacts/reproduce_sources --output artifacts/reproduce_normalized
```

The fetch retrieves the EPA observed-data workbook, Figshare/AirNow hourly mirror ZIP and NASA POWER meteorology for2016–2021. The normalizer extracts observed EPA concentrations, preserves missing days, and checks NASA units/UTC dates. Preserve the download/inspection manifests. NASA POWER is model-derived meteorology, not the earlier climate table or another observed pollution target. The hourly mirror checks averaging conventions for the same station; it is not an independent second monitoring site.

## Run the observed-PM and weather analyses

Choose a fresh run directory. Include the mirror ZIP to reproduce the station-day sensitivity in the manuscript. Omitting `--mirror` runs the two principal analyses without that optional diagnostic.

```bash
python scripts/run_paper_style_analysis.py \
  --epa artifacts/reproduce_normalized/epa_observed_daily_calendar.csv \
  --weather artifacts/reproduce_normalized/nasa_power_embassy_daily_2016_2021.csv \
  --mirror artifacts/reproduce_sources/figshare_airnow_12cities.zip \
  --output artifacts/reproduce_run
```

| Run subdirectory | Script | Scope |
|---|---|---|
| `observed/` | `analyze_observed_reference.py` | Observed EPA coverage, seasonality, trend, episodes and weather-context diagnostics |
| `weather/` | `analyze_observed_weather.py` | Calendar-adjusted associations, date/lag sensitivities and bounded retrospective prediction |
| `station_day/` | `inspect_station_day.py` | Optional hourly-mirror daily averaging/timezone sensitivity |

`RUN_COMPLETE.json` appears only after all requested subprocesses succeed and the input hashes remain unchanged. It records input/script hashes. Per-track tables, figures and findings retain their interpretation limits. Calendar months are primary; the four-season and both explicitly defined six-season windows are sensitivity summaries with unequal durations and disclosed coverage.

Prediction results are retrospective. The primary weather extension uses conservative lag-2 UTC weather; lag-1 weather is a separately labelled overlapping-day conditional benchmark. Observed scoring targets are never imputed. Full-record daily QA, averaging conventions and publication latency remain incompletely verified. The analyses do not certify operational forecasting, causal meteorological effects or health outcomes.

## Stage the manuscript assets and rebuild the PDF

The publisher reads a completed study run and writes selected figures/results into a **new** directory. It neither publishes to GitHub nor overwrites checked-in assets.

```bash
python scripts/publish_paper_assets.py \
  --run artifacts/reproduce_run --output artifacts/reproduce_assets
```

Inspect the staged tables, figures and provenance first. The next commands deliberately **replace** curated assets and rebuild the PDF from the root manuscript. PDF generation additionally requires Pandoc, XeLaTeX and DejaVu Serif/DejaVu Sans Mono fonts; these are outside the Python lock.

```bash
cp artifacts/reproduce_assets/figures/* figures/
cp artifacts/reproduce_assets/results/* results/
pandoc README.md --standalone --pdf-engine=xelatex \
  -V mainfont='DejaVu Serif' -V monofont='DejaVu Sans Mono' \
  -V geometry:margin=0.8in -V fontsize=10pt -o paper.pdf
```

The publisher includes the five primary prediction models; the overlapping-day lag-1 benchmark stays in the full run. Optional station-day and six-season tables are staged when present. Exact image/PDF bytes can vary with graphics/document toolchains; compare input hashes, numerical tables, case counts and conclusions.

## Layout and history

- `README.md`: manuscript; `paper.pdf`: generated PDF.
- `figures/`, `results/`: curated assets; `scripts/`, `tests/`: analysis code and scientific checks.
- `requirements.in`, `requirements.lock`: declared and hash-pinned Python dependencies.
- `artifacts/`: ignored source acquisitions and complete run outputs; not committed input data.

Older phase folders/package/audit material remain recoverable from Git commit `273f9aae0b2e93c8e15c5ea1613112e8559f3671`. They are not inputs to this study reproduction; the mixed-provenance uploaded archive is not required. [DATA_SELECTION.md](DATA_SELECTION.md) documents the retained findings and exclusions. The fixed `results/archive_source_audit.json` snapshot is historical exclusion evidence, preserved separately from the outputs generated by this runner.
