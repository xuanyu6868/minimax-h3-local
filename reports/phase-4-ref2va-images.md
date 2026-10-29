# 第四阶段：Ref2VA 受控验收（参考图）

日期：2026-10-30。依据：负责人转述的 ChatGPT 对 `f242fdb` 的审查意见与后续指令「执行第三阶段最终补正＋第四阶段 Ref2VA 受控验收」。

本轮只在本机隔离环境内操作，未改动全局 Python、系统 CUDA Toolkit、显卡驱动、页面文件配置或系统环境变量。

## 1. 起点与范围

| 项目 | 值 |
|---|---|
| 起点提交 | `f242fdb` |
| ComfyUI | v0.42.1，`63be2f9b82ad0dac88a7ceaa28a9cf3154125a18` |
| PyTorch | 2.10.0+cu130 |
| 模型集 | Ref2VA W6A8 + NVFP4-AWQ TE + 双 VAE |
| 本轮测试 | 单参考图、双参考图 |
| 未测 | 参考视频、参考音频、`ref_image_size=max`、≥362 帧、更高分辨率 |

## 2. 第三阶段最终补正

### 2.1 W6A8 下载地址缺陷

**问题**：模板里 W6A8 的 `models[].url` 文件名是 `minimax_h3_fl2va_pruned_w6a8.safetensors`，但 `name` 与加载器使用的文件名不同时，早期补丁脚本只固定了修订号，URL 仍指向旧文件名，实际下载会 404。

**修复**：`scripts/patch-workflow-w6a8.py` 改为强制规范路径——只要命中默认 int8 模型或已出现 W6A8 文件名，就同时写入 `name`、`directory`、`url` 三处，由 `verify()` 断言加载器名、URL 文件名、目录与修订四处一致。

新增回归检查：

- `test_patch_rewrites_url_file_name_to_w6a8`：构造"URL 指向 `main` 且文件名不同"的节点，断言改写后 URL 文件名为 W6A8。
- `test_verify_detects_name_url_mismatch`：构造文件名不一致的工作流，断言 `verify()` 报错。
- `test_committed_workflows_are_consistent`：对已入库的两个 UI 工作流跑 `verify()`。

`scripts/test-stage3b-fixes.py` 现共 11 项，全部通过（见第 6 节）。

### 2.2 资源数据更正

**问题**：初版报告写"337 个采样点、GPU 峰值 11,499 MiB、可用内存最低 1,552 MiB"，但提交的 CSV 只有 150 行，且两个极值都取自生成结束后的空闲段。

**复核**：提交时采样器仍在写入，快照不完整。现按每个 `prompt_id` 的实际时间窗口由 `scripts/summarize-samples.py` 重算，区分生成期与前后空闲期。生成期 GPU 峰值 **11,404 MiB**，可用物理内存最低 **2,007 MiB**。完整 337 行 CSV 已入库。

### 2.3 `/object_info` 检查的边界

原报告"界面工作流实际导入验证通过"表述过强。`/object_info` 只证明服务端注册了节点类型、模型名在可选列表内，**不能**证明前端完成界面导入、子图在画布上正确展开或节点连线在 UI 中可运行。报告第 3 节已改名为"服务端节点与选项兼容性检查"并说明该边界。本轮**未取得前端实际导入证据**，因此不再声称界面导入通过。

### 2.4 安装可复现性

- `requirements.lock.txt`（86 包）已入库，`uv pip install --dry-run -r requirements.lock.txt` 返回 `Would make no changes`。
- `scripts/install-runtime.ps1` 改为**默认使用已验证的锁文件**；需要重新解析依赖时必须显式传 `-Relock`。
- 重装后追加 CUDA 断言：若 `requirements.txt` 再次把 CUDA 版 PyTorch 换成 CPU 版，脚本立即失败。

### 2.5 提交内存与页面文件（只读）

`scripts/sample-resources.ps1` 新增 `committed_MiB` 与 `commit_limit_MiB` 两列，取自 `Win32_PerfRawData_PerfOS_Memory` 的 `CommittedBytes` / `CommitLimit`。原有 `os_commit_MiB` 是 `TotalVirtualMemorySize - FreeVirtualMemory`，口径不同，两者并列记录、互不替代。

`scripts/record-host-commit.py` 只读记录主机配置，未做任何修改：

