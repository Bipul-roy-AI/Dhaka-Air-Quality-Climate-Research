"""Run conservative archive reconstruction and a small retrospective pilot."""
from __future__ import annotations
import argparse
import hashlib
import importlib.metadata
import json
import platform
import math
import numbers
import tempfile
from pathlib import Path
import pandas as pd
from . import __version__
from .data import build_monthly
from .climate import join_climate
from .evaluation import evaluate_monthly
from .provenance import attribution


def _json_safe(value):
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, numbers.Real) and not math.isfinite(value):
        return None
    return value


def _dump(path, value):
    path.write_text(json.dumps(_json_safe(value),indent=2,ensure_ascii=False,allow_nan=False,default=str)+"\n")


def _summary(monthly):
    return monthly.groupby("source_regime",dropna=False).agg(
        months=("date","size"), mean_of_monthly_pm25=("pm25_mean","mean"),
        complete_months=("complete_month","sum"), unique_hours=("unique_hours","sum"),
        eligible_exploratory_months=("primary_eligible","sum"),
    ).reset_index()


def _reconcile(monthly, archived):
    old=pd.read_csv(archived,usecols=["date","pm25_mean","observations"])
    old["date"]=pd.to_datetime(old.date).dt.to_period("M").dt.to_timestamp()
    if old.date.duplicated().any():raise ValueError("Duplicate archived month")
    old=old.rename(columns={"pm25_mean":"archived_pm25_mean","observations":"archived_observations"})
    new=monthly.copy();new["date"]=pd.to_datetime(new.date)
    merged=new[["date","pm25_mean","unique_hours","complete_month","source_regime"]].merge(old,on="date",how="outer",validate="one_to_one",indicator=True)
    merged["pm25_difference"]=merged.pm25_mean-merged.archived_pm25_mean
    merged["count_overstatement"]=merged.archived_observations-merged.unique_hours
    return merged


