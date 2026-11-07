#!/usr/bin/env python3
"""Descriptive analysis of the EPA-hosted embassy daily concentration series.

No forecasts, causal effects, health outcomes, or regulatory compliance are
estimated. Output creation is exclusive: existing directories are never replaced.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import theilslopes

THRESHOLD = 15.0  # WHO 2021 daily guideline used retrospectively, not AQI.
FOUR_ORDER = ["Winter_DJF", "Pre_monsoon_MAM", "Monsoon_JJAS", "Post_monsoon_ON"]
SIX_ORDER = ["Winter", "Spring", "Summer", "Monsoon", "Autumn", "Late_autumn"]


def four_season(date: pd.Timestamp) -> str:
    if date.month in (12, 1, 2):
        return "Winter_DJF"
    if date.month in (3, 4, 5):
        return "Pre_monsoon_MAM"
    if date.month in (6, 7, 8, 9):
        return "Monsoon_JJAS"
    return "Post_monsoon_ON"


def six_season(date: pd.Timestamp) -> str:
    """Exact date boundaries from HyAQMet paper Table 3, not equal-length bins."""
    md = date.month * 100 + date.day
    if md >= 1216 or md <= 215:
        return "Winter"
    if md <= 415:
        return "Spring"
    if md <= 615:
        return "Summer"
    if md <= 1015:
        return "Monsoon"
    if md <= 1115:
        return "Autumn"
    return "Late_autumn"


def load_daily(path: Path) -> pd.Series:
    frame = pd.read_csv(path)
    if not {"date", "pm25_ugm3"}.issubset(frame):
        raise ValueError("Input needs date and pm25_ugm3 columns")
    dates = pd.to_datetime(frame.date, errors="raise")
    if dates.isna().any() or dates.duplicated().any() or not dates.eq(dates.dt.normalize()).all():
        raise ValueError("Dates must be unique nonmissing midnight calendar dates")
    if dates.dt.tz is not None:
        raise ValueError("Explicit averaging-timezone harmonization is required")
    values = pd.to_numeric(frame.pm25_ugm3, errors="raise")
    if (values.dropna().lt(0) | ~np.isfinite(values.dropna())).any():
        raise ValueError("Nonmissing concentrations must be finite and nonnegative")
    series = pd.Series(values.to_numpy(), index=pd.DatetimeIndex(dates), name="pm25_ugm3").sort_index()
    if series.empty:
        raise ValueError("No daily records")
    # Internal missing dates stay NaN and interrupt all episode calculations.
    return series.reindex(pd.date_range(series.index.min(), series.index.max(), freq="D", name="date"))


def summarize(series: pd.Series) -> dict:
    observed = series.dropna()
    n = len(observed)
    return {"calendar_days": len(series), "observed_days": n,
            "missing_days": int(series.isna().sum()),
            "coverage_fraction": n / len(series) if len(series) else np.nan,
            "mean_ugm3": float(observed.mean()) if n else np.nan,
            "median_ugm3": float(observed.median()) if n else np.nan,
            "std_ugm3": float(observed.std()) if n > 1 else np.nan,
            "p05_ugm3": float(observed.quantile(.05)) if n else np.nan,
            "p25_ugm3": float(observed.quantile(.25)) if n else np.nan,
            "p75_ugm3": float(observed.quantile(.75)) if n else np.nan,
            "p95_ugm3": float(observed.quantile(.95)) if n else np.nan,
            "max_ugm3": float(observed.max()) if n else np.nan,
            "days_gt_15": int(observed.gt(THRESHOLD).sum()),
            "fraction_observed_gt_15": float(observed.gt(THRESHOLD).mean()) if n else np.nan}


def grouped_summary(series: pd.Series, keys, label: str) -> pd.DataFrame:
    return pd.DataFrame([{label: key, **summarize(group)} for key, group in series.groupby(keys)])


def find_episodes(series: pd.Series, threshold: float) -> pd.DataFrame:
    """Consecutive calendar-day exceedances; unknown days never bridge a run."""
    if series.index.duplicated().any():
        raise ValueError("Duplicate dates")
    series = series.sort_index().reindex(pd.date_range(series.index.min(), series.index.max(), freq="D"))
    rows, current = [], []
    def finish():
        if not current:
            return
        values = series.loc[current]
        rows.append({"start_date": current[0].strftime("%Y-%m-%d"),
                     "end_date": current[-1].strftime("%Y-%m-%d"),
                     "duration_days": len(current), "mean_ugm3": float(values.mean()),
                     "max_ugm3": float(values.max()),
                     "sum_excess_ug_day_m3": float((values-threshold).sum()),
                     "threshold_ugm3": threshold})
    for date, value in series.items():
        if pd.notna(value) and value > threshold:
            current.append(date)
        else:
            finish()
            current = []
    finish()
    return pd.DataFrame(rows, columns=["start_date", "end_date", "duration_days", "mean_ugm3", "max_ugm3", "sum_excess_ug_day_m3", "threshold_ugm3"])


def monthly_targets(series: pd.Series, minimum_coverage: float = .75) -> pd.DataFrame:
    if not 0 < minimum_coverage <= 1:
        raise ValueError("Invalid minimum coverage")
    result = pd.DataFrame({"mean_ugm3": series.resample("MS").mean(), "observed_days": series.resample("MS").count()})
    # Full-calendar denominator even if the source starts/ends inside a month.
    result["calendar_days"] = result.index.days_in_month
    result["coverage_fraction"] = result.observed_days / result.calendar_days
    result["eligible"] = result.coverage_fraction.ge(minimum_coverage)
    eligible = result.mean_ugm3.where(result.eligible)
    seasonal_medians = eligible.groupby(eligible.index.month).median()
    result["calendar_month_median_ugm3"] = result.index.month.map(seasonal_medians)
    result["season_adjusted_ugm3"] = (result.mean_ugm3-result.calendar_month_median_ugm3).where(result.eligible)
    return result


def trend_with_block_bootstrap(monthly: pd.DataFrame, block_months: int, replicates: int = 1000, seed: int = 20261107) -> dict:
    """Conditional residual moving-block intervals; not an iid trend p-value.

    Candidate blocks are contiguous calendar windows with all monthly targets
    eligible. No block crosses an excluded/missing month. The estimated seasonal
    profile is held fixed. Stationary residuals after adjustment are assumed.
    """
    if block_months < 1 or replicates < 1:
        raise ValueError("Positive block size and replicate count required")
    yall = monthly.season_adjusted_ugm3.to_numpy(dtype=float)
    valid = np.isfinite(yall)
    if valid.sum() < max(block_months + 1, 8):
        return {"block_months": block_months, "status": "insufficient_months"}
    xall = (np.arange(len(monthly), dtype=float)) / 12
    x, y = xall[valid], yall[valid]
    slope, intercept, _, _ = theilslopes(y, x)
    residual = np.full(len(yall), np.nan)
    residual[valid] = y-(intercept+slope*x)
    residual[valid] -= np.median(residual[valid])
    blocks = np.array([residual[i:i+block_months] for i in range(len(residual)-block_months+1)
                       if np.isfinite(residual[i:i+block_months]).all()])
    if not len(blocks):
        return {"block_months": block_months, "status": "no_contiguous_eligible_blocks"}
    rng = np.random.default_rng(seed)
    slopes = np.empty(replicates)
    draws = int(np.ceil(len(y) / block_months))
    for n in range(replicates):
        noise = blocks[rng.integers(0, len(blocks), size=draws)].reshape(-1)[:len(y)]
        slopes[n] = theilslopes(intercept+slope*x+noise, x)[0]
    low, high = np.quantile(slopes, [.025, .975])
    return {"block_months": block_months, "status": "exploratory_conditional_interval",
            "eligible_months": int(valid.sum()), "candidate_contiguous_blocks": len(blocks),
            "slope_ugm3_per_year": float(slope), "ci95_low": float(low), "ci95_high": float(high),
            "bootstrap_replicates": replicates, "seed": seed,
            "interval_interpretation": "Conditional on estimated calendar-month profile and stationary block-residual approximation; six-year interval, not climate attribution or a significance test."}


def create_figures(series, monthly, annual, months, seasons, trend, output):
    os.environ.setdefault("MPLCONFIGDIR", "/tmp/dhaka-observed-mpl")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
    fig, ax = plt.subplots(2, 1, figsize=(11, 6), sharex=True, layout="constrained", gridspec_kw={"height_ratios": [3, 1]})
    ax[0].plot(series.index, series, color="#296688", lw=.65)
    ax[0].axhline(THRESHOLD, ls="--", color="#aa6333", label="15 µg/m³ retrospective daily benchmark")
    ax[0].set_ylabel("Daily PM₂.₅ (µg/m³)"); ax[0].legend(loc="upper right")
    ax[0].set_title("EPA-hosted Dhaka embassy series: reported daily concentrations, 2016–2021")
    coverage=monthly.coverage_fraction
    ax[1].bar(coverage.index, coverage, width=20, color="#487f91")
    ax[1].axhline(.75, color="#aa6333", ls="--")
    ax[1].set_ylabel("Monthly\ncoverage");ax[1].set_ylim(0, 1.06)
    fig.savefig(output/"observed_daily_and_coverage.png", dpi=180);plt.close(fig)
    fig, ax=plt.subplots(1, 2, figsize=(11, 4.4), layout="constrained")
    ax[0].plot(months.month, months.mean_ugm3, marker="o", label="Available-day mean")
    ax[0].plot(months.month, months.year_balanced_mean_ugm3, marker="s", ls="--", label="Equal-year eligible monthly means")
    ax[0].set_xticks(range(1, 13)); ax[0].set_xlabel("Calendar month");ax[0].set_ylabel("PM₂.₅ (µg/m³)");ax[0].legend(fontsize=8)
    ordered=seasons.set_index("season").loc[FOUR_ORDER]
    ax[1].bar(range(4), ordered.mean_ugm3, color="#487f91")
    ax[1].set_xticks(range(4), ["DJF", "MAM", "JJAS", "ON"]);ax[1].set_ylabel("Available-day mean (µg/m³)")
    ax[1].set_title("Unequal-length seasonal windows")
    for i, row in enumerate(ordered.itertuples()):ax[1].text(i, row.mean_ugm3+2, f"n={row.observed_days}", ha="center", fontsize=8)
    fig.savefig(output/"observed_monthly_and_seasonal.png", dpi=180);plt.close(fig)
    fig, ax=plt.subplots(1, 2, figsize=(11, 4.4), layout="constrained")
    ax[0].plot(annual.year, annual.mean_ugm3, marker="o", color="#296688")
    ax[0].set_ylabel("Available-day annual mean (µg/m³)");ax[0].set_xlabel("Year")
    ax[0].set_title("Annual descriptive means; no climate attribution")
    ax[1].plot(monthly.index, monthly.season_adjusted_ugm3, marker=".", lw=.7, label="Eligible monthly residual")
    valid=monthly.season_adjusted_ugm3.notna();x=np.arange(len(monthly))/12
    intercept=np.median(monthly.loc[valid, "season_adjusted_ugm3"]-trend["slope_ugm3_per_year"]*x[valid])
    ax[1].plot(monthly.index, intercept+trend["slope_ugm3_per_year"]*x, color="#aa6333", label="Theil–Sen descriptive trend")
    ax[1].axhline(0, lw=.5, color="#888888");ax[1].set_ylabel("Season-adjusted PM₂.₅ (µg/m³)");ax[1].legend(fontsize=8)
    fig.savefig(output/"observed_annual_and_adjusted_trend.png", dpi=180);plt.close(fig)


def run(input_path: Path, output: Path, weather_path: Path | None = None, replicates: int = 1000) -> dict:
    series = load_daily(input_path)
    overall = summarize(series)
    annual = grouped_summary(series, series.index.year, "year")
    months = grouped_summary(series, series.index.month, "month")
    seasons = grouped_summary(series, series.index.map(four_season), "season")
    six = grouped_summary(series, series.index.map(six_season), "season")
    monthly = monthly_targets(series)
    means = monthly.loc[monthly.eligible].groupby(monthly.loc[monthly.eligible].index.month).mean_ugm3.mean()
    months["year_balanced_mean_ugm3"] = months.month.map(means)
    episodes = find_episodes(series, float(series.quantile(.95)))
    trends = [trend_with_block_bootstrap(monthly, b, replicates) for b in [12, 6]]
    if trends[0]["status"] != "exploratory_conditional_interval":
        raise ValueError("Insufficient calendar-contiguous months for the requested trend analysis")
    metadata = {"input_sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
                "input_name": input_path.name, "first_date": str(series.index.min().date()), "last_date": str(series.index.max().date()),
                "overall": overall, "minimum_monthly_coverage": .75, "eligible_months": int(monthly.eligible.sum()),
                "excluded_months": monthly.index[~monthly.eligible].strftime("%Y-%m").tolist(),
                "daily_threshold_ugm3": THRESHOLD, "threshold_interpretation": "WHO2021 daily benchmark applied retrospectively, not AQI, regulatory compliance, health outcomes or an annual standard.",
                "episode_threshold_pooled_p95_ugm3": float(series.quantile(.95)), "episodes": len(episodes),
                "maximum_episode_days": int(episodes.duration_days.max()) if len(episodes) else 0,
                "trends": trends, "daily_interval_timezone_harmonized": False,
                "season_windows": "Four:DJF/MAM/JJAS/ON. Paper-definition six-season sensitivity (not a claim about released labels):Dec16-Feb15/Feb16-Apr15/Apr16-Jun15/Jun16-Oct15/Oct16-Nov15/Nov16-Dec15. Unequal durations; counts disclosed.",
                "causal_or_health_outcome_claims": False}
    weather = None
    if weather_path is not None:
        w = pd.read_csv(weather_path)
        dates = pd.to_datetime(w.date_utc, errors="raise")
        if dates.isna().any() or dates.duplicated().any():raise ValueError("Weather dates are missing or duplicated")
        cols = [x for x in w if x != "date_utc"]
        weather = pd.DataFrame([{"variable": c, "days": len(w), "finite_days": int(np.isfinite(pd.to_numeric(w[c], errors="raise")).sum()),
                                 "source": "NASA POWER/MERRA-2 meteorology", "daily_interval_aligned_to_embassy": False} for c in cols])
        metadata["weather"] = {"name": weather_path.name, "sha256": hashlib.sha256(weather_path.read_bytes()).hexdigest(),
                               "calendar_date_overlap_days": int(pd.Index(dates).intersection(series.index).size),
                               "interpretation": "Calendar labels overlap; weather days areUTC while exact embassy averaging interval is unverified. No paired weather effects estimated here."}
    output.mkdir(parents=True, exist_ok=False)
    series.to_csv(output/"observed_daily_calendar.csv", index_label="date")
    annual.to_csv(output/"annual_statistics.csv", index=False)
    months.to_csv(output/"calendar_month_statistics.csv", index=False)
    monthly.to_csv(output/"monthly_coverage_and_trend_inputs.csv", index_label="date")
    seasons.to_csv(output/"four_season_statistics.csv", index=False)
    six.to_csv(output/"six_season_sensitivity.csv", index=False)
    episodes.to_csv(output/"pooled_p95_episodes.csv", index=False)
    pd.DataFrame(trends).to_csv(output/"season_adjusted_trend_intervals.csv", index=False)
    if weather is not None:weather.to_csv(output/"weather_coverage.csv", index=False)
    (output/"analysis.json").write_text(json.dumps(metadata, indent=2, allow_nan=False)+"\n")
    create_figures(series, monthly, annual, months, seasons, trends[0], output)
    observed_pct=100*overall["fraction_observed_gt_15"]
    t12,t6=trends
    text=f'''# Observed-reference descriptive analysis

Source: supplied EPA-hosted embassy daily calendar, {metadata['first_date']}–{metadata['last_date']}. The source date mapping uses its caption and1-based day index; original monitor QA and exact daily averaging timezone remain unverified. This is not a reanalysis target. Missing values remain missing; no daily target interpolation or filling was performed.

## Actual results

- Calendar days:{overall['calendar_days']}; observed:{overall['observed_days']}; missing:{overall['missing_days']}; coverage:{overall['coverage_fraction']:.2%}.
- Available-day PM₂.₅ mean:{overall['mean_ugm3']:.2f}µg/m³; median:{overall['median_ugm3']:.2f}; maximum:{overall['max_ugm3']:.2f}.
- Days strictly above15µg/m³:{overall['days_gt_15']}/{overall['observed_days']} ({observed_pct:.2f}% of observed days). The15 benchmark is the WHO2021 daily value applied retrospectively, not AQI, legal compliance or a health-outcome estimate. Missing-day exceedances are unknown.
- Pooled available-day95th percentile:{metadata['episode_threshold_pooled_p95_ugm3']:.2f}µg/m³. Strictly-above-threshold episodes:{metadata['episodes']}; longest:{metadata['maximum_episode_days']}days. Gaps/missing days interrupt runs. This threshold is descriptive and estimated from the whole period, not a prospectively selected alarm threshold.
- Eligible monthly means:{metadata['eligible_months']}/{len(monthly)} using≥75%of full calendar days. Excluded:{', '.join(metadata['excluded_months'])}.
- Season-adjusted Theil–Sen slope:{t12['slope_ugm3_per_year']:.3f}µg/m³/year.12-month residual-block bootstrap95%interval:[{t12['ci95_low']:.3f},{t12['ci95_high']:.3f}];6-month sensitivity:[{t6['ci95_low']:.3f},{t6['ci95_high']:.3f}]. Each uses{replicates}replicates with a fixed reproducibility seed. Do not interpret these six-year results as climate-change attribution or a definitive trend-significance claim.

## Methods and interpretation

Annual/month/season tables use available daily values and report observed/missing denominators. The month plot additionally shows equal-year means of eligible monthly means to expose coverage/weighting sensitivity. Four seasons areDJF/MAM/JJAS/ON; these windows have3/3/4/2months. The exact paperTable3six-season boundaries are a paper-definition sensitivity analysis, also unequal in duration; this does not assert agreement with the final release's season labels. Calendar-month summaries are primary. Seasons are pooled; no independent equal-length seasonal replicates are implied.

Trend inputs are monthly daily-mean concentrations with≥75%coverage. Subtract the median eligible monthly mean for each calendar month. FitTheil–Sen slope to the residual versus actual elapsed calendar months/12. For uncertainty, center residuals around the fitted trend, sample moving blocks of12months (and6for sensitivity) only from completely eligible contiguous calendar windows, concatenate draws, and place residuals on the original eligible observation times. Refit slope for1000replicates unless CLI override is used. This preserves within-block dependence without bridging excluded months. Intervals assume approximately stationary residuals and hold the estimated seasonal profile fixed; they do not propagate all seasonal-estimation, missingness, source QA, endpoint or monitor-interval uncertainty. Coverage≥75%does not guarantee unbiased missingness. No iid Mann–Kendall p-value or independent-row CI is claimed.

NASA POWER/MERRA-2 weather coverage is documented separately. Calendar-date coincidence does not establish daily averaging-interval alignment with embassy observations. No causal weather effects or aligned daily pollutant-weather validation are estimated in this script. Final analysis requires confirming the embassy averaging interval and source QC documentation.

All generated outputs are reproducible from the identified input hashes. Existing output directories are refused. Original inputs and legacy results remain unchanged.
'''
    (output/"methods_findings.md").write_text(text)
    return metadata


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--weather", type=Path)
    parser.add_argument("--bootstrap-replicates", type=int, default=1000)
    args=parser.parse_args()
    if args.output.exists():parser.error("Output already exists; choose a new directory")
    if args.bootstrap_replicates<1:parser.error("Bootstrap replicates must be positive")
    if args.weather is not None and not args.weather.is_file():parser.error("Explicit weather file does not exist")
    weather=args.weather or args.input.parent/"nasa_power_embassy_daily_2016_2021.csv"
    result=run(args.input,args.output,weather if weather.exists() else None,args.bootstrap_replicates)
    print(json.dumps({"output":str(args.output),"overall":result["overall"],"trends":result["trends"]}, indent=2))


if __name__=="__main__":main()
