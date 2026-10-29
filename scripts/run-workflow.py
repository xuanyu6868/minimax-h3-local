import argparse
import json
import time
import urllib.request
import uuid
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--base-url', default='http://127.0.0.1:8188')
parser.add_argument('--workflow', type=Path, required=True)
parser.add_argument('--timeout', type=int, default=7200)
args = parser.parse_args()

workflow = json.loads(args.workflow.read_text(encoding='utf-8-sig'))
payload = json.dumps({'prompt': workflow, 'client_id': str(uuid.uuid4())}).encode('utf-8')
request = urllib.request.Request(
    args.base_url + '/prompt',
    data=payload,
    headers={'Content-Type': 'application/json'},
)
try:
    with urllib.request.urlopen(request, timeout=60) as response:
        queued = json.load(response)
except urllib.error.HTTPError as error:
    body = error.read().decode('utf-8', 'replace')
    print(json.dumps({'http_status': error.code, 'body': body[:4000]}, ensure_ascii=False, indent=2))
    raise SystemExit(1)
prompt_id = queued['prompt_id']
print(json.dumps({'queued': prompt_id}))

deadline = time.time() + args.timeout
while time.time() < deadline:
    with urllib.request.urlopen(f'{args.base_url}/history/{prompt_id}', timeout=30) as response:
        history = json.load(response)
    if prompt_id in history:
        entry = history[prompt_id]
        status = entry.get('status', {})
        print(json.dumps({
            'completed': status.get('completed'),
            'status_str': status.get('status_str'),
            'outputs': list(entry.get('outputs', {}).keys()),
        }, ensure_ascii=False))
        if status.get('status_str') == 'error':
            print(json.dumps(status.get('messages', []), ensure_ascii=False)[:2000])
            raise SystemExit(1)
        break
    time.sleep(10)
else:
    raise SystemExit('Timed out waiting for generation')
