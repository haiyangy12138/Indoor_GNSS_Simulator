"""Exercise the optional-import form and actual worker in an invisible Tk harness."""
from copy import deepcopy
from datetime import datetime
import csv
import hashlib
import json
from pathlib import Path
import sys
import time
import tkinter as tk
import uuid

PROJECT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PROJECT/'src'))
from indoor_gnss.app import SimulatorApp
from indoor_gnss.ui_config import load_for_app


def through_form(config, source=None, use_z=False, compare=False):
    root=tk.Tk()
    root.withdraw()
    app=SimulatorApp(root)
    try:
        app.replace_config(deepcopy(config),'导入功能验收用仿真场景',PROJECT/'configs')
        assert not any(path.startswith('compensation.') for path in app.fields)
        assert all('补偿'!=app.notebook.tab(tab,'text') for tab in app.notebook.tabs())
        app.use_z.set(use_z)
        app.mode_changed()
        app.height.set('1')
        field=app.fields['input_observations.corrected_csv']['variables'][0]
        assert app.collect()['input_observations']['corrected_csv'] is None
        if source:
            field.set(str(source))
            assert str(app.fields['iq.enabled']['controls'][0].cget('state'))=='disabled'
            app.clear_import()
            assert app.collect()['input_observations']['corrected_csv'] is None
            field.set(str(source))
            app.fields['input_observations.compare_reference']['variables'][0].set(compare)
            # These are deliberately irrelevant in import mode, to detect hidden regeneration.
            app.fields['iq.enabled']['variables'][0].set(True)
            app.fields['iq.start_s']['variables'][0].set('999')
            app.fields['observations.add_noise']['variables'][0].set(True)
        app.run_button.invoke()
        assert app.process is not None,app.log_box.get('1.0','end')
        deadline=time.monotonic()+60
        while app.process is not None:
            root.update()
            if time.monotonic()>deadline:
                raise TimeoutError('App worker did not finish')
            time.sleep(.03)
        output=app.last_output
        summary=json.loads((output/'run_summary.json').read_text(encoding='utf-8'))
        metrics=json.loads((output/'metrics.json').read_text(encoding='utf-8'))
        assert summary['status']=='complete'
        assert metrics['convergence_fraction']==1.
        with (output/'receiver_solution.csv').open(encoding='utf-8-sig',newline='') as stream:
            solutions=list(csv.DictReader(stream))
        assert ('estimated_z_m' in solutions[0])==use_z
        assert all(row['estimated_speed_mps'] for row in solutions)
        if source:
            assert not summary['iq_generated']
            assert not (output/'signal.iq').exists()
            assert not (output/'trajectory_truth.csv').exists()
            assert not (output/'channel_truth.npz').exists()
            assert (output/'trajectory_reference.csv').exists()==compare
            assert (metrics['position_error_m'] is not None)==compare
            assert (output/'imported_observations.csv').read_bytes()==source.read_bytes()
            with source.open(encoding='utf-8-sig',newline='') as stream:
                original=list(csv.DictReader(stream))
            with (output/'observations.csv').open(encoding='utf-8-sig',newline='') as stream:
                imported=list(csv.DictReader(stream))
            original_values=sorted((float(r['time_s']),int(r['prn']),float(r['pseudorange_m']),float(r['doppler_hz'])) for r in original)
            imported_values=[(float(r['time_s']),int(r['prn']),float(r['pseudorange_m']),float(r['doppler_hz'])) for r in imported]
            assert original_values==imported_values
        info={'output':str(output),'dimensions':metrics['solution_dimensions'],
              'observation_source':summary['observation_source'],'observation_rows':summary['observation_rows'],
              'converged_count':metrics['converged_count'],'reference_kind':metrics['reference_kind']}
        print(json.dumps(info,ensure_ascii=True),flush=True)
        return output,info
    finally:
        if app.process is not None and app.process.poll() is None:
            app.process.terminate()
            app.process.wait(timeout=5)
        root.destroy()


if __name__=='__main__':
    config=load_for_app(PROJECT/'configs/direct_baseline.json')
    # A synthetic direct, noise-free reference is used only as an import fixture.
    baseline,base_info=through_form(config)
    source=baseline/'observations.csv'
    before=hashlib.sha256(source.read_bytes()).hexdigest()
    xy,xy_info=through_form(config,source,False,False)
    xyz,xyz_info=through_form(config,source,True,True)
    assert hashlib.sha256(source.read_bytes()).hexdigest()==before
    report={'status':'pass','test_data_origin':'synthetic_direct_noise_free_fixture',
            'source_unchanged':True,'source_sha256':before,'baseline':base_info,
            'import_2d':xy_info,'import_3d_with_reference':xyz_info,
            'command':[sys.executable,*sys.argv]}
    report_path=baseline/'import_app_check.json'
    with report_path.open('x',encoding='utf-8') as stream:
        json.dump(report,stream,ensure_ascii=False,indent=2)
    print(json.dumps({'report':str(report_path)},ensure_ascii=True))
