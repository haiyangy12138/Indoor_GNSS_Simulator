"""WGS84, Earth rotation, a constant-speed path with physical dwell, specular image rays."""
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
        delta = self.end-self.start
        self.length = np.linalg.norm(delta)
        self.direction = delta / self.length
        self.speed = cfg['speed_mps']
        self.accel_time = cfg['acceleration_time_s']
        self.depart = cfg['start_time_s']
        if self.accel_time * self.speed > self.length:
            raise ValueError('Path too short for configured acceleration and deceleration ramps')
        self.cruise_time = (self.length-self.accel_time*self.speed)/self.speed
        self.move_duration = 2*self.accel_time+self.cruise_time

    def at(self, t):
        """Smooth acceleration ramps use constant acceleration, continuous position/velocity."""
        x = t-self.depart
        a, v, tc = self.accel_time, self.speed, self.cruise_time
        if x <= 0:
            d, speed = 0., 0.
        elif x >= self.move_duration:
            d, speed = self.length, 0.
        elif a == 0:
            d, speed = v*x, v
        elif x < a:
            d, speed = .5*v/a*x*x, v*x/a
        elif x <= a+tc:
            d, speed = .5*v*a+v*(x-a), v
        else:
            z = x-a-tc
            d, speed = .5*v*a+v*tc+v*z-.5*v/a*z*z, v-v*z/a
        return self.start+self.direction*d, self.direction*speed

    def at_distance(self, distance):
        lo, hi = self.depart, self.depart+self.move_duration
        for _ in range(55):
            mid = (lo+hi)/2
            pos, _ = self.at(mid)
            if np.dot(pos-self.start, self.direction) < distance:
                lo = mid
            else:
                hi = mid
        return (lo+hi)/2


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
