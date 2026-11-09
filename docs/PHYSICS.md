# 物理模型、计算约定与适用边界

本文以 `src/indoor_gnss/` 当前实现为准。所有输出均为仿真数据，必须连同配置、随机种子、软件版本及本说明使用。模型输出包括可追溯的传播真值、按指定随机误差模型生成的观测，以及理想复基带 I/Q；这三者具有不同含义。

当选择已补偿观测 CSV 时，观测来源改为外部文件，不再宣称其为本程序生成的仿真观测。程序直接使用文件中的完整伪距与多普勒，跳过合成观测、随机噪声、补偿函数及 I/Q 渲染；仍按配置星历和直达接收机模型求位置、速度、钟差和钟漂。默认不提供真值误差，可选参考只来自当前配置轨迹，不能视为外部实测真值。应用的原补偿控制块已移除；历史物理补偿函数保留用于复现已有研究配置。

## 1. 两种传播模式

`propagation.mode=direct` 表示真实卫星信号直接到达用户，用于模型与解算器的基线检查。此模式要求距离和载波补偿为零。

`propagation.mode=relay` 表示以下链路：

```text
GPS 卫星 S_i → 室外接收天线 A → 线缆/处理设备 → 室内发射点 V_j → 用户 U
```

`relay.mapping` 为 PRN 到室内发射点编号的映射；未明确指定的所选 PRN 按发射点列表循环分配。一颗 PRN 当前只映射到一个发射点。一个发射点可以播发多个 PRN。当前不实现同一 PRN 在多个独立发射点同时播发，也不实现运行期间切换映射。

`relay.architecture=transparent` 是保留原信号时基的理想透明转发模型。配置校验要求每个发射点的独立时钟误差为零。`regenerative` 允许在路径中加入每个发射点指定的等效时钟误差，但这只是显式的误差模型；并未实现实际再生设备的锁相、重采样、导航电文缓存或输出电路。

## 2. 坐标、时间与轨迹

- `site.latitude_deg`、`longitude_deg`、`height_m` 定义 WGS84 大地坐标原点；高度为椭球高，不是海拔。
- 室内坐标是 ENU：x 向东、y 向北、z 向上。`room_size_enu_m` 为这三个方向的尺寸，厂房尺寸不是地理经纬度。
- WGS84 原点转换到 ECEF，再用该点的 ENU 旋转矩阵进行局部与全球坐标转换。将厂房视为几十米尺度的欧氏长方体。
- `time.gps_week` 是完整 GPS 周，`gps_sow` 是 GPS 周内秒，二者采用 GPST。输入不是 UTC，程序不自动处理用户提供的 UTC 日期或闰秒转换。
- `time_s` 是从配置起始历元算起的接收机时钟时间。程序按 `physical = time_s - receiver_clock_m(time_s)/c` 得到用于轨迹和传播的近似物理时间。这是一阶时钟映射，适用于小钟差/小相对钟漂，不是广义相对论时钟积分模型。
- 接收机沿起点、各中间路径点、终点依次连接形成的折线移动。以各线段长度之和作为总路程，速度曲线按累计路程映射到各线段的位置。出发前与到达后静止。`acceleration_time_s=0` 时瞬时启停；正值时使用恒加速度起步、匀速和恒减速度停止。中间拐点的位置和速度大小连续，速度方向瞬时改变，模型未包含转弯半径或停车过程。
- `observation_interval_s` 定义常规时间网格；程序再插入按累计路程每隔 `trajectory_distance_step_m` 的采样时刻和各中间路径点的到达时刻。合并后的时刻未必等间隔。

默认用户速度为 80/3.6 m/s，30 m 的无加速运动持续 1.35 s。这是仿真真值设定，不代表接收机已达到对应输出率或跟踪能力。

### 仅解算 x、y 与三维物理传播

界面的“计算 Z 方向”按钮只控制接收机解算维度。关闭时用外部给定的 `solver.known_height_m` 固定用户 ENU 高度，求 x、y、接收机钟差及水平速度/钟漂；不会利用真实轨迹为解算器逐时提供高度。固定高度须在房间范围内，不准确的高度假设仍可能引入水平误差。此模式假设解算时垂直速度为零。

卫星、室外天线、室内发射点与用户仍处在三维物理空间，所有传播距离、大气项和 I/Q 波形保持三维计算。仅切换解算维度、保持其他配置和种子一致时，生成的轨迹真值与观测值相同；变化的是解算及其指标。二维结果不输出估计 z/vz，主位置与速度误差使用水平分量；三维保留 xyz 主指标。两种模式都额外报告水平误差，避免混用二维与三维误差口径。

## 3. 天空段、发射时刻与地球自转

程序对每个天空段迭代求解几何飞行时间：

```text
tau = | R3(omega_E*tau) S_i(t_A-tau) - A(t_A) | / c
```

`space_link()` 使用最多 8 次迭代，并以 `light_time_tolerance_s` 控制停止。`R3` 将发射时刻 ECEF 中的卫星坐标旋转到天空段接收时刻的 ECEF。地球自转使用几何飞行时间，不把接收机钟差、处理延迟或人工补偿误当作天空几何飞行时间。

