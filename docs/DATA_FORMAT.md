# 输出文件与字段说明

当前新增“已补偿观测导入”模式，详见 [导入协议](OBSERVATION_IMPORT.md)。最少输入列为 `time_s,prn,pseudorange_m,doppler_hz`，可选 valid。导入时不生成模拟观测或 I/Q；保留 `imported_observations.csv` 和 `observation_import.json`，输出规范化观测和定位结果。默认没有真值，所有真值误差列为空、误差统计为 null；可选仿真配置参考写入 `trajectory_reference.csv`，不写 `trajectory_truth.csv`。生成模式的原文件含义见下文。

两种模式的定位结果增加 `estimated_speed_mps`（当前维度的速度大小）和 `estimated_horizontal_speed_mps`（水平速度大小）；`metrics.json` 增加 `reference_available` 与 `reference_kind`，运行摘要增加 `observation_source` 与 `iq_generated`。读取误差时应先判断参考是否存在。

文件由命令行 `--output` 指定的全新目录保存，已有目录不会被覆盖。CSV 使用 UTF-8 BOM，JSON 为 UTF-8。默认布尔值在 CSV 中写为 `True/False`；解算失效的可空结果为留空。单位由字段后缀或本说明给出。

必须区分三种数据：

1. **传播/轨迹真值**：由配置和物理模型计算，可用于核查模型。
2. **统计模型观测**：LOS 真值加上指定的代码/多普勒误差，不是从 I/Q 经过实际接收机提取的观测。
3. **参考接收机估计**：用第 2 项输入执行真实卫星假设下的最小二乘输出，不是真实手机测量，也不是已验证的 GNSS-SDR 输出。

## 1. 文件清单

| 文件 | 条件 | 内容 |
|---|---|---|
| `config.resolved.json` | 正常创建输出目录后 | 经过默认合并和外部路径解析的完整配置。 |
| `provenance.json` | 正常创建输出目录后 | 环境、命令、代码/输入哈希、种子、模型边界和资料来源。 |
| `trajectory_truth.csv` | 模型生成成功 | 用户轨迹和速度真值。 |
| `observations.csv` | 模型生成成功 | 每历元每颗所选卫星的一条 LOS 模型观测及分项。 |
| `channel_truth.npz` | 模型生成成功 | I/Q 所用的逐路径传播参数时间序列，包含反射时可重复 PRN。 |
| `scene.json` | 模型生成成功 | 星历来源、PRN、映射、发射点和 NPZ 列对应关系。 |
| `receiver_solution.csv` | solver.enabled | 参考最小二乘接收机输出与误差。 |
| `metrics.json` | solver.enabled | 收敛率和成功历元误差汇总。 |
| `signal.iq` 或自定义名 | iq.enabled | 复数基带采样文件。 |
| `iq_metadata.json` | I/Q 完成 | 文件格式、时间、尺度、噪声、导航模式、SHA256。 |
| `run_summary.json` | 整次运行完成 | 运行时长和数据规模等摘要。 |
| `run_error.json` | 运行 try 范围内失败 | 异常类型与信息；失败前写出的文件可能仍在，应整体保留为失败实验。初始参数/输入读取失败可能早于该文件创建。 |

## 2. `trajectory_truth.csv`

每行一个合并后的历元，包含常规时间网格、按累计路程的等距离采样点、中间路径点和结束历元。`time_s` 对应接收机时间轴；用户真值由该时刻扣除接收机钟差后在物理时间轨迹上求值。

| 字段 | 单位/类型 | 含义 |
|---|---|---|
| `time_s` | s | 从仿真起始接收机时间算起的时刻。 |
| `gps_week` | 完整 GPS 周 | 接收机标记时间的 GPS 周，跨周时递增。 |
| `gps_sow` | s | 与该标记时间对应的周内秒，归一化到 `[0,604800)`。 |
| `x_m`, `y_m`, `z_m` | m | 用户真实 ENU 东、北、上坐标。 |
| `vx_mps`, `vy_mps`, `vz_mps` | m/s | 真实运动速度向量。 |
| `distance_sample` | bool | 是否为沿程距离采样点。该标记也包含起终点及中间路径点对应的历元。 |

## 3. `observations.csv`

每行对应 `(time_s, prn)`。反射路径不单独写入此文件；即使启用多径，CSV 仍是 LOS 统计观测。下游解算须按 `valid` 过滤，不能因为行存在就当作成功接收。

