# 参数应用使用说明

双击项目根目录 `Start-Simulator.cmd` 打开“室内定位仿真 · 参数控制台”。所有输入、配置和结果均在本机处理。生成数据均为合成研究数据。

## 中英文切换

点击界面顶部的语言切换按钮，可在中文和英文之间切换。切换语言不需要先保存或检查参数，当前输入会保留。

## 参数分组

| 页面 | 可以设置的内容 |
|---|---|
| 场景与轨迹 | 随机种子、GPST 时间、仿真时长、时间/距离采样间隔、场地经纬度、房间尺寸、室外天线坐标、运动起终点、中间路径点、速度和加减速时间 |
| 卫星与传播 | 合成/RINEX 星历、星历文件、卫星数量与 PRN、仰角、合成轨道参数、直达/转发、地球自转和传播求解参数 |
| 室内发射点 | 1–4 个点，逐点编号、坐标、线缆、处理延迟、路径损耗、相位及独立时钟；PRN 映射、转发架构、点间距约束 |
| 上传 / 导入数据 | 可留空的已补偿观测 CSV；清空文件、保存空白模板、可选配置轨迹对比 |
| 时钟与大气 | 接收机钟差/钟漂、随机频率过程、气象、TEC 和大气映射 |
| 噪声与多径 | 伪距/多普勒统计噪声、相关性、信噪比、丢失与门限、墙面反射 |
| 定位解算 | 开关、初始位置、迭代和收敛设置、大气改正、指标归一化 |
| I/Q 信号 | 生成开关、采样率、窗口、中频、格式、分块、量化、导航符号、AWGN 和资源限制 |

顶部控制二维/三维及二维固定高度。关闭 Z 解算时，高度仍用于三维传播，只是不作为待求未知量。加载配置保留其维度；初次打开和“恢复默认参数”采用二维、高度 1 m。

坐标输入按 x 东、y 北、z 上排列。速度单位 m/s，80 km/h 约为 22.2222 m/s；时间单位以字段说明为准。科学计数法可直接填写，如 1e-5；整数参数须填整数。卫星列表和反射墙列表使用 JSON 数组，例如 `[3, 16, 4, 10]`。

在“中间路径点（m）”中按经过顺序填写坐标列表，例如 `[[9, 2, 1], [9, 7, 1]]`。接收机从起点依次经过这些点，再到终点。所有点必须在房间内，相邻点不能重合。`[]` 表示直线。也可加载 `configs/polyline.json` 试用示例。

逐颗卫星映射示例：`{"3":"V1","16":"V2"}`；空对象使用默认分配。PRN 键须为字符串 `"1"` 到 `"32"`，不能写 G03 或 03。原补偿控制页已移除，应用中不再输入补偿量；你们在外部完成补偿后，导入完整伪距与多普勒。详见 [导入格式](OBSERVATION_IMPORT.md)。

## 使用步骤

1. 初次可直接使用默认参数，也可“加载配置”读取已有完整或部分 JSON；部分配置按程序默认值补齐。
2. 在分组中修改参数。搜索会筛选匹配项，并切换到有匹配项的页面；清空搜索恢复全部字段。减少发射点或替换未保存输入时，界面会提醒。
3. 点击“检查参数”。检查格式、物理约束和开始时卫星可用性；失败显示原因，能识别字段名时切换到对应输入。该检查不代表定位指标达标。
4. 可“另存配置”供以后复用。仅允许新文件名；不会覆盖默认配置或已有研究配置。所填外部文件路径按加载配置所在目录解析，保存时转成绝对路径。
5. 导入页留空时点击“生成仿真数据”，得到未补偿基线；选择文件后按钮改为“计算位置和速度”，直接解算导入观测。运行使用当时的不可变参数快照；后台运行时继续编辑输入不会改变当前任务。每次自动创建新输入快照和新结果目录。
6. 完成后查看统计摘要，点击“打开结果文件夹”。“停止”会中断计算并保留部分输出和日志，未完成数据集不能作为成功结果使用。

