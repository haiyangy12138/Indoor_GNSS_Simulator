"""Fully expanded, units-explicit configuration with strict unknown-key rejection."""
from copy import deepcopy
import json
import math
from pathlib import Path
import numpy as np

CLOCK = dict(bias_s=0., drift_sps=0., drift_rate_sps2=0., sinusoid_amplitude_s=0., sinusoid_period_s=20.)
COMP = dict(mode='delay_coupled', range_offset_m=0., range_rate_mps=0., range_sine_m=0., range_period_s=5.,
            frequency_offset_hz=0., frequency_rate_hzps=0., frequency_sine_hz=0., frequency_period_s=5.)
DEFAULT = {
    'seed':20261105,
    'time':{'gps_week':2443,'gps_sow':345600.,'duration_s':2.,'observation_interval_s':.01,
            'trajectory_distance_step_m':1.,'derivative_step_s':.002},
    'site':{'latitude_deg':31.2304,'longitude_deg':121.4737,'height_m':10.,'room_size_enu_m':[30.,10.,5.],
            'outdoor_antenna_enu_m':[15.,5.,8.]},
    'trajectory':{'start_enu_m':[0.,5.,1.],'end_enu_m':[30.,5.,1.],'waypoints_enu_m':[],'start_time_s':.2,
                  'speed_mps':80/3.6,'acceleration_time_s':0.},
    'satellites':{'source':'synthetic','rinex_nav_file':None,'max_ephemeris_age_s':14400.,
        'allow_unhealthy':False,'count':8,'prns':[],'elevation_mask_deg':5.,
        'synthetic_count':32,'synthetic_planes':8,'synthetic_radius_m':26560000.,
        'synthetic_inclination_deg':55.,'synthetic_raan_offset_deg':0.,
        'epoch_gps_week':2443,'epoch_gps_sow':345600.,
        'synthetic_clock_bias_s':0.,'synthetic_clock_drift_sps':0.,'synthetic_tgd_s':0.},
    'propagation':{'mode':'relay','earth_rotation':True,'light_time_tolerance_s':1e-12,
                   'min_path_m':.05},
    'relay':{'architecture':'transparent','mapping':{},'transmitters':[
        {'id':'V1','position_enu_m':[2.,2.,5.],'cable_length_m':20.,'cable_velocity_factor':.66,
         'processing_delay_s':.001,'phase_offset_rad':0.,'reference_distance_m':10.,
         'path_loss_exponent':2.,'excess_loss_db':0.,'clock':deepcopy(CLOCK)},
        {'id':'V2','position_enu_m':[28.,8.,5.],'cable_length_m':20.,'cable_velocity_factor':.66,
         'processing_delay_s':.001,'phase_offset_rad':0.,'reference_distance_m':10.,
         'path_loss_exponent':2.,'excess_loss_db':0.,'clock':deepcopy(CLOCK)}],
        'min_spacing_m':8.,'max_spacing_m':30.},
    'compensation':{'default':deepcopy(COMP),'per_prn':{},'max_range_m':30.,'max_doppler_hz':20.},
    'input_observations':{'corrected_csv':None,'compare_reference':False},
    'receiver_clock':{**deepcopy(CLOCK),'bias_s':1e-5,'drift_sps':2e-8,
                      'frequency_gm_sigma_sps':0.,'frequency_gm_tau_s':10.,'clock_grid_s':.001},
    'atmosphere':{'enabled':True,'pressure_hpa':1013.25,'temperature_k':293.15,
        'relative_humidity':.5,'vertical_tec_tecu':10.,'iono_shell_height_m':350000.,
        'min_mapping_elevation_deg':3.},
    'multipath':{'enabled':False,'walls':['east','west','north','south','floor','ceiling'],
                  'reflection_amplitude':.35,'reflection_phase_rad':3.141592653589793},
    'observations':{'add_noise':True,'reference_cn0_dbhz':45.,'reference_cn0_for_noise_dbhz':45.,
        'code_sigma_m':.6,'doppler_sigma_hz':.3,'code_noise_correlation_s':.1,
        'doppler_noise_correlation_s':.1,'noise_code_doppler_correlation':0.,
        'minimum_cn0_dbhz':20.,'dropout_probability':0.,'apply_cn0_gate':False},
    'solver':{'enabled':True,'initial_enu_m':[15.,5.,1.],'max_iterations':30,
              'position_tolerance_m':1e-5,'max_step_m':500.,'known_height_m':None,
              'apply_atmosphere':True,'position_normalization_m':30.,'velocity_normalization_mps':80/3.6},
    'iq':{'enabled':True,'start_s':.25,'duration_s':.05,'sample_rate_hz':4092000.,'intermediate_frequency_hz':0.,
          'format':'ci16_le','chunk_samples':65536,'output_name':'signal.iq',
          'adc_full_scale_sigma':6.,'navigation_bits_file':None,'add_noise':True,'max_output_bytes':2000000000}
}


