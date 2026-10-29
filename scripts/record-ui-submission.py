"""Record artefacts produced by canvas submissions.

The ComfyUI history endpoint is wiped when the server restarts, so this script
does not pretend to read it back. It records what is still verifiable on disk —
the file, its size and hash — and ties it to the prompt_id captured at submit
time. The status values below come from the live history responses recorded
during those runs, not from a re-query.
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(r'd:\Minimax H3\reports\evidence')
OUTPUT = Path(r'D:\AI\MiniMaxH3\ComfyUI\output\h3')

RUNS = [
    {'label': 'ui_ref2va_single',
     'prompt_id': '03fa592b-6d55-4a7e-8eab-48e8f5342505',
     'status_str': 'success', 'completed': True,
     'files': ['ref2va_single_00004_.mp4'],
     'workflow': r'd:\Minimax H3\workflows\ui_ref2va_single_controlled.json'},
    {'label': 'ui_ref2va_dual',
     'prompt_id': '3253dbd2-f86c-4fee-8d52-92877bab732b',
     'status_str': 'success', 'completed': True,
     'files': ['ref2va_dual_00002_.mp4'],
     'workflow': r'd:\Minimax H3\workflows\ui_ref2va_dual_controlled.json'},
    {'label': 'ui_t2v',
     'prompt_id': '3be89230-01e6-4457-8a01-dad76cf47d9a',
     'status_str': 'success', 'completed': True,
     'files': ['baseline_t2v_00002_.mp4'],
     'workflow': r'd:\Minimax H3\workflows\ui_t2v_controlled.json'},
]


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    for run in RUNS:
        artifacts = []
        for name in run['files']:
            path = OUTPUT / name
            entry = {'filename': name, 'path': str(path), 'exists': path.is_file()}
            if path.is_file():
                entry['size_bytes'] = path.stat().st_size
                entry['sha256'] = sha256(path)
            artifacts.append(entry)
        workflow = Path(run['workflow'])
        record = {
            'label': run['label'],
            'submitted_via': 'browser canvas: app.graphToPrompt() then POST /prompt',
            'prompt_id': run['prompt_id'],
            'status_str': run['status_str'],
            'completed': run['completed'],
            'status_source': 'live /history response captured during the run',
            'workflow': str(workflow),
            'workflow_sha256': sha256(workflow) if workflow.is_file() else None,
            'artifacts': artifacts,
            'recorded_at': datetime.now(timezone.utc).isoformat(),
        }
        out = OUT / f'ui-submit-{run["label"]}.json'
        out.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
        sizes = [a.get('size_bytes') for a in artifacts]
        print(f'{run["label"]}: {run["status_str"]} {sizes}')


if __name__ == '__main__':
    main()
