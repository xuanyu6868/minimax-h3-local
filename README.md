# MiniMax H3 本地部署

在本地 Windows 电脑部署 MiniMax H3，优先低显存、可复现和可回滚。

## 目标

- 文生视频（T2V）
- 图生视频（I2V）
- 首尾帧控制
- 多参考图、参考视频、参考音频生成
- 原生音视频工作流

## 已核实硬件

| 项目 | 实测 |
|---|---|
| CPU | AMD Ryzen 7 9700X 8-Core Processor |
| GPU | NVIDIA GeForce RTX 5070，12227 MiB |
| 内存 | 31.16 GiB（标称 32GB） |
| 系统 | Windows 11 专业版，64 位，build 26200 |
| 磁盘 | C: 764.60 GiB 可用；D: 461.95 GiB 可用 |

## 当前阶段

第一阶段只读环境审计和技术核验已完成。没有安装软件、下载模型或运行生成任务。

- [本机审计](ENVIRONMENT.md)
- [路线](PLAN.md)
- [任务状态](TASKS.md)
- [技术决策](DECISIONS.md)
- [模型清单](MODEL_MANIFEST.md)
- [风险](RISKS.md)

**首选路线：ComfyUI 0.42.1 原生 H3 工作流，W6A8 扩散模型（FL2VA + Ref2VA）、NVFP4-AWQ 文本编码器和官方双 VAE。** 已完成 T2V、I2V、首尾帧正式基线验收，以及 Ref2VA 单/双参考图受控验收；参考视频、参考音频与质量评估尚未完成。

## 当前状态（2026-10-30）

| 项目 | 状态 |
|---|---|
| 隔离运行环境 | 已建立（`D:\AI\MiniMaxH3`），依赖锁定于 `requirements.lock.txt` |
| CUDA / PyTorch | 2.10.0+cu130，实算通过 |
| FL2VA 模型集 | 已下载并校验（35,087,209,179 bytes） |
| Ref2VA 权重 | 已下载并校验（15,983,746,636 bytes） |
| 正式基线 | 736×416 / 124 帧 / 20 步 / 24fps 通过（T2V / I2V / 首尾帧） |
| Ref2VA 参考图 | 单图 160.72 s、双图 170.23 s 通过，规格全对 |
| 内存预设 | 默认提交峰值 49,345 MiB；`--disable-pinned-memory` 后 38,245 MiB |
| 参考音频 | 对照 + 实验通过，124 帧全不同、音频 RMS 0.0019 → 0.1998 |
| 界面验收 | T2V 经画布提交成功；**Ref2VA 经画布提交失败**（`ref_image_1` 扁平键） |
| Ref2VA 参考视频 | 未测 |
| 画质与听感 | **待人工确认** |

- [阶段二 A 报告](reports/phase-2a-runtime.md)
- [阶段三报告](reports/phase-3-fl2va-smoke.md)
- [阶段三补正与基线](reports/phase-3b-review-fixes-baseline.md)
- [阶段四 Ref2VA 参考图](reports/phase-4-ref2va-images.md)
- [阶段四 B 稳定性 / 界面 / 参考音频](reports/phase-4b-stability-ui-audio.md)
