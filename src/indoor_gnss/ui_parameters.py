"""Chinese labels, units and help for simulator inputs; no model calculations."""
import re


TAB_SECTIONS = [
    ('场景与轨迹', ['seed', 'time', 'site', 'trajectory']),
    ('卫星与传播', ['satellites', 'propagation']),
    ('室内发射点', ['relay']),
    ('上传 / 导入数据', ['input_observations']),
    ('时钟与大气', ['receiver_clock', 'atmosphere']),
    ('噪声与多径', ['observations', 'multipath']),
    ('定位解算', ['solver']),
    ('I/Q 信号', ['iq']),
]


# Keys refer to the public configuration schema. Numeric transmitter indices
# are replaced by '*'; all other keys stay identical to saved JSON.
_FIELDS = {
    'input_observations.corrected_csv': ('已补偿观测 CSV（可留空）',
        '选择本地已补偿伪距、多普勒文件。至少含 time_s、prn、pseudorange_m、doppler_hz；填写完整观测值，不是补偿量。留空时生成未补偿观测。导入模式仅计算位置速度，不生成 I/Q。'),
    'input_observations.compare_reference': ('与配置中的仿真轨迹对比',
        '默认关闭，仅输出位置和速度。只有文件来自同一仿真场景时才开启；开启后误差相对当前配置轨迹，不代表外部数据真实地面真值。'),
    'seed': ('随机种子', '非负整数。相同种子和参数可重复生成同一组随机误差；对照实验建议保持不变。'),
    'time.gps_week': ('起始 GPS 周', '完整 GPS 周数，采用 GPST；须与广播星历及外部导航符号的时间对应。'),
    'time.gps_sow': ('起始 GPS 周内秒（s）', '范围 0 ≤ 值 < 604800。这里使用 GPST，不自动把 UTC 日期或闰秒转换为 GPS 时间。'),
    'time.duration_s': ('总仿真时长（s）', '必须大于零，并覆盖整个运动过程与 I/Q 生成窗口。时长越长，计算量和数据量通常越大。'),
    'time.observation_interval_s': ('观测时间间隔（s）', '常规传播与观测网格，须大于零。建议先用 0.001～0.02 s；I/Q 路径参数在此网格间插值。'),
    'time.trajectory_distance_step_m': ('轨迹距离采样间隔（m）', '除时间网格外，还会按此距离插入轨迹点。须大于零，合并后的时刻未必等间隔。'),
    'time.derivative_step_s': ('多普勒差分半步长（s）', '载波路径中心差分的半步长，范围 0 < 值 < 0.1。过大可能跨越起停边界，过小可能增大浮点误差。'),
    'site.latitude_deg': ('场地原点纬度（°）', 'WGS84 纬度，物理有效范围为 -90～90°；用于 ENU 坐标及大气模型。'),
    'site.longitude_deg': ('场地原点经度（°）', 'WGS84 经度，通常用 -180～180°。真实场景应填写厂房位置。'),
    'site.height_m': ('场地原点椭球高（m）', 'WGS84 椭球高，不是自动换算后的海拔。室内 z 坐标相对此原点。'),
    'site.room_size_enu_m': ('房间尺寸 [东、北、高]（m）', '填写三个正数，如 [30, 10, 5]。轨迹和室内发射点必须在该范围内或边界上。'),
    'site.outdoor_antenna_enu_m': ('室外接收天线 [x、y、z]（m）', '室外接收天线在局部 ENU 中的位置，如 [15, 5, 8]；允许高于房间顶部。转发天空段以此点为终点。'),
    'trajectory.start_enu_m': ('运动起点 [x、y、z]（m）', '路径起点，须位于房间内。坐标依次向东、向北、向上。'),
    'trajectory.waypoints_enu_m': ('中间路径点（m）', '按经过顺序填写房间内的 [x, y, z]，如 [[10, 5, 1], [10, 8, 1]]。相邻点须不同。填 [] 直接连接起点和终点。'),
    'trajectory.end_enu_m': ('运动终点 [x、y、z]（m）', '路径终点，须位于房间内。设置中间路径点后可回到起点。'),
    'trajectory.start_time_s': ('开始运动时间（s）', '物理时间上的出发时刻，出发前静止在起点；应保证整个运动在总仿真时长内。'),
    'trajectory.speed_mps': ('运动巡航速度（m/s）', '须大于零。80 km/h ≈ 22.2222 m/s；70 km/h ≈ 19.4444 m/s。此参数只定义真值，不作为接收机已知速度。'),
    'trajectory.acceleration_time_s': ('起步及制动时长（s）', '整条路径的起步加速和终点制动各使用该时长。0 表示瞬时启停；正值须满足“速度 × 该时长 ≤ 路径总长度”。'),
    'satellites.source': ('卫星轨道来源', 'synthetic：合成圆轨道演示星座；rinex：本地 GPS RINEX 2/3 广播星历。合成轨道不是当日真实星座。'),
    'satellites.rinex_nav_file': ('RINEX 广播星历文件', '仅 rinex 来源必填。支持 GPS 或混合 RINEX 2/3 NAV 及 .gz；不支持 RINEX 4 或观测文件。留空表示不提供文件。'),
    'satellites.max_ephemeris_age_s': ('最大星历年龄（s）', '须大于零，还受广播记录有效期限制。不要单纯扩大此值来复用过期星历。'),
    'satellites.allow_unhealthy': ('允许非健康卫星星历', '一般关闭。开启后允许读取健康标志非零的 GPS 广播记录，仅建议用于明确标注的研究实验。'),
    'satellites.count': ('自动选取卫星数', '整数 1～32。仅未指定 PRN 列表时使用；程序按起始仰角由高到低选择，可见星不足会报错。'),
    'satellites.prns': ('指定卫星 PRN 列表', '整数列表，如 [3, 16, 4, 10]；空列表 [] 表示自动选择。PRN 须在 1～32 内、互不重复，并在开始时健康可见。'),
    'satellites.elevation_mask_deg': ('卫星最低仰角（°）', '起始筛选和逐时可见性门限。通常先用 5～15°；降低门限会增加低仰角和大气映射的影响。'),
    'satellites.synthetic_count': ('合成候选卫星数', '仅合成星座有效，整数 1～32；不是本次一定使用的卫星数。'),
    'satellites.synthetic_planes': ('合成轨道面数', '仅合成星座有效，整数 1～合成候选卫星数；不是对真实 GPS 布局的复现。'),
    'satellites.synthetic_radius_m': ('合成轨道地心半径（m）', '圆轨道相对地心的半径，不是离地高度；须大于 WGS84 赤道半径。'),
    'satellites.synthetic_inclination_deg': ('合成轨道倾角（°）', '仅合成星座有效，范围 0～180°。'),
    'satellites.synthetic_raan_offset_deg': ('合成轨道面赤经偏移（°）', '整体改变合成轨道面的初始升交点赤经，可用于改变演示卫星几何。'),
    'satellites.epoch_gps_week': ('合成轨道参考 GPS 周', '与参考周内秒共同定义合成轨道初始相位和线性卫星钟参考时刻。'),
    'satellites.epoch_gps_sow': ('合成轨道参考周内秒（s）', '仅合成星座有效，采用 GPST。'),
    'satellites.synthetic_clock_bias_s': ('合成卫星初始钟差（s）', '所有合成卫星共同使用的初始钟差，不是逐颗 PRN 的独立配置。'),
    'satellites.synthetic_clock_drift_sps': ('合成卫星钟漂（s/s）', '所有合成卫星共同使用的线性钟漂。应按目标设备或资料设置，探索性值须作为假设记录。'),
    'satellites.synthetic_tgd_s': ('合成 GPS L1 群延迟 TGD（s）', '代码路径加入 +c×TGD，载波路径不加入。'),
    'propagation.mode': ('传播方式', 'relay：卫星→室外天线→室内发射点→用户；direct：卫星直达用户，用作基线，要求补偿为零。'),
    'propagation.earth_rotation': ('修正天空段地球自转', '通常保持开启。关闭用于对照实验，不代表其他传播因素已达到相同精度。'),
    'propagation.light_time_tolerance_s': ('光行时迭代容差（s）', '天空几何飞行时间的正收敛阈值；实现最多迭代 8 次。容差不能等同于整个仿真的物理精度。'),
    'propagation.min_path_m': ('最小室内传播路径（m）', '用户到发射点或反射镜像源小于此距离时拒绝运行，避免点源损耗模型奇异；不是实测近场边界。'),
    'relay.architecture': ('转发架构', 'transparent：理想透明转发，独立发射点钟差须为零；regenerative：允许指定等效独立时钟误差，不含真实再生硬件电路。'),
    'relay.mapping': ('卫星到发射点映射', 'JSON 对象，例如 {"3":"V1","16":"V2"}。键用 PRN 字符串 1～32，不写 G03 或 03；未列出的卫星按发射点循环分配。'),
    'relay.transmitters': ('室内发射点列表', '完整配置 1～4 个发射点，每个条目均须保留完整字段。各点编号唯一，坐标须在房间内并满足两两间距约束。'),
    'relay.min_spacing_m': ('发射点间距严格下界（m）', '每对发射点的距离必须大于该值；等于下界也不允许。单发射点时没有两两间距约束。'),
    'relay.max_spacing_m': ('发射点间距严格上界（m）', '每对发射点的距离必须小于该值；等于上界也不允许。'),
    'relay.transmitters.*.id': ('编号', '唯一发射点编号，例如 V1；卫星映射中须引用完全相同的编号。'),
    'relay.transmitters.*.position_enu_m': ('位置 [x、y、z]（m）', '在局部 ENU 中的位置，须位于房间内或边界上，并满足发射点间距约束。即使仅解算 x、y，传播仍需要物理高度 z。'),
    'relay.transmitters.*.cable_length_m': ('线缆物理长度（m）', '非负。等效传播路径为“线缆长度 ÷ 速度因子”，不是直接把长度作为延迟路径。'),
    'relay.transmitters.*.cable_velocity_factor': ('线缆速度因子', '信号在线缆中的速度与光速之比，范围 0 < 值 ≤ 1。应参照线缆规格或实测，当前群延迟与相位延迟假设相同。'),
    'relay.transmitters.*.processing_delay_s': ('处理及缓冲延迟（s）', '非负。1 ms 约对应 300 km 的固定路径；公共延迟可被接收机钟差吸收，不等于室内距离误差。'),
    'relay.transmitters.*.phase_offset_rad': ('附加载波相位（rad）', '只改变载波相位，不改变代码时延。2π rad 为一个周期。'),
    'relay.transmitters.*.reference_distance_m': ('损耗参考距离（m）', '须大于零；在此距离且无附加损耗时使用参考 C/N0。'),
    'relay.transmitters.*.path_loss_exponent': ('功率路径损耗指数', '非负，2 对应自由空间距离指数模型。室内值须由实测校准，不能视为已完成绝对链路预算。'),
    'relay.transmitters.*.excess_loss_db': ('固定附加损耗（dB）', '正值衰减信号，通常从非负值开始；该值通过电压增益进入 I/Q。'),
    'compensation.default': ('默认补偿参数', '未设置逐星专属项的 PRN 使用这组补偿；补偿函数为事先给定的时间函数，不自动读取用户真值。'),
    'compensation.per_prn': ('逐颗卫星补偿', 'JSON 对象，例如 {"3":{"range_offset_m":2}}。PRN 键须用 1～32 的字符串；每项可只写部分字段，其余继承当前默认补偿。'),
    'compensation.max_range_m': ('距离补偿绝对上限（m）', '限制整个仿真时段的补偿包络，默认 30 m。负补偿还须有足够正固定缓冲，不允许信号因果超前。'),
    'compensation.max_doppler_hz': ('频移补偿绝对上限（Hz）', '限制补偿产生的多普勒，包括距离补偿导数和额外频率控制；不是天空信号的总多普勒上限。'),
    'compensation.default.mode': ('补偿控制方式', 'delay_coupled：距离与频移由同一延迟耦合；independent_frequency：另允许独立载波频移，需要相应硬件能力。'),
    'compensation.default.range_offset_m': ('常量距离补偿（m）', '初始常量路径补偿，正值延长代码与载波路径，负值减小已有的正固定缓冲。'),
    'compensation.default.range_rate_mps': ('距离补偿变化率（m/s）', '线性距离斜率，同时产生 -变化率/λ 的补偿多普勒，须满足频移上限。'),
    'compensation.default.range_sine_m': ('正弦距离补偿振幅（m）', '振幅与周期共同决定频移振幅；减小周期可能超出频移补偿约束。'),
    'compensation.default.range_period_s': ('正弦距离补偿周期（s）', '须大于零，即使正弦振幅为零也须保留有效周期。'),
    'compensation.default.frequency_offset_hz': ('额外常量载波频移（Hz）', '仅 independent_frequency 模式允许非零。正值使载波相位随时间增加。'),
    'compensation.default.frequency_rate_hzps': ('额外频移变化率（Hz/s）', '仅 independent_frequency 模式允许非零；通过积分进入连续载波相位。'),
    'compensation.default.frequency_sine_hz': ('额外正弦频移振幅（Hz）', '仅 independent_frequency 模式允许非零；须满足总频移补偿约束。'),
    'compensation.default.frequency_period_s': ('额外正弦频移周期（s）', '须大于零，即使额外频移振幅为零也须保留有效周期。'),
    'receiver_clock.frequency_gm_sigma_sps': ('随机钟漂标准差（s/s）', '非负。0 表示关闭；随机频率过程积分成连续钟差，不是每个时刻独立的时钟跳变。'),
    'receiver_clock.frequency_gm_tau_s': ('随机钟漂相关时间（s）', 'Gauss–Markov 频率过程的相关时间，须大于零。'),
    'receiver_clock.clock_grid_s': ('时钟过程积分间隔（s）', '须大于零。减小可提高时间分辨率，但会增加积分点数与内存。'),
    'atmosphere.enabled': ('加入简化大气延迟', '开启简化对流层与固定 TEC 单层电离层；无误差基线可关闭。这不是实测天气与实时电离层场。'),
    'atmosphere.pressure_hpa': ('气压（hPa）', '须大于零，用于对流层模型；应与天线高度及实验天气对应。'),
    'atmosphere.temperature_k': ('绝对温度（K）', '校验范围 150 < 值 < 350。20°C 对应 293.15 K。'),
    'atmosphere.relative_humidity': ('相对湿度（0～1）', '范围 0～1，不是百分数 0～100；例如 50% 填 0.5。'),
    'atmosphere.vertical_tec_tecu': ('垂直电子含量（TECU）', '非负。1 TECU = 10¹⁶ electrons/m²；全场景使用固定值，不是实测时空扰动。'),
    'atmosphere.iono_shell_height_m': ('电离层单层壳高（m）', '须大于零，用于把垂直电子含量映射到卫星斜路径。'),
    'atmosphere.min_mapping_elevation_deg': ('大气映射最低仰角（°）', '建议严格大于零，避免低仰角映射发散；与卫星可见性最低仰角是不同参数。'),
    'multipath.enabled': ('加入墙面单次反射', '仅在转发 I/Q 中加入镜面反射路径，不会自动在观测 CSV 中伪造多径测量偏差。'),
    'multipath.walls': ('参与反射的墙面列表', 'JSON 字符串列表，从 east、west、north、south、floor、ceiling 中选择；不包含家具与隔墙。'),
    'multipath.reflection_amplitude': ('反射电压幅度比例', '范围 0～1。功率比例是该值的平方，还会叠加反射路径自身的距离损耗。'),
    'multipath.reflection_phase_rad': ('反射相位变化（rad）', '默认 π rad，即 180°。当前使用常量，不按材料、入射角或极化推导。'),
    'observations.add_noise': ('向观测值加入统计噪声', '控制伪距与多普勒 CSV 的估计误差；与 I/Q 采样噪声开关相互独立。'),
    'observations.reference_cn0_dbhz': ('参考载噪密度比（dB-Hz）', '损耗参考距离上的 C/N0，同时用于 I/Q 信号电压幅度归一化；不是完整发射功率链路预算。'),
    'observations.reference_cn0_for_noise_dbhz': ('观测噪声标定 C/N0（dB-Hz）', '代码与多普勒噪声标准差对应的标定载噪密度比，实际标准差随当前信号强度缩放。'),
    'observations.code_sigma_m': ('伪距噪声标准差（m）', '标定 C/N0 条件下的代码测量噪声，须非负。不是最终位置误差。'),
    'observations.doppler_sigma_hz': ('多普勒噪声标准差（Hz）', '标定 C/N0 条件下的频移测量噪声，须非负。不是最终速度误差。'),
    'observations.code_noise_correlation_s': ('伪距噪声相关时间（s）', '非负。0 表示白噪声，正值使用指数相关模型，递推考虑实际时刻间隔。'),
    'observations.doppler_noise_correlation_s': ('多普勒噪声相关时间（s）', '非负。可与伪距噪声相关时间独立设置。'),
    'observations.noise_code_doppler_correlation': ('伪距与多普勒噪声相关系数', '范围 -1～1，作用于标准化创新项；两者相关时间不同则不等于稳态输出相关系数。'),
    'observations.minimum_cn0_dbhz': ('最低有效 C/N0（dB-Hz）', '仅开启 C/N0 门限时使用；低于此值的观测标记为无效。'),
    'observations.dropout_probability': ('观测随机丢失概率（0～1）', '每条 LOS 观测独立失效的概率。无效观测仍保留真值及有效性标志，不会直接删掉该行。'),
    'observations.apply_cn0_gate': ('按 C/N0 门限筛选观测', '开启后由最低有效 C/N0 判断有效性。这是模型门限，不等于真实接收机已经捕获或锁定。'),
    'solver.enabled': ('生成定位解与误差统计', '使用伪距、多普勒模型观测执行参考最小二乘；不使用室内发射点坐标修正解算，也不代表真实接收机输出。'),
    'solver.initial_enu_m': ('解算初始位置 [x、y、z]（m）', '首个时刻的独立初值；之后沿用上次估计，不会从每个时刻的真实位置初始化。'),
    'solver.max_iterations': ('每时刻最大迭代次数', '正整数；过小可能未收敛。数值收敛不能证明定位正确或室内几何可观测。'),
    'solver.position_tolerance_m': ('位置迭代停止阈值（m）', '正的位置和钟差更新阈值，是数值容差，不是定位精度保证。'),
    'solver.max_step_m': ('单次位置迭代最大步长（m）', '正值；限制每次位置更新，避免过大的迭代步长，不裁剪钟差更新。'),
    'solver.known_height_m': ('二维固定高度（m；空为三维）', 'null 或留空为三维；数值为固定 ENU 高度，范围 0～房间高度，0 有效。二维只解算 x、y，不从真值读取高度。'),
    'solver.apply_atmosphere': ('解算时使用大气改正', '在卫星直达预期模型中采用同一简化大气模型；传播端也关闭大气时，此项不产生改正。'),
    'solver.position_normalization_m': ('位置误差归一化尺度（m）', '须大于零。位置误差均值除以此值形成比例；默认 30 m 是研究约定，不是已确定的验收口径。'),
    'solver.velocity_normalization_mps': ('速度误差归一化尺度（m/s）', '须大于零。默认 80/3.6 m/s，静止段仍用固定尺度；不是每时刻真实速度。'),
    'iq.enabled': ('生成 I/Q 信号文件', '开启后保存复基带二进制数据及采样元信息。默认无完整导航电文，不能独立冷启动定位。'),
    'iq.start_s': ('I/Q 开始时刻（s）', '相对仿真起点的非负时刻，须与 I/Q 时长一起落在总仿真时段内。研究运动时注意覆盖动态段。'),
    'iq.duration_s': ('I/Q 生成时长（s）', '须大于零，默认 0.05 s 仅为短波形片段；长时长会明显增加文件与计算量。'),
    'iq.sample_rate_hz': ('I/Q 复采样率（sample/s）', '每秒复采样数，不是 I/Q 标量合计数。至少 2.046 MS/s，且中频与 C/A 主瓣须容于 Nyquist 区间。'),
    'iq.intermediate_frequency_hz': ('数字中频（Hz）', '0 为零中频复基带；须与采样率共同满足主瓣采样约束。'),
    'iq.format': ('I/Q 二进制格式', 'ci16_le：每个复采样 4 bytes，交错小端 int16；cf32_le：每个复采样 8 bytes，小端 complex64。'),
    'iq.chunk_samples': ('每块复采样数', '正整数，控制内存占用。改变分块不应改变全局时间、量化尺度或波形内容。'),
    'iq.output_name': ('I/Q 输出文件名', '只填基本文件名，如 signal.iq，不能包含目录，也不能与运行摘要、配置、CSV 等固定产物重名。'),
    'iq.adc_full_scale_sigma': ('ADC 满量程标准差倍数', '须大于零；仅 int16 量化使用。增大可减少削顶，但会降低量化利用率；cf32 不量化。'),
    'iq.navigation_bits_file': ('外部导航符号文件', '可选路径；留空为恒定 +1 符号，仅用于捕获/跟踪。外部 50 bit/s 符号不自动通过 LNAV 奇偶校验和星历一致性验证。'),
    'iq.add_noise': ('向 I/Q 采样加入 AWGN', '控制复采样的加性高斯白噪声，与观测 CSV 的统计噪声开关独立，避免重复计入测量误差。'),
    'iq.max_output_bytes': ('I/Q 文件字节上限（byte）', '仅限制单个 I/Q 文件的预计字节数，不含 CSV、NPZ 与 JSON；运行前还会检查磁盘空间。'),
}

