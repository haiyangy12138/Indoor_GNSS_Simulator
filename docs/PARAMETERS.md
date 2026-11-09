# 配置参数逐项说明

当前应用的原“补偿”页已替换成可留空的“上传 / 导入数据”。新增 `input_observations.corrected_csv`（默认 null）和 `input_observations.compare_reference`（默认 false）。前者导入已补偿的完整伪距、多普勒，后者可选对比同一配置的仿真参考轨迹。应用生成时不再施加内置补偿；下文补偿函数参数仅用于历史命令行实验复现。格式与输出见 [已补偿观测导入](OBSERVATION_IMPORT.md)。

参数以 `src/indoor_gnss/config.py` 的 `DEFAULT` 为准。表中的“建议”用于指导实验设计，不等于所有建议都由程序自动强制检查；数学公式和未实现因素见 [PHYSICS.md](PHYSICS.md)。默认配置是一组可运行演示条件，不代表已辨识的实际设备参数或最优设计。

## 1. 配置文件规则

JSON 支持只写需要更改的普通对象字段，未指定字段保留程序默认值。所有参数名区分大小写；未知键会报错，避免拼错后静默使用默认值。数值使用国际单位制；角度仅在后缀 `_deg` 时使用度，后缀 `_rad` 使用弧度。

- `relay.transmitters` 是完整替换的列表，不与默认列表逐项合并。每个发射点必须给出本表列出的全部字段，包含完整 `clock` 对象。建议复制默认条目后修改。
- `relay.mapping` 是 PRN 字符串到发射点 ID 的字典，例如 `{"1":"V1","8":"V2"}`。该字典整体替换；未写的所选 PRN 按发射点列表循环分配。键用 `"1"`，不要写 `"G01"`。
- `compensation.per_prn` 是按 PRN 字符串指定的补偿对象，每个对象可以只写部分补偿字段；具体补全语义见第 7 节。
- `satellites.rinex_nav_file`、`iq.navigation_bits_file` 的相对路径以 JSON 配置所在目录为基准，加载后保存绝对路径。输出路径由命令行 `--output` 指定。
- 不能用 JSON 的 `NaN`、`Infinity` 等非有限数值。`null` 仅用于文档说明的可空字段。
- 生成器拒绝覆盖已存在的输出目录。每次修改参数应换一个新实验目录，保留旧配置和旧结果。

最小覆盖例：

```json
{
  "seed": 20261106,
  "observations": {"add_noise": false},
  "iq": {"enabled": false}
}
```

## 2. 全局、时间与坐标

| 完整参数名 | 单位/类型 | 默认值 | 用途、建议与依赖 |
|---|---|---|---|
| `seed` | 非负整数 | `20261105` | 主随机种子。时钟、观测噪声和 I/Q AWGN 使用独立子流；对照实验保持种子以控制随机条件，多次试验再更换种子。 |
| `time.gps_week` | 完整 GPS 周，整数 | `2443` | 起始 GPST 周；必须与 RINEX/外部 NAV 位时间对应，不是截断的 10-bit 周。 |
| `time.gps_sow` | s | `345600.0` | 起始 GPS 周内秒，范围 `[0,604800)`；不自动转换 UTC/闰秒。 |
| `time.duration_s` | s | `2.0` | 总仿真时长，必须大于零并覆盖整个运动过程和 I/Q 窗口。增加时长会增加观测数、计算量与可选 I/Q 文件量。 |
| `time.observation_interval_s` | s | `0.01` | 常规传播/观测时间网格。I/Q 路径参数在该网格上线性插值；快速运动、多径变化时应减小并做收敛检查。建议起步 `0.001–0.02`。 |
| `time.trajectory_distance_step_m` | m | `1.0` | 沿累计路程插入等距离轨迹采样点，步长必须大于零。等距离点、中间路径点与时间网格合并，观测时间间隔可能不均匀。 |
| `time.derivative_step_s` | s | `0.002` | 载波路径与钟差中心差分半步长，要求 `(0,0.1)`。过小易受浮点消减影响，过大跨越运动分段；建议用 `0.001/0.002/0.005` 比较稳定性。 |
| `site.latitude_deg` | ° | `31.2304` | WGS84 原点纬度，物理有效值 `[-90,90]`；同时用于局部旋转和大气模型。真实场景应替换为厂房位置。 |
| `site.longitude_deg` | ° | `121.4737` | WGS84 原点经度，建议 `[-180,180]`。 |
| `site.height_m` | m | `10.0` | WGS84 原点椭球高；不是自动转换后的海拔。 |
| `site.room_size_enu_m` | `[m,m,m]` | `[30,10,5]` | 东、北、上三个方向的室内尺寸；均须为正。轨迹和发射点须位于该范围及其边界。 |
| `site.outdoor_antenna_enu_m` | `[m,m,m]` | `[15,5,8]` | 室外接收天线 A 的局部 ENU 坐标；可高于房间上边界，转发天空段以此点接收。直达模式不使用其作为信号终点。 |

## 3. 用户轨迹

| 完整参数名 | 单位/类型 | 默认值 | 用途、建议与依赖 |
|---|---|---|---|
| `trajectory.start_enu_m` | `[m,m,m]` | `[0,5,1]` | 路径起点，必须位于房间内。 |
| `trajectory.waypoints_enu_m` | `[[m,m,m],…]` | `[]` | 可选中间路径点，按经过顺序填写。各点必须在房间内，相邻点不能重合。空列表表示直线。 |
| `trajectory.end_enu_m` | `[m,m,m]` | `[30,5,1]` | 路径终点，必须位于房间内。设置有效中间路径点后，终点可以与起点相同。 |
| `trajectory.start_time_s` | s | `0.2` | 物理时间上的出发时刻，出发前停留于起点。改变此值时注意 I/Q 窗口是否覆盖动态段。 |
| `trajectory.speed_mps` | m/s | `22.2222222222` | 巡航速度，即 80 km/h，须大于零。70 km/h 对应约 `19.4444444444`。不是向接收机提供的已知速度。 |
| `trajectory.acceleration_time_s` | s | `0.0` | 起步与停止各自的加/减速时长。零表示瞬时启停；正值使用恒加速度过渡。须非负且 `acceleration_time_s * speed_mps <= 路径长度`。路径长度为各线段长度之和，完整运动须落在总时长内。 |

## 4. 卫星与星历

