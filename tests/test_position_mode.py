"""User-visible XY/XYZ selection, known-height constraints and metric semantics."""
from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import numpy as np

from indoor_gnss.config import DEFAULT, configure_position_mode, validate
from indoor_gnss.engine import Model
from indoor_gnss.solver import solve
from indoor_gnss.cli import main


class PositionModeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = deepcopy(DEFAULT)
        cls.cfg['propagation']['mode'] = 'direct'
        cls.cfg['observations']['add_noise'] = False
        cls.cfg['atmosphere']['enabled'] = False
        cls.cfg['receiver_clock'].update(bias_s=0., drift_sps=0.)
        cls.cfg['iq']['enabled'] = False
        cls.cfg['time'].update(duration_s=.4, observation_interval_s=.05)
        cls.cfg['trajectory'].update(start_time_s=.02, end_enu_m=[3., 5., 1.],
                                     speed_mps=10., acceleration_time_s=.02)
        validate(cls.cfg)
        cls.series, cls.rows, cls.truth = Model(cls.cfg).generate()

    def model(self, mode, height=None):
        return Model(configure_position_mode(deepcopy(self.cfg), mode, height))

    def test_xy_recovery_and_output_omit_z_estimates(self):
        answers, metrics = solve(self.model('2d', 1.), self.rows, self.truth)
        self.assertEqual(metrics['solution_dimensions'], 2)
        self.assertEqual(metrics['error_axes'], ['x', 'y'])
        self.assertEqual(metrics['convergence_fraction'], 1.)
        self.assertLess(metrics['position_error_m']['max'], .001)
        self.assertEqual(metrics['position_error_m'], metrics['horizontal_position_error_m'])
        for row in answers:
            self.assertNotIn('estimated_z_m', row)
            self.assertNotIn('estimated_vz_mps', row)
            self.assertEqual(row['fixed_height_m'], 1.)
            self.assertEqual(row['solution_dimensions'], 2)
            self.assertEqual(row['velocity_vector_error_mps'], row['horizontal_velocity_vector_error_mps'])

    def test_xy_metrics_and_solution_do_not_use_vertical_truth(self):
        original, metrics = solve(self.model('2d', 1.), self.rows, self.truth)
        changed_truth = deepcopy(self.truth)
        for row in changed_truth:
            row['z_m'] += 100.
            row['vz_mps'] = 123.
        changed, changed_metrics = solve(self.model('2d', 1.), self.rows, changed_truth)
        self.assertEqual(original, changed)
        self.assertEqual(metrics, changed_metrics)

    def test_switch_changes_solver_without_flattening_propagation(self):
        series, rows, truth = self.model('2d', 1.).generate()
        self.assertEqual(rows, self.rows)
        self.assertEqual(truth, self.truth)
        for key in series:
            np.testing.assert_array_equal(series[key], self.series[key])
        self.assertTrue(all(row['z_m'] == 1. for row in truth))

    def test_xyz_keeps_z_outputs_and_three_dimensional_errors(self):
        answers, metrics = solve(self.model('3d'), self.rows, self.truth)
        self.assertEqual(metrics['solution_dimensions'], 3)
        self.assertEqual(metrics['error_axes'], ['x', 'y', 'z'])
        self.assertIsNone(metrics['fixed_height_m'])
        self.assertLess(metrics['position_error_m']['max'], .001)
        for row, truth in zip(answers, self.truth):
            self.assertIn('estimated_z_m', row)
            self.assertIn('estimated_vz_mps', row)
            error = np.array([row[f'estimated_{a}_m'] - truth[f'{a}_m'] for a in 'xyz'])
            self.assertAlmostEqual(row['position_error_m'], np.linalg.norm(error), places=12)
            self.assertAlmostEqual(row['horizontal_position_error_m'], np.linalg.norm(error[:2]), places=12)

    def test_xy_uses_three_satellites_while_xyz_needs_four(self):
        prns = list(dict.fromkeys(row['prn'] for row in self.rows))[:3]
        rows = [row for row in self.rows if row['prn'] in prns]
        answers_2d, metrics_2d = solve(self.model('2d', 1.), rows, self.truth)
        self.assertEqual(metrics_2d['convergence_fraction'], 1.)
        self.assertTrue(all(row['valid_satellites'] == 3 for row in answers_2d))
        answers_3d, metrics_3d = solve(self.model('3d'), rows, self.truth)
        self.assertEqual(metrics_3d['convergence_fraction'], 0.)
        self.assertIsNone(metrics_3d['position_error_m'])
        self.assertTrue(all(row['status'] == 'insufficient_observations' for row in answers_3d))

    def test_mode_override_preserves_zero_height_and_can_restore_xyz(self):
        cfg = configure_position_mode(deepcopy(self.cfg), '2d', 0.)
        self.assertEqual(cfg['solver']['known_height_m'], 0.)
        configure_position_mode(cfg, '2d')
        self.assertEqual(cfg['solver']['known_height_m'], 0.)
        configure_position_mode(cfg, '3d')
        self.assertIsNone(cfg['solver']['known_height_m'])
        cfg['solver']['initial_enu_m'][2] = 1.5
        configure_position_mode(cfg, '2d')
        self.assertEqual(cfg['solver']['known_height_m'], 1.5)

    def test_invalid_height_and_incompatible_overrides_are_rejected(self):
        for value in [-1., 6., float('nan'), float('inf'), True, '1']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                configure_position_mode(deepcopy(self.cfg), '2d', value)
        with self.assertRaisesRegex(ValueError, 'only available'):
            configure_position_mode(deepcopy(self.cfg), '3d', 0.)
        with self.assertRaisesRegex(ValueError, 'requires 2D'):
            configure_position_mode(deepcopy(self.cfg), None, 1.)

    def test_cli_passes_mode_and_height_to_run(self):
        arguments = ['simulate.py', '--output', 'unused', '--position-mode', '2d', '--height-m', '0', '--no-iq']
        with patch.object(sys, 'argv', arguments), redirect_stdout(io.StringIO()), \
                patch('indoor_gnss.cli.run', return_value={'status': 'complete'}) as run:
            main()
        cfg, output, command = run.call_args.args
        self.assertEqual(cfg['solver']['known_height_m'], 0.)
        self.assertFalse(cfg['iq']['enabled'])
        self.assertEqual(output, Path('unused'))
        self.assertEqual(command, arguments)

    def test_cli_rejects_height_in_xyz_before_writing_data(self):
        arguments = ['simulate.py', '--output', 'unused', '--position-mode', '3d', '--height-m', '1']
        with patch.object(sys, 'argv', arguments), redirect_stderr(io.StringIO()), \
                patch('indoor_gnss.cli.run') as run:
            with self.assertRaises(SystemExit) as raised:
                main()
        self.assertEqual(raised.exception.code, 2)
        run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
