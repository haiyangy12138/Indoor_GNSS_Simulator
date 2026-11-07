"""External corrected values must reach the receiver unchanged, with honest provenance."""
from copy import deepcopy
import csv
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from indoor_gnss.config import DEFAULT, validate
from indoor_gnss.engine import Model
from indoor_gnss.solver import solve
from indoor_gnss.cli import run
from indoor_gnss.ui_config import load_for_app


class ImportPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = deepcopy(DEFAULT)
        cls.cfg['propagation']['mode'] = 'direct'
        cls.cfg['observations']['add_noise'] = False
        cls.cfg['atmosphere']['enabled'] = False
        cls.cfg['receiver_clock'].update(bias_s=0., drift_sps=0.)
        cls.cfg['iq']['enabled'] = False
        cls.cfg['time'].update(duration_s=.4, observation_interval_s=.05)
        cls.cfg['trajectory'].update(start_time_s=.02, end_enu_m=[3.,5.,1.],speed_mps=10.,acceleration_time_s=.02)
        validate(cls.cfg)
        cls.model = Model(cls.cfg)
        cls.series, cls.rows, cls.truth = cls.model.generate()

    def write_input(self, folder, rows=None):
        path = Path(folder)/'corrected.csv'
        with path.open('x',encoding='utf-8-sig',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=['time_s','prn','pseudorange_m','doppler_hz','valid'])
            writer.writeheader()
            for row in (self.rows if rows is None else rows):
                writer.writerow({key:row[key] for key in writer.fieldnames})
        return path

    def test_import_only_solves_uploaded_rows_without_reference_or_iq(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            source=self.write_input(directory,self.rows[:16])
            before=source.read_bytes()
            cfg=deepcopy(self.cfg)
            cfg['input_observations']['corrected_csv']=str(source.resolve())
            cfg['solver']['known_height_m']=1.
            # Deliberately inactive, invalid I/Q window/input must not block solving.
            cfg['iq'].update(enabled=True,start_s=999.,navigation_bits_file='does_not_exist.json')
            validate(cfg)
            target=Path(directory)/'result'
            with patch.object(Model,'generate',side_effect=AssertionError('Must not generate synthetic observations')):
                result=run(cfg,target,['import-pipeline-test'])
            self.assertEqual(result['observation_rows'],16)
            self.assertFalse(result['iq_generated'])
            self.assertEqual(result['observation_source'],'external_corrected_csv')
            self.assertFalse((target/'signal.iq').exists())
            self.assertFalse((target/'channel_truth.npz').exists())
            self.assertFalse((target/'trajectory_truth.csv').exists())
            self.assertFalse((target/'trajectory_reference.csv').exists())
            self.assertEqual(source.read_bytes(),before)
            self.assertEqual((target/'imported_observations.csv').read_bytes(),before)
            with (target/'receiver_solution.csv').open(encoding='utf-8-sig',newline='') as stream:
                answers=list(csv.DictReader(stream))
            self.assertTrue(all(row['position_error_m']=='' for row in answers))
            self.assertTrue(all(row['estimated_speed_mps']!='' for row in answers))
            self.assertTrue(all('estimated_z_m' not in row for row in answers))
            metrics=json.loads((target/'metrics.json').read_text(encoding='utf-8'))
            self.assertIsNone(metrics['position_error_m'])
            self.assertFalse(metrics['reference_available'])
            provenance=json.loads((target/'provenance.json').read_text(encoding='utf-8'))
            self.assertEqual(provenance['data_class'],'EXTERNAL_CORRECTED_OBSERVATIONS')
            self.assertEqual(provenance['input_sha256'][str(source.resolve())],hashlib.sha256(before).hexdigest())

    def test_optional_reference_recovers_same_xyz_solution_as_original_observations(self):
        expected,_=solve(self.model,self.rows,self.truth)
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            source=self.write_input(directory)
            cfg=deepcopy(self.cfg)
            cfg['input_observations'].update(corrected_csv=str(source.resolve()),compare_reference=True)
            target=Path(directory)/'result'
            run(cfg,target,['reference-test'])
            self.assertTrue((target/'trajectory_reference.csv').exists())
            self.assertFalse((target/'trajectory_truth.csv').exists())
            with (target/'receiver_solution.csv').open(encoding='utf-8-sig',newline='') as stream:
                actual=list(csv.DictReader(stream))
            for row,previous in zip(actual,expected):
                self.assertEqual(float(row['time_s']),previous['time_s'])
                for axis in 'xyz':
                    self.assertAlmostEqual(float(row[f'estimated_{axis}_m']),previous[f'estimated_{axis}_m'],places=7)
                    self.assertAlmostEqual(float(row[f'estimated_v{axis}_mps']),previous[f'estimated_v{axis}_mps'],places=7)
            metrics=json.loads((target/'metrics.json').read_text(encoding='utf-8'))
            self.assertEqual(metrics['reference_kind'],'configured_simulation_trajectory')
            self.assertLess(metrics['position_error_m']['max'],.001)

    def test_app_loading_old_compensation_clears_it_and_keeps_import_optional(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            path=Path(directory)/'old.json'
            path.write_text(json.dumps({'compensation':{'default':{'range_offset_m':999.}}}),encoding='utf-8')
            cfg=load_for_app(path)
            self.assertEqual(cfg['compensation'],DEFAULT['compensation'])
            self.assertIsNone(cfg['input_observations']['corrected_csv'])

    def test_no_reference_and_all_invalid_rows_reports_no_successful_fix(self):
        rows=deepcopy(self.rows)
        for row in rows:
            row['valid']=False
        answers,metrics=solve(self.model,rows,None)
        self.assertEqual(metrics['converged_count'],0)
        self.assertIsNone(metrics['position_error_m'])
        self.assertTrue(all(row['status']=='insufficient_observations' for row in answers))

    def test_empty_import_path_retains_generation(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            result=run(deepcopy(self.cfg),Path(directory)/'baseline',['baseline-test'])
            self.assertEqual(result['observation_source'],'synthetic_model')
            self.assertTrue((Path(directory)/'baseline'/'trajectory_truth.csv').exists())


if __name__=='__main__':
    unittest.main()