| 完整参数名 | 单位/类型 | 默认值 | 用途、建议与依赖 |
|---|---|---|---|
| `satellites.source` | 枚举 | `"synthetic"` | `synthetic` 为演示圆轨道集合；`rinex` 为 RINEX 2/3 GPS 广播星历。前者不代表真实日期的天空。 |
| `satellites.rinex_nav_file` | 路径或 null | `null` | `source=rinex` 时必填；支持 GPS/混合 RINEX 2/3 NAV 及 `.gz`。不是观测文件，不支持 RINEX 4。 |
| `satellites.max_ephemeris_age_s` | s | `14400.0` | RINEX 最大允许星历年龄，必须为正；还受记录中 fit interval 的限制。应按资料有效期设定，不应靠放大此值强行复用过期星历。 |
| `satellites.allow_unhealthy` | bool | `false` | RINEX 是否允许健康标志非零的 GPS 星历。通常保持 false；实验性开启应明确标注。 |
| `satellites.count` | 整数 | `8` | 未显式提供 PRN 时，按起始仰角从高到低选取的卫星数，允许 1–32；可见星不足报错。解算三维位置通常还需要足够独立观测。 |
| `satellites.prns` | 整数列表 | `[]` | 空列表自动选择；非空则以显式列表为准，列表长度代替 `count`。不允许重复，须在起始时刻健康、可见；I/Q 实现仅支持 PRN 1–32。 |
| `satellites.elevation_mask_deg` | ° | `5.0` | 起始筛选与逐时可见性门限。建议 `5–15` 起步；降低门限会引入更低仰角及更强大气映射。 |
| `satellites.synthetic_count` | 整数 | `32` | 合成星座候选数，允许 1–32；仅 synthetic 有效。 |
| `satellites.synthetic_planes` | 整数 | `8` | 合成轨道面数，范围 1 至 synthetic_count；仅 synthetic 有效，不等于真实 GPS 轨道布局。 |
| `satellites.synthetic_radius_m` | m | `26560000.0` | 合成圆轨道的地心半径，不是离地高度，须大于 WGS84 赤道半径。 |
| `satellites.synthetic_inclination_deg` | ° | `55.0` | 合成圆轨道倾角，允许 0–180。 |
| `satellites.synthetic_raan_offset_deg` | ° | `0.0` | 合成轨道面的整体初始升交点赤经偏移，可用于改变演示天空几何。 |
| `satellites.epoch_gps_week` | GPS 周 | `2443` | 合成轨道参考历元周；与下一字段共同定义初始轨道相位和线性卫星钟参考。 |
| `satellites.epoch_gps_sow` | s | `345600.0` | 合成轨道参考周内秒；仅 synthetic 有效。 |
| `satellites.synthetic_clock_bias_s` | s | `0.0` | 合成卫星共同初始钟差；不是每颗 PRN 独立的时钟配置。 |
| `satellites.synthetic_clock_drift_sps` | s/s | `0.0` | 合成卫星共同线性钟漂；小量测试可从 `1e-12–1e-10` 起步，实际值应由目标设备/资料确定。 |
| `satellites.synthetic_tgd_s` | s | `0.0` | 合成 GPS L1 TGD，代码路径中以 `+c*TGD` 体现；载波不加。 |

## 5. 传播与发射点

| 完整参数名 | 单位/类型 | 默认值 | 用途、建议与依赖 |
|---|---|---|---|
| `propagation.mode` | 枚举 | `"relay"` | `relay` 为室外接收/室内转发；`direct` 为真实卫星直达基线，要求补偿为零。 |
| `propagation.earth_rotation` | bool | `true` | 是否修正天空段飞行期间地球自转，通常保持 true；关闭仅用于消融实验。 |
| `propagation.light_time_tolerance_s` | s | `1e-12` | 天空几何飞行时间迭代的收敛阈值；实现最多迭代 8 次。正的较小值如 `1e-10–1e-12` 可用，不代表其他模型达到同等精度。 |
| `propagation.min_path_m` | m | `0.05` | 用户到 LOS/反射镜像源的最短允许路径；小于此值拒绝运行，避免点源路径损耗奇异。并非精确的天线近场边界。 |
| `relay.architecture` | 枚举 | `"transparent"` | `transparent` 要求独立发射点钟差为零；`regenerative` 允许添加指定时钟误差。后者仍是等效模型。 |
| `relay.mapping` | 字典 | `{}` | PRN 字符串到发射点 ID 的静态映射；未列出的所选 PRN 循环分配。 |
| `relay.transmitters` | 对象列表 | 两个发射点 | 配置 1–4 个发射点，完整替换默认列表；逐点字段见下一表。 |
| `relay.min_spacing_m` | m | `8.0` | 两发射点间距的严格下界，须满足 `distance > min_spacing_m`。 |
| `relay.max_spacing_m` | m | `30.0` | 两发射点间距的严格上界，须满足 `distance < max_spacing_m`；单发射点无两两约束。 |

`relay.transmitters[k]` 的每项完整字段如下，V1/V2 值不同时用斜杠列出：

| 字段 | 单位/类型 | 默认 V1 / V2 | 用途、建议与依赖 |
|---|---|---|---|
| `id` | 字符串 | `V1` / `V2` | 唯一发射点编号，供 mapping 引用。 |
| `position_enu_m` | `[m,m,m]` | `[2,2,5]` / `[28,8,5]` | 室内坐标，须在房间或边界内且满足间距约束。 |
| `cable_length_m` | m | `20.0` | 物理线缆长度，非负；等效路径为长度除以速度因子。 |
| `cable_velocity_factor` | 无量纲 | `0.66` | 线缆信号速度与光速之比，范围 `(0,1]`；实际值应按线缆规格设置。假设群/相位延迟相同。 |
| `processing_delay_s` | s | `0.001` | 正的固定处理/缓冲延迟，非负；1 ms 等效约 300 km。大部分公共延迟可能被接收机钟差吸收，不能把它当作室内几何距离。 |
| `phase_offset_rad` | rad | `0.0` | 该发射点额外载波相位偏移；仅相位，不改变代码时延。 |
| `reference_distance_m` | m | `10.0` | 路径损耗标定距离，须大于零。在此距离、无额外损耗时，使用参考 C/N0。 |
| `path_loss_exponent` | 无量纲 | `2.0` | 功率路径损耗指数，非负；2 为自由空间距离指数模型，室内值需依据实测，不代表已做完整链路预算。 |
| `excess_loss_db` | dB | `0.0` | 固定附加衰减，正值减弱电压增益；建议从非负值开始。 |
| `clock` | 对象 | 零误差 CLOCK | 等效独立发射机时钟，完整字段见第 8 节。transparent 要求所有误差幅度为零。 |

## 6. 补偿字典

| 完整参数名 | 单位/类型 | 默认值 | 用途、建议与依赖 |
|---|---|---|---|
| `compensation.default` | 对象 | 零补偿 COMP | 对没有专属条目的 PRN 使用的补偿；逐字段见下表。 |
| `compensation.per_prn` | 字典 | `{}` | 按 PRN 字符串配置专属补偿，例如 `{"1":{"range_offset_m":2}}`；每条允许部分字段。 |
| `compensation.max_range_m` | m | `30.0` | 距离补偿绝对值上限；校验采用全时段保守解析包络。 |
| `compensation.max_doppler_hz` | Hz | `20.0` | 总补偿多普勒绝对值上限，包含距离补偿导数及显式频率控制。不是总天空多普勒上限。 |