def _merge(base, patch, path=''):
    for key, value in patch.items():
        where = f'{path}.{key}' if path else key
        if key not in base:
            raise ValueError(f'Unknown parameter: {where}')
        if where in ('relay.mapping','compensation.per_prn'):
            base[key] = deepcopy(value)
        elif isinstance(base[key],dict) and isinstance(value,dict):
            _merge(base[key],value,where)
        else:
            base[key] = deepcopy(value)
    return base


def load(path=None):
    cfg = deepcopy(DEFAULT)
    if path:
        _merge(cfg,json.loads(Path(path).read_text(encoding='utf-8-sig')))
        # Only external input paths are relative to the config file, never the user's cwd.
        for section, field in [('satellites','rinex_nav_file'),('iq','navigation_bits_file'),
                               ('input_observations','corrected_csv')]:
            v=cfg[section][field]
            if v and not Path(v).is_absolute():
                cfg[section][field]=str((Path(path).resolve().parent/v).resolve())
    for p in cfg['compensation']['per_prn']:
        cfg['compensation']['per_prn'][p]=_merge(deepcopy(cfg['compensation']['default']),cfg['compensation']['per_prn'][p],f'compensation.prn_{p}')
    validate(cfg)
    return cfg


def configure_position_mode(cfg, mode=None, height_m=None):
    """Select solver dimensions without changing physical geometry or reading truth."""
    if mode not in (None, '2d', '3d'):
        raise ValueError('Position mode must be 2d or 3d')
    if mode == '3d':
        if height_m is not None:
            raise ValueError('--height-m is only available for 2D positioning')
        cfg['solver']['known_height_m'] = None
    elif mode == '2d':
        previous = cfg['solver']['known_height_m']
        cfg['solver']['known_height_m'] = (
            height_m if height_m is not None else
            previous if previous is not None else cfg['solver']['initial_enu_m'][2])
    elif height_m is not None:
        if cfg['solver']['known_height_m'] is None:
            raise ValueError('--height-m requires 2D positioning; use --position-mode 2d')
        cfg['solver']['known_height_m'] = height_m
    validate(cfg)
    return cfg


