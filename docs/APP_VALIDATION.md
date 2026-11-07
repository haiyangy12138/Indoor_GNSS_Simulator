# 参数应用验证记录（2026-11-06）

环境：Windows、Python 3.12.14、NumPy 2.3.5、Tk 8.6。

已通过 gui.ps1 实际启动 Python/Tk 参数窗口，检查八组参数布局、二维/三维开关、单位和说明。61 项自动检查全部通过，包括原有物理、星历、I/Q、二维/三维检查，以及新参数解析、默认往返、控件编辑、配置另存、相对输入路径保持、禁止覆盖和仅读取启用的外部文件。

完整检查命令：run.ps1 -Test。

控件到文件生成检查命令：
python -B scripts/check_app.py

该检查创建隐藏 Tk 窗口，修改真实输入控件并调用同一个“生成仿真数据”按钮，经过实际参数快照、子进程与 CLI，未通过桌面注入鼠标键盘。将种子设为 20261106、总时长设为 2.2 s，其他物理条件相同，分别执行二维与三维。

- 二维：experiments/run_gui_2d_20261106_171841_232386_7e4458
- 三维：experiments/run_gui_3d_20261106_171846_481255_9ab61d

每套有 252 个时刻、2016 条观测；最终种子、时长、解算维度与控件一致。二维无 estimated_z_m/estimated_vz_mps，三维有这两列。两套的 trajectory_truth.csv、observations.csv、signal.iq 均字节一致。二维目录的 app_check.json 保存报告和执行命令；每个结果另含完整配置、代码哈希、输入哈希、软件环境和原始命令。

验证范围：真实窗口启动及布局、实际控件到文件生成的进程内自动检查。未人工逐项鼠标编辑全部参数，也未覆盖所有显示缩放和 Python 环境。此次未修改传播公式或增加自动补偿优化，默认 I/Q 仍无完整合法 LNAV。


---

## English translation

# Parameter Application Validation (2026-11-06)

Environment: Windows, Python 3.12.14, NumPy 2.3.5, and Tk 8.6.

The Python/Tk parameter window was launched using `gui.ps1`; the layout of the eight parameter groups, the 2D/3D switch, units and descriptions were checked. All 61 automated checks passed, including the existing physics, ephemeris, I/Q and 2D/3D checks, and new tests of parameter parsing, default round trips, control editing, saving configurations under a new name, preserving relative input paths, preventing overwrites and reading only enabled external files.

Full test command: `run.ps1 -Test`.

Command for checking the path from controls to generated files:

```powershell
python -B scripts/check_app.py
```

This check creates a hidden Tk window, changes actual input controls and invokes the same “Generate simulation data” button. It exercises the actual parameter snapshot, subprocess and CLI, without injecting mouse or keyboard events into the desktop. The seed was set to 20261106 and total duration to 2.2 s; all other physical conditions were identical for the 2D and 3D runs.

- 2D: `experiments/run_gui_2d_20261106_171841_232386_7e4458`
- 3D: `experiments/run_gui_3d_20261106_171846_481255_9ab61d`

Each run contained 252 epochs and 2,016 observations; the final seed, duration and solution dimension matched the controls. The 2D output did not contain `estimated_z_m` or `estimated_vz_mps`; the 3D output contained both. The two runs' `trajectory_truth.csv`, `observations.csv` and `signal.iq` files were byte-identical. `app_check.json` in the 2D directory recorded the report and command; each result also contained the complete configuration, code and input hashes, software environment and original command.

Scope: actual window startup and layout, plus an in-process automated check from actual controls to generated files. Not every parameter was edited manually with a mouse, and not every display scaling or Python environment was covered. The propagation equations were not changed and no automatic compensation optimizer was added; the default I/Q still lacked complete, valid LNAV.