| 字段 | 单位/类型 | 含义 |
|---|---|---|
| `time_s` | s | 接收机标记历元，与轨迹表关联。 |
| `prn` | 整数 | GPS 卫星信号码编号，I/Q 支持 1–32。 |
| `transmitter_id` | 字符串 | 室内发射点编号；direct 模式为 `direct`。 |
| `pseudorange_truth_m` | m | LOS 代码路径真值，含天空、室内、固定链路、钟差、大气、TGD、距离补偿；不是纯几何距离。 |
| `carrier_path_truth_m` | m | LOS 连续载波相位等效路径，电离层取负号，无 TGD；未附加整数模糊度。 |
| `pseudorange_m` | m | `pseudorange_truth_m + code_noise_m`，供参考接收机使用的统计模型观测。 |
| `doppler_truth_hz` | Hz | `-carrier_range_rate_mps/lambda_L1`，尚未加观测估计噪声。 |
| `doppler_hz` | Hz | `doppler_truth_hz + doppler_noise_hz`。采用路径增长对应负频移的符号约定。 |
| `carrier_range_rate_mps` | m/s | 完整载波路径的中心差分变化率；包括钟漂、卫星运动、用户运动与补偿。 |
| `code_noise_m` | m | 实际加入该行的代码估计误差。 |
| `doppler_noise_hz` | Hz | 实际加入该行的多普勒估计误差。 |
| `valid` | bool | 综合逐时仰角、随机丢失和可选 C/N0 门限后的有效性。不是实际软件接收机锁定状态。 |
| `receiver_clock_drift_mps` | m/s | 接收机米单位钟差的中心差分；除以 c 得 s/s。 |
| `cn0_dbhz` | dB-Hz | 该 LOS 路径的模型 C/N0，为参考值加路径电压增益的 20log10。 |
| `azimuth_deg` | ° | 天空段到卫星的方位角，北为 0°，向东增加。 |
| `elevation_deg` | ° | 天空段到卫星的仰角；relay 模式参照室外接收天线。 |
| `space_range_m` | m | 经过发射时刻和地球自转处理的天空几何距离。 |
| `indoor_path_m` | m | 室内发射点到用户的 LOS 几何距离；direct 为 0。 |
| `fixed_relay_path_m` | m | `cable_length/velocity_factor + c*processing_delay`；direct 为 0。 |
| `receiver_clock_m` | m | 加入路径的接收机钟差，正值使代码/载波路径增长。 |
| `relay_clock_m` | m | regenerative 模式等效发射点钟差；transparent 要求为零。 |
| `troposphere_m` | m | 加到代码和载波的正对流层延迟。 |
| `ionosphere_code_m` | m | 正代码电离层延迟；载波使用其负值。 |
| `range_comp_m` | m | 代码路径补偿 `q_code`；正值延长路径。 |
| `compensation_doppler_hz` | Hz | 补偿本身造成的理论频移，包括距离导数与额外独立频移。 |
| `satellite_clock_s` | s | 卫星钟差；路径中为 `-c*satellite_clock_s`。RINEX 模式含相对论周期项、不含 TGD。 |
| `tgd_s` | s | GPS L1 TGD；代码路径额外加 `+c*tgd_s`，载波不加。 |
| `satellite_x_ecef_m`, `satellite_y_ecef_m`, `satellite_z_ecef_m` | m | 发射时刻卫星位置经天空段地球自转旋转后的接收时刻 ECEF 坐标。 |

代码中所有噪声和补偿分项保存后，都可以重新核算观测构成。`pseudorange_truth_m` 包含接收机时钟，因此不能把它直接减去几何距离并全部解释为虚拟卫星误差。

## 4. `channel_truth.npz` 与 `scene.json`

NPZ 用 NumPy `np.load(path)` 读取；不需要对象反序列化。令 N 为时间数，K 为传播路径数：

| NPZ 数组 | 形状 | 单位/含义 |
|---|---|---|
| `t_s` | `(N,)` | s，严格递增模型时刻。 |
| `prn` | `(K,)` | 每一列属于哪个 PRN，允许重复。 |
| `cn0_dbhz` | `(K,)` | 每条路径在乘 gain 前的参考 C/N0。当前由同一配置参考值填充。 |
| `code_path_m` | `(N,K)` | 每历元每条路径的代码路径，供码时间延迟使用。 |
| `carrier_path_m` | `(N,K)` | 每条路径的载波等效路径，供载波相位使用。 |
| `gain_linear` | `(N,K)` | 非负电压增益，不是功率增益；无效/不可见路径为零。 |
| `phase_offset_rad` | `(N,K)` | 额外发射点及反射相位，单位 rad。 |

**K 是路径数，不一定是唯一卫星数。** 例如一颗 PRN 有 LOS 和六个墙面反射候选，会占 7 列；波形合成时这些列相干叠加。零增益列仍保留，以保持列对应关系稳定。

`scene.json` 的主要字段：

| 字段 | 含义 |
|---|---|
| `satellite_source` | provider 的来源说明：合成模式为轨道参数；RINEX 为文件、版本、记录数、健康/有效期规则和钟改正说明等。 |
| `selected_prns` | 本次选定的 PRN 顺序。 |
| `mapping` | PRN 到发射点 ID 的映射；JSON 中键为字符串。 |
| `transmitters` | 本次实际使用的完整发射点参数。 |
| `channel_paths` | 与 NPZ 第二维逐列对应的对象列表，每项有 `prn` 和 `path`；path 为 `los` 或墙面名称。 |

