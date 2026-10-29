# 任务列表

## 第一阶段：只读审计与报告

- [x] 核实 Windows、CPU、GPU、显存、驱动、RAM 和磁盘
- [x] 检查 Python、Git、OpenCode、CUDA、PyTorch
- [x] 定向检查 ComfyUI、虚拟环境和模型目录
- [x] 检查 Git 配置、本地仓库与目标远程
- [x] 核验 ComfyUI 官方 H3 支持和工作流
- [x] 核验官方模型文件、精确大小、SHA256 和许可证
- [x] 核验原生/Easy/GGUF/WanGP 加载器差异
- [x] 记录低显存社区证据及适用范围
- [x] 编写八项阶段文档
- [x] 敏感信息检查与本地报告提交
- [x] 首次报告经批准后推送至 origin/master（c87e1d4）

## 第一阶段容量复核（待批准推送）

- [x] 按官方 HF API 复核五个基础文件及两个可选 Turbo 的文件名、字节数和 LFS SHA256
- [x] 重新计算：FL2VA 起步集合 35,087,209,179 bytes = 35.087209179 GB / 32.677509990 GiB
- [x] 重新计算：完整基础集合 51,070,955,815 bytes = 51.070955815 GB / 47.563534058 GiB
- [x] 修正 MODEL_MANIFEST.md、PLAN.md、RISKS.md 的容量、单文件 GiB 舍入和预留空间
- [x] 复核官方下载来源和 W6A8 的 ComfyUI 0.38.0+ 要求；未将文件存在视为本机运行成功
- [ ] 负责人审核本次报告 diff 并明确批准推送

## 第二阶段 A：隔离运行环境与 GPU 验证（已完成）

- [x] 固定 ComfyUI v0.42.1（`63be2f9b82ad0dac88a7ceaa28a9cf3154125a18`）
- [x] 在 `D:\AI\MiniMaxH3` 建立独立 venv，未改动全局 Python
- [x] 安装并验证 PyTorch 2.10.0+cu130，CUDA 张量实算与同步通过
- [x] 修复 `requirements.txt` 覆盖 CUDA PyTorch 的问题，脚本改为 `--no-deps`
- [x] ComfyUI 本机启动，H3 节点注册，官方模板随包安装并复制入仓库
- [ ] 模型加载与视频生成验收（未开始，需第三阶段授权）
- 报告：[reports/phase-2a-runtime.md](reports/phase-2a-runtime.md)

## 第二阶段 B：安装前审批（未开始）

- [ ] 负责人批准 FL2VA 下载预算和固定修订
- [ ] 审查模板中 W6A8 替换步骤
- [ ] 建立独立可回滚环境

## 第三阶段：FL2VA 基础验收（已完成小样）

- [x] 下载并校验 FL2VA、TE、双 VAE（35,087,209,179 bytes，SHA256 全部通过）
- [x] 修复下载脚本 `.partial` 被截断的缺陷
- [x] 以 API 工作流接入 W6A8，模型被 ComfyUI 正确识别
- [x] 验证 T2V（显存峰值约 11.0 GiB，端到端 11.54 秒）
- [x] 验证 I2V
- [x] 验证首尾帧
- [x] 记录峰值 VRAM/RAM：详见 [reports/phase-3-fl2va-smoke.md](reports/phase-3-fl2va-smoke.md)
- [ ] 正式时长（≥124 帧）与画质评估（未开始）

## 第三阶段补正：脚本修复与正式基线（2026-10-30）

- [x] 修正 install-runtime.ps1 首次检出顺序，拒绝重置已有改动目录
- [x] 改用约束文件 + lock 文件，不再依赖 `--no-deps`；记录实际依赖版本
- [x] 修正 patch-workflow-w6a8.py 加载器名与 URL 路径分离，并固定全部模型 URL 修订
- [x] 重写 run-workflow.py 完成判定、失败/超时退出码、产物校验与证据记录
- [x] 8 项回归检查全部通过
- [x] 界面工作流实际导入验证：模型可选、子图完整、无缺失节点
- [x] 正式基线：T2V / I2V / 首尾帧 736×416、124 帧、20 步、24fps 全部通过
- [x] T2V 同规格复跑通过（130.20 s）
- [x] 2 秒间隔资源采样与媒体规格核查
- [ ] 画质与听感人工确认（未观看画面、未试听音轨）
- 报告：[reports/phase-3b-review-fixes-baseline.md](reports/phase-3b-review-fixes-baseline.md)

## 第四阶段：Ref2VA 验收（未开始）

- [ ] 下载并校验 Ref2VA
- [ ] 验证多参考图
- [ ] 验证参考视频和音频
- [ ] 评估可选 Easy 节点统一界面

## 第五阶段：优化与备选（未开始）

- [ ] 评估 Turbo、注意力与长视频
- [ ] 必要时建立 GGUF 或 WanGP 隔离备选环境
