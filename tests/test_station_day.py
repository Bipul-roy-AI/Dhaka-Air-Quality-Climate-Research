from pathlib import Path
import importlib.util
import tempfile
from zipfile import ZipFile
import unittest
import numpy as np
import pandas as pd

spec=importlib.util.spec_from_file_location('station_day',Path(__file__).resolve().parents[1]/'scripts/inspect_station_day.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


def frame_for(times,values=None):
    times=pd.DatetimeIndex(times)
    return pd.DataFrame({'Date (LT)':times.strftime('%Y-%m-%d %I:%M %p'),'Raw Conc.':10 if values is None else values,'QC Name':'Valid','Conc. Unit':'UG/M3','Duration':'1 Hr'})

class StationDayTests(unittest.TestCase):
    def with_zip(self,frame,callback):
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)/'mirror.zip'
            with ZipFile(path,'w')as z:z.writestr(m.MEMBER,frame.to_csv(index=False))
            return callback(path)
    def test_exact_measurement_duplicates_removed_and_all_conflicts_excluded(self):
        d=frame_for(pd.date_range('2020-01-01',periods=24,freq='h'))
        # An exact duplicate does not add coverage. A conflicting hour is wholly lost.
        duplicate=d.iloc[[0]].copy();conflict=d.iloc[[1]].copy();conflict['Raw Conc.']=999
        hypotheses,qa=self.with_zip(pd.concat([d,duplicate,conflict]),m.mirror_daily)
        self.assertEqual(qa['duplicate_valid_timestamp_value_pairs_removed'],1)
        self.assertEqual(qa['conflicting_timestamp_count'],1)
        self.assertEqual(qa['conflicting_unique_measurement_rows_excluded'],2)
        self.assertEqual(qa['retained_unique_valid_hours'],23)
        self.assertEqual(hypotheses['local_labels'].iloc[0],10)
    def test_bad_quality_units_duration_values_do_not_contribute(self):
        d=frame_for(pd.date_range('2020-01-01',periods=24,freq='h'))
        d['Raw Conc.']=d['Raw Conc.'].astype(object)
        d.loc[0,'QC Name']='Missing';d.loc[1,'Conc. Unit']='MG/M3';d.loc[2,'Duration']='24 Hr';d.loc[3,'Raw Conc.']=-999;d.loc[4,'Raw Conc.']=np.inf;d.loc[5,'Raw Conc.']='bad'
        hypotheses,qa=self.with_zip(d,m.mirror_daily)
        self.assertEqual(qa['retained_unique_valid_hours'],18)
        self.assertEqual(hypotheses['local_labels'].iloc[0],10)
        d.loc[6,'QC Name']='Invalid'
        hypotheses,_=self.with_zip(d,m.mirror_daily)
        self.assertTrue(pd.isna(hypotheses['local_labels'].iloc[0]))
    def test_midnight_hour_ending_shift_changes_coverage_without_imputation(self):
        times=pd.date_range('2020-01-01 07:00',periods=18,freq='h')
        h,_=self.with_zip(frame_for(times),m.mirror_daily)
        self.assertTrue(pd.isna(h['local_labels'].loc['2020-01-01'])) #17hours before midnight.
        self.assertEqual(h['local_hour_ending'].loc['2020-01-01'],10) #18hour intervals.
        self.assertEqual(h['UTC_labels'].loc['2020-01-01'],10)
        self.assertEqual(set(h),{x[0]for x in m.CONVENTIONS})
    def test_daily_calendar_retains_missing_days_and_rejects_duplicate_or_bad_values(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'epa.csv';pd.DataFrame({'date':['2020-01-01','2020-01-03'],'pm25_ugm3':[10,20]}).to_csv(p,index=False)
            s=m.load_epa_daily(p);self.assertEqual(len(s),3);self.assertTrue(pd.isna(s.iloc[1]))
            pd.DataFrame({'date':['2020-01-01','2020-01-01'],'pm25_ugm3':[10,20]}).to_csv(p,index=False)
            with self.assertRaisesRegex(ValueError,'unique'):m.load_epa_daily(p)
            pd.DataFrame({'date':['2020-01-01'],'pm25_ugm3':[-1]}).to_csv(p,index=False)
            with self.assertRaisesRegex(ValueError,'nonnegative'):m.load_epa_daily(p)
    def test_matching_uses_absolute_epsilon_not_default_relative_tolerance(self):
        dates=pd.date_range('2020-01-01',periods=3,freq='D')
        a=pd.Series([1000,1000,1000],index=dates);b=pd.Series([1000.00001,1000.005,np.nan],index=dates)
        metrics=m.station_day_metrics(a,b)
        self.assertEqual(metrics['n_pairs'],2);self.assertEqual(metrics['matching_daily_means_at_1e_4'],1)
        self.assertGreater(metrics['bias_mirror_minus_epa'],0)
        self.assertAlmostEqual(metrics['RMSE'],np.sqrt((.00001**2+.005**2)/2),places=10)
    def test_missing_or_ambiguous_named_member_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'other.zip'
            with ZipFile(p,'w')as z:z.writestr('other.csv','x\n1\n')
            with self.assertRaisesRegex(ValueError,'unambiguous'):m.mirror_daily(p)

if __name__=='__main__':unittest.main()
