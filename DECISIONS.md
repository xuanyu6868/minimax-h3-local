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

## 推测 / 工程预期（未实测）

- W6A8 + NVFP4-AWQ 比官方默认 INT8 ConvRot 更适合 12GB VRAM + 32GB RAM，但采样/解码峰值可能仍造成 OOM 或换页。
- 先 FL2VA 后 Ref2VA 可降低下载与排障复杂度，不影响最终功能覆盖。

## 待验证

- 具体 ComfyUI、PyTorch、CUDA、Triton 版本的锁定组合。
- W6A8 在 RTX 5070 上的实际内核支持、质量、VRAM/RAM 峰值与稳定性。
- 是否需 `--disable-pinned-memory` 或其它内存参数；不能直接套用 8GB/16GB 机器结论。
- Easy 节点 nightly 当前代码安全性、依赖与 W6A8 的实测兼容。
- GGUF 备选精确文件与 Ref2VA 对应关系。
