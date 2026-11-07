#!/usr/bin/env python3
"""Inspect how an hourly embassy mirror aligns with published station-day means.

The mirror is the same monitoring network, not an independent second station.
Daily UTC/hour-ending rules and complete original QA remain unresolved. All four
conventions are retained as sensitivity checks without selecting the best match.
"""
from __future__ import annotations
import argparse
from hashlib import sha256
import json
from pathlib import Path
from zipfile import ZipFile
import numpy as np
import pandas as pd

MEMBER='PM2.5_data/dhaka.csv'
CONVENTIONS=(('local_labels',0),('local_hour_ending',-1),('UTC_labels',-6),('UTC_hour_ending',-7))


def load_epa_daily(path: str | Path) -> pd.Series:
    """Validate supplied calendar labels; do not infer their averaging timezone."""
    frame=pd.read_csv(path)
    if not {'date','pm25_ugm3'}.issubset(frame):raise ValueError('EPA CSV requires date and pm25_ugm3')
    dates=pd.to_datetime(frame.date,errors='raise')
    if dates.dt.tz is not None:raise ValueError('Daily averaging timezone requires explicit harmonization')
    if dates.isna().any() or dates.duplicated().any() or not dates.eq(dates.dt.normalize()).all():
        raise ValueError('Daily dates must be unique nonmissing midnight calendar labels')
    values=pd.to_numeric(frame.pm25_ugm3,errors='raise')
    known=values.dropna()
    if known.lt(0).any() or not np.isfinite(known).all():raise ValueError('Daily concentrations must be finite nonnegative values or missing')
    series=pd.Series(values.to_numpy(),index=pd.DatetimeIndex(dates),name='epa_pm25_ugm3').sort_index()
    if series.empty:raise ValueError('Daily input is empty')
    return series.reindex(pd.date_range(series.index.min(),series.index.max(),freq='D',name='date'))


def mirror_daily(zip_path: str | Path,min_hours: int=18):
    """Return four daily-label hypotheses and transparent valid-hour QC counts.

    Equal timestamp/concentration pairs are measurement duplicates. After their
    removal, *all* records at any remaining conflicting timestamp are excluded;
    no arbitrary first record or average is selected. The ZIP is read directly.
    """
    if isinstance(min_hours,bool) or not isinstance(min_hours,int) or not 1<=min_hours<=24:
        raise ValueError('min_hours must be an integer from1 to24')
    with ZipFile(zip_path) as archive:
        if archive.namelist().count(MEMBER)!=1:raise ValueError('ZIP requires one unambiguous PM2.5_data/dhaka.csv member')
        with archive.open(MEMBER) as stream:raw=pd.read_csv(stream)
    required={'Date (LT)','Raw Conc.','QC Name','Conc. Unit','Duration'}
    if not required.issubset(raw):raise ValueError(f'Missing mirror columns: {sorted(required-set(raw))}')
    time=pd.to_datetime(raw['Date (LT)'],format='%Y-%m-%d %I:%M %p',errors='coerce')
    value=pd.to_numeric(raw['Raw Conc.'],errors='coerce')
    quality=raw['QC Name'].eq('Valid');unit=raw['Conc. Unit'].eq('UG/M3');duration=raw.Duration.eq('1 Hr')
    finite=value.notna()&np.isfinite(value)&value.ge(0)
    hourly=time.notna()&time.eq(time.dt.floor('h'))
    valid=quality&unit&duration&finite&hourly
    clean=pd.DataFrame({'time':time[valid],'value':value[valid]})
    count_before=len(clean);clean=clean.drop_duplicates(['time','value'])
    removed=count_before-len(clean)
    conflict_rows=clean.time.duplicated(keep=False)
    conflicts=pd.DatetimeIndex(clean.loc[conflict_rows,'time'].unique())
    clean=clean.loc[~conflict_rows].set_index('time').sort_index()
    output={};daily_coverage={}
    for name,shift in CONVENTIONS:
        q=clean.value.copy();q.index=q.index+pd.Timedelta(hours=shift)
        if q.empty:
            output[name]=pd.Series(index=pd.DatetimeIndex([],name='date'),dtype=float,name=name)
            daily_coverage[name]={'calendar_days':0,'eligible_days':0,'under_18_or_requested_hours':0}
            continue
        daily=q.resample('D').agg(['mean','count']);daily.loc[daily['count']<min_hours,'mean']=np.nan
        output[name]=daily['mean'].rename(name)
        daily_coverage[name]={'calendar_days':len(daily),'eligible_days':int(daily['count'].ge(min_hours).sum()),'under_18_or_requested_hours':int(daily['count'].lt(min_hours).sum())}
    audit={'archive_member':MEMBER,'raw_rows':len(raw),'valid_rows_before_duplicate_adjudication':int(valid.sum()),
           'rejection_counts_nonexclusive':{'QC_not_Valid':int((~quality).sum()),'unit_not_UG_M3':int((~unit).sum()),'duration_not_1_Hr':int((~duration).sum()),'missing_nonfinite_or_negative_concentration':int((~finite).sum()),'invalid_or_nonhourly_timestamp':int((~hourly).sum())},
           'duplicate_valid_timestamp_value_pairs_removed':removed,'conflicting_timestamp_count':len(conflicts),'conflicting_unique_measurement_rows_excluded':int(conflict_rows.sum()),'retained_unique_valid_hours':len(clean),'min_hours_per_day':min_hours,'daily_coverage_by_convention':daily_coverage,
           'convention_hour_shifts':dict(CONVENTIONS),'concentration_unit_filter':'UG/M3','value_column':'Raw Conc. (not AQI or NowCast)',
           'interpretation':'Four averaging-label hypotheses for the same monitoring series; not four independent stations or independent source validations.',
           'full_original_record_QA_verified':False,'station_day_averaging_convention_verified':False}
    return output,audit


