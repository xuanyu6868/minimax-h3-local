# MiniMax H3 本地使用说明

本文件面向直接使用者，只讲怎么用，不涉及复现实验细节。实验证据见
[阶段四 C 报告](reports/phase-4c-ui-ready.md)。

## 1. 启动

低内存预设已是默认，不需要额外参数：

```powershell
powershell -File scripts\start-comfyui.ps1 -ModelSet ref2va
```

`-ModelSet` 取值：

| 值 | 用途 |
|---|---|
| `ref2va` | 多参考图 / 参考音频（本机已下载） |
| `fl2va` | 文生视频、图生视频、首尾帧 |

默认参数为 `--reserve-vram 1.0 --disable-pinned-memory`。如需对照旧行为（pinned 内存），
显式加 `-EnablePinnedMemory`，实测提交内存峰值会从约 38.2 GiB 升到约 49.3 GiB。

脚本会：

- 检查 8188 端口。已有服务时**报错退出**，不会静默连上去；确认要替换时加 `-StopExisting`。
- 把真实服务进程 PID 写入 `D:\AI\MiniMaxH3\comfyui.pid`。
- 在 `D:\AI\MiniMaxH3\launches\` 下记录启动参数、实际 argv 与日志路径。

## 2. 打开界面

浏览器访问 `http://127.0.0.1:8188`。

## 3. 导入工作流

界面左上角「工作流」→「打开」，选择下列任一文件：

| 文件 | 用途 |
|---|---|
| `workflows/ui_t2v_controlled.json` | 文生视频 |
| `workflows/ui_ref2va_single_controlled.json` | 单参考图 |
| `workflows/ui_ref2va_dual_controlled.json` | 双参考图 |

导入后画布应显示模型加载、条件节点、采样器、解码与保存节点，连线完整，无红色报错节点。

## 4. 更换提示词与参考图

- **提示词**：选中「MiniMax H3 参考生视频」节点（或图生视频节点），在 `prompt` 输入框中修改。
  引用参考图时写 `<Picture 1>`、`<Picture 2>`；引用参考音频写 `<Audio 1>`。
- **参考图**：选中 `LoadImage` 节点，点「选择文件上传」换图，或从下拉框选 `ComfyUI/input` 里已有的图片。
- **参考音频**：`LoadAudio` 节点同理会加载 `ComfyUI/input` 下的音频文件。
- **尺寸/帧数**：`width` / `height` 需为 32 的倍数；`length` 为 17 的倍数加 5
  （124 ≈ 5 秒，训练区间约 124–362）。本机已验证的规格是 736×416、124 帧、24fps。
- **步数**：在 `BasicScheduler` 节点，已验证值 20。

## 5. 运行

点右上角「运行」。任务会进入队列，画布上可看到执行进度。

## 6. 查看输出

产物默认保存在：

```
D:\AI\MiniMaxH3\ComfyUI\output\h3\
```

文件名由各工作流的 `SaveVideo` 前缀决定（如 `ref2va_single_00001_.mp4`）。

## 7. 停止任务

- 界面右上角有停止按钮，可中断当前任务。
- 或使用队列面板删除排队中的任务。
- 需要按内存余量自动中断时，见下一节。

## 8. 内存保护（可选）

`scripts/guard-memory.py` 会在提交余量不足时主动中断任务：

```powershell
python scripts\guard-memory.py --prompt-id <prompt_id> --record D:\AI\MiniMaxH3\records\guard.json
```

规则（仅作本机保护阈值，不是官方硬件要求）：

- 提交余量（CommitLimit − CommittedBytes）低于 512 MiB，立即中断；
- 提交占比连续两次采样 ≥ 97%，中断。

只对指定 `prompt_id` 生效：若该任务在排队，则从队列删除；若正在运行，才调用中断。
采样失败时不会当作"余量正常"，而是丢弃该次读数并记入 `read_errors`。

## 9. 已知限制

- **画质与听感未经验证**：任务成功只代表流程跑通，不代表画面或声音符合预期。
- 参考视频通路（`ref_videos`）未测。
- `ref_image_size=max` 未测，默认使用 `match`。
- 每档内存预设只做过单次测试，不是统计意义上的稳定性结论。