## 参数相互依赖

- 降低运动速度或增加加减速时间后，通常需要增加总时长，让整段运动完整落在仿真窗口内。软件不会自动修改你的实验条件。
- 起终点、接收机固定高度和发射点须满足房间范围。发射点间距离须严格大于下限、严格小于上限；新增点的初始坐标仅供编辑，不能当作已优化布局。
- 合成/RINEX 和 I/Q 开关会启用或停用相关文件输入；停用的输入路径保留在表单和配置中，但不会作为本次有效外部输入读取或计算校验值。
- 透明转发不允许独立发射点时钟误差。导入数据时须保持原星历、时间起点、PRN 和观测含义一致。
- I/Q 的采样率、时长、中频和资源上限相互关联，波形窗口须在总时长内。默认 I/Q 不含合法完整导航电文。
- 减少发射点后，需检查逐颗卫星映射是否还引用已移除编号。加载旧配置时，原补偿控制会归零，避免出现界面看不到的内置补偿。

## 保存与追溯

- 手动配置：用户选择的新 JSON 文件名。
- 每次运行配置：`configs/user/run_<时间与随机后缀>.json`。
- 运行结果：`experiments/run_gui_2d_<时间与随机后缀>` 或 `run_gui_3d_...`。
- 日志：`experiments/temp/gui`；结果目录另含最终配置、随机种子、命令、环境和代码/输入哈希。

界面只改变参数输入和运行方式，未改变传播物理公式或加入自动补偿优化器。二维和三维比较应使用相同水平指标，不能把维度不同的主误差直接当作算法优劣结论。

导入时 I/Q 设置停用，仅根据已有观测计算位置速度。默认不比较真值；只有明确来自同一配置仿真场景时才启用配置轨迹对比。导入的原值、文件副本、来源哈希和处理数量会保存，上传一词仅表示本地文件选择，不涉及网络传输。

---

# English translation: Application Parameter Guide

Double-click `Start-Simulator.cmd` in the project root to open the Indoor Positioning Simulation parameter console. All inputs, configurations and results are processed locally. Generated data are synthetic research data.

## Switching between Chinese and English

Click the language button at the top of the interface to switch between Chinese and English. Switching does not require saving or checking parameters first; current inputs are retained.

## Parameter groups

| Page | Available settings |
|---|---|
| Scene & trajectory | Random seed; GPST time; duration; time/distance sampling intervals; site latitude/longitude; room size; outdoor antenna coordinates; trajectory start, intermediate waypoints and end; speed; acceleration and braking time |
| Satellites & propagation | Synthetic/RINEX ephemerides and file; satellite count and PRNs; elevation; synthetic orbital parameters; direct/relay mode; Earth rotation and propagation-solution parameters |
| Indoor transmitters | 1–4 points, each with ID, coordinates, cable, processing delay, path loss, phase and independent clock; PRN mapping, relay architecture and spacing constraints |
| Import observations | Optional corrected-observation CSV; clear file selection; save empty template; optional comparison to configured trajectory |
| Clock & atmosphere | Receiver clock bias/drift, stochastic frequency process, weather, TEC and atmospheric mapping |
| Noise & multipath | Statistical pseudorange/Doppler noise, correlation, signal-to-noise ratio, dropout and thresholds, wall reflections |
| Position solution | Enable, initial position, iteration and convergence settings, atmospheric correction and metric normalization |
| I/Q signal | Enable, sample rate, window, intermediate frequency, format, chunking, quantization, navigation symbols, AWGN and resource limits |

The controls at the top set 2D/3D and fixed height for 2D. When Z is not solved, height is still used in 3D propagation but is not an unknown in the solution. Loading a configuration preserves its dimension; on first launch or when restoring defaults the application uses 2D at 1 m height.

