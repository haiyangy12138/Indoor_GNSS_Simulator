"""Typed, non-destructive configuration editing for the desktop application.

This layer prepares the same physics configuration as ``config.load``.  It does
not read trajectory truth, change simulation models, or open external datasets.
"""
from copy import deepcopy
import json
import math
from pathlib import Path

from .config import DEFAULT, _merge, load, validate


INPUT_PATHS = (('satellites', 'rinex_nav_file'), ('iq', 'navigation_bits_file'),
               ('input_observations', 'corrected_csv'))
_OPTIONAL_PATHS = {'.'.join(parts) for parts in INPUT_PATHS}


def _error(path, detail):
    raise ValueError(f'{path}: {detail}')


def _json(text, path):
    def reject_constant(value):
        _error(path, f'non-finite JSON number {value} is not allowed')
    try:
        return json.loads(text, parse_constant=reject_constant)
    except json.JSONDecodeError as exc:
        _error(path, f'invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}')


def parse_value(path, text, default_value, kind):
    """Convert one editor control value without silently coercing invalid input.

    Numbers accept scientific notation; integer fields require an integer token.
    Lists, vectors and mappings use ordinary JSON syntax.  An empty optional
    height or optional input path means ``None``.
    """
    if kind == 'bool':
        if isinstance(text, bool):
            return text
        if isinstance(text, str) and text.strip().lower() in ('true', 'false'):
            return text.strip().lower() == 'true'
        _error(path, 'expected true or false')
    raw = str(text).strip()
    if kind == 'int':
        if isinstance(text, bool):
            _error(path, 'expected an integer, not a boolean')
        try:
            # int('3.0') and int('1e3') deliberately fail: no rounding occurs.
            return int(raw)
        except (ValueError, OverflowError):
            _error(path, 'expected an integer')
    if kind in ('float', 'optional_float'):
        if kind == 'optional_float' and raw.lower() in ('', 'null', 'none'):
            return None
        if isinstance(text, bool):
            _error(path, 'expected a number, not a boolean')
        try:
            value = float(raw)
        except (ValueError, OverflowError):
            _error(path, 'expected a finite number')
        if not math.isfinite(value):
            _error(path, 'expected a finite number')
        return value
    if kind in ('vector', 'list', 'json'):
        value = _json(raw, path)
        if (kind in ('vector', 'list') or isinstance(default_value, list)) and not isinstance(value, list):
            _error(path, 'expected a JSON array')
        if kind == 'json' and isinstance(default_value, dict) and not isinstance(value, dict):
            _error(path, 'expected a JSON object')
        return value
    if kind == 'path' or path in _OPTIONAL_PATHS:
        return raw or None
    if kind in ('text', 'choice', 'enum'):
        return raw
    _error(path, f'unsupported editor field type {kind!r}')


def _number(value, path):
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
        _error(path, 'expected a finite number, not text or boolean')


def _check_template(value, template, path):
    """Validate input types before NumPy or Python can coerce booleans/text."""
    if path == 'compensation.per_prn':
        if not isinstance(value, dict):
            _error(path, 'expected an object indexed by satellite PRN')
        for prn, parameters in value.items():
            if not isinstance(prn, str) or not isinstance(parameters, dict):
                _error(path, 'PRN keys must be strings and their values must be objects')
            _check_template(parameters, DEFAULT['compensation']['default'], f'{path}.{prn}')
        return
    if path == 'relay.mapping':
        if not isinstance(value, dict):
            _error(path, 'expected an object, for example {"3": "V1"}')
        if any(not isinstance(prn, str) or not isinstance(tx, str) for prn, tx in value.items()):
            _error(path, 'PRN keys and transmitter IDs must be strings')
        return
    if path == 'relay.transmitters':
        if not isinstance(value, list) or not 1 <= len(value) <= 4:
            _error(path, 'expected a list containing 1 to 4 transmitters')
        for index, transmitter in enumerate(value):
            _check_template(transmitter, template[0], f'{path}.{index}')
        return
    if template is None:
        if path in _OPTIONAL_PATHS:
            if value is not None and not isinstance(value, str):
                _error(path, 'expected a file path or null')
        elif value is not None:
            _number(value, path)
        return
    if isinstance(template, bool):
        if not isinstance(value, bool):
            _error(path, 'expected true or false')
    elif isinstance(template, int):
        if not isinstance(value, int) or isinstance(value, bool):
            _error(path, 'expected an integer, not text, decimal or boolean')
    elif isinstance(template, float):
        _number(value, path)
    elif isinstance(template, str):
        if not isinstance(value, str):
            _error(path, 'expected text')
    elif isinstance(template, dict):
        if not isinstance(value, dict):
            _error(path, 'expected an object')
        unknown = set(value) - set(template)
        if unknown:
            _error(path, f'unknown parameter {sorted(unknown, key=str)[0]}')
        missing = set(template) - set(value)
        if missing:
            _error(path, f'missing parameter {sorted(missing)[0]}')
        for key, example in template.items():
            _check_template(value[key], example, f'{path}.{key}' if path else key)
    elif isinstance(template, list):
        if not isinstance(value, list):
            _error(path, 'expected a JSON array')
        if path == 'satellites.prns':
            for index, prn in enumerate(value):
                if not isinstance(prn, int) or isinstance(prn, bool):
                    _error(f'{path}.{index}', 'expected an integer PRN')
            if len(value) != len(set(value)):
                _error(path, 'satellite PRNs must be unique')
        elif path == 'multipath.walls':
            if any(not isinstance(wall, str) for wall in value):
                _error(path, 'wall names must be strings')
            if len(value) != len(set(value)):
                _error(path, 'wall names must be unique')
        elif path == 'trajectory.waypoints_enu_m':
            for index, waypoint in enumerate(value):
                _check_template(waypoint, DEFAULT['trajectory']['start_enu_m'], f'{path}.{index}')
        else:
            if len(value) != len(template):
                _error(path, f'expected {len(template)} coordinates')
            for index, coordinate in enumerate(value):
                _number(coordinate, f'{path}.{index}')


