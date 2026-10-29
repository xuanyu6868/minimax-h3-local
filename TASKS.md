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
- [x] `/object_info` 服务端节点与选项兼容性检查（不等同于前端界面导入验证）
- [x] 正式基线：T2V / I2V / 首尾帧 736×416、124 帧、20 步、24fps 全部通过
- [x] T2V 同规格复跑通过（130.20 s）
- [x] 2 秒间隔资源采样与媒体规格核查
- [x] 采样数据按生成窗口重算，修正峰值来源
- [ ] 画质与听感人工确认（未观看画面、未试听音轨）
- 报告：[reports/phase-3b-review-fixes-baseline.md](reports/phase-3b-review-fixes-baseline.md)

## 第三阶段最终补正（2026-10-30）

- [x] patch-workflow-w6a8.py 强制 W6A8 规范路径：加载器名、URL 文件名、目录、修订四处一致
- [x] 新增 3 项回归检查覆盖"URL 为 main 但文件名不同"的漏改情形（共 11 项通过）
- [x] `requirements.lock.txt` 入库，`uv pip install --dry-run -r requirements.lock.txt` 返回 Would make no changes
- [x] install-runtime.ps1 默认使用已验证锁文件，重新解析需显式 `-Relock`
- [x] 报告第 3 节改名并明确 `/object_info` 检查边界
- [x] 报告第 7 节按时间窗口重写：生成期 GPU 峰值 11,404 MiB，可用内存最低 2,007 MiB
- [x] 补提完整 337 行采样 CSV
- [x] 新增 `committed_MiB` / `commit_limit_MiB` 两列，只读记录页面文件配置

## 第四阶段：Ref2VA 受控验收（2026-10-30）

- [x] 下载并校验 Ref2VA（15,983,746,636 bytes，SHA256 `ece96bb…` 通过）
- [x] 确认 FL2VA 与 Ref2VA 不同时驻留：切换模型集需重启进程，启动参数已记录
- [x] 核实原生 `MiniMaxH3ReferenceToVideo` schema 与 Autogrow 输入键名
- [x] 单参考图 736×416 / 124 帧 / 20 步 / 24fps 通过（160.72 s）
- [x] 双参考图同规格通过（170.23 s），提示词显式区分 `<Picture 1>` / `<Picture 2>`
- [ ] 参考视频（未测；参考音频已在第四阶段 B 补测）
- [ ] 画面与听感人工确认（未观看、未试听）
- 报告：[reports/phase-4-ref2va-images.md](reports/phase-4-ref2va-images.md)

## 第四阶段 B：内存稳定性、界面交付与参考音频（2026-10-30）

- [x] install-runtime.ps1 锁文件改为按脚本位置解析，缺锁文件报错，仅 `-Relock` 重新解析
- [x] start-comfyui.ps1 启动前检查 8188，取监听进程为真实 PID，`-StopExisting` 才替换
- [x] launch JSON 不再把"未加载"预填成"已卸载"结论
- [x] 采样新增 `commit_headroom_MiB` / `commit_ratio`，汇总新增极值时间与中断规则判定
- [x] 修正报告口径：双图显存平均值高 298 MiB、峰值低 55 MiB，不能混写
- [x] 补齐 9 条视频媒体探测、7 个工作流哈希（含规范化哈希）、3 项输入哈希
- [x] 内存预设对比：默认 vs `--disable-pinned-memory`，提交峰值 49,345 → 38,245 MiB，破阈 29 → 0
- [x] UI 工作流生成器 + 本机实际导入（T2V 14 节点、Ref2VA 15 节点）
- [x] T2V 经界面提交成功（`3be89230`）
- [ ] **Ref2VA 经界面提交失败**：`ref_image_1` 扁平键报 `TypeError`，未改 ComfyUI 源码
- [x] 参考音频对照 + 实验：124 帧全不同、音频 RMS 0.0019 → 0.1998
- [ ] 参考视频通路、`ref_image_size=max`、多音频未测
- [ ] 中断流程未实际触发验证；每档预设仅 1 次，非统计结论
- 报告：[reports/phase-4b-stability-ui-audio.md](reports/phase-4b-stability-ui-audio.md)

## 第四阶段 C：修通 Ref2VA 界面并收尾（2026-10-30）

- [x] 修复 `build-ui-workflow.py`：删除把 `ref_images.ref_image_0` 改成 `ref_image_0` 的 RENAME，保留分组路径与 `shape=7`
- [x] 发现并按官方模板与原生节点校正 Autogrow 槽位为**零基**编号（原为 1 基，错）
- [x] 原生画布新建 Ref2VA 节点、由前端自己序列化，存为对照 `workflows/native_ref2va_single_serialized.json`
- [x] 界面提交单参考图成功（`03fa592b`，`ref2va_single_00004_.mp4`）
- [x] 界面提交双参考图成功（`3253dbd2`，`ref2va_dual_00002_.mp4`）
- [x] 刷新页面后重新导入，连接、分组路径与控件值全部保留
- [x] `--disable-pinned-memory` 固化为默认，`-EnablePinnedMemory` 为显式对照；argv 已记录
- [x] 实现 `scripts/guard-memory.py` 主动中断（余量 < 512 MiB，或占比连续两次 ≥ 97%）
- [x] 用回放读数验证阈值：单次超标不中断、连续两次才中断、缺失读数不作健康解
- [x] 真实中断测试通过：`execution_interrupted`、`completed=false`、任务确实停止、服务仍健康
- [x] 回归检查修复并扩到 17 项，全部通过（含 UI 前缀保留、零基槽位、默认预设、中断规则）
- [x] 新增 [USAGE.md](USAGE.md) 中文使用说明
- [x] 核实输入素材真实规格：`h3_first.png` 320×320、`h3b_last.png` 736×416、`h3_ref_tone.wav` 32 kHz 单声道
- [ ] 画质、听感、参考视频、`ref_image_size=max` 仍未验证
- 报告：[reports/phase-4c-ui-ready.md](reports/phase-4c-ui-ready.md)

## 第五阶段：优化与备选（未开始）

- [ ] 评估 Turbo、注意力与长视频
- [ ] 必要时建立 GGUF 或 WanGP 隔离备选环境
