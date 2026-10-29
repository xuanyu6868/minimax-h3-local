# 第四阶段 B：内存稳定性、界面交付与参考音频

日期：2026-10-30。依据：负责人转述的 ChatGPT 对 `a665118` 的审查意见。

> **勘误提示（2026-10-30，阶段四 C 追加）**
> 本报告原认定"Ref2VA 界面提交失败属于上游缺陷"，该归因**错误**。实际原因是
> `scripts/build-ui-workflow.py` 里的 `RENAME` 表主动把 `ref_images.ref_image_1` 改写成
> `ref_image_1`，丢了 Autogrow 分组路径。已修复，界面提交现已通过，详见
> [阶段四 C](phase-4c-ui-ready.md) 第 3 节。
> 另外，本报告使用的 Autogrow 槽位编号是从 1 开始，也是错的：schema 与官方模板都是零基。
> 两处均已在阶段四 C 更正并加了回归检查。

本轮只在本机隔离环境内操作，未修改系统页面文件、显卡驱动或全局环境变量。

## 1. 结论速览（按维度分开，不合并成"通过"）

| 维度 | 结论 | 依据 |
|---|---|---|
| 运行通过 | T2V 界面提交、Ref2VA 单图 API、参考音频对照与实验均 `completed=true` + `status_str=success`，产物真实存在 | 第 5、6 节 |
| 资源条件通过 | 仅在使用 `--disable-pinned-memory` 时成立：Committed 峰值 38,245 MiB、最小提交余量 2,934 MiB、零阈值突破 | 第 3、4 节 |
| 界面通过 | **当时未通过**（Ref2VA 报 `TypeError`），归因有误，已在阶段四 C 修通 | 第 5 节 |
| 画质通过 | **未验证**。未逐帧检查画面与提示词、参考图的一致性 | 第 7 节 |
| 听感通过 | **未验证**。未试听任何音轨 | 第 7 节 |

## 2. 修正上一轮报告的口径错误

`reports/phase-4-ref2va-images.md` 原写"双图比单图多约 300 MiB 显存"。查原始数据：

| 用例 | 生成期 GPU **平均** | 生成期 GPU **峰值** |
|---|---:|---:|
| Ref2VA 单图 | 10,083 MiB | 11,504 MiB |
| Ref2VA 双图 | 10,381 MiB | 11,449 MiB |

平均值高 298 MiB，但**峰值反而低 55 MiB**。原句把平均值差异写成了笼统的"显存占用"，容易被读成峰值。该报告已改为分别标注平均值与峰值，并说明峰值方向相反。这是口径错误，不是测量错误。

## 3. 安装与启动脚本修正

### 3.1 锁文件按脚本位置解析

原先 `install-runtime.ps1` 从 `$Root`（`D:\AI\MiniMaxH3`）找锁文件，但仓库实际的锁文件在 `d:\Minimax H3`，两侧路径不同。现在改为：

```powershell
$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
$LockFile = Join-Path $RepoRoot 'requirements.lock.txt'
$ConstraintsFile = Join-Path $RepoRoot 'torch-constraints.txt'
```

- 默认必须存在 `requirements.lock.txt`，缺失即报错退出，不再隐式重新解析。
- 只有显式 `-Relock` 才调用 `uv pip compile`，且 `torch-constraints.txt` 缺失时同样报错。
- 本轮**未重装**现有环境，只验证逻辑。

### 3.2 启动前检查已有服务

原脚本直接启动，可能连到旧服务上而不自知，PID 文件也可能记错进程。新逻辑：

1. 用 `Get-NetTCPConnection -LocalPort 8188 -State Listen` 取监听进程，而不是猜父子关系。
2. 发现已有监听时打印其命令行；不传 `-StopExisting` 就**报错退出**，不会静默连接。
3. 传 `-StopExisting` 才停止，并循环等待端口真正释放。
4. 启动后以**监听端口的进程**作为 `server_pid` 写入 `comfyui.pid` 和 launch JSON。

这里有一个容易误判的细节：`D:\AI\MiniMaxH3\.venv\Scripts\python.exe` 启动后，实际服务进程是运行在基础解释器下的子进程（本机为 `C:\Users\<user>\...\Python312\python.exe`）。`.venv\pyvenv.cfg` 的 `home` 就指向它，`include-system-site-packages = false`，因此这是 venv 的正常转发，不是用到全局环境。判断隔离性要看 `torch` 版本（`2.10.0+cu130`），而不是看父进程的 exe 路径。上一轮我把 pid 文件写成了这套转发链的末端，本轮已修正为监听进程。

