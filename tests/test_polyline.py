"""Physical and sampling regressions for receiver waypoint routes."""
from copy import deepcopy
import math
import unittest

import numpy as np

from indoor_gnss.config import DEFAULT, validate
from indoor_gnss.engine import Model
from indoor_gnss.geometry import LAMBDA_L1, Trajectory


def polyline_config():
    cfg = deepcopy(DEFAULT)
    cfg["trajectory"].update(
        start_enu_m=[0, 5, 1],
        waypoints_enu_m=[[1.25, 5, 1], [1.25, 6.75, 1]],
        end_enu_m=[1.25, 6.75, 3],
        start_time_s=0.0625,
        speed_mps=4,
        acceleration_time_s=0.125,
    )
    cfg["time"].update(observation_interval_s=0.09, trajectory_distance_step_m=2)
    cfg["receiver_clock"].update(bias_s=0, drift_sps=0)
    cfg["observations"]["add_noise"] = False
    cfg["iq"]["enabled"] = False
    return cfg


class PolylineTests(unittest.TestCase):
    def test_arc_length_timing_and_velocity_follow_segments(self):
        cfg = polyline_config()
        validate(cfg)
        route = Trajectory(cfg["trajectory"])
        self.assertAlmostEqual(route.length, 5)
        self.assertAlmostEqual(route.move_duration, 1.375)

        expected = [
            (0.0, [0, 5, 1], [0, 0, 0]),                     # Before departure.
            (0.125, [0.0625, 5, 1], [2, 0, 0]),              # Accelerating.
            (0.375, [1, 5, 1], [4, 0, 0]),
            (0.4375, [1.25, 5, 1], [0, 4, 0]),               # First corner.
            (0.625, [1.25, 5.75, 1], [0, 4, 0]),
            (0.875, [1.25, 6.75, 1], [0, 0, 4]),             # Second corner.
            (0.9375, [1.25, 6.75, 1.25], [0, 0, 4]),
            (1.375, [1.25, 6.75, 2.9375], [0, 0, 2]),        # Braking.
            (1.5, [1.25, 6.75, 3], [0, 0, 0]),               # At rest.
        ]
        for time_s, position, velocity in expected:
            with self.subTest(time_s=time_s):
                actual_position, actual_velocity = route.at(time_s)
                np.testing.assert_allclose(actual_position, position, atol=1e-12)
                np.testing.assert_allclose(actual_velocity, velocity, atol=1e-12)
        self.assertAlmostEqual(route.at_distance(2), 0.625)

    def test_generate_samples_corners_outside_the_regular_grids(self):
        cfg = polyline_config()
        validate(cfg)
        model = Model(cfg)
        series, rows, truth = model.generate()
        truth_by_time = {point["time_s"]: point for point in truth}
        for time_s, position in [(0.4375, [1.25, 5, 1]), (0.875, [1.25, 6.75, 1])]:
            with self.subTest(time_s=time_s):
                np.testing.assert_allclose(
                    [truth_by_time[time_s][axis] for axis in ("x_m", "y_m", "z_m")],
                    position,
                    atol=1e-12,
                )
                self.assertIn(time_s, series["t_s"])
                corner_rows = [row for row in rows if row["time_s"] == time_s]
                self.assertEqual(len(corner_rows), len(model.prns))
                for row in corner_rows:
                    self.assertTrue(math.isfinite(row["doppler_truth_hz"]))
                    self.assertAlmostEqual(
                        row["doppler_truth_hz"] * LAMBDA_L1,
                        -row["carrier_range_rate_mps"],
                    )

    def test_return_to_start_is_allowed(self):
        cfg = polyline_config()
        cfg["trajectory"].update(waypoints_enu_m=[[2, 5, 1]], end_enu_m=[0, 5, 1])
        validate(cfg)
        route = Trajectory(cfg["trajectory"])
        self.assertAlmostEqual(route.length, 4)
        position, velocity = route.at(0.75)
        np.testing.assert_allclose(position, [1.5, 5, 1])
        np.testing.assert_allclose(velocity, [-4, 0, 0])
        np.testing.assert_allclose(route.at(1.5)[0], [0, 5, 1])

    def test_invalid_waypoints_are_rejected(self):
        cases = [
            None,
            [1.25, 5, 1],
            [[1.25, 5]],
            [["1.25", 5, 1]],
            [[True, 5, 1]],
            [[1.25, 5, float("nan")]],
            [[1.25, 11, 1]],               # Outside the room.
            [[0, 5, 1]],                   # Repeats the start.
            [[1.25, 5, 1], [1.25, 5, 1]],   # Repeats the previous waypoint.
            [[1.25, 6.75, 3]],             # Repeats the end.
        ]
        for waypoints in cases:
            with self.subTest(waypoints=waypoints):
                cfg = polyline_config()
                cfg["trajectory"]["waypoints_enu_m"] = waypoints
                with self.assertRaises(ValueError):
                    validate(cfg)

    def test_config_guards_use_total_distance(self):
        cfg = polyline_config()
        # The direct endpoint distance fits these limits, but the longer
        # route through the intermediate points does not.
        cfg["time"]["duration_s"] = 0.95
        with self.assertRaisesRegex(ValueError, "simulation duration"):
            validate(cfg)
        cfg["time"].update(duration_s=2, trajectory_distance_step_m=0.000024)
        with self.assertRaisesRegex(ValueError, "epoch count"):
            validate(cfg)


if __name__ == "__main__":
    unittest.main()
