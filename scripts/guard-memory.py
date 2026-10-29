"""Actively interrupt a running ComfyUI task when the commit margin collapses.

The sampler only records; this module decides and acts. It runs as its own
process against the live performance counters and the ComfyUI queue, and it
never touches memory settings, the page file, or drivers.

Two rules, both scoped to the generation window of the task it watches:

* commit headroom (CommitLimit - CommittedBytes) below 512 MiB -> interrupt
* commit ratio (CommittedBytes / CommitLimit) at or above 0.97 on two
  consecutive samples -> interrupt

A missing or stale sample is never treated as healthy headroom: if the
counters cannot be read, the reading is discarded and a warning is logged, so
the rule cannot silently pass because sampling broke.
"""

import argparse
import json
import subprocess
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

COUNTER_QUERY = (
    "$m = Get-CimInstance Win32_PerfRawData_PerfOS_Memory; "
    "[ordered]@{ committed = $m.CommittedBytes; limit = $m.CommitLimit } | ConvertTo-Json -Compress"
)


def read_counters():
    """Return (committed_mib, limit_mib) or raise."""
    out = subprocess.run(
        ['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', COUNTER_QUERY],
        capture_output=True, text=True, timeout=30,
    )
    if out.returncode != 0:
        raise RuntimeError(f'counter query failed: {out.stderr.strip()[:200]}')
    data = json.loads(out.stdout)
    return data['committed'] / 2**20, data['limit'] / 2**20


def evaluate(reading, prev_streak, ratio_threshold, headroom_threshold):
    """Pure decision function, so the thresholds can be tested without hardware.

    `reading` is a dict with committed_MiB and commit_limit_MiB, or None when the
    sample is missing or stale.
    """
    if reading is None:
        return {'action': 'hold', 'reason': 'no usable sample', 'streak': 0}
    committed = reading['committed_MiB']
    limit = reading['commit_limit_MiB']
    headroom = limit - committed
    ratio = committed / limit if limit else 1.0
    reasons = []
    if headroom < headroom_threshold:
        reasons.append(f'headroom {headroom:.1f} MiB < {headroom_threshold} MiB')
        return {'action': 'interrupt', 'reason': '; '.join(reasons), 'streak': prev_streak + 1,
                'headroom_MiB': round(headroom, 1), 'ratio': round(ratio, 4)}
    streak = prev_streak + 1 if ratio >= ratio_threshold else 0
    if streak >= 2:
        reasons.append(f'ratio {ratio:.4f} >= {ratio_threshold} on {streak} consecutive samples')
        return {'action': 'interrupt', 'reason': '; '.join(reasons), 'streak': streak,
                'headroom_MiB': round(headroom, 1), 'ratio': round(ratio, 4)}
    return {'action': 'hold', 'reason': 'within limits', 'streak': streak,
            'headroom_MiB': round(headroom, 1), 'ratio': round(ratio, 4)}


def queue_has(base_url, prompt_id):
    with urllib.request.urlopen(f'{base_url}/queue', timeout=20) as response:
        queue = json.load(response)
    running = [item[1] for item in queue.get('queue_running', []) if len(item) > 1]
    pending = [item[1] for item in queue.get('queue_pending', []) if len(item) > 1]
    return prompt_id in running, prompt_id in pending


def interrupt(base_url, prompt_id):
    """Ask ComfyUI to interrupt, but only if this task is the one running."""
    running, pending = queue_has(base_url, prompt_id)
    if pending and not running:
        # Deleting from the pending queue is precise and affects nothing else.
        body = json.dumps({'delete': [prompt_id]}).encode('utf-8')
        request = urllib.request.Request(f'{base_url}/queue', data=body,
                                         headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=20) as response:
            response.read()
        return {'method': 'queue_delete', 'was_running': False, 'was_pending': True}
    if not running:
        return {'method': 'none', 'was_running': False, 'was_pending': False,
                'note': 'task is neither running nor pending; nothing to interrupt'}
    # /interrupt stops whatever is currently executing, so this is only safe
    # because the caller verified the target is the running task.
    body = json.dumps({'prompt_id': prompt_id}).encode('utf-8')
    request = urllib.request.Request(f'{base_url}/interrupt', data=body,
                                     headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=20) as response:
        response.read()
    return {'method': 'interrupt', 'was_running': True, 'was_pending': False}


