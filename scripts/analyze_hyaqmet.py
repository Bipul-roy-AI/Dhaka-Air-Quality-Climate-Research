"""Reproduce descriptive/inter-product HyAQMet analyses, preserving release defects.

The CSV is never repaired or overwritten. Both published-season and released-label
sensitivity tables are emitted; calendar months are the primary climatology.
No comparison between model products is independent station validation.
"""
from __future__ import annotations
import argparse
from hashlib import sha256
import json
import subprocess
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

SEASONS=['Winter','Spring','Summer','Monsoon','Autumn','Late Autumn']
COMPONENTS=['merra_bc_surface_ugm3','merra_oc_surface_ugm3','merra_so4_surface_ugm3','merra_dust_pm25_ugm3']
POLLUTANTS=['cams_pm25_ugm3','cams_pm10_ugm3','cams_no2_ugm3','cams_o3_ugm3','cams_co_mgm3','cams_so2_ugm3']
MERRA_RETAINED_MAP={
    'Black Carbon Surface Mass Concentration (µg/m³)':'merra_bc_surface_ugm3',
    'Organic Carbon Surface Mass Concentration (µg/m³)':'merra_oc_surface_ugm3',
    'SO4 Surface Mass Concentration (µg/m³)':'merra_so4_surface_ugm3',
    'Dust Surface Mass Concentration - PM2.5 (µg/m³)':'merra_dust_pm25_ugm3',
    'Total Aerosol Extinction AOT 550nm (-)':'merra_aot_extinction_550nm',
    'Total Aerosol Angstrom Parameter 470-870nm (-)':'merra_angstrom_470_870',
    'Dust Extinction AOT 550nm - PM2.5 (-)':'merra_dust_ext_aot_pm25',
    'Surface Wind Speed (m/s)':'merra_wind_speed_ms',
    'Surface Specific Humidity (g/kg)':'merra_specific_humidity_gkg',
    'Total Surface Precipitation (mm/hr)':'merra_precip_mmhr',
    'SO2 Column Mass Density (mg/m²)':'merra_so2_col_mgm2',
    'Total Column Ozone (DU)':'merra_col_ozone_du',
    'SO2 Surface Mass Concentration (µg/m³)':'merra_so2_surface_ugm3',
}



def season_labels(timestamps, scheme='paper_table3'):
    """Date-based boundaries respect leap years; never overwrite released labels."""
    t=pd.DatetimeIndex(timestamps); md=t.month*100+t.day
    if scheme=='paper_table3':
        bins=[(216,416,'Spring'),(416,616,'Summer'),(616,1016,'Monsoon'),(1016,1116,'Autumn'),(1116,1216,'Late Autumn')]
    elif scheme=='notebook':
        bins=[(215,415,'Spring'),(415,615,'Summer'),(615,815,'Monsoon'),(815,1015,'Autumn'),(1015,1215,'Late Autumn')]
    else:raise ValueError('Unknown season scheme')
    out=np.full(len(t),'Winter',dtype=object)
    for lo,hi,name in bins:out[(md>=lo)&(md<hi)]=name
    return pd.Series(out,index=t)


def scale_by_blh(mass,blh,reference_blh=None,floor=None):
    """Construct a sensitivity proxy, not a physically validated calibration.

    Invalid/nonpositive BLH remains missing even when a positive floor is used.
    """
    mass=np.asarray(mass,dtype=float);height=np.asarray(blh,dtype=float)
    if mass.shape!=height.shape:raise ValueError('Mass and BLH must have equal shapes')
    valid=np.isfinite(mass)&np.isfinite(height)&(height>0)
    reference=np.median(height[valid]) if reference_blh is None and valid.any() else reference_blh
    if reference is None or not np.isfinite(reference) or reference<=0:raise ValueError('Positive finite reference BLH required')
    if floor is not None and (not np.isfinite(floor) or floor<=0):raise ValueError('Positive finite floor required')
    denom=np.maximum(height,floor) if floor is not None else height
    out=np.full_like(mass,np.nan);out[valid]=mass[valid]*reference/denom[valid]
    return out


def annual_amount_sums(values,index):
    """Diagnostic sum of hourly *amounts*; caller must verify actual field semantics."""
    s=pd.Series(np.asarray(values,dtype=float),index=pd.DatetimeIndex(index))
    return s.groupby(s.index.year).sum(min_count=1)


def pair_metrics(a,b):
    a=np.asarray(a,dtype=float);b=np.asarray(b,dtype=float);valid=np.isfinite(a)&np.isfinite(b);a=a[valid];b=b[valid]
    if not len(a):return {'n':0,'bias_a_minus_b':None,'RMSE':None,'MAE':None,'Pearson_r':None,'Spearman_rho':None,'identity_R2_a_reference':None}
    err=a-b;var=np.sum((a-a.mean())**2)
    return {'n':len(a),'bias_a_minus_b':float(err.mean()),'RMSE':float(np.sqrt(np.mean(err**2))),'MAE':float(np.abs(err).mean()),'Pearson_r':float(np.corrcoef(a,b)[0,1]) if len(a)>1 and a.std()>0 and b.std()>0 else None,'Spearman_rho':float(pd.Series(a).corr(pd.Series(b),method='spearman')) if len(a)>1 and a.std()>0 and b.std()>0 else None,'identity_R2_a_reference':float(1-np.sum(err**2)/var) if var>0 else None}