单路径有效 C/N0 的关系为：

```text
C/N0_effective_dBHz = cn0_dbhz[k] + 20*log10(gain_linear[n,k])
```

零增益表示信号缺失。不能把 observations.csv 中已经包含路径损耗的 cn0 再作为 NPZ 参考值并重复乘 gain，否则会重复衰减。

## 5. `receiver_solution.csv`

结果由统计模型观测计算。内部采用真实卫星直达假设，不使用室内发射点坐标修正位置。数值收敛不能证明位置真实可观测。

| 字段 | 单位/含义 |
|---|---|
| `time_s` | 接收机标记历元，s。 |
| `status` | `converged`、`insufficient_observations`、`singular_geometry` 或 `iteration_limit`。 |
| `solution_dimensions` | 2 或 3，表示本次解算与主误差统计使用的维度。 |
| `fixed_height_m` | 二维模式固定 ENU 高度，m；三维模式为空。这是约束值，不是 z 估计。 |
| `valid_satellites` | 参与该历元解算的有效 LOS 观测数。 |
| `iterations` | 本历元位置迭代次数。 |
| `geometry_condition_number` | 最后计算的接收机假设雅可比条件数；不是实际转发系统可观测性的完整证明。 |
| `pseudorange_residual_rms_m` | 解算后伪距残差 RMS，m；小残差仍可能对应错误位置。 |
| `estimated_clock_bias_m` | 接收机解出的米单位钟差。可以吸收公共链路延迟，不应直接等同真实 receiver_clock_m。 |
| `estimated_clock_drift_mps` | 接收机解出的钟漂等效变化率，m/s。 |
| `estimated_x_m`, `estimated_y_m` | 估计 ENU 水平位置，m。 |
| `estimated_vx_mps`, `estimated_vy_mps` | 估计 ENU 水平速度，m/s。 |
| `estimated_z_m`, `estimated_vz_mps` | 仅三维模式输出：估计高度（m）和垂直速度（m/s）。二维模式不包含这两列。 |
| `position_error_m` | 当前维度的欧氏位置误差，m；二维只计算 x、y，三维计算 x、y、z。 |
| `velocity_vector_error_mps` | 当前维度的速度向量误差，m/s；二维只计算 vx、vy，三维计算 vx、vy、vz。 |
| `speed_magnitude_error_mps` | 当前维度下两者速度大小之差的绝对值，m/s；方向错误可能在该指标中被隐藏。 |
| `horizontal_position_error_m` | 两种模式均输出：仅用 x、y 计算的位置误差，m。用于同口径比较二维/三维。 |
| `horizontal_velocity_vector_error_mps` | 两种模式均输出：仅用 vx、vy 计算的速度向量误差，m/s。 |
| `horizontal_speed_magnitude_error_mps` | 两种模式均输出：水平速度大小误差，m/s。 |

只有 converged 行填入最终位置、速度和误差；失效行的相关字段为空。失败历元仍计入总历元/收敛率。

二维固定高度只约束接收机解算，不会删除 `trajectory_truth.csv` 中的真实 z/vz，或把传播计算压平。真实高度与固定高度不一致时，可能影响水平解算；不能把不输出 z 理解为传播不再依赖高度。历史实验文件不会因本次代码更新而自动改变。

## 6. `metrics.json`

| 字段 | 含义 |
|---|---|
| `epoch_count` | 总解算历元数。 |
| `converged_count` | converged 历元数。 |
| `convergence_fraction` | 收敛数/总数；误差统计必须与此项一起报告。 |
| `solution_dimensions`, `error_axes` | 解算维度 2/3，以及主误差使用的 `['x','y']` 或 `['x','y','z']`。 |
| `fixed_height_m` | 二维固定高度，m；三维为 null。 |
| `position_error_m` | 当前解算维度的位置欧氏误差统计对象。 |
| `velocity_vector_error_mps` | 当前解算维度的速度向量误差统计对象。 |
| `speed_magnitude_error_mps` | 当前解算维度的速度大小误差统计对象。 |
| `horizontal_position_error_m` | 水平位置误差统计对象，两种模式同口径。 |
| `horizontal_velocity_vector_error_mps` | 水平速度向量误差统计对象，两种模式同口径。 |
| `horizontal_speed_magnitude_error_mps` | 水平速度大小误差统计对象，两种模式同口径。 |
| 各统计对象的 `mean`, `rms`, `p95`, `max` | 仅对成功历元的误差幅值计算均值、均方根、95%分位数、最大值。没有成功历元时对象为 null。 |
| `position_normalization_m` | 位置归一化分母，m。 |
| `velocity_normalization_mps` | 速度归一化分母，m/s。 |
| `position_mean_fraction` | 平均位置误差/位置分母；0.1 表示10%。 |
| `velocity_mean_fraction` | 平均速度向量误差/速度分母。 |
| `velocity_rms_fraction` | 速度向量误差 RMS/速度分母。 |
| `warning` | 提醒收敛不等于真实可观测，失败历元未进入误差统计。 |

