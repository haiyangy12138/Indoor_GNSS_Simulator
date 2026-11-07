"""Synthetic NAV fixtures test physics/parser conventions without network access."""
import math
from pathlib import Path
import tempfile
import unittest
from dataclasses import replace
import numpy as np
from indoor_gnss.ephemeris import RinexGPS, calendar_to_gps, F_REL, WEEK_S, MU, OMEGA_E, _position_clock


def nav_text(version=3.05, health=0, e=0.01, week=2200, extra=""):
    from datetime import timedelta
    from indoor_gnss.ephemeris import GPS_EPOCH
    dt = GPS_EPOCH + timedelta(weeks=week)
    first_header = f"{version:9.2f}" + " "*11 + "N" + " "*39 + "RINEX VERSION / TYPE"
    def num(x): return f"{x:19.12E}".replace("E", "D")
    if version >= 3:
        epoch = f"G01 {dt.year:4d} {dt.month:02d} {dt.day:02d} 00 00 00"
        offset = " "*4
    else:
        epoch = f" 1 {dt.year % 100:02d} {dt.month:2d} {dt.day:2d}  0  0  0.0"
        offset = " "*3
    assert len(epoch) == (23 if version >= 3 else 22), repr(epoch)
    rows = [
        [1, 30, 4e-9, 0.7], [1e-6, e, 2e-6, math.sqrt(26560000)],
        [0, 1e-7, 1.0, -1e-7], [0.96, 200, 0.3, -8e-9],
        [1e-10, 0, week, 0], [2, health, -2e-9, 1], [0, 4, 0, 0],
    ]
    return "\n".join([first_header, " "*60 + "END OF HEADER", extra,
                       epoch + "".join(map(num, [2e-4, 1e-12, 1e-20])),
                       *[offset + "".join(map(num, row)) for row in rows]]) + "\n"


class EphemerisTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.addCleanup(self.tmp.cleanup)
    def reader(self, text, **kwargs):
        path = Path(self.tmp.name)/"test.nav"
        path.write_text(text, encoding="ascii")
        return RinexGPS(path, **kwargs)
    def test_calendar_is_gps_not_utc(self):
        self.assertEqual(calendar_to_gps(1980, 1, 6, 0, 0, 0), (0, 0))
        self.assertEqual(calendar_to_gps(2022, 3, 6, 0, 0, 0), (2200, 0))
    def test_orbit_and_clock(self):
        nav = self.reader(nav_text())
        p, v, cb, drift, tgd = nav.state(1, 2200, 100)
        self.assertTrue(25e6 < np.linalg.norm(p) < 28e6)
        self.assertTrue(1500 < np.linalg.norm(v) < 5000)
        self.assertTrue(np.isfinite(drift))
        self.assertEqual(tgd, -2e-9)
        # Nonzero eccentricity produces a periodic correction beyond af0/af1/af2.
        self.assertGreater(abs(cb-(2e-4+1e-12*100+1e-20*100**2)), 1e-9)
    def test_rinex2_matches_rinex3(self):
        a = self.reader(nav_text()).state(1, 2200, 100)
        b = self.reader(nav_text(version=2.11)).state(1, 2200, 100)
        np.testing.assert_allclose(a[0], b[0], atol=1e-8)
        self.assertAlmostEqual(a[2], b[2], places=14)
    def test_circular_equatorial_closed_form(self):
        nav = self.reader(nav_text())
        original = nav.records[1][0]
        record = replace(original, eccentricity=0, delta_n=0, m0=0, omega0=0,
                         crs=0, crc=0, cuc=0, cus=0, cic=0, cis=0,
                         i0=0, i_dot=0, argument_perigee=0, omega_dot=0)
        nav.records[1] = [record]
        radius = record.sqrt_a**2
        p, v, _, _, _ = nav.state(1, 2200, 0)
        np.testing.assert_allclose(p, [radius, 0, 0], atol=1e-7)
        expected_vy = radius*(math.sqrt(MU/radius**3)-OMEGA_E)
        np.testing.assert_allclose(v, [0, expected_vy, 0], atol=0.002)
    def test_relativistic_clock_closed_form(self):
        nav = self.reader(nav_text())
        original = nav.records[1][0]
        # E=pi/2 solves Kepler exactly for M=pi/2-e.
        record = replace(original, m0=math.pi/2-original.eccentricity)
        _, clock = _position_clock(record, record.toe_absolute)
        expected = record.af0 + F_REL*record.eccentricity*record.sqrt_a
        self.assertAlmostEqual(clock, expected, places=15)
    def test_health_and_expiry(self):
        nav = self.reader(nav_text(health=1))
        with self.assertRaisesRegex(ValueError, "healthy"):
            nav.state(1, 2200, 0)
        self.assertEqual(self.reader(nav_text(health=1), allow_unhealthy=True).prns, [1])
        nav = self.reader(nav_text())
        with self.assertRaisesRegex(ValueError, "stale"):
            nav.state(1, 2201, 0)
        with self.assertRaisesRegex(ValueError, "stale"):
            nav.state(1, 2200, 8000)
    def test_week_boundary_continuity(self):
        nav = self.reader(nav_text())
        p1 = nav.state(1, 2199, WEEK_S-0.01)[0]
        p2 = nav.state(1, 2200, 0.01)[0]
        self.assertLess(np.linalg.norm(p2-p1), 100)
    def test_mixed_glonass_skipped(self):
        block = "R01 2022 03 06 00 00 00" + " 0"*3 + "\n" + "\n".join(["    0"]*3)
        nav = self.reader(nav_text(extra=block))
        self.assertEqual(nav.prns, [1])
        self.assertEqual(nav.skipped_records, 1)
    def test_unsupported_and_truncated(self):
        with self.assertRaisesRegex(ValueError, "RINEX 4"):
            self.reader(nav_text(version=4.00))
        with self.assertRaisesRegex(ValueError, "truncated"):
            self.reader("\n".join(nav_text().splitlines()[:-1]))
    def test_gzip(self):
        import gzip
        path = Path(self.tmp.name)/"test.nav.gz"
        with gzip.open(path, "wt", encoding="ascii") as stream:
            stream.write(nav_text())
        self.assertEqual(RinexGPS(path).prns, [1])


if __name__ == "__main__": unittest.main()