转发模式下，天空段接收时刻取：

```text
t_A = t_physical - (d_indoor + d_fixed + q_code)/c
d_fixed = cable_length_m/cable_velocity_factor + c*processing_delay_s
```

所以卫星状态并非在用户最终接收时刻直接计算。室内路径使用当时用户与固定发射点的欧氏距离；没有迭代纳秒级室内飞行中用户位置的变化。以约 30 m 的路径和约 22 m/s 的速度估算，这项位移是微米量级。天空段的大气延迟计算在几何求解之后加入路径，不反馈到天空发射时刻迭代。

模型未加入固体潮、海潮负荷、天线相位中心改正、相位缠绕、Shapiro 延迟、地球极移、岁差章动或完整相对论光路模型。

## 4. 代码路径、载波路径和 TGD

把相位相关项也表示成米，当前代码采用：

```text
P_code = rho_sky + d_indoor + d_fixed + B_rx + B_tx
         - c*b_sat + T + I + c*TGD + q_code

L_carrier = rho_sky + d_indoor + d_fixed + B_rx + B_tx
            - c*b_sat + T - I + q_carrier
```

其中 `B_rx`、`B_tx` 为米单位钟差，`b_sat` 和 `TGD` 为秒，T/I 分别为对流层/电离层路径改正。`carrier_path_truth_m` 是连续相位路径模型，不是带整数模糊度的真实接收机载波相位观测。

RINEX 卫星钟改正包含广播钟多项式和周期相对论改正，不含 TGD。GPS L1 代码使用 `b_code=b_sat-TGD`，所以路径中的 `-c*b_code` 等于 `-c*b_sat+c*TGD`。载波路径没有加入 TGD。不能再在外部对已经包含这些项的仿真观测重复加减。

天空电离层使代码产生群延迟、载波产生相位超前，所以代码用 `+I`，载波用 `-I`。此实现只针对 GPS L1；不能直接将这些系数用于其他频段或其他 GNSS。

## 5. 大气模型

`atmosphere.enabled=true` 时支持：

1. 用气压、温度、相对湿度、大地纬度和高度计算 Saastamoinen 形式的干/湿天顶对流层延迟，再以 `1/sin(elevation)` 做简化映射。
2. 用固定 `vertical_tec_tecu` 和单层电离层高度，将垂直 TEC 映射到斜路径，并按 `40.3*TEC/f_L1^2` 得到米单位电离层项。

低仰角以 `min_mapping_elevation_deg` 截断，防止映射发散。模型采用全场景固定气象参数和垂直 TEC，没有读取实测气象、IONEX 或广播 Klobuchar 系数，没有空间/时间电离层扰动。转发模式的天空大气路径属于室外接收天线 A；不会再对室内几十米路径重复加入电离层。

## 6. 单次镜面反射与强度

`multipath.enabled=true` 且使用转发模式时，可为六个长方体表面选择单次镜面反射。程序将发射点关于墙面镜像，连接镜像点与用户，检查交点是否位于有限矩形表面，只有有效交点才保留该路径。镜像直线长度等于两段镜面反射光路的总长。

反射路径使用配置中的常量电压幅度系数和相位偏移。路径电压增益为：

```text
g = (reference_distance_m / d)^(path_loss_exponent/2)
    * 10^(-excess_loss_db/20)
```

反射路径再乘 `reflection_amplitude`，并加 `reflection_phase_rad`。`reference_cn0_dbhz + 20*log10(g)` 是该路径模型下的 C/N0。`reference_cn0_dbhz` 是归一化参考，不是通过发射功率、绝对天线增益和噪声温度完整推导出的链路预算。

当前没有室内物体/隔墙遮挡、穿透损耗、二次及更高次反射、绕射、散射、材质频率响应、Fresnel 系数、极化、天线方向图或近场电磁仿真。用户与点天线过近时由 `min_path_m` 拒绝，以免把远场路径损耗模型无限外推。天花板上恰好共面的发射点，其退化“反射”不会作为独立有效路径。

**观测表只输出 LOS 路径的模型伪距和多普勒。** 开启多径会在供 I/Q 合成的路径矩阵中增加反射信号，不会自动把反射偏差加进观测表。混合信号上的多径测量偏差取决于接收机相关器和跟踪算法，必须实际处理 I/Q 后评估。

## 7. 补偿、相位连续性与因果性

每颗 PRN 可以使用默认补偿，也可在 `compensation.per_prn` 覆盖。距离补偿由常量、线性斜坡和正弦组成：

```text
q(t) = q0 + v_q*t + A_q*sin(2*pi*t/T_q)
```

`delay_coupled` 模式令 `q_code=q_carrier=q(t)`，距离变化带来的补偿频移为：

```text
D_comp(t) = -q'(t)/lambda_L1
```

此模式禁止另外配置独立频移参数。`independent_frequency` 模式允许额外的频率偏移、频率斜坡和正弦。额外频移通过积分进入载波路径：

```text
q_carrier = q_code - lambda_L1 * integral(f_extra(t), dt)
```

