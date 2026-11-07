# 室内 GPS 信号转发仿真

[中文](#室内-gps-信号转发仿真) | [English](#english-translation-indoor-gps-signal-relay-simulation)

本项目提供观测值级室内转发仿真和 GPS L1 C/A 复数基带 I/Q 波形生成，帮助研究：当接收机仍按真实卫星坐标解算时，室内转发如何影响位置和速度。仿真生成的数据均为合成研究数据；用户导入的数据来源由用户自行确认。

应用可以生成未补偿的伪距和多普勒观测，也可以读取用户在外部补偿后的观测，计算位置和速度。图形界面支持中文和英文，包含二维与三维定位选项。

当前版本支持：WGS84/ECEF/ENU、动态圆轨道或 GPS RINEX 2/3 广播星历、发射时刻迭代、地球自转、卫星钟差与 TGD、大气简化模型、室内链路和相干单次反射、用户轨迹、连续接收机时钟、补偿约束、相关观测噪声、参考最小二乘、C/A I/Q、可复现运行记录。

## 重要适用范围

- 默认圆轨道是合成卫星，不是某日真实星座；使用 `satellites.source=rinex` 及本地 NAV 文件可换成真实广播星历。
- 观测 CSV 是 LOS 传播真值加统计误差模型，不是由 I/Q 解码得到。反射路径进入 I/Q；其最终测量偏差需要具体接收机处理，代码不伪造该结果。
- 默认 I/Q 的导航符号恒为 +1，仅用于 C/A 捕获、码/载波跟踪研究，不含合法 LNAV，不能独立冷启动定位。可导入外部 50 bit/s 数据，但未校验其奇偶校验、星历与时间一致性。
- 已进行本地数值和捕获检查，尚未完成 GNSS-SDR 全链路定位验证，RINEX 传播也未与独立真实精密轨道交叉核验。
- 无室内家具遮挡、绕射、穿透、天线方向图、真实前端滤波或完整硬件模型。I/Q 是理想矩形码脉冲带限采样近似。
- 当前版本是数据生成与基线分析工具，没有自动布局/映射优化器，不保证达到课件指标。

## 运行

### 安装依赖与启动

需要 Python 3.10 或更高版本、NumPy 和 Tkinter。Windows 用户可在项目根目录打开 PowerShell，创建虚拟环境并安装本项目：

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
```

请使用包含 Tkinter 的 Python 安装包。安装完成后，双击项目根目录的 **`Start-Simulator.cmd`** 打开控制窗口。也可在已安装依赖的 Python 环境中运行 `python app.py`；命令行工具可在其他支持该依赖的系统中使用。

- 应用包含八组输入：场景与轨迹、卫星与传播、室内发射点、上传/导入数据、时钟与大气、噪声与多径、定位解算、I/Q 信号。原“补偿”参数页已移除，应用不再施加内置补偿。
- 点击窗口右上角的 **English / 中文** 按钮可切换界面语言；切换保留当前输入和任务状态。
- 初次打开或恢复默认时不勾选“计算 Z 方向（三维定位）”，固定高度 1 m；勾选后切为三维。加载已有配置时保留该配置的定位维度与高度。
- 可调整 1–4 个发射点及其全部参数，逐星映射支持 JSON 对象输入。新增点先预填房间中心附近的坐标，必须自行核对间距、映射和坐标。
- “上传/导入数据”可留空：留空生成未补偿观测；选择已经补偿好的 CSV 后，直接使用其完整伪距和多普勒计算位置、速度。必要列为 `time_s,prn,pseudorange_m,doppler_hz`，可选 `valid`。页面可保存空白模板。导入只在本机读取，不发送到网络。
- 导入时跳过合成观测、噪声添加、内置补偿和 I/Q 生成；保留输入原文件副本、来源哈希与解算结果。默认不报告真值误差；只有明确来自当前仿真场景时，才勾选“与配置中的仿真轨迹对比”。详细格式见 [已补偿观测导入说明](docs/OBSERVATION_IMPORT.md)。
- “检查参数”会核对参数约束、星历输入和开始时可见卫星；“另存配置”保存完整 JSON，已有文件不会覆盖。输入文件路径会保存为绝对路径，换目录保存后仍指向同一输入。
- 点击“生成仿真数据”，当次参数自动保存到 `configs/user/run_*.json`，后台生成数据；每次新建 `experiments/run_gui_2d_*` 或 `experiments/run_gui_3d_*`。界面提供运行进度、误差摘要、停止和打开结果目录。运行时继续修改表单不影响已启动任务。

界面由 Python/Tk 运行，`gui.ps1` 会优先使用项目的 `.venv` 环境，并尝试其他可用的 Python；如启动报错，可运行 `powershell -NoProfile -ExecutionPolicy Bypass -File gui.ps1 -Console` 查看信息。更多使用方法见 [应用参数输入说明](docs/APP_GUIDE.md)。

二维模式的 `receiver_solution.csv` 不包含 `estimated_z_m` / `estimated_vz_mps`，其主误差统计也只用 x、y。原始轨迹与信号传播仍保留物理高度，避免错误地把天线与接收机投影到同一平面；固定高度不准确仍可能影响水平定位。两种模式都保存独立的水平误差字段，比较二维与三维时应对齐同名水平指标。

以下 PowerShell 命令使用 `run.ps1`，它会优先寻找项目的 `.venv`；确保所选 Python 环境已安装 NumPy。

```powershell
# 在项目根目录执行；每次输出目录必须是新目录。
.\run.ps1 -Output experiments\my_run
.\run.ps1 -NoIQ -Output experiments\observations_only
.\run.ps1 -Test

# 显式选择定位维度；固定高度单位 m，0 也是有效值。
.\run.ps1 -PositionMode 2D -HeightM 1
.\run.ps1 -PositionMode 3D
```

其他 Python 环境：

```powershell
python -m pip install numpy
python simulate.py --config configs/default.json --output experiments/demo_new
python simulate.py --config configs/direct_baseline.json --output experiments/direct_new
python simulate.py --config configs/multipath.json --output experiments/multipath_new
python simulate.py --config configs/default.json --validate-only
python simulate.py --config configs/default.json --position-mode 2d --height-m 1 --output experiments/xy_new
```

不需要安装软件包即可运行；也可以 `python -m pip install -e .` 后用 `indoor-gnss` 命令。外部输入路径按配置文件所在目录解析。

## 参数与示例

- `configs/default.json`：所有参数展开，30×10×5m 厂房、两发射点、80km/h、2s 仿真、每0.01s及每1m的轨迹点、50ms 动态 I/Q。
- `configs/xy_only.json`：默认场景的二维定位版本，固定 ENU 高度 1 m。
- `configs/direct_baseline.json`：无噪声直接接收基线，检验解算正确性。
- `configs/multipath.json`：六面墙的一次镜面反射，共同 PRN 的路径在 I/Q 中相干叠加。
- `configs/coupled_compensation.json`：距离与频移遵循同一时延的耦合补偿示例。
- `configs/rinex_template.json`：真实 GPS 广播星历输入模板，需自行提供合法本地文件。
- [参数逐项说明](docs/PARAMETERS.md)、[物理模型和局限](docs/PHYSICS.md)、[输出字段](docs/DATA_FORMAT.md)。

缺省会有0.2s静止准备段，随后按80km/h沿30m直线运动。默认0s加减速时间表示匀速测量段与两端静止段拼接，端点存在速度跃变；如研究启动/制动，设正的加减速时间并相应加长路径/降低速度，必须满足 `speed_mps*acceleration_time_s <= path_length`。速度、轨迹和接收机初始化均独立配置；解算器不读取真实用户位置或虚拟卫星坐标来修正位置。

## 项目结构

| 路径 | 内容 |
|---|---|
| `src/indoor_gnss/` | 仿真模型、求解器与图形界面 |
| `configs/` | 默认配置和对照实验配置 |
| `docs/` | 参数、物理模型、数据格式和使用说明 |
| `scripts/` | I/Q 检查、示例数据获取等工具 |
| `tests/` | 自动化测试 |
| `experiments/` | 本地生成的实验结果，每次运行使用新目录 |

## 输出

每次运行保存轨迹真值、伪距/多普勒观测、传播路径数组、解算与指标、完整配置、源代码/输入校验值、软件环境和命令；可选保存 I/Q 与二进制元信息。默认拒绝覆盖。具体字段及单位见 `docs/DATA_FORMAT.md`。

```powershell
# I/Q 捕获诊断（仅相关峰检查，不是完整接收机）
python scripts/inspect_iq.py experiments/my_run
```

指标默认位置归一化尺度30m、速度归一化尺度80/3.6 m/s，只是研究约定，并未替甲方确定百分比验收口径。误差仅统计数值收敛的历元，同时报告收敛比例；数值收敛不代表物理可观测，也不代表定位准确。

## 继续研究

先比较直达基线与无补偿转发，再固定星历/轨迹对照1–4个发射点与补偿。优化时不得利用测试点实时真值；逐点真值补偿只可作为理想参考。接入真实星历和真实接收机后，再校准测量噪声、多径与硬件参数。

数据来源与公式依据：GPS IS-GPS-200N、ESA/Navipedia、Xu 等 2015 年论文。详细链接及建模边界见 [物理模型和局限](docs/PHYSICS.md)。

## 已生成示例与真实星历

仓库不附带仿真运行结果。可运行 `.\run.ps1 -Output experiments/ready_example` 生成一套新示例；如果该目录已存在，请选择其他新目录。历史验证记录见 `docs/VALIDATION.md`。

`configs/smooth_motion.json` 是较低速度、非零加减速段的示例，用于避免把瞬时起停的差分误差解释为接收机性能。

可执行 `python scripts/fetch_example_nav.py` 获取公开广播星历样本。脚本校验固定 SHA-256，保留已有不同内容的文件。样本来自公开 gps-sdr-sim 仓库，表示 2022 年 1 月 1 日的卫星广播信息，不是室内观测；曾使用该样本完成 8 星链路检查。

---

# English translation: Indoor GPS Signal Relay Simulation

[中文](#室内-gps-信号转发仿真) | [English](#english-translation-indoor-gps-signal-relay-simulation)

This project provides observation-level indoor relay simulation and GPS L1 C/A complex-baseband I/Q generation. It supports research into position and velocity errors when a receiver still solves using real satellite coordinates. Simulated outputs are synthetic research data; the provenance of imported data must be established by the user.

The application generates uncompensated pseudorange and Doppler observations or reads externally compensated observations to calculate position and velocity. Its Chinese/English graphical interface supports both 2D and 3D solutions.

The current version supports WGS84/ECEF/ENU; dynamic circular orbits or GPS RINEX 2/3 broadcast ephemerides; transmit-time iteration; Earth rotation; satellite clock and TGD; simplified atmosphere; indoor links and coherent single reflections; user trajectories; a continuous receiver clock; compensation constraints; correlated observation noise; reference least squares; C/A I/Q; and reproducible run records.

## Important scope and limitations

- Default circular-orbit satellites are synthetic, not a real constellation for a particular day. Use `satellites.source=rinex` and a local NAV file for real broadcast ephemerides.
- Observation CSVs contain LOS propagation truth plus a statistical error model; they are not decoded from I/Q. Reflection paths enter I/Q, but their final measurement bias depends on receiver processing and is not fabricated by the code.
- Default I/Q navigation symbols are constantly +1 for C/A acquisition and code/carrier tracking research only. They contain no valid LNAV and cannot independently produce a cold-start fix. External 50 bit/s data can be imported, but parity, ephemeris and time consistency are not validated.
- Local numerical and acquisition checks have been performed; a complete GNSS-SDR positioning chain and independent precise-orbit cross-check of RINEX propagation have not yet been validated.
- Indoor furniture blockage, diffraction, penetration, antenna patterns, actual front-end filtering and complete hardware models are absent. I/Q approximates band-limited sampling of ideal rectangular code pulses.
- The current version generates data and baseline analyses, has no automatic layout/mapping optimizer and does not guarantee the lecture-material targets.

## Running

### Install dependencies and launch

Python 3.10 or newer, NumPy and Tkinter are required. On Windows, open PowerShell in the project root, create a virtual environment and install the project:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
```

Use a Python installation that includes Tkinter. Then double-click **`Start-Simulator.cmd`** in the project root. Alternatively, run `python app.py` in a Python environment with the dependencies installed; the command-line tools can be used on other systems that support those dependencies.

- The application has eight input groups: scene and trajectory, satellites and propagation, indoor transmitters, upload/import data, clock and atmosphere, noise and multipath, position solution, and I/Q signal. The former compensation page has been removed and the application no longer applies built-in compensation.
- Use the **English / 中文** button at the upper right to switch languages while preserving the current inputs and task state.
- On first launch or restoring defaults, “Solve Z (3D positioning)” is unchecked and height is fixed at 1 m; check it for 3D. Loading an existing configuration preserves its dimension and height.
- Configure 1–4 transmitters and all parameters; per-satellite mapping accepts a JSON object. Newly added points have initial coordinates near the room center. Verify spacing, mapping and coordinates yourself.
- “Import observations” is optional: an empty selection generates uncompensated observations. When a corrected CSV is selected, its full pseudorange and Doppler values are used directly to calculate position and velocity. Required columns: `time_s,prn,pseudorange_m,doppler_hz`; optional: `valid`. A blank template can be saved from the page. Import reads locally and does not transmit data.
- Import skips synthetic observations, noise addition, built-in compensation and I/Q generation; it preserves an input copy, provenance hash and solution. Truth errors are not reported by default. Select “Compare configured trajectory” only when data are known to come from the same simulation scene. See [corrected-observation import](docs/OBSERVATION_IMPORT.md).
- “Check parameters” verifies constraints, ephemeris input and satellites visible at the start. “Save configuration” saves complete JSON without overwriting existing files. Input paths are saved as absolute paths, preserving their targets when the configuration is saved elsewhere.
- Click “Generate simulation data” to save current parameters to `configs/user/run_*.json` and run in the background. Every run creates a new `experiments/run_gui_2d_*` or `experiments/run_gui_3d_*` directory. The interface provides progress, error summary, stop and open-results controls. Editing the form during execution does not change the started task.

The interface runs in Python/Tk. `gui.ps1` prefers the project's `.venv` and tries other available Python environments. If startup fails, run `powershell -NoProfile -ExecutionPolicy Bypass -File gui.ps1 -Console`. See the [application parameter guide](docs/APP_GUIDE.md).

In 2D mode, `receiver_solution.csv` omits `estimated_z_m` / `estimated_vz_mps`, and its primary error statistics use x and y only. The original trajectory and signal propagation retain physical height, avoiding incorrect projection of antenna and receiver onto one plane; an incorrect fixed height may still affect horizontal positioning. Both modes save separate horizontal-error fields. Compare matching horizontal metrics for 2D and 3D.

The PowerShell commands below use `run.ps1`, which prefers the project's `.venv`; make sure NumPy is installed in the selected Python environment.

```powershell
# Run from the project root; every output directory must be new.
.\run.ps1 -Output experiments\my_run
.\run.ps1 -NoIQ -Output experiments\observations_only
.\run.ps1 -Test

# Select solution dimensions explicitly; fixed height is in m, and 0 is valid.
.\run.ps1 -PositionMode 2D -HeightM 1
.\run.ps1 -PositionMode 3D
```

Other Python environments:

```powershell
python -m pip install numpy
python simulate.py --config configs/default.json --output experiments/demo_new
python simulate.py --config configs/direct_baseline.json --output experiments/direct_new
python simulate.py --config configs/multipath.json --output experiments/multipath_new
python simulate.py --config configs/default.json --validate-only
python simulate.py --config configs/default.json --position-mode 2d --height-m 1 --output experiments/xy_new
```

The package need not be installed; alternatively run `python -m pip install -e .` and use `indoor-gnss`. External input paths are resolved relative to the configuration file.

## Parameters and examples

- `configs/default.json`: all parameters expanded; 30×10×5 m factory, two transmitters, 80 km/h, 2 s simulation, trajectory points every 0.01 s and 1 m, 50 ms dynamic I/Q.
- `configs/xy_only.json`: 2D positioning version of the default scene, fixed ENU height 1 m.
- `configs/direct_baseline.json`: noise-free direct-reception baseline for checking the solution.
- `configs/multipath.json`: one specular reflection from each of six surfaces; paths sharing a PRN are coherently summed in I/Q.
- `configs/coupled_compensation.json`: example of distance and frequency compensation coupled by a common delay.
- `configs/rinex_template.json`: real GPS broadcast-ephemeris input template; provide a valid local file.
- [Parameter reference](docs/PARAMETERS.md), [physical models and limitations](docs/PHYSICS.md), [output fields](docs/DATA_FORMAT.md).

By default there is a 0.2 s stationary preparation segment followed by 30 m of straight motion at 80 km/h. The default 0 s acceleration time joins uniform measurement motion to stationary segments at either end, producing velocity jumps. To study starting/braking, set a positive acceleration time and lengthen the path or lower the speed; `speed_mps*acceleration_time_s <= path_length` must hold. Speed, trajectory and receiver initialization are configured independently; the solver does not read true user position or virtual-satellite coordinates to correct its position.

## Project structure

| Path | Contents |
|---|---|
| `src/indoor_gnss/` | Simulation models, solver and graphical interface |
| `configs/` | Default and comparison configurations |
| `docs/` | Parameter, physical model, data format and usage guides |
| `scripts/` | I/Q diagnostics, example-data retrieval and other tools |
| `tests/` | Automated tests |
| `experiments/` | Locally generated results; each run uses a new directory |

## Output

Each run saves trajectory truth, pseudorange/Doppler observations, propagation-path arrays, solution and metrics, complete configuration, source/input checksums, software environment and command. I/Q and binary metadata are optional. Existing outputs are not overwritten by default. See `docs/DATA_FORMAT.md` for fields and units.

```powershell
# I/Q acquisition diagnostic (correlation peak only; not a complete receiver)
python scripts/inspect_iq.py experiments/my_run
```

The default normalization scales are 30 m for position and 80/3.6 m/s for speed. These are research conventions and do not establish the client's percentage acceptance criteria. Errors are calculated only for numerically converged epochs, together with the convergence fraction. Numerical convergence does not imply physical observability or accurate positioning.

## Further research

First compare the direct baseline with uncompensated relay, then fix ephemeris and trajectory while comparing 1–4 transmitters and compensation. Optimization must not use real-time truth at test points; pointwise truth compensation is an ideal reference only. Calibrate measurement noise, multipath and hardware parameters after integrating real ephemerides and a real receiver.

Data and formula sources include GPS IS-GPS-200N, ESA/Navipedia and Xu et al. (2015). See [physical models and limitations](docs/PHYSICS.md) for links and modeling boundaries.

## Generated example and real ephemeris

Simulation runs are not included in the repository. Run `.\run.ps1 -Output experiments/ready_example` to generate a new example; choose a different new directory if that directory already exists. Historical validation records are in `docs/VALIDATION.md`.

`configs/smooth_motion.json` is a lower-speed example with nonzero acceleration/deceleration, to avoid misinterpreting finite-difference errors from instantaneous start/stop as receiver performance.

Run `python scripts/fetch_example_nav.py` to obtain a public broadcast-ephemeris sample. The script checks a fixed SHA-256 and preserves existing files with different content. The sample comes from the public gps-sdr-sim repository and contains satellite broadcast information for January 1, 2022, not indoor observations. An eight-satellite link check was previously performed with this sample.