以下字段适用于 `compensation.default` 及每个 `per_prn["PRN"]`：

| 字段 | 单位/类型 | 默认值 | 用途、建议与依赖 |
|---|---|---|---|
| `mode` | 枚举 | `"delay_coupled"` | `delay_coupled`：代码/载波同延迟，多普勒由延迟导数决定；`independent_frequency`：另外允许独立载波频移，代表硬件能力假设。 |
| `range_offset_m` | m | `0.0` | 初始常量路径补偿，正值延长路径。 |
| `range_rate_mps` | m/s | `0.0` | 距离补偿线性变化率，同时产生 `-range_rate_mps/lambda` Hz。 |
| `range_sine_m` | m | `0.0` | 正弦距离补偿振幅；频移振幅同时受振幅/周期制约。 |
| `range_period_s` | s | `5.0` | 正弦距离补偿周期，须大于零；即使振幅为零也须保留有效值。 |
| `frequency_offset_hz` | Hz | `0.0` | 额外常量载波频移，仅 independent_frequency 可非零。正值使载波相位随时间增加。 |
| `frequency_rate_hzps` | Hz/s | `0.0` | 额外频移线性斜率，仅 independent_frequency 可非零。 |
| `frequency_sine_hz` | Hz | `0.0` | 额外正弦频移振幅，仅 independent_frequency 可非零。 |
| `frequency_period_s` | s | `5.0` | 额外正弦频移周期，须大于零。 |

## 7. 部分覆盖与补偿约束示例

当前加载器对 `per_prn` 每项先复制本次已经合并的 `compensation.default`，再应用该项的部分字段。例如 default 设常量 5 m、PRN1 专属条目只写 `range_rate_mps`，PRN1 仍保留常量 5 m，同时加入专属斜率。没有专属项的 PRN 直接使用 default。专属项和默认项都拒绝未知字段。

```json
{
  "compensation": {
    "default": {"range_offset_m": 5.0},
    "per_prn": {
      "1": {"range_offset_m": 5.0, "range_rate_mps": 0.2},
      "8": {"mode": "independent_frequency", "frequency_offset_hz": 2.0}
    }
  }
}
```

参数可组合并不代表约束总能满足。例如距离正弦振幅过大或周期太短，会令其导数超出 ±20 Hz。负补偿也需要足够的正固定缓冲。范围校验是保守包络，不会为了通过校验自动裁剪参数。

## 8. 接收机与发射点时钟

前五个 CLOCK 字段同时适用于 `receiver_clock` 和 `relay.transmitters[k].clock`；表中接收机/发射点默认不同处分别说明。

| 字段 | 单位/类型 | 接收机默认 / 发射点默认 | 用途、建议与依赖 |
|---|---|---|---|
| `bias_s` | s | `1e-5` / `0` | 零时刻时钟偏差，正值进入观测为正的米单位钟差。 |
| `drift_sps` | s/s | `2e-8` / `0` | 线性时钟频率误差，正值使钟差增长；接收机默认对应约 6 m/s 的共同路径变化，速度解应同时估计钟漂。 |
| `drift_rate_sps2` | s/s² | `0` / `0` | 钟漂随时间的线性变化率，钟差中为 `0.5*a*t²`。 |
| `sinusoid_amplitude_s` | s | `0` / `0` | 时钟正弦偏差振幅；用于受控扰动，不代表实测晶振谱。 |
| `sinusoid_period_s` | s | `20.0` / `20.0` | 时钟正弦周期，须大于零。 |
| `receiver_clock.frequency_gm_sigma_sps` | s/s | `0.0` | 接收机随机频率误差稳态标准差，非负。零表示关闭；频率过程积分为钟差，不是每历元独立时钟跳变。 |
| `receiver_clock.frequency_gm_tau_s` | s | `10.0` | 随机频率 Gauss–Markov 相关时间，须为正。 |
| `receiver_clock.clock_grid_s` | s | `0.001` | 生成和积分随机钟漂的固定网格，须为正；更小提高时域分辨率并增加计算量。 |

## 9. 大气

| 完整参数名 | 单位/类型 | 默认值 | 用途、建议与依赖 |
|---|---|---|---|
| `atmosphere.enabled` | bool | `true` | 开启简化对流层和固定 TEC 单层电离层。无误差基线可关闭。 |
| `atmosphere.pressure_hpa` | hPa | `1013.25` | 对流层输入气压，须为正；应使用与天线高度和实验天气对应的数值。 |
| `atmosphere.temperature_k` | K | `293.15` | 绝对温度，当前校验范围 `(150,350)`；20°C 为 293.15 K。 |
| `atmosphere.relative_humidity` | 比例 | `0.5` | 相对湿度，范围 `[0,1]`，不是 0–100。 |
| `atmosphere.vertical_tec_tecu` | TECU | `10.0` | 固定垂直电子含量，非负，1 TECU=`1e16` electrons/m²；不是实测时空电离层模型。 |
| `atmosphere.iono_shell_height_m` | m | `350000.0` | 单层电离层壳高，须为正。 |
| `atmosphere.min_mapping_elevation_deg` | ° | `3.0` | 大气映射的仰角下限；建议严格大于零，避免 secant 映射发散。它与卫星可见性门限是不同参数。 |

## 10. 多径

| 完整参数名 | 单位/类型 | 默认值 | 用途、建议与依赖 |
|---|---|---|---|
| `multipath.enabled` | bool | `false` | 在转发 I/Q 的传播路径矩阵中加入单次镜面反射；不会给 LOS 观测表自动加入多径偏差。 |
| `multipath.walls` | 字符串列表 | 六个表面 | 从 `east,west,north,south,floor,ceiling` 选择；不包含家具/隔墙。 |
| `multipath.reflection_amplitude` | 电压比例 | `0.35` | 相对该反射路径距离增益的附加反射幅度，范围 `[0,1]`；功率比例是其平方。 |
| `multipath.reflection_phase_rad` | rad | `pi` | 常量反射相位，默认 180°；未按材料、入射角或极化推导。 |

## 11. 观测误差与有效性

