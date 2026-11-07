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

Choose a fresh run directory. Include the mirror ZIP to reproduce the station-day sensitivity reported in the README. Omitting `--mirror` runs the two principal analyses without that optional diagnostic.

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

## Stage the research figures and tables

The publisher reads a completed study run and writes selected figures/results into a **new** directory. It neither publishes to GitHub nor overwrites checked-in assets.

```bash
python scripts/publish_paper_assets.py \
  --run artifacts/reproduce_run --output artifacts/reproduce_assets
```

Inspect the staged tables, figures and provenance first. The next commands deliberately **replace** the curated assets.

```bash
cp artifacts/reproduce_assets/figures/* figures/
cp artifacts/reproduce_assets/results/* results/
```

The publisher includes the five primary prediction models; the overlapping-day lag-1 benchmark stays in the full run. Optional station-day and six-season tables are staged when present. Exact image bytes can vary with the graphics toolchain; compare input hashes, numerical tables, case counts and conclusions.

## Layout and history

- `README.md`: research overview, methods, results and references.
- `figures/`, `results/`: curated assets; `scripts/`, `tests/`: analysis code and scientific checks.
- `requirements.in`, `requirements.lock`: declared and hash-pinned Python dependencies.
- `artifacts/`: ignored source acquisitions and complete run outputs; not committed input data.

Older phase folders/package/audit material remain recoverable from Git commit `273f9aae0b2e93c8e15c5ea1613112e8559f3671`. They are not inputs to this study reproduction; the mixed-provenance uploaded archive is not required. [DATA_SELECTION.md](DATA_SELECTION.md) documents the retained findings and exclusions. The fixed `results/archive_source_audit.json` snapshot is historical exclusion evidence, preserved separately from the outputs generated by this runner.

## Optional reanalysis dataset and paired station comparison

The primary observed-PM/weather runner remains independent of this component. To inspect the same ERA5-Land, ERA5 single-level, CAMS EAC4 and MERRA-2 source families as the cited HyAQMet dataset, acquire its exact inspected release and pinned native-source checkout:

```bash
python scripts/fetch_hyaqmet_release.py --output artifacts/reproduce_release
git clone https://github.com/AdityBarua10/HyAQMet.git artifacts/reproduce_native
git -C artifacts/reproduce_native checkout --detach f23ee72d6bbec8a8ab36423295e14f1b8e3d4100
python scripts/analyze_hyaqmet.py \
  --releaseCSV artifacts/reproduce_release/HyAQMet.csv \
  --source-dir artifacts/reproduce_native/data \
  --output artifacts/reproduce_reanalysis --figure-dpi 600
python scripts/validate_hyaqmet_reference.py \
  --release artifacts/reproduce_release/HyAQMet.csv \
  --epa artifacts/reproduce_normalized/epa_observed_daily_calendar.csv \
  --output artifacts/reproduce_reference
```

The release fetch verifies the fixed Zenodo archive checksum. Preserve raw source bytes and compare native units/accumulation conventions before reusing derived fields; diagnostics do not silently repair the release. Calendar-month summaries remain primary, with explicitly separated season-definition sensitivities. Reanalysis source agreements are not independent station validation.

The paired-reference analysis adds timestamp-matched observed-PM comparisons over2017–2021 beyond aggregate literature benchmarks. It retains BST/UTC and−1/0/+1day alternatives without choosing the most favorable alignment, and computes monthly means on identical paired days with≥75% coverage. Seven-/30-day calendar-block intervals are conditional on the pairing; they do not resolve monitor QA or regional-versus-point representativeness. This is neither held-out forecasting nor bias calibration or causal/health inference. The hourly-mirror station-day diagnostic remains separate and is not a second independent site.

Both optional analysis scripts export600dpiPNG and SVG/PDF figures; SVG text remains editable and PDF fonts are embedded as TrueType. Full outputs remain ignored under `artifacts/`; selected files in `results/reference/` and `figures/reference/` are curated separately, not incorporated automatically by the primary asset publisher.

## Simple study-area map and reusable figure formats

The checked-in `data/maps/context.geojson`, adjacent `context_manifest.json` and `locations.geojson` permit an offline location-map redraw:

```bash
python scripts/make_study_area_map.py \
  --context data/maps/context.geojson --locations data/maps/locations.geojson \
  --output artifacts/reproduce_map --dpi 600
```

This is a credited study-location/context map, not a pollution surface, municipal boundary estimate or inferred extraction grid. Coordinates and source/CRS choices remain recorded in its manifest. To reacquire the pinned public-domain country context, run `python scripts/fetch_map_context.py --output artifacts/reproduce_map_context`; retain `context.geojson` and `context_manifest.json` together and pass that context path when redrawing.

After inspecting the output, refresh the curated map and its receipt explicitly:

```bash
cp artifacts/reproduce_map/study_area.* figures/
cp artifacts/reproduce_map/map_manifest.json data/maps/map_manifest.json
```

Use the 600dpiPNG for raster exports and SVG/PDF for editable/vector reuse. Dense scatter points may be rasterized within otherwise vector PDF figures. Figure export does not create a manuscript or manuscript PDF.

To stage the complete additional component, including its source-linked export manifest:

```bash
python scripts/publish_reference_assets.py \
  --reproduction artifacts/reproduce_reanalysis \
  --comparison artifacts/reproduce_reference --map artifacts/reproduce_map \
  --output artifacts/reproduce_reference_assets
```

After review, copy its `figures/reference/`, `results/reference/`, `figures/study_area.*` and `data/maps/map_manifest.json` to the matching repository paths. The helper verifies that reproduction and comparison use the same release and that native source files match the inspected Git commit. It does not change the primary observed-study assets or source data.
