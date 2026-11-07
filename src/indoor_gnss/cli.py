"""CLI, provenance and exclusive output directories."""
import argparse
import csv
import hashlib
import json
import platform
import shutil
import sys
import time
from pathlib import Path
import numpy as np
from . import __version__
from .config import DEFAULT,load,configure_position_mode
from .engine import Model


def json_default(x):
    if isinstance(x,np.ndarray): return x.tolist()
    if isinstance(x,np.generic): return x.item()
    raise TypeError(type(x).__name__)


def write_json(path,obj):
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2,default=json_default,allow_nan=False)+'\n',encoding='utf-8')


def write_csv(path,rows):
    if not rows: return
    with path.open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)


def provenance(root,cfg,output,command):
    sources={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((root/'src').rglob('*.py'))}
    input_hashes={}
    active_inputs = []
    if cfg['satellites']['source'] == 'rinex':
        active_inputs.append(cfg['satellites']['rinex_nav_file'])
    imported=cfg['input_observations']['corrected_csv']
    if cfg['iq']['enabled'] and not imported:
        active_inputs.append(cfg['iq']['navigation_bits_file'])
    if imported:
        active_inputs.append(imported)
    for p in active_inputs:
        if p:
            data=Path(p)
            input_hashes[str(data)]=hashlib.sha256(data.read_bytes()).hexdigest()
    record={'version':__version__,'python':sys.version,'numpy':np.__version__,'platform':platform.platform(),
        'command':command,'seed':cfg['seed'],'source_sha256':sources,'input_sha256':input_hashes,
        'data_class':'EXTERNAL_CORRECTED_OBSERVATIONS' if imported else 'SYNTHETIC_RESEARCH_DATA',
        'observation_source':'external_corrected_csv' if imported else 'synthetic_model',
        'reference_kind':('configured_simulation_trajectory' if cfg['input_observations']['compare_reference'] else 'none') if imported else 'simulation_truth',
        'receiver_measurement_claim':False,
        'output_directory':str(output.resolve()),
        'limitations':['Synthetic orbits are not the real GPS constellation. Use GPS RINEX NAV for real satellite states.',
         'Observations are LOS path truth plus a statistical measurement error model, not decoded IQ.',
         'Single specular wall reflections are included in IQ only; no ray tracing of furniture, penetration or diffraction.',
         'Default IQ has C/A code but no valid LNAV; no standalone cold-fix claim.',
         'GPS L1 C/A only. No external GNSS-SDR end-to-end validation or independent real-RINEX cross-check has yet been performed.',
         'Cable group/phase delay assumed equal, atmosphere quasi-static at the outdoor antenna.',
         'Time uses GPST week/seconds, not UTC. No implicit leap-second conversion.'],
        'references':['https://www.navcen.uscg.gov/sites/default/files/pdf/gps/IS-GPS-200N.pdf',
         'https://gssc.esa.int/navipedia/index.php/Satellite_Coordinates_Computation',
         'https://gssc.esa.int/navipedia/index.php/GPS_and_Galileo_Satellite_Coordinates_Computation',
         'https://pmc.ncbi.nlm.nih.gov/articles/PMC4481917/']}
    if imported:
        record['limitations']=[
            'External corrected pseudoranges and Doppler are used unchanged; their origin is unspecified.',
            'No synthetic observations, extra noise, compensation or IQ are generated in import mode.',
            'No external ground truth is inferred. Optional errors compare only with the configured synthetic trajectory.',
            'Position and velocity depend on the configured GPS ephemeris, GPST origin, observable conventions and receiver model.',
            'Numerical convergence does not establish positioning accuracy.']
    return record


