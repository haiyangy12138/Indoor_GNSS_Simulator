"""Truth paths and stochastic *modeled* observations. No real receiver measurements are claimed."""
from copy import deepcopy
import numpy as np
from .geometry import C, LAMBDA_L1, geodetic_to_ecef, enu_rotation, Trajectory, specular_image
from .physics import SyntheticGPS, space_link, atmosphere, compensation, clock_m

WALLS={'west':(0,0),'east':(0,1),'south':(1,0),'north':(1,1),'floor':(2,0),'ceiling':(2,1)}


class Model:
    def __init__(self, cfg):
        self.cfg=cfg
        site=cfg['site']; sc=cfg['satellites']; tm=cfg['time']
        self.origin=geodetic_to_ecef(site['latitude_deg'],site['longitude_deg'],site['height_m'])
        self.rot=enu_rotation(site['latitude_deg'],site['longitude_deg'])
        self.antenna=self.to_ecef(site['outdoor_antenna_enu_m'])
        self.trajectory=Trajectory(cfg['trajectory'])
        if sc['source']=='rinex':
            from .ephemeris import RinexGPS
            if not sc['rinex_nav_file']: raise ValueError('RINEX mode requires rinex_nav_file')
            self.provider=RinexGPS(sc['rinex_nav_file'],max_age_s=sc['max_ephemeris_age_s'],allow_unhealthy=sc['allow_unhealthy'])
        else:
            self.provider=SyntheticGPS(sc)
        visible=[]
        self.rejected_satellites={}
        ref=self.antenna if cfg['propagation']['mode']=='relay' else self.to_ecef(self.trajectory.start)
        for prn in self.provider.prns:
            try:
                link=self.link(int(prn),0.,ref)
            except ValueError as exc:
                if sc['source']!='rinex': raise
                self.rejected_satellites[int(prn)]=str(exc)
                continue
            if np.rad2deg(link['elevation_rad'])>=sc['elevation_mask_deg']:
                visible.append((link['elevation_rad'],int(prn)))
        visible.sort(reverse=True)
        requested=sc['prns']
        self.prns=[int(p) for p in requested] if requested else [p for _,p in visible[:sc['count']]]
        if len(self.prns)!=(len(requested) if requested else sc['count']):
            raise ValueError(f'Only {len(visible)} satellites visible, requested {sc["count"]}; change time/site/mask/count')
        if len(set(self.prns))!=len(self.prns) or not set(self.prns)<=set(p for _,p in visible):
            raise ValueError('Explicit PRNs must be unique, healthy and visible at start')
        txs=cfg['relay']['transmitters']
        self.mapping={p:cfg['relay']['mapping'].get(str(p),txs[k%len(txs)]['id']) for k,p in enumerate(self.prns)}
        self.txs={x['id']:x for x in txs}
        self.channels=[]
        for p in self.prns:
            self.channels.append((p,'los'))
            if cfg['multipath']['enabled'] and cfg['propagation']['mode']=='relay':
                self.channels.extend((p,w) for w in cfg['multipath']['walls'])
        # Stochastic FREQUENCY error, integrated into smooth clock bias on a fixed grid.
        cc=cfg['receiver_clock']; step=cc['clock_grid_s']
        self.clock_times=np.arange(-.2,tm['duration_s']+.2+step,step)
        rng=np.random.default_rng(np.random.SeedSequence([cfg['seed'],123]))
        alpha=np.exp(-step/cc['frequency_gm_tau_s'])
        freq=np.empty(len(self.clock_times)); freq[0]=rng.normal(0,cc['frequency_gm_sigma_sps'])
        for k in range(1,len(freq)):
            freq[k]=alpha*freq[k-1]+rng.normal()*cc['frequency_gm_sigma_sps']*np.sqrt(1-alpha*alpha)
        self.clock_bias=np.r_[0.,np.cumsum((freq[1:]+freq[:-1])*.5*step)]
        self.clock_bias-=np.interp(0.,self.clock_times,self.clock_bias)

    def to_ecef(self, enu):
        return self.origin+self.rot.T@np.asarray(enu)

    def link(self,p,t,xyz):
        tm=self.cfg['time']
        return space_link(self.provider,p,tm['gps_week'],tm['gps_sow']+t,xyz,self.rot,self.cfg['propagation'])

    def receiver_clock_m(self,t):
        return clock_m(self.cfg['receiver_clock'],t)+C*np.interp(t,self.clock_times,self.clock_bias)

    def user_at(self,t):
        # t is receiver-clock elapsed time; trajectory is specified on the physical GPS timeline.
        physical=t-self.receiver_clock_m(t)/C
        return self.trajectory.at(physical)

    def channel(self,t,p,path='los'):
        cfg=self.cfg
        rxclock=self.receiver_clock_m(t)
        physical=t-rxclock/C
        user,velocity=self.trajectory.at(physical)
        cp=cfg['compensation']['per_prn'].get(str(p),cfg['compensation']['default'])
        range_comp,carrier_comp,comp_doppler=compensation(cp,physical)
        valid=True; phase=0.; gain=1.; indoor=0.; fixed=0.; txclock=0.
        if cfg['propagation']['mode']=='relay':
            tx=self.txs[self.mapping[p]]
            source=np.array(tx['position_enu_m'],float)
            if path!='los':
                axis,upper=WALLS[path]
                coordinate=cfg['site']['room_size_enu_m'][axis]*upper
                source,valid=specular_image(source,user,axis,coordinate,cfg['site']['room_size_enu_m'])
                gain=cfg['multipath']['reflection_amplitude']
                phase+=cfg['multipath']['reflection_phase_rad']
            indoor=np.linalg.norm(user-source)
            if indoor<cfg['propagation']['min_path_m']:
                raise ValueError('User too close to a modeled point antenna for far-field path model')
            gain*= (tx['reference_distance_m']/indoor)**(tx['path_loss_exponent']/2)*10**(-tx['excess_loss_db']/20)
            gain*=float(valid)
            fixed=tx['cable_length_m']/tx['cable_velocity_factor']+C*tx['processing_delay_s']
            txclock=clock_m(tx['clock'],physical)
            phase+=tx['phase_offset_rad']
            # Retard sky reception by actual relay group delay, NOT receiver clock or carrier-only phase.
            arrival_a=physical-(indoor+fixed+range_comp)/C
            link=self.link(p,arrival_a,self.antenna)
            height=cfg['site']['height_m']+cfg['site']['outdoor_antenna_enu_m'][2]
        else:
            if abs(range_comp)+abs(carrier_comp)>1e-8:
                raise ValueError('Direct baseline requires zero compensation')
            link=self.link(p,physical,self.to_ecef(user))
            height=cfg['site']['height_m']+user[2]
        at=deepcopy(cfg['atmosphere']); at['latitude_deg']=cfg['site']['latitude_deg']
        trop,iono=atmosphere(at,link['azimuth_rad'],link['elevation_rad'],height)
        common=link['range_m']+indoor+fixed+rxclock+txclock-C*link['clock_s']+trop
        code=common+iono+C*link['tgd_s']+range_comp
        carrier=common-iono+carrier_comp
        cn0=cfg['observations']['reference_cn0_dbhz']+20*np.log10(max(gain,1e-30))
        visible=np.rad2deg(link['elevation_rad'])>=cfg['satellites']['elevation_mask_deg']
        return {'code_path_m':code,'carrier_path_m':carrier,'gain_linear':gain*float(visible),
            'phase_offset_rad':phase,'cn0_dbhz':cn0,'satellite_xyz':link['satellite_xyz'],
            'satellite_clock_s':link['clock_s'],'tgd_s':link['tgd_s'],
            'azimuth_deg':np.rad2deg(link['azimuth_rad']),'elevation_deg':np.rad2deg(link['elevation_rad']),
            'space_range_m':link['range_m'],'indoor_path_m':indoor,'fixed_relay_path_m':fixed,
            'receiver_clock_m':rxclock,'relay_clock_m':txclock,'troposphere_m':trop,'ionosphere_code_m':iono,
            'range_comp_m':range_comp,'compensation_doppler_hz':comp_doppler,'valid':visible and valid,
            'user_enu_m':user,'user_velocity_mps':velocity}

    def generate(self):
        cfg=self.cfg; tm=cfg['time']; dt=tm['observation_interval_s']; h=tm['derivative_step_s']
        times=np.arange(0.,tm['duration_s'],dt)
        distances=np.arange(0,self.trajectory.length,tm['trajectory_distance_step_m'])
        distances=np.r_[distances,self.trajectory.length]
        distance_times=[self.trajectory.at_distance(d) for d in distances]
        # Convert physical trajectory epochs to receiver-clock epochs by fixed point.
        distance_clock_times=[]
        for ptime in distance_times:
            rt=ptime
            for _ in range(4): rt=ptime+self.receiver_clock_m(rt)/C
            distance_clock_times.append(rt)
        times=np.unique(np.round(np.r_[times,tm['duration_s'],distance_clock_times],12))
        times=times[(times>=0)&(times<=tm['duration_s'])]
        n,k=len(times),len(self.channels)
        series={'t_s':times,'prn':np.array([p for p,_ in self.channels],int),
            'cn0_dbhz':np.full(k,cfg['observations']['reference_cn0_dbhz'])}
        for name in ['code_path_m','carrier_path_m','gain_linear','phase_offset_rad']:
            series[name]=np.zeros((n,k))
        rows=[]; truth=[]
        code_errors=np.zeros(len(self.prns)); dopp_errors=np.zeros(len(self.prns))
        rng=np.random.default_rng(np.random.SeedSequence([cfg['seed'],456]))
        oc=cfg['observations']
        for ti,t in enumerate(times):
            user,vel=self.user_at(t)
            truth.append({'time_s':t,'gps_week':tm['gps_week']+int((tm['gps_sow']+t)//604800),
                'gps_sow':(tm['gps_sow']+t)%604800,'x_m':user[0],'y_m':user[1],'z_m':user[2],
                'vx_mps':vel[0],'vy_mps':vel[1],'vz_mps':vel[2],
                'distance_sample':any(abs(t-d)<5e-10 for d in distance_clock_times)})
            pi=0
            for ci,(prn,path) in enumerate(self.channels):
                v=self.channel(t,prn,path)
                for name in ['code_path_m','carrier_path_m','gain_linear','phase_offset_rad']:
                    series[name][ti,ci]=v[name]
                if path!='los': continue
                left=self.channel(t-h,prn); right=self.channel(t+h,prn)
                rate=(right['carrier_path_m']-left['carrier_path_m'])/(2*h)
                dopp=-rate/LAMBDA_L1
                previous_dt=dt if ti==0 else t-times[ti-1]
                innovations=rng.standard_normal(2)
                r=oc['noise_code_doppler_correlation']
                innovations[1]=r*innovations[0]+np.sqrt(max(0,1-r*r))*innovations[1]
                for errors,key,z in [(code_errors,'code_noise_correlation_s',innovations[0]),(dopp_errors,'doppler_noise_correlation_s',innovations[1])]:
                    a=np.exp(-previous_dt/oc[key]) if oc[key]>0 else 0.
                    errors[pi]=a*errors[pi]+np.sqrt(1-a*a)*z if ti else z
                scale=10**(np.clip(oc['reference_cn0_for_noise_dbhz']-v['cn0_dbhz'],-100,100)/20)
                code_noise=code_errors[pi]*oc['code_sigma_m']*scale if oc['add_noise'] else 0.
                dop_noise=dopp_errors[pi]*oc['doppler_sigma_hz']*scale if oc['add_noise'] else 0.
                valid=v['valid'] and rng.random()>=oc['dropout_probability']
                if oc['apply_cn0_gate']: valid=valid and v['cn0_dbhz']>=oc['minimum_cn0_dbhz']
                row={'time_s':t,'prn':prn,'transmitter_id':self.mapping[prn] if cfg['propagation']['mode']=='relay' else 'direct',
                    'pseudorange_truth_m':v['code_path_m'],'carrier_path_truth_m':v['carrier_path_m'],
                    'pseudorange_m':v['code_path_m']+code_noise,'doppler_truth_hz':dopp,'doppler_hz':dopp+dop_noise,
                    'carrier_range_rate_mps':rate,'code_noise_m':code_noise,'doppler_noise_hz':dop_noise,
                    'valid':valid,'receiver_clock_drift_mps':(self.receiver_clock_m(t+h)-self.receiver_clock_m(t-h))/(2*h)}
                for name in ['cn0_dbhz','azimuth_deg','elevation_deg','space_range_m','indoor_path_m','fixed_relay_path_m',
                             'receiver_clock_m','relay_clock_m','troposphere_m','ionosphere_code_m','range_comp_m','compensation_doppler_hz','satellite_clock_s','tgd_s']:
                    row[name]=v[name]
                for j,axis in enumerate('xyz'): row[f'satellite_{axis}_ecef_m']=v['satellite_xyz'][j]
                rows.append(row); pi+=1
        return series,rows,truth