统计使用合并后所有成功历元，当前不按时间间隔或路径距离加权。因此增加等距离点会改变样本权重，比较实验应使用一致采样规则。

## 7. I/Q 二进制文件

文件没有逐点时间、卫星编号或伪距字段。所有路径的数字复数信号叠加成同一个复数序列；读取方式由 iq_metadata.json 指定。

| 格式 | 二进制排列 | 每个复采样字节数 | NumPy 读取示例 |
|---|---|---:|---|
| `ci16_le` | I0(int16),Q0(int16),I1,Q1…，little-endian | 4 | `a=np.fromfile(path,dtype='<i2').reshape(-1,2)`；再转浮点并除以 quantizer_scale。 |
| `cf32_le` | I/Q 各 float32，little-endian complex64 | 8 | `z=np.fromfile(path,dtype='<c8')`。 |

第 n 个复采样点的相对时间为 `time_offset_s+n/sample_rate_hz`。采样数采用 `round(duration_s*fs)`，实际时长为采样数/fs；不要把 2 个 I/Q 标量当作 2 个独立复采样。

示例：4.092 MS/s、0.05 s、ci16 对应 204600 个复采样，818400 字节。没有任何电文保证由这个短片段产生定位结果。

## 8. `iq_metadata.json`

| 字段 | 含义 |
|---|---|
| `signal_file` | I/Q 文件基本名。 |
| `format`, `iq_order`, `byte_order` | 数据类型、I/Q交错顺序和字节序。 |
| `sample_rate_hz` | 复采样率。 |
| `center_frequency_hz` | GPS L1 RF 中心频率 1575420000 Hz。 |
| `intermediate_frequency_hz` | 数字中频；与 RF 中心频率是不同层次。 |
| `sample_count`, `duration_s`, `byte_count` | 复采样总数、实际时长和文件字节数。 |
| `time_offset_s`, `start_gps_sow` | 窗口相对起点及起始周内秒标记；GPS 周取 resolved config。 |
| `sha256` | 最终 I/Q 文件字节的 SHA256。 |
| `path_count`, `prns` | 传播路径数与唯一 PRN 列表。 |
| `noise_enabled` | 本次实际是否加入 AWGN。 |
| `complex_noise_variance` | 归一化复采样噪声方差；开启时为 fs，关闭为0。 |
| `noise_psd_convention` | 复 N0=1、I/Q 各方差 fs/2 的约定说明。 |
| `gain_convention` | gain 为电压增益、cn0为乘gain前参考值的说明。 |
| `quantizer_scale` | int16 数值=未量化值*scale 再舍入/削顶；cf32 记录为1。 |
| `clipped_components`, `clipping_fraction` | 超出 int16 范围的 I 或 Q 分量数，以及除以2*sample_count的比例。 |
| `mean_complex_power_before_quantization` | 加信号/噪声后、量化前的平均复数功率。 |
| `navigation_mode` | 默认 `constant_symbols_tracking_only`；外部位序列为 `external_50bps_symbols_unverified`。 |
| `navigation_bits_file` | 外部位文件路径或null。 |
| `standalone_cold_fix_validated` | 当前恒 false；生成波形并不表示完成冷启动定位验证。 |
| `limitations` | NAV、电文一致性、接收机未验证、矩形码片与前端未模拟等限制。 |
| `ca_reference` | C/A码 ICD 依据链接。 |

## 9. 外部导航位输入格式

以下只是格式示例，短位串不能代表有效 LNAV：

```json
{
  "1": {"start_gps_sow": 345599.0, "bits": [0, 1, 1, 0]},
  "8": {"start_gps_sow": 345599.0, "bits": [1, 0, 1, 0]}
}
```

每位持续0.02 s，二进制0映射+1、1映射−1。必须覆盖每条路径的卫星发射时刻，即含传播延迟后可能早于接收窗口的时刻，并为每个所选PRN提供数据。程序不循环补位，越界拒绝。程序不验证电文奇偶校验、TOW/周、星历或卫星健康的一致性；要进行完整导航需外部保证。

## 10. 配置、来源与运行记录

`provenance.json` 保存 `version`、`python`、`numpy`、`platform`、`command`、`seed`、`source_sha256`、`input_sha256`、`data_class`、`receiver_measurement_claim`、`output_directory`、`limitations` 和 `references`。

- `source_sha256` 记录 src 下各 Python 源文件；不等同整个项目全部文件的签名。
- `input_sha256` 记录实际外部 RINEX/NAV 位文件，便于确认是否更改。
- `data_class=SYNTHETIC_RESEARCH_DATA`、`receiver_measurement_claim=false` 明确标记数据性质。
- `config.resolved.json` 必须与原始配置一起保留；默认合并和相对路径转换后实际运行配置以此文件为准。

