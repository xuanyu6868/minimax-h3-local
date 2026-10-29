"""Record media probe JSON and both byte and normalized content hashes.

Byte hashes differ across platforms because of CRLF/LF conversion; the
normalized hash re-serializes JSON with sorted keys and LF newlines so a
reviewer on another OS can compare content, not checkout encoding.
"""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

PROBE = Path(r'D:\Minimax H3\scripts\probe-media.py')
PYTHON = r'D:\AI\MiniMaxH3\.venv\Scripts\python.exe'


def byte_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalized_hash(path):
    if path.suffix == '.json':
        data = json.loads(path.read_text(encoding='utf-8-sig'))
        text = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    else:
        # Normalize line endings only, so the hash is platform-independent.
        text = path.read_text(encoding='utf-8').replace('\r\n', '\n')
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


if __name__ == '__main__':
    videos = sys.argv[1:]
    result = {'videos': [], 'workflows': []}
    for raw in videos:
        path = Path(raw)
        probe = subprocess.run([PYTHON, str(PROBE), str(path)],
                               capture_output=True, text=True, check=False)
        data = json.loads(probe.stdout) if probe.returncode == 0 else {'error': probe.stderr}
        result['videos'].append({
            'path': str(path),
            'sha256': byte_hash(path) if path.is_file() else None,
            'probe': data.get('probe'),
        })
    out = Path(r'D:\Minimax H3\reports\evidence\media-probe.json')
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))
