import argparse
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

TERMINAL_ERROR = {'error', 'failed', 'failure', 'cancelled', 'canceled'}


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def queue_state(base_url, prompt_id):
    """Return (running, pending_count, position_or_None)."""
    try:
        with urllib.request.urlopen(f'{base_url}/queue', timeout=20) as response:
            queue = json.load(response)
    except Exception as error:  # noqa: BLE001 - reported, not swallowed
        return None, None, f'queue query failed: {error}'
    running_ids = [item[1] for item in queue.get('queue_running', []) if len(item) > 1]
    pending = queue.get('queue_pending', [])
    pending_ids = [item[1] for item in pending if len(item) > 1]
    if prompt_id in running_ids:
        return True, len(pending_ids), 0
    if prompt_id in pending_ids:
        return False, len(pending_ids), pending_ids.index(prompt_id) + 1
    return False, len(pending_ids), None


def collect_outputs(history_entry, output_root):
    """Locate SaveVideo artifacts and confirm they exist on disk."""
    found = []
    for node_id, node_output in (history_entry.get('outputs') or {}).items():
        for key in ('images', 'gifs', 'videos'):
            for item in node_output.get(key, []) or []:
                filename = item.get('filename')
                if not filename:
                    continue
                subfolder = item.get('subfolder') or ''
                candidate = Path(output_root) / subfolder / filename
                entry = {
                    'node_id': node_id,
                    'filename': filename,
                    'subfolder': subfolder,
                    'path': str(candidate),
                    'exists': candidate.is_file(),
                }
                if candidate.is_file():
                    entry['size_bytes'] = candidate.stat().st_size
                    entry['sha256'] = sha256_file(candidate)
                found.append(entry)
    return found


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-url', default='http://127.0.0.1:8188')
    parser.add_argument('--workflow', type=Path, required=True)
    parser.add_argument('--output-root', type=Path, default=Path(r'D:\AI\MiniMaxH3\ComfyUI\output'))
    parser.add_argument('--record', type=Path, help='Write a JSON evidence record here')
    parser.add_argument('--label', default='run')
    parser.add_argument('--timeout', type=int, default=7200)
    parser.add_argument('--poll-interval', type=int, default=5)
    args = parser.parse_args()

    raw = args.workflow.read_bytes()
    workflow = json.loads(raw.decode('utf-8-sig'))
    workflow_sha256 = hashlib.sha256(raw).hexdigest()
    payload = json.dumps({'prompt': workflow, 'client_id': str(uuid.uuid4())}).encode('utf-8')
    request = urllib.request.Request(
        args.base_url + '/prompt',
        data=payload,
        headers={'Content-Type': 'application/json'},
    )
    record = {
        'label': args.label,
        'workflow': str(args.workflow),
        'workflow_sha256': workflow_sha256,
        'submitted_at': datetime.now(timezone.utc).isoformat(),
    }
    started = time.time()
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            queued = json.load(response)
    except urllib.error.HTTPError as error:
        body = error.read().decode('utf-8', 'replace')
        record.update({'result': 'rejected', 'http_status': error.code, 'body': body[:4000]})
        print(json.dumps(record, ensure_ascii=False, indent=2))
        raise SystemExit(2)

    prompt_id = queued['prompt_id']
    record['prompt_id'] = prompt_id
    print(json.dumps({'queued': prompt_id, 'workflow_sha256': workflow_sha256}))

    deadline = time.time() + args.timeout
    final_status = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f'{args.base_url}/history/{prompt_id}', timeout=30) as response:
                history = json.load(response)
        except Exception as error:  # noqa: BLE001
            history = {}
            record.setdefault('poll_errors', []).append(str(error))
        entry = history.get(prompt_id)
        if entry is not None:
            status = entry.get('status') or {}
            completed = status.get('completed') is True
            status_str = status.get('status_str')
            if completed and status_str == 'success':
                final_status = ('success', entry)
                break
            if status_str in TERMINAL_ERROR:
                final_status = ('error', entry)
                break
            if completed and status_str != 'success':
                final_status = ('inconsistent', entry)
                break
        time.sleep(args.poll_interval)
    else:
        running, pending, position = queue_state(args.base_url, prompt_id)
        record.update({'result': 'timeout', 'running': running,
                       'queue_pending': pending, 'queue_position': position})
        record['elapsed_seconds'] = round(time.time() - started, 2)
        print(json.dumps(record, ensure_ascii=False, indent=2))
        if args.record:
            args.record.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
        raise SystemExit(3)

    kind, entry = final_status
    status = entry.get('status') or {}
    record.update({
        'result': kind,
        'completed': status.get('completed'),
        'status_str': status.get('status_str'),
        'elapsed_seconds': round(time.time() - started, 2),
    })
    if kind == 'error':
        record['messages'] = status.get('messages', [])
    artifacts = collect_outputs(entry, args.output_root)
    record['artifacts'] = artifacts

    # Task success is not video acceptance: require a real file on disk.
    present = [item for item in artifacts if item.get('exists')]
    record['task_completed'] = kind == 'success'
    record['video_present'] = bool(present)
    if kind == 'success' and not present:
        record['result'] = 'success_without_output_file'

    print(json.dumps(record, ensure_ascii=False, indent=2))
    if args.record:
        args.record.parent.mkdir(parents=True, exist_ok=True)
        args.record.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')

    if kind != 'success':
        raise SystemExit(1)
    if not present:
        raise SystemExit(4)


if __name__ == '__main__':
    main()
