"""Conditional independent-reference comparison, retaining daily alignment ambiguity."""
from pathlib import Path
import argparse
import hashlib
import json
from zipfile import ZipFile
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def metrics(frame):
    d=frame[['observed','model']].replace([np.inf,-np.inf],np.nan).dropna()
    if d.empty:return {'n':0,'bias':np.nan,'MAE':np.nan,'RMSE':np.nan,'Pearson_r':np.nan,'Spearman_rho':np.nan,'R2':np.nan}
    e=d.model-d.observed;den=((d.observed-d.observed.mean())**2).sum()
    return {'n':len(d),'bias':float(e.mean()),'MAE':float(e.abs().mean()),'RMSE':float(np.sqrt((e**2).mean())),'Pearson_r':float(d.observed.corr(d.model)),'Spearman_rho':float(spearmanr(d.observed,d.model).statistic) if len(d)>1 else np.nan,'R2':float(1-(e**2).sum()/den) if den>0 else np.nan}


def model_daily(data, basis='BST', min_hours=18):
    """Explicit release timezone, never infer a station averaging timezone."""
    d=data[['ts','cams_pm25_ugm3']].copy()
    t=pd.to_datetime(d.ts,errors='raise')
    if t.duplicated().any():raise ValueError('Duplicate release hour')
    t=t.dt.tz_localize('Asia/Dhaka')
    if basis=='UTC':t=t.dt.tz_convert('UTC')
    elif basis!='BST':raise ValueError('Unknown daily basis')
    d.index=t;v=pd.to_numeric(d.cams_pm25_ugm3,errors='raise').where(lambda x:np.isfinite(x)&x.ge(0))
    daily=v.resample('D').agg(['mean','count']);daily.index=daily.index.tz_localize(None)
    daily.loc[daily['count']<min_hours,'mean']=np.nan
    return daily.rename(columns={'mean':'model','count':'model_hours'})


def monthly_common_pairs(pairs,min_coverage=.75):
    d=pairs[['observed','model']].dropna()
    mean=d.resample('MS').mean();n=d.observed.resample('MS').count()
    mean['matched_days']=n;mean['expected_days']=mean.index.days_in_month
    mean['coverage']=mean.matched_days/mean.expected_days
    mean['eligible']=mean.coverage.ge(min_coverage)
    return mean


def block_uncertainty(pairs,block=30,reps=1000,seed=726):
    # Retain calendar gaps in the sampling frame; do not compress missing days.
    a=pairs[['observed','model']].to_numpy(float);n=len(a);rng=np.random.default_rng(seed)
    values={k:[] for k in ['bias','MAE','RMSE','Pearson_r']}
    if n<block:return {}
    for _ in range(reps):
        starts=rng.integers(0,n-block+1,size=int(np.ceil(n/block)))
        indices=np.concatenate([np.arange(s,s+block) for s in starts])[:n]
        v=a[indices];v=v[np.isfinite(v).all(axis=1)]
        if len(v)<3:continue
        e=v[:,1]-v[:,0]
        draw={'bias':e.mean(),'MAE':np.abs(e).mean(),'RMSE':np.sqrt(np.mean(e**2)),'Pearson_r':np.corrcoef(v[:,0],v[:,1])[0,1]}
        for k,x in draw.items():
            if np.isfinite(x):values[k].append(float(x))
    return {k:{'lower':float(np.quantile(x,.025)),'upper':float(np.quantile(x,.975)),'draws':len(x)} for k,x in values.items() if x}


