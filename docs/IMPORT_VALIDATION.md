# 已补偿数据导入验证（2026-11-06）

74 项单元与集成检查通过，无跳过。执行命令：`run.ps1 -Test`，覆盖原有物理/星历/IQ、导入格式与数值校验、缺失观测不补齐、源文件不改写、无参考解算、可选配置轨迹参考及界面空路径/移除补偿参数/旧参数归零。

正常桌面运行环境为 Python 3.12.14、NumPy 2.3.5、Tk 8.6。受限执行环境的 Tcl 读取曾造成窗口测试跳过，正常桌面环境复跑后窗口测试全部通过；未为此修改依赖目录。

实际控件到后台进程的验证命令：

```powershell
& 'python' -B scripts/check_import_app.py
```

该脚本创建隐藏 Tk 测试窗口，通过实际字段和生成/解算按钮执行三个独立任务，不向其他应用注入鼠标键盘。

| 情况 | 结果目录 | 观测数 / 有效解 |
|---|---|---|
| 文件留空，生成无噪声直达仿真样例 | experiments/run_gui_2d_20261106_195832_953433_1d9d77 | 1728 条 / 216 个时刻 |
| 将上述完整观测作为外部导入样例，二维、不启用参考 | experiments/run_gui_2d_20261106_195837_205663_50487e | 1728 条 / 216 个时刻 |
| 同一文件三维导入，启用同配置轨迹参考 | experiments/run_gui_3d_20261106_195840_777959_030c5c | 1728 条 / 216 个时刻 |

验证输入来源为合成的无噪声直达样例，只用于检查数据导入链路，不代表已经验证用户的补偿算法或真实设备效果。

已核对：界面中无补偿字段；文件选择可清空；导入时 IQ 设置停用；即使保留 IQ 开关或将观测噪声开关打开，导入行仍按原值解算且不生成 IQ/通道；全部导入伪距、多普勒与原文件数值一致，原文件 SHA-256 不变。无参考二维结果不输出虚构误差；三维可选参考明确为配置仿真轨迹。

第一个结果目录的 `import_app_check.json` 保存命令、样例来源、源文件哈希和三套结果路径；各套结果另含配置快照、环境和代码/输入哈希。所有输出为新目录，原有研究结果保留。

尚未收到用户实际补偿后的观测文件。实际使用时，仍须匹配数据的 GPS 时间起点、星历、PRN 和观测定义；本次未新增自动补偿算法。


---

## English translation

# Corrected Observation Import Validation (2026-11-06)

All 74 unit and integration checks passed without skips. Command: `run.ps1 -Test`. They covered existing physics, ephemeris and I/Q tests, import format and numerical validation, no filling of missing observations, no modification of the source file, solutions without a reference, the optional configured trajectory as reference, an empty UI path, removal of compensation parameters from the interface and zeroing of legacy parameters.

The normal desktop environment was Python 3.12.14, NumPy 2.3.5 and Tk 8.6. Tcl access in a restricted execution environment had caused the window tests to be skipped; all window tests passed when rerun in the normal desktop environment. The dependency directory was not modified for this.

Command for checking actual controls through to the background process:

```powershell
& 'python' -B scripts/check_import_app.py
```

The script creates a hidden Tk test window and performs three independent tasks using the actual fields and generate/solve button; it does not inject mouse or keyboard events into other applications.

| Case | Result directory | Observations / valid solutions |
|---|---|---|
| Empty file selection; generate a noiseless direct-path synthetic example | `experiments/run_gui_2d_20261106_195832_953433_1d9d77` | 1,728 / 216 epochs |
| Import the complete observations above as an external example, in 2D without a reference | `experiments/run_gui_2d_20261106_195837_205663_50487e` | 1,728 / 216 epochs |
| Import the same file in 3D with the same-configuration trajectory reference enabled | `experiments/run_gui_3d_20261106_195840_777959_030c5c` | 1,728 / 216 epochs |

The input was a synthetic noiseless direct-path example used only to check the data-import pipeline; this does not validate the user's compensation algorithm or real-device performance.

Checks confirmed that the interface contains no compensation fields; file selection can be cleared; I/Q settings are disabled during import; even if the I/Q preference is retained or observation noise is enabled, imported rows are solved using the original values and no I/Q or channel data is generated. All imported pseudorange and Doppler values match the source, and its SHA-256 is unchanged. The 2D result without reference does not output fabricated errors; the optional 3D reference is explicitly the configured simulation trajectory.

`import_app_check.json` in the first result directory records the command, example provenance, source hash and all three result paths. Each run also contained a configuration snapshot, environment details and code/input hashes. All outputs were created in new directories and existing research results were preserved.

No actual user-compensated observation file had been received. Actual use still requires matching GPS time origin, ephemeris, PRNs and observation definitions. No automatic compensation algorithm was added.
