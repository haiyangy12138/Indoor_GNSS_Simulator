"""English UI labels and help; configuration keys and values stay unchanged."""

TAB_TITLES = ['Scene & trajectory', 'Satellites & propagation', 'Indoor transmitters',
              'Import observations', 'Clock & atmosphere', 'Noise & multipath',
              'Position solution', 'I/Q signal']

# English text for every field exposed by the application. Each description
# describes the same model as its Chinese counterpart without changing units.
FIELDS = {
 'seed': ('Random seed', 'A nonnegative integer. The same seed and parameters reproduce random errors.'),
 'time.gps_week': ('Start GPS week', 'Full GPS week in GPST; match the ephemeris and navigation symbols.'),
 'time.gps_sow': ('Start GPS seconds of week (s)', 'GPST seconds of week, 0 ≤ value < 604800; UTC is not converted automatically.'),
 'time.duration_s': ('Simulation duration (s)', 'Positive duration covering all motion and the I/Q window.'),
 'time.observation_interval_s': ('Observation interval (s)', 'Positive interval for propagation and observations; I/Q path parameters are interpolated.'),
 'time.trajectory_distance_step_m': ('Trajectory distance step (m)', 'Positive distance step; additional points are merged with the time grid.'),
 'time.derivative_step_s': ('Doppler difference half-step (s)', 'Central difference half-step: 0 < value < 0.1.'),
 'site.latitude_deg': ('Origin latitude (°)', 'WGS84 latitude from −90 to 90 degrees.'),
 'site.longitude_deg': ('Origin longitude (°)', 'WGS84 longitude, normally −180 to 180 degrees.'),
 'site.height_m': ('Origin ellipsoidal height (m)', 'WGS84 ellipsoidal height; local indoor z is relative to this origin.'),
 'site.room_size_enu_m': ('Room size [east, north, up] (m)', 'Three positive dimensions; trajectory and transmitters must lie inside the room.'),
 'site.outdoor_antenna_enu_m': ('Outdoor antenna [x, y, z] (m)', 'Local ENU position; the antenna may be above the room.'),
 'trajectory.start_enu_m': ('Trajectory start [x, y, z] (m)', 'Start of the straight path inside the room; must differ from the end.'),
 'trajectory.end_enu_m': ('Trajectory end [x, y, z] (m)', 'End of the straight path inside the room.'),
 'trajectory.start_time_s': ('Motion start time (s)', 'The receiver remains at the start until this time.'),
 'trajectory.speed_mps': ('Cruise speed (m/s)', 'Positive ground-truth speed; not supplied to the receiver as known velocity.'),
 'trajectory.acceleration_time_s': ('Acceleration / braking time (s)', 'Time for each ramp. Zero means instantaneous start and stop; speed × time must not exceed path length.'),
 'satellites.source': ('Satellite orbit source', 'synthetic: demonstration circular orbits, not real constellation geometry; rinex: local GPS broadcast ephemeris.'),
 'satellites.rinex_nav_file': ('RINEX navigation file', 'Required for rinex. GPS or mixed RINEX 2/3 NAV and .gz are supported; RINEX 4 is not.'),
 'satellites.max_ephemeris_age_s': ('Maximum ephemeris age (s)', 'Positive; broadcast record validity limits also apply.'),
 'satellites.allow_unhealthy': ('Allow unhealthy satellites', 'Normally disabled. Enable only for clearly identified research experiments.'),
 'satellites.count': ('Automatic satellite count', 'Integer 1–32, used when the PRN list is empty; satellites must be visible at the start.'),
 'satellites.prns': ('Explicit satellite PRNs', 'List of distinct GPS PRNs from 1 to 32, e.g. [3, 16, 4, 10]; [] selects automatically.'),
 'satellites.elevation_mask_deg': ('Minimum elevation (°)', 'Initial selection and time-varying visibility threshold.'),
 'satellites.synthetic_count': ('Synthetic candidate count', 'Integer 1–32; only used for the synthetic constellation.'),
 'satellites.synthetic_planes': ('Synthetic orbit planes', 'Integer between 1 and the synthetic candidate count.'),
 'satellites.synthetic_radius_m': ('Synthetic orbital radius (m)', 'Circular orbit radius from Earth’s center, not altitude; greater than the WGS84 equatorial radius.'),
 'satellites.synthetic_inclination_deg': ('Synthetic inclination (°)', 'Synthetic constellation inclination from 0 to 180 degrees.'),
 'satellites.synthetic_raan_offset_deg': ('Synthetic RAAN offset (°)', 'Initial right ascension offset for synthetic orbital planes.'),
 'satellites.epoch_gps_week': ('Synthetic reference GPS week', 'Reference epoch for synthetic orbit phase and satellite clock.'),
 'satellites.epoch_gps_sow': ('Synthetic reference seconds (s)', 'Reference seconds of GPS week in GPST.'),
 'satellites.synthetic_clock_bias_s': ('Synthetic satellite clock bias (s)', 'Initial clock bias shared by all synthetic satellites.'),
 'satellites.synthetic_clock_drift_sps': ('Synthetic satellite clock drift (s/s)', 'Linear clock drift shared by synthetic satellites.'),
 'satellites.synthetic_tgd_s': ('Synthetic GPS L1 TGD (s)', 'Adds +c × TGD to the code path, not the carrier path.'),
 'propagation.mode': ('Propagation mode', 'relay: satellite to outdoor antenna, indoor transmitter and user; direct: satellite to user baseline.'),
 'propagation.earth_rotation': ('Correct Earth rotation', 'Account for Earth rotation along the satellite-to-antenna path.'),
 'propagation.light_time_tolerance_s': ('Light-time tolerance (s)', 'Positive sky-path iteration threshold; at most eight iterations.'),
 'propagation.min_path_m': ('Minimum indoor path (m)', 'Rejects shorter source paths to avoid the point-source loss singularity.'),
 'relay.architecture': ('Relay architecture', 'transparent requires zero independent transmitter clock error; regenerative allows equivalent clock error.'),
 'relay.mapping': ('Satellite-to-transmitter mapping', 'JSON object, e.g. {"3":"V1"}; unmapped satellites are assigned cyclically.'),
 'relay.min_spacing_m': ('Minimum spacing, exclusive (m)', 'Every pair of transmitters must be strictly farther apart than this value.'),
 'relay.max_spacing_m': ('Maximum spacing, exclusive (m)', 'Every pair of transmitters must be strictly closer than this value.'),
 'relay.transmitters.*.id': ('ID', 'Unique transmitter ID; mappings must use exactly the same ID.'),
 'relay.transmitters.*.position_enu_m': ('Position [x, y, z] (m)', 'Position in the room. Physical height remains relevant in 2D positioning.'),
 'relay.transmitters.*.cable_length_m': ('Cable length (m)', 'Nonnegative physical length; equivalent path is length divided by velocity factor.'),
 'relay.transmitters.*.cable_velocity_factor': ('Cable velocity factor', 'Propagation speed divided by light speed, 0 < value ≤ 1.'),
 'relay.transmitters.*.processing_delay_s': ('Processing delay (s)', 'Nonnegative fixed delay; common delay can be absorbed by receiver clock bias.'),
 'relay.transmitters.*.phase_offset_rad': ('Carrier phase offset (rad)', 'Changes carrier phase without changing code delay.'),
 'relay.transmitters.*.reference_distance_m': ('Loss reference distance (m)', 'Positive reference distance used with the reference C/N0.'),
 'relay.transmitters.*.path_loss_exponent': ('Path-loss exponent', 'Nonnegative; 2 is the free-space distance exponent. Calibrate indoors.'),
 'relay.transmitters.*.excess_loss_db': ('Additional fixed loss (dB)', 'Positive values attenuate the signal.'),
 'input_observations.corrected_csv': ('Corrected observations CSV (optional)', 'Choose a local file containing full corrected time_s, prn, pseudorange_m, doppler_hz values, not corrections. Empty generates uncorrected observations; import does not generate I/Q.'),
 'input_observations.compare_reference': ('Compare configured trajectory', 'Enable only when the input comes from the same simulation; error is relative to the configured trajectory, not external ground truth.'),
 'receiver_clock.frequency_gm_sigma_sps': ('Random clock drift sigma (s/s)', 'Nonnegative; zero disables the correlated random frequency process.'),
 'receiver_clock.frequency_gm_tau_s': ('Random clock drift correlation time (s)', 'Positive Gauss–Markov frequency correlation time.'),
 'receiver_clock.clock_grid_s': ('Clock integration interval (s)', 'Positive; a smaller interval increases time resolution and memory use.'),
 'atmosphere.enabled': ('Enable simplified atmosphere', 'Models simplified troposphere and fixed-TEC ionosphere, not measured weather.'),
 'atmosphere.pressure_hpa': ('Pressure (hPa)', 'Positive pressure used by the troposphere model.'),
 'atmosphere.temperature_k': ('Temperature (K)', 'Absolute temperature, 150 < value < 350.'),
 'atmosphere.relative_humidity': ('Relative humidity (0–1)', 'Fraction, not percent; use 0.5 for 50%.'),
 'atmosphere.vertical_tec_tecu': ('Vertical TEC (TECU)', 'Nonnegative constant electron content; not a measured time-varying field.'),
 'atmosphere.iono_shell_height_m': ('Ionospheric shell height (m)', 'Positive height for mapping vertical TEC to the slant path.'),
 'atmosphere.min_mapping_elevation_deg': ('Atmosphere mapping minimum elevation (°)', 'A positive value avoids divergent low-elevation mapping.'),
 'observations.add_noise': ('Add observation noise', 'Controls statistical pseudorange and Doppler noise independently of I/Q noise.'),
 'observations.reference_cn0_dbhz': ('Reference C/N0 (dB-Hz)', 'C/N0 at the loss reference distance; also normalizes I/Q amplitude.'),
 'observations.reference_cn0_for_noise_dbhz': ('Noise calibration C/N0 (dB-Hz)', 'Reference C/N0 for code and Doppler noise standard deviations.'),
 'observations.code_sigma_m': ('Pseudorange noise sigma (m)', 'Nonnegative measurement noise at calibration C/N0, not position error.'),
 'observations.doppler_sigma_hz': ('Doppler noise sigma (Hz)', 'Nonnegative measurement noise at calibration C/N0, not velocity error.'),
 'observations.code_noise_correlation_s': ('Pseudorange correlation time (s)', 'Nonnegative; zero selects white noise.'),
 'observations.doppler_noise_correlation_s': ('Doppler correlation time (s)', 'Nonnegative; zero selects white noise.'),
 'observations.noise_code_doppler_correlation': ('Code / Doppler noise correlation', 'From −1 to 1, applied to standardized innovations.'),
 'observations.minimum_cn0_dbhz': ('Minimum valid C/N0 (dB-Hz)', 'Observations below this threshold are invalid when the C/N0 gate is enabled.'),
 'observations.dropout_probability': ('Observation dropout probability', 'Independent LOS observation loss probability from 0 to 1.'),
 'observations.apply_cn0_gate': ('Apply C/N0 observation gate', 'Marks low-C/N0 observations invalid; does not simulate receiver lock.'),
 'multipath.enabled': ('Enable single wall reflections', 'Adds reflections to relay I/Q only; no fabricated multipath bias is added to observation CSV.'),
 'multipath.walls': ('Reflecting surfaces', 'JSON list containing east, west, north, south, floor or ceiling.'),
 'multipath.reflection_amplitude': ('Reflection voltage amplitude', 'From 0 to 1; power ratio is the square of this value.'),
 'multipath.reflection_phase_rad': ('Reflection phase (rad)', 'Constant phase change, not derived from material or incidence angle.'),
 'solver.enabled': ('Generate solution and metrics', 'Reference least-squares solution from pseudorange and Doppler, not a physical receiver output.'),
 'solver.initial_enu_m': ('Initial solution [x, y, z] (m)', 'Independent starting position for the first epoch; later epochs reuse the last estimate.'),
 'solver.max_iterations': ('Maximum iterations per epoch', 'Positive integer; numerical convergence does not guarantee an accurate solution.'),
 'solver.position_tolerance_m': ('Position iteration tolerance (m)', 'Positive numerical stopping threshold, not an accuracy guarantee.'),
 'solver.max_step_m': ('Maximum position step (m)', 'Positive limit on each position update.'),
 'solver.apply_atmosphere': ('Apply atmosphere in solution', 'Use the same simplified atmosphere model in the direct-path solver.'),
 'solver.position_normalization_m': ('Position error scale (m)', 'Positive normalization scale; default 30 m is a research convention.'),
 'solver.velocity_normalization_mps': ('Velocity error scale (m/s)', 'Positive normalization scale; default 80/3.6 m/s is a research convention.'),
 'iq.enabled': ('Generate I/Q signal file', 'Saves complex baseband and metadata. Default signal lacks valid LNAV for cold-start positioning.'),
 'iq.start_s': ('I/Q start time (s)', 'Nonnegative time relative to simulation start; the full I/Q window must fit.'),
 'iq.duration_s': ('I/Q duration (s)', 'Positive; longer durations increase data and computation.'),
 'iq.sample_rate_hz': ('I/Q complex sample rate (sample/s)', 'Complex samples per second; at least 2.046 MS/s, with the main lobe inside Nyquist.'),
 'iq.intermediate_frequency_hz': ('Digital intermediate frequency (Hz)', 'Zero means zero-IF complex baseband; must meet the Nyquist constraint.'),
 'iq.format': ('I/Q binary format', 'ci16_le: interleaved little-endian int16; cf32_le: little-endian complex64.'),
 'iq.chunk_samples': ('Complex samples per chunk', 'Positive integer controlling memory; chunk size must not change waveform content.'),
 'iq.output_name': ('I/Q output filename', 'Base filename only, e.g. signal.iq; must not collide with fixed result files.'),
 'iq.adc_full_scale_sigma': ('ADC full-scale sigma', 'Positive; used only for int16 quantization to control clipping and range utilization.'),
 'iq.navigation_bits_file': ('External navigation symbols', 'Optional local 50 bit/s symbols. Empty uses +1; LNAV parity and ephemeris consistency are not validated.'),
 'iq.add_noise': ('Add I/Q AWGN', 'Adds complex Gaussian noise independently of observation CSV noise.'),
 'iq.max_output_bytes': ('I/Q file size limit (bytes)', 'Limits the expected I/Q file size only; disk space is checked separately.'),
}