Coordinate inputs are x east, y north, z up. Speed is in m/s; 80 km/h is approximately 22.2222 m/s. See each field for time units. Scientific notation such as 1e-5 is accepted; integer parameters require integers. Satellite and reflecting-wall lists use JSON arrays, for example `[3, 16, 4, 10]`.

Enter intermediate waypoints as a list of coordinates in visit order, for example `[[9, 2, 1], [9, 7, 1]]`. The receiver visits them in order between the start and end. All points must be inside the room, and adjacent points must differ. The empty list `[]` gives a straight path. Load `configs/polyline.json` to try the example.

Example per-satellite mapping: `{"3":"V1","16":"V2"}`. An empty object uses default assignment. PRN keys must be strings `"1"` through `"32"`, not G03 or 03. The old compensation page has been removed: compensation values are no longer entered in the app. After compensation externally, import full pseudorange and Doppler values. See the [import format](OBSERVATION_IMPORT.md).

## Steps

1. Use defaults initially, or select “Load configuration” to read full or partial JSON; missing values in a partial file are filled from the application defaults.
2. Edit parameters in their groups. Search filters matching fields and switches to a page containing matches; clear search to restore all fields. The interface warns when reducing transmitters or replacing unsaved inputs.
3. Click “Check parameters” to check format, physical constraints and satellite availability at the start. Failures show the reason and, if the field can be identified, navigate to it. Passing this check does not imply positioning targets have been met.
4. Optionally use “Save configuration” for later reuse. Only a new filename is permitted; default and existing research configurations are not overwritten. External file paths are resolved relative to the loaded configuration and saved as absolute paths.
5. With no imported file, click “Generate simulation data” for an uncompensated baseline. After selecting a file, the button changes to “Calculate position and velocity” and solves the imported observations directly. Each run uses an immutable snapshot; editing the form while it runs does not change that task. A new input snapshot and results directory are created automatically each time.
6. Review the statistical summary and click “Open results folder.” “Stop” interrupts computation while retaining partial outputs and logs; an incomplete data set must not be treated as a successful result.

## Parameter dependencies

- Reducing speed or increasing acceleration/braking time normally requires a longer overall duration so that the whole motion fits in the simulation window. The software does not change your experimental conditions automatically.
- Start/end points, receiver fixed height and transmitter positions must lie within room limits. Transmitter spacing must be strictly greater than the minimum and strictly less than the maximum. New point coordinates are editable placeholders, not an optimized layout.
- Synthetic/RINEX and I/Q switches enable or disable associated file inputs. Disabled paths remain in the form and configuration but are not read or hashed as active external inputs for the run.
- Transparent relay does not permit independent transmitter clock errors. Imported data must retain the original ephemeris, time origin, PRNs and observation meanings.
- I/Q sample rate, duration, intermediate frequency and resource limits are related; the waveform window must fit within the overall duration. Default I/Q has no valid complete navigation message.
- After reducing the transmitter count, check that per-satellite mapping does not refer to removed IDs. Loading an old configuration zeros old compensation controls to avoid hidden built-in compensation.

## Saving and traceability

- Manual configuration: a new JSON filename chosen by the user.
- Per-run configuration: `configs/user/run_<time and random suffix>.json`.
- Run results: `experiments/run_gui_2d_<time and random suffix>` or `run_gui_3d_...`.
- Logs: `experiments/temp/gui`. The results directory also contains final configuration, random seed, command, environment and code/input hashes.

The interface changes parameter entry and execution only; it does not change propagation physics or add an automatic compensation optimizer. Compare 2D and 3D using the same horizontal metrics; primary errors of different dimensions cannot directly establish algorithm superiority.

During import, I/Q settings are disabled and position/velocity are calculated solely from existing observations. Ground truth is not compared by default; enable configured-trajectory comparison only when the data are known to originate from the same configured simulation. Original imported values, a file copy, provenance hash and processing counts are saved. “Upload” means local file selection only and does not involve network transmission.
