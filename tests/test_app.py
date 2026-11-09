"""Parameter form tests; no OS-window automation or lingering main loop."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from indoor_gnss.config import DEFAULT, load
from indoor_gnss.app import iter_fields, set_at, SimulatorApp


class FormStructureTests(unittest.TestCase):
    def test_iter_fields_preserves_structured_values_and_expands_transmitters(self):
        cfg = deepcopy(DEFAULT)
        cfg['relay']['mapping'] = {'3': 'V1'}
        cfg['compensation']['per_prn'] = {'3': {'range_offset_m': 2}}
        fields = dict(iter_fields(cfg))
        self.assertEqual(fields['relay.mapping'], {'3': 'V1'})
        self.assertEqual(fields['compensation.per_prn'], {'3': {'range_offset_m': 2}})
        self.assertNotIn('relay.mapping.3', fields)
        self.assertIn('relay.transmitters.1.clock.bias_s', fields)
        self.assertEqual(fields['trajectory.start_enu_m'], [0., 5., 1.])

    def test_set_at_updates_coordinates_and_transmitter_paths(self):
        cfg = deepcopy(DEFAULT)
        set_at(cfg, 'relay.transmitters.1.clock.bias_s', 1e-6)
        set_at(cfg, 'trajectory.start_enu_m', [1., 4., 1.])
        self.assertEqual(cfg['relay']['transmitters'][1]['clock']['bias_s'], 1e-6)
        self.assertEqual(cfg['trajectory']['start_enu_m'], [1., 4., 1.])
        self.assertEqual(DEFAULT['relay']['transmitters'][1]['clock']['bias_s'], 0.)


class FormRoundtripTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import tkinter as tk
        except ImportError as error:
            raise unittest.SkipTest(f'Tk UI unavailable for in-process form tests: {error}')
        cls.tk = tk
        try:
            root = tk.Tk()
            root.withdraw()
            root.destroy()
        except tk.TclError as error:
            raise unittest.SkipTest(f'Tk UI unavailable for in-process form tests: {error}')

    def setUp(self):
        self.root = self.tk.Tk()
        self.root.withdraw()
        self.app = SimulatorApp(self.root)

    def tearDown(self):
        self.root.destroy()

    def test_default_roundtrip_and_dimension_toggle_preserve_other_parameters(self):
        expected = deepcopy(DEFAULT)
        expected['solver']['known_height_m'] = 1.
        self.assertEqual(self.app.collect(), expected)
        self.app.use_z.set(True)
        self.app.mode_changed()
        expected['solver']['known_height_m'] = None
        self.assertEqual(self.app.collect(), expected)
        self.app.use_z.set(False)
        self.app.height.set('0')
        expected['solver']['known_height_m'] = 0.
        self.assertEqual(self.app.collect(), expected)

    def test_scalar_vector_boolean_and_optional_import_reach_configuration(self):
        self.app.fields['seed']['variables'][0].set('12345')
        self.app.fields['trajectory.speed_mps']['variables'][0].set('10')
        self.app.fields['time.duration_s']['variables'][0].set('4')
        self.app.fields['trajectory.start_enu_m']['variables'][0].set('1')
        self.app.fields['iq.enabled']['variables'][0].set(False)
        self.assertFalse(any(path.startswith('compensation.') for path in self.app.fields))
        self.app.fields['input_observations.corrected_csv']['variables'][0].set('corrected.csv')
        self.app.fields['input_observations.compare_reference']['variables'][0].set(True)
        cfg = self.app.collect()
        self.assertEqual(cfg['seed'], 12345)
        self.assertEqual(cfg['trajectory']['speed_mps'], 10.)
        self.assertEqual(cfg['trajectory']['start_enu_m'], [1., 5., 1.])
        self.assertFalse(cfg['iq']['enabled'])
        self.assertEqual(cfg['input_observations']['corrected_csv'], str((self.app.base_directory/'corrected.csv').resolve()))
        self.assertTrue(cfg['input_observations']['compare_reference'])
        self.app.clear_import()
        self.assertIsNone(self.app.collect()['input_observations']['corrected_csv'])

    def test_no_hidden_legacy_compensation_and_import_does_not_clear_iq_preference(self):
        self.app.config['compensation']['default']['range_offset_m'] = 7.
        self.assertEqual(self.app.collect()['compensation'], DEFAULT['compensation'])
        self.app.fields['input_observations.corrected_csv']['variables'][0].set('corrected.csv')
        self.assertEqual(str(self.app.fields['iq.enabled']['controls'][0].cget('state')), 'disabled')
        self.assertTrue(self.app.collect()['iq']['enabled'])
        self.app.clear_import()
        self.assertEqual(str(self.app.fields['iq.enabled']['controls'][0].cget('state')), 'normal')

    def test_waypoint_editor_keeps_travel_order_across_language_switch(self):
        field = self.app.fields['trajectory.waypoints_enu_m']
        editor = field['controls'][0]
        editor.delete('1.0', 'end')
        editor.insert('1.0', '[[10, 5, 1],\n [10, 8, 1]]')
        self.app.toggle_language()

        trajectory = self.app.collect()['trajectory']
        self.assertEqual(trajectory['waypoints_enu_m'], [[10, 5, 1], [10, 8, 1]])
        self.assertEqual(trajectory['start_enu_m'], DEFAULT['trajectory']['start_enu_m'])
        self.assertEqual(trajectory['end_enu_m'], DEFAULT['trajectory']['end_enu_m'])

    def test_save_to_new_directory_preserves_relative_input_identity(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            base = Path(directory)
            self.app.base_directory = base / 'source'
            self.app.fields['satellites.rinex_nav_file']['variables'][0].set('data/nav.22n')
            target = base / 'other' / 'saved.json'
            with patch('indoor_gnss.app.filedialog.asksaveasfilename', return_value=str(target)):
                saved = self.app.save_dialog()
            self.assertEqual(saved, target.resolve(), self.app.log_box.get('1.0', 'end'))
            expected = str((base / 'source' / 'data' / 'nav.22n').resolve())
            self.assertEqual(load(saved)['satellites']['rinex_nav_file'], expected)
            self.assertEqual(self.app.collect()['satellites']['rinex_nav_file'], expected)


if __name__ == '__main__':
    unittest.main()