def mirror_daily(zip_path):
    with ZipFile(zip_path) as archive:
        with archive.open('PM2.5_data/dhaka.csv') as stream:d=pd.read_csv(stream)
    d['time']=pd.to_datetime(d['Date (LT)'],format='%Y-%m-%d %I:%M %p',errors='raise')
    d['value']=pd.to_numeric(d['Raw Conc.'],errors='coerce')
    valid=d['QC Name'].eq('Valid')&d['Conc. Unit'].eq('UG/M3')&d.Duration.eq('1 Hr')&d.value.ge(0)&np.isfinite(d.value)
    clean=d.loc[valid,['time','value']].drop_duplicates()
    conflicts=clean.loc[clean.time.duplicated(keep=False),'time'].unique()
    clean=clean.loc[~clean.time.isin(conflicts)].set_index('time').sort_index()
    output={}
    for name,shift in [('local_labels',0),('local_hour_ending',-1),('UTC_labels',-6),('UTC_hour_ending',-7)]:
        q=clean.copy();q.index=q.index+pd.Timedelta(hours=shift)
        mean=q.value.resample('D').mean();count=q.value.resample('D').count()
        output[name]=mean.where(count>=18)
    return output,{'raw_rows':len(d),'valid_rows_before_duplicate_adjudication':int(valid.sum()),'conflicting_timestamp_count':len(conflicts),'retained_unique_valid_hours':len(clean),'point':'All four conventions are sensitivity checks, not four independent stations; exact averaging convention remains a source question.'}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--release',type=Path,required=True);p.add_argument('--epa',type=Path,required=True);p.add_argument('--mirror',type=Path)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--bootstrap-reps',type=int,default=1000)
    args=p.parse_args()
    if args.output.exists():p.error('Choose a new output directory')
    raw=pd.read_csv(args.release);ref=pd.read_csv(args.epa,parse_dates=['date']).set_index('date').pm25_ugm3
    if ref.index.duplicated().any():raise ValueError('Duplicate station date')
    ref=ref.where(np.isfinite(ref)&ref.ge(0))
    calendar=pd.date_range('2017-01-01','2021-12-31',freq='D')
    rows=[];primary=None;daily_outputs=[]
    for basis in ['BST','UTC']:
        daily=model_daily(raw,basis)
        for shift in [-1,0,1]:
            q=daily.copy();q.index=q.index+pd.Timedelta(days=shift)
            pair=pd.DataFrame({'observed':ref.reindex(calendar),'model':q.model.reindex(calendar)})
            stat=metrics(pair);rows.append({'model_daily_basis':basis,'model_calendar_shift_days':shift,**stat})
            qout=pair.copy();qout['model_daily_basis']=basis;qout['model_calendar_shift_days']=shift;daily_outputs.append(qout)
            if basis=='BST' and shift==0:primary=pair
    args.output.mkdir(parents=True)
    pd.DataFrame(rows).to_csv(args.output/'daily_alignment_sensitivity.csv',index=False)
    pd.concat(daily_outputs).rename_axis('date').to_csv(args.output/'paired_daily_all_alignments.csv')
    month=monthly_common_pairs(primary);month.to_csv(args.output/'monthly_matched_coverage.csv')
    summaries=[{'scope':'nominal_BST_daily',**metrics(primary)},{'scope':'nominal_BST_monthly_ge75pct_reference_days',**metrics(month.loc[month.eligible])}]
    for year,g in primary.groupby(primary.index.year):summaries.append({'scope':f'year_{year}',**metrics(g)})
    for name,months in [('DJF',[12,1,2]),('MAM',[3,4,5]),('JJAS',[6,7,8,9]),('ON',[10,11])]:
        summaries.append({'scope':'conventional_'+name,**metrics(primary.loc[primary.index.month.isin(months)])})
    pd.DataFrame(summaries).to_csv(args.output/'reference_metrics.csv',index=False)
    uncertainty={str(block):block_uncertainty(primary,block,args.bootstrap_reps) for block in [7,30]}
    (args.output/'block_uncertainty.json').write_text(json.dumps(uncertainty,indent=2)+'\n')
    matched=primary.dropna();fig,ax=plt.subplots(2,1,figsize=(11,7),layout='constrained')
    ax[0].plot(primary.index,primary.observed,color='black',lw=.5,label='Published embassy daily observations')
    ax[0].plot(primary.index,primary.model,color='#b24e27',alpha=.65,lw=.5,label='HyAQMet CAMS daily mean (BST)');ax[0].legend(fontsize=8);ax[0].set_ylabel('PM₂.₅ (µg/m³)')
    ax[0].set_title('Conditional regional-product / point-monitor comparison; daily convention unresolved')
    ax[1].scatter(matched.observed,matched.model,s=5,alpha=.2);lim=max(matched.max());ax[1].plot([0,lim],[0,lim],'k--',lw=1)
    ax[1].set_xlabel('Embassy observed PM₂.₅ (µg/m³)');ax[1].set_ylabel('Regional CAMS PM₂.₅ (µg/m³)')
    fig.savefig(args.output/'independent_reference_comparison.png',dpi=180);plt.close(fig)
    fig,ax=plt.subplots(figsize=(10,4),layout='constrained');paired=month.loc[month.eligible]
    ax.plot(paired.index,paired.observed,label='Embassy matched-day mean');ax.plot(paired.index,paired.model,label='CAMS same matched days');ax.legend();ax.set_ylabel('PM₂.₅ (µg/m³)');ax.set_title('Monthly comparison uses identical observed days and ≥75% daily coverage')
    fig.savefig(args.output/'matched_monthly_comparison.png',dpi=180);plt.close(fig)
    mirror_info=None
    if args.mirror:
        hypotheses,mirror_info=mirror_daily(args.mirror);check=[]
        for name,series in hypotheses.items():
            dates=ref.index.intersection(series.index);pair=pd.DataFrame({'observed':ref.reindex(dates),'model':series.reindex(dates)})
            result=metrics(pair);delta=(pair.observed-pair.model).abs();result.update({'convention':name,'matching_daily_means_at_1e_4':int((delta<1e-4).sum())});check.append(result)
        pd.DataFrame(check).to_csv(args.output/'hourly_mirror_station_day_sensitivity.csv',index=False)
    meta={'assumption':'Nominal release BST calendar days compared with published EPA date labels; station-day averaging timezone and original QA remain unresolved. UTC and ±1day sensitivity retained without choosing the best after seeing scores.','comparison_type':'Conditional paired independent-point-reference comparison; regional spatial support differs, not causal or operational validation.','primary_metrics':metrics(primary),'bootstrap':'Moving calendar blocks of7/30days; conditional sampling intervals, not measurement/model-structural uncertainty.','mirror':mirror_info,'source_hashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [args.release,args.epa]+([args.mirror] if args.mirror else [])}}
    (args.output/'analysis_manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    m=meta['primary_metrics']
    (args.output/'findings.md').write_text(f"# Conditional independent-reference comparison\n\nMatched daily cases: {m['n']}. Nominal BST comparison: bias {m['bias']:.3f}, RMSE {m['RMSE']:.3f}, MAE {m['MAE']:.3f} µg/m³; Pearson r {m['Pearson_r']:.3f}. Bias is model minus reference.\n\n{meta['assumption']}\n\nBoth monthly means use identical available reference days, with ≥75% daily coverage. Seven- and30-day bootstrap intervals are conditional on the stated pairing; they do not resolve station QA or spatial representativeness. The hourly mirror is the same monitoring network, not another independent site. No held-out forecast or calibration was performed.\n")
    print(json.dumps(m,indent=2))

if __name__=='__main__':main()
