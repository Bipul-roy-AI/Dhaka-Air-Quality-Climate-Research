import tempfile
import unittest
from pathlib import Path
import pandas as pd
from dhaka_air_quality.climate import join_climate

class ClimateTests(unittest.TestCase):
    def test_sentinels_flags_and_target_protection(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/"climate.csv"
            pd.DataFrame({"date":["2024-01","2024-02"], "AOD":[-999,.7],"AOD_available":[1,0],"temperature":[20,float("inf")],"pm25_mean":[999,999],"temperature_anomaly":[100,100]}).to_csv(p,index=False)
            result,audit=join_climate(pd.DataFrame({"date":["2024-01-01","2024-02-01"],"pm25_mean":[10,11]}),p)
            self.assertEqual(result.pm25_mean.tolist(),[10,11])
            self.assertTrue(result.AOD.isna().all())
            self.assertNotIn("temperature_anomaly",result)
            self.assertFalse(audit["archived_anomalies_used"])
            self.assertEqual(audit["present_months"]["temperature"],1)
            self.assertTrue(pd.isna(result.temperature.iloc[1]))
    def test_duplicate_month_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/"climate.csv"
            pd.DataFrame({"date":["2024-01-01","2024-01-15"],"temperature":[20,21]}).to_csv(p,index=False)
            with self.assertRaisesRegex(ValueError,"Duplicate climate month"):
                join_climate(pd.DataFrame({"date":["2024-01-01"]}),p)

if __name__=="__main__":unittest.main()