| 项目 | 值 |
|---|---|
| 物理内存 | 31,903.9 MiB |
| Commit Limit | 41,119.9 MiB |
| 差值（即页面文件可用量） | 9,216 MiB |
| 页面文件 | `C:\pagefile.sys`，已分配 9,216 MiB，当前使用 850 MiB，峰值 1,563 MiB（累计，非本轮） |
| 自动管理 | 是（`AutomaticManagedPagefile=True`） |

副作用提示：本轮生成期间提交内存峰值 **49,097–49,162 MiB**，高于本轮观察到的 CommitLimit 最低值 41,120 MiB。这不矛盾——CommitLimit 随页面文件动态扩张而调整。单图那一轮 CSV 里 CommitLimit 的取值区间是 41,119.9–50,441.3 MiB，可见上限被抬高了约 9.3 GiB，峰值时刻的实际上限高于 41,120 MiB。**结论：运行确实依赖页面文件扩张**，但本轮未采集页面文件读写速率，因此不能量化换页程度。

## 3. 运行环境切换

FL2VA 与 Ref2VA 是两个独立权重文件（各 15,983,746,636 bytes）。ComfyUI 会缓存已加载的 checkpoint 直到进程退出，因此**切换模型集必须重启进程**，而不是换节点参数。

`scripts/start-comfyui.ps1` 新增 `-ModelSet fl2va|ref2va`，启动前把以下内容写入 `D:\AI\MiniMaxH3\launch-args.json`：

```json
{
  "captured_at_utc": "2026-10-29T21:27:18.8978702Z",
  "model_set": "ref2va",
  "comfyui_commit": "63be2f9b82ad0dac88a7ceaa28a9cf3154125a18",
  "python": "3.12.10",
  "torch": "2.10.0+cu130",
  "launch_command": "D:\\AI\\MiniMaxH3\\.venv\\Scripts\\python.exe D:\\AI\\MiniMaxH3\\ComfyUI\\main.py --listen 127.0.0.1 --port 8188 --disable-auto-launch --reserve-vram 1.0",
  "unloaded_model": "minimax_h3_fl2va_pruned_w6a8.safetensors",
  "unloaded_size": 15983746636
}
```

`/system_stats` 返回的 `argv` 与 `launch_command` 一致，可交叉核对。两轮 Ref2VA 测试均在同一个 Ref2VA 进程内完成，未同时加载 FL2VA。

## 4. 节点 schema（运行时实测）

`scripts/dump-node-schema.py` 直接读运行中的 `/object_info`，不做任何推断。

`MiniMaxH3ReferenceToVideo`：

| 输入 | 类型 | 约束 |
|---|---|---|
| `clip` | CLIP | 必填 |
| `prompt` | STRING | 多行，支持 `<Picture i>` / `<Video k>` / `<Audio j>` 标签 |
| `width` / `height` | INT | 默认 1344 / 768，step 32 |
| `length` | INT | 默认 124，min 5，max 3600，step 17 |
| `ref_image_size` | COMBO | `match` / `max`，默认 `match` |
| `vae` / `audio_vae` | VAE | 可选；缺 video VAE 时参考图只作用于文本编码器 |
| `ref_images` | COMFY_AUTOGROW_V3 | 前缀 `ref_image_`，0–9 个 |
| `ref_videos` | COMFY_AUTOGROW_V3 | 前缀 `ref_video_`，0–3 个 |
| `ref_video_audios` | COMFY_AUTOGROW_V3 | 前缀 `ref_video_audio_`，与同序号参考视频配对 |
| `ref_audios` | COMFY_AUTOGROW_V3 | 前缀 `ref_audio_`，0–3 个 |

输出：`positive`(CONDITIONING)、`LATENT`。

**API 键名**：Autogrow 输入在 API 格式里必须写成 `ref_images.ref_image_1`、`ref_images.ref_image_2` 这样的带组前缀形式。依据是 `comfy_api/latest/_io.py` 的 `Autogrow._expand_schema_for_dynamic()`（`expected_id = finalize_prefix(curr_prefix, name)`）与 `build_nested_inputs()`（按 `.` 拆分路径重建嵌套字典）。实测被服务端接受，确认该结论。

## 5. 受控测试结果

固定条件：736×416、124 帧、20 步、24fps、种子 12345、`res_multistep` + `simple` 调度、`ref_image_size=match`、未用 Turbo、一次只跑一个任务。

### 5.1 单参考图

- 参考图：`h3_first.png`（736×416 几何图形，非私人素材）
- 提示词：`The object in <Picture 1> sits on a plain wooden table in soft daylight. A slow, steady camera push-in reveals its shape; ambient room tone only.`

