"""GPS legacy broadcast ephemerides (RINEX 2/3 NAV; not RINEX 4).

Coordinates refer to the ECEF frame at signal transmission. The caller must
handle light time and Earth rotation to the reception frame. Clock output
includes the periodic relativistic correction but EXCLUDES TGD; apply the GPS
L1 C/A code correction separately. Calendar epochs in GPS NAV are GPST, not UTC.

References: IS-GPS-200, Table 20-IV; ESA Navipedia, GPS and Galileo Satellite
Coordinates Computation; Relativistic Clock Correction. RINEX 3.05 Table A6.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
import math
import numpy as np

MU = 3.986005e14  # GPS user algorithm value, m^3/s^2
OMEGA_E = 7.2921151467e-5  # rad/s, GPS interface specification
F_REL = -4.442807633e-10  # s / sqrt(m)
WEEK_S = 604800.0
GPS_EPOCH = datetime(1980, 1, 6)


def calendar_to_gps(year, month, day, hour, minute, second):
    """Convert a GPS-system calendar label to (full week, seconds of week)."""
    epoch = datetime(int(year), int(month), int(day), int(hour), int(minute))
    epoch += timedelta(seconds=float(second))
    absolute = (epoch - GPS_EPOCH).total_seconds()
    if absolute < 0:
        raise ValueError("GPS navigation epoch precedes 1980-01-06")
    week = math.floor(absolute / WEEK_S)
    return week, absolute - week * WEEK_S


def _wrap_week(delta):
    return (delta + WEEK_S / 2) % WEEK_S - WEEK_S / 2


def _number(value, *, required=False):
    value = value.strip().replace("D", "E").replace("d", "e")
    if not value:
        if required:
            raise ValueError("missing required RINEX numeric field")
        return 0.0
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("non-finite RINEX numeric field")
    return result


@dataclass(frozen=True)
class GPSRecord:
    prn: int
    toc_absolute: float
    toe_absolute: float
    toe_sow: float
    af0: float
    af1: float
    af2: float
    crs: float
    delta_n: float
    m0: float
    cuc: float
    eccentricity: float
    cus: float
    sqrt_a: float
    cic: float
    omega0: float
    cis: float
    i0: float
    crc: float
    argument_perigee: float
    omega_dot: float
    i_dot: float
    health: int
    tgd_s: float
    fit_interval_h: float


def _position_clock(record: GPSRecord, absolute_time: float):
    tk = _wrap_week(absolute_time - record.toe_absolute)
    a = record.sqrt_a ** 2
    n = math.sqrt(MU / a**3) + record.delta_n
    mean = math.remainder(record.m0 + n * tk, 2 * math.pi)
    eccentric = mean
    for _ in range(30):
        correction = (eccentric - record.eccentricity * math.sin(eccentric) - mean) / (
            1 - record.eccentricity * math.cos(eccentric)
        )
        eccentric -= correction
        if abs(correction) < 1e-14:
            break
    else:
        raise ValueError("Kepler iteration did not converge")
    e = record.eccentricity
    true = math.atan2(math.sqrt(1 - e*e) * math.sin(eccentric), math.cos(eccentric) - e)
    phi = true + record.argument_perigee
    sin2, cos2 = math.sin(2 * phi), math.cos(2 * phi)
    u = phi + record.cus * sin2 + record.cuc * cos2
    r = a * (1 - e * math.cos(eccentric)) + record.crs * sin2 + record.crc * cos2
    inc = record.i0 + record.i_dot * tk + record.cis * sin2 + record.cic * cos2
    node = record.omega0 + (record.omega_dot - OMEGA_E) * tk - OMEGA_E * record.toe_sow
    xp, yp = r * math.cos(u), r * math.sin(u)
    xyz = np.array([
        xp * math.cos(node) - yp * math.cos(inc) * math.sin(node),
        xp * math.sin(node) + yp * math.cos(inc) * math.cos(node),
        yp * math.sin(inc),
    ], dtype=float)
    dt = _wrap_week(absolute_time - record.toc_absolute)
    rel = F_REL * e * record.sqrt_a * math.sin(eccentric)
    clock = record.af0 + record.af1 * dt + record.af2 * dt**2 + rel
    return xyz, clock


class RinexGPS:
    """Read GPS broadcast ephemerides from RINEX 2/3 navigation files.

    Mixed RINEX 3 files may contain other systems, which are skipped using their
    record lengths. Only GPS legacy eight-line records are decoded. Unknown
    system types, malformed records, stale ephemerides, and unhealthy satellites
    are rejected explicitly. Files ending .gz are supported without extraction.
    """
    def __init__(self, path, max_age_s=14400.0, allow_unhealthy=False):
        self.path = Path(path).resolve()
        self.max_age_s = float(max_age_s)
        self.allow_unhealthy = bool(allow_unhealthy)
        if not math.isfinite(self.max_age_s) or self.max_age_s <= 0:
            raise ValueError("max_age_s must be positive and finite")
        if self.path.suffix.lower() == ".gz":
            import gzip
            with gzip.open(self.path, "rt", encoding="ascii") as stream:
                lines = stream.read().splitlines()
        else:
            lines = self.path.read_text(encoding="ascii").splitlines()
        if not lines or "RINEX VERSION / TYPE" not in lines[0]:
            raise ValueError("not a RINEX navigation file")
        self.version = _number(lines[0][:9], required=True)
        if not 2 <= self.version < 4:
            raise ValueError("only RINEX 2/3 legacy GPS NAV is supported; RINEX 4 is not")
        if len(lines[0]) < 21 or lines[0][20].upper() != "N":
            raise ValueError("expected a GPS/mixed navigation file, not observations or GLONASS-only NAV")
        if self.version < 3 and "GLONASS" in lines[0][:60].upper():
            raise ValueError("RINEX 2 GLONASS navigation is unsupported")
        header_end = next((i for i, line in enumerate(lines) if "END OF HEADER" in line), None)
        if header_end is None:
            raise ValueError("RINEX header has no END OF HEADER")
        self.records: dict[int, list[GPSRecord]] = {}
        self.skipped_records = 0
        index = header_end + 1
        while index < len(lines):
            if not lines[index].strip():
                index += 1
                continue
            first = lines[index]
            if self.version >= 3:
                system = first[0]
                if system not in "GRECJIS":
                    raise ValueError(f"unknown or unsupported RINEX 3 record at line {index + 1}: {system!r}")
                count = 4 if system in "RS" else 8
            else:
                system, count = "G", 8
            block = lines[index:index + count]
            if len(block) != count:
                raise ValueError(f"truncated RINEX record at line {index + 1}")
            if system == "G":
                try:
                    record = self._parse(block)
                except (ValueError, IndexError) as error:
                    raise ValueError(f"invalid GPS record at line {index + 1}: {error}") from error
                self.records.setdefault(record.prn, []).append(record)
            else:
                self.skipped_records += 1
            index += count
        if not self.records:
            raise ValueError("RINEX file contains no GPS broadcast ephemerides")
        for records in self.records.values():
            records.sort(key=lambda r: (r.toe_absolute, r.toc_absolute))

    def _parse(self, block):
        first = block[0]
        if self.version >= 3:
            prn = int(first[1:3])
            epoch = first[3:23].split()
            start = 23
            offset = 4
        else:
            prn = int(first[:2])
            epoch = first[2:22].split()
            if len(epoch) != 6:
                raise ValueError("invalid RINEX 2 epoch")
            yy = int(epoch[0])
            epoch[0] = str(1900 + yy if yy >= 80 else 2000 + yy)
            start = 22
            offset = 3
        if len(epoch) != 6:
            raise ValueError("invalid GPS epoch")
        week, sow = calendar_to_gps(*[float(x) for x in epoch])
        clocks = [_number(first[start+i*19:start+(i+1)*19], required=True) for i in range(3)]
        rows = [[_number(line[offset+i*19:offset+(i+1)*19], required=(row < 5 or i < 2))
                 for i in range(4)] for row, line in enumerate(block[1:])]
        raw_week = int(round(rows[4][2]))
        # Old NAV files may carry a 10-bit week; use the calendar epoch to resolve it.
        full_week = raw_week
        if 0 <= raw_week < 1024:
            full_week += round((week - raw_week) / 1024) * 1024
        if abs(full_week - week) > 1:
            raise ValueError("ephemeris week is inconsistent with clock calendar epoch")
        toe = rows[2][0]
        if not 0 <= toe < WEEK_S:
            raise ValueError("toe must be seconds of GPS week")
        if not 0 <= rows[1][1] < 1 or not 4000 <= rows[1][3] <= 6500:
            raise ValueError("nonphysical GPS eccentricity or sqrt(A)")
        if not 1 <= prn <= 99:
            raise ValueError("invalid GPS PRN")
        return GPSRecord(
            prn, week*WEEK_S+sow, full_week*WEEK_S+toe, toe,
            *clocks, rows[0][1], rows[0][2], rows[0][3],
            rows[1][0], rows[1][1], rows[1][2], rows[1][3],
            rows[2][1], rows[2][2], rows[2][3], rows[3][0], rows[3][1],
            rows[3][2], rows[3][3], rows[4][0], int(round(rows[5][1])),
            rows[5][2], rows[6][1],
        )

    @property
    def prns(self):
        return sorted(self.records)

    def _select(self, prn, absolute):
        records = self.records.get(int(prn), [])
        candidates = [r for r in records if self.allow_unhealthy or r.health == 0]
        if not candidates:
            raise ValueError(f"no healthy GPS ephemeris for PRN {prn}")
        record = min(candidates, key=lambda r: abs(absolute-r.toe_absolute))
        # Absolute age, not modulo-week age: never reuse a file a week later.
        age = max(abs(absolute-record.toe_absolute), abs(absolute-record.toc_absolute))
        fit_limit = record.fit_interval_h * 3600 / 2 if record.fit_interval_h > 0 else float("inf")
        if age > min(self.max_age_s, fit_limit):
            raise ValueError(f"stale GPS ephemeris for PRN {prn}: age {age:.1f} s")
        return record

    def state(self, prn, gps_week, gps_sow):
        """Return (ECEF m, ECEF m/s, clock s, clock drift s/s, TGD s).

        Velocity/drift use a centered 0.1 s finite difference on the SAME record
        so an ephemeris update cannot cause a spurious rate discontinuity.
        gps_sow can extend outside a week; absolute time remains continuous.
        """
        absolute = int(gps_week)*WEEK_S + float(gps_sow)
        if not math.isfinite(absolute):
            raise ValueError("requested GPS time must be finite")
        record = self._select(prn, absolute)
        xyz, clock = _position_clock(record, absolute)
        h = 0.1
        before, cb = _position_clock(record, absolute-h)
        after, ca = _position_clock(record, absolute+h)
        return xyz, (after-before)/(2*h), clock, (ca-cb)/(2*h), record.tgd_s

    def describe(self):
        return {"mode": "gps_rinex_broadcast", "source": str(self.path),
                "rinex_version": self.version, "prns": self.prns,
                "record_count": sum(map(len, self.records.values())),
                "skipped_non_gps_records": self.skipped_records,
                "max_age_s": self.max_age_s, "allow_unhealthy": self.allow_unhealthy,
                "clock_includes_relativity": True, "clock_includes_tgd": False,
                "epoch_time_system": "GPST (not UTC)",
                "earth_rotation_during_flight_applied": False}
