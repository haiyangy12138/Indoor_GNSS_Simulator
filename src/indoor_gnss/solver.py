"""A reference least-squares receiver that assumes real satellites, not indoor transmitters."""
import numpy as np
from .geometry import C, LAMBDA_L1
from .physics import atmosphere


def expected(model,prn,t,enu):
    """No user truth, relay map or true relay position is accessed here."""
    cfg=model.cfg
    link=model.link(prn,t,model.to_ecef(enu))
    at=dict(cfg['atmosphere']); at['enabled']=cfg['solver']['apply_atmosphere'] and at['enabled']
    at['latitude_deg']=cfg['site']['latitude_deg']
    trop,iono=atmosphere(at,link['azimuth_rad'],link['elevation_rad'],cfg['site']['height_m']+enu[2])
    base=link['range_m']-C*link['clock_s']+trop
    return base+iono+C*link['tgd_s'],base-iono


def solve(model,rows,truth):
    cfg=model.cfg['solver']; h=model.cfg['time']['derivative_step_s']
    known_z=cfg['known_height_m']; dims=3 if known_z is None else 2
    groups={}
    for row in rows: groups.setdefault(float(row['time_s']),[]).append(row)
    reference={float(x['time_s']):x for x in truth} if truth is not None else None
    results=[]
    estimate=np.array(cfg['initial_enu_m'],float)
    if known_z is not None: estimate[2]=known_z
    bias=0.
    for t,observations in groups.items():
        obs=[o for o in observations if o['valid']]
        status='insufficient_observations'; iterations=0; cond=None; residual_rms=None
        velocity=np.full(3,np.nan); drift=np.nan
        if len(obs)>=dims+1:
            status='iteration_limit'
            for iterations in range(1,cfg['max_iterations']+1):
                pred=[]; jac=[]
                for o in obs:
                    p=o['prn']; e=expected(model,p,t,estimate)[0]
                    grad=[]
                    for d in range(dims):
                        delta=np.zeros(3); delta[d]=.1
                        grad.append((expected(model,p,t,estimate+delta)[0]-expected(model,p,t,estimate-delta)[0])/.2)
                    pred.append(e+bias); jac.append([*grad,1.])
                jac=np.array(jac); residual=np.array([o['pseudorange_m'] for o in obs])-pred
                cond=float(np.linalg.cond(jac))
                if np.linalg.matrix_rank(jac)<dims+1 or not np.isfinite(cond) or cond>1e12:
                    status='singular_geometry'; break
                delta=np.linalg.lstsq(jac,residual,rcond=None)[0]
                positional=delta[:dims]; scale=min(1.,cfg['max_step_m']/max(np.linalg.norm(positional),1e-30))
                estimate[:dims]+=positional*scale; bias+=delta[-1]
                if np.linalg.norm(positional)<cfg['position_tolerance_m'] and abs(delta[-1])<cfg['position_tolerance_m']:
                    status='converged'; break
            residual=np.array([o['pseudorange_m']-expected(model,o['prn'],t,estimate)[0]-bias for o in obs])
            residual_rms=float(np.sqrt(np.mean(residual**2)))
            if status=='converged':
                vs=[]; vg=[]
                for o in obs:
                    prn=o['prn']
                    station_rate=(expected(model,prn,t+h,estimate)[1]-expected(model,prn,t-h,estimate)[1])/(2*h)
                    grad=[]
                    for d in range(dims):
                        delta=np.zeros(3); delta[d]=.1
                        grad.append((expected(model,prn,t,estimate+delta)[1]-expected(model,prn,t,estimate-delta)[1])/.2)
                    vs.append(-LAMBDA_L1*o['doppler_hz']-station_rate)
                    vg.append([*grad,1.])
                v=np.linalg.lstsq(vg,vs,rcond=None)[0]
                velocity=np.r_[v[:2],0.] if dims==2 else v[:3]
                drift=v[-1]
        tr=reference[t] if reference is not None else None
        true_position=np.array([tr[x+'_m'] for x in 'xyz']) if tr is not None else None
        true_velocity=np.array([tr['v'+x+'_mps'] for x in 'xyz']) if tr is not None else None
        usable=status=='converged'
        comparable=usable and tr is not None
        result={'time_s':t,'status':status,'solution_dimensions':dims,'fixed_height_m':known_z,
            'valid_satellites':len(obs),'iterations':iterations,
            'geometry_condition_number':cond,'pseudorange_residual_rms_m':residual_rms,
            'estimated_clock_bias_m':float(bias) if usable else None,
            'estimated_clock_drift_mps':float(drift) if usable else None,
            'estimated_speed_mps':float(np.linalg.norm(velocity[:dims])) if usable else None,
            'estimated_horizontal_speed_mps':float(np.linalg.norm(velocity[:2])) if usable else None,
            'position_error_m':float(np.linalg.norm(estimate[:dims]-true_position[:dims])) if comparable else None,
            'velocity_vector_error_mps':float(np.linalg.norm(velocity[:dims]-true_velocity[:dims])) if comparable else None,
            'speed_magnitude_error_mps':float(abs(np.linalg.norm(velocity[:dims])-np.linalg.norm(true_velocity[:dims]))) if comparable else None,
            'horizontal_position_error_m':float(np.linalg.norm(estimate[:2]-true_position[:2])) if comparable else None,
            'horizontal_velocity_vector_error_mps':float(np.linalg.norm(velocity[:2]-true_velocity[:2])) if comparable else None,
            'horizontal_speed_magnitude_error_mps':float(abs(np.linalg.norm(velocity[:2])-np.linalg.norm(true_velocity[:2]))) if comparable else None}
        for j,axis in enumerate('xyz'[:dims]):
            result[f'estimated_{axis}_m']=float(estimate[j]) if usable else None
            result[f'estimated_v{axis}_mps']=float(velocity[j]) if usable else None
        results.append(result)
    successful=[r for r in results if r['status']=='converged']
    def stats(key):
        values=[r[key] for r in successful if r[key] is not None]
        if not values: return None
        a=np.array(values)
        return {'mean':float(np.mean(a)),'rms':float(np.sqrt(np.mean(a*a))),'p95':float(np.percentile(a,95)),'max':float(np.max(a))}
    pe=stats('position_error_m'); ve=stats('velocity_vector_error_mps')
    metrics={'epoch_count':len(results),'converged_count':len(successful),'convergence_fraction':len(successful)/len(results),
        'solution_dimensions':dims,'error_axes':list('xyz'[:dims]),'fixed_height_m':known_z,
        'reference_available':reference is not None,
        'position_error_m':pe,'velocity_vector_error_mps':ve,'speed_magnitude_error_mps':stats('speed_magnitude_error_mps'),
        'horizontal_position_error_m':stats('horizontal_position_error_m'),
        'horizontal_velocity_vector_error_mps':stats('horizontal_velocity_vector_error_mps'),
        'horizontal_speed_magnitude_error_mps':stats('horizontal_speed_magnitude_error_mps'),
        'position_normalization_m':cfg['position_normalization_m'],'velocity_normalization_mps':cfg['velocity_normalization_mps'],
        'position_mean_fraction':pe['mean']/cfg['position_normalization_m'] if pe else None,
        'velocity_mean_fraction':ve['mean']/cfg['velocity_normalization_mps'] if ve else None,
        'velocity_rms_fraction':ve['rms']/cfg['velocity_normalization_mps'] if ve else None,
        'warning':'Numerical convergence is not proof of true indoor observability; unsuccessful epochs excluded from errors, convergence_fraction must be reported.'}
    return results,metrics