`run_summary.json` 字段为 `status`、`seconds`、`epoch_count`、`observation_rows`、`propagation_paths`、`selected_prns`；其中 seconds 为墙钟执行耗时，非场景仿真时长。`run_error.json` 字段为异常 `type`、`message`，应查看后用新输出目录重跑。

---

# English translation: Output Files and Fields

The new corrected-observation import mode is described in the [import protocol](OBSERVATION_IMPORT.md). Minimum input columns: `time_s,prn,pseudorange_m,doppler_hz`; `valid` is optional. Import does not generate simulated observations or I/Q; it keeps `imported_observations.csv` and `observation_import.json`, and outputs normalized observations and a positioning solution. By default no truth is available, all truth-error columns are blank and error statistics are null. An optional simulation-configuration reference is written to `trajectory_reference.csv`, not `trajectory_truth.csv`. Meanings of files in generation mode follow.

Both modes add `estimated_speed_mps` (speed magnitude in the current dimensions) and `estimated_horizontal_speed_mps` (horizontal speed magnitude) to positioning results; `metrics.json` adds `reference_available` and `reference_kind`, and the run summary adds `observation_source` and `iq_generated`. Check whether a reference exists before reading errors.

Files are stored in a new directory specified by command-line `--output`; existing directories are not overwritten. CSV uses UTF-8 BOM and JSON uses UTF-8. Boolean CSV values default to `True/False`; nullable results for failed solutions are blank. Units are indicated by field suffixes or below.

Distinguish three types of data:

1. **Propagation/trajectory truth**: calculated from configuration and physical models, suitable for checking the model.
2. **Statistical-model observations**: LOS truth plus specified code/Doppler errors, not observations extracted from I/Q by an actual receiver.
3. **Reference receiver estimates**: least-squares outputs using item 2 under a real-satellite assumption, not real phone measurements or validated GNSS-SDR output.

## 1. Files

| File | Condition | Contents |
|---|---|---|
| `config.resolved.json` | Output directory successfully created | Full configuration after defaults are merged and external paths resolved. |
| `provenance.json` | Output directory successfully created | Environment, command, code/input hashes, seed, model boundaries and sources. |
| `trajectory_truth.csv` | Model generation succeeds | True user trajectory and velocity. |
| `observations.csv` | Model generation succeeds | One LOS model observation and components per selected satellite and epoch. |
| `channel_truth.npz` | Model generation succeeds | Per-path propagation-parameter time series used for I/Q; PRNs can repeat with reflections. |
| `scene.json` | Model generation succeeds | Ephemeris source, PRNs, mapping, transmitters and NPZ column relationships. |
| `receiver_solution.csv` | solver.enabled | Reference least-squares receiver output and errors. |
| `metrics.json` | solver.enabled | Convergence and error summary for successful epochs. |
| `signal.iq` or custom name | iq.enabled | Complex-baseband sample file. |
| `iq_metadata.json` | I/Q completed | File format, time, scale, noise, navigation mode and SHA256. |
| `run_summary.json` | Entire run completed | Summary including elapsed run time and data volume. |
| `run_error.json` | Failure inside run try block | Exception type and message. Files written before failure may remain and should be retained together as a failed experiment. Initial parameter/input read failures can precede creation of this file. |

## 2. `trajectory_truth.csv`

Each row is a merged epoch, including the regular time grid, samples at equal intervals along the path, intermediate waypoints and the final epoch. `time_s` refers to the receiver timeline; user truth is evaluated on the physical-time trajectory after subtracting receiver clock bias from that time.

| Field | Unit/type | Meaning |
|---|---|---|
| `time_s` | s | Time from receiver time at the simulation start. |
| `gps_week` | full GPS week | GPS week of the receiver time tag, incremented at week rollover. |
| `gps_sow` | s | Seconds of week for the time tag, normalized to `[0,604800)`. |
| `x_m`, `y_m`, `z_m` | m | True user ENU east, north and up coordinates. |
| `vx_mps`, `vy_mps`, `vz_mps` | m/s | True motion velocity vector. |
| `distance_sample` | bool | Whether the epoch is a path-distance sample. This includes the start, end and intermediate waypoints. |

## 3. `observations.csv`

Each row corresponds to `(time_s, prn)`. Reflection paths are not written separately; even with multipath enabled the CSV contains LOS statistical observations. Downstream solutions must filter on `valid`; row existence does not imply successful reception.

