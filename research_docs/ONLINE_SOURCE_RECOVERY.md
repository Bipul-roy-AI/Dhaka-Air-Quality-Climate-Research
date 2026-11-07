# Public source recovery: what is now available

The researcher does not need to supply files to begin the next evidence checks. Public sources were actually requested, downloaded and parsed, with TLS verification enabled. This update resolves deposited-file identity and obtains independent-monitor candidates and new documented meteorology. It does not reconstruct the unknown original acquisition history or certify the entire legacy archive.

## 1. The uploaded original is identified exactly

[Paul, Tapon, Mendeley Data V2, DOI10.17632/9j447cynb9.2](https://doi.org/10.17632/9j447cynb9.2) publishes a98,303,184-byte `AQI Bangladesh.csv`. Its published SHA256 is `8760175fc048eea4180b828fd60d10cb799a73a5144a7e4aca19ddbaf8dbdd62`, exactly matching the uploaded CSV. This is stronger evidence than matching the title or row count.

[Public file inventory](https://data.mendeley.com/public-api/datasets/9j447cynb9/files?folder_id=root&version=2&%24start=0&%24limit=1000) contains only that CSV and `cities.csv`, with no README or acquisition/generation code. The folder listing is empty. Public metadata does not identify instruments, segment-specific pollutant units, timestamp timezone or the August2022 construction change. Early Dhaka2000 records are already present in bounded V1 samples; it would be wrong to assume V2 alone introduced that history. V1/V2 scope/precision differ, but their reason remains unknown.

Saved evidence: [file inventory](source_metadata/online_recovery/mendeley_v2_files.json), [provenance investigation](source_metadata/online_recovery/mendeley_provenance_summary.json). Published-checksum agreement identifies deposited bytes; it does not independently authenticate measurements.

## 2. The later segment has a model-source fingerprint

A direct request to [Open-Meteo Air Quality API](https://open-meteo.com/en/docs/air-quality-api), `domains=cams_global`, at23.7104°N,90.40744°E and explicitUTC produced exact PM2.5 matches at the same naive clock labels for **all312 sampled hours** across four disjoint windows:

- 4–7August2022:96hours;
- 10–12January2023:72hours;
- 10–12July2024:72hours;
- 20–22November2025:72hours.

PM10 and ozone also match all312. CO matches308/312; NO2/SO2 match many values exactly and some early-window values differ by0.1. The last CO window includes four differences, so do not claim every pollutant is unchanged or every archive row was checked. These values are documented regional model output, not an independent ground-monitor series. The API explicitly reports GMT/UTC and concentration unitsµg/m³. This is strong evidence of common model lineage for the sampled later archive, but not the depositor's code or a certificate for every row. Retain a distinction between depositor documentation and source-fingerprint inference; do not assign units/timezone to the earlier history from this evidence.

Open-Meteo's official documentation lists CAMS Global historical availability fromAugust2022 onward, consistent with the detected archive boundary. This does not explain how earlier records were generated. Also distinguish CAMS Global forecast archives from the HyAQMet paper's CAMS EAC4 reanalysis; they are related product families, not identical datasets.

[Exact requests and match counts](source_metadata/online_recovery/openmeteo_fingerprints.json) are retained. A separately deposited [Open-Meteo/CAMS daily export, Zenodo10.5281/zenodo.18673791](https://doi.org/10.5281/zenodo.18673791), was downloaded too: its daily values correlate strongly but are not generally identical under unshifted date labels. It must not be described as an exact match or independent validation. Daily averaging/timezone choices matter.

## 3. Independent observed PM2.5 is publicly recoverable

### Official EPA research data

[EPA DOI10.23719/1528454](https://doi.org/10.23719/1528454), *Characterizing variations in ambient PM2.5 concentrations at the U.S. Embassy in Dhaka, Bangladesh using observations and the CMAQ modeling system*, provides five downloadable spreadsheets. [Figure1 data](https://pasteur.epa.gov/uploads/10.23719/1528454/Figure_1_data.xlsx) contains **2117 observed daily PM2.5 values during2016–2021**. Extract only the observed columns; do not confuse CMAQ or weather-normalized quantities with observations.

The workbook caption supplies2016-01-01–2021-12-31 and the observed column supplies a1-based day index. A full2192-day calendar preserves75 missing days. Exact daily averaging timezone, original station QC flags and the station-day completeness rule are not specified in this workbook, so they remain limitations. [Derived observed data](source_metadata/online_recovery/epa_embassy_daily_2016_2021.csv) and [manifest](source_metadata/online_recovery/monitor_reference_manifest.json) retain that qualification.

A first calendar-label monthly crosswalk gives72 overlapping months,69 meeting a diagnostic75%-reference-day coverage rule. This is a prespecified availability screen for this exploratory source check, not a validated station QA standard. [Crosswalk](source_metadata/online_recovery/epa_archive_monthly_diagnostic.csv) is a source diagnostic: legacy units/timezone and geographic support are unresolved, so it is **not** a publication-ready station bias/error estimate. The archive's2021 mean of monthly values158.71 and EPA's available-day2021 station mean98.02 use different constructions and spatial support; do not present their difference as a corrected pollution estimate.

### Hourly observation candidates

[Figshare DOI10.6084/m9.figshare.12687695.v2](https://doi.org/10.6084/m9.figshare.12687695.v2) is a CC BY4.0 secondary archive reporting AirNow DOS provenance. Its downloadable1.74MB ZIP contains a Dhaka file with12,777 rows from1January2019 to29June2020. Fields include **Raw Conc.**, unitsUG/M3,1Hr duration, local-time labels and QC status:12,718Valid,42Missing,17Invalid. Two timestamp duplicates require adjudication; do not count all rows or use NowCast/AQI instead of raw concentration. This is a candidate mirror of embassy measurements, not a second independent monitoring network.

Anonymous [OpenAQ public AWS records](https://openaq-data-archive.s3.amazonaws.com/records/csv.gz/locationid=8415/year=2024/month=01/location-8415-20240101.csv.gz) also work without an API key. Bounded2017/2024 samples yielded48 PM2.5 rows, explicit+06:00 offsets and unitsµg/m³ for sensor24434/location8415. Official AirNow metadata identifies the Dhaka diplomatic-post stationDK1010001 at23.796374,90.424614. [Sample data](source_metadata/online_recovery/openaq_embassy_sample.csv) are evidence of access and metadata, not a recovered full hourly history. The inspected2022 AWS listing lacks June–August, so that route does not directly verify the August4 boundary. The EPA, Figshare and OpenAQ sources may represent the same embassy station; never count them as three independent stations.

Tested DoE endpoints returned upstream/access failures in this environment. This establishes a retrieval limitation, not that DoE data do not exist or are unavailable to everyone.

## 4. Original extraction not recovered; a documented weather alternative works

All27 public repository commits were inspected: no original GEE script or executable extraction notebook was found. The old repository name redirects to the current repository. The sole ERA5 template does not establish how the monthly table was generated.

A new [NASA POWER Daily API request](https://power.larc.nasa.gov/api/temporal/daily/point?parameters=T2M%2CT2MDEW%2CRH2M%2CWS10M%2CPRECTOTCORR%2CPS&community=AG&longitude=90.40744&latitude=23.7104&start=20220101&end=20251231&format=JSON&time-standard=UTC) succeeded without credentials: **1461 UTC days,2022–2025**, at the archive's declared Dhaka coordinates. Six parameters are complete with zero-999 fill values: temperature/dewpoint°C, RH%, windm/s, precipitationmm/day and pressurekPa. [Request, units and checksum manifest](source_metadata/online_recovery/nasa_power_manifest.json).

The response identifies **MERRA2/POWER** sources. This is a newly acquired, explicitly identified meteorological candidate—not recovered ERA5, a substitute for station PM2.5, or proof of the old rainfall units. Keep it separate. For monthly processing, distinguish summed daily precipitation from mean daily precipitation and explicitly convert pressure if needed. No transformations or replacement model run were applied to the legacy climate export.

A second NASA request now also covers **2192 UTC days,2016–2021**, at the officially reported embassy coordinates23.796374,90.424614, matching the EPA record's date range. [Manifest and exact request](source_metadata/online_recovery/nasa_power_embassy_2016_2021_manifest.json). This resolves the date-coverage gap for a future measured-reference analysis. It does not establish that UTC weather days equal the EPA workbook's unspecified station-day averaging interval. Preserve that distinction before joining or fitting models.

Official product documentation was also accessible:

- [ERA5-Land monthly aggregated](https://developers.google.com/earth-engine/datasets/catalog/ECMWF_ERA5_LAND_MONTHLY_AGGR): flow bands such as `total_precipitation_sum` are monthly sums inmetres; multiplying by1000 produces monthlymm. CDS monthly means use different aggregation semantics.
- [MODIS MAIAC AOD](https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MCD19A2_GRANULES): scaling and QA need explicit handling.
- [MODIS daily LST](https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MOD11A1): scale0.02K, then Celsius conversion; daytime surface temperature is not air temperature.
- [Sentinel-5P NO2](https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S5P_OFFL_L3_NO2): tropospheric columnmol/m², beginning28June2018; not surface concentration.

Earth Engine/CDS authenticated extraction was not established. It is unnecessary for the already downloaded sources above; account/project access would only be needed if that additional route is chosen.

## Reproduce the bounded recovery

From the repository root with the existing project environment:

```bash
.venv/bin/python scripts/fetch_public_sources.py --output artifacts/public_sources_new
.venv/bin/python scripts/inspect_public_sources.py \
  --sources artifacts/public_sources_new --output artifacts/public_sources_inspected
```

The first command actually downloads bounded source artifacts and verifies the pinned EPA snapshot and Figshare checksum; the second reproduces the observed-only EPA extraction and NASA native-unit daily candidate without extra spreadsheet dependencies. Existing nonempty output directories are preserved. These commands were executed successfully in this session. The model pipeline, original exports and historical result snapshots were not replaced or relabelled as independently validated.

## Preferred next scientific step

Build an explicitly measured-reference study around the recoverable embassy period, after resolving daily interval/QC and representativeness. In parallel, retain the later archive as a clearly labelled CAMS-related model-product experiment. Matching-date2016–2021 NASA meteorology is now recovered; align station-day intervals and assess QC before evaluating meteorological benefit. The separate2022–2025 candidate applies to the later archive, not the earlier EPA reference. Do not join disjoint dates or report model-to-model agreement as ground validation. If a target or period changes, register that change and use new, source-appropriate validation rather than reusing the previous14-case scores as evidence.

No files are needed from the user immediately. Remaining unknown acquisition history may require a future depositor answer; no one was contacted. Reproducible new extraction can replace an unrecoverable script as a new version, but cannot retroactively authenticate the old one.