_CLOCK_FIELDS = {
    'bias_s': ('初始钟差（s）', '零时刻的时钟偏差，正值使等效代码和载波路径增长。'),
    'drift_sps': ('线性钟漂（s/s）', '时钟频率误差；正值使钟差随时间增长。接收机解算同时估计等效钟漂。'),
    'drift_rate_sps2': ('钟漂变化率（s/s²）', '钟差中的二次项为 0.5×变化率×时间²。'),
    'sinusoid_amplitude_s': ('正弦钟差振幅（s）', '受控的正弦时钟扰动，不代表实测晶振完整噪声谱。'),
    'sinusoid_period_s': ('正弦钟差周期（s）', '须大于零；即使振幅为零，也保留有效周期。'),
}
for _name, (_label, _help) in _CLOCK_FIELDS.items():
    _FIELDS['receiver_clock.' + _name] = ('接收机' + _label, _help)
    _FIELDS['relay.transmitters.*.clock.' + _name] = ('时钟' + _label, _help + ' 透明转发时该点的独立误差幅度须为零。')

_CHOICES = {
    'satellites.source': ['synthetic', 'rinex'],
    'propagation.mode': ['relay', 'direct'],
    'relay.architecture': ['transparent', 'regenerative'],
    'compensation.default.mode': ['delay_coupled', 'independent_frequency'],
    'iq.format': ['ci16_le', 'cf32_le'],
}
_VECTORS = {
    'site.room_size_enu_m', 'site.outdoor_antenna_enu_m',
    'trajectory.start_enu_m', 'trajectory.end_enu_m',
    'relay.transmitters.*.position_enu_m', 'solver.initial_enu_m',
}
_PATHS = {'satellites.rinex_nav_file', 'iq.navigation_bits_file', 'input_observations.corrected_csv'}
_JSON = {'trajectory.waypoints_enu_m', 'relay.mapping', 'relay.transmitters',
         'compensation.default', 'compensation.per_prn'}


