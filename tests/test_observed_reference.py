import importlib.util
from pathlib import Path
import tempfile
import unittest

import numpy as np
import pandas as pd

_SPEC=importlib.util.spec_from_file_location("observed_analysis",Path(__file__).parents[1]/"scripts/analyze_observed_reference.py")
a=importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(a)


class ObservedReferenceTests(unittest.TestCase):
    def test_coverage_and_threshold_use_observed_denominator(self):
        values=pd.Series([15.,16.,np.nan,30.],index=pd.date_range("2020-01-01",periods=4))
        result=a.summarize(values)
        self.assertEqual(result["calendar_days"],4)
        self.assertEqual(result["observed_days"],3)
        self.assertEqual(result["days_gt_15"],2)
        self.assertAlmostEqual(result["fraction_observed_gt_15"],2/3)
        self.assertEqual(result["missing_days"],1)

    def test_missing_calendar_days_and_nan_break_episodes(self):
        # Both an absent row and an explicit unknown must break a spell.
        values=pd.Series([21.,22.,25.,np.nan,26.,20.],index=pd.to_datetime(["2020-01-01","2020-01-02","2020-01-04","2020-01-05","2020-01-06","2020-01-07"]))
        episodes=a.find_episodes(values,20.)
        self.assertEqual(episodes.duration_days.tolist(),[2,1,1])
        self.assertEqual(episodes.start_date.tolist(),["2020-01-01","2020-01-04","2020-01-06"])
        self.assertEqual(episodes.sum_excess_ug_day_m3.tolist(),[3.,5.,6.])
        self.assertEqual(episodes.iloc[-1].end_date,"2020-01-06")

    def test_all_below_or_equal_threshold_yields_no_episode(self):
        values=pd.Series([20.,19.,np.nan],index=pd.date_range("2020-01-01",periods=3))
        self.assertTrue(a.find_episodes(values,20.).empty)

    def test_monthly_denominator_is_full_calendar_including_leap_day(self):
        values=pd.Series(20.,index=pd.date_range("2020-02-01",periods=22))
        targets=a.monthly_targets(values)
        self.assertEqual(targets.iloc[0].calendar_days,29)
        self.assertAlmostEqual(targets.iloc[0].coverage_fraction,22/29)
        self.assertTrue(targets.iloc[0].eligible)
        values.iloc[-1]=np.nan
        targets=a.monthly_targets(values)
        self.assertFalse(targets.iloc[0].eligible)
        self.assertTrue(pd.isna(targets.iloc[0].season_adjusted_ugm3))

    def test_six_season_boundaries_are_paper_definition_not_equal_bins(self):
        examples={"2020-02-15":"Winter","2020-02-16":"Spring","2020-04-15":"Spring","2020-04-16":"Summer",
                  "2020-06-15":"Summer","2020-06-16":"Monsoon","2020-10-15":"Monsoon","2020-10-16":"Autumn",
                  "2020-11-15":"Autumn","2020-11-16":"Late_autumn","2020-12-15":"Late_autumn","2020-12-16":"Winter"}
        for date,expected in examples.items():
            with self.subTest(date=date):self.assertEqual(a.six_season(pd.Timestamp(date)),expected)
        self.assertEqual(a.four_season(pd.Timestamp("2020-09-01")),"Monsoon_JJAS")
        self.assertEqual(a.four_season(pd.Timestamp("2020-11-01")),"Post_monsoon_ON")

    def test_load_daily_keeps_gaps_unknown_and_rejects_conflicts(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"source.csv"
            pd.DataFrame({"date":["2020-01-01","2020-01-03"],"pm25_ugm3":[20.,30.]}).to_csv(path,index=False)
            series=a.load_daily(path)
            self.assertEqual(len(series),3)
            self.assertTrue(pd.isna(series.iloc[1]))
            pd.DataFrame({"date":["2020-01-01","2020-01-01"],"pm25_ugm3":[20.,30.]}).to_csv(path,index=False)
            with self.assertRaises(ValueError):a.load_daily(path)
            pd.DataFrame({"date":["2020-01-01"],"pm25_ugm3":[-99.]}).to_csv(path,index=False)
            with self.assertRaises(ValueError):a.load_daily(path)

    def test_block_bootstrap_respects_calendar_gaps_and_reproducibility(self):
        index=pd.date_range("2016-01-01",periods=36,freq="MS")
        values=pd.Series(np.arange(36)/12,index=index)
        values.iloc[18]=np.nan
        monthly=pd.DataFrame({"season_adjusted_ugm3":values})
        result=a.trend_with_block_bootstrap(monthly,12,replicates=25,seed=4)
        self.assertEqual(result["eligible_months"],35)
        # Starts0..6 before the gap and19..24 after:13 complete blocks.
        self.assertEqual(result["candidate_contiguous_blocks"],13)
        self.assertAlmostEqual(result["slope_ugm3_per_year"],1.)
        self.assertEqual(result,a.trend_with_block_bootstrap(monthly,12,25,seed=4))
        self.assertAlmostEqual(result["ci95_low"],1.)
        self.assertAlmostEqual(result["ci95_high"],1.)

    def test_output_directory_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"input.csv"
            dates=pd.date_range("2016-01-01","2018-12-31")
            pd.DataFrame({"date":dates,"pm25_ugm3":20.+np.sin(np.arange(len(dates)))}).to_csv(path,index=False)
            output=Path(directory)/"existing";output.mkdir()
            marker=output/"user.txt";marker.write_text("keep")
            with self.assertRaises(FileExistsError):a.run(path,output,replicates=2)
            self.assertEqual(marker.read_text(),"keep")
            self.assertEqual(list(output.iterdir()),[marker])


if __name__=="__main__":unittest.main()
