# 已补偿观测导入

应用的“补偿”块已经替换为“上传 / 导入数据”。本功能读取本地 CSV；不向网络上传文件。原来距离偏移、距离斜率、正弦补偿和独立频移等界面输入全部移除。

## 两种使用方式

- 不选择文件：生成当前场景的未补偿观测，供你们在外部设计补偿算法。正常生成轨迹、观测、解算结果及可选 I/Q。
- 选择文件：读取你们已经补偿好的完整伪距、多普勒，只解算文件中实际存在的时刻和卫星。不补齐缺行、不添加随机误差、不施加内置补偿，不生成 I/Q 或合成传播通道。

应用加载旧配置时，将旧的补偿设置归零；已有研究文件保留。历史命令行物理模型接口仍保留以便复现旧实验，当前应用界面不使用这套补偿功能。

## CSV 格式

UTF-8 编码，可带 BOM。第一行为字段名，随后每行是一颗卫星在一个时刻的观测。

| 列 | 必需 | 含义 |
|---|---|---|
| time_s | 是 | 从配置的 GPS 周/周内秒起点算起的接收机相对时间，单位 s；不是 UTC 时间或 GPS 周内秒本身。须落在配置总时长内。 |
| prn | 是 | GPS PRN 整数 1–32，如 3；不写 G03、03 或 3.0。须在当前配置选用卫星中。 |
| pseudorange_m | 是 | 补偿后的完整伪距，单位 m，须为正；不是补偿量、误差或残差。 |
| doppler_hz | 是 | 补偿后的完整多普勒，单位 Hz。沿用路径增长对应负频移的符号约定。 |
| valid | 否 | true/false 或 1/0；缺少整列时按有效处理。标为无效的观测不参与拟合。 |

其余列允许保留并忽略，因此可以直接编辑或处理旧 `observations.csv`，再导入处理后的文件。文件中附带的真实位置、噪声、补偿分量等列不会作为解算依据。相同 `(time_s, prn)` 不能重复，数值须有限，不接受 NaN 或无穷大。限制为 100 MiB、200 万条观测，较大数据应分段。

导入页提供“保存空白 CSV 模板”与“清空文件选择”。空白模板只有表头，需要填写观测后才能导入；完全不选择文件则是合法状态。

## 星历、时间与误差对比

选择的星历/合成星座、起始 GPS 时间、PRN 和观测符号必须与原数据一致。建议明确填写原数据的 PRN 列表，避免自动选星与文件不匹配。接收机仍同时估计钟差和钟漂，二维模式固定高度、三维模式估计高度。大气改正开关须与原观测含义一致，避免重复扣除同一种改正。

默认只输出位置和速度，不知道外部文件的真实轨迹，因此误差列留空、误差统计为 null。只有明确来自当前同一仿真场景时，才勾选“与配置中的仿真轨迹对比”；这种对比使用配置生成的参考轨迹，不把它当作外部实测真值。

每个时刻须有足够独立的有效观测：二维位置与钟差至少需要 3 条，三维至少 4 条；还需满足几何可解条件。不足时保留失败状态，不补造观测。处理完成不等于每个时刻定位成功，界面会报告有效解数量。

## 文件与追溯

导入结果目录包含：

- `imported_observations.csv`：原文件的字节副本；原文件不会修改。
- `observations.csv`：规范化后的实际解算输入，数值不变。
- `observation_import.json`：来源、SHA-256、时刻和卫星范围、观测数量。
- `receiver_solution.csv`：位置、速度分量、速度大小、钟差/钟漂、状态和残差；不启用参考对比时真值误差为空。
- `metrics.json`：收敛比例、维度、参考来源；无参考时误差统计为 null。
- `trajectory_reference.csv`：仅在明确启用配置轨迹对比时输出。
- 配置、环境、代码与输入哈希及完成摘要。

导入时不输出 `trajectory_truth.csv`、`channel_truth.npz` 或新的 I/Q。原观测文件对应的 I/Q 不会被已补偿 CSV 自动改写。

配置字段为 `input_observations.corrected_csv`（空值 null）及 `input_observations.compare_reference`（默认 false）。相对路径以配置文件所在目录为基准，应用保存时转为绝对路径。命令行也可使用 `--corrected-observations <本地CSV路径>`。

