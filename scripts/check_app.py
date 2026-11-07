"""Exercise the actual Tk controls and worker without controlling the OS desktop."""
import csv
import hashlib
import json
from pathlib import Path
import sys
import time
import tkinter as tk

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / 'src'))
from indoor_gnss.app import SimulatorApp


def check_mode(use_z):
    root = tk.Tk()
    root.withdraw()
    app = SimulatorApp(root)
    try:
        app.fields['seed']['variables'][0].set('20261106')
        app.fields['time.duration_s']['variables'][0].set('2.2')
        app.use_z.set(use_z)
        app.mode_changed()
        app.run_button.invoke()
        assert app.process is not None, app.log_box.get('1.0', 'end')
        deadline = time.monotonic() + 45
        while app.process is not None:
            root.update()
            if time.monotonic() > deadline:
                app.stop_run()
                raise TimeoutError('App worker did not finish within 45 seconds')
            time.sleep(.03)
        run = app.last_output
        summary = json.loads((run / 'run_summary.json').read_text(encoding='utf-8'))
        config = json.loads((run / 'config.resolved.json').read_text(encoding='utf-8'))
        metrics = json.loads((run / 'metrics.json').read_text(encoding='utf-8'))
        assert summary['status'] == 'complete'
        assert config['seed'] == 20261106
        assert config['time']['duration_s'] == 2.2
        assert metrics['solution_dimensions'] == (3 if use_z else 2)
        with (run / 'receiver_solution.csv').open(encoding='utf-8-sig', newline='') as stream:
            fields = csv.DictReader(stream).fieldnames
        assert ('estimated_z_m' in fields) == use_z
        assert ('estimated_vz_mps' in fields) == use_z
        assert metrics['error_axes'] == (list('xyz') if use_z else list('xy'))
        info = dict(output=str(run), dimensions=metrics['solution_dimensions'],
                    seed=config['seed'], duration_s=config['time']['duration_s'],
                    epoch_count=summary['epoch_count'], observation_rows=summary['observation_rows'],
                    position_error_mean_m=metrics['position_error_m']['mean'])
        print(json.dumps(info, ensure_ascii=True), flush=True)
        return run, info
    finally:
        if app.process is not None and app.process.poll() is None:
            app.process.terminate()
            app.process.wait(timeout=5)
        root.destroy()


if __name__ == '__main__':
    xy, info_xy = check_mode(False)
    xyz, info_xyz = check_mode(True)
    equivalent = {}
    for name in ('trajectory_truth.csv', 'observations.csv', 'signal.iq'):
        equivalent[name] = hashlib.sha256((xy / name).read_bytes()).digest() == hashlib.sha256((xyz / name).read_bytes()).digest()
    assert all(equivalent.values()), equivalent
    report = dict(data_class='SYNTHETIC_RESEARCH_DATA', gui_control_smoke='pass',
                  run_2d=info_xy, run_3d=info_xyz, identical_physical_outputs=equivalent,
                  command=[sys.executable, *sys.argv])
    with (xy / 'app_check.json').open('x', encoding='utf-8') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
    print(json.dumps({'report':str(xy / 'app_check.json'), 'checks':equivalent}, ensure_ascii=True))
