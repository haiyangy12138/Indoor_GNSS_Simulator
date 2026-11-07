"""Editor boundaries: typed values, portable inputs and non-destructive saving."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from indoor_gnss.config import DEFAULT, load
from indoor_gnss.ui_config import parse_value, prepare_config, load_for_edit, save_config
from indoor_gnss.cli import provenance


class UIConfigTests(unittest.TestCase):
    def test_numeric_parsing_accepts_scientific_values_without_rounding(self):
        self.assertEqual(parse_value('time.duration_s', '2e-3', 2., 'float'), .002)
        self.assertEqual(parse_value('seed', '123', 1, 'int'), 123)
        for invalid in ('1.5', '1e3', 'true', ''):
            with self.subTest(invalid=invalid), self.assertRaisesRegex(ValueError, 'seed'):
                parse_value('seed', invalid, 1, 'int')
        for invalid in ('NaN', 'Infinity', True):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                parse_value('time.duration_s', invalid, 2., 'float')

    def test_optional_fields_and_structured_values(self):
        self.assertIsNone(parse_value('solver.known_height_m', '', None, 'optional_float'))
        self.assertEqual(parse_value('solver.known_height_m', '0', None, 'optional_float'), 0.)
        self.assertIsNone(parse_value('satellites.rinex_nav_file', ' ', None, 'path'))
        self.assertEqual(parse_value('trajectory.start_enu_m', '[0, 5, 1]', [0, 5, 1], 'vector'), [0, 5, 1])
        self.assertEqual(parse_value('relay.mapping', '{"3": "V1"}', {}, 'json'), {'3': 'V1'})
        self.assertTrue(parse_value('iq.enabled', True, True, 'bool'))
        with self.assertRaises(ValueError):
            parse_value('iq.enabled', '1', True, 'bool')
        with self.assertRaises(ValueError):
            parse_value('relay.mapping', '[]', {}, 'json')
        with self.assertRaises(ValueError):
            parse_value('trajectory.start_enu_m', '[NaN, 0, 0]', [], 'vector')

    def test_relative_external_paths_survive_save_in_a_different_directory(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            root = Path(folder)
            source_dir = root / 'source'
            source_dir.mkdir()
            config_path = source_dir / 'config.json'
            config_path.write_text(json.dumps({'satellites': {'rinex_nav_file': 'data/nav.22n'},
                                               'iq': {'navigation_bits_file': '../navbits.json'}}), encoding='utf-8')
            cfg = load_for_edit(config_path)
            output = save_config(cfg, root / 'saved' / 'copy.json', source_dir)
            again = load(output)
            self.assertEqual(again['satellites']['rinex_nav_file'], str((source_dir / 'data/nav.22n').resolve()))
            self.assertEqual(again['iq']['navigation_bits_file'], str((root / 'navbits.json').resolve()))

    def test_per_prn_defaults_expand_without_mutating_the_editor_value(self):
        patch = {'compensation': {'default': {'range_offset_m': 2.},
                                  'per_prn': {'3': {'range_rate_mps': .1}}}}
        original = deepcopy(patch)
        cfg = prepare_config(patch, Path.cwd())
        self.assertEqual(patch, original)
        self.assertEqual(cfg['compensation']['per_prn']['3']['range_offset_m'], 2.)
        self.assertEqual(cfg['compensation']['per_prn']['3']['range_rate_mps'], .1)
        self.assertEqual(cfg['compensation']['per_prn']['3']['mode'], 'delay_coupled')

    def test_unknown_parameters_and_incorrect_types_are_rejected(self):
        cases = [
            {'seed': -1}, {'seed': True}, {'time': {'gps_week': 2443.5}},
            {'time': {'gps_week': -1}}, {'time': {'duration_s': True}},
            {'site': {'room_size_enu_m': [30, 10, True]}},
            {'satellites': {'prns': [3, 3]}},
            {'solver': {'known_height_m': True}}, {'solver': {'max_iterations': 0}},
            {'observations': {'add_noise': 'false'}},
            {'relay': {'mapping': {'3': 1}}},
            {'compensation': {'per_prn': {'3': {'range_offest_m': 2}}}},
            {'observations': {'typo': 0}}, {'relay': 'not an object'},
        ]
        for patch in cases:
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                prepare_config(patch, Path.cwd())

    def test_transmitter_coordinates_and_clock_types_are_checked(self):
        for mutate in (
            lambda tx: tx.update(position_enu_m=[1, 2]),
            lambda tx: tx.update(position_enu_m=[True, 2, 5]),
            lambda tx: tx['clock'].update(drift_sps='0'),
            lambda tx: tx.update(unexpected=1),
        ):
            cfg = deepcopy(DEFAULT)
            mutate(cfg['relay']['transmitters'][0])
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                prepare_config(cfg, Path.cwd())

    def test_save_never_overwrites_and_invalid_values_create_no_file(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            root = Path(folder)
            target = save_config({}, root / 'kept.json', root)
            before = target.read_bytes()
            with self.assertRaises(FileExistsError):
                save_config({'seed': 42}, target, root)
            self.assertEqual(target.read_bytes(), before)
            invalid_target = root / 'new_folder' / 'invalid.json'
            with self.assertRaises(ValueError):
                save_config({'seed': -1}, invalid_target, root)
            self.assertFalse(invalid_target.parent.exists())

    def test_existing_examples_load_without_editor_only_regressions(self):
        project = Path(__file__).resolve().parents[1]
        for path in (project / 'configs').glob('*.json'):
            with self.subTest(path=path.name):
                cfg = load_for_edit(path)
                self.assertIn('time', cfg)
                self.assertIn('solver', cfg)

    def test_provenance_ignores_missing_files_for_disabled_inputs(self):
        project = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            cfg = deepcopy(DEFAULT)
            cfg['satellites']['source'] = 'synthetic'
            cfg['satellites']['rinex_nav_file'] = str(Path(folder) / 'missing_nav.22n')
            cfg['iq']['enabled'] = False
            cfg['iq']['navigation_bits_file'] = str(Path(folder) / 'missing_bits.json')
            result = provenance(project, cfg, Path(folder) / 'unused', ['test-provenance'])
            self.assertEqual(result['input_sha256'], {})

    def test_provenance_hashes_only_active_existing_inputs(self):
        project = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            root = Path(folder)
            nav = root / 'nav.22n'
            nav_payload = b'Unit-test payload for input hashing, not a valid ephemeris.'
            nav.write_bytes(nav_payload)
            cfg = deepcopy(DEFAULT)
            cfg['satellites']['source'] = 'rinex'
            cfg['satellites']['rinex_nav_file'] = str(nav)
            cfg['iq']['enabled'] = False
            cfg['iq']['navigation_bits_file'] = str(root / 'missing_bits.json')
            result = provenance(project, cfg, root / 'unused', ['test-provenance'])
            expected = {str(nav): hashlib.sha256(nav_payload).hexdigest()}
            self.assertEqual(result['input_sha256'], expected)
            bits = root / 'bits.json'
            bits.write_bytes(b'{}')
            cfg['iq']['enabled'] = True
            cfg['iq']['navigation_bits_file'] = str(bits)
            result = provenance(project, cfg, root / 'unused', ['test-provenance'])
            expected[str(bits)] = hashlib.sha256(b'{}').hexdigest()
            self.assertEqual(result['input_sha256'], expected)


if __name__ == '__main__':
    unittest.main()
