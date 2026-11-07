# Reproduce the executed analysis

Use the project Python3.12 environment and hash-pinned requirements from the root README. No secret is needed for these public downloads. Source ZIPs/native extracts are kept outside tracked result tables. Credit HyAQMet's creators, EPA/Sarwar et al., NASA POWER and the AirNow mirror creators.

## Acquire sources without replacing old exports

```bash
.venv/bin/python scripts/fetch_public_sources.py --output artifacts/public_sources_new
.venv/bin/python scripts/inspect_public_sources.py \
  --sources artifacts/public_sources_new --output artifacts/public_sources_normalized_new
.venv/bin/python scripts/fetch_hyaqmet_release.py --output artifacts/hyaqmet_release_new
```

Fetch the native GitHub extracts at the inspected version (the notebook is not executed):

```bash
git clone https://github.com/AdityBarua10/HyAQMet.git artifacts/hyaqmet_github
git -C artifacts/hyaqmet_github checkout f23ee72d6bbec8a8ab36423295e14f1b8e3d4100
```

Use fresh destinations; clone/analysis commands will preserve existing nonempty output directories. The final release's pinned ZIP md5 and SHA256 are checked before explicit CSV/README members are read; the extraction does not trust arbitrary archive paths.

## Run all four analysis tracks

```bash
.venv/bin/python scripts/run_paper_style_analysis.py \
  --release artifacts/hyaqmet_release_new/HyAQMet.csv \
  --hyaqmet-source-dir artifacts/hyaqmet_github/data \
  --epa artifacts/public_sources_normalized_new/epa_observed_daily_calendar.csv \
  --weather artifacts/public_sources_normalized_new/nasa_power_embassy_daily_2016_2021.csv \
  --mirror artifacts/public_sources_new/figshare_airnow_12cities.zip \
  --output artifacts/paper_style_new
```

This runs `analyze_hyaqmet.py`, `analyze_observed_reference.py`, `analyze_observed_weather.py` and `validate_hyaqmet_reference.py` as separate processes. Bootstrap counts default to1000. `RUN_COMPLETE.json` appears only after all four tracks succeed, with input/script hashes. Per-track methods retain source/QA/time assumptions. The two weather branches are not interchangeable: conservative lag2 is primary, while lag1 may overlap local target hours.

In a read-only or shared home directory, set writable `MPLCONFIGDIR` and `XDG_CACHE_HOME` before plotting. Limiting BLAS threads can reduce oversubscription, e.g. `OPENBLAS_NUM_THREADS=2`. No source notebook, model pin or global hook is installed.

## Render reports and check results

```bash
.venv/bin/python scripts/build_paper_style_report.py --results artifacts/paper_style_new
.venv/bin/python -m unittest discover -s tests -v
```

The report generator writes/refreshes only its own summary Markdown, figure collection PDF, support schematic and inventory within the selected result directory. Four computational tracks refuse existing outputs. Existing tracked CSVs and original inputs are not changed.

The actual audited run in this repository is `research_docs/analysis_results/`. A fresh full four-track run was also executed under `artifacts/paper_style_reproduction/`; seven key numeric tables matched the reviewed results within numerical tolerance (rtol1e-8,atol1e-7), allowing insignificant BLAS rounding differences. Raw downloads, normalized reference extraction, actual source hashes, data quality and all methods are documented separately. Passing tests/reproduction does not certify the unknown original source history or operational data latency.

`ANALYSIS_REPORT.md` is the detailed methods/results document; `ANALYSIS_FIGURES.pdf` contains a portable summary and15figures. `ANALYSIS_REPORT.pdf`, when present, is a typeset copy generated with Pandoc/XeLaTeX; these optional document tools are not needed to run the analysis.

Optional typeset PDF (Pandoc and XeLaTeX installed in this environment):

```bash
pandoc research_docs/analysis_results/ANALYSIS_REPORT.md --standalone \
  --pdf-engine=xelatex -V mainfont="DejaVu Serif" -V monofont="DejaVu Sans Mono" \
  -V geometry:margin=0.8in -V fontsize=10pt \
  -o research_docs/analysis_results/ANALYSIS_REPORT.pdf
```
