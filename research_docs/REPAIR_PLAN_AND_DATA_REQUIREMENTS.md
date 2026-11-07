# Repair scope and data requirements

> **Online recovery update:** [Public-source findings](ONLINE_SOURCE_RECOVERY.md) now provide the deposited-file checksum match, actual EPA reference data, OpenAQ/AirNow samples and NASA POWER meteorology. The user does not need to find these files. Remaining questions below concern unresolved acquisition/QC history or optional further extraction, not a prerequisite to investigating the recovered sources.

This project follows the chosen order: **objectives or research questions → actual evidence → planning**. The repair pipeline addresses reproducibility and known counting/evaluation defects. It does not certify the source archive as measured ambient pollution, identify its underlying station/model provider, or turn existing results into validated long-term trends.

## Primary question and present scope

A suitable bounded question is: **Within a documented, source-consistent Dhaka record, do available meteorological inputs add out-of-time PM2.5 predictive value beyond persistence and seasonality?** The exact target follows its provenance: model-product prediction is not an independent test of ambient concentration accuracy.

The original archive has a construction boundary on **4 August 2022**. Its later segment supplies only **38 complete calendar months**, September 2022–October 2025. November 2025 stops after 23 days; December has no raw target. Later data are not automatically reference observations. The earlier segment remains available for source diagnosis, but its unverified origin prevents validated 2000–2025 atmospheric-trend claims.

## Repairs that can proceed with the available files

- Preserve original bytes and historical result exports. Record checksums and rebuild derived outputs separately.
- Select Dhaka explicitly, audit exact and conflicting timestamp duplicates, and retain source/coverage/QC flags. Do not pool Azimpur as another independent monitor: 28,968 overlapping hours have identical pollutant/AQI values.
- Count unique hourly observations, expected calendar hours and valid-target coverage separately. All 311 archived monthly counts match Dhaka+Azimpur pooled counts, whereas monthly PM2.5 means match Dhaka alone. For August 2022, blindly pooling rows gives a different mean; the legacy mean-aggregation implementation is still unknown.
- Preserve the source boundary and mixed-month flag rather than applying arbitrary offsets or harmonization to erase it. Do not create absent targets or score forward-filled targets as observations.
- Rebuild calendar lags without shifting across missing calendar months. Restrict eligible evaluations to complete months within the same selected regime.
- Use expanding, chronological one-step retrospective evaluation. Fit imputation/scaling inside each training fold, use lagged rather than future observed weather, and compare persistence, seasonal-naive, calendar climatology and a small fixed regularized-regression pilot.
- Score models on matched dates; publish the case count and target-unit/provenance limitations with every metric. Chronological splitting alone does not establish absence of leakage.

From the repository root, the rebuilt pipeline is invoked as:

```bash
python -m dhaka_air_quality --input /path/to/original.csv --output artifacts/rebuilt
```

The CLI also supports the supplied ZIP through its input reader. Follow the root README for environment setup and exact optional arguments. Outputs are reproducible **archive diagnostics and exploratory retrospective predictions**, not a new certified pollution product. The original Phase 2/3 tables remain historical exports.

## What the researcher needs to supply