| 项目 | 值 |
|---|---|
| prompt_id | `a0acf8c9-6e56-452a-9761-56a1847dcc3f` |
| 工作流 SHA256 | `0a220bd975b38190bdc7a9088e0d01e15f613768e338dcd5a872a2ef9b277485` |
| 耗时 | 160.72 s |
| 产物 | `ref2va_single_00001_.mp4`，719,282 bytes |
| 视频 SHA256 | `f32bc5c8a6222b70bab941551753dad79ad3d1d4f099a58fe69467a6ca6c32bb` |
| 规格实测 | H.264 736×416，124 帧，24 fps，5.167 s；AAC 32 kHz 双声道 5.167 s |

### 5.2 双参考图

- 参考图：`<Picture 1>` = `h3_first.png`（红色圆形），`<Picture 2>` = `h3b_last.png`（蓝色圆形）
- 提示词显式标注两个角色：`Picture 1 shows a circular red object and <Picture 2> shows a circular blue object; ... the <Picture 1> shape slides slowly to the right while the <Picture 2> shape slides slowly to the left, then they settle side by side.`

| 项目 | 值 |
|---|---|
| prompt_id | `5e13e2d1-1c67-42e4-8db6-70c7c0416660` |
| 工作流 SHA256 | `18972e534df48f08c6534088bebd866fff98eab52170de36a730d234d9af8126` |
| 耗时 | 170.23 s |
| 产物 | `ref2va_dual_00001_.mp4`，270,221 bytes |
| 视频 SHA256 | `f6353057a4699f975bc570cebaf63658d5fa26862ffb5d992be4fe148d1e3ec1` |
| 规格实测 | H.264 736×416，124 帧，24 fps，5.167 s；AAC 32 kHz 双声道 5.167 s |

两条任务都是 `completed=true` 且 `status_str=success`，并在产物目录定位到真实文件后记录大小与 SHA256。**服务端成功与规格正确不等于画面符合提示词**——本轮未逐帧检查是否真的出现红色与蓝色两个对象及其运动方向。

## 6. 回归检查

```text
$ python scripts/test-stage3b-fixes.py
PASS test_committed_workflows_are_consistent
PASS test_install_script_checks_out_before_verifying
PASS test_install_script_refuses_dirty_existing_checkout
PASS test_patch_rewrites_url_file_name_to_w6a8
PASS test_patch_script_runs_end_to_end
PASS test_patch_uses_bare_loader_name_and_pinned_url
PASS test_patch_verify_rejects_path_in_loader_and_floating_url
PASS test_run_workflow_exits_nonzero_on_failure
PASS test_run_workflow_rejects_incomplete_then_accepts_success
PASS test_run_workflow_success_without_file_is_distinct
PASS test_verify_detects_name_url_mismatch
11 checks passed
```

## 7. 资源占用（按生成窗口）

采样间隔标称 2 s，实测中位间隔 2.17 s。

| 用例 | 窗口 | 样本 | GPU 峰值 | GPU 平均 | GPU 利用率平均 | 进程工作集峰值 | 进程私有峰值 | 可用内存最低 | Committed 峰值 | CommitLimit 最低 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Ref2VA 单图 | 生成期 | 73 | **11,504 MiB** | 10,083 MiB | 81.7% | 18,064 MiB | 27,792 MiB | **1,295 MiB** | **49,097 MiB** | 41,120 MiB |
| Ref2VA 单图 | 生成前空闲 | 9 | 1,787 MiB | 1,695 MiB | 6.0% | 966 MiB | 2,464 MiB | 19,022 MiB | 23,649 MiB | 41,120 MiB |
| Ref2VA 双图 | 生成期 | 78 | **11,449 MiB** | 10,381 MiB | 84.7% | 18,199 MiB | 28,096 MiB | **1,160 MiB** | **49,162 MiB** | 41,120 MiB |
| Ref2VA 双图 | 生成前空闲 | 9 | 1,720 MiB | 1,605 MiB | 7.6% | 955 MiB | 2,455 MiB | 19,010 MiB | 23,925 MiB | 41,120 MiB |

对照 FL2VA 正式基线（第三阶段，736×416/124 帧/20 步）：生成期 GPU 峰值 11,404 MiB、可用内存最低 2,007 MiB。

结论：

