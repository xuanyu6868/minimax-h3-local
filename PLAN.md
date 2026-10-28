# 部署路线

## 唯一首选：ComfyUI 原生 H3 + W6A8 + NVFP4-AWQ

采用独立、可删除的 ComfyUI 环境，使用官方原生节点，不让全局 Python 的 `2.11.0+cpu` 参与 GPU 推理。

### 已验证事实

- [ComfyUI 官方教程](https://docs.comfy.org/tutorials/video/minimax/minimax-h3)提供 T2V、I2V、R2V、Multiframe 和 Fun ControlNet 工作流。
- FL2VA 覆盖 T2V/I2V/首尾帧；Ref2VA 覆盖图像、视频、音频参考。
- 官方模型卡将 W6A8 列为最小扩散模型，要求 ComfyUI 0.38.0+，NVFP4-AWQ 文本编码器不要求 Blackwell。
- [8GB 复现仓库](https://github.com/FlowForgeLabAi/-h3-8gb-traps)在 RTX 5060 Laptop 8GB + 16GB RAM、Windows、ComfyUI 0.35.0 上实测生成成功；它使用较大的 pruned INT8 + NVFP4 TE，且报告约 34.5GiB 工作集和换页问题。这证明低显存路线可行，但不证明本机速度或完全无换页。
- [WanGP 原始仓库](https://github.com/deepbeepmeep/Wan2GP)声称 MMGP v4 可用 11GB VRAM 生成 15 秒 1080p H3、5–6GB 生成 480p。属于项目方声明，本机未验证，且与 ComfyUI 路线不能混算。

### 待批准的实施顺序

1. 固定 ComfyUI 0.38.0+ 的具体提交及依赖版本，使用独立 Python 环境；安装支持 RTX 5070 的 CUDA PyTorch，而不是现有 CPU 包。
2. 首先下载 FL2VA W6A8、NVFP4-AWQ TE、视频 INT8 VAE、音频 FP32 VAE，共 35,087,209,179 bytes（35.09GB / 32.68GiB）。
3. 导入官方 T2V/I2V 模板，只将原默认 INT8 扩散文件替换为同家族 W6A8。先以 0.4MP、5 秒、无 Turbo 做加载和小样测试。
4. 记录加载、文本编码、采样、双 VAE 解码的 VRAM、RAM 和提交内存峰值；成功后再测首尾帧。
5. 下载 Ref2VA W6A8，单独导入 R2V 模板，依次验证多图、参考视频、独立音频。
6. 需要统一界面时，审查 [ComfyUI-MiniMaxH3-Easy](https://github.com/nkxx188/ComfyUI-MiniMaxH3-Easy) 的固定版本后添加。其 Loader 支持 FL2VA/Ref2VA、共享 TE 和双 VAE，Model Adapter 可接原生或 GGUF loader；基础功能不依赖它。
7. 暂不启用可选优化器、云服务提示词增强、自动安装脚本或额外注意力后端。

### 功能切换

共享文本编码器与双 VAE，不共享扩散权重：

- T2V/I2V/首尾帧：选择 FL2VA W6A8，使用 Image to Video 模板。
- 多参考图/视频/音频：选择 Ref2VA W6A8，切换完整 R2V 模板，而不是只在 I2V 画布摆一个未接入采样器的 Reference 节点。
- Easy 节点可通过 Loader/Model Adapter 在一个主节点切换，但底层仍需对应权重和输入条件。

### 资源边界

- 完整基础集合为 51,070,955,815 bytes（51.07GB / 47.56GiB），不含运行时、缓存、临时下载、输入或输出。
- 不能将文件大小之和解释为显存需求。设计目标是通过模型卸载让活跃模块进入 12GB VRAM，而非同时驻留全部权重。
- 32GB RAM 是主要风险。保守地避免额外大型进程，先单任务运行；页面文件仅作防崩溃缓冲，不作为性能方案。
- 尚无本机可靠速度、峰值显存或峰值内存数据，第一阶段不提供性能承诺。

## 备选一：ComfyUI-GGUF

[ComfyUI-GGUF](https://github.com/city96/ComfyUI-GGUF)提供 `Unet Loader (GGUF)` 和对应 CLIP loader。[MiniMax 集成索引](https://github.com/MiniMax-AI/awesome-minimax-h3-integration)将 pruned Q4_K_M GGUF（索引称 10.64GiB）与 TE Q2_K（索引称 7.91GiB）列为 12–16GB 组合，并指出更低量化质量下降。

何时切换：官方 W6A8 在 32GB RAM 上无法稳定完成短样，且已排除工作流接线和依赖错误。

差异：需要额外自定义节点与 gguf Python 包、不同扩散与 TE 文件、不同 loader；VAE 与 H3 条件节点保留。实际文件、SHA256、Ref2VA 支持及本机质量必须在下载前单独核验，不能直接复用首选 safetensors。

## 备选二：WanGP 独立运行时

[WanGP](https://github.com/deepbeepmeep/Wan2GP)集成 H3、FL2VA/Ref2VA、多模态参考及 MMGP 低显存管理，Windows/RTX 50 系列文档建议独立 Python 3.11、PyTorch 2.10 cu130 与匹配 Triton。

何时切换：希望脱离 ComfyUI 使用独立 Web UI，或官方 ComfyUI 路线的内存管理不满足需求。

差异：不共享 ComfyUI 工作流/节点/加载器，模型可能由 WanGP 自行下载和转换；其显存声明属于该项目运行时，不能用于证明 ComfyUI 可行。必须在另一独立目录和环境中安装，禁止与 ComfyUI 混用包环境。

## 不作为当前路线

- 完整 BF16 或 BF16 TE：体积和内存不适合 12GB/32GB。
- Diffusers 原始完整仓库：索引称总量 464.2GiB，无必要。
- Fun ControlNet、upscale、长视频、Sol/Sage 等加速：基础验收后再评估。
- 云端提示词优化：默认关闭，避免媒体/提示词与凭据外流。
