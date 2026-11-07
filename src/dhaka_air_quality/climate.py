"""Conservative ingestion of the existing monthly covariate export.

Only raw covariates are retained. No archived target, anomaly, lag, sentinel,
row-count or availability-derived source value may overwrite the rebuilt target.
Provider extraction units, source grid and timezone still require verification.
"""
from pathlib import Path
import hashlib
import pandas as pd

WEATHER = ["temperature", "dewpoint", "wind_speed", "rainfall_mm", "pressure"]
SATELLITE = ["AOD", "LST_C", "NO2"]


def join_climate(monthly: pd.DataFrame, path: str | Path):
    path = Path(path)
    raw = pd.read_csv(path)
    if "date" not in raw:
        raise ValueError("Climate table requires date")
    dates = pd.to_datetime(raw["date"], errors="raise")
    if dates.isna().any():
        raise ValueError("Climate dates must not be missing")
    if dates.dt.tz is not None:
        raise ValueError("Climate monthly labels must have an explicit agreed timezone convention")
    raw["date"] = dates.dt.to_period("M").dt.to_timestamp()
    if raw.date.duplicated().any():
        raise ValueError("Duplicate climate month: refusing a many-to-many join")
    columns = [c for c in WEATHER + SATELLITE if c in raw]
    if not columns:
        raise ValueError("Climate table contains no recognized covariates")
    for col in columns:
        raw[col] = pd.to_numeric(raw[col], errors="raise").replace([-999, float("inf"), -float("inf")], float("nan"))
        flag = f"{col}_available"
        if flag in raw:
            valid = pd.to_numeric(raw[flag], errors="raise")
            if not valid.isin([0, 1]).all():
                raise ValueError(f"Invalid binary availability flag: {flag}")
            raw.loc[valid == 0, col] = float("nan")
    if "climate_available" in raw:
        valid = pd.to_numeric(raw.climate_available, errors="raise")
        if not valid.isin([0, 1]).all():
            raise ValueError("Invalid climate_available flag")
        raw.loc[valid == 0, [c for c in WEATHER if c in columns]] = float("nan")
    out = monthly.copy()
    out["date"] = pd.to_datetime(out["date"], errors="raise")
    overlap = set(columns) & set(out.columns)
    if overlap:
        raise ValueError(f"Target table already has climate columns: {sorted(overlap)}")
    out = out.merge(raw[["date", *columns]], on="date", how="left", validate="one_to_one")
    coverage = {c: int(out[c].notna().sum()) for c in columns}
    audit = {
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "columns_retained": columns, "present_months": coverage,
        "archived_anomalies_used": False,
        "predictor_units_and_extraction_verified": False,
        "weather_evaluation_uses_lags_not_contemporaneous_values": True,
        "satellite_columns_retained_for_coverage_only": True,
        "warning": "rainfall_mm aggregation meaning, geographic support and timestamp convention remain unverified",
    }
    return out, audit