def _plot(monthly,path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    d=monthly.copy();d["date"]=pd.to_datetime(d.date)
    fig,ax=plt.subplots(2,1,figsize=(10,6),sharex=True,layout="constrained")
    for regime,part in d.groupby("source_regime",sort=False):
        ax[0].plot(part.date,part.pm25_mean,label=regime,linewidth=1.4)
    ax[0].set_ylabel("Reported PM₂.₅ field\n(units unverified)")
    ax[0].set_title("Archive reconstruction: source regimes and valid temporal coverage")
    ax[0].legend(fontsize=8)
    ax[1].plot(d.date,d.coverage_fraction,color="#245a81")
    ax[1].set_ylabel("Unique valid PM₂.₅ hours /\nexpected calendar hours")
    for a in ax:
        a.axvline(pd.Timestamp("2022-08-04"),color="gray",linestyle="--",linewidth=1)
        a.spines[["top","right"]].set_visible(False)
    fig.savefig(path,dpi=160);plt.close(fig)


DICTIONARY="""# Rebuilt dataset dictionary

One row is one calendar month within the observed timestamp span for exactly the requested city. Empty internal months retain missing targets and zero coverage. Dates are month-start labels in the archive's unresolved naive timestamp convention; they have not been asserted to be UTC or Bangladesh Standard Time.

- `pm25_mean`, `pm25_max`, other pollutant means: aggregated reported fields. Units remain unverified; no arbitrary unit conversion or source-break correction is applied.
- `unique_hours`: distinct available city timestamps, never summed over duplicate locations.
- `valid_pm25_hours`: finite nonnegative PM2.5 observations contributing to the target.
- `expected_hours`: calendar days × 24, with timezone unknown. Duplicate clock hours require resolution before applying this convention to a timezone with DST.
- `coverage_fraction`: valid PM2.5 hours / expected calendar hours.
- `complete_month`: complete temporal and valid-PM2.5 coverage, as implemented in data.py.
- `source_regime`: earlier_unverified, mixed boundary month, or later_unverified. The boundary is a data-construction audit flag, not a physical changepoint.
- `primary_eligible`: computational exploratory cohort flag (complete month wholly within the later source regime); it does not certify source validity.
- `target_imputed_by_pipeline`: always false; this pipeline never imputes targets. `upstream_imputation_status` remains unknown because the deposited archive does not supply generation/imputation provenance.
- QA counts: retain physical-range/order flags for inspection. Flagging is not evidence of fabrication. Source units are not repaired using these flags.
- Raw climate columns: retained only from the supplied monthly covariate export; -999 and unavailable retrievals become missing, not zero.
- Archived anomaly columns, archived targets/counts and archived lags are never used as model inputs.
- Prediction lags and preprocessing: generated inside evaluation.py with calendar-aware lags and training-fold-only transforms; current-month covariates are not prediction inputs.

No absent final month is fabricated; no monthly target is forward-filled. Annual summaries are descriptive means of monthly reported values, not validated ambient annual exposure. Metrics inherit unresolved target units.
"""


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input",type=Path,required=True,help="Original AQI CSV or ZIP; never modified")
    p.add_argument("--output",type=Path,default=Path("artifacts/rebuilt"))
    p.add_argument("--climate",type=Path,help="Optional monthly raw climate/satellite export")
    p.add_argument("--archived-monthly",type=Path,help="Optional existing monthly table for reconciliation only")
    p.add_argument("--city",default="Dhaka",choices=["Dhaka"],help="This audited source boundary applies only to Dhaka")
    p.add_argument("--min-train-months",type=int,default=24)
    p.add_argument("--no-figure",action="store_true")
    args=p.parse_args(argv)
    if args.output.exists() and any(args.output.iterdir()):
        p.error("Output directory is not empty; choose a new run directory to preserve previous results")
    # Compute first; a failed validation should not leave a superficially complete run.
    monthly,data_audit=build_monthly(args.input,city=args.city)
    source_attribution=attribution(data_audit["csv_sha256"])
    data_audit["deposited_source_attribution"]=source_attribution
    climate_audit={"used":False}
    if args.climate:monthly,climate_audit=join_climate(monthly,args.climate)
    predictions,metrics,eval_audit=evaluate_monthly(monthly,min_train_months=args.min_train_months)
    reconciliation=_reconcile(monthly,args.archived_monthly) if args.archived_monthly else None
    args.output.parent.mkdir(parents=True,exist_ok=True)
    # Publish a complete run atomically; exceptions remove the staging directory.
    with tempfile.TemporaryDirectory(prefix=f".{args.output.name}-",dir=args.output.parent) as staging:
        run_dir=Path(staging)
        monthly.to_csv(run_dir/"monthly_rebuilt.csv",index=False)
        _summary(monthly).to_csv(run_dir/"source_regime_summary.csv",index=False)
        predictions.to_csv(run_dir/"predictions.csv",index=False)
        metrics.to_csv(run_dir/"metrics.csv",index=False)
        if reconciliation is not None:reconciliation.to_csv(run_dir/"archive_reconciliation.csv",index=False)
        _dump(run_dir/"source_audit.json",data_audit)
        _dump(run_dir/"climate_audit.json",climate_audit)
        _dump(run_dir/"evaluation_audit.json",eval_audit)
        (run_dir/"DATA_DICTIONARY.md").write_text(DICTIONARY)
        if not args.no_figure:_plot(monthly,run_dir/"coverage_and_regime.png")
        versions={name:importlib.metadata.version(name) for name in ["numpy","pandas","scikit-learn","matplotlib"]}
        manifest={"pipeline_version":__version__,"python":platform.python_version(),"packages":versions,"input_filename":args.input.name,"source_attribution":source_attribution,"input_sha256":hashlib.sha256(args.input.read_bytes()).hexdigest(),"city":args.city,"min_train_months":args.min_train_months,"climate_filename":args.climate.name if args.climate else None,"scientific_measurement_validated":False,"evaluation":"Retrospective exploratory rolling one-step archive hindcast; operational availability unverified","code_sha256":{f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in Path(__file__).parent.glob('*.py')}}
        _dump(run_dir/"run_manifest.json",manifest)
        complete=int(monthly.complete_month.sum());eligible=int(monthly.primary_eligible.sum())
        report=f"""# Rebuilt run report

    **Status: computational reconstruction and retrospective pilot; independent observational validation remains unresolved.**

    - Input: `{args.input.name}`; selected city: {args.city}.
    - Rebuilt observed months: {len(monthly)}; complete months: {complete}; eligible later-regime exploratory months: {eligible}.
    - Missing months are not fabricated. Earlier/mixed/partial months remain visible for audit and excluded from the primary pilot.
    - Temporal semantics: naive archive timestamps, timezone unknown. Rolling prediction is retrospective and assumes preceding inputs have become available; operational release timing has not been established.
    - Baseline and fixed-regularization models use backward calendar lags and fold-local preprocessing. Archived full-period anomalies are excluded.
    - Results do not establish a measured 2000–2025 pollution trend, causation, health effects, or universal model superiority.
    - Read `evaluation_audit.json` for fold/sample limitations and `metrics.csv` for common-case comparisons. A small short-period pilot is not a final untouched-test experiment.

    Source attribution: {source_attribution}. See research_docs/source_metadata for public provenance metadata for the inspected reference input; station/product identities, segment units and pre-2022 acquisition/generation remain unverified.

    See `archive_reconciliation.csv` when supplied for changes versus legacy tables. Original repository CSVs and original input files have not been overwritten.
    """
        (run_dir/"RUN_REPORT.md").write_text(report.replace("\n    ","\n"))
        if args.output.exists():
            # Recheck before publication; never replace another run's files.
            if not args.output.is_dir() or any(args.output.iterdir()):
                raise FileExistsError("Output changed during run; refusing overwrite")
            args.output.rmdir()
        run_dir.rename(args.output)
    print(f"Wrote {args.output}; {len(monthly)} observed months, {eligible} later-regime complete months. See RUN_REPORT.md.")
    return 0

if __name__=="__main__":raise SystemExit(main())
