import importlib.util
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

SPEC = importlib.util.spec_from_file_location('observed_weather', Path(__file__).resolve().parents[1]/'scripts/analyze_observed_weather.py')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def fixture(end='2019-03-31'):
    dates = pd.date_range('2016-01-01', end, freq='D')
    t = np.arange(len(dates))
    frame = pd.DataFrame(index=dates)
    frame['pm25_ugm3'] = 50 + 10*np.cos(t/25) + t*.001
    for i, column in enumerate(MODULE.WEATHER): frame[column] = 10 + i + np.sin(t/(8+i))
    return frame


class ObservedWeatherTests(unittest.TestCase):
    def test_calendar_gap_does_not_become_previous_observation(self):
        frame = fixture('2018-03-31').drop(pd.Timestamp('2018-02-14'))
        features = MODULE.features_for_prediction(frame)
        self.assertTrue(pd.isna(features.loc['2018-02-15', 'pm25_lag_1']))
        self.assertTrue(pd.isna(features.loc['2018-02-15', 'T2M_lag_1']))
        predictions = MODULE.predict_daily(frame)
        selected = predictions[predictions.date.eq('2018-02-15') & predictions.model.eq('persistence')]
        self.assertTrue(selected.prediction.isna().all())
        metrics = MODULE.metric_table(predictions)
        common = metrics[metrics.period.eq('2018') & metrics.sample_set.eq('common_cases')]
        self.assertEqual(common.n.nunique(), 1)

    def test_future_and_same_day_inputs_do_not_change_earlier_hindcasts(self):
        frame = fixture('2018-04-30')
        expected = MODULE.predict_daily(frame)
        changed = frame.copy()
        changed.loc[changed.index > '2018-02-15', 'pm25_ugm3'] += 1000
        changed.loc[changed.index >= '2018-02-15', MODULE.WEATHER] += 10000
        actual = MODULE.predict_daily(changed)
        pd.testing.assert_frame_equal(expected[expected.date <= '2018-02-15'].reset_index(drop=True),
                                      actual[actual.date <= '2018-02-15'].reset_index(drop=True))
        self.assertTrue((expected.training_end < expected.refit_date).all())
        self.assertTrue((expected.nominal_issue_date < expected.date).all())

    def test_missing_targets_never_imputed_or_scored(self):
        frame = fixture('2018-03-31')
        frame.loc['2018-02-02', 'pm25_ugm3'] = np.nan
        predictions = MODULE.predict_daily(frame)
        self.assertNotIn('2018-02-02', set(predictions.date))
        self.assertFalse(predictions.observed.isna().any())
        self.assertEqual(set(predictions.model), {'persistence', 'seasonal_naive_365', 'calendar_month_climatology',
                                                'ridge_calendar_lags', 'ridge_calendar_lags_weather', 'ridge_calendar_lags_weather_safe2'})

    def test_prediction_requires_two_calendar_years(self):
        frame = fixture('2017-12-31')
        self.assertTrue(MODULE.predict_daily(frame, first_prediction='2017-01-01').empty)

    def test_bootstrap_uses_paired_losses_and_reports_all_block_lengths(self):
        dates = pd.date_range('2018-01-01', '2019-12-31', freq='D')
        rows = []
        for date in dates:
            observed = 40 + date.day
            for model, error in [('ridge_calendar_lags', 1), ('ridge_calendar_lags_weather', 2)]:
                rows.append(dict(date=date.strftime('%Y-%m-%d'), model=model, observed=observed, prediction=observed+error))
        output = MODULE.weather_benefit_bootstrap(pd.DataFrame(rows), repetitions=20)
        self.assertEqual(set(output.block_days), {7, 30})
        self.assertTrue(np.allclose(output.weather_minus_core, 1))
        self.assertTrue(np.allclose(output.ci95_lower, 1))
        self.assertTrue(np.allclose(output.ci95_upper, 1))

    def test_safe2_daily_interval_ends_before_midnight_bst_issue(self):
        lag1 = MODULE.weather_interval_timing('2020-01-02', 1)
        lag2 = MODULE.weather_interval_timing('2020-01-02', 2)
        self.assertEqual(lag1['hours_after_issue'], 6)
        self.assertEqual(lag2['hours_after_issue'], 0)
        self.assertLess(pd.Timestamp(lag2['source_interval_end_utc']), pd.Timestamp(lag2['nominal_issue_bst']))

    def test_primary_safe2_ignores_weather_interval_overlapping_issue(self):
        frame = fixture('2018-04-30')
        expected = MODULE.predict_daily(frame)
        changed = frame.copy()
        changed.loc[changed.index >= '2018-02-14', MODULE.WEATHER] += 10000
        actual = MODULE.predict_daily(changed)
        mask = expected.date.le('2018-02-15') & expected.model.eq('ridge_calendar_lags_weather_safe2')
        pd.testing.assert_frame_equal(expected[mask].reset_index(drop=True), actual[mask].reset_index(drop=True))
        unsafe = actual[actual.date.eq('2018-02-15') & actual.model.eq('ridge_calendar_lags_weather')]
        self.assertTrue(unsafe.evaluation.eq('overlapping_day_conditional_benchmark').all())
        self.assertFalse(unsafe.primary_weather_branch.any())
        safe = actual[actual.model.eq('ridge_calendar_lags_weather_safe2')]
        self.assertTrue(safe.weather_lag_days.eq(2).all())
        self.assertTrue(safe.primary_weather_branch.all())

    def test_weather_date_shift_semantics(self):
        frame = fixture('2016-01-10')
        pair = MODULE.aligned_pair(frame, 'T2M', alignment_shift_days=1, weather_lag_days=0)
        self.assertEqual(pair.loc['2016-01-03', 'T2M'], frame.loc['2016-01-04', 'T2M'])
        lagged = MODULE.aligned_pair(frame, 'T2M', alignment_shift_days=0, weather_lag_days=1)
        self.assertEqual(lagged.loc['2016-01-03', 'T2M'], frame.loc['2016-01-02', 'T2M'])

    def test_month_adjustment_removes_calendar_fixed_effects(self):
        frame = fixture('2018-12-31')
        pair = frame[['pm25_ugm3','T2M']].copy()
        residual = MODULE.adjusted_residuals(pair, 'calendar_month')
        self.assertTrue(np.allclose(residual.groupby(residual.index.month).mean(), 0, atol=1e-10))
        residual = MODULE.adjusted_residuals(pair, 'year_and_calendar_month')
        self.assertTrue(np.allclose(residual.groupby(residual.index.year).mean(), 0, atol=1e-10))

    def test_load_preserves_missing_dates_rejects_duplicates_and_sentinels(self):
        frame = fixture('2016-01-05')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            e = frame[['pm25_ugm3']].drop(index=frame.index[2]).rename_axis('date').reset_index()
            w = frame[MODULE.WEATHER].rename_axis('date_utc').reset_index()
            w.loc[1,'PRECTOTCORR'] = -999
            e.to_csv(root/'epa.csv', index=False); w.to_csv(root/'weather.csv', index=False)
            result = MODULE.load_daily(root/'epa.csv',root/'weather.csv')
            self.assertTrue(pd.isna(result.loc['2016-01-03','pm25_ugm3']))
            self.assertTrue(pd.isna(result.loc['2016-01-02','PRECTOTCORR']))
            pd.concat([e,e.iloc[[0]]]).to_csv(root/'epa.csv', index=False)
            with self.assertRaisesRegex(ValueError, 'unique'):
                MODULE.load_daily(root/'epa.csv',root/'weather.csv')


if __name__ == '__main__': unittest.main()