def prepare_config(config, base_directory):
    """Expand, resolve and validate an editor snapshot without mutating it."""
    if not isinstance(config, dict):
        _error('config', 'expected a JSON object')
    try:
        cfg = _merge(deepcopy(DEFAULT), config)
        per_prn = cfg['compensation']['per_prn']
        if not isinstance(per_prn, dict):
            _error('compensation.per_prn', 'expected an object')
        for prn, parameters in list(per_prn.items()):
            if not isinstance(parameters, dict):
                _error(f'compensation.per_prn.{prn}', 'expected an object')
            per_prn[prn] = _merge(deepcopy(cfg['compensation']['default']), parameters,
                                  f'compensation.per_prn.{prn}')
        _check_template(cfg, DEFAULT, '')
        base = Path(base_directory).resolve()
        for section, field in INPUT_PATHS:
            value = cfg[section][field]
            if value:
                data_path = Path(value).expanduser()
                cfg[section][field] = str(data_path.resolve() if data_path.is_absolute()
                                          else (base / data_path).resolve())
            else:
                cfg[section][field] = None
        if cfg['seed'] < 0:
            _error('seed', 'must be a non-negative integer')
        for section, field in (('time', 'gps_week'), ('satellites', 'epoch_gps_week')):
            if cfg[section][field] < 0:
                _error(f'{section}.{field}', 'must be a non-negative GPS week')
        if not -90 <= cfg['site']['latitude_deg'] <= 90:
            _error('site.latitude_deg', 'must lie in [-90, 90] degrees')
        if not -180 <= cfg['site']['longitude_deg'] <= 180:
            _error('site.longitude_deg', 'must lie in [-180, 180] degrees')
        if not 0 <= cfg['satellites']['epoch_gps_sow'] < 604800:
            _error('satellites.epoch_gps_sow', 'must lie in [0, 604800) seconds')
        for section, field in (('solver', 'max_iterations'), ('solver', 'position_tolerance_m'),
                               ('solver', 'max_step_m'), ('propagation', 'light_time_tolerance_s'),
                               ('propagation', 'min_path_m'), ('iq', 'chunk_samples'),
                               ('iq', 'max_output_bytes')):
            if cfg[section][field] <= 0:
                _error(f'{section}.{field}', 'must be positive')
        if not 0 <= cfg['relay']['min_spacing_m'] < cfg['relay']['max_spacing_m']:
            _error('relay.min_spacing_m', 'spacing bounds must satisfy 0 <= min < max')
        validate(cfg)
    except (TypeError, AttributeError, KeyError, IndexError) as exc:
        raise ValueError(f'config: invalid parameter structure ({exc})') from exc
    return cfg


def load_for_edit(path=None):
    """Load existing partial/full configurations using the simulator loader."""
    if path is None:
        return prepare_config(load(), Path.cwd())
    path = Path(path).resolve()
    try:
        cfg = load(path)
    except (TypeError, AttributeError, KeyError, IndexError) as exc:
        raise ValueError(f'{path.name}: invalid parameter structure ({exc})') from exc
    return prepare_config(cfg, path.parent)


def load_for_app(path=None):
    """The current application accepts corrected data instead of applying compensation."""
    if path is None:
        return prepare_config({}, Path.cwd())
    path = Path(path).resolve()
    config = _json(path.read_text(encoding='utf-8-sig'), 'config')
    if not isinstance(config, dict):
        _error('config', 'expected a JSON object')
    config['compensation'] = deepcopy(DEFAULT['compensation'])
    return prepare_config(config, path.parent)


def save_config(config, target, base_directory):
    """Save a validated, self-contained JSON snapshot, refusing to overwrite."""
    target = Path(target)
    cfg = prepare_config(config, base_directory)
    # Validate and serialize before creating any directory or destination file.
    text = json.dumps(cfg, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('x', encoding='utf-8') as stream:
        stream.write(text)
    return target.resolve()