- Ref2VA 单图/双图在相同规格下与 FL2VA 显存占用同级（峰值 11.4–11.5 GiB / 12.2 GiB）。
- **平均值与峰值方向相反，不能混写**：双图生成期 GPU 平均值比单图**高 298 MiB**（10,381 vs 10,083 MiB），但**峰值比单图低 55 MiB**（11,449 vs 11,504 MiB）。系统可用内存最低值双图再低约 135 MiB。三项差异都在百 MiB 量级，属同一水平，不据此推断复杂度曲线。
- 双图耗时 170.23 s 比单图 160.72 s 增加 9.51 s（+5.9%）。
- 生成期可用物理内存最低降到 1,160 MiB，余量很小；未发生 OOM，也未观察到驱动重置。
- 两轮进程工作集与私有内存峰值接近，说明当前驻留策略稳定。
- 本轮启用默认的 pinned memory。后续实验（见 [阶段四 B](phase-4b-stability-ui-audio.md)）表明禁用该项可把提交峰值从 49,345 MiB 降到 38,245 MiB。

## 8. 未通过 / 待确认

- **画面与听感未确认**：未逐帧检查参考图身份保持、双图角色是否正确分离、运动方向是否符合提示词，也未试听音轨。
- **界面路径未验证（后续已证实失败）**：`reports/phase-4b-stability-ui-audio.md` 第 5 节显示，从画布提交 Ref2VA 会因 `ref_image_1` 扁平键报 `TypeError`。本轮全部结果都来自 API 形式。
- **参考视频未测**：`ref_videos` / `ref_video_audios` 两条通路本轮完全未覆盖。参考音频已由 [阶段四 B](phase-4b-stability-ui-audio.md) 补测。
- **`ref_image_size=max` 未测**：工具提示称可显著提升身份保真但可能慢数倍，本轮只用 `match`。
- **未测 ≥362 帧、更高分辨率、Turbo、LoRA**。
- **未量化换页**：只记录了提交量与上限，未采集页面文件读写速率。
- **前端界面导入当时无证据**：本轮所有提交都走 API，UI 格式工作流仅做服务端兼容性检查。实际导入已在 [阶段四 B](phase-4b-stability-ui-audio.md) 补齐，并暴露了 Ref2VA 的界面提交缺陷。
- **提示词副作用未排除**：单图提示词含 "wooden table"，而参考图是纯几何图形；若画面上出现木桌，需按提示词与参考图冲突来解释，不能归为模型缺陷。

## 9. 复现步骤

```powershell
# 1. 下载并校验 Ref2VA
powershell -File scripts\download-fl2va.ps1 -Ref2VA

# 2. 以 Ref2VA 模型集重启（同时写入 launch-args.json）
powershell -File scripts\start-comfyui.ps1 -ModelSet ref2va

# 3. 核实节点 schema
python scripts\dump-node-schema.py MiniMaxH3ReferenceToVideo

# 4. 生成单参考图工作流
python scripts\build-h3-api-workflow.py --output workflows\ref2va_single_ref_api.json `
  --width 736 --height 416 --length 124 --steps 20 --prefix h3/ref2va_single `
  --unet minimax_h3_ref2va_pruned_w6a8.safetensors --ref-image h3_first.png `
  --prompt "The object in <Picture 1> sits on a plain wooden table in soft daylight. ..."

# 5. 采样 + 提交
powershell -File scripts\sample-resources.ps1 -OutFile D:\AI\MiniMaxH3\samples\ref2va_single.csv
python scripts\run-workflow.py --workflow workflows\ref2va_single_ref_api.json `
  --record D:\AI\MiniMaxH3\records\ref2va_single.json --label ref2va_single --timeout 3600

# 6. 规格与资源汇总
python scripts\probe-media.py D:\AI\MiniMaxH3\ComfyUI\output\h3\ref2va_single_00001_.mp4
python scripts\summarize-samples.py --csv D:\AI\MiniMaxH3\samples\ref2va_single.csv `
  --record D:\AI\MiniMaxH3\records\ref2va_single.json --interval 2
```

证据文件：`reports/evidence/ref2va_single.json`、`reports/evidence/ref2va_dual.json`、`reports/evidence/host-commit.json`、`reports/samples-ref2va-single.csv`、`reports/samples-ref2va-dual.csv`。

本地视频：`D:\AI\MiniMaxH3\ComfyUI\output\h3\ref2va_single_00001_.mp4`、`ref2va_dual_00001_.mp4`。