### 3.3 不把"未加载"写成"已卸载"

上一版 launch JSON 里预填了 `unloaded_model`，读起来像"已确认卸载"。现在该字段改名为 `other_model_present_on_disk` / `other_model_file`，含义只是"这个文件本次没有加载"，并注明：卸载只能由运行窗口内的显存/工作集读数证明。

## 4. 内存预设对比（一次只改一项）

`main.py --help` 的原始输出确认了 `--disable-pinned-memory` 存在，且默认日志会打印 `Enabled pinned memory 12761.0`。本轮只改这一项，其他参数保持 `--reserve-vram 1.0` 等不变。

测试条件固定：Ref2VA 单参考图、`ref_image_size=match`、736×416、124 帧、20 步、24fps、种子 12345。

| 用例 | 预设 | 耗时 | GPU 峰值 / 平均 | 进程工作集峰值 | 进程私有峰值 | 可用内存最低 | Committed 峰值 | 最小提交余量 | 最高提交占比 | 破阈样本 / 最长连续 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| preset_baseline | 默认（pinned 启用） | 156.37 s | 11,485 / 10,868 MiB | **18,715 MiB** | **28,586 MiB** | 1,879 MiB | **49,345 MiB** | **420 MiB** @05:56:07 | **0.9913** | **29 / 12** |
| preset_nopin | `--disable-pinned-memory` | 150.38 s | 11,432 / 10,542 MiB | **7,733 MiB** | **17,754 MiB** | 12,082 MiB | **38,245 MiB** | **2,934 MiB** @06:10:06 | 0.9287 | **0 / 0** |

中断监测规则（仅本轮测试阈值，不宣称是硬件要求）：提交余量 < 512 MiB，或提交占比连续两次采样 ≥ 97%，即请求中断。基线组确实越过了该规则（29 个样本、最长连续 12 次），但**当时只做了事后统计，没有任何中断代码**；主动中断已在阶段四 C 实现并验证。

差值（同一工作流、同一文件）：

- 工作集峰值 −10,982 MiB（−58.7%）
- 私有内存峰值 −10,832 MiB（−37.9%）
- Committed 峰值 −11,101 MiB（−22.5%）
- 最小提交余量 +2,514 MiB
- 耗时 −5.99 s（−3.8%）

产物 SHA256 两组完全相同（`f32bc5c8…`），说明禁用 pinned memory 不改变结果，只改变内存驻留方式。

**结论**：`--disable-pinned-memory` 是本机唯一有实测依据的基础预设调整，已通过本轮监测条件。当时未设为默认，需显式传参；该预设已在阶段四 C 固化为默认。

## 5. 界面交付

### 5.1 生成 UI 工作流

`/prompt` 只接受 API 形式，而画布需要 LiteGraph 形式。新增 `scripts/build-ui-workflow.py`，把已验证的 API 工作流转成 UI 图（节点、连线、控件值、输入输出槽位），只支持纯连线图，遇到不支持的节点类型直接报错。产出：

- `workflows/ui_t2v_controlled.json`（14 节点 / 17 连线）
- `workflows/ui_ref2va_single_controlled.json`（15 节点 / 19 连线）

### 5.2 实际导入（本机 127.0.0.1:8188）

用 ego-browser 打开本机前端，调用前端自己导入工作流用的 `app.loadGraphData()`，而不是只看 `/object_info`。

| 检查项 | 结果 |
|---|---|
| 节点重建 | 15 个全部重建，`missing = 0` |
| 连线 | 19 条全部解析到源节点 |
| UNETLoader 可选值 | `minimax_h3_fl2va_pruned_w6a8` / `minimax_h3_ref2va_pruned_w6a8`，当前选中 Ref2VA |
| 条件节点输入 | `clip` ← CLIPLoader(2)、`vae` ← VAELoader(3)、`audio_vae` ← VAELoader(4)、参考图 ← LoadImage(21)，全部已连接 |
| 控件值 | prompt / width 736 / height 416 / length 124 / ref_image_size match |
| 节点报错 | 无 |
| 参考图预览 | 画布上 LoadImage 显示红色圆形缩略图 |

