"""Physical invariants and receiver baseline checks, independent of waveform rendering."""
from copy import deepcopy
import json
import math
from pathlib import Path
import tempfile
import unittest
import numpy as np

from indoor_gnss.config import DEFAULT, COMP, validate, load
from indoor_gnss.engine import Model
from indoor_gnss.geometry import LAMBDA_L1, specular_image, Trajectory
from indoor_gnss.physics import compensation, atmosphere
from indoor_gnss.solver import solve


def baseline(mode="direct", noise=False):
    cfg = deepcopy(DEFAULT)
    cfg["propagation"]["mode"] = mode
    cfg["observations"]["add_noise"] = noise
    cfg["receiver_clock"]["bias_s"] = 0
    cfg["receiver_clock"]["drift_sps"] = 0
    cfg["atmosphere"]["enabled"] = False
    cfg["iq"]["enabled"] = False
    cfg["time"]["duration_s"] = 0.4
    cfg["time"]["observation_interval_s"] = 0.05
    cfg["trajectory"]["start_time_s"] = 0.05
    cfg["trajectory"]["end_enu_m"] = [3, 5, 1]
    cfg["trajectory"]["acceleration_time_s"] = 0.02
    validate(cfg)
    return cfg


class PhysicsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = baseline()
        cls.model = Model(cls.cfg)
        cls.series, cls.rows, cls.truth = cls.model.generate()
        cls.solutions, cls.metrics = solve(cls.model, cls.rows, cls.truth)

    def test_direct_noise_free_position_velocity_recovery(self):
        self.assertEqual(self.metrics["convergence_fraction"], 1.0)
        self.assertLess(self.metrics["position_error_m"]["max"], 1e-3)
        # At the short acceleration ramp boundaries the centered derivative is
        # an interval average rather than the point velocity. Test cruise/dwell
        # sufficiently far from every acceleration boundary.
        trajectory = self.model.trajectory
        boundaries = [trajectory.depart, trajectory.depart + trajectory.accel_time,
                      trajectory.depart + trajectory.accel_time + trajectory.cruise_time,
                      trajectory.depart + trajectory.move_duration]
        usable = [s for s in self.solutions if min(abs(s["time_s"]-b) for b in boundaries) > 0.003]
        self.assertTrue(usable)
        self.assertLess(max(s["velocity_vector_error_mps"] for s in usable), 0.03)

    def test_delay_compensation_doppler_is_phase_derivative(self):
        cp = deepcopy(COMP)
        cp.update(range_offset_m=3., range_rate_mps=.1, range_sine_m=.2, range_period_s=.7)
        for t in [.03, .19, .73]:
            a, carrier, doppler = compensation(cp, t)
            h = 1e-6
            left = compensation(cp, t-h)[1]
            right = compensation(cp, t+h)[1]
            self.assertEqual(a, carrier)
            self.assertAlmostEqual(doppler, -(right-left)/(2*h)/LAMBDA_L1, places=7)

    def test_independent_frequency_integrates_phase(self):
        cp = deepcopy(COMP)
        cp.update(mode="independent_frequency", range_rate_mps=.1,
                  frequency_offset_hz=2., frequency_rate_hzps=.4,
                  frequency_sine_hz=.3, frequency_period_s=.9)
        for t in [.03, .19, .73]:
            _, _, doppler = compensation(cp, t)
            h = 1e-6
            numerical = -(compensation(cp,t+h)[1]-compensation(cp,t-h)[1])/(2*h)/LAMBDA_L1
            self.assertAlmostEqual(doppler, numerical, places=7)

    def test_common_observation_delay_absorbed_by_clock(self):
        shifted = deepcopy(self.rows)
        shift = 3000.
        for row in shifted:
            row["pseudorange_m"] += shift
        # Differences between satellite observations are invariant.
        for original, current in zip(self.rows, shifted):
            self.assertAlmostEqual(current["pseudorange_m"]-original["pseudorange_m"], shift)
        answers, metrics = solve(self.model, shifted, self.truth)
        self.assertEqual(metrics["convergence_fraction"], 1.)
        self.assertLess(metrics["position_error_m"]["max"], .001)
        for original, current in zip(self.solutions, answers):
            self.assertAlmostEqual(current["estimated_clock_bias_m"]-original["estimated_clock_bias_m"], shift, places=4)

    def test_single_transmitter_spatial_jacobian_is_degenerate(self):
        cfg = baseline("relay")
        cfg["relay"]["transmitters"] = cfg["relay"]["transmitters"][:1]
        validate(cfg)
        model = Model(cfg)
        t = .13
        # Numerical derivative with respect to a spatial translation of the
        # user's entire local path at a fixed epoch (not the receiver's assumed
        # far-away-satellite Jacobian, which can misleadingly be full rank).
        start, end = model.trajectory.start.copy(), model.trajectory.end.copy()
        columns = []
        step = .05
        for axis in range(3):
            delta = np.zeros(3); delta[axis] = step
            model.trajectory.start, model.trajectory.end = start+delta, end+delta
            right = np.array([model.channel(t,p)["code_path_m"] for p in model.prns])
            model.trajectory.start, model.trajectory.end = start-delta, end-delta
            left = np.array([model.channel(t,p)["code_path_m"] for p in model.prns])
            columns.append((right-left)/(2*step))
        model.trajectory.start, model.trajectory.end = start, end
        jacobian = np.column_stack([*columns, np.ones(len(model.prns))])
        singular = np.linalg.svd(jacobian, compute_uv=False)
        # All spatial sensitivity has one indoor radial direction. Receiver
        # time is an additional nuisance direction; 3D position cannot be
        # recovered instantaneously with this geometry and unknown clock.
        self.assertLess(singular[-2]/singular[0], 1e-5)

    def test_reflection_paths_and_finite_wall(self):
        tx, rx, room = np.array([2., 2., 4.]), np.array([13., 6., 1.]), np.array([30.,10.,5.])
        direct = np.linalg.norm(rx-tx)
        for axis in range(3):
            for coordinate in [0.,room[axis]]:
                image, valid = specular_image(tx,rx,axis,coordinate,room)
                self.assertTrue(valid)
                self.assertGreaterEqual(np.linalg.norm(rx-image), direct)
        # A source on its reflecting plane yields a degenerate endpoint hit,
        # and an infinite-plane hit outside the finite room must not be used.
        _, valid = specular_image(np.array([0.,2.,4.]),rx,0,0.,room)
        self.assertFalse(valid)
        _, valid = specular_image(tx,np.array([13.,100.,1.]),0,0.,room)
        self.assertFalse(valid)

    def test_invalid_configurations_rejected(self):
        cases = [
            ("negative noise", lambda c:c["observations"].update(code_sigma_m=-1)),
            ("range bound", lambda c:c["compensation"]["default"].update(range_offset_m=31)),
            ("Doppler bound", lambda c:c["compensation"]["default"].update(range_rate_mps=4)),
            ("independent frequency", lambda c:c["compensation"]["default"].update(frequency_offset_hz=1)),
            ("out of room", lambda c:c["trajectory"].update(end_enu_m=[40,5,1])),
            ("coincident tx", lambda c:c["relay"]["transmitters"][1].update(position_enu_m=[2,2,5])),
            ("insufficient duration", lambda c:c["time"].update(duration_s=.01)),
        ]
        for name, modify in cases:
            with self.subTest(name=name):
                cfg = baseline()
                modify(cfg)
                with self.assertRaises(ValueError): validate(cfg)
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            path = Path(folder)/"bad.json"
            path.write_text(json.dumps({"observations":{"typo_noise":1}}),encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"Unknown parameter"):
                load(path)

    def test_seed_reproducible_and_noise_disabled(self):
        self.assertTrue(all(r["code_noise_m"]==0 and r["doppler_noise_hz"]==0 for r in self.rows))
        cfg = baseline(noise=True)
        a, b = Model(cfg).generate()[1], Model(cfg).generate()[1]
        self.assertEqual(a,b)
        self.assertTrue(any(abs(r["code_noise_m"])>0 for r in a))
        cfg["seed"] += 1
        c = Model(cfg).generate()[1]
        self.assertTrue(any(x["code_noise_m"]!=y["code_noise_m"] for x,y in zip(a,c)))

    def test_atmosphere_sign_and_off_switch(self):
        at = deepcopy(DEFAULT["atmosphere"])
        at["latitude_deg"] = DEFAULT["site"]["latitude_deg"]
        trop, iono = atmosphere(at,0.,math.pi/2,10.)
        self.assertGreater(trop,0.)
        self.assertGreater(iono,0.)
        at["enabled"] = False
        self.assertEqual(atmosphere(at,0.,math.pi/2,10.),(0.,0.))


if __name__ == "__main__": unittest.main()
