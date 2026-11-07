"""Behavior tests for provenance-preserving aggregation, using synthetic fixtures."""
import hashlib
import tempfile
import unittest
from pathlib import Path
import zipfile

import numpy as np
import pandas as pd

from dhaka_air_quality.data import build_monthly


def fixture(start, periods):
    dates = pd.date_range(start, periods=periods, freq="h")
    return pd.DataFrame({"city_name": "Dhaka", "city_id": 1,
                         "datetime": dates.strftime("%Y-%m-%dT%H:%M"),
                         "pm2_5": 20., "pm10": 30., "carbon_monoxide": 100.,
                         "nitrogen_dioxide": 3., "sulphur_dioxide": 2.,
                         "ozone": 5., "aqi": 40.})


class DataTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.directory = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def run_frame(self, frame):
        path = self.directory / "archive.csv"
        frame.to_csv(path, index=False)
        before = path.read_bytes()
        result = build_monthly(path)
        self.assertEqual(path.read_bytes(), before)
        return result

    def test_complete_month_uses_unique_city_hours_not_duplicate_locations(self):
        dhaka = fixture("2022-09-01", 720)
        azimpur = dhaka.assign(city_name="Azimpur", city_id=2)
        monthly, audit = self.run_frame(pd.concat([dhaka, azimpur], ignore_index=True))
        self.assertEqual(len(monthly), 1)
        row = monthly.iloc[0]
        self.assertEqual(row.unique_hours, 720)
        self.assertEqual(row.expected_hours, 720)
        self.assertEqual(row.pm25_mean, 20)
        self.assertTrue(row.complete_month)
        self.assertTrue(row.primary_eligible)
        self.assertFalse(row.source_validated)
        self.assertEqual(row.source_regime, "later_unverified")
        self.assertEqual(audit["location_overlap"]["identical_all_available_pollutant_hours"], 720)
        self.assertEqual(audit["all_rows"], 1440)
        self.assertEqual(audit["selected_unique_hours"], 720)

    def test_exact_duplicates_removed_but_conflicts_rejected(self):
        data = fixture("2022-09-01", 2)
        monthly, audit = self.run_frame(pd.concat([data, data.iloc[[0]]]))
        self.assertEqual(audit["exact_duplicate_rows_removed"], 1)
        self.assertEqual(monthly.iloc[0].unique_hours, 2)
        conflict = data.iloc[[0]].assign(pm2_5=99)
        with self.assertRaisesRegex(ValueError, "Conflicting rows"):
            self.run_frame(pd.concat([data, conflict]))
        # Even equal concentrations with conflicting source/quality metadata must fail.
        conflict = data.iloc[[0]].assign(city_id=999)
        with self.assertRaisesRegex(ValueError, "Conflicting rows"):
            self.run_frame(pd.concat([data, conflict]))

    def test_missing_internal_month_is_explicit_without_imputed_target(self):
        data = pd.concat([fixture("2022-09-01", 1), fixture("2022-11-01", 1)])
        monthly, audit = self.run_frame(data)
        october = monthly.loc[monthly.date.eq("2022-10-01")].iloc[0]
        self.assertEqual(october.unique_hours, 0)
        self.assertTrue(pd.isna(october.pm25_mean))
        self.assertFalse(october.complete_month)
        self.assertFalse(october.primary_eligible)
        self.assertEqual(monthly.date.max(), "2022-11-01")
        self.assertEqual(monthly.target_imputed_by_pipeline.sum(), 0)
        self.assertGreater(audit["missing_hours_within_input_span"], 0)

    def test_partial_final_month_not_scored_or_extended(self):
        monthly, audit = self.run_frame(fixture("2025-11-01", 23 * 24))
        self.assertEqual(monthly.date.tolist(), ["2025-11-01"])
        row = monthly.iloc[0]
        self.assertEqual(row.unique_hours, 552)
        self.assertAlmostEqual(row.coverage_fraction, 23/30)
        self.assertFalse(row.primary_eligible)
        self.assertFalse(row.complete_month)
        self.assertTrue(audit["no_target_imputation"])

    def test_boundary_month_is_mixed_even_with_complete_coverage(self):
        monthly, _ = self.run_frame(fixture("2022-08-01", 744))
        row = monthly.iloc[0]
        self.assertTrue(row.complete_month)
        self.assertEqual(row.source_regime, "mixed")
        self.assertFalse(row.primary_eligible)
        earlier, _ = self.run_frame(fixture("2022-07-01", 744))
        self.assertEqual(earlier.iloc[0].source_regime, "earlier_unverified")
        self.assertFalse(earlier.iloc[0].primary_eligible)

    def test_nonphysical_or_missing_target_prevents_complete_month(self):
        frame = fixture("2022-09-01", 720)
        frame.loc[0, "pm2_5"] = -1
        frame.loc[1, "pm2_5"] = np.nan
        frame.loc[2, "pm2_5"] = np.inf
        monthly, audit = self.run_frame(frame)
        row = monthly.iloc[0]
        self.assertEqual(row.unique_hours, 720)
        self.assertEqual(row.valid_pm25_hours, 717)
        self.assertEqual(row.pm25_mean, 20)
        self.assertFalse(row.primary_eligible)
        self.assertFalse(row.complete_month)
        self.assertEqual(audit["negative_pm25_hours"], 1)
        self.assertEqual(audit["nonfinite_or_missing_pm25_hours"], 2)

    def test_mass_ordering_qc_prevents_primary_eligibility(self):
        frame = fixture("2022-09-01", 720)
        frame.loc[0, "pm2_5"] = 31
        monthly, audit = self.run_frame(frame)
        self.assertTrue(monthly.iloc[0].complete_month)
        self.assertEqual(monthly.iloc[0].pm25_gt_pm10_hours, 1)
        self.assertFalse(monthly.iloc[0].primary_eligible)
        self.assertEqual(audit["pm25_gt_pm10_hours"], 1)

    def test_invalid_nonhourly_and_timezone_timestamps_raise(self):
        for value in ["not a date", "2022-09-01T00:30", None, "2022-09-01T00:00+06:00"]:
            frame = fixture("2022-09-01", 1)
            frame.loc[0, "datetime"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.run_frame(frame)

    def test_zip_is_read_directly_with_hashes_and_no_extraction(self):
        path = self.directory / "original.zip"
        csv = fixture("2022-09-01", 2).to_csv(index=False).encode()
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("folder/AQI Bangladesh.csv", csv)
            archive.writestr("folder/cities.csv", "ID,Name\n1,Dhaka\n")
        before = set(self.directory.iterdir())
        monthly, audit = build_monthly(path)
        self.assertEqual(set(self.directory.iterdir()), before)
        self.assertEqual(audit["archive_member"], "folder/AQI Bangladesh.csv")
        self.assertEqual(audit["csv_sha256"], hashlib.sha256(csv).hexdigest())
        self.assertEqual(audit["input_sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertEqual(monthly.iloc[0].unique_hours, 2)

    def test_unsafe_or_ambiguous_zip_members_rejected(self):
        csv = fixture("2022-09-01", 1).to_csv(index=False)
        for names in [["../AQI Bangladesh.csv"], ["one.csv", "two.csv"]]:
            path = self.directory / "unsafe.zip"
            with zipfile.ZipFile(path, "w") as archive:
                for name in names:
                    archive.writestr(name, csv)
            with self.subTest(names=names), self.assertRaises(ValueError):
                build_monthly(path)
            self.assertFalse((self.directory.parent / "AQI Bangladesh.csv").exists())

    def test_exact_city_selection_and_required_columns(self):
        with self.assertRaisesRegex(ValueError, "No exact city_name"):
            self.run_frame(fixture("2022-09-01", 1).assign(city_name="Dhaka North"))
        with self.assertRaisesRegex(ValueError, "Missing required columns"):
            self.run_frame(fixture("2022-09-01", 1).drop(columns="pm2_5"))


if __name__ == "__main__":
    unittest.main()