截图：`reports/evidence/ui/ref2va-ui-imported.png`、`reports/evidence/ui/ref2va-ui-node-detail.png`、`reports/evidence/ui/t2v-ui-run-success.png`。截图只含本地画布，未包含个人信息。

### 5.3 经界面提交

**T2V：成功。** 通过 `app.graphToPrompt()` 取前端转换后的 prompt 并提交，`prompt_id = 3be89230-01e6-4457-8a01-dad76cf47d9a`，`status_str = success`，产物 `baseline_t2v_00002_.mp4`，736×416 / 124 帧 / 24 fps。

**Ref2VA 单参考图：失败。** `prompt_id = 009c1fcf-71ba-45b6-b32e-63e2ec4c2fa9`，`status_str = error`：

```text
node_type: MiniMaxH3ReferenceToVideo
exception_message: MiniMaxH3ReferenceToVideo.execute() got an unexpected keyword argument 'ref_image_1'
```

表层原因是前端把 Autogrow 输入以扁平键 `ref_image_1` 提交，而后端 `execute()` 只接受 `ref_images`
字典参数；`comfy_api/latest/_io.py` 的 `build_nested_inputs()` 依赖 `v3_data["dynamic_paths"]`
才能把扁平键重组回嵌套字典，而这条信息不在提交的 prompt 里。

这一条能被 `/object_info` 检查完全漏过：节点存在、类型正确、下拉框可选、连线上屏，
只有真正从界面提交才会报错。

**但根因在我的转换器。** 我当时判断为"固定版 ComfyUI / 前端的行为，需上游处理"，这是错误的。
`scripts/build-ui-workflow.py` 的 `RENAME` 表主动把 `ref_images.ref_image_1` 改写成 `ref_image_1`，
丢了分组路径，而仓库里的官方 R2V 模板一直保留完整前缀。该缺陷已在阶段四 C 修复，
界面提交现已通过单图与双图。

顺带发现 `build-ui-workflow.py` 的另一个缺陷：`last_node_id` 用了 API 的节点数量而不是最大节点 ID，
导致 LoadImage(21) 超出范围。已修正为 `max(节点 id)`；这不是运行失败的原因，但会干扰手工编辑。

## 6. 参考音频

### 6.1 素材

`scripts/make-reference-audio.py` 用正弦音合成一段 3.0 秒、32 kHz、单声道 WAV（两音上行动机），完全可由脚本重建，不含任何第三方或私人素材：

- 文件 `h3_ref_tone.wav`，192,044 bytes
- SHA256 `e1a4cc0766225a05288c96e08feb530b82002984de8f03be2344a9e253f91d89`

### 6.2 schema 与命名

运行时 `/object_info` 确认 `ref_audios` 为 `COMFY_AUTOGROW_V3`，前缀 `ref_audio_`，0–3 个；`audio_vae` 必须连接，否则参考音频只作用于文本编码器。

本轮使用的键名是 `ref_audios.ref_audio_1`，服务端接受。但**这也是错的**：Autogrow 槽位是零基编号，
`min=0` 只是允许从任意序号起步，因此节点第 2 个槽位实际对应提示词里的 `<Picture 1>`，整体错位一格。
零基编号已在阶段四 C 校正为 `ref_image_0` / `ref_audio_0`，并加了回归检查。

角色分工：`<Picture 1>` 控制画面主体外观，`<Audio 1>` 控制音轨内容；两者通过同一个 `MiniMaxH3ReferenceToVideo` 节点的 `ref_images` 与 `ref_audios` 分组传入。

### 6.3 对照与实验

两组只差一个 `ref_audios`，其余完全相同（同提示词、同种子、同参考图、同规格）：

| 用例 | prompt_id | 耗时 | 产物 | 视频 SHA256 |
|---|---|---:|---|---|
| 无参考音频（对照） | `c10147c5-003b-4622-99a6-7666cecb5420` | 145.22 s | `ref_audio_control_00001_.mp4`，1,206,807 B | `ba176905a57a6c14…` |
| 一条参考音频 | `338f3256-12a1-4893-a1c0-a6ab1ec85ca8` | 145.23 s | `ref_audio_test_00001_.mp4`，1,251,874 B | `f4956c05f587b918…` |