def station_day_metrics(epa: pd.Series,mirror: pd.Series,tolerance: float=1e-4):
    if not np.isfinite(tolerance) or tolerance<0:raise ValueError('Matching tolerance must be finite and nonnegative')
    pairs=pd.concat([epa.rename('epa'),mirror.rename('mirror')],axis=1).replace([np.inf,-np.inf],np.nan).dropna()
    delta=pairs.mirror-pairs.epa
    return {'n_pairs':len(pairs),'matching_daily_means_at_1e_4':int(delta.abs().le(tolerance).sum()),
            'MAE':float(delta.abs().mean()) if len(pairs) else None,'RMSE':float(np.sqrt(np.mean(delta**2))) if len(pairs) else None,
            'bias_mirror_minus_epa':float(delta.mean()) if len(pairs) else None,'first_paired_date':str(pairs.index.min().date()) if len(pairs) else None,'last_paired_date':str(pairs.index.max().date()) if len(pairs) else None}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--epa',type=Path,required=True);parser.add_argument('--mirror',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(argv)
    if args.output.exists():parser.error('Choose a new output directory; existing output is preserved')
    epa=load_epa_daily(args.epa);hypotheses,qa=mirror_daily(args.mirror)
    results=pd.DataFrame([{'convention':name,**station_day_metrics(epa,value)}for name,value in hypotheses.items()])
    analysis={'purpose':'Station-day identity/alignment sensitivity within the embassy monitoring network, not independent-site validation','epa_calendar_days':len(epa),'epa_nonmissing_days':int(epa.notna().sum()),'mirror_QC':qa,'comparison_tolerance_ugm3':1e-4,'bias_definition':'Mirror daily mean minus EPA-hosted daily mean','no_best_alignment_selected':True,'full_record_QA_verified':False,'averaging_convention_verified':False,'source_sha256':{args.epa.name:sha256(args.epa.read_bytes()).hexdigest(),args.mirror.name:sha256(args.mirror.read_bytes()).hexdigest()},'script_sha256':sha256(Path(__file__).read_bytes()).hexdigest()}
    text=json.dumps(analysis,indent=2,allow_nan=False)+'\n'
    args.output.mkdir(parents=True)
    results.to_csv(args.output/'station_day_sensitivity.csv',index=False)
    (args.output/'analysis.json').write_text(text)
    print(results.to_string(index=False))
    return 0

if __name__=='__main__':raise SystemExit(main())
