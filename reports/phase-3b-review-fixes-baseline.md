# 第三阶段补正：脚本修复与正式 FL2VA 基线验收

日期：2026-10-30。依据：负责人转述的 ChatGPT 对 `ce082e7` 的审查意见。本轮只在本机隔离环境内操作，未安装 Turbo/加速插件，未下载 Ref2VA。

## 0. 授权与起点

| 项目 | 记录 |
|---|---|
| 起点提交 | `ce082e7c0146f3464e8551b559189a6c32f0aa6e` |
| 起点工作区 | 干净，`master` 与 `origin/master` 一致 |
| 运行环境 | `D:\AI\MiniMaxH3`，ComfyUI `63be2f9b82ad0dac88a7ceaa28a9cf3154125a18` |
| 模型 | 仅 FL2VA W6A8 + NVFP4-AWQ TE + 双 VAE（35,087,209,179 bytes） |

**授权来源**：第三阶段下载与生成是在“执行第三阶段：FL2VA 下载与基础验收”的直接指令下进行的；本轮补正是在“执行第三阶段补正”的指令下进行的。除这两条指令外，仓库中没有独立的书面审查批准记录，本报告不声称存在此类记录。

## 1. 脚本修复

### 1.1 install-runtime.ps1

**原缺陷**：首次克隆使用 `--no-checkout` 后立刻 `rev-parse HEAD` 并与目标提交比较，不等检出即抛错，首次安装永远到不了检出步骤；同时依赖 `--no-deps` 掩盖依赖完整性问题。

**修复**：

- 先判断目录状态：不存在才克隆；已存在则要求它是可用 git 仓库、工作区干净、且 HEAD 等于固定提交，否则**报错退出，不重置、不覆盖**。
- 检出动作提前到 HEAD 断言之前，并新增 `git fetch --depth 1 origin <commit>` 保证可检出。
- 用 `torch-constraints.txt` 约束 `torch/torchvision/torchaudio==2.10.0+cu130`，再由 `uv pip compile` 生成 `requirements.lock.txt`，用 `uv pip sync` 应用，**不再依赖 `--no-deps`**。
- 安装后断言 `torch.cuda.is_available()`，防止 CUDA 构建被替换。
- 新增 `-PlanOnly`，只打印将执行的步骤，不修改环境。

本轮**未重装现有环境**；现有环境通过 `uv pip check`（86 包全部兼容）与 `uv pip freeze` 记录确认。实际版本见 `reports/dependency-freeze.txt`。

### 1.2 patch-workflow-w6a8.py

**原缺陷**：把 `diffusion_models/minimax_h3_fl2va_pruned_w6a8.safetensors` 同时写进加载器和下载 URL，导致 `UNETLoader` 的值不在可选项内。

**修复**：加载器只用裸文件名，URL 使用带 `diffusion_models/` 的仓库路径并固定修订 `e5eb578a…`；此外把模板里其余仍指向 `/resolve/main/` 的 Comfy-Org 模型 URL 一并固定。新增 `verify()`，加载器含路径或 URL 未固定修订都会直接失败。

回归检查还暴露了一个**此前未发现的问题**：早期版本只改了扩散模型 URL，TE 与两个 VAE 仍指向 `main`。已修复并通过检查。

### 1.3 run-workflow.py

**原缺陷**：`history` 一旦出现条目就判定完成，且失败与超时都未明确区分退出码。

**修复**：

- 只有 `completed is True` 且 `status_str == 'success'` 才算完成；否则继续轮询。
- `completed` 为真但 `status_str` 不是成功 → 视为不一致，非零退出。
- 超时：记录 `running` 状态、队列长度、队列位置，退出码 3。
- 失败：记录服务端 `messages`，退出码 1。
- 提交被拒：记录 HTTP 状态与响应体，退出码 2。
- 成功任务额外检查 `SaveVideo` 产物是否真实存在：存在则写入路径、大小、SHA256；**不存在则记为 `success_without_output_file` 并退出码 4**，明确区分“任务完成”和“视频验收通过”。
- 每次运行写出证据记录：`prompt_id`、工作流 SHA256、提交时间、最终状态、耗时、产物定位。

## 2. 回归检查

`scripts/test-stage3b-fixes.py`，8 项全部通过：

```text
PASS test_install_script_checks_out_before_verifying
PASS test_install_script_refuses_dirty_existing_checkout
PASS test_patch_script_runs_end_to_end
PASS test_patch_uses_bare_loader_name_and_pinned_url
PASS test_patch_verify_rejects_path_in_loader_and_floating_url
PASS test_run_workflow_exits_nonzero_on_failure
PASS test_run_workflow_rejects_incomplete_then_accepts_success
PASS test_run_workflow_success_without_file_is_distinct
8 checks passed
```

覆盖点：首次检出的“检出先于断言”顺序、脏工作区拒绝、加载器名/URL 路径分离、URL 必须固定修订、未完成响应必须继续轮询、失败非零退出、成功但无产物必须区分。

