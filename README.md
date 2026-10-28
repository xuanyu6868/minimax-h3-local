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

**首选路线：ComfyUI 0.38.0+ 原生 H3 工作流，W6A8 双扩散模型、NVFP4-AWQ 文本编码器和官方双 VAE。** 备选为 ComfyUI-GGUF 与 WanGP 的独立低显存运行时。部署须另行批准。