The user identified the original source as **Paul, Tapon (2026), Mendeley Data V2, [doi:10.17632/9j447cynb9.2](https://doi.org/10.17632/9j447cynb9.2)**. Official public metadata gives a 21 January 2026 publication date, CC BY 4.0 licence, 1,048,551 hourly records, a claimed 103-city scope and US EPA AQI. This resolves the dataset attribution; it does **not** establish station instrumentation, pollutant units, timestamp conventions or how the early history was acquired/generated. The uploaded observation CSV contains 30 city names, whereas its city metadata lists 103 locations. Record this scope discrepancy rather than describing 103 observed city series.

Do not ask the researcher to provide the already supplied source URL again. Remaining source evidence may require contacting the depositor or locating its acquisition/generation materials. The following items remain necessary before stronger scientific claims or independent validation:

| Requirement | Please supply | Why it matters |
|---|---|---|
| Source record (identified) | Retain the supplied Mendeley DOI/V2 citation, official metadata and CC BY 4.0 attribution; record retrieval date and file checksums. Recover any separate README or acquisition materials if they exist. | Provider attribution and use terms are known; exact original-input and acquisition lineage still need reproducible records. |
| Early history | Acquisition or generation code and an explanation of how 2000–3 August 2022 records were produced; any synthetic, simulated, interpolated or clipped portions | Early data have unusually regular annual increases, repeated bounds and nested-PM ordering warnings. These do not prove fabrication, but cannot be resolved from a CSV alone. |
| Boundary history | Explanation and source exports around 4 August 2022; source/provider/version changes; append/merge scripts | Determines why precision, CO scale and AQI missingness change. Do not assume a unit conversion or physical event. |
| Pollution data dictionary | Unit per pollutant; PM mass definitions; AQI standard and averaging window; missing-value codes; QA flags; measured versus modelled status | CO's scale change is not sufficient evidence for an automatic 1000× conversion. Derived AQI must not be counted as an independent pollutant measurement. |
| Spatial identity | Station/instrument IDs and coordinates, or model grid IDs/resolution/extraction footprints; calibration and instrument methods where available | Nearby identical location series are not independent station validation. The supplied `cities.csv` and AQI IDs do not share a verified numeric crosswalk. |
| Time definitions | Timezone, timestamp interval start/end/centre, native sampling frequency, aggregation rules, publication latency | Prevents shifted joins and establishes which inputs actually existed at a forecast issue time. Current wall-clock timestamps must not silently be asserted as UTC or local time. |
| Climate and satellite extraction | Actual script/notebook used, product/version, variable metadata, extraction area/grid, retrieval QA masks and aggregation; rainfall accumulation/reset conventions | The committed extraction template requests ERA5 single levels, while legacy documentation says ERA5-Land. The template is not proven to generate the archived table. |
| Independent observations | Original DoE or US Embassy/AirNow monitor files with provenance, QA, station/coordinate, units and timestamp/averaging definitions | Needed for ambient-concentration validation. Another CAMS/reanalysis/API-derived export is not independent truth. Upload or link records securely; no secret API values belong in chat or tracked files. |
| Intended use | Retrospective regional estimation, one-step monthly forecasting, or another explicit target/horizon and decision | Determines the allowable predictor information set and whether daily/hourly analysis is scientifically warranted. |

If some records cannot be recovered, record the limitation and narrow the claim. Do not fabricate metadata, backfill an observed history, or silently substitute a different source.

## What to borrow from HyAQMet

Borrow its explicit source inventory, native extracts, timestamp/unit documentation, geographical support and reproducible validation structure. Do **not** copy transformations merely because they appear in a published paper:

- Its 2017–2022 regional reanalysis sources do not validate the user's full archive and do not resolve the user's August 2022 boundary.
- Native three-hourly CAMS interpolated to hourly does not add independent measurements. Future-endpoint interpolation cannot supply earlier forecast information.
- Public implementation checks found unit-description inconsistencies and an accumulation-versus-rate concern in precipitation. Check the actual provider metadata, resets and conservation before any conversion. The final Zenodo release was not validated in this project audit.
- Preserve original BLH and aerosol quantities; do not introduce a mixing relationship through a constructed proxy and then present its correlation as independent causal evidence.
- Figures are optional when useful; neither a compulsory schematic count nor six-season labels establish quality. Select seasons and covariates for the question, then report coverage and sensitivity.

## Gates for interpreting results

1. **Computational repair:** deterministic input→diagnostics/evaluation and meaningful tests. This is what the code repair establishes.
2. **Source acceptance:** documented acquisition/generation method, units, temporal/spatial support and eligibility rules. Records without verified measurement lineage remain excluded from primary ambient conclusions; citing a depositor does not itself establish that lineage.
3. **Prediction assessment:** fixed information timing, train-only transformations, common-case baseline comparison and uncertainty across temporal blocks. All currently inspected historical test periods are retrospective; they are not newly untouched holdouts.
4. **Independent validation:** matched reference monitoring with bias/error as well as correlation, coverage and seasonal checks. If unavailable, label the work as product intercomparison/emulation.
5. **Claim scope:** no causal emissions attribution, climate-change effect, source apportionment or health-outcome estimate follows from correlation/PCA/SHAP or the current data. Health relevance remains motivation unless matched health evidence and a suitable design are added.
