# 第四阶段 C：修通 Ref2VA 界面并完成可用性收尾

日期：2026-10-30。依据：负责人转述的 ChatGPT 对 `16f8998` 的审查意见。

本轮优先交付可直接使用的界面。未修改 ComfyUI 源码、后端请求、驱动、页面文件或系统环境变量，也未重装依赖。

## 1. 三项结论（分开判断）

| 项目 | 结果 | 依据 |
|---|---|---|
| Ref2VA 界面 | **通过** | 单图与双图均从画布提交成功，刷新重导入后连接与参数保留 |
| 中断流程 | **通过** | 回放验证阈值逻辑；真实任务被中断且核实确实停止 |
| 回归检查 | **通过** | 17 项全部实跑通过（此前为 10 过 1 失败） |

画质、听感、参考视频、`ref_image_size=max` 仍未验证，见第 6 节。

## 2. 先更正上一轮的三处错误

ChatGPT 复核 `16f8998` 时指出三点，全部成立：

1. **Ref2VA 界面报错是我自己的转换器缺陷，不是上游问题。**
   `build-ui-workflow.py` 里的 `RENAME` 表主动把 `ref_images.ref_image_1` 改写成 `ref_image_1`，
   丢掉了 Autogrow 分组路径。仓库里的官方 R2V 模板一直保留完整前缀，我没有对照。
   上一轮把它归为"上游缺陷"是错误归因。

2. **"中断监测已实现"是误报。**
   上一轮只做了事后阈值统计（`summarize-samples.py` 里数一数有几个样本越线），
   没有任何发出中断请求的代码。报告写"按指令本轮只观察记录"，把"没实现"说成了"合规选择"。

3. **回归检查当时是 10 通过 1 失败，不是 11 全过。**
   `test_install_script_checks_out_before_verifying` 仍在查找我已删除的分支字符串
   `$Relock -or -not (Test-Path $verifiedLock)`。我改了实现没同步测试，且汇报时没有重跑。

## 3. Ref2VA 界面修复

### 3.1 找到权威序列化

不靠推断，直接在原生画布上新建 `MiniMaxH3ReferenceToVideo` 节点，读前端自己填出来的输入：

```text
name = "ref_images.ref_image_0"   shape = 7   type = IMAGE
name = "ref_videos.ref_video_0"   shape = 7
name = "ref_video_audios.ref_video_audio_0"
name = "ref_audios.ref_audio_0"
```

同时对照仓库官方模板 `workflows/video_minimax_h3_r2v.json` 的节点 136：同样是
`name="ref_images.ref_image_0"`、`shape=7`、`label="ref_image_0"`。

由此确认两件事：

- **必须保留完整分组路径**，`label` 只是界面显示名；
- **槽位编号从 0 开始**（schema 里 `names = [f"{prefix}{i}" for i in range(max)]`）。

第二点是我此前的另一个错误：API 工作流一直用 `ref_image_1` 起步。它"能跑通"只是因为
Autogrow 的 `min=0` 允许从任意序号起，但序号与提示词里的 `<Picture N>` 对应关系会整体错位一格。

### 3.2 修复内容

`scripts/build-ui-workflow.py`：

- 删除 `RENAME` 表，改为 `socket_for()`：保留 `group.field` 原名，补 `label`，标 `shape=7`；
- 新增 `verify()`：裸名（如 `ref_image_0`）、未知分组、缺 `shape=7` 一律报错，不再靠人工检查；
- 补上 `LoadAudio` 的槽位定义（原表缺失，导致参考音频无法转成 UI 图）；
- `last_node_id` 用 `max(节点 id)` 而非节点数量。

`scripts/build-h3-api-workflow.py`：Autogrow 槽位改为零基编号，并注明提示词里的 `<Picture 1>`
仍对应第 0 号槽位——那是模型侧编号，与节点槽位编号是两套体系。

