"""Local Tk application: typed inputs, immutable run snapshots, background simulation."""
from copy import deepcopy
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback
import uuid
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from .config import DEFAULT
from .ui_config import load_for_app, parse_value, prepare_config, save_config
from .ui_parameters import describe, TAB_SECTIONS
from .ui_english import TAB_TITLES, translate_error

PROJECT = Path(__file__).resolve().parents[2]
STRUCTURED = {'relay.mapping', 'compensation.per_prn'}


def iter_fields(value, prefix=''):
    if prefix in STRUCTURED:
        yield prefix, value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from iter_fields(item, f'{prefix}.{key}' if prefix else key)
    elif prefix == 'relay.transmitters':
        for index, transmitter in enumerate(value):
            yield from iter_fields(transmitter, f'{prefix}.{index}')
    else:
        yield prefix, value


def set_at(config, path, value):
    parts = path.split('.')
    node = config
    for part in parts[:-1]:
        node = node[int(part)] if isinstance(node, list) else node[part]
    key = int(parts[-1]) if isinstance(node, list) else parts[-1]
    node[key] = value


class ScrollPage(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.canvas = tk.Canvas(self, highlightthickness=0, background='#ffffff')
        bar = ttk.Scrollbar(self, orient='vertical', command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=bar.set)
        bar.pack(side='right', fill='y')
        self.canvas.pack(side='left', fill='both', expand=True)
        self.body = ttk.Frame(self.canvas, padding=(16, 10))
        self.window = self.canvas.create_window(0, 0, anchor='nw', window=self.body)
        self.body.columnconfigure(0, weight=1)
        self.body.bind('<Configure>', lambda e: self.canvas.configure(scrollregion=self.canvas.bbox('all')))
        self.canvas.bind('<Configure>', lambda e: self.canvas.itemconfigure(self.window, width=e.width))


class SimulatorApp:
    def __init__(self, root):
        self.root = root
        self.language = 'zh'
        self.localized_widgets = []
        self.default_source = True
        self.loading = True
        self.dirty = False
        self.process = None
        self.last_output = None
        self.run_log = None
        self.fields = {}
        self.pages = []
        self.base_directory = PROJECT / 'configs'
        self.config = load_for_app()
        self.config['solver']['known_height_m'] = 1.
        root.title('室内定位仿真 · 参数控制台')
        width = min(1140, root.winfo_screenwidth() - 100)
        height = min(880, root.winfo_screenheight() - 100)
        root.geometry(f'{width}x{height}')
        root.minsize(880, 640)
        root.option_add('*Font', ('Microsoft YaHei', 10))
        style = ttk.Style(root)
        if 'vista' in style.theme_names():
            style.theme_use('vista')
        style.configure('TFrame', background='white')
        style.configure('TLabel', background='white')
        style.configure('TLabelframe', background='white')
        style.configure('TLabelframe.Label', background='white')
        style.configure('Title.TLabel', font=('Microsoft YaHei', 16, 'bold'))
        style.configure('Help.TLabel', foreground='#526176')
        shell = ttk.Frame(root, padding=16)
        shell.pack(fill='both', expand=True)
        header = ttk.Frame(shell)
        header.pack(fill='x')
        self.localize(ttk.Label(header, style='Title.TLabel'), '室内定位仿真', 'Indoor Positioning Simulator').pack(side='left')
        self.language_button = ttk.Button(header, text='English', command=self.toggle_language)
        self.language_button.pack(side='right')
        self.data_kind = tk.StringVar(value='未补偿仿真数据')
        ttk.Label(header, textvariable=self.data_kind, style='Help.TLabel').pack(side='left', padx=18)
        self.toolbar = ttk.Frame(shell)
        self.toolbar.pack(fill='x', pady=(10, 8))
        for zh, en, callback in [('加载配置', 'Load configuration', self.load_dialog),
                                 ('另存配置', 'Save configuration', self.save_dialog),
                                 ('恢复默认参数', 'Restore defaults', self.reset_defaults),
                                 ('检查参数', 'Check parameters', self.validate_inputs)]:
            self.localize(ttk.Button(self.toolbar, command=callback), zh, en).pack(side='left', padx=(0, 8))
        self.source_label = tk.StringVar(value='当前配置：默认参数（二维定位，高度 1 m）')
        ttk.Label(shell, textvariable=self.source_label, style='Help.TLabel').pack(fill='x', pady=(0, 8))
        mode = ttk.Frame(shell)
        mode.pack(fill='x', pady=(0, 8))
        self.use_z = tk.BooleanVar(value=False)
        self.localize(ttk.Checkbutton(mode, variable=self.use_z, command=self.mode_changed),
                      '计算 Z 方向（三维定位）', 'Solve Z (3D positioning)').pack(side='left')
        self.localize(ttk.Label(mode), '二维固定高度（m）：', '2D fixed height (m):').pack(side='left', padx=(18, 0))
        self.height = tk.StringVar(value='1')
        self.height_entry = ttk.Entry(mode, textvariable=self.height, width=12)
        self.height_entry.pack(side='left')
        self.height.trace_add('write', lambda *a: self.mark_dirty())
        self.search = tk.StringVar()
        self.localize(ttk.Label(mode), '查找参数：', 'Find parameter:').pack(side='left', padx=(18, 0))
        ttk.Entry(mode, textvariable=self.search, width=23).pack(side='left', fill='x', expand=True)
        self.search.trace_add('write', lambda *a: self.filter_fields())
        self.notebook = ttk.Notebook(shell)
        self.notebook.pack(fill='both', expand=True)
        self.help_text = tk.StringVar(value='坐标采用 x 东、y 北、z 上；二维解算仍保留传播高度。')
        ttk.Label(shell, textvariable=self.help_text, style='Help.TLabel', wraplength=1030).pack(fill='x', pady=(6, 5))
        bottom = ttk.Frame(shell)
        bottom.pack(fill='x')
        self.run_button = ttk.Button(bottom, text='生成仿真数据', command=self.start_run)
        self.run_button.pack(side='left')
        self.stop_button = self.localize(ttk.Button(bottom, command=self.stop_run, state='disabled'), '停止', 'Stop')
        self.stop_button.pack(side='left', padx=8)
        self.open_button = self.localize(ttk.Button(bottom, command=self.open_output, state='disabled'), '打开结果文件夹', 'Open results folder')
        self.open_button.pack(side='left')
        self.progress = ttk.Progressbar(bottom, mode='indeterminate', length=160)
        self.progress.pack(side='right')
        self.output = tk.StringVar()
        ttk.Entry(shell, textvariable=self.output, state='readonly').pack(fill='x', pady=(8, 4))
        self.log_box = tk.Text(shell, height=4, wrap='word', background='#f4f7fb', relief='flat')
        self.log_box.pack(fill='x')
        self.log_box.configure(state='disabled')
        root.bind_all('<MouseWheel>', self.mousewheel, add='+')
        root.protocol('WM_DELETE_WINDOW', self.on_close)
        root.report_callback_exception = self.callback_error
        self.render_fields()
        self.loading = False
        self.log(self.tr('数据导入可留空。选择已补偿 CSV 后计算位置和速度；留空时生成未补偿仿真观测。', 'Import is optional. Select corrected CSV to calculate position and velocity; leave empty to generate uncorrected observations.'))

    def tr(self, zh, en):
        return en if self.language == 'en' else zh

    def localize(self, widget, zh, en):
        self.localized_widgets.append((widget, zh, en))
        widget.configure(text=self.tr(zh, en))
        return widget

    def toggle_language(self):
        # Update existing widgets in place: raw/invalid edits, focus, selection,
        # page, scroll positions and any running process all remain untouched.
        self.language = 'en' if self.language == 'zh' else 'zh'
        self.root.title(self.tr('室内定位仿真 · 参数控制台', 'Indoor Positioning Simulator · Parameters'))
        self.language_button.configure(text=self.tr('English', '中文'))
        live = []
        for widget, zh, en in self.localized_widgets:
            if widget.winfo_exists():
                widget.configure(text=self.tr(zh, en))
                live.append((widget, zh, en))
        self.localized_widgets = live
        for index, page in enumerate(self.pages):
            self.notebook.tab(page, text=TAB_TITLES[index] if self.language == 'en' else TAB_SECTIONS[index][0])
        for path, field in self.fields.items():
            meta = describe(path, field['value'], self.language)
            field['meta'] = meta
            field['label'].configure(text=meta['label'])
            field['help_label'].configure(text=meta['help'].split('\n')[0])
        if self.default_source:
            source = self.tr('默认参数（二维定位，高度 1 m）', 'Default parameters (2D, height 1 m)')
        else:
            source = self.source_value
        self.source_label.set(self.tr('当前配置：', 'Current configuration: ') + source)
        focus = self.root.focus_get()
        focused_field = next((field for field in self.fields.values() if focus in field['controls']), None)
        self.help_text.set(focused_field['meta']['help'] if focused_field else self.tr(
            '坐标采用 x 东、y 北、z 上；二维解算仍保留传播高度。',
            'Coordinates: x east, y north, z up; 2D positioning retains physical propagation height.'))
        self.refresh_states()

    def log(self, text):
        self.log_box.configure(state='normal')
        self.log_box.insert('end', str(text) + '\n')
        self.log_box.see('end')
        self.log_box.configure(state='disabled')

    def mark_dirty(self):
        if not self.loading:
            self.dirty = True

    def mode_changed(self):
        self.height_entry.configure(state='disabled' if self.use_z.get() else 'normal')
        self.mark_dirty()

    def mousewheel(self, event):
        if not self.pages or self.notebook.instate(['disabled']):
            return
        target = self.root.winfo_containing(event.x_root, event.y_root)
        if target is None or isinstance(target, (tk.Text, ttk.Combobox)):
            return
        page = self.pages[self.notebook.index('current')]
        if str(target).startswith(str(page)):
            page.canvas.yview_scroll(int(-event.delta / 120), 'units')

    def render_fields(self):
        self.loading = True
        for tab in self.notebook.tabs():
            self.root.nametowidget(tab).destroy()
        self.fields.clear()
        self.pages.clear()
        for tab_index, (title, sections) in enumerate(TAB_SECTIONS):
            page = ScrollPage(self.notebook)
            self.pages.append(page)
            self.notebook.add(page, text=TAB_TITLES[tab_index] if self.language == 'en' else title)
            index = 0
            if 'input_observations' in sections:
                note = self.localize(ttk.Label(page.body, style='Help.TLabel', wraplength=950),
                    '导入补偿后的完整伪距和多普勒，仅在本机读取。\n必要列：time_s（秒）、prn、pseudorange_m（米）、doppler_hz（赫兹）；可选 valid。\n时间起点、GPS 星历与卫星编号须和原数据一致。可以直接使用处理后的 observations.csv。',
                    'Import full corrected pseudorange and Doppler values; files are read locally.\nRequired: time_s (seconds), prn, pseudorange_m (meters), doppler_hz (Hz); valid is optional.\nThe time origin, GPS ephemeris and PRNs must match the original observations.')
                note.grid(row=index, column=0, sticky='w', pady=(0, 10))
                index += 1
                actions = ttk.Frame(page.body)
                actions.grid(row=index, column=0, sticky='w', pady=(0, 10))
                self.localize(ttk.Button(actions, command=self.clear_import), '清空文件选择', 'Clear file').pack(side='left')
                self.localize(ttk.Button(actions, command=self.save_import_template), '保存空白 CSV 模板', 'Save blank CSV template').pack(side='left', padx=8)
                index += 1
            if 'relay' in sections:
                count_row = ttk.Frame(page.body)
                count_row.grid(row=index, column=0, sticky='ew', pady=(0, 8))
                self.localize(ttk.Label(count_row), '室内发射点数量', 'Indoor transmitter count').pack(side='left')
                self.tx_count = tk.StringVar(value=str(len(self.config['relay']['transmitters'])))
                count = ttk.Combobox(count_row, values=['1', '2', '3', '4'], width=5,
                                     textvariable=self.tx_count, state='readonly')
                count.pack(side='left', padx=12)
                count.bind('<<ComboboxSelected>>', self.resize_transmitters)
                self.localize(ttk.Label(count_row, style='Help.TLabel'), '新增后请检查坐标、间距和卫星映射。', 'Check positions, spacing and satellite mappings after adding.').pack(side='left')
                index += 1
            for section in sections:
                for path, value in iter_fields(self.config[section], section):
                    if path == 'solver.known_height_m':
                        continue
                    self.add_field(page, index, path, value)
                    index += 1
        self.height_entry.configure(state='disabled' if self.use_z.get() else 'normal')
        self.loading = False
        self.filter_fields()
        self.refresh_states()

    def add_field(self, page, row, path, value):
        meta = describe(path, value, self.language)
        kind = meta['kind']
        frame = ttk.Frame(page.body, padding=(0, 4))
        frame.grid(row=row, column=0, sticky='ew')
        frame.columnconfigure(2, weight=1)
        label = ttk.Label(frame, text=meta['label'], width=24, wraplength=195, anchor='w')
        label.grid(row=0, column=0, sticky='nw', padx=(0, 8))
        edit = ttk.Frame(frame)
        edit.grid(row=0, column=1, sticky='nw')
        variables, controls = [], []
        if kind == 'bool':
            var = tk.BooleanVar(value=value)
            widget = self.localize(ttk.Checkbutton(edit, variable=var), '启用', 'Enable')
            widget.pack(anchor='w')
            variables.append(var)
            controls.append(widget)
        elif kind == 'vector':
            for axis, number in zip('xyz', value):
                ttk.Label(edit, text=axis).pack(side='left')
                var = tk.StringVar(value=str(number))
                widget = ttk.Entry(edit, textvariable=var, width=9)
                widget.pack(side='left', padx=(2, 6))
                variables.append(var)
                controls.append(widget)
        elif kind == 'json':
            widget = tk.Text(edit, width=35, height=4, wrap='word', relief='solid', borderwidth=1)
            widget.insert('1.0', json.dumps(value, ensure_ascii=False, indent=2))
            widget.edit_modified(False)
            widget.pack(fill='x')
            def changed(event, text=widget):
                if text.edit_modified():
                    self.mark_dirty()
                    text.edit_modified(False)
            widget.bind('<<Modified>>', changed)
            controls.append(widget)
        else:
            text = '' if value is None else json.dumps(value, ensure_ascii=False) if isinstance(value, list) else str(value)
            var = tk.StringVar(value=text)
            if meta.get('choices'):
                widget = ttk.Combobox(edit, textvariable=var, values=meta['choices'], width=32, state='readonly')
            else:
                widget = ttk.Entry(edit, textvariable=var, width=35)
            widget.pack(side='left', fill='x')
            variables.append(var)
            controls.append(widget)
            if kind == 'path':
                button = self.localize(ttk.Button(edit, width=7, command=lambda: self.browse_input(var)), '选择', 'Browse')
                button.pack(side='left', padx=4)
                controls.append(button)
        help_label = ttk.Label(frame, text=meta.get('help', '').split('\n')[0],
                               style='Help.TLabel', wraplength=300)
        help_label.grid(row=0, column=2, sticky='nw', padx=(12, 0))
        for var in variables:
            var.trace_add('write', lambda *a, field=path: self.field_changed(field))
        for widget in [label, *controls]:
            widget.bind('<FocusIn>', lambda e, p=path: self.help_text.set(self.fields[p]['meta']['help']), add='+')
        self.fields[path] = dict(meta=meta, value=value, kind=kind, variables=variables,
                                 controls=controls, frame=frame, page=page, row=row, label=label, help_label=help_label)

    def field_changed(self, path):
        self.mark_dirty()
        if path in ('iq.enabled', 'satellites.source', 'input_observations.corrected_csv'):
            self.refresh_states()

    def refresh_states(self):
        source = self.fields.get('satellites.source')
        rinex = bool(source and source['variables'][0].get() == 'rinex')
        iq = self.fields.get('iq.enabled')
        iq_on = not iq or iq['variables'][0].get()
        imported_field = self.fields.get('input_observations.corrected_csv')
        imported = bool(imported_field and imported_field['variables'][0].get().strip())
        self.data_kind.set(self.tr('已补偿观测定位解算', 'Corrected observations') if imported else self.tr('未补偿仿真数据', 'Uncorrected simulation'))
        self.run_button.configure(text=self.tr('计算位置和速度', 'Calculate position and velocity') if imported else self.tr('生成仿真数据', 'Generate simulation data'))
        for path, field in self.fields.items():
            enabled = not (path.startswith('iq.') and (imported or (path != 'iq.enabled' and not iq_on)))
            if path == 'input_observations.compare_reference':
                enabled = imported
            if path == 'satellites.rinex_nav_file':
                enabled = rinex
            for widget in field['controls']:
                if isinstance(widget, ttk.Combobox):
                    widget.configure(state='readonly' if enabled else 'disabled')
                else:
                    widget.configure(state='normal' if enabled else 'disabled')

    def filter_fields(self):
        query = self.search.get().strip().casefold()
        first_match = None
        current = self.notebook.select()
        current_matches = False
        for path, field in self.fields.items():
            match = query in (path + ' ' + field['meta']['label'] + ' ' + field['meta']['help']).casefold()
            if match:
                field['frame'].grid()
                first_match = first_match or field['page']
                current_matches |= str(field['page']) == current
            else:
                field['frame'].grid_remove()
        if query and first_match and not current_matches:
            self.notebook.select(first_match)

    def browse_input(self, var):
        filename = filedialog.askopenfilename(parent=self.root, title=self.tr('选择本地输入文件', 'Select local input file'), initialdir=self.base_directory)
        if filename:
            var.set(str(Path(filename).resolve()))

    def clear_import(self):
        self.fields['input_observations.corrected_csv']['variables'][0].set('')

    def save_import_template(self):
        filename = filedialog.asksaveasfilename(parent=self.root, title=self.tr('保存空白导入模板', 'Save blank import template'),
            initialdir=PROJECT / 'configs', initialfile='corrected_observations_template.csv',
            defaultextension='.csv', filetypes=[(self.tr('CSV 文件', 'CSV files'), '*.csv')], confirmoverwrite=False)
        if filename:
            try:
                with Path(filename).open('x', encoding='utf-8-sig', newline='') as stream:
                    stream.write('time_s,prn,pseudorange_m,doppler_hz,valid\r\n')
                self.log(self.tr('已保存空白模板。请填入补偿后的完整观测值，再选择该文件导入。', 'Blank template saved. Fill in the full corrected observations, then select the file to import.'))
            except OSError as error:
                self.show_error(error)

    def collect(self, validate=True):
        config = deepcopy(self.config)
        config['compensation'] = deepcopy(DEFAULT['compensation'])
        for path, field in self.fields.items():
            kind = field['kind']
            if kind == 'json':
                text = field['controls'][0].get('1.0', 'end-1c')
            elif kind == 'vector':
                numbers = [parse_value(path + '.' + axis, v.get(), 0., 'float')
                           for axis, v in zip('xyz', field['variables'])]
                set_at(config, path, numbers)
                continue
            else:
                text = field['variables'][0].get()
            set_at(config, path, parse_value(path, text, field['value'], kind))
        config['solver']['known_height_m'] = None if self.use_z.get() else parse_value(
            'solver.known_height_m', self.height.get(), None, 'float')
        return prepare_config(config, self.base_directory) if validate else config

    def show_error(self, error):
        details = translate_error(str(error)) if self.language == 'en' else str(error)
        self.log(self.tr('参数或运行错误：', 'Parameter or run error: ') + details)
        self.help_text.set(details)
        for path in sorted(self.fields, key=len, reverse=True):
            if path in str(error):
                field = self.fields[path]
                self.search.set('')
                self.notebook.select(field['page'])
                self.root.update_idletasks()
                top = field['frame'].winfo_y()
                total = max(1, field['page'].body.winfo_height())
                field['page'].canvas.yview_moveto(max(0, (top - 30) / total))
                field['controls'][0].focus_set()
                break

    def validate_inputs(self):
        try:
            config = self.collect()
            from .engine import Model
            model = Model(config)
            if config['input_observations']['corrected_csv']:
                from .observation_import import load_corrected_observations
                rows, reference, info = load_corrected_observations(config['input_observations']['corrected_csv'],model)
                self.log(self.tr(f'导入检查通过：{info["row_count"]} 条已补偿观测、{info["epoch_count"]} 个时刻；按原值解算。', f'Import validated: {info["row_count"]} corrected observations, {info["epoch_count"]} epochs; values used as provided.'))
            mode = self.tr('三维', '3D') if config['solver']['known_height_m'] is None else self.tr('二维', '2D')
            n = len(config['relay']['transmitters'])
            self.log(self.tr(f'参数检查通过：{mode}，{len(model.prns)} 颗可见卫星，{n} 个发射点。', f'Parameters valid: {mode}, {len(model.prns)} visible satellites, {n} transmitters.'))
            return config
        except Exception as error:
            self.show_error(error)
            return None

    def replace_config(self, config, source, base_directory):
        self.loading = True
        self.config = deepcopy(config)
        self.base_directory = Path(base_directory)
        height = config['solver']['known_height_m']
        self.use_z.set(height is None)
        self.height.set(str(height if height is not None else config['solver']['initial_enu_m'][2]))
        self.search.set('')
        self.render_fields()
        self.default_source = source == '默认参数（二维定位，高度 1 m）'
        self.source_value = source
        shown_source = self.tr(source, 'Default parameters (2D, height 1 m)') if self.default_source else source
        self.source_label.set(self.tr('当前配置：', 'Current configuration: ') + shown_source)
        self.dirty = False

    def load_dialog(self):
        if self.dirty and not messagebox.askyesno(self.tr('尚未保存', 'Unsaved changes'), self.tr('加载配置将替换当前未保存的输入，是否继续？', 'Loading a configuration replaces unsaved inputs. Continue?'), parent=self.root):
            return
        filename = filedialog.askopenfilename(parent=self.root, title=self.tr('加载场景配置', 'Load scene configuration'), initialdir=PROJECT / 'configs',
                                               filetypes=[(self.tr('JSON 配置', 'JSON configuration'), '*.json')])
        if filename:
            try:
                self.replace_config(load_for_app(filename), filename, Path(filename).parent)
                self.log(self.tr('已加载配置；当前二维/三维设置与该配置一致。', 'Configuration loaded; 2D/3D mode matches the file.'))
            except Exception as error:
                self.show_error(error)

    def save_dialog(self):
        try:
            config = self.collect()
            filename = filedialog.asksaveasfilename(parent=self.root, title=self.tr('另存配置（使用新文件名）', 'Save configuration under a new name'),
                initialdir=PROJECT / 'configs', initialfile='my_scene_' + datetime.now().strftime('%Y%m%d_%H%M%S') + '.json',
                defaultextension='.json', filetypes=[(self.tr('JSON 配置', 'JSON configuration'), '*.json')], confirmoverwrite=False)
            if filename:
                path = save_config(config, filename, self.base_directory)
                self.replace_config(config, str(path), path.parent)
                self.log(self.tr('配置已另存；已有配置文件会受到保护。', 'Configuration saved as a new file.'))
                return path
        except Exception as error:
            self.show_error(error)

    def reset_defaults(self):
        if self.dirty and not messagebox.askyesno(self.tr('恢复默认', 'Restore defaults'), self.tr('用默认参数替换当前未保存的输入？', 'Replace unsaved inputs with defaults?'), parent=self.root):
            return
        cfg = load_for_app()
        cfg['solver']['known_height_m'] = 1.
        self.replace_config(cfg, '默认参数（二维定位，高度 1 m）', PROJECT / 'configs')

    def resize_transmitters(self, event=None):
        try:
            config = self.collect(validate=False)
            count = int(self.tx_count.get())
            txs = config['relay']['transmitters']
            if count < len(txs):
                if not messagebox.askyesno(self.tr('减少发射点', 'Reduce transmitters'), self.tr('将移除末尾发射点的当前输入。继续？', 'Inputs for the last transmitters will be removed. Continue?'), parent=self.root):
                    self.tx_count.set(str(len(txs)))
                    return
                del txs[count:]
            while len(txs) < count:
                index = len(txs)
                tx = deepcopy(DEFAULT['relay']['transmitters'][0])
                tx['id'] = f'V{index + 1}'
                room = config['site']['room_size_enu_m']
                tx['position_enu_m'] = [room[0] / 2, room[1] / 2, room[2]]
                txs.append(tx)
            selected = self.notebook.index('current')
            self.config = config
            self.render_fields()
            self.notebook.select(selected)
            self.dirty = True
            self.log(self.tr('发射点数量已改变；请设置新增坐标，并核对映射和点间距。', 'Transmitter count changed; set new positions and check mappings and spacing.'))
        except Exception as error:
            self.tx_count.set(str(len(self.config['relay']['transmitters'])))
            self.show_error(error)

    def set_busy(self, busy):
        for button in self.toolbar.winfo_children():
            button.configure(state='disabled' if busy else 'normal')
        self.run_button.configure(state='disabled' if busy else 'normal')
        self.stop_button.configure(state='normal' if busy else 'disabled')
        self.open_button.configure(state='normal' if self.last_output and self.last_output.exists() else 'disabled')
        # The immutable snapshot used by the worker is independent of later form edits.
        if busy:
            self.progress.start(12)
        else:
            self.progress.stop()

    def start_run(self):
        if self.process is not None:
            return
        config = self.validate_inputs()
        if config is None:
            return
        try:
            tag = datetime.now().strftime('%Y%m%d_%H%M%S_%f') + '_' + uuid.uuid4().hex[:6]
            mode = '3d' if config['solver']['known_height_m'] is None else '2d'
            snapshot = save_config(config, PROJECT / 'configs' / 'user' / f'run_{tag}.json', self.base_directory)
            output = PROJECT / 'experiments' / f'run_gui_{mode}_{tag}'
            log_dir = PROJECT / 'experiments' / 'temp' / 'gui'
            log_dir.mkdir(parents=True, exist_ok=True)
            self.run_log = log_dir / f'{tag}.log'
            python = Path(sys.executable)
            if python.stem.lower() == 'pythonw':
                python = python.with_name('python.exe')
            command = [str(python), str(PROJECT / 'simulate.py'), '--config', str(snapshot), '--output', str(output)]
            environment = dict(os.environ, PYTHONIOENCODING='utf-8')
            with self.run_log.open('xb') as stream:
                self.process = subprocess.Popen(command, cwd=PROJECT, env=environment, stdout=stream,
                    stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            self.last_output = output
            self.output.set(str(output))
            action = '解算已补偿观测' if config['input_observations']['corrected_csv'] else '生成未补偿观测'
            action_en = 'Solving corrected observations' if config['input_observations']['corrected_csv'] else 'Generating uncorrected observations'
            self.log(self.tr(f'正在{action}（{mode.upper()}）；本次参数已保存到 {snapshot.name}。', f'{action_en} ({mode.upper()}); parameters saved to {snapshot.name}.'))
            self.set_busy(True)
            self.root.after(200, self.poll_run)
        except Exception as error:
            self.process = None
            self.set_busy(False)
            self.show_error(error)

    def poll_run(self):
        if self.process is None:
            return
        code = self.process.poll()
        if code is None:
            self.root.after(200, self.poll_run)
            return
        self.process = None
        self.set_busy(False)
        try:
            summary_file = self.last_output / 'run_summary.json'
            if code != 0 or not summary_file.exists():
                details = self.run_log.read_text(encoding='utf-8', errors='replace')[-4000:]
                self.log(self.tr('本次未完成；保留部分输出和日志。\n', 'Run incomplete; partial output and log retained.\n') + details)
                return
            summary = json.loads(summary_file.read_text(encoding='utf-8'))
            if summary.get('status') != 'complete':
                raise ValueError(self.tr('完成记录状态异常', 'Unexpected run summary status'))
            self.log(self.tr(f'处理完成：{summary["epoch_count"]} 个时刻、{summary["observation_rows"]} 条观测。', f'Completed: {summary["epoch_count"]} epochs, {summary["observation_rows"]} observations.'))
            metrics_file = self.last_output / 'metrics.json'
            if metrics_file.exists():
                metrics = json.loads(metrics_file.read_text(encoding='utf-8'))
                self.log(self.tr(f'定位有效解：{metrics["converged_count"]}/{metrics["epoch_count"]}。', f'Converged solutions: {metrics["converged_count"]}/{metrics["epoch_count"]}.'))
                if metrics['position_error_m'] is not None:
                    kind = '水平' if metrics['solution_dimensions'] == 2 else '三维'
                    reference = '相对配置仿真轨迹：' if summary['observation_source']=='external_corrected_csv' else ''
                    kind_en = 'Horizontal' if metrics['solution_dimensions'] == 2 else '3D'
                    reference_en = 'Relative to configured simulation trajectory: ' if summary['observation_source'] == 'external_corrected_csv' else ''
                    pos = metrics['position_error_m']['mean']
                    vel = metrics['velocity_vector_error_mps']['rms']
                    self.log(self.tr(f'{reference}{kind}平均位置误差 {pos:.3f} m；速度向量 RMSE {vel:.3f} m/s。',
                                     f'{reference_en}{kind_en} mean position error {pos:.3f} m; velocity vector RMSE {vel:.3f} m/s.'))
                elif summary['observation_source']=='external_corrected_csv':
                    self.log(self.tr('未启用配置轨迹对比，结果文件提供位置、速度；不报告真值误差。', 'Trajectory comparison is disabled. Results contain position and velocity; ground-truth error is not reported.'))
        except Exception as error:
            self.show_error(error)

    def stop_run(self):
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            self.log(self.tr('已请求停止；本次部分输出会保留，不作为完整数据集。', 'Stop requested; partial output is retained and is not a complete dataset.'))

    def open_output(self):
        if self.last_output and self.last_output.exists():
            os.startfile(str(self.last_output))

    def on_close(self):
        if self.process is not None:
            self.log(self.tr('请先停止当前生成任务，再关闭窗口。', 'Stop the current run before closing the window.'))
            return
        if self.dirty and not messagebox.askyesno(self.tr('尚未保存', 'Unsaved changes'), self.tr('当前输入尚未另存配置，仍然关闭窗口？', 'Inputs have not been saved. Close anyway?'), parent=self.root):
            return
        self.root.destroy()

    def callback_error(self, kind, error, tb):
        self.show_error(error)
        log_dir = PROJECT / 'experiments' / 'temp' / 'gui'
        log_dir.mkdir(parents=True, exist_ok=True)
        log = log_dir / ('interface_' + uuid.uuid4().hex + '.log')
        log.write_text(''.join(traceback.format_exception(kind, error, tb)), encoding='utf-8')


def main():
    root = tk.Tk()
    SimulatorApp(root)
    root.mainloop()