逐帧与音频比对（`scripts/compare-videos.py`，结果见 `reports/evidence/ref-audio-compare.json`）：

| 指标 | 对照 | 实验 |
|---|---:|---:|
| 与对照完全相同的帧数 | — | **0 / 124** |
| 平均逐帧像素差比 | — | **0.1079** |
| 最大逐帧像素差比 | — | 0.1197 |
| 音轨 RMS | 0.00187 | **0.19978** |
| 音轨峰值 | 0.0604 | **0.5758** |
| 音轨 PCM SHA256 | `e0b05f69…` | `03efa688…` |

结论：参考音频**确实进入了生成**——124 帧全部改变、音轨能量提升约 107 倍且 PCM 完全不同。
"音轨存在"本身不算证据；这里的证据是"加入参考音频后输出发生了系统性变化"。

**但这只证明生效，不证明是按要求生效。** 未试听，无法判断生成的音轨是否真的复现了那段三音动机。听感判定为未验证。

### 6.4 资源

| 用例 | GPU 峰值 | 进程私有峰值 | 可用内存最低 | Committed 峰值 | 最小提交余量 | 破阈样本 |
|---|---:|---:|---:|---:|---:|---:|
| 无参考音频 | 11,489 MiB | 17,912 MiB | 12,382 MiB | 38,597 MiB | 2,582 MiB | 0 |
| 一条参考音频 | 11,460 MiB | 17,881 MiB | 12,446 MiB | 38,637 MiB | 2,542 MiB | 0 |

单条 3 秒参考音频没有显著增加负担（各指标差异均在 40 MiB 内），未越过监测阈值。

## 7. 未通过 / 未验证

- **界面路径 Ref2VA 当时未通过**：根因是我的 `RENAME` 丢分组路径，已在阶段四 C 修复。
- **画质未验证**：未逐帧核对参考图身份保持、双图角色分离、运动方向。
- **听感未验证**：未试听任何音轨，包括对照与实验两组。
- **`ref_image_size=max` 未测**。
- **参考视频通路（`ref_videos` / `ref_video_audios`）完全未测**。
- **未测多音频（≥2）与音频+视频组合**。
- **未量化换页**：只有提交量与上限，没有页面文件读写速率。
- **主动中断当时未实现**：只有事后统计，已由阶段四 C 补上并验证。
- **每档预设只跑了一次**，样本量为 1，不构成统计意义上的稳定性结论。

## 8. 复现步骤

```powershell
# 1. 以禁用 pinned memory 启动（自动记录 launch JSON 与真实 PID）
powershell -File scripts\start-comfyui.ps1 -ModelSet ref2va -StopExisting

# 2. 资源采样（含同一时刻的提交余量与占比）
powershell -File scripts\sample-resources.ps1 -OutFile D:\AI\MiniMaxH3\samples\x.csv

# 3. 参考音频素材与工作流
python scripts\make-reference-audio.py D:\AI\MiniMaxH3\ComfyUI\input\h3_ref_tone.wav
python scripts\build-h3-api-workflow.py --output workflows\ref_audio_test_api.json `
  --width 736 --height 416 --length 124 --steps 20 --prefix h3/ref_audio_test `
  --unet minimax_h3_ref2va_pruned_w6a8.safetensors --ref-image h3_first.png `
  --ref-audio h3_ref_tone.wav --prompt "..."

# 4. 提交、媒体探测、逐帧比对、窗口统计
python scripts\run-workflow.py --workflow workflows\ref_audio_test_api.json `
  --record D:\AI\MiniMaxH3\records\audio_test.json --label audio_test --timeout 3600
python scripts\compare-videos.py --a <control>.mp4 --b <test>.mp4 `
  --out reports\evidence\ref-audio-compare.json
python scripts\summarize-samples.py --csv <csv> --record <record.json> --interval 2

# 5. UI 工作流
python scripts\build-ui-workflow.py --api workflows\baseline_t2v_api.json `
  --output workflows\ui_t2v_controlled.json
```

证据文件：`reports/evidence/{resource-summary,media-probe,ref-audio-compare,host-commit,preset_baseline,preset_nopin,audio_control,audio_test,launch-pinned,launch-nopin}.json`、`reports/evidence/ui/*.png`、`reports/samples-{preset-baseline,preset-nopin,audio-control,audio-test}.csv`。