这样使载波相位连续；不能用瞬时 `f(t)*t` 代替变频信号的相位积分。独立频移代表设备具有独立载波控制能力的假设，不是所有转发硬件都具备该能力。

程序对完整仿真区间使用保守解析包络检查 ±`max_range_m` 和 ±`max_doppler_hz`，不是只检查离散采样点。负补偿表示减小正的固定链路延迟；程序要求固定线缆/处理路径足够覆盖负补偿包络，保证不要求信号因果超前。这是保守检查，可能拒绝部分实际始终非负但解析上界偏大的参数组合。

补偿是配置好的开环时间函数，不会在每个时刻偷偷读取用户真值后求最佳补偿。本程序不自动完成发射点布局、映射或补偿参数优化。

## 8. 接收机时钟和随机频率过程

确定性钟差包括初始偏差、线性钟漂、钟漂变化率和正弦项。接收机还可配置固定网格上的 Gauss–Markov 频率误差：

```text
epsilon[k+1] = alpha*epsilon[k] + sigma*sqrt(1-alpha^2)*z[k]
alpha = exp(-clock_grid_s/frequency_gm_tau_s)
```

频率误差先梯形积分成钟差，随后对钟差做线性插值。零时刻的随机积分偏差被移除，随机种子由主种子与固定子流标识确定。此设计避免每个观测时刻独立跳动的时钟；但它仍是离散、分段线性近似，没有建模真实晶振的全部相位噪声谱、温漂、老化与硬件重启。

## 9. 多普勒、差分步长与观测随机误差

LOS 理想多普勒从完整载波路径的中心差分计算：

```text
range_rate(t) = [L_carrier(t+h)-L_carrier(t-h)]/(2*h)
D(t) = -range_rate(t)/lambda_L1
```

`time.derivative_step_s` 是 h。正的距离变化率代表路径增长，对应负的本程序多普勒。`carrier_range_rate_mps` 与代码伪距的时间导数不必完全相同，电离层符号及独立载波频移可以造成差异。

轨迹出发、拐点、停止、反射路径有效性改变、星历记录选择切换或线性插值节点附近，中心差分可能跨过分段边界，应检查步长敏感性；它不是所有时刻的严格解析瞬时速度。

`observations` 中的噪声是按参数生成的观测估计误差模型：

- 代码和多普勒分别设置标准差及指数相关时间；无相关时间时为白噪声。
- 根据每个输出时刻实际间隔递推，相关过程作用于标准化误差，再按该路径 C/N0 缩放。
- 可配置代码与多普勒“创新项”的相关系数；当两者相关时间不同，该参数不等于稳态输出误差的相关系数。
- 可配置随机丢失和 C/N0 有效门限；无效行仍保留真值和标志，使用者应按 `valid` 过滤。

这些观测噪声直接加在 LOS 伪距/多普勒表中，不是软件接收机从 I/Q 估计得到的误差。

## 10. I/Q 波形与 AWGN

I/Q 模块支持 GPS L1 C/A 的 PRN 1–32，1.023 Mchip/s、1023 码片、1 ms 周期。传播参数在模型时间网格上计算，再在线性插值后用于更高采样率的波形。时间网格过粗时，不能声称准确模拟快速弯曲的相位和运动；应缩小 `observation_interval_s` 并比较结果收敛性。

每条传播路径的复数波形近似为：

```text
s_k(t) = A_k*g_k(t)*C_PRN(t-P_code(t)/c)*data(t-P_code(t)/c)
         * exp(j*(-2*pi*L_carrier(t)/lambda_L1 + phi_k + 2*pi*f_IF*t))
```

同一 PRN 的 LOS 和反射路径相干叠加，所有 PRN 再相加。代码延迟使用代码路径，载波相位使用载波路径，二者不能互换。`phase_offset_rad` 表示额外硬件/反射相位，不是时间标记。

AWGN 采用显式归一化：复噪声 PSD 约定 N0=1，`E|w[n]|²=fs`，I/Q 各自方差为 fs/2；参考信号电压幅度 `A=sqrt(10^(C/N0_dBHz/10))`，路径增益再单独乘入。此噪声实际加入每个复采样点，和第 9 节的观测误差使用独立随机子流。I/Q 中不会再注入已加在观测表中的代码/多普勒随机误差，避免重复计入。

支持交错 little-endian int16（每个复采样 4 字节）和 little-endian complex64（每个复采样 8 字节）。int16 使用整段固定量化尺度，并记录削顶分量数与比例；不会每个分块重新归一化。时间索引来自全局整数采样点，分块只控制内存占用。

当前为理想矩形码片的复基带波形。矩形码片的频谱旁瓣无限延伸，采样率/IF 校验仅保证主瓣有足够 Nyquist 空间，**不等于实现了严格抗混叠滤波**。当前未实现模拟射频前端滤波、前端带宽、AGC 动态、ADC 非线性、独立采样时钟误差、真实天线或硬件重放设备。

## 11. 导航电文与不能宣称的结果

默认 `iq.navigation_bits_file=null` 时，数据符号恒为 +1。输出是 `constant_symbols_tracking_only`：可用于研究 C/A 捕获/跟踪，但没有合法 LNAV 时间、电文和星历信息，不能据此宣称可独立冷启动定位。