## 3. 服务端节点与选项兼容性检查

用 `scripts/validate-ui-workflow.py` 针对运行中的服务端 `/object_info` 检查工作流引用的节点类型与模型取值：

| 工作流 | 子图 | UNETLoader 值 | 服务端缺失节点 | 结论 |
|---|---|---:|---|---|
| `video_minimax_h3_t2v_w6a8.json` | 1 | `minimax_h3_fl2va_pruned_w6a8.safetensors` | 无 | 通过 |
| `video_minimax_h3_i2v_w6a8.json` | 1 | `minimax_h3_fl2va_pruned_w6a8.safetensors` | 无 | 通过 |

**该检查的边界**：它能证明服务端注册了所需节点类型、且模型名在可选列表中。它**不能**证明前端实际完成了界面导入、子图在画布上正确展开、或节点连线在 UI 中可运行。本轮**未取得前端实际导入证据**，因此不声称“界面导入验收通过”。真正的端到端运行由第 5 节的 API 提交覆盖，那是独立证据。

- 唯一警告：Turbo LoRA 未安装。该 LoRA 仅在 `turbo_mode=true` 时使用，不阻止基础模式运行。
- 每个工作流的模型名、URL 文件名、目标目录和固定修订现在由 `verify()` 强制一致；新增回归 `test_patch_rewrites_url_file_name_to_w6a8` 与 `test_verify_detects_name_url_mismatch` 覆盖“名称 W6A8、URL INT8”这一缺陷。

## 4. 正式基线参数核实

| 参数 | 候选值 | 当前实现约束 | 结论 |
|---|---|---|---|
| 尺寸 | 736×416 | `width/height` 为 32 的倍数 | 有效 |
| 帧数 | 124 | `min 5 / max 3600 / step 17`，工具提示 124 ≈ 5 秒、训练区间约 124–362 | 有效，为训练下限 |
| 步数 | 20 | 无硬限制，官方默认 20 | 有效 |
| 帧率 | 24 | `CreateVideo.fps` | 有效 |

未使用 Turbo，因此 20 步为官方基线步数。

## 5. 正式基线结果

固定提示词、固定种子 12345、固定测试图片（736×416 几何图形，非私人素材）。

| 用例 | prompt_id | 耗时 | 产物 | 大小 (bytes) | 视频 SHA256 |
|---|---|---:|---|---:|---|
| T2V | `62827d6b-c13f-4572-9c32-36dd8d016d18` | 150.30 s | `baseline_t2v_00001_.mp4` | 304,926 | `e4fcc9bd8ee425700aa7ad1e025d45781151f13410d97bd776ce352c4299fecf` |
| I2V | `d718397d-0115-4482-b30b-e1c9f81e3b6a` | 140.81 s | `baseline_i2v_00001_.mp4` | 372,029 | `9dd7669ea26d44bc3e8cadc727495dde19eaeaa2da1a06de13aec2c2365aec0a` |
| 首尾帧 | `97d05235-c6db-4dd2-948e-7525ac1c843b` | 150.27 s | `baseline_flf_00001_.mp4` | 428,198 | `a105053054c20a517583cc33b1c4fbd879089ba99a7bfd03910079fd014629f0` |
| T2V 复跑 | `3d1439f4-eb11-4957-8fd1-bfe1c577acfd` | 130.20 s | `baseline_t2v_repeat_00001_.mp4` | 304,933 | `a6e4cf7053e327fc76c74377d166d915c03ccb2915f39d2862b0b7a2b31d14e3` |

工作流 SHA256（API 格式）：

- T2V `0a26dc51d6be97eabf12049ecc9e3dc51f6497daf069a126c4239eed6665f1aa`
- I2V `48656916548101f513249d6471e011c22f70525bbffcac4e7400a260341f36fb`
- 首尾帧 `5084805653c4130e024ed89decb0b4f65dd566b193b51359fba5e19752cbca4b`
- T2V 复跑 `ccde95bf412a2fd49c19e8f922d6412a015d3862ef55a38a9e70ab6062ded2c8`

复跑与首次 T2V 工作流内容仅文件前缀不同，因此 SHA 不同；提示词、种子、尺寸、帧数、步数完全一致。

## 6. 媒体核查（PyAV 实测）

三条正式产物规格一致：

| 项目 | 实测值 |
|---|---|
| 容器 | MP4（mov/mp4/m4a） |
| 视频编码 | H.264 |
| 尺寸 | 736 × 416 |
| 帧数 | 124 |
| 帧率 | 24 fps |
| 时长 | 5.167 s |
| 音轨 | 存在，AAC，32000 Hz，2 声道，5.167 s |

## 7. 资源采样

采样脚本 `scripts/sample-resources.ps1`，**标称间隔 2 秒**，同时记录 GPU 显存、GPU 利用率、ComfyUI 工作进程工作集/私有内存、系统可用物理内存、系统提交内存（`Win32_OperatingSystem` 推导，非 Committed Bytes 性能计数器）。

