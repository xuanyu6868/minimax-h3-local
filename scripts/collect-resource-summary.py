"""Collect window-scoped resource statistics for several runs into one file.

Each run's numbers come from summarize-samples.py, so the JSON here cannot drift
from the CSV evidence it is built on.
"""

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(r'd:\Minimax H3')
SUMMARY = REPO / 'scripts' / 'summarize-samples.py'
SAMPLES = Path(r'D:\AI\MiniMaxH3\samples')
RECORDS = Path(r'D:\AI\MiniMaxH3\records')

RUNS = [
    ('preset_baseline', 'pinned memory enabled (previous default)', 'preset-baseline.csv', 'preset_baseline.json', ''),
    ('preset_nopin', 'pinned memory disabled', 'preset-nopin.csv', 'preset_nopin.json', '--disable-pinned-memory'),
    ('audio_control', 'no reference audio', 'audio-control.csv', 'audio_control.json', '--disable-pinned-memory'),
    ('audio_test', 'one reference audio', 'audio-test.csv', 'audio_test.json', '--disable-pinned-memory'),
]


def summarize(csv_name, record_name):
    out = subprocess.run(
        [sys.executable, str(SUMMARY), '--csv', str(SAMPLES / csv_name),
         '--record', str(RECORDS / record_name), '--interval', '2'],
        capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def main():
    rows = []
    for label, note, csv_name, record_name, args in RUNS:
        data = summarize(csv_name, record_name)
        generation = data['generation_window']
        rows.append({
            'label': label,
            'note': note,
            'extra_args': args,
            'prompt_id': json.loads((RECORDS / record_name).read_text(encoding='utf-8'))['prompt_id'],
            'elapsed_seconds': data['record_elapsed_seconds'],
            'window_samples': generation['samples'],
            'gpu_used_MiB_max': generation['gpu_used_MiB_max'],
            'gpu_used_MiB_avg': generation['gpu_used_MiB_avg'],
            'comfy_ws_MiB_max': generation['comfy_ws_MiB_max'],
            'comfy_private_MiB_max': generation['comfy_private_MiB_max'],
            'os_free_MiB_min': generation['os_free_MiB_min'],
            'committed_MiB_max': generation['committed_MiB_max'],
            'commit_limit_MiB_min': generation['commit_limit_MiB_min'],
            'commit_headroom_MiB_min': data['generation_window_extremes']['min_headroom']['MiB'],
            'commit_headroom_MiB_min_at': data['generation_window_extremes']['min_headroom']['timestamp'],
            'commit_ratio_max': data['generation_window_extremes']['max_ratio']['ratio'],
            'commit_ratio_max_at': data['generation_window_extremes']['max_ratio']['timestamp'],
            'margin_breach_samples': data['margin_rule_generation_window']['breach_samples'],
            'margin_longest_streak': data['margin_rule_generation_window']['longest_streak'],
        })
    out_path = REPO / 'reports' / 'evidence' / 'resource-summary.json'
    payload = {
        'rule': {
            'ratio_threshold': 0.97,
            'headroom_threshold_MiB': 512,
            'scope': 'generation window only; a sampling rule for this round, not a hardware requirement',
        },
        'runs': rows,
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'out': str(out_path), 'runs': len(rows)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
