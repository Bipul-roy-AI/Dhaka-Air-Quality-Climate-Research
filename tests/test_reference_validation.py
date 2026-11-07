import importlib.util
from pathlib import Path
import unittest
import numpy as np
import pandas as pd
spec=importlib.util.spec_from_file_location('reference_validation',Path(__file__).resolve().parents[1]/'scripts/validate_hyaqmet_reference.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
class ReferenceTests(unittest.TestCase):
    def test_daily_coverage_and_timezone_are_explicit(self):
        frame=pd.DataFrame({'ts':pd.date_range('2017-01-01',periods=24,freq='h'),'cams_pm25_ugm3':10})
        local=mod.model_daily(frame,'BST');utc=mod.model_daily(frame,'UTC')
        self.assertEqual(local.model.iloc[0],10)
        self.assertTrue(pd.isna(utc.model.iloc[0])) # Six-hour partial preceding UTC day.
        self.assertEqual(utc.model.iloc[1],10)
    def test_matched_monthly_means_use_same_days_and_threshold(self):
        t=pd.date_range('2020-01-01',periods=31);d=pd.DataFrame({'observed':1.,'model':2.},index=t);d.loc[t[:10],'observed']=np.nan
        result=mod.monthly_common_pairs(d)
        self.assertEqual(result.matched_days.iloc[0],21);self.assertFalse(result.eligible.iloc[0]);self.assertEqual(result.model.iloc[0],2)
    def test_bias_direction_and_block_sampling_missing_days(self):
        t=pd.date_range('2020-01-01',periods=60);d=pd.DataFrame({'observed':np.arange(60,dtype=float),'model':np.arange(60,dtype=float)+3},index=t);d.iloc[10:20,0]=np.nan
        m=mod.metrics(d);self.assertEqual(m['n'],50);self.assertEqual(m['bias'],3)
        ci=mod.block_uncertainty(d,7,20);self.assertAlmostEqual(ci['bias']['lower'],3)
if __name__=='__main__':unittest.main()
