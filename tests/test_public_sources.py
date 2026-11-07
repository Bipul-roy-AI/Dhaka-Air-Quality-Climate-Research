"""Scientific input checks for optional public-source inspection utilities."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

path=Path(__file__).resolve().parents[1]/'scripts/inspect_public_sources.py'
spec=importlib.util.spec_from_file_location('public_inspection',path)
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)

class PublicSourceTests(unittest.TestCase):
    def sample(self):
        units={'T2M':'C','T2MDEW':'C','RH2M':'%','WS10M':'m/s','PRECTOTCORR':'mm/day','PS':'kPa'}
        return {'header':{'time_standard':'UTC','fill_value':-999},'parameters':{k:{'units':v} for k,v in units.items()},'properties':{'parameter':{k:{'20220101':1,'20220102':-999} for k in units}}}
    def test_native_units_and_missing_days_are_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'power.json';p.write_text(json.dumps(self.sample()))
            frame,units=mod.power_daily(p)
            self.assertEqual(len(frame),2)
            self.assertTrue(frame.iloc[1].isna().all())
            self.assertEqual(units['PRECTOTCORR'],'mm/day')
            self.assertEqual(frame.PS.iloc[0],1)  # No implicit kPa-to-Pa conversion.
    def test_wrong_units_and_timezone_fail_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'power.json';data=self.sample();data['parameters']['PS']['units']='Pa';p.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,'units'):mod.power_daily(p)
            data=self.sample();data['header']['time_standard']='LST';p.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,'UTC'):mod.power_daily(p)
    def test_changed_epa_workbook_requires_reinspection(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'epa.xlsx';p.write_bytes(b'changed source')
            with self.assertRaisesRegex(ValueError,'changed'):mod.epa_daily(p)

if __name__=='__main__':unittest.main()
