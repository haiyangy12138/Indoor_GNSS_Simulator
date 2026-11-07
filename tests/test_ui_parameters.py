"""Ensure every public input can be named and edited in the parameter UI."""
import unittest

from indoor_gnss.config import DEFAULT
from indoor_gnss.ui_parameters import TAB_SECTIONS, describe


def input_fields(value, path=''):
    if isinstance(value, dict) and value:
        for key, child in value.items():
            yield from input_fields(child, path + '.' + key if path else key)
    elif path == 'relay.transmitters':
        for index, transmitter in enumerate(value):
            yield from input_fields(transmitter, path + '.' + str(index))
    else:
        yield path, value


class ParameterCatalogTests(unittest.TestCase):
    def test_all_default_inputs_have_specific_labels_and_types(self):
        count = 0
        for path, value in input_fields(DEFAULT):
            with self.subTest(path=path):
                item = describe(path, value)
                self.assertFalse(item['label'].startswith('扩展参数'))
                self.assertIn(path, item['help'])
                self.assertIn(item['kind'], {'bool', 'int', 'float', 'text', 'vector', 'list', 'json', 'path', 'optional_float'})
                count += 1
        self.assertGreater(count, 100)

    def test_groups_cover_every_top_level_section_once(self):
        sections = [section for title, group in TAB_SECTIONS for section in group]
        self.assertEqual(len(sections), len(set(sections)))
        self.assertEqual(set(sections), set(DEFAULT) - {'compensation'})
        self.assertIn('input_observations', sections)
        self.assertNotIn('补偿', [title for title, _ in TAB_SECTIONS])

    def test_dynamic_transmitters_and_prn_override_are_described(self):
        point = describe('relay.transmitters.3.clock.bias_s', 0.)
        self.assertTrue(point['label'].startswith('发射点 4'))
        self.assertNotIn('扩展参数', point['label'])
        override = describe('compensation.per_prn.16.mode', 'delay_coupled')
        self.assertTrue(override['label'].startswith('PRN 16'))
        self.assertEqual(override['choices'], ['delay_coupled', 'independent_frequency'])

    def test_nullable_and_structured_inputs_are_not_plain_text(self):
        self.assertEqual(describe('solver.known_height_m', None)['kind'], 'optional_float')
        self.assertEqual(describe('satellites.rinex_nav_file', None)['kind'], 'path')
        self.assertEqual(describe('relay.mapping', {})['kind'], 'json')
        self.assertEqual(describe('site.room_size_enu_m', [30., 10., 5.])['kind'], 'vector')


if __name__ == '__main__':
    unittest.main()