def vif_table(frame,center=True):
    x=frame.to_numpy(dtype=float);x=x[np.isfinite(x).all(axis=1)]
    if center:x=x-x.mean(axis=0)
    rows=[]
    for j,name in enumerate(frame.columns):
        y=x[:,j];other=np.delete(x,j,axis=1)
        fit=np.linalg.lstsq(other,y,rcond=None)[0];sse=np.sum((y-other@fit)**2);sst=np.sum(y*y)
        vif=float(sst/sse) if sst>0 and sse>sst*1e-12 else float('inf')
        rows.append({'variable':name,'VIF':vif,'regression_convention':'centered_with_intercept' if center else 'uncentered_no_intercept_notebook','n':len(x)})
    return pd.DataFrame(rows)



def paper_vs_reproduced(qc,data,deciles,associations):
    """Trace selected printed claims to explicit computations, without forcing agreement.

    Publication locations refer to the supplied15-page article. Approximate ratios
    are compared only at whole-ratio precision; that is not statistical validation.
    Candidate counts are not inferred when source extracts were not supplied.
    """
    rows=[]
    def add(item,location,claim,value,definition,status,limit):
        rows.append({'result':item,'paper_location':location,'paper_claim':claim,'reproduced_value':value,'definition':definition,'match_status':status,'limitation':limit})
    def rounded(value,claim,digits):
        if value is None or not np.isfinite(value):return 'not_assessed'
        return 'reproduced_at_reported_precision' if format(value,f'.{digits}f')==format(claim,f'.{digits}f') else 'not_reproduced_at_reported_precision'
    no_validation='Structural agreement is not independent concentration validation.'
    add('rows','Abstractp1;§3.1p7',52584,qc['rows'],'CSV record count','reproduced_exactly' if qc['rows']==52584 else 'not_reproduced',no_validation)
    add('columns','Abstractp1;Table4p7',42,qc['columns_including_timestamp'],'CSV columns including timestamp and derived time fields','reproduced_exactly' if qc['columns_including_timestamp']==42 else 'not_reproduced','42 columns are not42 independent environmental measurements.')
    nulls=sum(qc['missing_by_column'].values())
    add('missing_cells','§3.1p7',0,nulls,'Null cells in all released non-timestamp columns; timestamps checked separately','reproduced_exactly' if nulls==0 else 'not_reproduced','Complete model output does not establish complete station monitoring.')
    add('missing_expected_hours','§3.1p7',0,qc['missing_expected_hours'],'Absent labels on2017-01-01 through2022-12-31 hourlyBST grid','reproduced_exactly' if qc['missing_expected_hours']==0 and qc['unexpected_hours']==0 else 'not_reproduced','Interpolated labels add no independently observed hourly signal.')
    r=next((a['Pearson_r']for a in associations if a['scale']=='hourly_unadjusted'),None)
    add('BLH_PM25_Pearson_r','§3.6p11',-.65,r,'Pearson correlation of released hourly boundary_layer_height_m and cams_pm25_ugm3',rounded(r,-.65,2),'Serial dependence, interpolation and shared seasonal structure prevent causal interpretation.')
    ratio=float(deciles.pm25_mean_ugm3.iloc[0]/deciles.pm25_mean_ugm3.iloc[-1])
    add('lowest_to_highest_BLH_decile_ratio','§3.6/Figure5p11','approximately3',ratio,'Mean CAMS PM2.5 in lowest BLH decile / highest decile using qcut over all released rows',rounded(ratio,3,0),'Whole-number approximate agreement; decile spread is not an uncertainty interval.')
    add('CAMS_PM25_mean_2017_2022','Table6p11',102.3,float(data.cams_pm25_ugm3.mean()),'Mean of all released2017–2022 hourly CAMS PM2.5 inµg/m³',rounded(float(data.cams_pm25_ugm3.mean()),102.3,1),'Regional model mean, not an independent ground-reference mean.')
    stage=qc.get('vif_before_after_diagnostics',{})
    before=stage.get('original_candidates_centered_with_intercept',{}).get('variables')
    after=stage.get('released_retained_centered_with_intercept',{}).get('variables')
    count_value=f'{before}->{after}' if before is not None and after is not None else None
    add('MERRA_candidate_to_retained_count','§2.7p6','26->13',count_value,'Numeric original-source candidate columns and release merra_ columns; source-to-release mapping is explicit','counts_reproduced_selection_not_rerun' if (before,after)==(26,13) else ('not_assessed' if count_value is None else 'not_reproduced'),'Does not rerun a physical-selection procedure or establish globally optimal features.')
    for convention in ['centered_with_intercept','uncentered_no_intercept_notebook']:
        diag=stage.get('released_retained_'+convention,{})
        max_vif=diag.get('largest_finite_vif')
        high=diag.get('at_or_above_100_including_infinite')
        add('retained_MERRA_VIF_'+convention,'§2.7p6','all13<100',max_vif,'Largest finiteVIF; all-VIF threshold additionally checks high/infinite count under named regression convention','threshold_reproduced_under_named_convention' if high==0 and diag.get('variables')==13 else ('not_assessed' if high is None else 'not_reproduced'),'VIF100 is the paper diagnostic, not a universal predictor-selection target; intercept convention changes VIF.')
    codes=qc['released_season_codes']
    add('season_codes','§2.8/Table3p7','0,1,2,3,4,5',','.join(map(str,codes)),'Unique released integer codes','reproduced_exactly' if codes==list(range(6)) else 'not_reproduced','Original codes preserved; no silent recoding.')
    mismatch=qc['released_vs_paper_table3_label_disagreements']
    add('season_label_disagreements_with_Table3','§3.1/Table3p7',0,mismatch,'Hourly released labels compared with published date boundaries, leap-year-aware','reproduced_exactly' if mismatch==0 else 'not_reproduced','Both published and released season definitions remain separate sensitivities; calendar months primary.')
    return pd.DataFrame(rows)