def run(cfg,output,command):
    output=Path(output)
    if output.exists(): raise FileExistsError(f'Refusing to overwrite existing output directory: {output}')
    parent=output.resolve().parent
    while not parent.exists(): parent=parent.parent
    imported=cfg['input_observations']['corrected_csv']
    model=None; import_metadata=None
    if imported:
        from .observation_import import load_corrected_observations
        model=Model(cfg)
        rows,reference,import_metadata=load_corrected_observations(imported,model)
    expected_iq=int(round(cfg['iq']['sample_rate_hz']*cfg['iq']['duration_s']))*(4 if cfg['iq']['format']=='ci16_le' else 8) if cfg['iq']['enabled'] and not imported else 0
    length=np.linalg.norm(np.array(cfg['trajectory']['end_enu_m'])-cfg['trajectory']['start_enu_m'])
    epochs=int(np.ceil(cfg['time']['duration_s']/cfg['time']['observation_interval_s']))+int(np.ceil(length/cfg['time']['trajectory_distance_step_m']))+3
    satellites=len(cfg['satellites']['prns']) or cfg['satellites']['count']
    paths=satellites*(1+len(cfg['multipath']['walls']) if cfg['multipath']['enabled'] and cfg['propagation']['mode']=='relay' else 1)
    expected_bytes=(Path(imported).stat().st_size+len(rows)*1500+10_000_000) if imported else expected_iq+epochs*satellites*1000+epochs*paths*8*4+10_000_000
    if shutil.disk_usage(parent).free<expected_bytes:
        raise ValueError(f'Insufficient free disk space; conservative estimate {expected_bytes} bytes')
    output.mkdir(parents=True)
    started=time.perf_counter()
    write_json(output/'config.resolved.json',cfg)
    root=Path(__file__).resolve().parents[2]
    try:
        record=provenance(root,cfg,output,command)
        write_json(output/'provenance.json',record)
        model=model if model is not None else Model(cfg)
        if imported:
            snapshot=output/'imported_observations.csv'
            shutil.copyfile(imported,snapshot)
            copied_hash=hashlib.sha256(snapshot.read_bytes()).hexdigest()
            if copied_hash!=import_metadata['sha256'] or record['input_sha256'][str(Path(imported))]!=copied_hash:
                raise ValueError('导入文件在读取期间发生变化，请保存文件后重新运行。')
            truth=reference if cfg['input_observations']['compare_reference'] else None
            import_metadata.update(reference_used=truth is not None,reference_kind=record['reference_kind'])
            write_json(output/'observation_import.json',import_metadata)
            if truth is not None:
                write_csv(output/'trajectory_reference.csv',truth)
            scene={'satellite_source':model.provider.describe(),'selected_prns':import_metadata['prns'],
                   'observation_source':'external_corrected_csv','channel_paths':[],
                   'reference_kind':record['reference_kind']}
        else:
            series,rows,truth=model.generate()
            write_csv(output/'trajectory_truth.csv',truth)
            np.savez_compressed(output/'channel_truth.npz',**series)
            txs=cfg['relay']['transmitters']
            scene={'satellite_source':model.provider.describe(),'selected_prns':model.prns,
                   'rejected_ephemerides':model.rejected_satellites,
                   'mapping':model.mapping,'transmitters':txs,'channel_paths':[{'prn':p,'path':path} for p,path in model.channels]}
        write_csv(output/'observations.csv',rows)
        write_json(output/'scene.json',scene)
        if cfg['solver']['enabled']:
            from .solver import solve
            solutions,metrics=solve(model,rows,truth)
            metrics['reference_kind']=record['reference_kind']
            write_csv(output/'receiver_solution.csv',solutions)
            write_json(output/'metrics.json',metrics)
        if cfg['iq']['enabled'] and not imported:
            from .iq import render_iq
            render_iq(cfg,series,output)
        summary={'status':'complete','seconds':time.perf_counter()-started,
                 'epoch_count':import_metadata['epoch_count'] if imported else len(truth),
                 'observation_rows':len(rows),'propagation_paths':0 if imported else len(model.channels),
                 'selected_prns':import_metadata['prns'] if imported else model.prns,
                 'observation_source':record['observation_source'],'reference_kind':record['reference_kind'],
                 'iq_generated':bool(cfg['iq']['enabled'] and not imported),
                 'solution_dimensions':3 if cfg['solver']['known_height_m'] is None else 2,
                 'fixed_height_m':cfg['solver']['known_height_m']}
        write_json(output/'run_summary.json',summary)
        return summary
    except Exception as exc:
        write_json(output/'run_error.json',{'type':type(exc).__name__,'message':str(exc)})
        raise


def main():
    parser=argparse.ArgumentParser(description='Generate synthetic GPS relay observations and L1 C/A baseband IQ')
    parser.add_argument('--config',type=Path)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--write-default',type=Path,help='Write all editable parameters and exit')
    parser.add_argument('--no-iq',action='store_true')
    parser.add_argument('--corrected-observations',type=Path,help='Use a local corrected observation CSV for position/velocity solving')
    parser.add_argument('--position-mode',choices=['2d','3d'],
                        help='Override solver dimensions; physical propagation remains three-dimensional')
    parser.add_argument('--height-m',type=float,
                        help='Fixed ENU height for 2D positioning, in metres')
    parser.add_argument('--validate-only',action='store_true')
    args=parser.parse_args()
    if args.write_default:
        if args.write_default.exists(): parser.error('--write-default target already exists')
        args.write_default.parent.mkdir(parents=True,exist_ok=True)
        write_json(args.write_default,DEFAULT); return
    try:
        cfg=configure_position_mode(load(args.config),args.position_mode,args.height_m)
        if args.corrected_observations:
            from .config import validate
            cfg['input_observations']['corrected_csv']=str(args.corrected_observations.resolve())
            validate(cfg)
    except (ValueError,OSError) as exc:
        parser.error(str(exc))
    if args.no_iq: cfg['iq']['enabled']=False
    if args.validate_only:
        model=Model(cfg)
        if cfg['input_observations']['corrected_csv']:
            from .observation_import import load_corrected_observations
            load_corrected_observations(cfg['input_observations']['corrected_csv'],model)
        print(json.dumps({'valid':True,'prns':model.prns,'mapping':model.mapping,
                          'solution_dimensions':3 if cfg['solver']['known_height_m'] is None else 2,
                          'fixed_height_m':cfg['solver']['known_height_m']},ensure_ascii=False)); return
    if args.output is None: parser.error('--output is required')
    try:
        print(json.dumps(run(cfg,args.output,sys.argv),ensure_ascii=False))
    except (ValueError,FileNotFoundError,FileExistsError) as exc:
        parser.exit(2,f'ERROR: {exc}\n')


if __name__=='__main__': main()
