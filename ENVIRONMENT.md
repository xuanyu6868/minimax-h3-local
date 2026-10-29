# 本机环境审计

审计日期：2026-10-28。所有命令均为只读查询；没有安装软件、创建虚拟环境或下载模型。

## 结果

| 项目 | 实际结果 | 判定 |
|---|---|---|
| Windows | Microsoft Windows 11 专业版，10.0.26200，build 26200，64 位 | 已核实 |
| CPU | AMD Ryzen 7 9700X 8-Core Processor | 已核实 |
| GPU | NVIDIA GeForce RTX 5070 | 已核实 |
| 显存 | 12227 MiB（nvidia-smi） | 已核实 |
| 驱动 | 617.42；nvidia-smi 报告 CUDA UMD 13.4 | 已核实；不是 CUDA Toolkit |
| 系统内存 | 31.16 GiB；审计时约 13.35 GiB 空闲 | 已核实 |
| 页面文件 | 9216 MiB 已分配 | 已核实；不建议依赖其承载常规推理 |
| C: | 764.60 GiB 可用 | 已核实 |
| D: | 461.95 GiB 可用 | 已核实 |
| Python / py | 3.12.10，用户级 Python 3.12 | 已核实 |
| Git | 2.54.0.windows.1，位于 D:\Git\cmd\git.exe | 已核实 |
| OpenCode | 1.19.5 | 已核实 |
| uv | PATH 中存在；版本未查询 | 不作为部署决策 |
| conda / nvcc | 未找到 | 不安装补齐 |
| PyTorch | 全局 2.11.0+cpu，torch.version.cuda=None，CUDA 不可用 | 不能用于 GPU 推理 |
| ComfyUI | 用户目录及 D: 定向 Glob 未发现 | 不等同整盘不存在 |
| 虚拟环境 | 用户目录定向 Glob 未发现 pyvenv.cfg | 不等同整盘不存在 |
| 模型 | 项目目录为空，未发现本地模型 | 已核实 |

Windows CIM 的 `AdapterRAM` 对本 NVIDIA GPU 报告约 4GB，与 `nvidia-smi` 不一致；显存采用面向驱动的 nvidia-smi 数值。

## 关键命令与原始输出（节选）

```text
WindowsCaption : Microsoft Windows 11 专业版
WindowsVersion : 10.0.26200
CPU            : AMD Ryzen 7 9700X 8-Core Processor
RAM_GiB        : 31.16
```

```text
NVIDIA GeForce RTX 5070, 12227 MiB, 617.42
Name Free_GiB Used_GiB
C    764.6    188.85
D    461.95   491.9
```

```text
Python 3.12.10
git version 2.54.0.windows.1
OpenCode: 1.19.5
nvcc: command not found
conda: command not found
```

```text
torch_version=2.11.0+cpu
torch_cuda_build=None
cuda_available=False
```

```text
NVIDIA-SMI 617.42
CUDA UMD Version: 13.4
GPU: NVIDIA GeForce RTX 5070 WDDM
Memory: 726MiB / 12227MiB（审计时）
```

## Git 状态

- 审计开始时 `d:\Minimax H3` 是空目录，且已经是一个无提交的 Git 仓库，分支显示 `master`。
- `git remote -v` 无输出。
- `git ls-remote https://github.com/xuanyu6868/minimax-h3-local.git HEAD` 无输出，退出码 0。
- Git 用户已配置为 `xuanyu6868`，邮箱使用 GitHub noreply 地址。
- 第一阶段文档完成后才设置目标远程并创建报告提交；不推送。

## 未覆盖项

未进行整盘递归扫描、注册表审计或管理员权限查询。因此“未发现 ComfyUI/虚拟环境”只表示上述定向检查范围，不是全盘不存在证明。

## 第二阶段 A 更新（2026-10-28）

只读复查：驱动 617.42、RTX 5070 12227 MiB、审计时约 16.8 GiB 空闲内存、D: 可用 461.93 GiB。全局 Python 与 PyTorch 未改动。

新建隔离环境（不在本仓库内）：

| 项目 | 结果 |
|---|---|
| 位置 | `D:\AI\MiniMaxH3`（ComfyUI 源码 + `.venv`） |
| ComfyUI | v0.42.1，提交 `63be2f9b82ad0dac88a7ceaa28a9cf3154125a18` |
| Python | 3.12.10（venv） |
| PyTorch | 2.10.0+cu130，`torch.cuda.is_available()` 为 True |
| GPU 实算 | 4×4 CUDA 矩阵乘法 + 同步通过；能力 12.0 |
| ComfyUI | 本机启动成功，H3 节点已注册 |
| 模型 | 未下载，未进行加载或生成验收 |

详细命令、退出码与错误修复见 [reports/phase-2a-runtime.md](reports/phase-2a-runtime.md)。

## 第三阶段更新（2026-10-30）

| 项目 | 结果 |
|---|---|
| 本地模型 | FL2VA W6A8 + NVFP4-AWQ TE + 视频/音频 VAE，合计 35,087,209,179 bytes |
| 校验 | 四个文件字节数与 SHA256 全部匹配 |
| 生成验证 | T2V、I2V、首尾帧均 `success`（22 帧、3 步小样） |
| 显存峰值 | 约 11.0 GiB / 12.2 GiB |
| ComfyUI 进程 RAM | 13.7–15.93 GiB |
| Ref2VA | 未下载 |

详见 [reports/phase-3-fl2va-smoke.md](reports/phase-3-fl2va-smoke.md)。
