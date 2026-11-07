# 室内 GNSS 仿真项目说明

## 范围
- 在本项目内开展活跃工作。修改模型前阅读 README.md 和 docs/PHYSICS.md。
- 使用 Python 3.10+ 和 NumPy；测试应可通过标准库 unittest 运行。

## 科研真实性
- 所有生成数据均标为仿真数据。区分传播真值、统计观测和接收机估计结果。
- 合成轨道不能称为真实星座；I/Q 未具备经验证的 LNAV 时，不能声称支持冷启动导航。
- 记录完整参数、随机种子、执行命令、软件版本、来源和局限。

## 验证
- 修改模型时运行物理、星历和 I/Q 测试。保持距离、相位和多普勒一致。
- 不覆盖已有实验目录；每次运行使用新的独立目录。
- 未经用户授权，不上传研究数据或未发表结果。

## 文档
- 行为改变时更新参数指南和模型局限。
- 修改本文件时，必须同步更新相邻 AGENTS.md，保持含义一致。
- 相邻中文说明同时附有英文原文，便于双语阅读。

---

## English original

# Indoor GNSS Simulator Instructions

## Scope
- Keep active work in this project. Read README.md and docs/PHYSICS.md before changing models.
- Use Python 3.10+ and NumPy. Keep tests runnable with standard-library unittest.

## Scientific integrity
- Label all generated data as synthetic. Separate path truth, statistical observations and receiver estimates.
- Do not claim real constellation geometry for synthetic orbits, or cold-start navigation for IQ without validated LNAV.
- Record resolved parameters, random seeds, execution commands, software versions, sources and limitations.

## Validation
- Run the physics, ephemeris and IQ tests when changing models. Preserve distance/phase/Doppler consistency.
- Never overwrite existing experiment directories. Save each new run in a separate directory.
- Do not upload research data or unpublished results without user authorization.

## Documentation
- Update the parameter guide and model limitations when behavior changes.
- Any change to this file must update adjacent AGENTS.zh-notes.md with aligned meaning.
- The adjacent Chinese notes also include this English original for bilingual reading.
