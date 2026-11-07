"""Import already-corrected observations without changing their measurements.

The CSV is external input of unspecified provenance.  The accompanying reference
trajectory is calculated from the configured simulation, not read from the CSV
and not asserted to be ground truth for real measurements.
"""
import csv
import hashlib
import io
import math
from pathlib import Path
import re


REQUIRED_FIELDS = ('time_s', 'prn', 'pseudorange_m', 'doppler_hz')
MAX_FILE_BYTES = 100 * 1024 * 1024
MAX_ROWS = 2_000_000


def _number(value, field, line):
    if value is None or not str(value).strip():
        raise ValueError(f'导入 CSV 第 {line} 行：{field} 不能为空。')
    try:
        number = float(str(value).strip())
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f'导入 CSV 第 {line} 行：{field} 必须为有限数值。') from exc
    if not math.isfinite(number):
        raise ValueError(f'导入 CSV 第 {line} 行：{field} 不能是 NaN 或无穷大。')
    return number


def load_corrected_observations(path, model):
    """Return ``(rows, reference, metadata)`` for one local corrected CSV.

    Required units are elapsed receiver-clock seconds, GPS PRN integer, metres,
    and hertz.  Positive Doppler follows the receiver's existing convention:
    ``doppler_hz = -carrier_range_rate_mps / lambda_L1``.  Rows need not lie on
    the generator's original sampling grid.  Missing rows are never synthesized.
    """
    source = Path(path).expanduser().resolve()
    try:
        if source.stat().st_size > MAX_FILE_BYTES:
            raise ValueError('导入 CSV 超过 100 MiB，请分段导入。')
        with source.open('rb') as stream:
            raw = stream.read(MAX_FILE_BYTES + 1)
    except OSError as exc:
        raise ValueError(f'无法读取已补偿观测文件：{source}（{exc}）') from exc
    if len(raw) > MAX_FILE_BYTES:
        raise ValueError('导入 CSV 超过 100 MiB，请分段导入。')
    try:
        text = raw.decode('utf-8-sig')
    except UnicodeDecodeError as exc:
        raise ValueError('导入 CSV 必须使用 UTF-8 编码，可带 BOM。') from exc
    if not text.strip():
        raise ValueError('导入 CSV 为空，请提供已补偿的伪距和多普勒观测。')

    reader = csv.DictReader(io.StringIO(text, newline=''), strict=True)
    try:
        headers = reader.fieldnames
        if not headers:
            raise ValueError('导入 CSV 缺少表头。')
        headers = [header.strip() for header in headers]
        if any(not header for header in headers):
            raise ValueError('导入 CSV 表头不能为空。')
        if len(headers) != len(set(headers)):
            raise ValueError('导入 CSV 存在重复表头。')
        missing = [field for field in REQUIRED_FIELDS if field not in headers]
        if missing:
            raise ValueError('导入 CSV 缺少必要字段：' + ', '.join(missing))
        reader.fieldnames = headers
        has_valid = 'valid' in headers
        allowed_prns = {int(prn) for prn in model.prns}
        duration = model.cfg['time']['duration_s']
        rows, keys = [], set()
        for item in reader:
            line = reader.line_num
            if len(rows) >= MAX_ROWS:
                raise ValueError('导入 CSV 超过 200 万条观测，请分段导入。')
            if None in item:
                raise ValueError(f'导入 CSV 第 {line} 行：数据列数多于表头。')
            time_s = _number(item.get('time_s'), 'time_s', line)
            if not 0 <= time_s <= duration:
                raise ValueError(f'导入 CSV 第 {line} 行：time_s 必须位于 [0, {duration}] 秒，请核对起始时间和仿真时长。')
            prn_text = (item.get('prn') or '').strip()
            if not re.fullmatch(r'[1-9][0-9]?', prn_text) or not 1 <= int(prn_text) <= 32:
                raise ValueError(f'导入 CSV 第 {line} 行：prn 必须为 1～32 的整数，不使用 G 前缀、前导零或小数。')
            prn = int(prn_text)
            if prn not in allowed_prns:
                raise ValueError(f'导入 CSV 第 {line} 行：PRN {prn} 不在当前配置选用的卫星中，请在卫星 PRN 列表中设置数据对应的卫星。')
            pseudorange = _number(item.get('pseudorange_m'), 'pseudorange_m', line)
            if pseudorange <= 0:
                raise ValueError(f'导入 CSV 第 {line} 行：pseudorange_m 必须大于零，单位为 m。')
            doppler = _number(item.get('doppler_hz'), 'doppler_hz', line)
            valid = True
            if has_valid:
                validity = (item.get('valid') or '').strip().lower()
                if validity not in ('true', 'false', '1', '0'):
                    raise ValueError(f'导入 CSV 第 {line} 行：valid 必须为 true、false、1 或 0。')
                valid = validity in ('true', '1')
            key = (time_s, prn)
            if key in keys:
                raise ValueError(f'导入 CSV 第 {line} 行：重复的 (time_s, prn)=({time_s}, {prn})。')
            keys.add(key)
            rows.append({'time_s': time_s, 'prn': prn, 'transmitter_id': 'external',
                         'pseudorange_m': pseudorange, 'doppler_hz': doppler,
                         'valid': valid})
    except csv.Error as exc:
        raise ValueError(f'导入 CSV 格式错误（第 {reader.line_num} 行）：{exc}') from exc
    if not rows:
        raise ValueError('导入 CSV 没有观测行，至少需要一条已补偿观测。')
    rows.sort(key=lambda row: (row['time_s'], row['prn']))
    times = sorted({row['time_s'] for row in rows})
    reference = []
    tm = model.cfg['time']
    for time_s in times:
        position, velocity = model.user_at(time_s)
        gps_sow = tm['gps_sow'] + time_s
        row = {'time_s': time_s,
               'gps_week': tm['gps_week'] + int(gps_sow // 604800),
               'gps_sow': gps_sow % 604800,
               'distance_sample': False}
        for index, axis in enumerate('xyz'):
            row[axis + '_m'] = float(position[index])
            row['v' + axis + '_mps'] = float(velocity[index])
        reference.append(row)
    metadata = {'source_path': str(source), 'sha256': hashlib.sha256(raw).hexdigest(),
                'row_count': len(rows), 'epoch_count': len(times),
                'prns': sorted({row['prn'] for row in rows}),
                'source_kind': 'external_corrected_csv',
                'reference_kind': 'configured_simulation_trajectory',
                'input_origin': 'unspecified',
                'measurements_modified': False,
                'missing_observations_filled': False,
                'time_range_s': [times[0], times[-1]],
                'required_fields': list(REQUIRED_FIELDS),
                'reference_warning': '参考轨迹来自当前仿真配置，不是导入文件的实测真值。'}
    return rows, reference, metadata