---

# English translation: Corrected Observation Import

The application's “Compensation” block has been replaced with “Upload / Import Data”. This feature reads a local CSV; it does not upload files to a network. The former interface inputs for distance offset, range slope, sinusoidal compensation and independent frequency shifts have all been removed.

## Two usage modes

- No file selected: generate uncompensated observations for the current scene so that you can design compensation algorithms externally. Trajectory, observations, solution and optional I/Q are generated normally.
- File selected: read your already-corrected full pseudorange and Doppler, and solve only the epochs and satellites actually present. Missing rows are not filled, random errors are not added, built-in compensation is not applied, and I/Q or synthetic propagation channels are not generated.

When the application loads an old configuration, old compensation settings are zeroed; existing research files are retained. Historical command-line physics-model interfaces remain available for reproducing old experiments, but the current application interface does not use that compensation functionality.

## CSV format

Use UTF-8, optionally with BOM. The first row contains column names; each following row is an observation of one satellite at one time.

| Column | Required | Meaning |
|---|---|---|
| time_s | Yes | Receiver-relative time in seconds from the configured GPS week / seconds-of-week origin; not UTC time or GPS seconds of week itself. Must lie within the configured duration. |
| prn | Yes | GPS PRN integer 1–32, e.g. 3; do not write G03, 03 or 3.0. Must be among the satellites selected by the current configuration. |
| pseudorange_m | Yes | Full compensated pseudorange, in m, positive; not a correction, error or residual. |
| doppler_hz | Yes | Full compensated Doppler, in Hz. The convention assigns negative frequency shift to increasing path length. |
| valid | No | true/false or 1/0; if the entire column is absent, observations are treated as valid. Invalid observations are excluded from fitting. |

Additional columns may remain and are ignored, so an old `observations.csv` can be edited or processed and then imported. Included true position, noise and compensation components are not used in the solution. A `(time_s, prn)` pair must not be duplicated, and values must be finite: NaN and infinity are rejected. Limits are 100 MiB and two million observations; split larger datasets into segments.

The import page provides “Save blank CSV template” and “Clear file”. The template contains only a header and must be filled before import; selecting no file at all is valid.

## Ephemeris, time and error comparisons

The selected ephemeris/synthetic constellation, GPS start time, PRNs and observation sign convention must match the original data. Explicitly setting the original PRN list is recommended to avoid automatic satellite selection mismatching the file. The receiver still estimates clock bias and drift. In 2D height is fixed; in 3D height is estimated. The atmosphere-correction switch must match the meaning of the original observations to avoid applying the same correction twice.

By default, only position and velocity are output. The true external trajectory is unknown, so truth-error columns are blank and error statistics are null. Select “Compare configured trajectory” only if the data are known to come from the same current simulation scene. The comparison uses the trajectory generated from the configuration and does not assert that this is measured truth for external data.

Every epoch needs enough independent valid observations: at least 3 for 2D position and clock bias, or 4 for 3D, and the geometry must also be solvable. When insufficient, failure status is retained and observations are not fabricated. Completing processing does not mean every epoch yielded a position; the interface reports the number of valid solutions.

## Files and traceability

The import results directory contains:

- `imported_observations.csv`: a byte-for-byte copy of the original file; the original is not modified.
- `observations.csv`: normalized actual solver input, with values unchanged.
- `observation_import.json`: source, SHA-256, epoch and satellite ranges, and observation count.
- `receiver_solution.csv`: position, velocity components and magnitude, clock bias/drift, status and residuals; truth errors are blank when reference comparison is disabled.
- `metrics.json`: convergence fraction, dimensionality and reference source; error statistics are null without a reference.
- `trajectory_reference.csv`: output only when configured-trajectory comparison is explicitly enabled.
- Configuration, environment, code and input hashes, and completion summary.

Import does not output `trajectory_truth.csv`, `channel_truth.npz` or new I/Q. I/Q associated with the original observations is not automatically rewritten by a compensated CSV.

Configuration fields are `input_observations.corrected_csv` (null when empty) and `input_observations.compare_reference` (default false). Relative paths are based on the configuration file's directory and are converted to absolute paths when saved by the app. The command line also accepts `--corrected-observations <local CSV path>`.