| 完整参数名 | 单位/类型 | 默认值 | 用途、建议与依赖 |
|---|---|---|---|
| `observations.add_noise` | bool | `true` | 是否将统计估计误差加到观测表；不控制 I/Q AWGN。 |
| `observations.reference_cn0_dbhz` | dB-Hz | `45.0` | 路径损耗参考距离上的 C/N0，同时用于 I/Q 信号振幅归一化。 |
| `observations.reference_cn0_for_noise_dbhz` | dB-Hz | `45.0` | 代码/多普勒标准差对应的标定 C/N0，实际标准差乘 `10^((reference-current)/20)`。 |
| `observations.code_sigma_m` | m | `0.6` | 标定 C/N0 下代码伪距噪声标准差，须非负；不是最终位置误差。 |
| `observations.doppler_sigma_hz` | Hz | `0.3` | 标定 C/N0 下多普勒估计噪声标准差，须非负；不是最终速度误差。 |
| `observations.code_noise_correlation_s` | s | `0.1` | 代码误差的指数相关时间；零为白噪声，正值用于相关估计误差模型。 |
| `observations.doppler_noise_correlation_s` | s | `0.1` | 多普勒误差相关时间；与代码独立可设。 |
| `observations.noise_code_doppler_correlation` | 相关系数 | `0.0` | 代码/多普勒标准化创新项的相关，范围 `[-1,1]`；相关时间不同则不等于输出稳态相关系数。 |
| `observations.minimum_cn0_dbhz` | dB-Hz | `20.0` | 启用 C/N0 门限时，有效观测至少达到的值。 |
| `observations.dropout_probability` | 概率 | `0.0` | 每行 LOS 观测独立随机丢失概率，范围 `[0,1]`。失效由 valid 标志表示，数据行仍保存。 |
| `observations.apply_cn0_gate` | bool | `false` | 是否用 minimum_cn0_dbhz 限制 LOS 有效性；不是实际接收机捕获检测器。 |

## 12. 参考最小二乘接收机

| 完整参数名 | 单位/类型 | 默认值 | 用途、建议与依赖 |
|---|---|---|---|
| `solver.enabled` | bool | `true` | 是否生成参考接收机解和统计结果。接收机使用真实卫星模型，不读取虚拟卫星位置解算。 |
| `solver.initial_enu_m` | `[m,m,m]` | `[15,5,1]` | 首历元位置初值。后续使用上次内部估计；不是从每历元真值初始化。 |
| `solver.max_iterations` | 正整数 | `30` | 每历元位置/钟差最小二乘最大迭代数；过小可能未收敛。 |
| `solver.position_tolerance_m` | m | `1e-5` | 迭代位置更新和钟差更新的停止阈值；它是数值收敛容差，不是物理精度保证。 |
| `solver.max_step_m` | m | `500.0` | 每次位置更新向量的最大步长，建议为正；仅裁剪位置更新，不裁剪钟差更新。 |
| `solver.known_height_m` | m 或 null | `null` | null 解三维位置+钟差；数值则固定 ENU z，仅解 x、y 及水平速度。数值须在 `[0, room_z]` 内，0 有效。二维结果不输出估计 z/vz，主误差统计只使用 x、y；物理传播仍计入高度差。固定高度是外部假设，错误高度可能导致水平偏差。 |
| `solver.apply_atmosphere` | bool | `true` | 在接收机真实卫星直达预期模型中应用同一简化大气模型。实际传播也关闭大气时此项不产生改正。 |
| `solver.position_normalization_m` | m | `30.0` | 当前解算维度下位置平均欧氏误差的归一化分母，须为正。默认以厂房长度为基准是项目暂定约定。 |
| `solver.velocity_normalization_mps` | m/s | `22.2222222222` | 当前解算维度下速度向量误差均值/RMS 的归一化分母，须为正；停留段仍使用这个固定分母，非逐时真实速度。 |

### 二维/三维按钮与命令行覆盖

双击项目根目录 `Start-Simulator.cmd`。界面默认不勾选“计算 Z 方向（三维定位）”，使用二维解算；固定高度优先预填所选配置的 `solver.known_height_m`，否则取 `solver.initial_enu_m[2]`，配置省略时为 1 m。该值不会读取真实轨迹。勾选后覆盖为三维，停用固定高度输入。

- `run.ps1 -PositionMode 2D -HeightM 1` 或 `simulate.py --position-mode 2d --height-m 1`：二维定位，固定 ENU 高度 1 m。
- `run.ps1 -PositionMode 3D` 或 `simulate.py --position-mode 3d`：三维定位，覆盖配置中的固定高度。
- 命令行只指定二维、不提供高度时，优先保留配置的固定高度；若为 null，使用初始位置的 z。高度参数不能与显式三维模式同时使用。
- 不传新命令行选项时，沿用原配置；`configs/default.json` 仍为三维，`configs/xy_only.json` 为二维。这使旧的运行命令保持原有解算维度。
- 每次的有效高度写入 `config.resolved.json`，维度和高度写入 `run_summary.json`、`metrics.json` 及结果 CSV，可复核当次设置。

## 13. I/Q 生成

| 完整参数名 | 单位/类型 | 默认值 | 用途、建议与依赖 |
|---|---|---|---|
| `iq.enabled` | bool | `true` | 是否写 I/Q 文件；可用命令行 --no-iq 关闭。 |
| `iq.start_s` | s | `0.25` | I/Q 窗口在仿真接收机时间轴上的起点，非负；默认位于出发后的动态段。 |
| `iq.duration_s` | s | `0.05` | I/Q 时长，须为正，整个窗口须在总仿真内。默认短片段用于验证，不够支撑完整冷启动。 |
| `iq.sample_rate_hz` | complex sample/s | `4092000.0` | 每秒复采样数，不是 I 与 Q 标量合计数；至少 2.046 MS/s，且 IF+C/A 主瓣须容于 Nyquist。增大后磁盘/计算开销线性增加。 |
| `iq.intermediate_frequency_hz` | Hz | `0.0` | 数字中频，零为中心化复基带；信号相位加 `+2*pi*IF*t`。 |
| `iq.format` | 枚举 | `"ci16_le"` | ci16_le：I/Q 各 int16，共 4 bytes/sample；cf32_le：I/Q 各 float32，共 8 bytes/sample。均 little-endian。 |
| `iq.chunk_samples` | 正整数 | `65536` | 每块复采样数，控制内存；不改变整段归一化、时间原点和随机序列。 |
| `iq.output_name` | 文件名 | `"signal.iq"` | 输出基本文件名，不能包含目录路径；实际目录取 --output。 |
| `iq.adc_full_scale_sigma` | 无量纲 | `6.0` | int16 满量程相对整段估计单分量标准差的倍数，须为正；大值降低削顶但降低量化利用率。cf32 不量化。 |
| `iq.navigation_bits_file` | 路径或 null | `null` | 外部每 PRN 50 bit/s 0/1 符号；null 为恒 +1、tracking_only。外部文件格式见 DATA_FORMAT；不验证 LNAV parity/TOW/星历一致性。 |
| `iq.add_noise` | bool | `true` | 是否在复采样上加入 AWGN；独立于 observations.add_noise。 |
| `iq.max_output_bytes` | byte | `2000000000` | 单个 I/Q 文件预计字节上限；不包括 CSV/NPZ/JSON。大实验前还需检查磁盘空间。 |

## 14. 参数选择建议

先使用零噪声直达配置核对几何和符号，再开启转发、时钟、大气和噪声，每次只改变可解释的一组因素。补偿效果应与无补偿基线比较。参数来自真实设备时，记录厂家规格/校准来源；探索性参数应标注为假设。