可提供按 PRN 区分的外部 50 bit/s 0/1 符号文件，并用 `start_gps_sow` 标记首比特时间。程序检查发射时刻是否被提供的位序列覆盖，不会循环填充、不做越界外推。但它不检查 LNAV 奇偶校验、TOW、IODC/IODE、周数、卫星健康状态或电文星历是否与传播所用星历一致。用户提供任意 0/1 数组不代表已经构成合法 GPS 导航电文。

当前项目未验证完整的 GNSS-SDR 捕获、跟踪、电文解码和冷启动定位链路。单元测试或波形文件成功生成只能证明各自覆盖的计算或文件性质。默认 I/Q 是用户出发后的50ms动态片段；其他配置的窗口也可能位于用户出发前；若研究动态段，应明确设置 `iq.start_s` 和 `iq.duration_s`，并为实际接收机安排足够的初始化/辅助数据。

## 12. 合成星座与 RINEX 星历

`satellites.source=synthetic` 使用按配置生成的圆形中地球轨道集合：给定轨道半径、倾角、轨道面数及初始相位，按二体角速度与地球自转得到移动 ECEF 坐标。它具有受约束的轨道尺度与速度，但不是指定日期的真实 GPS 星座；其 PRN 是波形标识，不能和真实星历混用。其钟差为配置的公共线性模型。

`source=rinex` 支持 RINEX 2/3 传统 GPS NAV（含 `.gz`），按广播开普勒参数和谐波修正计算位置，加入周期相对论钟改正。混合 RINEX 3 文件的非 GPS 记录按格式长度跳过。RINEX 4、观测文件、GLONASS-only NAV、未知记录类型、过期或默认不允许的不健康星历会明确报错。速度和钟漂用同一条选定记录的 ±0.1 s 差分，避免仅因记录切换制造速率跳变。

程序按开始时刻健康且满足仰角门限的卫星筛选列表，之后仍计算各时刻可见性。用户可显式指定 PRN；指定列表必须在开始时刻可见。完整运行期间星历过期仍会报错，不会无声复用。

RINEX 读取与传播实现包含构造数据的单元验证，已用 `data/raw/brdc0010.22n` 公共真实广播 NAV 样本完成 8 星读取和生成链路冒烟检查，结果应连同实验目录和运行日志使用。当前没有以独立 RTKLIB/gLAB 或 SP3 精密轨道完成数值交叉验证，也未据真实 RINEX 自动生成完整可解码 LNAV。真实 NAV 链路成功运行不等于轨道算法已被独立精度验证。

## 13. 建议的物理核验顺序

1. 无噪声、无大气、零钟差的直达基线：检查传播与位置/速度解算。
2. 公共距离/频率偏移：检查其与接收机钟差/钟漂的关系，不应误判为所有位置均被同量移动。
3. 线性距离补偿：检查 `D_comp=-q'/lambda`，以及不同差分步长下的结果收敛。
4. 反射几何：检查路径不短于 LOS，交点位于有限墙面，退化反射无效。
5. 同一配置/种子：检查观测可复现、I/Q 分块大小不改变波形字节。
6. 实际软件接收机与真实星历：独立检查捕获/跟踪、电文及观测结果。此项是后续验证，不应由前五项代替。

## 14. 官方与原始资料