def describe(path, default_value, language='zh'):
    """Return a label/help/editor-kind dictionary for a dotted config path.

    ``path`` uses numeric transmitter indices (``relay.transmitters.0.id``).
    ``choices``, when present, contains exact saved JSON values, not translated
    display strings. Empty optional floats and file paths are represented by
    ``None`` in the configuration. The caller remains responsible for parsing
    and validating edited values through the model's public configuration API.
    """
    key = re.sub(r'^relay\.transmitters\.\d+(?=\.|$)', 'relay.transmitters.*', path)
    prefix = ''
    transmitter = re.match(r'^relay\.transmitters\.(\d+)\.', path)
    if transmitter:
        prefix = '发射点 ' + str(int(transmitter.group(1)) + 1) + ' · '
    per_prn = re.match(r'^compensation\.per_prn\.([^\.]+)\.(.+)$', key)
    if per_prn:
        prefix = 'PRN ' + per_prn.group(1) + ' · '
        key = 'compensation.default.' + per_prn.group(2)
    label, help_text = _FIELDS.get(key, ('扩展参数（' + path + '）', '按该字段的配置类型填写；运行前将按物理和格式规则校验。'))
    if key == 'solver.known_height_m':
        kind = 'optional_float'
    elif key in _PATHS:
        kind = 'path'
    elif key in _VECTORS:
        kind = 'vector'
    elif key in _JSON or isinstance(default_value, dict):
        kind = 'json'
    elif isinstance(default_value, bool):
        kind = 'bool'
    elif isinstance(default_value, int):
        kind = 'int'
    elif isinstance(default_value, float):
        kind = 'float'
    elif isinstance(default_value, list):
        kind = 'list'
    else:
        kind = 'text'
    if language == 'en':
        from .ui_english import FIELDS
        label, help_text = FIELDS.get(key, ('Parameter (' + path + ')', 'Enter a value of the required configuration type.'))
        if transmitter:
            prefix = 'Transmitter ' + str(int(transmitter.group(1)) + 1) + ' · '
        suffix = '\nParameter: '
    else:
        suffix = '\n参数名：'
    result = {'label': prefix + label, 'help': help_text + suffix + path, 'kind': kind}
    if key in _CHOICES:
        result['choices'] = list(_CHOICES[key])
    return result