I/Q 波形目前采用矩形码片和参数插值，不应把采样率高理解为整个仿真具有同等精度。应同时检查传播网格、差分步长、导航电文和模拟接收机处理结果。

## 资源与键名保护

映射和逐星补偿键严格使用字符串 `1`～`32`；带前导零或 G 前缀的键会报错，显式 PRN 列表须为整数。I/Q 文件名不得与运行摘要等固定产物重名。单次运行限制估计历元不超过200000、时钟过程网格不超过2000000点；更长实验应分段。磁盘预估包括时间网格、等距离轨迹点与反射通道。


---

# English translation: Configuration parameter reference

The application's former “Compensation” page has been replaced with an optional “Upload / Import data” page. `input_observations.corrected_csv` (default null) and `input_observations.compare_reference` (default false) were added. The former imports complete corrected pseudorange and Doppler; the latter optionally compares the simulated reference trajectory from the same configuration. The application no longer applies built-in compensation when generating data. Compensation function parameters below are only for reproducing historical command-line experiments. See [Corrected observation import](OBSERVATION_IMPORT.md) for the format and outputs.

Parameters follow `DEFAULT` in `src/indoor_gnss/config.py`. Table recommendations guide experimental design; not every recommendation is automatically enforced. For formulas and omitted effects see [PHYSICS.md](PHYSICS.md). Defaults are a runnable demonstration, not identified parameters of actual equipment or an optimal design.

## 1. Configuration file rules

JSON may specify only ordinary object fields that need changes; omitted fields retain program defaults. Names are case-sensitive. Unknown keys cause errors so spelling mistakes do not silently fall back to defaults. Values use SI units; angles with `_deg` are degrees and those with `_rad` are radians.

- `relay.transmitters` is a completely replaced list, not merged item by item with defaults. Every transmitter must include all fields in the table, including a complete `clock` object. Copy and edit a default item.
- `relay.mapping` maps PRN strings to transmitter IDs, e.g. `{"1":"V1","8":"V2"}`. The dictionary is replaced as a whole; selected PRNs omitted from it are assigned cyclically over the transmitter list. Use keys such as `"1"`, not `"G01"`.
- `compensation.per_prn` is a compensation object per PRN string; each object may specify only some compensation fields. Section 7 explains how missing values are filled.
- Relative paths for `satellites.rinex_nav_file` and `iq.navigation_bits_file` are resolved against the JSON configuration directory and saved as absolute paths after loading. The command-line `--output` specifies the output path.
- Non-finite JSON values such as `NaN` and `Infinity` are not permitted. `null` applies only to documented nullable fields.
- The generator refuses to overwrite an existing output directory. Use a new experiment directory after each parameter change, preserving earlier configurations and results.

Minimal override example:

```json
{
  "seed": 20261106,
  "observations": {"add_noise": false},
  "iq": {"enabled": false}
}
```

## 2. Global, time, and coordinate parameters

| Full parameter name | Unit/type | Default | Purpose, recommendations, and dependencies |
|---|---|---|---|
| `seed` | nonnegative integer | `20261105` | Main random seed. Clock, observation noise and I/Q AWGN use independent substreams. Keep the seed fixed to control random conditions in comparisons; vary it across trials. |
| `time.gps_week` | full GPS week, integer | `2443` | Initial GPST week; must match RINEX/external NAV bit time, not a truncated 10-bit week. |
| `time.gps_sow` | s | `345600.0` | Initial GPS seconds of week, `[0,604800)`; no automatic UTC/leap-second conversion. |
| `time.duration_s` | s | `2.0` | Total duration, positive and covering all motion and the I/Q window. A longer duration increases observation count, computation and optional I/Q file size. |
| `time.observation_interval_s` | s | `0.01` | Regular propagation/observation grid; I/Q path parameters are linearly interpolated on it. Reduce and check convergence for fast motion or changing multipath. Suggested starting range `0.001–0.02`. |
| `time.trajectory_distance_step_m` | m | `1.0` | Inserts samples at equal intervals along the cumulative path length. The step must be positive. These samples and intermediate waypoints merge with the time grid, so observation intervals can be uneven. |
| `time.derivative_step_s` | s | `0.002` | Half-step for central differences of carrier path and clock bias, `(0,0.1)`. Too small invites floating-point cancellation; too large may cross motion segments. Compare `0.001/0.002/0.005` for stability. |
| `site.latitude_deg` | ° | `31.2304` | WGS84 origin latitude, valid `[-90,90]`; used for local rotation and atmosphere. Replace with the factory location for real scenes. |
| `site.longitude_deg` | ° | `121.4737` | WGS84 origin longitude; recommended `[-180,180]`. |
| `site.height_m` | m | `10.0` | WGS84 origin ellipsoidal height, not automatically converted altitude above sea level. |
| `site.room_size_enu_m` | `[m,m,m]` | `[30,10,5]` | Room dimensions east, north and up; all positive. Trajectory and transmitters must be inside or on the boundary. |
| `site.outdoor_antenna_enu_m` | `[m,m,m]` | `[15,5,8]` | Local ENU position of outdoor receiving antenna A; may be above the room. It receives the relay sky path; direct mode does not use it as the signal endpoint. |

## 3. User trajectory

| Full parameter name | Unit/type | Default | Purpose, recommendations, and dependencies |
|---|---|---|---|
| `trajectory.start_enu_m` | `[m,m,m]` | `[0,5,1]` | Path start, inside the room. |
| `trajectory.waypoints_enu_m` | `[[m,m,m],…]` | `[]` | Optional intermediate waypoints in visit order. All points must be inside the room and adjacent points must differ. An empty list gives a straight path. |
| `trajectory.end_enu_m` | `[m,m,m]` | `[30,5,1]` | Path end inside the room. With valid intermediate waypoints, the end may equal the start. |
| `trajectory.start_time_s` | s | `0.2` | Departure in physical time; stationary at the start beforehand. When changing it check that the I/Q window covers the dynamic segment. |
| `trajectory.speed_mps` | m/s | `22.2222222222` | Positive cruise speed, 80 km/h; 70 km/h is about `19.4444444444`. It is not supplied to the receiver as known velocity. |
| `trajectory.acceleration_time_s` | s | `0.0` | Each startup and stopping ramp duration. Zero means instantaneous start/stop; positive values use constant acceleration. Must be nonnegative and `acceleration_time_s * speed_mps <= path length`. Path length is the sum of the segment lengths. All motion must fit in the total duration. |

## 4. Satellites and ephemerides

