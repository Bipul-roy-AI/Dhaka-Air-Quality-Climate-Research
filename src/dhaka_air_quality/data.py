"""Conservative, provenance-bearing aggregation of the supplied hourly archive.

No station identity, physical units, or timezone is inferred from a city label.
The documented 2022 boundary is a diagnostic boundary, not a verified source ID.
"""
from __future__ import annotations

from contextlib import contextmanager
from hashlib import sha256
from pathlib import Path, PurePosixPath
import zipfile

import numpy as np
import pandas as pd

BOUNDARY = pd.Timestamp("2022-08-04 00:00:00")
POLLUTANTS = {
    "pm2_5": "pm25_mean", "pm10": "pm10_mean",
    "carbon_monoxide": "co_mean", "nitrogen_dioxide": "no2_mean",
    "sulphur_dioxide": "so2_mean", "ozone": "ozone_mean", "aqi": "aqi_mean",
}


def _hash_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


@contextmanager
def _input_stream(path: Path):
    """Read one archive member directly; never extract or trust archive paths."""
    if path.suffix.lower() != ".zip":
        with path.open("rb") as stream:
            yield stream, None
        return
    with zipfile.ZipFile(path) as archive:
        candidates = [i for i in archive.infolist() if not i.is_dir()
                      and PurePosixPath(i.filename).name.casefold() == "aqi bangladesh.csv"]
        if not candidates:
            candidates = [i for i in archive.infolist() if not i.is_dir()
                          and i.filename.lower().endswith(".csv")
                          and PurePosixPath(i.filename).name.casefold() != "cities.csv"]
        if len(candidates) != 1:
            raise ValueError("ZIP must contain one unambiguous air-quality CSV member")
        member = candidates[0]
        name = PurePosixPath(member.filename.replace("\\", "/"))
        if name.is_absolute() or ".." in name.parts or (name.parts and ":" in name.parts[0]):
            raise ValueError("Unsafe archive member path")
        if member.file_size > 2 * 1024**3:
            raise ValueError("Archive CSV exceeds the 2 GiB safety limit")
        with archive.open(member) as stream:
            yield stream, member.filename


def _timestamps(values: pd.Series) -> pd.Series:
    try:
        times = pd.to_datetime(values, errors="raise", format="mixed")
    except (ValueError, TypeError) as exc:
        raise ValueError("Invalid or inconsistent hourly timestamps") from exc
    if times.isna().any():
        raise ValueError("Missing hourly timestamp")
    if not pd.api.types.is_datetime64_any_dtype(times):
        raise ValueError("Mixed timezones are unsupported; harmonize explicit timezone metadata first")
    if times.dt.tz is not None:
        raise ValueError("Timezone-aware archive input requires an explicit harmonization decision")
    if not times.eq(times.dt.floor("h")).all():
        raise ValueError("Timestamps must be aligned to exact hours")
    return times


