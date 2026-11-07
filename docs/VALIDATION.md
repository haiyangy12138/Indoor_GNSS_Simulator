# 验证记录（2026-11-05）

环境：Windows，Python 3.12.14，NumPy 2.3.5。配置模板约 117 个叶级参数项（重复发射点条目仅计一次），包括支持的模型开关、物理单位和资源控制；不是所有现实物理效应均已实现。

## 命令

项目根目录：`<project-root>`。

```powershell
.\run.ps1 -Test
.\run.ps1 -Output experiments/ready_example
python scripts/inspect_iq.py experiments/ready_example
python scripts/fetch_example_nav.py
.\run.ps1 -Config configs/rinex_template.json -Output experiments/rinex_eight_verified
```

本机使用 run.ps1 自动选择的 Codex 内置 Python。源代码与输入哈希、确切命令、环境和随机种子见各实验 provenance.json。未上传外部服务。

## 结果

- 33项unittest全部通过：C/A ICD首十码、自相关、码延迟、载波相位/多普勒一致性、分块/噪声复现、NAV覆盖、GPS星历和相对论钟差闭式检查、直达LS恢复、公共钟差、单发射点退化、有限墙面反射、非法参数/文件冲突与资源保护。
- 默认ready_example：232个接收机时间历元、1856行观测、8条LOS传播路径；I/Q为204600个复数采样、818400字节、50ms、4.092MS/s。文件字节数与SHA-256、观测行数、路径数组有限性和单调时间及全部源代码哈希已再次核对。
- 独立运行了直达无噪声、双发射点无补偿、单次墙面反射和耦合补偿示例。多径示例为8颗卫星×7路径=56条波形路径。
- 已下载公开GPS RINEX2样本brdc0010.22n并核对SHA-256，成功选择8颗健康可见星并生成数据。开发中发现某些PRN不健康会中止整体筛选，现已改为记录拒绝原因并继续选择；相关回归测试通过。
- 真实星历来源：https://raw.githubusercontent.com/osqzss/gps-sdr-sim/master/brdc0010.22n 。SHA-256：7db04513dd2d0e13c0ee20cb4eaa8f71e5a28ab58b65c9b5b789f86eeab436cd。

## I/Q捕获诊断的实际边界

10ms非相干累积、每段1ms、频率网格250Hz：PRN3/4/9/17的峰/中值约90，多普勒峰与真值的差在125Hz以内，码相位差在约0.16chip以内。PRN2/10/15/16因相对较弱信号表现较差；PRN10出现假峰。找到最大峰不等于可靠捕获，不能声称8颗星均捕获。

该诊断仅为FFT相关搜索，不是完整DLL/PLL、NAV解码或GNSS-SDR验证。默认I/Q无合法LNAV，不能独立冷启动定位。

## 结果解释

直达无噪声位置恢复至浮点数精度只说明模型/解算自洽，不代表现实定位达到纳米精度。默认轨迹瞬时起停处速度不连续，中心差分跨越该点时给出平均速度，会产生约半个速度阶跃的误差；动态误差研究须使用平滑轨迹或单独标注边界。

无补偿转发示例误差明显较大，未声称达到课件指标。布局优化、合法导航电文、完整接收机链、实测噪声/多径校准、与独立精密轨道数值交叉核验仍待开展。


---

## English translation

# Validation Record (2026-11-05)

Environment: Windows, Python 3.12.14, NumPy 2.3.5. The configuration template has approximately 117 leaf parameters (repeated transmitter entries counted once), including supported model switches, physical units and resource controls; not every real physical effect is implemented.

## Commands

Project root at the time: `<project-root>`.

```powershell
.\run.ps1 -Test
.\run.ps1 -Output experiments/ready_example
python scripts/inspect_iq.py experiments/ready_example
python scripts/fetch_example_nav.py
.\run.ps1 -Config configs/rinex_template.json -Output experiments/rinex_eight_verified
```

The local run used the bundled Codex Python automatically selected by `run.ps1`. Source and input hashes, exact commands, environment and seed were recorded in each experiment's `provenance.json`. Nothing was uploaded to an external service.

## Results

- All 33 unittest checks passed: first ten C/A ICD chips, autocorrelation, code delay, carrier phase/Doppler consistency, chunk/noise reproducibility, NAV coverage, closed-form GPS ephemeris and relativistic clock checks, direct-path least-squares recovery, common clock bias, single-transmitter degeneracy, finite wall reflection, invalid parameters/file conflicts and resource protection.
- Default `ready_example`: 232 receiver-time epochs, 1,856 observation rows and 8 LOS propagation paths. I/Q contained 204,600 complex samples, 818,400 bytes, 50 ms at 4.092 MS/s. File byte counts and SHA-256, observation row counts, finite path arrays and monotonic times, and all source hashes were checked again.
- Direct noiseless, two-transmitter uncompensated, single-wall-reflection and coupled-compensation examples were run separately. The multipath example had 8 satellites × 7 paths = 56 waveform paths.
- The public GPS RINEX 2 sample `brdc0010.22n` was downloaded and its SHA-256 verified; eight healthy visible satellites were selected and data generated successfully. During development, some unhealthy PRNs had aborted the entire selection; the code was changed to record rejection reasons and continue selection, with regression tests passing.
- Real ephemeris source: https://raw.githubusercontent.com/osqzss/gps-sdr-sim/master/brdc0010.22n . SHA-256: `7db04513dd2d0e13c0ee20cb4eaa8f71e5a28ab58b65c9b5b789f86eeab436cd`.

## Actual scope of the I/Q acquisition diagnostic

With 10 ms noncoherent accumulation, 1 ms segments and a 250 Hz frequency grid, the peak-to-median ratio was about 90 for PRNs 3/4/9/17; Doppler peak differences from truth were within 125 Hz and code-phase differences within about 0.16 chip. PRNs 2/10/15/16 performed less well due to relatively weak signals; PRN 10 showed a false peak. Finding the maximum peak does not establish reliable acquisition, so acquisition of all eight satellites cannot be claimed.

This diagnostic is only an FFT correlation search, not a complete DLL/PLL, NAV decoder or GNSS-SDR validation. Default I/Q has no valid LNAV and cannot independently support cold-start positioning.

## Interpretation

Noiseless direct-path position recovery to floating-point precision shows only model/solver self-consistency; it does not imply nanometer positioning accuracy in reality. The default trajectory has instantaneous starts and stops with velocity discontinuities. Central differences spanning such a point produce an average velocity, giving an error of about half the velocity step; dynamic-error studies should use a smooth trajectory or separately flag the boundaries.

The uncompensated relay example has substantial error and does not claim to meet the course-material targets. Layout optimization, valid navigation messages, a complete receiver chain, calibration against measured noise/multipath and numerical cross-validation with independent precise orbits remain future work.