| Full parameter name | Unit/type | Default | Purpose, recommendations, and dependencies |
|---|---|---|---|
| `satellites.source` | enum | `"synthetic"` | `synthetic` is a demonstration set of circular orbits, not a real sky on a date; `rinex` uses RINEX 2/3 GPS broadcast ephemeris. |
| `satellites.rinex_nav_file` | path or null | `null` | Required for `source=rinex`; supports GPS/mixed RINEX 2/3 NAV and `.gz`, not observation files or RINEX 4. |
| `satellites.max_ephemeris_age_s` | s | `14400.0` | Positive maximum RINEX ephemeris age; record fit interval also applies. Set from validity documentation; do not enlarge it merely to force reuse of expired ephemerides. |
| `satellites.allow_unhealthy` | bool | `false` | Whether RINEX GPS records with nonzero health flags are allowed. Usually false; explicitly label experiments that enable it. |
| `satellites.count` | integer | `8` | Number of satellites chosen by descending initial elevation when no PRNs are explicit, 1–32. Insufficient visible satellites cause an error. Three-dimensional solving normally also requires enough independent observations. |
| `satellites.prns` | integer list | `[]` | Empty selects automatically; otherwise explicit PRNs override `count`. No duplicates; all must be healthy and visible initially. I/Q supports only PRNs 1–32. |
| `satellites.elevation_mask_deg` | ° | `5.0` | Initial selection and per-epoch visibility threshold. Start with `5–15`; lowering it brings in lower elevations and stronger atmospheric mapping. |
| `satellites.synthetic_count` | integer | `32` | Number of candidate synthetic satellites, 1–32; synthetic only. |
| `satellites.synthetic_planes` | integer | `8` | Synthetic orbit planes from 1 through synthetic_count; synthetic only, not the real GPS layout. |
| `satellites.synthetic_radius_m` | m | `26560000.0` | Geocentric radius of synthetic circular orbits, not altitude; must exceed the WGS84 equatorial radius. |
| `satellites.synthetic_inclination_deg` | ° | `55.0` | Synthetic circular-orbit inclination, 0–180. |
| `satellites.synthetic_raan_offset_deg` | ° | `0.0` | Common initial right-ascension-of-ascending-node offset, for changing the demonstration sky geometry. |
| `satellites.epoch_gps_week` | GPS week | `2443` | Synthetic orbit reference week; with the next field defines initial orbit phase and linear satellite-clock reference. |
| `satellites.epoch_gps_sow` | s | `345600.0` | Reference GPS seconds of week; synthetic only. |
| `satellites.synthetic_clock_bias_s` | s | `0.0` | Common synthetic satellite initial clock bias, not an independent clock configuration per PRN. |
| `satellites.synthetic_clock_drift_sps` | s/s | `0.0` | Common linear clock drift; `1e-12–1e-10` can be a starting range for small tests. Determine actual values from target hardware or documentation. |
| `satellites.synthetic_tgd_s` | s | `0.0` | Synthetic GPS L1 TGD, represented by `+c*TGD` in the code path and not added to the carrier. |

## 5. Propagation and transmitters

| Full parameter name | Unit/type | Default | Purpose, recommendations, and dependencies |
|---|---|---|---|
| `propagation.mode` | enum | `"relay"` | `relay` is outdoor reception/indoor retransmission; `direct` is a real-satellite direct-path baseline and requires zero compensation. |
| `propagation.earth_rotation` | bool | `true` | Correct Earth rotation during sky-path flight. Usually true; disable only for ablation. |
| `propagation.light_time_tolerance_s` | s | `1e-12` | Sky geometric flight-time iteration convergence threshold; at most 8 iterations. Small positive values like `1e-10–1e-12` can be used, but do not imply equal accuracy of other models. |
| `propagation.min_path_m` | m | `0.05` | Minimum user-to-LOS/reflected-image-source path; shorter paths are rejected to avoid a point-source loss singularity. Not an exact antenna near-field boundary. |
| `relay.architecture` | enum | `"transparent"` | `transparent` requires zero independent transmitter clock errors; `regenerative` allows specified errors but remains an equivalent model. |
| `relay.mapping` | dictionary | `{}` | Static PRN-string-to-transmitter-ID mapping; omitted selected PRNs are assigned cyclically. |
| `relay.transmitters` | object list | two transmitters | Configure 1–4 transmitters, completely replacing the default list. Per-transmitter fields follow. |
| `relay.min_spacing_m` | m | `8.0` | Exclusive minimum spacing: `distance > min_spacing_m`. |
| `relay.max_spacing_m` | m | `30.0` | Exclusive maximum spacing: `distance < max_spacing_m`; no pairwise constraint with one transmitter. |

Complete fields of each `relay.transmitters[k]` follow; differing V1/V2 values are separated by a slash:

| Field | Unit/type | Default V1 / V2 | Purpose, recommendations, and dependencies |
|---|---|---|---|
| `id` | string | `V1` / `V2` | Unique transmitter ID referenced by mapping. |
| `position_enu_m` | `[m,m,m]` | `[2,2,5]` / `[28,8,5]` | Indoor position within or on the room boundary and satisfying spacing constraints. |
| `cable_length_m` | m | `20.0` | Nonnegative physical cable length; equivalent path is length divided by velocity factor. |
| `cable_velocity_factor` | dimensionless | `0.66` | Cable signal speed divided by light speed, `(0,1]`; set from the cable specification. Group and phase delays are assumed equal. |
| `processing_delay_s` | s | `0.001` | Nonnegative fixed processing/buffering delay; 1 ms corresponds to about 300 km. Much common delay may be absorbed by receiver clock bias and must not be treated as indoor geometric distance. |
| `phase_offset_rad` | rad | `0.0` | Additional transmitter carrier phase offset; phase only, no code-delay change. |
| `reference_distance_m` | m | `10.0` | Positive path-loss calibration distance; reference C/N0 applies here without additional loss. |
| `path_loss_exponent` | dimensionless | `2.0` | Nonnegative power path-loss exponent; 2 is the free-space distance-exponent model. Indoor values require measurement and do not imply a complete link budget. |
| `excess_loss_db` | dB | `0.0` | Fixed additional attenuation; positive values reduce voltage gain. Start with a nonnegative value. |
| `clock` | object | zero-error CLOCK | Equivalent independent transmitter clock; complete fields in section 8. Transparent relay requires all error amplitudes to be zero. |

## 6. Compensation dictionary

| Full parameter name | Unit/type | Default | Purpose, recommendations, and dependencies |
|---|---|---|---|
| `compensation.default` | object | zero-compensation COMP | Compensation for PRNs without a dedicated entry; fields follow. |
| `compensation.per_prn` | dictionary | `{}` | Dedicated compensation by PRN string, e.g. `{"1":{"range_offset_m":2}}`; each entry may specify some fields. |
| `compensation.max_range_m` | m | `30.0` | Absolute range-compensation limit, validated by a conservative analytic envelope over the whole interval. |
| `compensation.max_doppler_hz` | Hz | `20.0` | Absolute total compensation-Doppler limit including range-compensation derivative and explicit frequency control; not a total sky-Doppler limit. |

The following fields apply to `compensation.default` and each `per_prn["PRN"]`:

| Field | Unit/type | Default | Purpose, recommendations, and dependencies |
|---|---|---|---|
| `mode` | enum | `"delay_coupled"` | `delay_coupled`: code and carrier share delay and its derivative determines Doppler. `independent_frequency`: independent carrier shift is also allowed, assuming the corresponding hardware ability. |
| `range_offset_m` | m | `0.0` | Initial constant path compensation; positive lengthens the path. |
| `range_rate_mps` | m/s | `0.0` | Linear range-compensation rate, also producing `-range_rate_mps/lambda` Hz. |
| `range_sine_m` | m | `0.0` | Sinusoidal range-compensation amplitude; shift amplitude depends on amplitude and period. |
| `range_period_s` | s | `5.0` | Positive sinusoidal range period; retain a valid value even for zero amplitude. |
| `frequency_offset_hz` | Hz | `0.0` | Extra constant carrier frequency shift; nonzero only in independent_frequency. Positive values increase carrier phase over time. |
| `frequency_rate_hzps` | Hz/s | `0.0` | Extra linear frequency ramp; nonzero only in independent_frequency. |
| `frequency_sine_hz` | Hz | `0.0` | Extra sinusoidal frequency amplitude; nonzero only in independent_frequency. |
| `frequency_period_s` | s | `5.0` | Extra sinusoidal frequency period; must be positive. |

## 7. Partial override and compensation constraints

For each `per_prn` entry the loader copies the already merged `compensation.default` and applies the entry's partial fields. For example, if default has constant 5 m and PRN1's entry specifies only `range_rate_mps`, PRN1 retains the 5 m constant and gains its dedicated slope. PRNs with no dedicated entry use default. Both dedicated and default objects reject unknown fields.

```json
{
  "compensation": {
    "default": {"range_offset_m": 5.0},
    "per_prn": {
      "1": {"range_offset_m": 5.0, "range_rate_mps": 0.2},
      "8": {"mode": "independent_frequency", "frequency_offset_hz": 2.0}
    }
  }
}
```

Combinable parameters do not guarantee constraints are met. Excessive sinusoidal range amplitude or too short a period can make the derivative exceed ±20 Hz. Negative compensation also needs sufficient positive fixed buffering. Range validation uses a conservative envelope and does not automatically clip values to pass.

## 8. Receiver and transmitter clocks

The first five CLOCK fields apply to both `receiver_clock` and `relay.transmitters[k].clock`; receiver/transmitter defaults are shown separately where different.

| Field | Unit/type | Receiver / transmitter default | Purpose, recommendations, and dependencies |
|---|---|---|---|
| `bias_s` | s | `1e-5` / `0` | Time-zero clock bias; positive bias enters observation as a positive clock error in meters. |
| `drift_sps` | s/s | `2e-8` / `0` | Linear clock frequency error; positive increases bias. Receiver default corresponds to about 6 m/s common path rate; velocity solution should jointly estimate clock drift. |
| `drift_rate_sps2` | s/s² | `0` / `0` | Linear change rate of clock drift; clock bias includes `0.5*a*t²`. |
| `sinusoid_amplitude_s` | s | `0` / `0` | Sinusoidal clock-bias amplitude for controlled perturbations, not a measured oscillator spectrum. |
| `sinusoid_period_s` | s | `20.0` / `20.0` | Positive sinusoidal clock period. |
| `receiver_clock.frequency_gm_sigma_sps` | s/s | `0.0` | Nonnegative steady-state standard deviation of receiver random frequency error. Zero disables it; frequency is integrated into clock bias rather than independently jumping each epoch. |
| `receiver_clock.frequency_gm_tau_s` | s | `10.0` | Positive Gauss–Markov random-frequency correlation time. |
| `receiver_clock.clock_grid_s` | s | `0.001` | Positive fixed grid for generating and integrating random drift; smaller improves temporal resolution and increases computation. |

## 9. Atmosphere

| Full parameter name | Unit/type | Default | Purpose, recommendations, and dependencies |
|---|---|---|---|
| `atmosphere.enabled` | bool | `true` | Enable simplified troposphere and fixed-TEC single-layer ionosphere; can be disabled for an error-free baseline. |
| `atmosphere.pressure_hpa` | hPa | `1013.25` | Positive troposphere input pressure; match antenna height and experimental weather. |
| `atmosphere.temperature_k` | K | `293.15` | Absolute temperature, currently validated in `(150,350)`; 20°C is 293.15 K. |
| `atmosphere.relative_humidity` | fraction | `0.5` | Relative humidity in `[0,1]`, not 0–100. |
| `atmosphere.vertical_tec_tecu` | TECU | `10.0` | Nonnegative fixed vertical electron content; 1 TECU=`1e16` electrons/m². Not a measured spatiotemporal ionosphere. |
| `atmosphere.iono_shell_height_m` | m | `350000.0` | Positive single-layer ionosphere shell height. |
| `atmosphere.min_mapping_elevation_deg` | ° | `3.0` | Atmospheric mapping elevation floor; recommend strictly positive to avoid divergent secant mapping. Different from the satellite visibility threshold. |

## 10. Multipath

| Full parameter name | Unit/type | Default | Purpose, recommendations, and dependencies |
|---|---|---|---|
| `multipath.enabled` | bool | `false` | Add single specular reflections to the relay I/Q propagation-path matrix; no multipath bias is automatically added to the LOS observation table. |
| `multipath.walls` | string list | six surfaces | Select from `east,west,north,south,floor,ceiling`; furniture and partitions are excluded. |
| `multipath.reflection_amplitude` | voltage ratio | `0.35` | Additional reflection amplitude relative to the path distance gain, `[0,1]`; the power ratio is its square. |
| `multipath.reflection_phase_rad` | rad | `pi` | Constant reflection phase, default 180°; not derived from material, incidence angle or polarization. |

## 11. Observation errors and validity

| Full parameter name | Unit/type | Default | Purpose, recommendations, and dependencies |
|---|---|---|---|
| `observations.add_noise` | bool | `true` | Add statistical estimation errors to the observation table; does not control I/Q AWGN. |
| `observations.reference_cn0_dbhz` | dB-Hz | `45.0` | C/N0 at the path-loss reference distance, also used for I/Q signal-amplitude normalization. |
| `observations.reference_cn0_for_noise_dbhz` | dB-Hz | `45.0` | Calibration C/N0 for code/Doppler standard deviations; actual standard deviations are multiplied by `10^((reference-current)/20)`. |
| `observations.code_sigma_m` | m | `0.6` | Nonnegative code pseudorange noise standard deviation at calibration C/N0; not final position error. |
| `observations.doppler_sigma_hz` | Hz | `0.3` | Nonnegative Doppler estimation noise standard deviation at calibration C/N0; not final velocity error. |
| `observations.code_noise_correlation_s` | s | `0.1` | Exponential code-error correlation time; zero gives white noise, positive values correlated estimation error. |
| `observations.doppler_noise_correlation_s` | s | `0.1` | Doppler error correlation time, independently configurable from code. |
| `observations.noise_code_doppler_correlation` | correlation coefficient | `0.0` | Correlation of standardized code/Doppler innovations in `[-1,1]`; with different correlation times it is not the steady-state output correlation. |
| `observations.minimum_cn0_dbhz` | dB-Hz | `20.0` | Minimum C/N0 for a valid observation when the gate is enabled. |
| `observations.dropout_probability` | probability | `0.0` | Independent random dropout probability per LOS observation, `[0,1]`; `valid` marks failure and rows are retained. |
| `observations.apply_cn0_gate` | bool | `false` | Apply minimum_cn0_dbhz to LOS validity; not an actual receiver acquisition detector. |