def _deduplicate_city(frame: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    # Compare every original field: source/quality/coordinates may be significant.
    distinct = frame.drop_duplicates()
    removed = len(frame) - len(distinct)
    if distinct["_timestamp"].duplicated().any():
        raise ValueError("Conflicting rows for the same city and timestamp; source adjudication required")
    return distinct.sort_values("_timestamp").copy(), removed


def _overlap_diagnostic(raw: pd.DataFrame, city: str, selected: pd.DataFrame) -> dict:
    if city != "Dhaka" or not raw.city_name.eq("Azimpur").any():
        return {"comparison_city": "Azimpur", "available": False}
    other = raw.loc[raw.city_name.eq("Azimpur")].copy()
    try:
        other["_timestamp"] = _timestamps(other.datetime)
        other, removed = _deduplicate_city(other)
    except ValueError as exc:
        return {"comparison_city": "Azimpur", "available": True, "status": "ambiguous", "reason": str(exc)}
    columns = [c for c in POLLUTANTS if c in selected and c in other]
    joined = selected[["_timestamp", *columns]].merge(
        other[["_timestamp", *columns]], on="_timestamp", suffixes=("_selected", "_other"), validate="one_to_one")
    match = pd.Series(True, index=joined.index)
    per_column = {}
    for column in columns:
        left, right = joined[column + "_selected"], joined[column + "_other"]
        eq = left.eq(right) | (left.isna() & right.isna())
        per_column[column] = int(eq.sum())
        match &= eq
    return {"comparison_city": "Azimpur", "available": True,
            "overlapping_unique_hours": len(joined),
            "identical_all_available_pollutant_hours": int(match.sum()),
            "matching_hours_by_field": per_column,
            "exact_duplicate_rows_removed_from_comparison": removed,
            "interpretation": "Identical location series are not independent observations; common source/grid identity remains unverified."}


def build_monthly(input_path: str | Path, city: str = "Dhaka") -> tuple[pd.DataFrame, dict]:
    """Build unfilled monthly targets and an input/source-quality audit.

    Empty months *inside* the observed span are represented with NaN targets and
    zero coverage. No month beyond the final raw timestamp is appended. A month
    marked primary_eligible is only eligible for the exploratory later-regime
    computational benchmark; it is not independently validated pollution data.
    """
    path = Path(input_path)
    if not path.is_file():
        raise FileNotFoundError(path)
    with _input_stream(path) as (stream, member):
        # Hash the exact CSV bytes as well as its enclosing ZIP, without extraction.
        digest = sha256()
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
        stream.seek(0)
        raw = pd.read_csv(stream, low_memory=False)
    required = {"city_name", "datetime", "pm2_5"}
    if not required.issubset(raw):
        raise ValueError(f"Missing required columns: {sorted(required - set(raw.columns))}")
    # Reject numeric parsing errors rather than silently converting text to missing.
    for column in POLLUTANTS:
        if column in raw:
            raw[column] = pd.to_numeric(raw[column], errors="raise")
    selected = raw.loc[raw.city_name.eq(city)].copy()
    if selected.empty:
        raise ValueError(f"No exact city_name match for {city!r}")
    selected["_timestamp"] = _timestamps(selected.datetime)
    selected, duplicate_rows = _deduplicate_city(selected)
    overlap = _overlap_diagnostic(raw, city, selected)
    selected["_valid_pm25"] = np.isfinite(selected.pm2_5) & selected.pm2_5.ge(0)
    selected["_negative_pm25"] = selected.pm2_5.lt(0)
    selected["_pm25_gt_pm10"] = (selected.pm2_5.gt(selected.pm10)
                                      if "pm10" in selected else False)
    selected["_clip5"] = selected.pm2_5.eq(5)
    selected["_clip250"] = selected.pm2_5.eq(250)
    selected["_period"] = selected._timestamp.dt.to_period("M")
    first, last = selected._timestamp.min(), selected._timestamp.max()
    rows = []
    for month in pd.period_range(first.to_period("M"), last.to_period("M"), freq="M"):
        group = selected.loc[selected._period.eq(month)]
        valid = group.loc[group._valid_pm25]
        expected = month.days_in_month * 24
        start, end = month.start_time, (month + 1).start_time
        regime = "earlier_unverified" if end <= BOUNDARY else (
            "later_unverified" if start >= BOUNDARY else "mixed")
        count, valid_count = len(group), len(valid)
        complete = count == expected and valid_count == expected
        row = {"date": start.strftime("%Y-%m-%d"), "source_regime": regime,
               "unique_hours": count, "expected_hours": expected,
               "valid_pm25_hours": valid_count,
               "coverage_fraction": valid_count / expected, "complete_month": complete,
               "negative_pm25_hours": int(group._negative_pm25.sum()),
               "pm25_gt_pm10_hours": int(group._pm25_gt_pm10.sum()),
               "pm25_exactly_5_hours": int(group._clip5.sum()),
               "pm25_exactly_250_hours": int(group._clip250.sum()),
               "target_imputed_by_pipeline": False, "upstream_imputation_status": "unknown", "source_validated": False,
               "timezone_status": "unverified_wall_clock", "concentration_units": "unverified"}
        for source, target in POLLUTANTS.items():
            values = valid[source] if source == "pm2_5" else group.get(source, pd.Series(dtype=float))
            finite = values.loc[np.isfinite(values)]
            row[target] = float(finite.mean()) if len(finite) else np.nan
        row["pm25_max"] = float(valid.pm2_5.max()) if valid_count else np.nan
        row["primary_eligible"] = bool(complete and regime == "later_unverified"
                                       and not row["pm25_gt_pm10_hours"])
        rows.append(row)
    monthly = pd.DataFrame(rows)
    audit = {"input_name": path.name, "input_sha256": _hash_file(path),
             "archive_member": member, "csv_sha256": digest.hexdigest(),
             "all_rows": len(raw), "all_city_names": int(raw.city_name.nunique()),
             "selected_city": city, "selected_unique_hours": len(selected),
             "exact_duplicate_rows_removed": duplicate_rows,
             "first_timestamp": str(first), "last_timestamp": str(last),
             "timestamp_timezone": "unverified; wall-clock timestamps retained without a UTC/BST assumption",
             "source_identity": "unverified", "units": "unverified",
             "recorded_city_ids": sorted(selected.city_id.dropna().astype(str).unique().tolist()) if "city_id" in selected else [],
             "recorded_coordinates": selected[["lat", "lon"]].drop_duplicates().to_dict("records") if {"lat", "lon"}.issubset(selected) else [],
             "nonfinite_or_missing_by_field": {c: int((~np.isfinite(selected[c])).sum()) for c in POLLUTANTS if c in selected},
             "negative_values_by_field": {c: int(selected[c].lt(0).sum()) for c in POLLUTANTS if c in selected},
             "source_validated": False, "diagnostic_boundary": str(BOUNDARY),
             "diagnostic_boundary_is_verified_source_identity": False,
             "primary_eligibility_meaning": "Complete observed later-regime computational cohort with no PM2.5>PM10 flags; not validated ambient concentration.",
             "input_span_expected_hours": int((last-first).total_seconds()/3600)+1,
             "missing_hours_within_input_span": int((last-first).total_seconds()/3600)+1-len(selected),
             "monthly_rows": len(monthly), "primary_eligible_months": int(monthly.primary_eligible.sum()),
             "negative_pm25_hours": int(selected._negative_pm25.sum()),
             "nonfinite_or_missing_pm25_hours": int((~np.isfinite(selected.pm2_5)).sum()),
             "pm25_gt_pm10_hours": int(selected._pm25_gt_pm10.sum()),
             "location_overlap": overlap,
             "no_target_imputation": True, "no_months_appended_beyond_last_raw_month": True}
    return monthly, audit