生成的对照文件 `workflows/native_ref2va_single_serialized.json` 由前端 `graph.serialize()` 直接写出，
不含任何人工编辑。

### 3.3 验证

| 检查 | 单图 | 双图 |
|---|---|---|
| 导入节点数 / 连线数 | 15 / 19 | 16 / 20 |
| `graphToPrompt()` 输出键 | 含 `ref_images.ref_image_0` | 含 `ref_images.ref_image_0`、`ref_images.ref_image_1` |
| 已连接槽位 | clip, vae, audio_vae, ref_images.ref_image_0 | 另加 ref_images.ref_image_1 |
| 提交结果 | `success` | `success` |
| prompt_id | `03fa592b-6d55-4a7e-8eab-48e8f5342505` | `3253dbd2-f86c-4fee-8d52-92877bab732b` |
| 产物 | `ref2va_single_00004_.mp4`，720,158 B | `ref2va_dual_00002_.mp4`，271,145 B |

刷新页面后重新导入：分组路径、四条参考槽位连线、`prompt`/`width 736`/`height 416`/`length 124`/`ref_image_size match`
全部保留。截图见 `reports/evidence/ui/ref2va-ui-fixed-dual.png`。

T2V 界面提交在上一轮已通过（`3be89230`，`baseline_t2v_00002_.mp4`，305,754 B），本轮保留为对照。

## 4. 低内存预设固化

`scripts/start-comfyui.ps1` 改为默认带 `--disable-pinned-memory`，`-EnablePinnedMemory` 是显式对照开关。
启动时打印实际 argv，并把 `pinned_memory` 字段写入 launch JSON。实测记录：

```text
reported_argv: main.py --listen 127.0.0.1 --port 8188 --disable-auto-launch --reserve-vram 1.0 --disable-pinned-memory
pinned_memory: disabled (project default)
```

依据仍是 `16f8998` 那组数据：同一工作流、同一输入，提交峰值 49,345 → 38,245 MiB，
最小提交余量 420 → 2,934 MiB，产物 SHA256 完全相同。

## 5. 主动中断

### 5.1 实现

新增 `scripts/guard-memory.py`，独立进程，只读性能计数器 + 查询队列：

- 提交余量（`CommitLimit − CommittedBytes`）< 512 MiB → 立即中断；
- 提交占比连续两次采样 ≥ 97% → 中断；
- **采样失败不作为健康解**：读数丢弃、记入 `read_errors`，连续计数清零；
- 中断前先确认目标任务的身份：在排队则从 `/queue` 删除该 `prompt_id`；确在运行才调 `/interrupt`；
  两者都不是则不动作。
- 中断后轮询 `/queue` 直到目标确实消失（`wait_for_stop`），不是发完就假设成功。

### 5.2 阈值逻辑验证（回放读数，不消耗内存）

| 输入序列 | 期望 | 实际 |
|---|---|---|
| 比值 0.7285 → 0.9738 → 0.9762 | 第 3 个样本才中断 | 前两个 `hold`（streak 1），第三个 `interrupt`（streak 2） |
| 余量 2,179 → 379 MiB | 第二个样本立即中断 | `hold` → `interrupt`，理由 `headroom 379.0 MiB < 512.0 MiB` |
| 中间夹一个 `null` 读数 | 不当作健康，连续计数清零 | `action=hold`，`streak=0`，理由 `no usable sample` |

### 5.3 真实中断（内存充足时触发，不制造危险条件）

```text
prompt_id: d99630fe-53b8-49f5-b787-3953bda3113d
before_interrupt: running = true
interrupt_request: method = interrupt, was_running = true, was_pending = false
stopped: true
final_status: status_str = error, completed = false, interrupted = true
message_kinds: execution_start, execution_cached, execution_interrupted
verified_stopped: true
```

中断后服务仍能正常响应 `/system_stats`，argv 未变。该记录的 `note` 字段已写明
"阈值被刻意绕过，本测试证明中断通路，不是真实的低内存事件"，避免与正常基线混淆。