- [IS-GPS-200N：GPS Space Segment/Navigation User Interfaces](https://www.navcen.uscg.gov/sites/default/files/pdf/gps/IS-GPS-200N.pdf)：L1 C/A 码结构、导航电文与广播星历用户算法。
- [ESA Navipedia：Satellite Coordinates Computation](https://gssc.esa.int/navipedia/index.php/Satellite_Coordinates_Computation)：发射/接收时刻 ECEF 与地球自转。
- [ESA Navipedia：GPS and Galileo Satellite Coordinates Computation](https://gssc.esa.int/navipedia/index.php/GPS_and_Galileo_Satellite_Coordinates_Computation)：广播轨道参数、周边界与有效期。
- [ESA Navipedia：GNSS Basic Observables](https://gssc.esa.int/navipedia/index.php/GNSS_Basic_Observables)：伪距、载波、多普勒和电离层符号。
- [ESA Navipedia：Combining Pairs of Signals and Clock Definition](https://gssc.esa.int/navipedia/index.php/Combining_pairs_of_signals_and_clock_definition)：钟定义与代码硬件偏差。
- [ESA Navipedia：Data Demodulation and Processing](https://gssc.esa.int/navipedia/index.php/Data_Demodulation_and_Processing)：代码延迟、导航时间与伪距生成。
- [GNSS-SDR：My First Position Fix](https://gnss-sdr.org/my-first-fix/)：真实采样文件与软件接收机处理流程，不能视为本项目已完成该验证。
- [Xu 等，2015 原论文](https://pmc.ncbi.nlm.nih.gov/articles/PMC4481917/)：真实信号分离、加入几何延迟及重新合成的研究背景。本程序不声称复现其原始录波或逐点结果。


---

# English translation: Physical model, computational conventions, and limits

This document describes the current implementation in `src/indoor_gnss/`. All generated outputs are simulated data and must be used with the configuration, random seed, software version, and this document. Outputs include traceable propagation truth, observations generated under specified random-error models, and ideal complex-baseband I/Q; these have different meanings.

When a corrected-observations CSV is selected, observations come from that external file and are no longer claimed to have been simulated by this program. The program uses the complete pseudorange and Doppler values directly and skips synthetic observations, random noise, compensation functions, and I/Q rendering. It still uses the configured ephemeris and direct-path receiver model to solve for position, velocity, clock bias, and clock drift. Ground-truth errors are not reported by default; the optional reference is only the current configured trajectory and is not ground truth for external measurements. The application's former compensation controls have been removed; historical physical compensation functions remain available for reproducing existing research configurations.

## 1. Two propagation modes

`propagation.mode=direct` means that a real satellite signal reaches the user directly; it provides a baseline for model and solver checks. This mode requires zero range and carrier compensation.

`propagation.mode=relay` represents the following link:

```text
GPS satellite S_i → outdoor receiving antenna A → cable/processing equipment → indoor transmitter V_j → user U
```

`relay.mapping` maps PRNs to indoor transmitter IDs. Selected PRNs not explicitly specified are assigned cyclically over the transmitter list. A PRN currently maps to one transmitter; a transmitter can broadcast multiple PRNs. Simultaneous broadcasting of one PRN from multiple independent transmitters and switching mappings during a run are not implemented.

`relay.architecture=transparent` is an ideal transparent relay preserving the original signal timebase. Configuration validation requires zero independent clock error at every transmitter. `regenerative` permits a specified equivalent clock error per transmitter, but this is only an explicit error model; actual regenerative hardware phase locking, resampling, navigation-message buffering, and output circuitry are not implemented.

## 2. Coordinates, time, and trajectory

- `site.latitude_deg`, `longitude_deg`, and `height_m` define the WGS84 geodetic origin; height is ellipsoidal height, not altitude above sea level.
- Indoor coordinates are ENU: x east, y north, z up. `room_size_enu_m` gives the dimensions in these directions; factory dimensions are not geographic latitude and longitude.
- The WGS84 origin is converted to ECEF, then the origin's ENU rotation matrix converts between local and global coordinates. The factory is treated as a Euclidean rectangular cuboid on the scale of tens of meters.
- `time.gps_week` is the full GPS week, and `gps_sow` is seconds of GPS week, both in GPST. Input is not UTC; the program does not automatically convert user-supplied UTC dates or leap seconds.
- `time_s` is receiver-clock time from the configured initial epoch. The approximate physical time used for trajectory and propagation is `physical = time_s - receiver_clock_m(time_s)/c`. This first-order clock mapping is suitable for small clock bias and relative drift; it is not a general-relativistic clock integration model.
- The receiver follows straight segments through the start, intermediate waypoints and end in order. The sum of the segment lengths gives the total path length. The motion profile determines cumulative distance, which gives the position on each segment. The receiver remains stationary before departure and after arrival. With `acceleration_time_s=0`, it starts and stops instantaneously. A positive value gives constant acceleration at departure, a constant-speed phase and constant deceleration at arrival. Position and speed are continuous at intermediate turns, and the velocity direction changes instantaneously. The model uses sharp turns without a pause.
- `observation_interval_s` defines the regular time grid. The simulator adds samples spaced by `trajectory_distance_step_m` along the cumulative path length and the arrival time at each intermediate waypoint. The merged grid may have uneven intervals.

The default user speed is 80/3.6 m/s, and unaccelerated motion across 30 m takes 1.35 s. This is a simulation truth setting, not a claim about receiver output rate or tracking capability.

### Solving only x and y while retaining three-dimensional physical propagation

The interface's “Solve Z” control affects only receiver solution dimensions. When disabled, the externally supplied `solver.known_height_m` fixes user ENU height while solving x, y, receiver clock bias, horizontal velocity and clock drift; the solver is not supplied with the true trajectory height at each epoch. Fixed height must be within the room; an inaccurate assumed height may still introduce horizontal error. This mode assumes zero vertical velocity in the solver.

Satellites, the outdoor antenna, indoor transmitters and the user remain in three-dimensional physical space, and all propagation distances, atmosphere terms and I/Q waveforms remain three-dimensional. Changing only the solution dimension while holding other configuration and the random seed fixed leaves generated trajectory truth and observations unchanged; the solution and its metrics change. Two-dimensional results do not output estimated z/vz and use horizontal components for primary position and velocity errors; three-dimensional results retain xyz primary metrics. Both modes additionally report horizontal errors to prevent mixing two- and three-dimensional error definitions.

## 3. Sky path, transmission time, and Earth rotation

For each sky path, the program iteratively solves geometric flight time:

```text
tau = | R3(omega_E*tau) S_i(t_A-tau) - A(t_A) | / c
```

`space_link()` uses at most 8 iterations, stopping according to `light_time_tolerance_s`. `R3` rotates satellite coordinates from ECEF at transmission to ECEF at sky-path reception. Earth rotation uses geometric flight time and does not mistake receiver clock bias, processing delay or artificial compensation for sky-path geometric flight time.

In relay mode, the sky-path reception time is:

```text
t_A = t_physical - (d_indoor + d_fixed + q_code)/c
d_fixed = cable_length_m/cable_velocity_factor + c*processing_delay_s
```

Thus satellite state is not evaluated directly at final user reception time. The indoor path uses the Euclidean distance between the user and fixed transmitter at that time; it does not iterate the user's position change during nanosecond-scale indoor flight. For a path of about 30 m and speed of about 22 m/s, the displacement is on the order of micrometers. Sky-path atmospheric delay is added after geometric solution and is not fed back into the sky transmission-time iteration.

Solid Earth tides, ocean loading, antenna phase-center corrections, phase windup, Shapiro delay, polar motion, precession-nutation, and a complete relativistic light-path model are not included.

## 4. Code path, carrier path, and TGD

Expressing phase-related terms in meters, the current code uses:

```text
P_code = rho_sky + d_indoor + d_fixed + B_rx + B_tx
         - c*b_sat + T + I + c*TGD + q_code

L_carrier = rho_sky + d_indoor + d_fixed + B_rx + B_tx
            - c*b_sat + T - I + q_carrier
```

`B_rx` and `B_tx` are clock biases in meters; `b_sat` and `TGD` are in seconds; T and I are tropospheric and ionospheric path corrections. `carrier_path_truth_m` is a continuous phase-path model, not a real receiver carrier-phase observation with integer ambiguity.

RINEX satellite clock correction includes the broadcast clock polynomial and periodic relativistic correction, but not TGD. GPS L1 code uses `b_code=b_sat-TGD`, so `-c*b_code` in the path equals `-c*b_sat+c*TGD`. TGD is not added to the carrier path. Do not externally add or subtract these terms again from simulated observations that already include them.

Sky-path ionosphere produces code group delay and carrier phase advance, so code uses `+I` and carrier uses `-I`. This implementation is only for GPS L1; these coefficients cannot be applied directly to other bands or GNSS systems.

## 5. Atmospheric model

When `atmosphere.enabled=true`:

1. Pressure, temperature, relative humidity, geodetic latitude and height give Saastamoinen-form dry/wet zenith tropospheric delays, mapped using simplified `1/sin(elevation)`.
2. Fixed `vertical_tec_tecu` and a single-layer ionosphere height map vertical TEC onto the slant path; `40.3*TEC/f_L1^2` gives the ionospheric term in meters.

Low elevations are clamped at `min_mapping_elevation_deg` to avoid divergent mapping. Weather parameters and vertical TEC are fixed throughout the scene. No measured weather, IONEX or broadcast Klobuchar coefficients are read, and no spatial or temporal ionospheric perturbation is modeled. In relay mode the sky atmospheric path belongs to outdoor receiving antenna A; the ionosphere is not added again to the indoor path of tens of meters.

## 6. Single specular reflections and signal strength

With `multipath.enabled=true` in relay mode, single specular reflections can be selected for the six cuboid surfaces. The transmitter is mirrored across the wall and connected to the user; the program checks whether the intersection lies on the finite rectangular surface and retains the path only for a valid intersection. The mirror-line length equals the total length of the two reflected segments.

Reflected paths use configured constant voltage amplitude and phase offsets. Path voltage gain is:

```text
g = (reference_distance_m / d)^(path_loss_exponent/2)
    * 10^(-excess_loss_db/20)
```

A reflected path is additionally multiplied by `reflection_amplitude` and shifted by `reflection_phase_rad`. `reference_cn0_dbhz + 20*log10(g)` gives path C/N0 under this model. `reference_cn0_dbhz` is a normalization reference, not a complete link budget derived from transmit power, absolute antenna gain and noise temperature.

The model omits indoor object/partition blockage, penetration loss, second and higher-order reflections, diffraction, scattering, material frequency response, Fresnel coefficients, polarization, antenna patterns and near-field electromagnetic simulation. If the user is too close to a point antenna, `min_path_m` rejects the path to avoid infinitely extrapolating a far-field loss model. A transmitter exactly coplanar with the ceiling does not create a separate valid degenerate “reflection.”

**The observation table outputs model pseudorange and Doppler for LOS paths only.** Multipath adds reflected signals to the path matrix used for I/Q synthesis, but does not automatically add reflection bias to the observation table. Multipath measurement bias in a mixed signal depends on the receiver correlator and tracking algorithm and must be evaluated by actually processing I/Q.

## 7. Compensation, phase continuity, and causality

Each PRN can use default compensation or an override in `compensation.per_prn`. Range compensation combines a constant, a linear ramp and a sinusoid:

```text
q(t) = q0 + v_q*t + A_q*sin(2*pi*t/T_q)
```

In `delay_coupled` mode, `q_code=q_carrier=q(t)` and the compensation frequency shift caused by changing range is:

```text
D_comp(t) = -q'(t)/lambda_L1
```

This mode prohibits independent frequency-shift parameters. `independent_frequency` mode permits an additional frequency offset, frequency ramp and sinusoid. The extra frequency shift is integrated into the carrier path:

```text
q_carrier = q_code - lambda_L1 * integral(f_extra(t), dt)
```

This keeps carrier phase continuous; instantaneous `f(t)*t` cannot replace phase integration for a varying-frequency signal. Independent frequency shift assumes equipment has independent carrier control; not all relay hardware has this capability.

Conservative analytic envelopes check ±`max_range_m` and ±`max_doppler_hz` over the whole simulation interval, not only discrete sample points. Negative compensation means reducing positive fixed-link delay; enough fixed cable/processing path must cover the negative compensation envelope so the model never demands causally advanced signals. This conservative check may reject some combinations that are always nonnegative in practice but have a loose analytic bound.

Compensation is a configured open-loop time function; it does not secretly read user truth at every time to find optimal compensation. The program does not automatically optimize transmitter layout, mapping or compensation parameters.

## 8. Receiver clock and random frequency process

Deterministic clock bias includes initial offset, linear drift, drift rate and a sinusoidal term. A Gauss–Markov receiver frequency error can additionally be configured on a fixed grid:

```text
epsilon[k+1] = alpha*epsilon[k] + sigma*sqrt(1-alpha^2)*z[k]
alpha = exp(-clock_grid_s/frequency_gm_tau_s)
```

Frequency error is trapezoidally integrated to clock bias, then clock bias is linearly interpolated. The random integrated offset at time zero is removed; the random seed is determined from the main seed and a fixed substream identifier. This avoids a clock independently jumping at each observation epoch, but remains a discrete, piecewise-linear approximation that omits the full real oscillator phase-noise spectrum, temperature drift, aging and hardware restarts.

## 9. Doppler, difference step, and random observation errors

Ideal LOS Doppler comes from a central difference of the complete carrier path:

```text
range_rate(t) = [L_carrier(t+h)-L_carrier(t-h)]/(2*h)
D(t) = -range_rate(t)/lambda_L1
```

`time.derivative_step_s` is h. A positive range rate indicates an increasing path and corresponds to negative Doppler in this program. `carrier_range_rate_mps` need not exactly equal the time derivative of code pseudorange: ionospheric sign and independent carrier frequency shift can make them differ.

Near trajectory departure, turns, stopping, changes in reflection validity, ephemeris-record selection changes, or linear interpolation nodes, central differences can cross piecewise boundaries. Check sensitivity to step size; the result is not a strict analytic instantaneous velocity at all times.

Noise in `observations` models observation estimation error using configured parameters:

- Code and Doppler have separately configured standard deviations and exponential correlation times; zero correlation time gives white noise.
- Recursion uses actual intervals between output epochs. Correlation acts on standardized errors, which are then scaled by path C/N0.
- Code and Doppler innovation correlation is configurable; with different correlation times it is not equal to the steady-state correlation of output errors.
- Random dropout and a C/N0 validity threshold are configurable. Invalid rows retain truth and flags; users should filter on `valid`.

These observation errors are added directly to the LOS pseudorange/Doppler table, not estimated by a software receiver from I/Q.

## 10. I/Q waveforms and AWGN

The I/Q module supports GPS L1 C/A PRNs 1–32 at 1.023 Mchip/s, 1023 chips and a 1 ms period. Propagation parameters are evaluated on the model time grid and linearly interpolated for higher-rate waveform samples. If the grid is too coarse, accurate fast-changing phase and motion cannot be claimed; reduce `observation_interval_s` and compare convergence.

The complex waveform for each propagation path is approximately:

```text
s_k(t) = A_k*g_k(t)*C_PRN(t-P_code(t)/c)*data(t-P_code(t)/c)
         * exp(j*(-2*pi*L_carrier(t)/lambda_L1 + phi_k + 2*pi*f_IF*t))
```

LOS and reflected paths for the same PRN are coherently summed, then all PRNs are summed. Code delay uses the code path, and carrier phase uses the carrier path; they are not interchangeable. `phase_offset_rad` is additional hardware/reflection phase, not a time tag.

AWGN is explicitly normalized: complex noise PSD convention N0=1, `E|w[n]|²=fs`, and each I/Q component has variance fs/2. Reference signal voltage amplitude is `A=sqrt(10^(C/N0_dBHz/10))`, with path gain multiplied separately. This noise is added to every complex sample and uses a random substream independent of section 9 observation errors. Code/Doppler random errors already added to the observation table are not injected again into I/Q, avoiding double counting.

Supported formats are interleaved little-endian int16 (4 bytes per complex sample) and little-endian complex64 (8 bytes per complex sample). Int16 uses one fixed quantization scale for the whole segment and records the count and fraction of clipped components; it is not renormalized per chunk. Time indices come from global integer sample indices; chunks only control memory use.

The current complex-baseband waveform uses ideal rectangular chips. Rectangular-chip spectral sidelobes extend indefinitely; the sample-rate/IF check only ensures adequate Nyquist space for the main lobe and **does not implement strict anti-alias filtering**. Analog RF front-end filtering, front-end bandwidth, AGC dynamics, ADC nonlinearities, independent sampling-clock errors, real antennas and hardware playback devices are not implemented.

## 11. Navigation messages and claims that cannot be made

By default, `iq.navigation_bits_file=null` and data symbols remain +1. Output is `constant_symbols_tracking_only`: it can support C/A acquisition/tracking research but lacks valid LNAV time, message and ephemeris information and cannot support a claim of independent cold-start positioning.

An external per-PRN 50 bit/s 0/1 symbol file can be provided, with `start_gps_sow` marking the first bit. The program checks whether the supplied bit sequence covers transmission times; it does not repeat or extrapolate beyond the sequence. It does not verify LNAV parity, TOW, IODC/IODE, week, satellite health, or consistency between message and propagation ephemerides. Arbitrary user-supplied 0/1 arrays do not automatically constitute valid GPS navigation messages.

Full GNSS-SDR acquisition, tracking, message decoding and cold-start positioning have not been validated in this project. Successful unit tests or waveform generation only demonstrate the specific computations or file properties covered. Default I/Q is a 50 ms dynamic segment after user departure; other configurations may place the window before departure. For dynamic research explicitly set `iq.start_s` and `iq.duration_s` and allow enough initialization/assistance data for the actual receiver.

## 12. Synthetic constellation and RINEX ephemeris

`satellites.source=synthetic` uses a configured collection of circular medium Earth orbits: orbital radius, inclination, number of planes and initial phase, combined with two-body angular velocity and Earth rotation, produce moving ECEF coordinates. Orbital scale and speed are constrained, but the constellation is not the real GPS constellation on a specified date. PRNs identify waveforms and cannot be mixed with real ephemerides. Clock bias uses the configured common linear model.

`source=rinex` supports traditional RINEX 2/3 GPS NAV, including `.gz`; positions come from broadcast Keplerian parameters and harmonic corrections, with periodic relativistic clock correction. Non-GPS records in mixed RINEX 3 files are skipped by format length. RINEX 4, observation files, GLONASS-only NAV, unknown record types, expired ephemerides and unhealthy ephemerides disallowed by default produce explicit errors. Velocity and clock drift use ±0.1 s differencing of the same selected record to avoid rate jumps caused solely by switching records.

The program selects satellites healthy and above the elevation mask at the start, then computes visibility at each epoch. Users may specify PRNs explicitly; every specified PRN must be visible initially. Expired ephemerides during a run cause an error rather than silent reuse.

RINEX reading and propagation have unit tests using constructed data; an 8-satellite read and generation smoke check used the public real broadcast NAV sample `data/raw/brdc0010.22n`. Results should be used with the experiment directory and run log. Numerical cross-validation against independent RTKLIB/gLAB or SP3 precise orbits has not been completed, and complete decodable LNAV has not been automatically generated from real RINEX. Successful real NAV processing is not independent accuracy validation of the orbit algorithm.

## 13. Suggested physical verification order

1. Direct baseline without noise, atmosphere or clock bias: check propagation and position/velocity solution.
2. Common range/frequency offset: check its relationship to receiver clock bias/drift; do not assume all positions shift by the same amount.
3. Linear range compensation: check `D_comp=-q'/lambda` and convergence under different difference steps.
4. Reflection geometry: check that paths are no shorter than LOS, intersections lie on finite walls, and degenerate reflections are invalid.
5. Identical configuration/seed: check observation reproducibility and unchanged I/Q waveform bytes across chunk sizes.
6. Actual software receiver and real ephemerides: independently check acquisition/tracking, messages and observations. This is future validation and must not be replaced by the first five checks.

## 14. Official and original references

- [IS-GPS-200N: GPS Space Segment/Navigation User Interfaces](https://www.navcen.uscg.gov/sites/default/files/pdf/gps/IS-GPS-200N.pdf): L1 C/A code structure, navigation messages and broadcast-ephemeris user algorithms.
- [ESA Navipedia: Satellite Coordinates Computation](https://gssc.esa.int/navipedia/index.php/Satellite_Coordinates_Computation): transmission/reception ECEF and Earth rotation.
- [ESA Navipedia: GPS and Galileo Satellite Coordinates Computation](https://gssc.esa.int/navipedia/index.php/GPS_and_Galileo_Satellite_Coordinates_Computation): broadcast orbit parameters, week boundaries and validity.
- [ESA Navipedia: GNSS Basic Observables](https://gssc.esa.int/navipedia/index.php/GNSS_Basic_Observables): pseudorange, carrier, Doppler and ionospheric signs.
- [ESA Navipedia: Combining Pairs of Signals and Clock Definition](https://gssc.esa.int/navipedia/index.php/Combining_pairs_of_signals_and_clock_definition): clock definitions and code hardware biases.
- [ESA Navipedia: Data Demodulation and Processing](https://gssc.esa.int/navipedia/index.php/Data_Demodulation_and_Processing): code delay, navigation time and pseudorange generation.
- [GNSS-SDR: My First Position Fix](https://gnss-sdr.org/my-first-fix/): real sample files and software-receiver processing; this does not mean the project has completed that validation.
- [Xu et al., 2015 original paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC4481917/): research background on separating real signals, adding geometric delays and resynthesizing them. This program does not claim to reproduce their original recordings or point-by-point results.
