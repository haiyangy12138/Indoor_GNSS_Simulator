"""Waveform unit checks independent of a full GNSS receiver installation."""
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from indoor_gnss.iq import C_MPS, L1_WAVELENGTH_M, ca_code, render_iq


def example_series(duration=0.01, range_rate=0.0):
    times = np.array([0.0, duration])
    path = (100.0 + times * range_rate)[:, None]
    return {"t_s": times, "prn": np.array([1]), "code_path_m": path,
            "carrier_path_m": path, "gain_linear": np.ones((2, 1)),
            "phase_offset_rad": np.zeros((2, 1)), "cn0_dbhz": np.array([45.0])}


def config(**kwargs):
    return {"seed": 42, "time": {"gps_sow": 100000.0},
            "iq": {"sample_rate_hz": 4_000_000, "duration_s": 0.002,
                   "format": "cf32_le", "noise_enabled": False, **kwargs}}


class IQTests(unittest.TestCase):
    def test_icd_first_ten_chips(self):
        # IS-GPS-200 Table 3-Ia first-ten-chip octal, not from this generator.
        for prn, octal in ((1, "1440"), (2, "1620"), (3, "1710"), (32, "1712")):
            expected = np.array([int(b) for b in format(int(octal, 8), "010b")])
            np.testing.assert_array_equal((1 - ca_code(prn)[:10]) // 2, expected)

    def test_code_autocorrelation_and_balance(self):
        for prn in range(1, 33):
            code = ca_code(prn).astype(np.int64)
            self.assertEqual(len(code), 1023)
            self.assertEqual(int(np.dot(code, code)), 1023)
            self.assertLessEqual(abs(int(np.sum(code))), 65)
            corr = np.fft.ifft(np.abs(np.fft.fft(code)) ** 2).real
            self.assertLessEqual(np.max(np.abs(corr[1:])), 65.000001)

    def test_invalid_prn(self):
        for prn in (0, 33, 1.5, True):
            with self.assertRaises(ValueError):
                ca_code(prn)

    def test_size_period_and_chunk_invariance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = render_iq(config(chunk_samples=617), example_series(), root / "a")
            second = render_iq(config(chunk_samples=8192), example_series(), root / "b")
            self.assertEqual(first["sha256"], second["sha256"])
            self.assertEqual(first["byte_count"], 8000 * 8)
            data = np.fromfile(root / "a" / "signal.iq", dtype="<c8")
            np.testing.assert_allclose(data[:4000], data[4000:], atol=1e-4)
            self.assertFalse(first["standalone_cold_fix_validated"])

    def test_awgn_chunk_invariance_and_ci16(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            a = render_iq(config(format="ci16_le", noise_enabled=True, chunk_samples=313), example_series(), root / "a")
            b = render_iq(config(format="ci16_le", noise_enabled=True, chunk_samples=10000), example_series(), root / "b")
            self.assertEqual(a["sha256"], b["sha256"])
            self.assertEqual(a["byte_count"], 8000 * 4)

    def test_carrier_doppler_from_distance_derivative(self):
        rate = 1.234
        cfg = config(duration_s=0.004)
        with tempfile.TemporaryDirectory() as tmp:
            render_iq(cfg, example_series(range_rate=rate), tmp)
            data = np.fromfile(Path(tmp) / "signal.iq", dtype="<c8")
            # Squaring removes BPSK C/A sign. Recover carrier frequency from phase.
            phase = np.unwrap(np.angle(data.astype(complex) ** 2))
            slope = np.polyfit(np.arange(len(data)) / 4e6, phase, 1)[0]
            self.assertAlmostEqual(slope / (4 * np.pi), -rate / L1_WAVELENGTH_M, places=4)

    def test_code_delay_is_not_carrier_delay(self):
        cfg = config(sample_rate_hz=4_092_000, duration_s=0.002)
        baseline = example_series()
        shifted = example_series()
        # Exactly 10 C/A chips; independent code path to test code-phase mapping.
        shifted["code_path_m"] += 10 * C_MPS / 1_023_000
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            render_iq(cfg, baseline, root / "a")
            render_iq(cfg, shifted, root / "b")
            a = np.fromfile(root / "a" / "signal.iq", dtype="<c8")
            b = np.fromfile(root / "b" / "signal.iq", dtype="<c8")
            np.testing.assert_allclose(b[40:], a[:-40], atol=1e-4)

    def test_rejects_extrapolation_and_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                render_iq(config(duration_s=0.02), example_series(), tmp)
            render_iq(config(), example_series(), tmp)
            with self.assertRaises(FileExistsError):
                render_iq(config(), example_series(), tmp)

    def test_external_navigation_coverage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            nav = root / "nav.json"
            nav.write_text(json.dumps({"1": {"start_gps_sow": 100000.0, "bits": [0, 1]}}))
            with self.assertRaises(ValueError):
                render_iq(config(navigation_bits_file=str(nav)), example_series(), root / "bad")
            nav.write_text(json.dumps({"1": {"start_gps_sow": 99999.98, "bits": [0, 1, 0]}}))
            result = render_iq(config(navigation_bits_file=str(nav)), example_series(), root / "good")
            self.assertEqual(result["navigation_mode"], "external_50bps_symbols_unverified")


if __name__ == "__main__":
    unittest.main()
