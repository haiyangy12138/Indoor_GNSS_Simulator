"""Propagation models, synthetic circular orbits, continuous oscillator and compensation models."""
import math
import numpy as np
from .geometry import C, F_L1, LAMBDA_L1, OMEGA_E, MU, earth_rotation


class SyntheticGPS:
    """Physically moving circular MEO orbit ensemble, explicitly not a real constellation."""
    def __init__(self, cfg):
        self.cfg = cfg
        self.prns = list(range(1, cfg['synthetic_count']+1))

    def state(self, prn, gps_week, gps_sow):
        cfg = self.cfg
        dt = (gps_week-cfg['epoch_gps_week'])*604800+gps_sow-cfg['epoch_gps_sow']
        planes = cfg['synthetic_planes']
        plane, slot = (prn-1) % planes, (prn-1)//planes
        slots = math.ceil(cfg['synthetic_count']/planes)
        r = cfg['synthetic_radius_m']
        i = np.deg2rad(cfg['synthetic_inclination_deg'])
        node = 2*np.pi*plane/planes+np.deg2rad(cfg['synthetic_raan_offset_deg'])-OMEGA_E*dt
        arg = 2*np.pi*slot/slots + 2*np.pi*plane/(planes*slots) + np.sqrt(MU/r**3)*dt
        def position(d):
            o, u = node-OMEGA_E*d, arg+np.sqrt(MU/r**3)*d
            return r*np.array([np.cos(o)*np.cos(u)-np.sin(o)*np.sin(u)*np.cos(i),
                               np.sin(o)*np.cos(u)+np.cos(o)*np.sin(u)*np.cos(i),
                               np.sin(u)*np.sin(i)])
        xyz = position(0)
        vel = (position(.1)-position(-.1))/.2
        # Common satellite clock settings; per-PRN errors can be added through config later.
        bias = cfg['synthetic_clock_bias_s']+cfg['synthetic_clock_drift_sps']*dt
        return xyz, vel, bias, cfg['synthetic_clock_drift_sps'], cfg['synthetic_tgd_s']

    def describe(self):
        return {'type': 'synthetic_circular_MEO_not_real_GPS', 'parameters': self.cfg}


def clock_m(cfg, t):
    """Deterministic continuous clock, range units. No hidden per-epoch independent jumps."""
    return C*(cfg['bias_s']+cfg['drift_sps']*t+.5*cfg['drift_rate_sps2']*t*t
              +cfg['sinusoid_amplitude_s']*np.sin(2*np.pi*t/cfg['sinusoid_period_s']))


def compensation(cfg, t):
    """Positive range extends code/carrier path. Positive extra Hz advances carrier phase."""
    mode = cfg['mode']
    a = cfg['range_offset_m'] + cfg['range_rate_mps']*t + cfg['range_sine_m']*np.sin(2*np.pi*t/cfg['range_period_s'])
    adot = cfg['range_rate_mps'] + cfg['range_sine_m']*2*np.pi/cfg['range_period_s']*np.cos(2*np.pi*t/cfg['range_period_s'])
    if mode == 'delay_coupled':
        return a, a, -adot/LAMBDA_L1
    f0, fr, amp = cfg['frequency_offset_hz'], cfg['frequency_rate_hzps'], cfg['frequency_sine_hz']
    w = 2*np.pi/cfg['frequency_period_s']
    integ = f0*t+.5*fr*t*t+amp*(1-np.cos(w*t))/w
    # Independent frequency control is explicit. Phase is integrated, never f(t)*t.
    return a, a-LAMBDA_L1*integ, -adot/LAMBDA_L1+f0+fr*t+amp*np.sin(w*t)


def atmosphere(cfg, az, el, height_m):
    """Saastamoinen zenith hydro/wet + simple secant mapping; thin-shell TEC, L1."""
    if not cfg['enabled']:
        return 0., 0.
    el = max(el, np.deg2rad(cfg['min_mapping_elevation_deg']))
    lat = np.deg2rad(cfg['latitude_deg'])
    p, temp, rh = cfg['pressure_hpa'], cfg['temperature_k'], cfg['relative_humidity']
    e = rh*6.108*np.exp((17.15*(temp-273.15))/(234.7+temp-273.15))
    zhd = .0022768*p/(1-.00266*np.cos(2*lat)-.00028*height_m/1000)
    zwd = .002277*(1255/temp+.05)*e
    trop = (zhd+zwd)/np.sin(el)
    earth_r = 6371000.
    mapping = 1/np.sqrt(1-(earth_r*np.cos(el)/(earth_r+cfg['iono_shell_height_m']))**2)
    iono = 40.3*cfg['vertical_tec_tecu']*1e16/F_L1**2*mapping
    return trop, iono


def space_link(provider, prn, week, sow, receiver_xyz, rotation, cfg):
    """Iterate retarded transmit time; Earth rotation uses geometric flight time only."""
    tau = .075
    for _ in range(8):
        sat, vel, clk, drift, tgd = provider.state(prn, week, sow-tau)
        rotated = earth_rotation(sat, tau) if cfg['earth_rotation'] else sat
        rho = np.linalg.norm(rotated-receiver_xyz)
        new_tau = rho/C
        if abs(new_tau-tau) < cfg['light_time_tolerance_s']:
            tau = new_tau
            break
        tau = new_tau
    los = rotated-receiver_xyz
    east, north, up = rotation @ los
    az = np.arctan2(east,north) % (2*np.pi)
    el = np.arctan2(up,np.hypot(east,north))
    return {'range_m':rho,'satellite_xyz':rotated,'clock_s':clk,'tgd_s':tgd,
            'azimuth_rad':az,'elevation_rad':el,'flight_s':tau}
