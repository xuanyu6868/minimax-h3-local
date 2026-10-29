# 技术决策记录

日期：2026-10-28，第一阶段。

## 已确认

1. **运行时选择 ComfyUI 原生 H3 节点。** 官方有明确版本要求、模型仓库、模板和加载链；不是按文件名猜兼容。
2. **版本下限为 ComfyUI 0.38.0+。** 由 W6A8 支持要求决定，高于基础 H3 的 0.30.0。
3. **首选扩散模型为 pruned W6A8。** 官方 Comfy-Org 仓库的 FL2VA 与 Ref2VA 文件均实际存在，每个 15,983,746,636 bytes。
4. **首选文本编码器为 Qwen3-VL-32B NVFP4-AWQ。** 官方明确无需 Blackwell；不由此推断任意 NVFP4 扩散 checkpoint 的兼容性。
5. **使用视频 INT8 ConvRot VAE 与音频 FP32 VAE。** 官方模板明确使用二者；不省略音频 VAE。
6. **FL2VA 与 Ref2VA 分工。** 前者 T2V/I2V/首尾帧，后者多模态参考。切换完整工作流与扩散权重，共享 TE/VAE。
7. **第一阶段不选 GGUF。** 它是可行备选，但需独立量化文件、GGUF loader 和自定义节点；精确下载清单另行锁定。
8. **隔离运行环境。** 现有全局 PyTorch 是 CPU 构建，不修改全局 Python，不在项目文档目录内混放依赖。
9. **首轮不启用第三方 Easy 节点或可选加速。** 先用官方模板减少变量；基础验收后再固定并审查 Easy 节点版本。
10. **安全边界。** 不提交权重、媒体、虚拟环境、缓存、日志、令牌或 `prompt_optimizer.json`；不运行来源不明脚本。
11. **Git 只提交本地报告，不自行推送。** 远程地址必须为 `https://github.com/xuanyu6868/minimax-h3-local.git`。

## 第二阶段 A 新增

12. **固定 ComfyUI v0.42.1 提交 `63be2f9b82ad0dac88a7ceaa28a9cf3154125a18`。** 官方稳定版，满足 W6A8 的 0.38.0+ 下限；不以“最新版”作为版本依据。
13. **固定 PyTorch 2.10.0+cu130。** 来源为 PyTorch 官方 cu130 轮子索引；驱动报告的 CUDA UMD 13.4 不等于已安装 Toolkit。
14. **ComfyUI 依赖必须用 `--no-deps` 安装。**（2026-10-30 被第 16 条取代，保留历史）实测 `requirements.txt` 的无版本 `torch` 会把 CUDA 构建替换为 2.15.0，导致 `c10_cuda.dll` 加载失败。
15. **运行环境位于 `D:\AI\MiniMaxH3`。** 汇报仓库保持在 `d:\Minimax H3`，不改全局 Python、驱动、页面文件或系统环境变量。

## 第三阶段补正新增（2026-10-30）

16. **依赖锁定改为约束 + lock 文件。** `--no-deps` 不作为依赖完整性保证；使用 `torch-constraints.txt` 约束 CUDA 三件套，`uv pip compile` 生成 `requirements.lock.txt`，`uv pip sync` 应用，安装后断言 CUDA 可用。
17. **已有环境目录不得自动重置。** 非空目录必须是干净且 HEAD 等于固定提交的 git 仓库，否则报错退出。
18. **工作流中的加载器名与下载 URL 路径必须分离，且 URL 固定修订。** 加载器只用文件名；URL 使用 `resolve/<commit>/<dir>/<file>`。
19. **“任务完成”不等于“视频验收通过”。** 成功任务必须定位到真实产物并记录大小与 SHA256，否则单独标记。
20. **性能数字必须来自定时采样并注明间隔。** 2 秒采样的统计值不表述为硬件精确峰值；复跑更快视为缓存差异，不作为加速结论。

## 第一阶段容量复核结论

- W6A8 + NVFP4-AWQ 比官方默认 INT8 ConvRot 更适合 12GB VRAM + 32GB RAM，但采样/解码峰值可能仍造成 OOM 或换页。
- 先 FL2VA 后 Ref2VA 可降低下载与排障复杂度，不影响最终功能覆盖。

## 待验证

- 具体 ComfyUI、PyTorch、CUDA、Triton 版本的锁定组合。
- W6A8 在 RTX 5070 上的实际内核支持、质量、VRAM/RAM 峰值与稳定性。
- 是否需 `--disable-pinned-memory` 或其它内存参数；不能直接套用 8GB/16GB 机器结论。
- Easy 节点 nightly 当前代码安全性、依赖与 W6A8 的实测兼容。
- GGUF 备选精确文件与 Ref2VA 对应关系。