| Field | Unit/type | Meaning |
|---|---|---|
| `time_s` | s | Receiver-tagged epoch, linked to the trajectory table. |
| `prn` | integer | GPS satellite signal-code number; I/Q supports 1–32. |
| `transmitter_id` | string | Indoor transmitter ID; `direct` in direct mode. |
| `pseudorange_truth_m` | m | True LOS code path including space, indoor, fixed link, clocks, atmosphere, TGD and range compensation; not purely geometric distance. |
| `carrier_path_truth_m` | m | Continuous LOS carrier-phase equivalent path; ionosphere has the opposite sign and TGD is absent; integer ambiguity is not added. |
| `pseudorange_m` | m | `pseudorange_truth_m + code_noise_m`, statistical-model observation for the reference receiver. |
| `doppler_truth_hz` | Hz | `-carrier_range_rate_mps/lambda_L1`, before observation estimation noise. |
| `doppler_hz` | Hz | `doppler_truth_hz + doppler_noise_hz`; increasing path corresponds to negative frequency shift. |
| `carrier_range_rate_mps` | m/s | Central-difference rate of the full carrier path, including clock drift, satellite motion, user motion and compensation. |
| `code_noise_m` | m | Code estimation error actually added to the row. |
| `doppler_noise_hz` | Hz | Doppler estimation error actually added to the row. |
| `valid` | bool | Validity after time-varying elevation, random dropout and optional C/N0 gate; not actual software-receiver lock state. |
| `receiver_clock_drift_mps` | m/s | Central difference of receiver clock bias in meters; divide by c for s/s. |
| `cn0_dbhz` | dB-Hz | Model C/N0 for the LOS path: reference plus 20log10 of path voltage gain. |
| `azimuth_deg` | ° | Satellite azimuth along the space path, north 0°, increasing eastward. |
| `elevation_deg` | ° | Space-path elevation; referenced to outdoor antenna in relay mode. |
| `space_range_m` | m | Space geometric range after transmit-time and Earth-rotation treatment. |
| `indoor_path_m` | m | LOS geometric distance from indoor transmitter to user; zero in direct mode. |
| `fixed_relay_path_m` | m | `cable_length/velocity_factor + c*processing_delay`; zero in direct mode. |
| `receiver_clock_m` | m | Receiver clock bias added to the path; positive increases code/carrier path. |
| `relay_clock_m` | m | Equivalent transmitter clock bias in regenerative mode; transparent requires zero. |
| `troposphere_m` | m | Positive tropospheric delay added to code and carrier. |
| `ionosphere_code_m` | m | Positive code ionospheric delay; carrier uses its negative. |
| `range_comp_m` | m | Code-path compensation `q_code`; positive lengthens the path. |
| `compensation_doppler_hz` | Hz | Theoretical frequency shift caused by compensation, including range derivative and extra independent frequency shift. |
| `satellite_clock_s` | s | Satellite clock bias; path contribution is `-c*satellite_clock_s`. RINEX includes periodic relativity, excludes TGD. |
| `tgd_s` | s | GPS L1 TGD; code path adds `+c*tgd_s`, carrier does not. |
| `satellite_x_ecef_m`, `satellite_y_ecef_m`, `satellite_z_ecef_m` | m | Transmit-time satellite position rotated for Earth rotation along the space path into reception-time ECEF coordinates. |

Saved noise and compensation components permit recalculation of observation composition. `pseudorange_truth_m` includes receiver clock bias, so subtracting geometric distance from it cannot be interpreted entirely as virtual-satellite error.

## 4. `channel_truth.npz` and `scene.json`

Read NPZ with NumPy `np.load(path)`; object deserialization is not needed. Let N be the number of times and K the number of propagation paths:

| NPZ array | Shape | Unit/meaning |
|---|---|---|
| `t_s` | `(N,)` | Strictly increasing model times, s. |
| `prn` | `(K,)` | PRN for each column; repetition allowed. |
| `cn0_dbhz` | `(K,)` | Reference C/N0 before multiplying by gain for each path; currently filled from the same configured reference. |
| `code_path_m` | `(N,K)` | Code path per epoch and path, used for code time delay. |
| `carrier_path_m` | `(N,K)` | Carrier equivalent path, used for carrier phase. |
| `gain_linear` | `(N,K)` | Nonnegative voltage gain, not power gain; zero for invalid/invisible paths. |
| `phase_offset_rad` | `(N,K)` | Additional transmitter and reflection phase, rad. |

**K is the number of paths, not necessarily unique satellites.** For example one PRN with LOS and six wall-reflection candidates occupies seven columns; these are coherently added in waveform synthesis. Zero-gain columns are retained for stable column correspondence.

Main `scene.json` fields:

| Field | Meaning |
|---|---|
| `satellite_source` | Provider source description: orbital parameters for synthetic mode; file, version, record count, health/validity rules and clock correction details for RINEX. |
| `selected_prns` | Selected PRNs in their order for the run. |
| `mapping` | PRN to transmitter-ID mapping; JSON keys are strings. |
| `transmitters` | Full transmitter parameters actually used. |
| `channel_paths` | Object list corresponding column by column to NPZ's second dimension; each has `prn` and `path`, where path is `los` or a surface name. |

