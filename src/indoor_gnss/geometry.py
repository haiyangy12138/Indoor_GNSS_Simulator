"""WGS84, Earth rotation, receiver paths with physical dwell, specular image rays."""
import math
import numpy as np

C = 299792458.0
F_L1 = 1575420000.0
LAMBDA_L1 = C / F_L1
OMEGA_E = 7.2921151467e-5
MU = 3.986005e14


def geodetic_to_ecef(lat_deg, lon_deg, height_m):
    lat, lon = np.deg2rad([lat_deg, lon_deg])
    a, e2 = 6378137.0, 6.6943799901413165e-3
    n = a / np.sqrt(1 - e2 * np.sin(lat)**2)
    return np.array([(n+height_m)*np.cos(lat)*np.cos(lon),
                     (n+height_m)*np.cos(lat)*np.sin(lon),
                     (n*(1-e2)+height_m)*np.sin(lat)])


def enu_rotation(lat_deg, lon_deg):
    lat, lon = np.deg2rad([lat_deg, lon_deg])
    return np.array([[-np.sin(lon), np.cos(lon), 0],
                     [-np.sin(lat)*np.cos(lon), -np.sin(lat)*np.sin(lon), np.cos(lat)],
                     [np.cos(lat)*np.cos(lon), np.cos(lat)*np.sin(lon), np.sin(lat)]])


def earth_rotation(xyz, travel_s):
    a = OMEGA_E * travel_s
    c, s = np.cos(a), np.sin(a)
    x, y, z = xyz
    return np.array([c*x+s*y, -s*x+c*y, z])


class Trajectory:
    def __init__(self, cfg):
        self.cfg = cfg
        self.start = np.asarray(cfg['start_enu_m'], float)
        self.end = np.asarray(cfg['end_enu_m'], float)
        points = np.asarray([self.start, *cfg.get('waypoints_enu_m', []), self.end], float)
        segments = np.diff(points, axis=0)
        lengths = np.linalg.norm(segments, axis=1)
        self._segment_distances = np.r_[0., np.cumsum(lengths)]
        if not np.all(np.isfinite(self._segment_distances)) or np.any(np.diff(self._segment_distances) <= 0):
            raise ValueError('Consecutive trajectory points must differ and define positive, finite segment lengths')
        self._waypoints = points[1:-1]
        self._directions = segments / lengths[:, None]
        self.length = float(self._segment_distances[-1])
        self.corner_distances = self._segment_distances[1:-1]
        self.speed = cfg['speed_mps']
        self.accel_time = cfg['acceleration_time_s']
        self.depart = cfg['start_time_s']
        if self.accel_time * self.speed > self.length:
            raise ValueError('Path too short for configured acceleration and deceleration ramps')
        self.cruise_time = (self.length-self.accel_time*self.speed)/self.speed
        self.move_duration = 2*self.accel_time+self.cruise_time
        self._corner_times = np.array([self.at_distance(d) for d in self.corner_distances])

    def at(self, t):
        """Return position and velocity along the polyline at physical time t."""
        if t <= self.depart:
            return self.start.copy(), np.zeros(3)
        if t >= self.depart+self.move_duration:
            return self.end.copy(), np.zeros(3)
        x = t-self.depart
        a, v, tc = self.accel_time, self.speed, self.cruise_time
        if a == 0:
            d, speed = v*x, v
        elif x < a:
            d, speed = .5*v/a*x*x, v*x/a
        elif x <= a+tc:
            d, speed = .5*v*a+v*(x-a), v
        else:
            z = x-a-tc
            d, speed = .5*v*a+v*tc+v*z-.5*v/a*z*z, v-v*z/a
        index = np.searchsorted(self._corner_times, t, side='right')
        # The receiver epoch grid is rounded to picoseconds. Use the outgoing
        # segment even if that rounding puts a corner epoch slightly early.
        if index < len(self._corner_times) and self._corner_times[index]-t <= 0.5e-12 + np.spacing(t):
            index += 1
        origin = self.start if index == 0 else self._waypoints[index-1]
        offset = np.clip(d, self._segment_distances[index], self._segment_distances[index+1])
        offset -= self._segment_distances[index]
        direction = self._directions[index]
        return origin+direction*offset, direction*speed

    def at_distance(self, distance):
        """Invert the speed profile using distance along the entire path."""
        if distance <= 0:
            return self.depart
        if distance >= self.length:
            return self.depart+self.move_duration
        a, v = self.accel_time, self.speed
        ramp_distance = .5*v*a
        if distance < ramp_distance:
            return self.depart+math.sqrt(2*a*distance/v)
        if distance > self.length-ramp_distance:
            return self.depart+self.move_duration-math.sqrt(2*a*(self.length-distance)/v)
        return self.depart+a+(distance-ramp_distance)/v

    def epoch_upper_bound(self, time_cfg):
        """Bound the merged time, distance and corner sampling grids."""
        return (math.ceil(time_cfg['duration_s']/time_cfg['observation_interval_s'])
                + math.ceil(self.length/time_cfg['trajectory_distance_step_m'])
                + len(self.corner_distances)+3)


def specular_image(tx, rx, axis, coordinate, room):
    """One reflection on a finite rectangular room wall. Returns (image, valid)."""
    image = np.array(tx, float)
    image[axis] = 2*coordinate-image[axis]
    denom = rx[axis]-image[axis]
    if abs(denom) < 1e-10:
        return image, False
    fraction = (coordinate-image[axis])/denom
    hit = image+fraction*(rx-image)
    valid = 0 < fraction < 1 and all(-1e-9 <= hit[k] <= room[k]+1e-9 for k in range(3) if k != axis)
    return image, valid