def validate(cfg):
    from .physics import compensation
    from .geometry import Trajectory
    def require(v,msg):
        if not v: raise ValueError(msg)
    def finite(obj):
        if isinstance(obj,dict):
            for v in obj.values(): finite(v)
        elif isinstance(obj,list):
            for v in obj: finite(v)
        elif isinstance(obj,(float,int)):
            require(math.isfinite(obj),'All numbers must be finite')
    finite(cfg)
    t=cfg['time']; s=cfg['satellites']; iq=cfg['iq']; obs=cfg['observations']
    imported=cfg['input_observations']['corrected_csv']
    require(imported is None or isinstance(imported,str),'input_observations.corrected_csv must be a path or null')
    require(isinstance(cfg['input_observations']['compare_reference'],bool),'compare_reference must be true or false')
    require(not imported or cfg['solver']['enabled'],'导入观测数据时须启用“生成定位解与误差统计”。')
    require(t['duration_s']>0 and t['observation_interval_s']>0 and t['trajectory_distance_step_m']>0,'Positive duration and spacings required')
    require(0<t['derivative_step_s']<.1,'derivative_step_s must lie in (0,0.1)')
    require(0<=t['gps_sow']<604800,'gps_sow must be in [0,604800)')
    require(s['source'] in ('synthetic','rinex'),'satellites.source must be synthetic or rinex')
    require(1<=s['synthetic_count']<=32 and 1<=s['synthetic_planes']<=s['synthetic_count'],'GPS C/A generator supports PRN1..32')
    require(s['synthetic_radius_m']>6378137 and 0<=s['synthetic_inclination_deg']<=180,'Invalid synthetic orbit')
    require(1<=s['count']<=32,'Satellite count must be 1..32')
    require(isinstance(s['count'],int) and not isinstance(s['count'],bool),'Satellite count must be an integer')
    require(all(isinstance(p,int) and not isinstance(p,bool) and 1<=p<=32 for p in s['prns']),
            'Explicit GPS PRNs must be integers 1..32')
    require(cfg['propagation']['mode'] in ('direct','relay'),'propagation.mode must be direct or relay')
    require(cfg['relay']['architecture'] in ('transparent','regenerative'),'Invalid relay architecture')
    motion=cfg['trajectory']
    require(motion['speed_mps']>0 and motion['acceleration_time_s']>=0,'Invalid trajectory speed/ramp')
    room=np.asarray(cfg['site']['room_size_enu_m'],float)
    require(room.shape==(3,) and np.all(room>0),'Room must have 3 positive dimensions')
    for name in ['start_enu_m','end_enu_m']:
        x=np.asarray(motion[name],float)
        require(x.shape==(3,) and np.all((x>=0)&(x<=room)),f'trajectory.{name} must be inside room')
    waypoints=motion.get('waypoints_enu_m',[])
    require(isinstance(waypoints,list),'trajectory.waypoints_enu_m must be a list of [east, north, up] points')
    for index,point in enumerate(waypoints):
        name=f'trajectory.waypoints_enu_m[{index}]'
        require(isinstance(point,list) and len(point)==3 and
                all(isinstance(value,(int,float)) and not isinstance(value,bool) for value in point),
                f'{name} must contain three numeric coordinates [east, north, up]')
        require(np.all((np.asarray(point)>=0)&(np.asarray(point)<=room)),f'{name} must be inside room')
    traj=Trajectory(motion)
    estimated_epochs=traj.epoch_upper_bound(t)
    require(estimated_epochs<=200000,'Estimated epoch count exceeds 200000; increase sampling intervals or split the run')
    require(int(np.ceil((t['duration_s']+.4)/cfg['receiver_clock']['clock_grid_s']))<=2000000,
            'Clock process grid exceeds 2000000 points; increase clock_grid_s or split the run')
    require(0<=traj.depart and traj.depart+traj.move_duration<=t['duration_s'],'Entire movement must fit inside simulation duration')
    txs=cfg['relay']['transmitters']
    require(1<=len(txs)<=4,'Use 1..4 transmitters')
    require(len({x['id'] for x in txs})==len(txs),'Transmitter IDs must be unique')
    for tx in txs:
        require(set(tx)==set(DEFAULT['relay']['transmitters'][0]),'Transmitter entries require all documented fields, with no unknown fields')
        _merge(deepcopy(CLOCK),tx['clock'],'relay.clock')
        x=np.asarray(tx['position_enu_m'],float)
        require(x.shape==(3,) and np.all((x>=0)&(x<=room)),'Transmitter must be inside room or on its boundary')
        require(0<tx['cable_velocity_factor']<=1 and tx['cable_length_m']>=0 and tx['processing_delay_s']>=0,'Invalid physical relay delay')
        require(tx['reference_distance_m']>0 and tx['path_loss_exponent']>=0,'Invalid path loss reference/exponent')
        if cfg['relay']['architecture']=='transparent':
            require(all(tx['clock'][k]==0 for k in ['bias_s','drift_sps','drift_rate_sps2','sinusoid_amplitude_s']),
                    'Transparent relay cannot add an independent transmitter clock; choose regenerative')
    for i,a in enumerate(txs):
        for b in txs[i+1:]:
            d=np.linalg.norm(np.array(a['position_enu_m'])-b['position_enu_m'])
            require(cfg['relay']['min_spacing_m']<d<cfg['relay']['max_spacing_m'],'Transmitter spacing must satisfy strict min/max bounds')
    for prn,txid in cfg['relay']['mapping'].items():
        require(isinstance(prn,str) and prn in {str(p) for p in range(1,33)} and txid in [a['id'] for a in txs],
                'Mapping keys must be canonical PRN strings 1..32 (no G prefix or leading zero) with valid transmitter IDs')
    require(all(isinstance(p,str) and p in {str(k) for k in range(1,33)} for p in cfg['compensation']['per_prn']),
            'per_prn keys must be canonical PRN strings 1..32 (no G prefix or leading zero)')
    for cp in [cfg['compensation']['default'],*cfg['compensation']['per_prn'].values()]:
        require(cp['mode'] in ('delay_coupled','independent_frequency'),'Unknown compensation mode')
        require(cp['range_period_s']>0 and cp['frequency_period_s']>0,'Compensation periods must be positive')
        if cp['mode']=='delay_coupled':
            require(all(cp[x]==0 for x in ['frequency_offset_hz','frequency_rate_hzps','frequency_sine_hz']),
                    'Independent frequency parameters require independent_frequency mode')
        # Conservative analytic envelopes guarantee continuous-time bounds, not only sampled bounds.
        rbound=abs(cp['range_offset_m'])+abs(cp['range_rate_mps'])*t['duration_s']+abs(cp['range_sine_m'])
        from .geometry import LAMBDA_L1, C
        fbound=(abs(cp['range_rate_mps'])+abs(cp['range_sine_m'])*2*np.pi/cp['range_period_s'])/LAMBDA_L1
        if cp['mode']=='independent_frequency':
            fbound+=abs(cp['frequency_offset_hz'])+abs(cp['frequency_rate_hzps'])*t['duration_s']+abs(cp['frequency_sine_hz'])
        require(rbound<=cfg['compensation']['max_range_m'],'Continuous range compensation bound exceeds allowed range')
        require(fbound<=cfg['compensation']['max_doppler_hz'],'Continuous compensation Doppler bound exceeds allowed range')
        for tx in txs:
            require(tx['cable_length_m']/tx['cable_velocity_factor']+tx['processing_delay_s']*C>=rbound,
                    'Negative compensation would require non-causal relay timing; increase fixed positive buffer')
    require(0<=obs['dropout_probability']<=1 and abs(obs['noise_code_doppler_correlation'])<=1,'Invalid probability/correlation')
    require(obs['code_sigma_m']>=0 and obs['doppler_sigma_hz']>=0,'Noise sigmas must be nonnegative')
    require(obs['code_noise_correlation_s']>=0 and obs['doppler_noise_correlation_s']>=0,'Noise correlation times must be nonnegative')
    require(cfg['receiver_clock']['frequency_gm_sigma_sps']>=0 and cfg['receiver_clock']['frequency_gm_tau_s']>0 and cfg['receiver_clock']['clock_grid_s']>0,'Invalid oscillator process')
    for clock in [cfg['receiver_clock'],*[x['clock'] for x in txs]]:
        require(clock['sinusoid_period_s']>0,'Clock sinusoid period must be positive')
    at=cfg['atmosphere']
    require(150<at['temperature_k']<350 and 0<=at['relative_humidity']<=1 and at['pressure_hpa']>0 and at['vertical_tec_tecu']>=0 and at['iono_shell_height_m']>0,'Invalid atmospheric inputs')
    require(0<=cfg['multipath']['reflection_amplitude']<=1,'Reflection amplitude must be in [0,1]')
    require(set(cfg['multipath']['walls'])<=set(['east','west','north','south','floor','ceiling']),'Unknown reflection wall')
    require(cfg['solver']['position_normalization_m']>0 and cfg['solver']['velocity_normalization_mps']>0,'Metric normalizations must be positive')
    initial = np.asarray(cfg['solver']['initial_enu_m'], float)
    require(initial.shape == (3,), 'solver.initial_enu_m must contain three coordinates')
    known_height = cfg['solver']['known_height_m']
    require(known_height is None or (
        isinstance(known_height, (int, float)) and not isinstance(known_height, bool)
        and 0 <= known_height <= room[2]),
        'solver.known_height_m must be null or a height inside the room [0, room_z]')
    if iq['enabled'] and not imported:
        require(iq['start_s']>=0 and iq['duration_s']>0 and iq['start_s']+iq['duration_s']<=t['duration_s'],'IQ window must lie inside simulation')
        require(iq['sample_rate_hz']>=2046000,'At least 2.046 MS/s required for this L1 C/A implementation')
        require(abs(iq['intermediate_frequency_hz'])+1023000<iq['sample_rate_hz']/2+1e-6,'IF and C/A main lobe must fit Nyquist interval')
        require(iq['format'] in ('ci16_le','cf32_le'),'Unsupported IQ format')
        require(iq['chunk_samples']>0 and iq['adc_full_scale_sigma']>0,'Invalid IQ chunk/ADC scale')
        require(Path(iq['output_name']).name==iq['output_name'],'IQ output_name must be a basename')
        require(iq['output_name'].lower() not in {'run_summary.json','run_error.json','iq_metadata.json','config.resolved.json',
            'provenance.json','scene.json','metrics.json','trajectory_truth.csv','observations.csv','receiver_solution.csv','channel_truth.npz','acquisition_check.json',
            'imported_observations.csv','observation_import.json','trajectory_reference.csv'},
            'IQ output_name collides with a reserved experiment artifact')
        size=int(round(iq['sample_rate_hz']*iq['duration_s']))*(4 if iq['format']=='ci16_le' else 8)
        require(size<=iq['max_output_bytes'],'IQ expected size exceeds configured resource limit')