def wait_for_stop(base_url, prompt_id, timeout=120):
    """Confirm the task really left the queue, rather than assuming it did."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        running, pending = queue_has(base_url, prompt_id)
        if not running and not pending:
            return True
        time.sleep(2)
    return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--prompt-id', required=True)
    parser.add_argument('--base-url', default='http://127.0.0.1:8188')
    parser.add_argument('--ratio-threshold', type=float, default=0.97)
    parser.add_argument('--headroom-threshold', type=float, default=512.0)
    parser.add_argument('--interval', type=float, default=2.0)
    parser.add_argument('--timeout', type=int, default=3600)
    parser.add_argument('--max-sample-age', type=float, default=15.0)
    parser.add_argument('--readings', type=Path,
                        help='Replay a JSON list of readings instead of the live counters')
    parser.add_argument('--dry-run', action='store_true',
                        help='Decide but never request an interrupt')
    parser.add_argument('--record', type=Path)
    args = parser.parse_args()

    log = {
        'prompt_id': args.prompt_id,
        'base_url': args.base_url,
        'started_at': datetime.now(timezone.utc).isoformat(),
        'rules': {'ratio_threshold': args.ratio_threshold,
                  'headroom_threshold_MiB': args.headroom_threshold,
                  'consecutive_samples_for_ratio': 2},
        'dry_run': args.dry_run,
        'samples': [],
    }

    if args.readings:
        readings = json.loads(args.readings.read_text(encoding='utf-8'))
        source = 'replay'
    else:
        readings = None
        source = 'live'
    log['source'] = source

    streak = 0
    decision = {'action': 'hold', 'reason': 'not evaluated', 'streak': 0}
    started = time.time()
    index = 0
    while time.time() - started < args.timeout:
        if readings is not None:
            if index >= len(readings):
                log['ended'] = 'replay exhausted'
                break
            reading = readings[index]
            index += 1
        else:
            try:
                committed, limit = read_counters()
                reading = {'committed_MiB': committed, 'commit_limit_MiB': limit}
            except Exception as error:  # noqa: BLE001 - recorded, never treated as healthy
                reading = None
                log.setdefault('read_errors', []).append(str(error))
        decision = evaluate(reading, streak, args.ratio_threshold, args.headroom_threshold)
        streak = decision['streak']
        log['samples'].append({'at': datetime.now(timezone.utc).isoformat(),
                               'reading': reading, 'decision': decision})
        if decision['action'] == 'interrupt':
            log['decision'] = decision
            if args.dry_run:
                log['ended'] = 'dry-run: would interrupt'
                break
            log['interrupt_request'] = interrupt(args.base_url, args.prompt_id)
            log['stopped'] = wait_for_stop(args.base_url, args.prompt_id)
            log['ended'] = 'interrupted'
            break
        if readings is None:
            try:
                running, pending = queue_has(args.base_url, args.prompt_id)
                if not running and not pending:
                    log['ended'] = 'task left the queue before any rule fired'
                    break
            except Exception:  # noqa: BLE001
                pass
        time.sleep(args.interval)
    else:
        log['ended'] = 'monitor timeout'

    log['rule_fired'] = bool(log.get('decision'))
    log['finished_at'] = datetime.now(timezone.utc).isoformat()
    text = json.dumps(log, ensure_ascii=False, indent=2)
    if args.record:
        args.record.parent.mkdir(parents=True, exist_ok=True)
        args.record.write_text(text, encoding='utf-8')
    print(text)


if __name__ == '__main__':
    main()