### 7.1 数据更正说明（2026-10-30）

初版本报告写的“337 个采样点、GPU 峰值 11,499 MiB、可用内存最低 1,552 MiB”**表述有误**，原因有两点，均已核实：

1. **提交的 CSV 不完整。** 提交时采样器仍在写入，快照只含前 150 行。现已提交完整 337 行（`reports/samples-t2v-baseline.csv`，时间跨度 04:11:10–04:23:13，本地时间 UTC+08:00）。
2. **峰值取自全程而非生成期。** 11,499 MiB 与 1,552 MiB 出现在生成结束后的空闲段，不能作为生成期峰值。

现按每个 `prompt_id` 的实际时间窗口重算，并由 `scripts/summarize-samples.py` 自动生成，区分生成期与前后空闲期。

### 7.2 采样间隔实测

| 用例 | 标称间隔 | 实测中位间隔 | 最大间隔 |
|---|---:|---:|---:|
| T2V 首次 | 2 s | 2.148 s | 2.288 s |
| T2V 复跑 | 2 s | 2.142 s | — |

采样本身有约 0.15 s 开销，因此实际间隔略大于标称值。

### 7.3 按窗口统计

| 用例 | 窗口 | 样本数 | GPU 峰值 | GPU 平均 | 进程工作集峰值 | 可用内存最低 | 提交内存峰值 |
|---|---|---:|---:|---:|---:|---:|---:|
| T2V 首次 | 生成期 | 70 | **11,404 MiB** | 10,428 MiB | 未采集（pid 错误） | **2,007 MiB** | 49,902 MiB |
| T2V 首次 | 生成前空闲 | 5 | 2,176 MiB | 2,135 MiB | — | 16,947 MiB | 27,177 MiB |
| T2V 首次 | 全程 | 337 | 11,499 MiB | 10,455 MiB | — | 1,552 MiB | 49,902 MiB |
| T2V 复跑 | 生成期 | 61 | **11,469 MiB** | — | **18.72 GiB** | **2,024 MiB** | 48,679 MiB |
| T2V 复跑 | 生成前空闲 | 6 | 10,188 MiB | — | 16.88 GiB | 3,925 MiB | 45,049 MiB |

结论修正：

- 生成期 GPU 峰值约为 **11.4 GiB / 12.2 GiB**，不是 11,499 MiB。
- 生成期可用物理内存最低约 **2.0 GiB**，余量很小。
- 提交内存峰值约 48–49 GiB，超过 31.16 GiB 物理内存，说明运行依赖页面文件；但**提交量不等于实际换页量**，本轮未采集 `Committed Bytes` 与 `Commit Limit` 性能计数器，也未采集页面文件读写速率，因此不能据此判定换页程度。
- 未发生 OOM。
- 进程内存只对复跑用例有效：首次用例的 pid 文件指向 ComfyUI 父进程（工作集 4.3 MiB），已在复跑前修正到实际工作进程。

## 8. 冷启动与缓存

- 首次 T2V 含模型初始化，150.30 s；复跑 130.20 s。两者都触发了实际采样（前后 `/prompt` 新 `prompt_id`，GPU 利用率观察到 99%），非节点缓存命中。
- 复跑更快主要来自模型已在显存/页面缓存中，属于正常差异，未据此计算“加速比”。
- 本轮未单独测“重启后冷启动”，因此不提供冷启动对比数据。

## 9. 未通过 / 待确认

- **画质与听感未评估**：未实际观看画面或试听音轨。API `success` 与规格核查不等于质量合格。
- I2V 与首尾帧未单独做资源采样，仅有 T2V 两组完整采样。
- 未测试 ≥362 帧、更高分辨率、Turbo、Ref2VA。
- 进程内存峰值仅复跑用例有效。

## 10. 复现步骤

```powershell
# 1. 资源采样（另开窗口）
powershell -File scripts\sample-resources.ps1 -IntervalSeconds 2 `
  -OutFile D:\AI\MiniMaxH3\samples\t2v.csv

# 2. 生成 API 工作流
python scripts\build-h3-api-workflow.py --output workflows\baseline_t2v_api.json `
  --width 736 --height 416 --length 124 --steps 20 --prefix h3/baseline_t2v `
  --prompt "A single red ball rests on a plain wooden table ..."

# 3. 提交并记录证据
python scripts\run-workflow.py --workflow workflows\baseline_t2v_api.json `
  --record D:\AI\MiniMaxH3\records\t2v.json --label t2v_baseline --timeout 5400

# 4. 规格核查
python scripts\probe-media.py D:\AI\MiniMaxH3\ComfyUI\output\h3\baseline_t2v_00001_.mp4
```

证据文件：`reports/evidence/*.json`、`reports/samples-t2v-baseline.csv`、`reports/samples-t2v-repeat.csv`、`reports/dependency-freeze.txt`。

本地视频：`D:\AI\MiniMaxH3\ComfyUI\output\h3\`。