## 6. 输入素材真实规格

不沿用旧报告文字，用 PyAV 实测（`reports/evidence/input-assets.json`）：

| 文件 | 实测规格 | bytes | SHA256 |
|---|---|---:|---|
| `h3_first.png` | **320 × 320** PNG | 1,656 | `eaa7e9a818fcb0d60b358e8338415eaafab5091bd612b39a830e0b74ccb387a8` |
| `h3b_last.png` | 736 × 416 PNG | 2,525 | `4694187025783d6995af5c3094bc351cf2f810fd1a3ff9013216ff0e4d4be3cc` |
| `h3_ref_tone.wav` | 32,000 Hz 单声道 | 192,044 | `e1a4cc0766225a05288c96e08feb530b82002984de8f03be2344a9e253f91d89` |

两点说明：

- 早前报告把 `h3_first.png` 笼统写成"736×416 几何图形"，实测是 **320×320**，屏幕短边不足，参考图会被
  `ref_image_size=match` 放大到接近生成像素面积，与 `max` 的差异可能因此被削弱。旧描述已更正。
- 单图提示词里含 "wooden table"，但参考图只是纯色几何图形；若画面出现木桌，是提示词与参考图冲突，
  不是模型缺陷。

## 7. 回归检查（真实结果）

```text
$ python scripts/test-stage3b-fixes.py
PASS test_api_builder_uses_zero_based_autogrow_slots
PASS test_committed_workflows_are_consistent
PASS test_guard_rule_thresholds
PASS test_install_script_checks_out_before_verifying
PASS test_install_script_refuses_dirty_existing_checkout
PASS test_install_script_uses_repo_lock_and_refuses_implicit_resolve
PASS test_patch_rewrites_url_file_name_to_w6a8
PASS test_patch_script_runs_end_to_end
PASS test_patch_uses_bare_loader_name_and_pinned_url
PASS test_patch_verify_rejects_path_in_loader_and_floating_url
PASS test_run_workflow_exits_nonzero_on_failure
PASS test_run_workflow_rejects_incomplete_then_accepts_success
PASS test_run_workflow_success_without_file_is_distinct
PASS test_start_script_defaults_to_low_memory_preset
PASS test_ui_converter_keeps_autogrow_group_path
PASS test_ui_verify_rejects_stripped_group_path
PASS test_verify_detects_name_url_mismatch
17 checks passed
```

新增的 5 项针对本轮缺陷，其中 `test_ui_converter_keeps_autogrow_group_path` 与
`test_ui_verify_rejects_stripped_group_path` 在编写时**先失败过**：一次暴露转换器缺 `LoadAudio`、
一次暴露 `verify()` 把裸名判错（`rstrip('_')` 生成了 `ref_image0` 而不是 `ref_image_0`）。两处都已修掉。

## 8. 交付

- 启动入口：`scripts/start-comfyui.ps1`（默认低内存）
- 使用说明：[USAGE.md](../USAGE.md)
- UI 工作流：`workflows/ui_t2v_controlled.json`、`ui_ref2va_single_controlled.json`、`ui_ref2va_dual_controlled.json`
- 对照序列化：`workflows/native_ref2va_single_serialized.json`
- API 对照工作流仍保留：`workflows/*_api.json`

## 9. 未通过 / 未验证

- **画质未验证**：未逐帧核对参考图身份保持、双图角色分离、运动方向。
- **听感未验证**：未试听任何音轨。
- **参考视频通路未测**：`ref_videos` / `ref_video_audios`。
- **`ref_image_size=max` 未测**。
- **多音频（≥2）与音频+视频组合未测**。
- **换页量未量化**：仍只有提交量与上限。
- **中断只验证了"能中断"**：真实低内存场景下由规则自动触发的中断未发生过（真实测试是刻意绕过阈值触发的）。
- **每档预设仍只有 1 次运行**，不构成统计结论。
