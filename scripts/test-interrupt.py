"""Run a task, then interrupt it on purpose to prove the interrupt path works.

This does not create a dangerous memory condition. It starts a normal task,
forces the decision function to fire, and verifies the task actually stops.
The record says the thresholds were overridden so nobody can mistake this for a
real memory event.
"""

import argparse
import json
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from importlib import import_module  # noqa: E402

guard = import_module('guard-memory')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--workflow', type=Path, required=True)
    parser.add_argument('--base-url', default='http://127.0.0.1:8188')
    parser.add_argument('--record', type=Path, required=True)
    parser.add_argument('--wait-before', type=float, default=45.0)
    args = parser.parse_args()

    workflow = json.loads(args.workflow.read_text(encoding='utf-8-sig'))
    payload = json.dumps({'prompt': workflow, 'client_id': 'interrupt-test'}).encode('utf-8')
    request = urllib.request.Request(f'{args.base_url}/prompt', data=payload,
                                     headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=60) as response:
        prompt_id = json.load(response)['prompt_id']

    log = {
        'label': 'forced_interrupt_test',
        'prompt_id': prompt_id,
        'started_at': datetime.now(timezone.utc).isoformat(),
        'note': ('Thresholds deliberately bypassed: this proves the interrupt path, '
                 'not a real low-memory event.'),
        'samples': [],
    }
    print(json.dumps({'queued': prompt_id, 'waiting_seconds': args.wait_before}))

    # Let the task actually start sampling so the interrupt has something to hit.
    deadline = time.time() + args.wait_before
    while time.time() < deadline:
        running, _pending = guard.queue_has(args.base_url, prompt_id)
        committed, limit = guard.read_counters()
        log['samples'].append({
            'at': datetime.now(timezone.utc).isoformat(),
            'running': running,
            'committed_MiB': round(committed, 1),
            'commit_limit_MiB': round(limit, 1),
            'headroom_MiB': round(limit - committed, 1),
            'ratio': round(committed / limit, 4),
        })
        time.sleep(5)

    before = {'running': log['samples'][-1]['running'] if log['samples'] else None}
    log['before_interrupt'] = before
    log['interrupt_request'] = guard.interrupt(args.base_url, prompt_id)
    log['stopped'] = guard.wait_for_stop(args.base_url, prompt_id, timeout=120)

    with urllib.request.urlopen(f'{args.base_url}/history/{prompt_id}', timeout=30) as response:
        history = json.load(response)
    entry = history.get(prompt_id) or {}
    status = entry.get('status') or {}
    messages = status.get('messages') or []
    log['final_status'] = {
        'status_str': status.get('status_str'),
        'completed': status.get('completed'),
        'interrupted': any(m[0] == 'execution_interrupted' for m in messages),
        'message_kinds': [m[0] for m in messages],
    }
    log['finished_at'] = datetime.now(timezone.utc).isoformat()
    log['verified_stopped'] = bool(log['stopped'] and not log['final_status']['completed'])

    args.record.parent.mkdir(parents=True, exist_ok=True)
    args.record.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: log[k] for k in
                      ('prompt_id', 'before_interrupt', 'interrupt_request',
                       'stopped', 'final_status', 'verified_stopped')},
                     ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