## 12. Reference least-squares receiver

| Full parameter name | Unit/type | Default | Purpose, recommendations, and dependencies |
|---|---|---|---|
| `solver.enabled` | bool | `true` | Generate reference receiver solutions and statistics. The receiver uses the real-satellite model, not virtual-satellite positions, for solving. |
| `solver.initial_enu_m` | `[m,m,m]` | `[15,5,1]` | First-epoch initial position. Later epochs reuse the prior internal estimate, not each epoch's truth. |
| `solver.max_iterations` | positive integer | `30` | Maximum position/clock least-squares iterations per epoch; too few may prevent convergence. |
| `solver.position_tolerance_m` | m | `1e-5` | Stopping threshold for position and clock-bias updates, a numerical convergence tolerance rather than a physical accuracy guarantee. |
| `solver.max_step_m` | m | `500.0` | Maximum position-update vector step; recommended positive. Only position updates, not clock-bias updates, are clipped. |
| `solver.known_height_m` | m or null | `null` | null solves 3D position plus clock bias; a value fixes ENU z and solves only x, y and horizontal velocity. Must be in `[0, room_z]`; zero is valid. 2D output omits estimated z/vz and primary error statistics use x/y only; propagation still includes height differences. Fixed height is an external assumption and an incorrect height may cause horizontal bias. |
| `solver.apply_atmosphere` | bool | `true` | Apply the same simplified atmosphere to the receiver's expected real-satellite direct-path model. No correction is produced if atmosphere is also disabled in propagation. |
| `solver.position_normalization_m` | m | `30.0` | Positive denominator for mean Euclidean position error in the solved dimensions. Factory length as default is a provisional project convention. |
| `solver.velocity_normalization_mps` | m/s | `22.2222222222` | Positive denominator for mean/RMS velocity-vector error in the solved dimensions; fixed even during stationary segments, not the true speed at each time. |

### 2D/3D button and command-line overrides

Double-click `Start-Simulator.cmd` in the project root. The interface defaults to leaving “Solve Z (3D positioning)” unchecked and uses 2D. Fixed height is initially taken from the selected configuration's `solver.known_height_m`, otherwise `solver.initial_enu_m[2]`; it is 1 m when omitted from configuration. This does not read the true trajectory. Checking it overrides to 3D and disables fixed-height input.

- `run.ps1 -PositionMode 2D -HeightM 1` or `simulate.py --position-mode 2d --height-m 1`: 2D positioning with ENU height fixed at 1 m.
- `run.ps1 -PositionMode 3D` or `simulate.py --position-mode 3d`: 3D positioning overriding a fixed height in configuration.
- If 2D is specified without a height, retain configured fixed height when available; if null, use initial-position z. A height parameter cannot be combined with explicit 3D mode.
- Without new CLI options the original configuration is used: `configs/default.json` remains 3D, `configs/xy_only.json` 2D. This preserves dimensions of older run commands.
- Effective height is written to `config.resolved.json`; dimension and height are written to `run_summary.json`, `metrics.json` and result CSV for review.

## 13. I/Q generation

| Full parameter name | Unit/type | Default | Purpose, recommendations, and dependencies |
|---|---|---|---|
| `iq.enabled` | bool | `true` | Write I/Q output; command-line --no-iq can disable it. |
| `iq.start_s` | s | `0.25` | Nonnegative I/Q-window start on the simulation receiver-time axis; default lies in motion after departure. |
| `iq.duration_s` | s | `0.05` | Positive I/Q duration; the whole window must fit in the simulation. The default short validation segment is insufficient for a full cold start. |
| `iq.sample_rate_hz` | complex sample/s | `4092000.0` | Complex samples per second, not total I and Q scalar samples; at least 2.046 MS/s and IF plus the C/A main lobe must fit Nyquist. Disk/computing costs rise linearly. |
| `iq.intermediate_frequency_hz` | Hz | `0.0` | Digital intermediate frequency; zero is centered complex baseband. Signal phase adds `+2*pi*IF*t`. |
| `iq.format` | enum | `"ci16_le"` | ci16_le: int16 I and Q, 4 bytes/sample; cf32_le: float32 I and Q, 8 bytes/sample. Both little-endian. |
| `iq.chunk_samples` | positive integer | `65536` | Complex samples per chunk control memory without changing whole-segment normalization, time origin or random sequence. |
| `iq.output_name` | filename | `"signal.iq"` | Output base filename without directory path; actual directory is --output. |
| `iq.adc_full_scale_sigma` | dimensionless | `6.0` | Positive int16 full-scale multiple of whole-segment estimated single-component standard deviation. Higher values reduce clipping but lower quantization utilization; cf32 is not quantized. |
| `iq.navigation_bits_file` | path or null | `null` | External per-PRN 50 bit/s 0/1 symbols; null gives constant +1, tracking_only. See DATA_FORMAT for file format; LNAV parity/TOW/ephemeris consistency are not validated. |
| `iq.add_noise` | bool | `true` | Add AWGN to complex samples, independent of observations.add_noise. |
| `iq.max_output_bytes` | byte | `2000000000` | Expected byte limit for a single I/Q file, excluding CSV/NPZ/JSON. Check disk space before large experiments. |

## 14. Parameter selection recommendations

First use a zero-noise direct configuration to verify geometry and signs, then enable relay, clock, atmosphere and noise while changing one interpretable group of factors at a time. Compare compensation against an uncompensated baseline. For parameters from real equipment record manufacturer specifications/calibration sources; mark exploratory values as assumptions.

I/Q currently uses rectangular chips and parameter interpolation; a high sampling rate does not imply the entire simulation has equivalent accuracy. Also check the propagation grid, difference step, navigation message and simulated receiver processing results.

## Resource and key-name protection

Mapping and per-PRN compensation keys must be strings `1`–`32`; keys with leading zeros or G prefixes cause errors, and an explicit PRN list must contain integers. I/Q filenames must not collide with fixed products such as the run summary. A run is limited to at most 200000 estimated epochs and 2000000 clock-process grid points; divide longer experiments into segments. Disk estimates include the time grid, equal-distance trajectory points and reflected channels.