Single-path effective C/N0:

```text
C/N0_effective_dBHz = cn0_dbhz[k] + 20*log10(gain_linear[n,k])
```

Zero gain means no signal. Do not use the `observations.csv` C/N0, which already includes path loss, as the NPZ reference and multiply gain again; that would duplicate attenuation.

## 5. `receiver_solution.csv`

Results are calculated from statistical-model observations. The solver assumes real satellite direct paths and does not use indoor-transmitter coordinates to correct position. Numerical convergence does not prove real position observability.

| Field | Unit/meaning |
|---|---|
| `time_s` | Receiver-tagged epoch, s. |
| `status` | `converged`, `insufficient_observations`, `singular_geometry`, or `iteration_limit`. |
| `solution_dimensions` | 2 or 3, the dimensions used by this solution and primary error statistics. |
| `fixed_height_m` | Fixed ENU height in 2D, m; blank in 3D. This is a constraint, not a z estimate. |
| `valid_satellites` | Number of valid LOS observations used at the epoch. |
| `iterations` | Position-iteration count at this epoch. |
| `geometry_condition_number` | Last computed condition number of the receiver-assumed Jacobian; not complete proof of actual relay-system observability. |
| `pseudorange_residual_rms_m` | Post-solution pseudorange residual RMS, m; small residual can still correspond to a wrong position. |
| `estimated_clock_bias_m` | Estimated receiver clock bias in meters. It may absorb common link delay and should not be equated directly to true `receiver_clock_m`. |
| `estimated_clock_drift_mps` | Estimated clock-drift equivalent rate, m/s. |
| `estimated_x_m`, `estimated_y_m` | Estimated ENU horizontal position, m. |
| `estimated_vx_mps`, `estimated_vy_mps` | Estimated ENU horizontal velocity, m/s. |
| `estimated_z_m`, `estimated_vz_mps` | 3D only: estimated height (m) and vertical velocity (m/s). These columns are absent in 2D. |
| `position_error_m` | Euclidean position error in current dimensions, m; x/y in 2D and x/y/z in 3D. |
| `velocity_vector_error_mps` | Velocity-vector error in current dimensions, m/s; vx/vy in 2D and vx/vy/vz in 3D. |
| `speed_magnitude_error_mps` | Absolute difference in speed magnitude in current dimensions, m/s; direction error can be hidden. |
| `horizontal_position_error_m` | Output in both modes: position error using x/y only, m; same-basis 2D/3D comparison. |
| `horizontal_velocity_vector_error_mps` | Output in both modes: velocity-vector error using vx/vy only, m/s. |
| `horizontal_speed_magnitude_error_mps` | Output in both modes: horizontal speed-magnitude error, m/s. |

Only `converged` rows contain final position, velocity and errors; corresponding fields in failed rows are blank. Failed epochs still count toward total epochs and convergence fraction.

The 2D fixed height constrains the receiver solution only; it does not delete true z/vz from `trajectory_truth.csv` or flatten propagation calculations. A mismatch between true and fixed height can affect the horizontal solution. Absence of z output does not mean propagation is independent of height. Historical experiment files do not change automatically when code is updated.

## 6. `metrics.json`

| Field | Meaning |
|---|---|
| `epoch_count` | Total solution epochs. |
| `converged_count` | Number of converged epochs. |
| `convergence_fraction` | Converged count / total; report error statistics alongside this value. |
| `solution_dimensions`, `error_axes` | Solution dimensions 2/3 and `['x','y']` or `['x','y','z']` used for primary errors. |
| `fixed_height_m` | Fixed height in 2D, m; null in 3D. |
| `position_error_m` | Euclidean position-error statistics object for the current dimensions. |
| `velocity_vector_error_mps` | Velocity-vector error statistics object for the current dimensions. |
| `speed_magnitude_error_mps` | Speed-magnitude error statistics object for the current dimensions. |
| `horizontal_position_error_m` | Horizontal position-error statistics object, same basis in both modes. |
| `horizontal_velocity_vector_error_mps` | Horizontal velocity-vector error statistics object, same basis in both modes. |
| `horizontal_speed_magnitude_error_mps` | Horizontal speed-magnitude error statistics object, same basis in both modes. |
| Each statistics object's `mean`, `rms`, `p95`, `max` | Mean, root mean square, 95th percentile and maximum of error magnitudes over successful epochs only. Object is null if none succeed. |
| `position_normalization_m` | Position normalization denominator, m. |
| `velocity_normalization_mps` | Velocity normalization denominator, m/s. |
| `position_mean_fraction` | Mean position error / position denominator; 0.1 means 10%. |
| `velocity_mean_fraction` | Mean velocity-vector error / velocity denominator. |
| `velocity_rms_fraction` | Velocity-vector error RMS / velocity denominator. |
| `warning` | Warns that convergence is not true observability and failed epochs are excluded from error statistics. |

