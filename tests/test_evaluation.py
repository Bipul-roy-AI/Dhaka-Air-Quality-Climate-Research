"""Behavioral checks for information timing and comparable monthly evaluation."""

import json
import unittest

import numpy as np
import pandas as pd

from dhaka_air_quality.evaluation import evaluate_monthly


def example_months(n=40):
    dates = pd.date_range("2022-09-01", periods=n, freq="MS")
    index = np.arange(n, dtype=float)
    return pd.DataFrame({
        "date": dates.strftime("%Y-%m-%d"),
        "pm25_mean": 40 + 12 * np.cos(2 * np.pi * dates.month / 12) + index / 5,
        "complete_month": True, "primary_eligible": True,
        "source_regime": "later_unverified", "ground_pollution_imputed": 0,
        "temperature": 25 + 5 * np.sin(index / 5),
        "rainfall_mm": 4 + np.cos(index),
    })


class MonthlyEvaluationTests(unittest.TestCase):
    def test_expanding_training_boundaries_and_serializable_audit(self):
        predictions, metrics, audit = evaluate_monthly(example_months(38))
        self.assertEqual(audit["eligible_months"], 38)
        self.assertEqual(audit["scored_forecast_months"], 14)
        self.assertTrue((predictions.train_end < predictions.date).all())
        self.assertTrue((predictions.n_train >= 24).all())
        self.assertFalse(audit["global_anomaly_columns_used"])
        self.assertFalse(audit["operational_forecast_validated"])
        self.assertEqual(set(metrics.sample_set), {"available_cases", "common_cases"})
        json.dumps(audit, allow_nan=False)

    def test_future_targets_and_weather_cannot_change_earlier_predictions(self):
        data = example_months()
        baseline, _, _ = evaluate_monthly(data)
        changed = data.copy()
        cutoff = "2025-01-01"
        future = changed.date > cutoff
        changed.loc[future, "pm25_mean"] += 10000
        changed.loc[future, "temperature"] -= 5000
        changed.loc[future, "rainfall_mm"] += 10000
        # The current month's weather is also unavailable to that month.
        changed.loc[changed.date.eq(cutoff), "temperature"] = -99999
        actual, _, _ = evaluate_monthly(changed)
        pd.testing.assert_frame_equal(
            baseline.loc[baseline.date <= cutoff].reset_index(drop=True),
            actual.loc[actual.date <= cutoff].reset_index(drop=True),
        )

    def test_same_month_satellite_and_global_anomalies_are_not_features(self):
        data = example_months()
        expected, _, _ = evaluate_monthly(data)
        data["temperature_anomaly"] = np.arange(len(data)) * 999999
        data["NO2"] = data.pm25_mean * 100
        data["AOD"] = data.pm25_mean
        actual, _, audit = evaluate_monthly(data)
        pd.testing.assert_frame_equal(expected, actual)
        self.assertTrue(all("NO2" not in values for values in audit["features"].values()))

    def test_calendar_gaps_are_not_previous_rows_and_common_cases_match(self):
        data = example_months(40)
        missing_month = data.loc[25, "date"]
        following_month = data.loc[26, "date"]
        data = data.drop(index=25)
        predictions, metrics, audit = evaluate_monthly(data)
        persistence = predictions.loc[predictions.model.eq("persistence")].set_index("date")
        self.assertNotIn(missing_month, persistence.index)
        self.assertTrue(pd.isna(persistence.loc[following_month, "predicted_pm25"]))
        seasonal = predictions.loc[predictions.model.eq("seasonal_naive")].set_index("date")
        missing_year_later = (pd.Timestamp(missing_month) + pd.DateOffset(years=1)).strftime("%Y-%m-%d")
        self.assertTrue(pd.isna(seasonal.loc[missing_year_later, "predicted_pm25"]))
        common = metrics.loc[metrics.sample_set.eq("common_cases")]
        self.assertEqual(common.n.nunique(), 1)
        self.assertLess(common.n.iloc[0], metrics.loc[metrics.model.eq("ridge_lags_calendar") & metrics.sample_set.eq("available_cases"), "n"].iloc[0])
        self.assertEqual(audit["calendar_months"], 40)
        self.assertEqual(audit["input_months"], 39)

    def test_disallowed_targets_and_lags_are_excluded(self):
        data = example_months(40)
        data.loc[25, "complete_month"] = False
        data.loc[27, "ground_pollution_imputed"] = 1
        data.loc[29, "source_regime"] = "mixed"
        data.loc[31, "source_regime"] = "earlier_unverified"
        data.loc[33, "primary_eligible"] = False
        data.loc[35, "pm25_mean"] = np.nan
        data.loc[37, "pm25_mean"] = -5
        excluded = set(data.loc[[25, 27, 29, 31, 33, 35, 37], "date"])
        predictions, _, audit = evaluate_monthly(data, min_train_months=12)
        self.assertTrue(excluded.isdisjoint(predictions.date))
        self.assertEqual(audit["eligible_months"], 33)
        persistence = predictions.loc[predictions.model.eq("persistence")].set_index("date")
        for previous in [25, 27, 29, 31, 33, 35, 37]:
            next_date = data.loc[previous + 1, "date"]
            self.assertTrue(pd.isna(persistence.loc[next_date, "predicted_pm25"]))

    def test_unavailable_baseline_is_missing_not_replaced_by_imputed_target(self):
        predictions, metrics, _ = evaluate_monthly(example_months(10), min_train_months=2)
        seasonal = predictions.loc[predictions.model.eq("seasonal_naive"), "predicted_pm25"]
        self.assertTrue(seasonal.isna().all())
        self.assertTrue(metrics.loc[metrics.sample_set.eq("common_cases"), "n"].eq(0).all())

    def test_csv_boolean_strings_do_not_treat_false_as_true(self):
        data = example_months(38)
        data["complete_month"] = "True"
        data["primary_eligible"] = "True"
        data.loc[25, "complete_month"] = "False"
        predictions, _, audit = evaluate_monthly(data)
        self.assertEqual(audit["eligible_months"], 37)
        self.assertNotIn(data.loc[25, "date"], set(predictions.date))

    def test_duplicate_months_raise_and_short_series_returns_empty_outputs(self):
        data = example_months(10)
        with self.assertRaisesRegex(ValueError, "duplicate calendar months"):
            evaluate_monthly(pd.concat([data, data.iloc[[0]]]))
        predictions, metrics, audit = evaluate_monthly(data)
        self.assertTrue(predictions.empty)
        self.assertTrue(metrics.empty)
        self.assertEqual(audit["scored_forecast_months"], 0)


if __name__ == "__main__":
    unittest.main()
