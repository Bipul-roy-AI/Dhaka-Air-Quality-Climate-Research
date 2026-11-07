# Questions to resolve archive provenance

Reference: Paul, Tapon (2026), *Bangladesh Air Quality Index (AQI) Dataset (2000–2025): Historical Hourly Air Pollution Data Across 103 Cities*, Mendeley Data V2, DOI [10.17632/9j447cynb9.2](https://doi.org/10.17632/9j447cynb9.2).

The DOI and public metadata identify the deposited dataset. To use its concentrations and historical changes scientifically, please clarify:

1. Which monitoring networks, instruments, APIs or model products produced each time segment? Please provide acquisition/preprocessing code and station/grid identifiers, including whether any records are reconstructed, simulated, interpolated, clipped or imputed.
2. What are the units of every pollutant, including CO before and after 4 August 2022? What timezone and averaging interval do the timestamp labels represent?
3. Did a provider, unit, processing method or source version change around 4 August 2022? The uploaded Dhaka series changes precision and CO scale at that boundary and lacks AQI for that day. This is a question about construction, not an assertion of fabrication.
4. Why do Dhaka and Azimpur have identical pollutant values for 28,968 overlapping hours? Do these location names refer to the same underlying model grid or copied source observations?
5. The supplied observation file contains 30 city names, while cities.csv lists 103. Is this a subset, an export limit, or the intended complete release? Are additional files available?
6. What US EPA AQI breakpoint edition, averaging windows and rounding/truncation rules were used? Is recomputation code available?
7. Are station-quality flags, calibration records and independent ground-reference comparisons available?

Do not infer answers from the DOI, plausible values or apparent seasonal patterns. Preserve received answers and source files as provenance evidence. This question list has not been sent to the depositor.

The study researcher should separately provide the actual meteorology/satellite extraction script and original variable metadata. The repository's template is not proven to have produced its current monthly climate table. Independent DoE or US Embassy monitor records, when obtainable with source/QA/time metadata, would enable ambient-concentration validation; without them, restrict claims to archive/product analysis.
