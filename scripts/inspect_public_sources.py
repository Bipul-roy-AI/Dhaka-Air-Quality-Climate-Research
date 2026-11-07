"""Normalize the EPA observed series and NASA embassy-period weather source.

This is a source-audit utility, not a replacement forecasting or validation run.
"""
import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile
import xml.etree.ElementTree as ET
import pandas as pd

EPA_SHA='87f2d78c8722c86ec000098819aa90fe19eb75902180a5b2667ea0f5dda0a5db'


def epa_daily(path):
    if hashlib.sha256(path.read_bytes()).hexdigest()!=EPA_SHA:
        raise ValueError('EPA workbook changed; re-inspect its caption and layout before extraction')
    ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    with ZipFile(path) as archive:
        # Pinned file: README is sheet1; data is sheet2. First two columns only
        # are observed PM2.5, not CMAQ or weather-normalized series.
        sheet=ET.fromstring(archive.read('xl/worksheets/sheet2.xml'))
        rows=[]
        for row in sheet.findall('s:sheetData/s:row',ns):
            if int(row.attrib['r'])<3:continue
            values={}
            for cell in row.findall('s:c',ns):
                col=''.join(x for x in cell.attrib['r'] if x.isalpha())
                value=cell.find('s:v',ns)
                if col in ('A','B') and value is not None:
                    if cell.attrib.get('t') in ('s','e') or cell.find('s:f',ns) is not None:
                        raise ValueError('Expected numeric observed EPA data')
                    values[col]=float(value.text)
            if not values:continue
            if set(values)!= {'A','B'}:raise ValueError('Incomplete EPA observation row')
            rows.append(values)
    data=pd.DataFrame(rows).rename(columns={'A':'day_index','B':'pm25_ugm3'})
    if not data.day_index.eq(data.day_index.round()).all() or not data.day_index.between(1,2192).all() or data.day_index.duplicated().any():
        raise ValueError('Unexpected EPA day index')
    data['date']=pd.Timestamp('2016-01-01')+pd.to_timedelta(data.day_index-1,unit='D')
    if len(data)!=2117 or not data.pm25_ugm3.ge(0).all():raise ValueError('Unexpected EPA values/count')
    return data


def power_daily(path):
    data=json.loads(path.read_text())
    if data['header']['time_standard']!='UTC':raise ValueError('POWER time standard must be explicit UTC')
    fields=data['properties']['parameter']
    units={'T2M':'C','T2MDEW':'C','RH2M':'%','WS10M':'m/s','PRECTOTCORR':'mm/day','PS':'kPa'}
    if set(fields)!=set(units):raise ValueError('Unexpected POWER fields')
    for field,unit in units.items():
        if data['parameters'][field]['units']!=unit:raise ValueError('Unexpected POWER units')
    frame=pd.DataFrame(fields).sort_index().replace(data['header']['fill_value'],float('nan'))
    frame.index=pd.to_datetime(frame.index,format='%Y%m%d');frame.index.name='date_utc'
    return frame,units


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sources',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():parser.error('Choose a new output directory')
    epa=epa_daily(args.sources/'Figure_1_data.xlsx')
    power,units=power_daily(args.sources/'nasa_power_embassy_2016_2021.json')
    expected=pd.date_range('2016-01-01','2021-12-31')
    if not power.index.equals(expected.rename('date_utc')):
        raise ValueError('Expected the complete 2016–2021 NASA daily calendar')
    args.output.mkdir(parents=True)
    full=pd.DataFrame({'date':pd.date_range('2016-01-01','2021-12-31')}).merge(epa,on='date',how='left',validate='one_to_one')
    full.to_csv(args.output/'epa_observed_daily_calendar.csv',index=False)
    power.to_csv(args.output/'nasa_power_embassy_daily_2016_2021.csv')
    manifest={'epa_doi':'10.23719/1528454','epa_observed_days':len(epa),'epa_missing_days':int(full.pm25_ugm3.isna().sum()),'epa_date_mapping':'Caption2016-01-01 to2021-12-31 with1-based day index; exact averaging timezone and daily QA rules unspecified','nasa_days':len(power),'nasa_original_units':units,'nasa_fill_counts':power.isna().sum().to_dict(),'nasa_source':'MERRA2/POWER; model-derived meteorology, not original ERA5 or independent monitor truth','no_legacy_data_replaced':True,'no_validation_or_retraining_performed':True,'epa_day_interval_aligned':False,'nasa_period':'2016-01-01 through2021-12-31'}
    (args.output/'inspection.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(manifest,indent=2))

if __name__=='__main__':main()
