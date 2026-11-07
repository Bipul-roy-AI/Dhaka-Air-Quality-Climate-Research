"""Coordinate-order and distance checks for the scientific location map."""
import importlib.util
from pathlib import Path
import unittest

import numpy as np

spec = importlib.util.spec_from_file_location('study_map', Path(__file__).resolve().parents[1] / 'scripts/make_study_area_map.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class MapCoordinateTests(unittest.TestCase):
    def test_reported_locations_round_trip_in_explicit_lon_lat_order(self):
        lon, lat = np.array([90.4, 90.424614]), np.array([23.8, 23.796374])
        x, y = mod.project(lon, lat)
        result_lon, result_lat = mod.INVERSE.transform(x, y)
        np.testing.assert_allclose(result_lon, lon, atol=1e-9, rtol=0)
        np.testing.assert_allclose(result_lat, lat, atol=1e-9, rtol=0)
        self.assertGreater(x[1], x[0])

    def test_swapped_or_nonfinite_coordinates_are_rejected(self):
        with self.assertRaises(ValueError):
            mod.project(23.8, 90.4)
        with self.assertRaises(ValueError):
            mod.project(90.4, float('nan'))

    def test_local_projected_kilometre_agrees_with_wgs84_geodesic(self):
        lon, lat = 90.4, 23.8
        east_lon, east_lat, _ = mod.GEOD.fwd(lon, lat, 90, 1000)
        x0, y0 = mod.project(lon, lat)
        x1, y1 = mod.project(east_lon, east_lat)
        self.assertAlmostEqual(float(np.hypot(x1-x0, y1-y0)), 1000, delta=1)


if __name__ == '__main__':
    unittest.main()