Statistics use all successful merged epochs, currently without time-interval or path-distance weighting. Adding equidistant points therefore changes sample weights; use consistent sampling rules across comparative experiments.

## 7. I/Q binary file

The file has no per-sample time, satellite ID or pseudorange fields. Digital complex signals for all paths are added into one complex sequence; `iq_metadata.json` specifies how to read it.

| Format | Binary ordering | Bytes per complex sample | NumPy reading example |
|---|---|---:|---|
| `ci16_le` | I0(int16), Q0(int16), I1, Q1…, little-endian | 4 | `a=np.fromfile(path,dtype='<i2').reshape(-1,2)`; convert to floating point and divide by quantizer_scale. |
| `cf32_le` | I and Q float32, little-endian complex64 | 8 | `z=np.fromfile(path,dtype='<c8')`. |

Relative time of complex sample n is `time_offset_s+n/sample_rate_hz`. Sample count is `round(duration_s*fs)` and actual duration is sample count/fs. Do not treat two I/Q scalars as two independent complex samples.

Example: 4.092 MS/s, 0.05 s and ci16 give 204600 complex samples and 818400 bytes. No navigation message guarantees a positioning result from this short segment.

## 8. `iq_metadata.json`

| Field | Meaning |
|---|---|
| `signal_file` | I/Q file base name. |
| `format`, `iq_order`, `byte_order` | Data type, I/Q interleaving order and byte order. |
| `sample_rate_hz` | Complex sample rate. |
| `center_frequency_hz` | GPS L1 RF center frequency 1575420000 Hz. |
| `intermediate_frequency_hz` | Digital intermediate frequency; distinct from RF center frequency. |
| `sample_count`, `duration_s`, `byte_count` | Complex sample count, actual duration and file byte count. |
| `time_offset_s`, `start_gps_sow` | Window offset from start and starting seconds-of-week tag; GPS week comes from resolved config. |
| `sha256` | SHA256 of final I/Q file bytes. |
| `path_count`, `prns` | Number of propagation paths and unique PRN list. |
| `noise_enabled` | Whether AWGN was actually added. |
| `complex_noise_variance` | Normalized complex-sample noise variance: fs when enabled, 0 when disabled. |
| `noise_psd_convention` | Convention: complex N0=1, I and Q each have variance fs/2. |
| `gain_convention` | Explanation that gain is voltage gain and cn0 is reference before multiplying gain. |
| `quantizer_scale` | int16 value = unquantized value × scale, then rounded/clipped; recorded as 1 for cf32. |
| `clipped_components`, `clipping_fraction` | Number of I or Q components outside int16 range and fraction after division by 2*sample_count. |
| `mean_complex_power_before_quantization` | Mean complex power after signal/noise addition and before quantization. |
| `navigation_mode` | Default `constant_symbols_tracking_only`; external bits use `external_50bps_symbols_unverified`. |
| `navigation_bits_file` | External bit-file path or null. |
| `standalone_cold_fix_validated` | Currently always false; waveform generation does not mean cold-start positioning is validated. |
| `limitations` | Limitations including NAV/message consistency, unvalidated receiver, rectangular chips and unmodeled front end. |
| `ca_reference` | Link to the C/A-code ICD source. |

## 9. External navigation-bit input format

This is only a format example; short bit strings cannot represent valid LNAV:

```json
{
  "1": {"start_gps_sow": 345599.0, "bits": [0, 1, 1, 0]},
  "8": {"start_gps_sow": 345599.0, "bits": [1, 0, 1, 0]}
}
```

Each bit lasts 0.02 s; binary 0 maps to +1 and 1 maps to −1. Data must cover satellite transmission times for every path, including times before the receiver window due to propagation delay, and must be supplied for every selected PRN. Bits are not looped or padded; out-of-range access is rejected. The program does not validate message parity, TOW/week, ephemeris or satellite health consistency; complete navigation requires external assurance of these properties.

## 10. Configuration, provenance and run records

`provenance.json` stores `version`, `python`, `numpy`, `platform`, `command`, `seed`, `source_sha256`, `input_sha256`, `data_class`, `receiver_measurement_claim`, `output_directory`, `limitations` and `references`.

- `source_sha256` records Python source files under src; it is not a signature of every file in the project.
- `input_sha256` records actual external RINEX/NAV bit files so changes can be identified.
- `data_class=SYNTHETIC_RESEARCH_DATA` and `receiver_measurement_claim=false` explicitly identify the nature of the data.
- `config.resolved.json` must be retained with the original configuration; after merging defaults and converting relative paths, this file is authoritative for the actual run configuration.

`run_summary.json` fields are `status`, `seconds`, `epoch_count`, `observation_rows`, `propagation_paths`, `selected_prns`. Here seconds is wall-clock execution time, not the simulated scene duration. `run_error.json` contains exception `type` and `message`; inspect it and rerun with a new output directory.
