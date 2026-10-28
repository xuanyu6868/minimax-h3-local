# MiniMax H3 模型清单与兼容性证据

核验日期：2026-10-28。文件大小与 SHA256 来自 [Hugging Face API（recursive, expand）](https://huggingface.co/api/models/Comfy-Org/MiniMax-H3/tree/main?recursive=true&expand=true)，仓库修订 `e5eb578a89295337b8ff433a035929ce0279e0b6`。只查询元数据，未下载权重。

下载 URL 统一为 `https://huggingface.co/Comfy-Org/MiniMax-H3/resolve/main/<path>`。以下模型均在该官方 ComfyUI 重打包仓库中实际存在。

## 首选最小完整集合

不含可选 Turbo LoRA。字节求和 54,069,051,479 bytes = **54.07 GB / 50.36 GiB**。

| 放置路径 / 文件名 | bytes | GiB | SHA256 (LFS oid) |
|---|---:|---:|---|
| diffusion_models/minimax_h3_fl2va_pruned_w6a8.safetensors | 15,983,746,636 | 14.885 | ac746a2e41628ab25afd44d2b22a7fab8d7e66cd07a01bf89ed9d74b0d3f0c35 |
| diffusion_models/minimax_h3_ref2va_pruned_w6a8.safetensors | 15,983,746,636 | 14.885 | ece96bbbce76670ec782de84acc888fd9d9b210bd2ab97c1957b39896734f9f1 |
| text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors | 15,687,142,551 | 14.609 | 35a88d51044231fe332301d7a62aa81e3f2cba62febeb446e2c1e3e0ef76f2c6 |
| vae/minimax_h3_video_vae_int8_convrot.safetensors | 2,811,065,184 | 2.618 | 52a2c8c73583c86e4f41cdcce3a6ad0ea562987bc0bf3d60a0cef5f5c8e60c0e |
| vae/minimax_h3_audio_vae_fp32.safetensors | 605,254,808 | 0.564 | 8e505d95dd1561d47abd43d4238fd40d9bb1ae9e147ed0a4cba778d76ae4db48 |

建议先只取 FL2VA 加共享组件，**38.09 GB / 35.47 GiB**，验证 T2V/I2V/首尾帧后再下载 Ref2VA。完整下载时预留至少 70 GiB 给权重、临时文件和校验；运行时、缓存、输入和输出另留空间。

## 可选 Turbo

| 文件（均置于 loras/） | bytes | GiB | 匹配工作流 | SHA256 |
|---|---:|---:|---|---|
| minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors | 1,956,193,000 | 1.822 | FL2VA 8 步 | 2339acdf19bfe123f46b971ea35d367a84adb85de43627e1eceafa5a5b2b111e |
| minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors | 1,956,193,000 | 1.822 | Ref2VA 4 步 | 5b9ab5ade15d0775676d01a907268a69a1468dc6033b3b0d3ded5502f3ebb84c |

完整集合加这两个可选 LoRA 为 **57.98 GB / 54.00 GiB**。它们不是基础模型推理的通用依赖，但官方模板模型扫描可能列出它们。官方建议参考匹配优先时关闭 Turbo，使用 20–25 步。

## 加载器与工作流兼容性

证据：[官方总教程](https://docs.comfy.org/tutorials/video/minimax/minimax-h3)、[原生工作流](https://docs.comfy.org/tutorials/video/minimax/minimax-h3-native)、[Comfy-Org 模型卡](https://huggingface.co/Comfy-Org/MiniMax-H3)。

| 功能 | 扩散模型 | 官方节点 / 模板 | 共享组件 |
|---|---|---|---|
| T2V | FL2VA | `MiniMaxH3ImageToVideo`（不接图像）；`video_minimax_h3_t2v.json` | 同一文本编码器、视频 VAE、音频 VAE |
| I2V | FL2VA | `MiniMaxH3ImageToVideo`，`first_frame`；`video_minimax_h3_i2v.json` | 同上 |
| 首尾帧 | FL2VA | 同节点接 `first_frame` / `last_frame` | 同上 |
| 多参考图 | Ref2VA | `MiniMaxH3ReferenceToVideo`；`video_minimax_h3_r2v.json` | 同上 |
| 参考视频 / 音频 | Ref2VA | 同上；`<Video N>`、`<Audio N>` 标签 | 同上；音频须接音频 VAE |
| 多帧时间线控制 | FL2VA | `MiniMaxH3AddGuide`；ComfyUI 0.34.0+ | 非初始必选功能 |

- 扩散模型使用核心 `UNETLoader`（界面“Load Diffusion Model”）；量化信息从 checkpoint 读取，不应换用 GGUF 加载器。
- 文本编码器使用核心 H3 模板对应的 CLIP loader；`nvfp4_awq` 明确不要求 Blackwell，RTX 5070 不构成该格式的障碍。
- 视频与音频各用一个 `VAELoader`，分别进入 `VAEDecode` 和 `VAEDecodeAudio`，再用 `CreateVideo` 合并。
- 基础 T2V/I2V/R2V 需要 ComfyUI 0.30.0+；**W6A8 明确要求 0.38.0+**。
- 模板默认 pruned INT8 ConvRot；本项目换成 W6A8 只改扩散模型选择，不能把不同格式混入 GGUF loader。
- `int8_convrot` checkpoint 不支持 Comfy Kitchen attention；教程建议该后端配 BF16。W6A8 与该后端的组合尚未在本机验证，不预设开启。

## 官方仓库其它真实文件

| 角色 | 文件 / 格式 | 每个文件 bytes | 说明 |
|---|---|---:|---|
| FL2VA / Ref2VA | `*_bf16` | 66,280,487,368 | 完整 BF16，不适合作为本机首选 |
| FL2VA / Ref2VA | `*_int8_convrot` | 34,038,892,334 / 34,038,894,550 | 完整 INT8 |
| FL2VA / Ref2VA | `*_pruned_bf16` | 40,225,724,176 | 剪枝 BF16 |
| FL2VA / Ref2VA | `*_pruned_fp8_scaled` | 20,958,205,608 | 官方称无法使用 INT8 时再考虑 |
| FL2VA / Ref2VA | `*_pruned_int8_convrot` | 20,970,379,616 | 模板默认；PyTorch cu130 优先 |
| 文本编码器 | `qwen3vl_32b_minimax_h3_bf16` | 51,506,295,256 | 超出本机 RAM 单独容纳能力 |
| 文本编码器 | `qwen3vl_32b_minimax_h3_int8_convrot` | 27,141,342,152 | 比 NVFP4 大 |
| 视频 VAE | `minimax_h3_video_vae_fp16` | 5,207,808,496 | INT8 视频 VAE 的替代 |

W6A8 是权重 6-bit、激活 8-bit 的 ComfyUI 格式，不是 GGUF/NVFP4。文件存在和官方加载说明是兼容性证据，不等于本机已运行成功。

## 许可证

模型卡声明 **MiniMax H3 Community License Agreement**，原文：[LICENSE](https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/LICENSE)。不是 Apache/MIT 模型许可证。

[ComfyUI 商业许可说明](https://docs.comfy.org/tutorials/video/minimax/minimax-h3#commercial-licensing)指出：本地下载运行免费；商业输出的权利受地域、年收入和展示署名等条件约束，特定地区或超过门槛需商业许可。实际使用前由负责人按原文和适用法律确认，不把本报告当法律意见。

## 备选格式

- **GGUF**：[ComfyUI-GGUF](https://github.com/city96/ComfyUI-GGUF) 用 `Unet Loader (GGUF)` 替换原生 diffusion loader，文本编码器使用匹配的 GGUF CLIP loader。不得把 safetensors 直接当 GGUF 加载。社区索引将 H3 pruned Q4_K_M 与 TE Q2_K 作为 12–16GB 路线，但本阶段未取得首选仓库同等级的精确文件校验信息，故不列入批准下载清单。
- **NVFP4 扩散模型**：属于社区转换，加载支持依具体 ComfyUI 版本/内核；不能把 NVFP4-AWQ 文本编码器的支持声明外推给所有 NVFP4 扩散 checkpoint。
- **FP8 scaled**：官方重打包存在，但体积与 pruned INT8 基本相同，官方仅建议不能走 INT8 时使用；本项目不优先。
- **INT8 ConvRot**：官方工作流已有证据，但文件更大，且在 32GB RAM 上内存压力高；仅作质量对照或排障备选。
- **WanGP**：其仓库声明自己的 MMGP 运行时支持 H3、GGUF/NVFP4/FP8/INT8，不能据此认定这些文件可直接在 ComfyUI 使用。
