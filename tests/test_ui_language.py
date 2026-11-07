"""Language switching must preserve an unfinished form and its UI state."""
import unittest

from indoor_gnss.app import SimulatorApp
from indoor_gnss.ui_english import translate_error


class ErrorTranslationTests(unittest.TestCase):
    def test_common_import_errors_and_unknown_message(self):
        examples = {
            '导入 CSV 缺少必要字段：prn, doppler_hz': 'Imported CSV is missing required fields: prn, doppler_hz',
            '导入 CSV 第 7 行：pseudorange_m 必须大于零，单位为 m。':
                'Imported CSV line 7: pseudorange_m must be greater than zero, in meters.',
            '导入 CSV 第 9 行：valid 必须为 true、false、1 或 0。':
                'Imported CSV line 9: valid must be true, false, 1 or 0.',
            '导入 CSV 为空，请提供已补偿的伪距和多普勒观测。':
                'Imported CSV is empty; provide corrected pseudorange and Doppler observations.',
        }
        for message, expected in examples.items():
            with self.subTest(message=message):
                self.assertEqual(translate_error(message), expected)
        unknown = '未识别的诊断信息: file xyz'
        self.assertEqual(translate_error(unknown), unknown)


class LanguageSwitchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import tkinter as tk
        except ImportError as error:
            raise unittest.SkipTest(f'Tk UI unavailable: {error}')
        try:
            root = tk.Tk()
            root.withdraw()
            root.destroy()
        except tk.TclError as error:
            raise unittest.SkipTest(f'Tk UI unavailable: {error}')
        cls.tk = tk

    def setUp(self):
        self.root = self.tk.Tk()
        self.root.withdraw()
        self.app = SimulatorApp(self.root)

    def tearDown(self):
        self.root.destroy()

    def test_button_switches_titles_and_tabs_both_ways(self):
        chinese_title = self.root.title()
        chinese_tabs = [self.app.notebook.tab(tab, 'text') for tab in self.app.notebook.tabs()]
        chinese_run = self.app.run_button.cget('text')
        self.assertEqual(self.app.language, 'zh')

        self.app.language_button.invoke()
        english_tabs = [self.app.notebook.tab(tab, 'text') for tab in self.app.notebook.tabs()]
        self.assertEqual(self.app.language, 'en')
        self.assertNotEqual(self.root.title(), chinese_title)
        self.assertEqual(len(english_tabs), len(chinese_tabs))
        self.assertTrue(all(en != zh for en, zh in zip(english_tabs, chinese_tabs)))
        self.assertNotEqual(self.app.run_button.cget('text'), chinese_run)

        self.app.language_button.invoke()
        self.assertEqual(self.app.language, 'zh')
        self.assertEqual(self.root.title(), chinese_title)
        self.assertEqual([self.app.notebook.tab(tab, 'text') for tab in self.app.notebook.tabs()], chinese_tabs)
        self.assertEqual(self.app.run_button.cget('text'), chinese_run)

    def test_unfinished_invalid_values_and_ui_state_survive_switching(self):
        self.app.fields['seed']['variables'][0].set('1e-')
        mapping = self.app.fields['relay.mapping']['controls'][0]
        mapping.delete('1.0', 'end')
        mapping.insert('1.0', '{"3": ')
        self.app.use_z.set(True)
        self.app.mode_changed()
        self.app.height.set('unfinished')
        self.app.fields['input_observations.corrected_csv']['variables'][0].set('unfinished.csv')
        self.app.search.set('seed')
        selected = self.app.notebook.index('current')
        visible = {path: field['frame'].winfo_manager()
                   for path, field in self.app.fields.items()}
        self.assertTrue(self.app.dirty)
        self.assertEqual(str(self.app.height_entry.cget('state')), 'disabled')
        self.assertEqual(str(self.app.fields['iq.enabled']['controls'][0].cget('state')), 'disabled')

        for expected_language in ('en', 'zh'):
            with self.subTest(language=expected_language):
                self.app.language_button.invoke()
                self.assertEqual(self.app.language, expected_language)
                self.assertEqual(self.app.fields['seed']['variables'][0].get(), '1e-')
                self.assertEqual(self.app.fields['relay.mapping']['controls'][0].get('1.0', 'end-1c'), '{"3": ')
                self.assertTrue(self.app.use_z.get())
                self.assertEqual(self.app.height.get(), 'unfinished')
                self.assertEqual(str(self.app.height_entry.cget('state')), 'disabled')
                self.assertEqual(self.app.fields['input_observations.corrected_csv']['variables'][0].get(), 'unfinished.csv')
                self.assertEqual(str(self.app.fields['iq.enabled']['controls'][0].cget('state')), 'disabled')
                self.assertEqual(self.app.search.get(), 'seed')
                self.assertEqual(self.app.notebook.index('current'), selected)
                self.assertEqual({path: field['frame'].winfo_manager()
                                  for path, field in self.app.fields.items()}, visible)
                self.assertTrue(self.app.dirty)

    def test_switch_while_busy_preserves_running_state(self):
        process = object()  # No subprocess or new experiment is started.
        self.app.process = process
        self.app.set_busy(True)
        self.app.progress.configure(value=23)
        self.app.output.set('existing-run-path')
        for language in ('en', 'zh'):
            with self.subTest(language=language):
                self.app.language_button.invoke()
                self.assertEqual(self.app.language, language)
                self.assertIs(self.app.process, process)
                self.assertEqual(str(self.app.run_button.cget('state')), 'disabled')
                self.assertEqual(str(self.app.stop_button.cget('state')), 'normal')
                self.assertTrue(all(str(button.cget('state')) == 'disabled'
                                    for button in self.app.toolbar.winfo_children()))
                self.assertEqual(float(self.app.progress.cget('value')), 23.0)
                self.assertEqual(self.app.output.get(), 'existing-run-path')
        self.app.progress.stop()
        self.app.process = None


if __name__ == '__main__':
    unittest.main()
