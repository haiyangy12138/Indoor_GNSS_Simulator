"""Corrected CSVs reach the receiver unchanged, with strict input validation."""
from copy import deepcopy
import csv
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from indoor_gnss.config import DEFAULT, validate
from indoor_gnss.engine import Model
from indoor_gnss.observation_import import load_corrected_observations, REQUIRED_FIELDS
from indoor_gnss.solver import solve


class ObservationImportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cfg = deepcopy(DEFAULT)
        cfg['propagation']['mode'] = 'direct'
        cfg['observations']['add_noise'] = False
        cfg['atmosphere']['enabled'] = False
        cfg['receiver_clock'].update(bias_s=0., drift_sps=0.)
        cfg['iq']['enabled'] = False
        cfg['time'].update(duration_s=.4, observation_interval_s=.05)
        cfg['trajectory'].update(start_time_s=.02, end_enu_m=[3., 5., 1.],
                                  speed_mps=10., acceleration_time_s=.02)
        validate(cfg)
        cls.model = Model(cfg)
        cls.series, cls.rows, cls.truth = cls.model.generate()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'corrected.csv'

    def write_rows(self, rows, fields=None, bom=True):
        with self.path.open('w', encoding='utf-8-sig' if bom else 'utf-8', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=fields or list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

    def test_existing_observations_csv_roundtrip_has_identical_solutions(self):
        self.write_rows(self.rows)
        imported, reference, metadata = load_corrected_observations(self.path, self.model)
        expected = sorted(self.rows, key=lambda row: (row['time_s'], row['prn']))
        for original, current in zip(expected, imported):
            for field in (*REQUIRED_FIELDS, 'valid'):
                self.assertEqual(current[field], original[field])
        original_solutions, original_metrics = solve(self.model, self.rows, self.truth)
        answers, metrics = solve(self.model, imported, reference)
        # Input summation order is defined by PRN for imports; tolerate tiny
        # floating-point changes from the generator's PRN ordering.
        for a, b in zip(original_solutions, answers):
            self.assertEqual(a['status'], b['status'])
            for field in ('estimated_x_m', 'estimated_y_m', 'estimated_z_m',
                          'estimated_vx_mps', 'estimated_vy_mps', 'estimated_vz_mps'):
                self.assertAlmostEqual(a[field], b[field], places=6)
        self.assertEqual(metrics['convergence_fraction'], original_metrics['convergence_fraction'])
        self.assertEqual(metadata['sha256'], hashlib.sha256(self.path.read_bytes()).hexdigest())
        self.assertEqual(metadata['input_origin'], 'unspecified')
        self.assertEqual(metadata['reference_kind'], 'configured_simulation_trajectory')
        self.assertFalse(metadata['measurements_modified'])

    def test_minimal_off_grid_partial_data_are_not_filled_or_recompensated(self):
        prn = self.model.prns[0]
        rows = [{'time_s': .1234567, 'prn': prn, 'pseudorange_m': 12345678.9,
                 'doppler_hz': -987.65, 'x_m': 999999.}]
        self.write_rows(rows, bom=False)
        imported, reference, metadata = load_corrected_observations(self.path, self.model)
        self.assertEqual(len(imported), 1)
        self.assertEqual(len(reference), 1)
        self.assertEqual(imported[0]['pseudorange_m'], 12345678.9)
        self.assertEqual(imported[0]['doppler_hz'], -987.65)
        self.assertTrue(imported[0]['valid'])
        self.assertNotEqual(reference[0]['x_m'], 999999.)
        self.assertNotIn('x_m', imported[0])
        self.assertEqual(reference[0]['time_s'], .1234567)
        answers, metrics = solve(self.model, imported, reference)
        self.assertEqual(len(answers), 1)
        self.assertEqual(answers[0]['status'], 'insufficient_observations')
        self.assertEqual(answers[0]['valid_satellites'], 1)
        self.assertFalse(metadata['missing_observations_filled'])

    def test_valid_flag_and_sorted_epochs_are_preserved(self):
        prn = self.model.prns[0]
        rows = [dict(time_s=.2, prn=prn, pseudorange_m=2e7, doppler_hz=10., valid='0'),
                dict(time_s=.1, prn=prn, pseudorange_m=2e7, doppler_hz=-10., valid='TRUE')]
        self.write_rows(rows)
        imported, reference, _ = load_corrected_observations(self.path, self.model)
        self.assertEqual([row['time_s'] for row in imported], [.1, .2])
        self.assertEqual([row['valid'] for row in imported], [True, False])
        self.assertEqual([row['time_s'] for row in reference], [.1, .2])

    def test_missing_duplicate_headers_and_empty_files_are_rejected(self):
        for content in ('', 'time_s,prn,pseudorange_m,doppler_hz\n',
                        'time_s,prn,doppler_hz\n',
                        'time_s,prn,pseudorange_m,doppler_hz,prn\n'):
            with self.subTest(content=content):
                self.path.write_text(content, encoding='utf-8')
                with self.assertRaises(ValueError):
                    load_corrected_observations(self.path, self.model)

    def test_invalid_values_and_duplicate_keys_are_rejected(self):
        original = dict(time_s=.1, prn=self.model.prns[0], pseudorange_m=2e7, doppler_hz=10., valid='true')
        patches = [dict(time_s=-.1), dict(time_s=.5), dict(time_s='nan'),
                   dict(pseudorange_m=0), dict(pseudorange_m=-1),
                   dict(pseudorange_m='inf'), dict(doppler_hz='nan'),
                   dict(prn='03'), dict(prn='3.0'), dict(prn='G03'),
                   dict(prn=33), dict(prn=0), dict(valid='maybe'), dict(valid='')]
        unselected = next(p for p in range(1, 33) if p not in self.model.prns)
        patches.append(dict(prn=unselected))
        for patch in patches:
            with self.subTest(patch=patch):
                row = {**original, **patch}
                self.write_rows([row])
                with self.assertRaises(ValueError):
                    load_corrected_observations(self.path, self.model)
        self.write_rows([original, original])
        with self.assertRaisesRegex(ValueError, '重复'):
            load_corrected_observations(self.path, self.model)

    def test_malformed_csv_and_missing_values_are_rejected(self):
        self.path.write_text(f'time_s,prn,pseudorange_m,doppler_hz\n0.1,{self.model.prns[0]},20000000\n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'doppler_hz'):
            load_corrected_observations(self.path, self.model)
        self.path.write_text('time_s,prn,pseudorange_m,doppler_hz\n"unterminated', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'CSV'):
            load_corrected_observations(self.path, self.model)

    def test_resource_limits_encoding_and_missing_file_have_clear_errors(self):
        row = dict(time_s=.1, prn=self.model.prns[0], pseudorange_m=2e7, doppler_hz=0.)
        self.write_rows([row, {**row, 'time_s': .2}])
        with patch('indoor_gnss.observation_import.MAX_FILE_BYTES', 8):
            with self.assertRaisesRegex(ValueError, 'MiB'):
                load_corrected_observations(self.path, self.model)
        with patch('indoor_gnss.observation_import.MAX_ROWS', 1):
            with self.assertRaisesRegex(ValueError, '条观测'):
                load_corrected_observations(self.path, self.model)
        self.path.write_bytes(b'\xff')
        with self.assertRaisesRegex(ValueError, 'UTF-8'):
            load_corrected_observations(self.path, self.model)
        with self.assertRaisesRegex(ValueError, '无法读取'):
            load_corrected_observations(self.path.with_name('missing.csv'), self.model)


if __name__ == '__main__':
    unittest.main()