def _json_safe(value):
    if isinstance(value,dict):return {k:_json_safe(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [_json_safe(v) for v in value]
    if isinstance(value,(float,np.floating)) and not np.isfinite(value):return None
    if isinstance(value,np.integer):return int(value)
    return value



def _source_commit_provenance(source_dir,files):
    """Read Git metadata/objects only; no checkout hooks or notebooks execute."""
    try:
        root=Path(subprocess.check_output(['git','-C',str(source_dir),'rev-parse','--show-toplevel'],stderr=subprocess.DEVNULL,text=True).strip()).resolve()
        commit=subprocess.check_output(['git','-C',str(root),'rev-parse','--verify','HEAD^{commit}'],stderr=subprocess.DEVNULL,text=True).strip()
        checks={}
        for path in files:
            relative=Path(path).resolve().relative_to(root).as_posix()
            committed=subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD:'+relative],stderr=subprocess.DEVNULL,text=True).strip()
            current=subprocess.check_output(['git','-C',str(root),'hash-object','--no-filters','--',relative],stderr=subprocess.DEVNULL,text=True).strip()
            checks[Path(path).name]=committed==current
        return {'commit':commit,'source_file_bytes_match_commit':checks,'all_supplied_source_files_match':bool(checks) and all(checks.values()),'operation':'Read-only commit/object comparison with filters disabled; source SHA256 also recorded separately'}
    except (subprocess.CalledProcessError,FileNotFoundError,ValueError):
        return {'commit':None,'all_supplied_source_files_match':False,'status':'Git commit linkage not verified; individual file SHA256 remains available'}


def _read_source(path):
    data=pd.read_csv(path,encoding='latin1')
    data['ts']=pd.to_datetime(data.timestamp_bst,format='%m/%d/%Y %H:%M')
    if data.ts.duplicated().any():raise ValueError(f'Duplicate source timestamp: {path}')
    return data.set_index('ts')


def analyze(release_csv,source_dir,output,figure_dpi=300):
    if isinstance(figure_dpi,bool) or not isinstance(figure_dpi,int) or not 150<=figure_dpi<=1200:raise ValueError('figure_dpi must be an integer from150 to1200')
    release_csv=Path(release_csv);source_dir=Path(source_dir);output=Path(output)
    if output.exists() and any(output.iterdir()):raise ValueError('Choose a new or empty output directory')
    data=pd.read_csv(release_csv);data['ts']=pd.to_datetime(data.ts,errors='raise')
    if data.ts.isna().any() or data.ts.duplicated().any():raise ValueError('Missing or duplicate release timestamps')
    data=data.sort_values('ts').set_index('ts')
    required=set(COMPONENTS+POLLUTANTS+['boundary_layer_height_m','precip_mm','solar_radiation_wm2','season','merra_precip_mmhr','wind_speed_ms','merra_wind_speed_ms'])
    missing=required-set(data)
    if missing:raise ValueError(f'Missing analysis columns: {sorted(missing)}')
    output.mkdir(parents=True,exist_ok=True)
    source_hashes={}
    numeric=data.select_dtypes(include='number');native_numeric=list(numeric.columns)
    numeric.describe(percentiles=[.01,.05,.25,.5,.75,.95,.99]).T.to_csv(output/'numeric_summary.csv')
    expected=pd.date_range('2017-01-01','2022-12-31 23:00',freq='h')
    qc={'analysis_script_sha256':sha256(Path(__file__).read_bytes()).hexdigest(),'release_sha256':sha256(release_csv.read_bytes()).hexdigest(),'rows':len(data),'columns_including_timestamp':len(data.columns)+1,'first_bst':str(data.index.min()),'last_bst':str(data.index.max()),'declared_timezone':'Asia/Dhaka/BST from release README; naive file labels retained','missing_expected_hours':len(expected.difference(data.index)),'unexpected_hours':len(data.index.difference(expected)),'interval_counts_hours':{str(k):int(v)for k,v in data.index.to_series().diff().dropna().dt.total_seconds().div(3600).value_counts().items()},'missing_by_column':data.isna().sum().to_dict(),'nonfinite_by_numeric_column':{c:int((~np.isfinite(numeric[c])).sum())for c in numeric},'negative_by_concentration_or_precip_column':{c:int(data[c].lt(0).sum())for c in COMPONENTS+POLLUTANTS+['precip_mm','merra_precip_mmhr']},'pm25_greater_than_pm10':int((data.cams_pm25_ugm3>data.cams_pm10_ugm3).sum()),'nonpositive_blh':int(data.boundary_layer_height_m.le(0).sum()),'blh_below_50m':int(data.boundary_layer_height_m.lt(50).sum()),'solar_min':float(data.solar_radiation_wm2.min()),'solar_max':float(data.solar_radiation_wm2.max()),'night_01_04_bst_solar_above_001':int(((data.index.hour>=1)&(data.index.hour<=4)&data.solar_radiation_wm2.gt(.01)).sum())}
    if 'relative_humidity_pct' in data:qc['relative_humidity_outside_0_100']=int((~data.relative_humidity_pct.between(0,100)).sum())
    if 'total_cloud_cover_fraction' in data:qc['cloud_outside_0_1']=int((~data.total_cloud_cover_fraction.between(0,1)).sum())
    for c in ['hour_sin','hour_cos','doy_sin','doy_cos']:
        if c in data:qc[f'{c}_outside_minus1_plus1']=int((~data[c].between(-1-1e-12,1+1e-12)).sum())
    # Calendar month is primary; conflicting season definitions are sensitivities.
    data['paper_table3_season']=season_labels(data.index,'paper_table3').to_numpy()
    data['notebook_season']=season_labels(data.index,'notebook').to_numpy()
    season_compare=pd.crosstab(data['season'],data['paper_table3_season']);season_compare.to_csv(output/'released_vs_paper_season_counts.csv')
    qc['released_vs_paper_table3_label_disagreements']=int(data.season.ne(data.paper_table3_season).sum())
    qc['released_vs_notebook_label_disagreements']=int(data.season.ne(data.notebook_season).sum())
    qc['released_season_codes']=sorted(data.season_code.unique().tolist()) if 'season_code'in data else []
    for key in ['season','paper_table3_season','notebook_season']:
        data.groupby(key)[POLLUTANTS].agg(['count','mean','std','min','max']).to_csv(output/f'pollutant_{key}_sensitivity.csv')
    for label,group in [('calendar_month',data.index.month),('local_hour',data.index.hour)]:
        data.groupby(group)[POLLUTANTS].agg(['count','mean','std']).to_csv(output/f'pollutant_{label}_climatology.csv')
    monthly=data[POLLUTANTS].resample('MS').mean();monthly.to_csv(output/'pollutant_monthly_time_series.csv')
    # These correlations describe model products, not independent causal evidence.
    data[native_numeric].corr().to_csv(output/'pearson_correlation.csv')
    merra=[c for c in native_numeric if c.startswith('merra_')]
    pd.concat([vif_table(data[merra],True),vif_table(data[merra],False)]).to_csv(output/'merra_vif_diagnostic.csv',index=False)
    data['merra_component_sum_ugm3']=data[COMPONENTS].sum(axis=1,min_count=len(COMPONENTS))
    reference=float(data.boundary_layer_height_m.median())
    data['merra_blh_scaled_raw']=scale_by_blh(data.merra_component_sum_ugm3,data.boundary_layer_height_m,reference)
    data['merra_blh_scaled_floor50']=scale_by_blh(data.merra_component_sum_ugm3,data.boundary_layer_height_m,reference,50)
    qc['reference_median_blh_m']=reference
    variants=['merra_component_sum_ugm3','merra_blh_scaled_raw','merra_blh_scaled_floor50']
    comparisons=[]
    for convention in ['all','season','paper_table3_season']:
        groups=[('all',data)] if convention=='all' else data.groupby(convention)
        for season,sub in groups:
            for variant in variants:
                comparisons.append({'season_convention':convention,'season':season,'a':'cams_pm25_ugm3','b':variant,**pair_metrics(sub.cams_pm25_ugm3,sub[variant]),'interpretation':'model_intercomparison; BLH variants are constructed sensitivity proxies'})
    pd.DataFrame(comparisons).to_csv(output/'pm25_intercomparison.csv',index=False)
    # Explicit native3h sensitivity, not extra independent interpolated samples.
    native=data[data.index.hour%3==0]
    pd.DataFrame([{'a':'cams_pm25_ugm3','b':v,**pair_metrics(native.cams_pm25_ugm3,native[v])}for v in variants]).to_csv(output/'pm25_native_3hour_sensitivity.csv',index=False)
    deciles=data.assign(blh_decile=pd.qcut(data.boundary_layer_height_m,q=10,labels=False,duplicates='drop')).groupby('blh_decile').agg(n=('cams_pm25_ugm3','size'),blh_mean_m=('boundary_layer_height_m','mean'),pm25_mean_ugm3=('cams_pm25_ugm3','mean'),pm25_std_ugm3=('cams_pm25_ugm3','std'))
    deciles.to_csv(output/'blh_deciles.csv')
    daily=data[['cams_pm25_ugm3','boundary_layer_height_m']].resample('D').mean()
    residual=daily-daily.groupby([daily.index.year,daily.index.month]).transform('mean')
    associations=[{'scale':'hourly_unadjusted','n':len(data),'Pearson_r':data.cams_pm25_ugm3.corr(data.boundary_layer_height_m)},{'scale':'daily_unadjusted','n':len(daily),'Pearson_r':daily.cams_pm25_ugm3.corr(daily.boundary_layer_height_m)},{'scale':'daily_within_year_month_demeaned','n':len(residual),'Pearson_r':residual.cams_pm25_ugm3.corr(residual.boundary_layer_height_m)}]
    pd.DataFrame(associations).to_csv(output/'blh_associations.csv',index=False)
    daily.assign(pm25_yearmonth_residual=residual.cams_pm25_ugm3,blh_yearmonth_residual=residual.boundary_layer_height_m).to_csv(output/'daily_blh_pm25.csv')
    annual=pd.DataFrame({'sum_reported_era5_precip_field_mm_if_hourly_amount':annual_amount_sums(data.precip_mm,data.index),'sum_merra_precip_mmhr_times1hour':annual_amount_sums(data.merra_precip_mmhr,data.index)})
    annual.to_csv(output/'annual_precipitation_diagnostic.csv')
    qc['precipitation_sum_semantics_warning']='Summing precip_mm as hourly amount gives implausible totals; no deaccumulation is certified without original NetCDF/provider metadata.'
    # Released fields vs GitHub source extracts establish which known issues survive.
    field_checks=[];met_comparisons=[]
    era_path=source_dir/'ERA5_hourly_2017-2022_bst.csv'
    merra_path=source_dir/'MERRA-2_hourly_2017-2022_bst.csv'
    cams_path=source_dir/'CAMS_3hourly_2017-2022_bst.csv'
    for p in [era_path,merra_path,cams_path]:
        if p.exists():source_hashes[p.name]=sha256(p.read_bytes()).hexdigest()
    if era_path.exists():
        era=_read_source(era_path)
        for c in ['precip_mm','solar_radiation_wm2','t2m_celsius','wind_speed_ms']:
            aligned=data[[c]].rename(columns={c:c+'_final'}).join(era[[c]].rename(columns={c:c+'_source'}),how='inner')
            a=aligned[c+'_final'];b=aligned[c+'_source']
            field_checks.append({'source':'ERA5_source_extract','field':c,'n':len(aligned),'exact_equal_rows':int(a.eq(b).sum()),'max_abs_difference':float((a-b).abs().max())})
    extended=data.copy()
    if merra_path.exists():
        m=_read_source(merra_path)
        candidate_frame=m.select_dtypes(include='number')
        candidate_vif=pd.concat([vif_table(candidate_frame,True),vif_table(candidate_frame,False)],ignore_index=True)
        candidate_vif['released_column']=candidate_vif.variable.map(MERRA_RETAINED_MAP)
        candidate_vif['retained_in_final_release']=candidate_vif.released_column.isin(merra)
        candidate_vif.to_csv(output/'merra_26_candidate_vif.csv',index=False)
        retained_vif=pd.concat([vif_table(data[merra],True),vif_table(data[merra],False)],ignore_index=True)
        qc['vif_before_after_diagnostics']={}
        for stage,table in [('original_candidates',candidate_vif),('released_retained',retained_vif)]:
            for convention,sub in table.groupby('regression_convention'):
                values=sub.VIF.to_numpy(dtype=float)
                qc['vif_before_after_diagnostics'][stage+'_'+convention]={
                    'variables':len(sub),'at_or_above_100_including_infinite':int((values>=100).sum()),
                    'infinite_or_numerically_exact_dependence':int(np.isinf(values).sum()),
                    'largest_finite_vif':float(np.max(values[np.isfinite(values)])) if np.isfinite(values).any() else None,
                }
        qc['vif_stage_interpretation']='Before/after diagnostic of source candidates and published retained columns, not reproduction or endorsement of a VIF100 selection algorithm; infinite flag uses SSE<=SST*1e-12.'

        total='Total Surface Mass Concentration - PM2.5 (µg/m³)'
        if total in m:
            z=data[['cams_pm25_ugm3','merra_component_sum_ugm3']].join(m[[total]],how='inner')
            pd.DataFrame([{'a':c,'b':'source_merra_labelled_total_PM25',**pair_metrics(z[c],z[total]),'warning':'Source-extract total-labelled model quantity, not independent truth; not a released final field'}for c in ['cams_pm25_ugm3','merra_component_sum_ugm3']]).to_csv(output/'source_merra_total_mass_sensitivity.csv',index=False)
        mapping={'2-meter Air Temperature (°C)':'t2m_celsius','Surface Pressure (hPa)':'surface_pressure_hpa'}
        for original,final in mapping.items():
            if original in m and final in data:
                z=data[[final]].join(m[[original]],how='inner');extended['source_merra_'+final]=m[original].reindex(extended.index);met_comparisons.append({'a':final,'b':'source_merra_'+original,**pair_metrics(z[final],z[original]),'units_verified_from_labels_only':True})
    for a,b in [('wind_speed_ms','merra_wind_speed_ms'),('precip_mm','merra_precip_mmhr'),('cams_so2_ugm3','merra_so2_surface_ugm3')]:
        met_comparisons.append({'a':a,'b':b,**pair_metrics(data[a],data[b]),'units_verified_from_labels_only':True,'warning':'ERA5_precip_accumulation_semantics_suspect' if a=='precip_mm' else 'Different model products and spatial supports; no ground-truth reference'})
    if cams_path.exists():
        c=_read_source(cams_path)
        for original,final in [('pm2_5_ugm3','cams_pm25_ugm3'),('co_mgm3','cams_co_mgm3')]:
            z=data[[final]].join(c[[original]],how='inner');field_checks.append({'source':'native_CAMS_3hour_extract','field':final,'n':len(z),'exact_equal_rows':int(z[final].eq(z[original]).sum()),'max_abs_difference':float((z[final]-z[original]).abs().max())})
    seasonal_met=[]
    pairs=[('wind_speed_ms','merra_wind_speed_ms'),('precip_mm','merra_precip_mmhr'),('cams_so2_ugm3','merra_so2_surface_ugm3')]
    pairs += [(c,'source_merra_'+c) for c in ['t2m_celsius','surface_pressure_hpa'] if 'source_merra_'+c in extended]
    for scheme,labels in [('calendar_month',extended.index.month),('released_season_sensitivity',extended.season),('paper_table3_season_sensitivity',extended.paper_table3_season)]:
        for level,sub in extended.groupby(labels):
            for a,b in pairs:seasonal_met.append({'stratum':scheme,'level':level,'a':a,'b':b,**pair_metrics(sub[a],sub[b]),'precipitation_accumulation_warning':a=='precip_mm'})
    pd.DataFrame(seasonal_met).to_csv(output/'meteorology_calendar_season_sensitivities.csv',index=False)
    pd.DataFrame(field_checks).to_csv(output/'final_vs_source_checks.csv',index=False)
    pd.DataFrame(met_comparisons).to_csv(output/'meteorology_and_so2_intercomparison.csv',index=False)
    qc['source_file_sha256']=source_hashes
    qc['source_git_provenance']=_source_commit_provenance(source_dir,[p for p in [era_path,merra_path,cams_path] if p.exists()])
    qc['figure_exports']={'formats':['PNG','SVG','PDF'],'png_dpi':figure_dpi,'font_family':'DejaVu Sans','pdf_fonttype':42,'ps_fonttype':42,'svg_fonttype':'none (editable text)','dense_scatter_rasterized':True,'figure_PDFs_only_no_manuscript':True,'source_doi':'10.5281/zenodo.20705735'}
    qc['independent_ground_validation_performed']=False
    qc['inferential_pvalues_or_independent_hour_confidence_intervals_claimed']=False
    (output/'quality_and_provenance.json').write_text(json.dumps(_json_safe(qc),indent=2,allow_nan=False)+'\n')
    paper_vs_reproduced(qc,data,deciles,associations).to_csv(output/'paper_vs_reproduced.csv',index=False)
    _figures(data,annual,deciles,residual,output,figure_dpi)
    overall=pd.DataFrame(comparisons).query("season_convention=='all'").set_index('b')
    notes=f'''# HyAQMet final-release descriptive reproduction

Input SHA256 `{qc['release_sha256']}`. Read {len(data):,} rows and {qc['columns_including_timestamp']} columns from final Zenodo CSV; source extracts were separately checked. Timestamp labels are BST/UTC+6 per released README, not inferred from concentration patterns. Primary climatology uses calendar months. All computations retain original released values; no source repair, imputation or station calibration was performed.

## Structural and physical checks

- Expected-hour gaps: {qc['missing_expected_hours']}; unexpected hours: {qc['unexpected_hours']}; missing cells: {int(data[native_numeric].isna().sum().sum())} numeric cells.
- CAMS PM2.5>PM10 rows: {qc['pm25_greater_than_pm10']}; BLH<=0 rows: {qc['nonpositive_blh']}.
- Final solar maximum: {qc['solar_max']:.3f}W/m²; 01–04BST nighttime rows above0.01W/m²: {qc['night_01_04_bst_solar_above_001']}.
- `final_vs_source_checks.csv` quantifies which public-source fields match. Precipitation remains unchanged relative to the source extract, while the final solar field is transformed. Annual sums of the released ERA5 precipitation field are {annual.iloc[:,0].min():,.1f}–{annual.iloc[:,0].max():,.1f}mm **if interpreted as hourly water amounts**; the suspect accumulation semantics survive in the released field. This is not a validated corrected rainfall total. Original NetCDF and provider conventions are needed before deaccumulation.

## Season-definition conflict: exposed, not resolved

Released labels disagree with paper Table3 at {qc['released_vs_paper_table3_label_disagreements']:,} hours and with the public notebook date rules at {qc['released_vs_notebook_label_disagreements']:,} hours. Released codes are {qc['released_season_codes']}; paper states0–5. Table3 extends Monsoon through15October and gives Autumn/LateAutumn approximately one month each; notebook/release use approximately two-month seasons beginning15February/April/June/August/October/December. Separate sensitivity tables preserve both definitions. The user selected reporting both definitions as separate sensitivity analyses. Calendar months remain primary; neither conflicting six-season scheme is silently preferred.

## Inter-product particulate comparison

CAMS mean PM2.5={data.cams_pm25_ugm3.mean():.3f}µg/m³; MERRA component-sum mean={data.merra_component_sum_ugm3.mean():.3f}µg/m³. The component sum is BC+OC+SO4+dust, not a chemically complete independently measured PM2.5 reference. Median BLH={reference:.3f}m; {qc['blh_below_50m']:,} hours have BLH<50m. For CAMS minus unscaled MERRA sum, bias={overall.loc['merra_component_sum_ugm3','bias_a_minus_b']:.3f}µg/m³ and RMSE={overall.loc['merra_component_sum_ugm3','RMSE']:.3f}. Dividing a surface mass proxy by BLH is a constructed sensitivity transformation, not an independently validated calibration; raw-BLH and50m-floor variants are both reported. Identical units do not remove differing spatial support or model construction. Full seasonal and native3h metrics are in CSV files.

## BLH association

The paper reports overall Pearson r=−0.65 (§3.6,p11), whereas the final released columns reproduce hourly unadjusted r={associations[0]['Pearson_r']:.4f}; daily r={associations[1]['Pearson_r']:.4f}; daily within-year-month-demeaned r={associations[2]['Pearson_r']:.4f}. Lowest/highest BLH-decile CAMS mean ratio={deciles.pm25_mean_ugm3.iloc[0]/deciles.pm25_mean_ugm3.iloc[-1]:.3f}. Association and physical plausibility do not identify a causal effect. Interpolated hours and serial dependence do not create independent samples; no independent-hour significance claim is made.

## VIF and meteorology

Both standard centered/intercept VIF and the public notebook's uncentered/no-intercept calculation are reported for the13 retained MERRA columns and, separately, the original26 numeric source candidates in `merra_26_candidate_vif.csv`. Published retention is mapped explicitly by source/release column name; it is not selected anew by a threshold. Before/after high/infinite VIF counts are recorded in `quality_and_provenance.json`; the numerical dependence flag uses residual SSE≤SST×10⁻¹². Their difference matters; VIF100 is not used as a universal selection rule or proof of collinearity removal. Meteorology comparisons use labelled°C/hPa/m/s fields where available, but the ERA5 precipitation comparison is marked suspect due to accumulation semantics. No original upstream units/conversion metadata is independently revalidated from raw NetCDF.

## Outputs and limits

`paper_vs_reproduced.csv` links selected printed claims to their page/table, reproduced values, definitions and limitations; disagreements are retained. CSV summaries cover every released numeric field, calendar-month/local-hour pollutant climatologies, both season sensitivities, correlations, VIF, source field identity, precipitation diagnostics, PM variants and BLH checks. Figures are exported as standalone PNGs at{figure_dpi}dpi plus SVG and PDF with editable/vector axes and text; dense scatter layers are rasterized. PDFs contain figures only, not a manuscript. This is a reproducible final-release audit/intercomparison, not external validation or causal/health attribution. Independent monitor analyses, when present, remain separately labelled and are not used to tune these transformations. No source values are silently corrected and no better forecast claim follows from these descriptive tables.
'''
    (output/'findings.md').write_text(notes)
    print(notes)
    return qc


def _save_figure(fig,out,stem,dpi=300):
    if isinstance(dpi,bool) or not isinstance(dpi,int) or not 150<=dpi<=1200:raise ValueError('Figure DPI must be an integer from150 to1200')
    with matplotlib.rc_context({'pdf.fonttype':42,'ps.fonttype':42,'svg.fonttype':'none','font.family':'DejaVu Sans'}):
        for ext in ['png','svg','pdf']:
            fig.savefig(Path(out)/(stem+'.'+ext),dpi=dpi,bbox_inches='tight',pad_inches=.08)


def _figures(d,annual,deciles,residual,out,figure_dpi=300):
    plt.rcParams.update({'font.size':10,'font.family':'DejaVu Sans','pdf.fonttype':42,'ps.fonttype':42,'svg.fonttype':'none'})
    # Dataset/workflow visual: native temporal support is explicit.
    fig,ax=plt.subplots(figsize=(10,3.3));ax.axis('off')
    sources=[('ERA5-Land + ERA5 SL','hourly meteorology'),('CAMS EAC4','native3h → interpolated hourly'),('MERRA-2','model aerosol/met fields')]
    for i,(a,b)in enumerate(sources):
        ax.text(.16+i*.34,.78,a+'\n'+b,ha='center',va='center',bbox={'boxstyle':'round','facecolor':'#dceaf3','edgecolor':'#456'})
        ax.annotate('',xy=(.5,.4),xytext=(.16+i*.34,.62),arrowprops={'arrowstyle':'->','color':'#456'})
    ax.text(.5,.32,'Final Zenodo CSV:52,584 BST-labelled hourly rows\nQA → calendar climatology → labelled sensitivity/inter-product diagnostics',ha='center',va='center',bbox={'boxstyle':'round','facecolor':'#ecf1dc','edgecolor':'#456'})
    ax.text(.5,.03,'Reanalysis agreement ≠ independent station validation; source defects remain flagged',ha='center')
    _save_figure(fig,out,'workflow',figure_dpi);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(11,4),layout='constrained')
    annual.plot.bar(ax=axes[0]);axes[0].set_ylabel('Annual sum of reported field\n(mm if each row is an hourly amount)');axes[0].set_xlabel('Year');axes[0].legend(['ERA5 suspect accumulation','MERRA hourly amount'],fontsize=7);axes[0].set_title('Released-data precipitation diagnostic')
    solar=d.groupby(d.index.hour).solar_radiation_wm2.mean();axes[1].plot(solar.index,solar.values);axes[1].set_xlabel('BST hour');axes[1].set_ylabel('Final solar irradiance W/m²');axes[1].set_title('Released-data mean diurnal solar cycle')
    _save_figure(fig,out,'data_quality',figure_dpi);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(11,4),layout='constrained')
    for c in ['cams_pm25_ugm3','cams_pm10_ugm3','cams_o3_ugm3']:
        d.groupby(d.index.month)[c].mean().plot(ax=axes[0],label={'cams_pm25_ugm3':'CAMS PM₂.₅','cams_pm10_ugm3':'CAMS PM₁₀','cams_o3_ugm3':'CAMS O₃'}[c])
        d.groupby(d.index.hour)[c].mean().plot(ax=axes[1],label={'cams_pm25_ugm3':'CAMS PM₂.₅','cams_pm10_ugm3':'CAMS PM₁₀','cams_o3_ugm3':'CAMS O₃'}[c])
    axes[0].set_xlabel('Calendar month');axes[0].set_xticks(range(1,13));axes[1].set_xlabel('BST hour');axes[1].set_xticks(range(0,24,3))
    for a in axes:a.set_ylabel('Reported concentration µg/m³');a.legend(fontsize=7)
    fig.suptitle('Released-data reproduction: calendar and diurnal climatology')
    _save_figure(fig,out,'pollutant_climatology',figure_dpi);plt.close(fig)
    cols=['cams_pm25_ugm3','boundary_layer_height_m','wind_speed_ms','relative_humidity_pct','precip_mm','merra_precip_mmhr','merra_component_sum_ugm3','cams_o3_ugm3']
    labels=['CAMS PM₂.₅','ERA5 BLH','ERA5 wind','ERA5 RH','ERA5 precipitation*','MERRA precipitation','MERRA component proxy','CAMS O₃']
    corr=d[cols].corr();fig,ax=plt.subplots(figsize=(8,7),layout='constrained');im=ax.imshow(corr,vmin=-1,vmax=1,cmap='RdBu_r');ax.set_xticks(range(len(cols)),labels,rotation=60,ha='right');ax.set_yticks(range(len(cols)),labels);fig.colorbar(im,ax=ax,label='Pearson r (descriptive)');ax.set_title('Released-data associations; precipitation semantics suspect');_save_figure(fig,out,'correlation',figure_dpi);plt.close(fig)
    fig,axes=plt.subplots(1,3,figsize=(13,4),layout='constrained')
    native=d.loc[d.index.hour%3==0]
    sample=native.sample(min(5000,len(native)),random_state=726)
    panels=[('merra_component_sum_ugm3','Unscaled four-component proxy'),('merra_blh_scaled_raw','Proxy × median BLH / BLH'),('merra_blh_scaled_floor50','Proxy × median BLH / max(BLH,50 m)')]
    for a,(c,title) in zip(axes,panels):
        a.scatter(sample[c],sample.cams_pm25_ugm3,s=3,alpha=.25,rasterized=True)
        a.set_xlabel('MERRA-derived proxy (µg m⁻³)');a.set_ylabel('CAMS PM₂.₅ (µg m⁻³)');a.set_title(title,fontsize=9)
        lim=max(sample[c].max(),sample.cams_pm25_ugm3.max());a.plot([0,lim],[0,lim],color='gray',ls='--',lw=.8)
    fig.suptitle('Released-data reproduction: native 3-hour CAMS/MERRA knots\nFixed-seed 5,000-point display; scaled fields are constructed sensitivities')
    _save_figure(fig,out,'pm25_cross_source',figure_dpi);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(11,4),layout='constrained')
    axes[0].bar(range(len(deciles)),deciles.pm25_mean_ugm3,yerr=deciles.pm25_std_ugm3,capsize=2);axes[0].set_xlabel('BLH decile (low → high)');axes[0].set_xticks(range(len(deciles)),range(1,len(deciles)+1));axes[0].set_ylabel('CAMS PM2.5 mean±SD µg/m³');axes[0].set_title('SD describes spread, not independent-sample CI')
    axes[1].scatter(residual.boundary_layer_height_m,residual.cams_pm25_ugm3,s=4,alpha=.3,rasterized=True);axes[1].set_xlabel('Daily BLH residual within year/month (m)');axes[1].set_ylabel('Daily CAMS PM2.5 residual (µg/m³)');axes[1].set_title('Within-year/month association remains noncausal')
    fig.suptitle('Released-data reproduction: BLH / PM₂.₅ association')
    _save_figure(fig,out,'blh_association',figure_dpi);plt.close(fig)


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--releaseCSV',type=Path,required=True);p.add_argument('--source-dir',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--figure-dpi',type=int,default=300);a=p.parse_args(argv);analyze(a.releaseCSV,a.source_dir,a.output,a.figure_dpi)
if __name__=='__main__':main()