_CLOCK = {
 'bias_s': ('initial bias (s)', 'Initial clock bias; a positive value increases equivalent code and carrier path.'),
 'drift_sps': ('linear drift (s/s)', 'Frequency error; a positive value increases clock bias over time.'),
 'drift_rate_sps2': ('drift rate (s/s²)', 'The quadratic clock-bias term is 0.5 × drift rate × time².'),
 'sinusoid_amplitude_s': ('sinusoidal bias amplitude (s)', 'Controlled sinusoidal clock disturbance, not a full oscillator noise spectrum.'),
 'sinusoid_period_s': ('sinusoidal bias period (s)', 'Positive even when amplitude is zero.'),
}
for _name, (_label, _help) in _CLOCK.items():
    FIELDS['receiver_clock.' + _name] = ('Receiver clock ' + _label, _help)
    FIELDS['relay.transmitters.*.clock.' + _name] = ('Clock ' + _label, _help + ' Independent error amplitude must be zero for transparent relay.')


def translate_error(message):
    """Translate known import errors; preserve unknown diagnostics verbatim."""
    import re
    exact = {
        '导入观测数据时须启用“生成定位解与误差统计”。': 'Enable “Generate solution and metrics” when importing observations.',
        '导入 CSV 超过 100 MiB，请分段导入。': 'Imported CSV exceeds 100 MiB; split it into smaller files.',
        '导入 CSV 必须使用 UTF-8 编码，可带 BOM。': 'Imported CSV must be UTF-8 encoded, optionally with a BOM.',
        '导入 CSV 为空，请提供已补偿的伪距和多普勒观测。': 'Imported CSV is empty; provide corrected pseudorange and Doppler observations.',
        '导入 CSV 缺少表头。': 'Imported CSV has no header row.',
        '导入 CSV 表头不能为空。': 'Imported CSV header names cannot be blank.',
        '导入 CSV 存在重复表头。': 'Imported CSV has duplicate header names.',
        '导入 CSV 超过 200 万条观测，请分段导入。': 'Imported CSV exceeds two million observations; split it into smaller files.',
        '导入 CSV 没有观测行，至少需要一条已补偿观测。': 'Imported CSV has no observation rows; at least one corrected observation is required.',
    }
    if message in exact:
        return exact[message]
    prefixes = (
        ('导入 CSV 缺少必要字段：', 'Imported CSV is missing required fields: '),
    )
    for source, target in prefixes:
        if message.startswith(source):
            return target + message[len(source):]
    patterns = (
        (r'无法读取已补偿观测文件：(.*)（(.*)）', r'Cannot read corrected observation file: \1 (\2)'),
        (r'导入 CSV 格式错误（第 (\d+) 行）：(.*)', r'Imported CSV format error on line \1: \2'),
        (r'导入 CSV 第 (\d+) 行：(.+) 不能为空。', r'Imported CSV line \1: \2 cannot be empty.'),
        (r'导入 CSV 第 (\d+) 行：(.+) 必须为有限数值。', r'Imported CSV line \1: \2 must be a finite number.'),
        (r'导入 CSV 第 (\d+) 行：(.+) 不能是 NaN 或无穷大。', r'Imported CSV line \1: \2 cannot be NaN or infinite.'),
        (r'导入 CSV 第 (\d+) 行：数据列数多于表头。', r'Imported CSV line \1: more data columns than header columns.'),
        (r'导入 CSV 第 (\d+) 行：time_s 必须位于 \[0, (.*)\] 秒，请核对起始时间和仿真时长。', r'Imported CSV line \1: time_s must be in [0, \2] seconds; check the time origin and duration.'),
        (r'导入 CSV 第 (\d+) 行：prn 必须为 1～32 的整数，不使用 G 前缀、前导零或小数。', r'Imported CSV line \1: prn must be an integer from 1 to 32, without a G prefix, leading zeros or decimals.'),
        (r'导入 CSV 第 (\d+) 行：PRN (\d+) 不在当前配置选用的卫星中，请在卫星 PRN 列表中设置数据对应的卫星。', r'Imported CSV line \1: PRN \2 is not selected; add the data satellites to the PRN list.'),
        (r'导入 CSV 第 (\d+) 行：pseudorange_m 必须大于零，单位为 m。', r'Imported CSV line \1: pseudorange_m must be greater than zero, in meters.'),
        (r'导入 CSV 第 (\d+) 行：valid 必须为 true、false、1 或 0。', r'Imported CSV line \1: valid must be true, false, 1 or 0.'),
        (r'导入 CSV 第 (\d+) 行：重复的 \(time_s, prn\)=\((.*), (.*)\)。', r'Imported CSV line \1: duplicate (time_s, prn)=(\2, \3).'),
    )
    for pattern, translation in patterns:
        if re.fullmatch(pattern, message):
            return re.sub(pattern, translation, message)
    return message
