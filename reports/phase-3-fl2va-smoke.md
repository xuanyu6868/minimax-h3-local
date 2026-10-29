# 第三阶段：FL2VA 下载与基础验收

日期：2026-10-30。本轮完成 FL2VA 起步模型集下载、校验，并首次在本机以 W6A8 完成 T2V、I2V 和首尾帧小样生成。**未安装 Turbo LoRA、未启用任何加速插件、未使用云服务。**

## 1. 下载与校验

固定修订：`Comfy-Org/MiniMax-H3@e5eb578a89295337b8ff433a035929ce0279e0b6`。

| 文件 | 目标目录 | 字节数 | 结果 |
|---|---|---:|---|
| `minimax_h3_fl2va_pruned_w6a8.safetensors` | `models/diffusion_models/` | 15,983,746,636 | SHA256 通过 |
| `qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors` | `models/text_encoders/` | 15,687,142,551 | SHA256 通过 |
| `minimax_h3_video_vae_int8_convrot.safetensors` | `models/vae/` | 2,811,065,184 | SHA256 通过 |
| `minimax_h3_audio_vae_fp32.safetensors` | `models/vae/` | 605,254,808 | SHA256 通过 |
| **合计** | | **35,087,209,179** | 与预期完全一致 |

脚本 `scripts/download-fl2va.ps1` 使用固定修订 URL，逐个比对字节数后再校验 SHA256，最后才把 `.partial` 改名为正式文件；校验失败不会删除或覆盖已有文件。

## 2. 网络与下载过程

| 路线 | 实测 | 结论 |
|---|---|---|
| VPN（美国节点，全局） | 60 秒 165.6 MiB，约 2.76 MiB/s；续传时升至 8–16 MiB/s | 可建立连接，整体可用 |
| 直连（`-Direct`） | 首次 60 秒 147 MiB（约 2.45 MiB/s）；后续连接停在 `SynSent`，无响应 | 不稳定，不能依赖 |

Hugging Face 是由美国 AWS CDN 承载的服务，直连不构成“国内下载”。实际选择走 VPN 完成本轮下载。

### 修复的脚本缺陷

初次使用的 `curl --retry` 在低速重试时会重新打开 `--output` 文件并**截断**已有 `.partial`，导致文本编码器下载到约 2756 MiB 后进度被清零。

已改为在 PowerShell 层循环重试，每次 curl 调用自动 `--continue-at -` 续传，并保留 `--speed-limit 1024 --speed-time 120` 作为停滞检测。重试上限 10 次，失败保留 `.partial`。

## 3. 工作流接入

官方 UI 模板（含 subgraph）不能直接 POST 到 `/prompt`：该接口要求 API 格式，直接提交会返回 500 `TypeError: argument of type 'int' is not iterable`。

因此新增 `scripts/build-h3-api-workflow.py`，直接按节点 schema 构造最小 API 工作流（14–16 个节点），链为：

```text
UNETLoader + CLIPLoader + 双 VAELoader
  → MiniMaxH3ImageToVideo / first_frame / last_frame
  → RandomNoise + KSamplerSelect + BasicScheduler + BasicGuider
  → SamplerCustomAdvanced → VAEDecode + VAEDecodeAudio → CreateVideo → SaveVideo
```

注意：模型名必须使用文件名，不能带 `diffusion_models/` 等目录前缀，否则 `value_not_in_list` 校验失败。

## 4. 本机验收结果

测试参数：短边 224–320、22 帧（约 1 秒，低于官方训练的 124 帧下限）、3 步，仅用于验证链路，不代表质量或速度基线。

| 用例 | 扩散模型 | 输入 | 结果 | 输出 |
|---|---|---|---|---|
| T2V | W6A8 | 仅文本 | `completed: true / success` | `output/h3/t2v_smoke_00001_.mp4` |
| I2V | W6A8 | `first_frame` | `completed: true / success` | `output/h3/i2v_smoke_00001_.mp4` |
| 首尾帧 | W6A8 | `first_frame` + `last_frame` | `completed: true / success` | `output/h3/flf_smoke_00001_.mp4` |

### 资源占用

| 项目 | 实测 |
|---|---|
| ComfyUI 识别显存 | 12199 MB |
| 生成期显存占用 | 约 11012–11089 MiB（接近上限） |
| ComfyUI 进程 RAM | 13.7–15.93 GiB |
| 单次端到端 | 11.54 秒（含模型初始化） |
| 3 步采样 | 约 2.5 秒 |

模型初始化首次约 3.6 秒/步，之后 1–2 it/s。显存已接近容量上限，提高分辨率、帧数或步数前必须先做小步回归。

## 5. 成功、失败与未测试

- **成功**：四文件下载、字节与 SHA256 双重校验；W6A8 在 12GB 卡上加载并完成 T2V/I2V/首尾帧。
- **失败并已修复**：`curl --retry` 截断 `.partial`；UI 模板不能直接作为 API prompt；模型名带目录前缀被拒。
- **未测试**：Ref2VA 与多参考图/视频/音频；124 帧以上正式时长；Turbo LoRA；提升分辨率后的显存表现；质量主观评价；峰值内存监控工具。
- **未安装**：Turbo LoRA、SageAttention、Triton、TeaCache、Easy 节点。

## 6. 回滚

1. 停止 ComfyUI 进程。
2. 删除 `D:\AI\MiniMaxH3\ComfyUI\models` 下对应模型文件即可回退到无权重状态；`.venv` 与源码不受影响。
3. 删除 `D:\AI\MiniMaxH3` 可整体回滚本轮环境。
4. 汇报仓库仅包含脚本、报告与测试工作流，不含权重或输出视频。

## 7. 下一阶段建议：Ref2VA

按 `MODEL_MANIFEST.md` 追加下载 `minimax_h3_ref2va_pruned_w6a8.safetensors`（15,983,746,636 bytes，SHA256 `ece96bbbce76670ec782de84acc888fd9d9b210bd2ab97c1957b39896734f9f1`），随后用 `MiniMaxH3ReferenceToVideo` 验证多图、参考视频与独立音频。

建议先保持当前分辨率与步数做最小验证，再逐步增加时长，避免在显存接近上限时直接放大参数。
