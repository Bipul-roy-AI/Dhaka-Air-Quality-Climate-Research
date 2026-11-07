"""Small, source-consistent rolling monthly hindcasts.

These are exploratory product-prediction diagnostics, not operational forecasts
or validation against reference monitors. Source units and publication latency
remain unresolved. No archived result is read or overwritten by this module.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


LATER_REGIME = "later_unverified"
WEATHER_COLUMNS = ("temperature", "dewpoint", "wind_speed", "rainfall_mm", "pressure")
BASE_MODELS = (
    "persistence",
    "seasonal_naive",
    "calendar_climatology",
    "ridge_lags_calendar",
)


def _boolean(series: pd.Series, name: str) -> pd.Series:
    """Handle booleans round-tripped through CSV without bool('False') errors."""
    mapping = {True: True, False: False, 1: True, 0: False, "True": True,
               "False": False, "true": True, "false": False, "1": True, "0": False}
    result = series.map(mapping)
    if result.isna().any():
        raise ValueError(f"{name} must contain explicit boolean values")
    return result.astype(bool)


def _prepare(monthly: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series, list[str]]:
    required = {"date", "pm25_mean", "complete_month", "primary_eligible", "source_regime"}
    missing = required - set(monthly)
    if missing:
        raise ValueError(f"Missing monthly columns: {', '.join(sorted(missing))}")
    if monthly.empty:
        raise ValueError("Monthly input is empty")
    frame = monthly.copy()
    dates = pd.to_datetime(frame["date"], errors="raise")
    if dates.isna().any():
        raise ValueError("Monthly dates must not be missing")
    if dates.dt.tz is not None:
        raise ValueError("Monthly labels must be timezone-naive calendar months")
    frame.index = dates.dt.to_period("M").dt.to_timestamp()
    if frame.index.duplicated().any():
        raise ValueError("Monthly input contains duplicate calendar months")
    frame = frame.sort_index()
    target = pd.to_numeric(frame["pm25_mean"], errors="raise")
    eligible = (
        _boolean(frame["complete_month"], "complete_month")
        & _boolean(frame["primary_eligible"], "primary_eligible")
        & frame["source_regime"].eq(LATER_REGIME)
        & target.notna()
        & np.isfinite(target)
        & target.ge(0)
    )
    for flag in ("ground_pollution_imputed", "target_imputed_by_pipeline"):
        if flag in frame:
            eligible &= ~_boolean(frame[flag], flag)
    frame["pm25_mean"] = target.where(eligible)
    available_weather = []
    for column in WEATHER_COLUMNS:
        if column in frame:
            values = pd.to_numeric(frame[column], errors="raise")
            values = values.where(np.isfinite(values)).where(eligible)
            frame[column] = values
            # Column inclusion is a declared schema choice, not a full-record
            # correlation, VIF or missingness-based feature selection.
            available_weather.append(column)
    full_index = pd.date_range(frame.index.min(), frame.index.max(), freq="MS")
    return frame.reindex(full_index), eligible.reindex(full_index, fill_value=False), available_weather


def _features(frame: pd.DataFrame, weather: list[str]) -> tuple[pd.DataFrame, list[str], list[str]]:
    features = pd.DataFrame(index=frame.index)
    target_columns = []
    for lag in (1, 3, 12):
        name = f"pm25_lag_{lag}"
        features[name] = frame["pm25_mean"].shift(lag)
        target_columns.append(name)
    features["month_sin"] = np.sin(2 * np.pi * features.index.month / 12)
    features["month_cos"] = np.cos(2 * np.pi * features.index.month / 12)
    target_columns += ["month_sin", "month_cos"]
    weather_columns = []
    for column in weather:
        name = f"{column}_lag_1"
        features[name] = frame[column].shift(1)
        weather_columns.append(name)
    return features, target_columns, weather_columns


def _metric_rows(predictions: pd.DataFrame, models: list[str]) -> pd.DataFrame:
    columns = ["model", "sample_set", "n", "RMSE", "MAE", "bias", "R2", "start", "end"]
    if predictions.empty:
        return pd.DataFrame(columns=columns)
    wide = predictions.pivot(index="date", columns="model", values="predicted_pm25")
    common_dates = wide.index[wide.reindex(columns=models).notna().all(axis=1)]
    rows = []
    for model in models:
        model_rows = predictions.loc[predictions.model.eq(model)]
        for sample_set in ("available_cases", "common_cases"):
            scored = model_rows.loc[model_rows.predicted_pm25.notna()]
            if sample_set == "common_cases":
                scored = scored.loc[scored.date.isin(common_dates)]
            errors = scored.predicted_pm25 - scored.observed_pm25
            n = len(scored)
            variance_sum = ((scored.observed_pm25 - scored.observed_pm25.mean()) ** 2).sum()
            rows.append({
                "model": model, "sample_set": sample_set, "n": n,
                "RMSE": float(np.sqrt(np.mean(errors ** 2))) if n else None,
                "MAE": float(np.mean(np.abs(errors))) if n else None,
                "bias": float(np.mean(errors)) if n else None,
                "R2": float(1 - (errors ** 2).sum() / variance_sum) if n > 1 and variance_sum > 0 else None,
                "start": scored.date.min() if n else None,
                "end": scored.date.max() if n else None,
            })
    return pd.DataFrame(rows, columns=columns)


def evaluate_monthly(
    monthly: pd.DataFrame, min_train_months: int = 24
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Return predictions, metrics and audit for expanding one-step hindcasts.

    Only complete, explicitly eligible later-regime target months are used.
    Missing/excluded months remain calendar gaps. No target is imputed. Lagged
    feature gaps are median-imputed *inside each training fold*. Fixed-alpha
    Ridge is a prespecified diagnostic; there is no model selection or tuning.
    Weather predictors are shifted one calendar month. Their actual release
    latency is unknown, so results must not be called operational forecasts.
    """
    if isinstance(min_train_months, bool) or not isinstance(min_train_months, int) or min_train_months < 2:
        raise ValueError("min_train_months must be an integer of at least 2")
    frame, eligible, weather = _prepare(monthly)
    features, core_columns, weather_columns = _features(frame, weather)
    models = list(BASE_MODELS)
    if weather_columns:
        models.append("ridge_lags_calendar_weather")
    rows = []
    for date in frame.index[eligible]:
        train_dates = frame.index[(frame.index < date) & eligible]
        if len(train_dates) < min_train_months:
            continue
        train_target = frame.loc[train_dates, "pm25_mean"]
        same_month = train_target.loc[train_target.index.month == date.month]
        values = {
            "persistence": features.at[date, "pm25_lag_1"],
            "seasonal_naive": features.at[date, "pm25_lag_12"],
            "calendar_climatology": same_month.mean() if len(same_month) else np.nan,
        }
        specifications = {"ridge_lags_calendar": core_columns}
        if weather_columns:
            specifications["ridge_lags_calendar_weather"] = core_columns + weather_columns
        for model, columns in specifications.items():
            pipeline = make_pipeline(
                SimpleImputer(strategy="median", keep_empty_features=True),
                StandardScaler(), Ridge(alpha=1.0),
            )
            pipeline.fit(features.loc[train_dates, columns], train_target)
            values[model] = float(pipeline.predict(features.loc[[date], columns])[0])
        for model in models:
            value = values[model]
            rows.append({
                "date": date.strftime("%Y-%m-%d"),
                "forecast_date": date.strftime("%Y-%m-%d"),
                "train_start": train_dates.min().strftime("%Y-%m-%d"),
                "train_end": train_dates.max().strftime("%Y-%m-%d"),
                "n_train": len(train_dates), "model": model,
                "observed_pm25": float(frame.at[date, "pm25_mean"]),
                "predicted_pm25": float(value) if np.isfinite(value) else np.nan,
                "source_regime": LATER_REGIME,
                "target_type": "archive_product_unverified",
                "units": "unverified_original_field",
                "evaluation_type": "exploratory_rolling_one_step_hindcast",
                "publication_latency_verified": False,
            })
    prediction_columns = ["date", "forecast_date", "train_start", "train_end", "n_train", "model",
                          "observed_pm25", "predicted_pm25", "source_regime", "target_type", "units",
                          "evaluation_type", "publication_latency_verified"]
    predictions = pd.DataFrame(rows, columns=prediction_columns)
    metrics = _metric_rows(predictions, models)
    audit = {
        "evaluation_type": "exploratory_rolling_one_step_hindcast",
        "source_regime": LATER_REGIME, "source_validated": False,
        "publication_latency_verified": False, "operational_forecast_validated": False,
        "target_units": "unverified_original_field",
        "input_months": int(len(monthly)), "calendar_months": int(len(frame)),
        "eligible_months": int(eligible.sum()), "min_train_months": min_train_months,
        "scored_forecast_months": int(predictions.date.nunique()),
        "models": models, "ridge_alpha": 1.0,
        "features": {"ridge_lags_calendar": core_columns},
        "feature_imputation": "per-fold training median; target is never imputed",
        "preprocessing_fit_scope": "eligible months strictly before each target month",
        "global_anomaly_columns_used": False,
        "metric_case_sets": {
            "available_cases": "model-specific nonmissing predictions; do not compare unmatched case counts",
            "common_cases": "intersection of predicted dates across all declared models",
        },
        "limitations": [
            "Unknown source, units and publication latency prevent operational or ground-truth claims.",
            "Later regime is a detected archive-construction regime, not an authenticated product identity.",
            "Already inspected historical dates are retrospective; no newly untouched test period is claimed.",
            "No tuning, causal attribution, reference-monitor validation or uncertainty certification is performed.",
        ],
    }
    if weather_columns:
        audit["features"]["ridge_lags_calendar_weather"] = core_columns + weather_columns
    return predictions, metrics, audit
