# 第二阶段 A：隔离运行环境与 GPU 验证

日期：2026-10-28。本轮在 `D:\AI\MiniMaxH3` 建立独立环境并完成 CUDA 与 ComfyUI 启动验证。**未下载 H3 模型、未安装可选插件、未运行视频生成。**

## 1. 本轮状态

| 项目 | 结果 |
|---|---|
| 起点提交 | `decbbb8bf9b79de3cec11145ebb4a809c4af7946`（docs: correct H3 model size totals） |
| 起点工作区 | 干净，`master` 与 `origin/master` 一致 |
| 汇报仓库 | `d:\Minimax H3`，未移动 |
| 运行环境 | `D:\AI\MiniMaxH3`（新建，此前不存在） |
| 结束状态 | 环境可用；CUDA 实算与 ComfyUI 启动通过；模型未加载 |

只读复查：驱动 617.42、RTX 5070 12227 MiB、审计时约 16.8 GiB 空闲内存、D: 可用 461.93 GiB。未安装系统级 CUDA Toolkit，未改动驱动、页面文件、系统环境变量或全局 Python（全局仍为 2.11.0+cpu）。

## 2. 版本选择与依据

| 组件 | 版本 | 来源与依据 |
|---|---|---|
| ComfyUI | v0.42.1，提交 `63be2f9b82ad0dac88a7ceaa28a9cf3154125a18` | 官方 [releases/latest](https://api.github.com/repos/Comfy-Org/ComfyUI/releases/latest) 为 v0.42.1（2026-10-19 发布，非预发行）；`git ls-remote refs/tags/v0.42.1` 得到该提交。满足 W6A8 的 0.38.0+ 下限 |
| Python | 3.12.10 | 复用本机已有解释器创建独立 venv，未改动全局包 |
| PyTorch | 2.10.0+cu130（torchvision 0.25.0、torchaudio 2.10.0） | [PyTorch 历史版本页](https://pytorch.org/get-started/previous-versions/) 的 cu130 Windows 轮子；驱动报告 CUDA UMD 13.4，兼容 13.0 运行时 |
| ComfyUI 依赖 | comfyui-frontend-package 1.55.18、comfyui-workflow-templates 0.11.89、comfy-kitchen 0.2.39 等 | v0.42.1 仓库 `requirements.txt` 固定版本；[requirements.txt](https://raw.githubusercontent.com/Comfy-Org/ComfyUI/v0.42.1/requirements.txt) |

`nvidia-smi` 的 CUDA UMD 版本只说明驱动支持上限，不代表已安装 Toolkit；本机仍无 `nvcc`。

## 3. 实际执行

| 步骤 | 命令要点 | 退出码 | 结果 |
|---|---|---|---|
| 定位提交 | `git ls-remote https://github.com/Comfy-Org/ComfyUI.git refs/tags/v0.42.1` | 0 | `63be2f9b…` |
| 克隆源码 | `git clone --filter=blob:none --no-checkout … D:\AI\MiniMaxH3\ComfyUI` | 0 | 无更新、无覆盖 |
| 检出固定版 | `git checkout --detach 63be2f9b82ad0dac88a7ceaa28a9cf3154125a18` | 0 | HEAD 为 v0.42.1 |
| 建 venv | `uv venv --python 3.12 D:\AI\MiniMaxH3\.venv` | 0 | Python 3.12.10 |
| 装 CUDA PyTorch | `uv pip install torch==2.10.0 torchvision==0.25.0 torchaudio==2.10.0 --index-url …/cu130` | 0 | torch 2.10.0+cu130 |
| 装 ComfyUI 依赖（首次） | `uv pip install -r ComfyUI\requirements.txt` | 0 | **副作用：torch 被换成 2.15.0，CUDA 不可用** |
| 最小修复 | `uv pip install --reinstall <固定 CUDA 三件套> --index-url …/cu130` | 0 | 恢复 torch 2.10.0+cu130 / torchvision 0.25.0+cu130 |
| 锁定补齐依赖 | `uv pip install --no-deps -r ComfyUI\requirements.txt` | 0 | 34 个包已满足，无覆盖 |
| 启动 ComfyUI | `python main.py --listen 127.0.0.1 --port 8188 --disable-auto-launch` | 运行中后正常停止 | 仅本机监听 |

### 错误与修复记录

首次按官方 `requirements.txt` 安装时，其中 `torch` 无版本约束，解析器安装了默认 PyPI 的 **torch 2.15.0**，随后 `import torch` 报：

```text
OSError: [WinError 127] 找不到指定的程序。
Error loading "...\torch\lib\c10_cuda.dll" or one of its dependencies.
```

修复仅限隔离环境：强制重装固定 cu130 三件套，然后用 `--no-deps` 补齐 ComfyUI 依赖，避免再次覆盖。脚本已改为默认 `--no-deps` 并加入安装后 CUDA 断言。未改动系统配置或全局环境。

## 4. 验证结果

### GPU 实算（`scripts/verify-cuda.py`）

```json
{
  "python": "D:\\AI\\MiniMaxH3\\.venv\\Scripts\\python.exe",
  "python_version": "3.12.10",
  "torch": "2.10.0+cu130",
  "torch_cuda": "13.0",
  "gpu": "NVIDIA GeForce RTX 5070",
  "capability": [12, 0],
  "matrix_shape": [4, 4],
  "matrix_diagonal": [0.0, 5.0, 10.0, 15.0],
  "cuda_synchronize": "passed"
}
```

执行了实际矩阵乘法并 `torch.cuda.synchronize()`，结果与单位阵右乘一致；不仅是 `is_available()` 检查。

### ComfyUI 启动

关键日志（脱敏）：

```text
Total VRAM 12199 MB, total RAM 31904 MB
pytorch version: 2.10.0+cu130
Device: cuda:0 NVIDIA GeForce RTX 5070 : cudaMallocAsync
Using pytorch attention
```

Windows 上 ComfyUI 默认强制单 GPU 模式。comfy-kitchen 报告 `cuda` 后端可用；`triton` 后端不可用（未安装 Triton，本轮范围外）。

### H3 节点注册（`/object_info`）

```text
EmptyMiniMaxH3LatentAV
MiniMaxH3ImageToVideo
MiniMaxH3AddGuide
MiniMaxH3ReferenceToVideo
MiniMaxH3SigmaShift
MiniMaxH3FunControlNetApply
```

### 官方模板

模板随 `comfyui-workflow-templates 0.11.89` 安装，已复制三份基础模板到 `workflows/`。检查结果：

| 模板 | 扩散模型引用 | 共享组件 | 主节点 |
|---|---|---|---|
| `video_minimax_h3_t2v.json` | fl2va_pruned_int8_convrot | NVFP4-AWQ TE、video int8 VAE、audio fp32 VAE | MiniMaxH3ImageToVideo |
| `video_minimax_h3_i2v.json` | fl2va_pruned_int8_convrot | 同上 | MiniMaxH3ImageToVideo |
| `video_minimax_h3_r2v.json` | ref2va_pruned_int8_convrot | 同上 | MiniMaxH3ReferenceToVideo |

模板默认使用 pruned INT8 ConvRot；第三阶段应替换为同家族 W6A8，而不是修改为 GGUF loader。

## 5. 成功、失败与未测试

- **成功**：固定版 ComfyUI 安装、独立 venv、CUDA 实算、ComfyUI 本机启动、H3 节点注册、官方模板随包安装。
- **已修复失败**：依赖安装覆盖 CUDA PyTorch，已恢复并固化到脚本。
- **未测试**：任何模型加载、推理、T2V/I2V/首尾帧/参考生成；VRAM/RAM 峰值；W6A8 实际兼容性；质量与速度。模板中的模型名称仅表示工作流预期引用。
- **网络备注**：本轮 PyPI 传输很慢（依赖准备约 131 分钟），GitHub 新连接曾超时；不影响已固定的本地提交。

## 6. 回滚方法

1. 停止 ComfyUI 进程。
2. 如需完全回滚，删除 `D:\AI\MiniMaxH3`（源码、venv、依赖缓存隔离在此目录内）。
3. 报告仓库仅保留文本与模板副本，删除对应提交即可；不影响远程历史。
4. 全局 Python、驱动、页面文件与系统环境变量未被修改，无需回退。

## 7. 下一阶段：FL2VA 下载清单

固定模型仓库修订：`Comfy-Org/MiniMax-H3@e5eb578a89295337b8ff433a035929ce0279e0b6`。

| 文件 | bytes | 目标目录 |
|---|---:|---|
| `minimax_h3_fl2va_pruned_w6a8.safetensors` | 15,983,746,636 | `ComfyUI/models/diffusion_models/` |
| `qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors` | 15,687,142,551 | `ComfyUI/models/text_encoders/` |
| `minimax_h3_video_vae_int8_convrot.safetensors` | 2,811,065,184 | `ComfyUI/models/vae/` |
| `minimax_h3_audio_vae_fp32.safetensors` | 605,254,808 | `ComfyUI/models/vae/` |

合计 **35,087,209,179 bytes = 35.087209179 GB / 32.677509990 GiB**。

校验方法：

1. 下载 URL 统一为 `https://huggingface.co/Comfy-Org/MiniMax-H3/resolve/e5eb578a89295337b8ff433a035929ce0279e0b6/<path>`，固定修订而非浮动 `main`。
2. 下载后逐个比对字节数，并计算 SHA256：
   - fl2va W6A8：`ac746a2e41628ab25afd44d2b22a7fab8d7e66cd07a01bf89ed9d74b0d3f0c35`
   - NVFP4-AWQ TE：`35a88d51044231fe332301d7a62aa81e3f2cba62febeb446e2c1e3e0ef76f2c6`
   - video VAE int8：`52a2c8c73583c86e4f41cdcce3a6ad0ea562987bc0bf3d60a0cef5f5c8e60c0e`
   - audio VAE fp32：`8e505d95dd1561d47abd43d4238fd40d9bb1ae9e147ed0a4cba778d76ae4db48`
3. 三项任一不符即停止，不进入加载验收。
