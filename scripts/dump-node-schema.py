"""Print the live /object_info schema for named ComfyUI nodes.

Read-only: only issues a GET against the running server so the recorded
schema is what the runtime actually offers, not what the docs claim.
"""

import json
import sys
import urllib.request

BASE = 'http://127.0.0.1:8188'


def main(names):
    with urllib.request.urlopen(f'{BASE}/object_info', timeout=120) as resp:
        info = json.load(resp)
    missing = [n for n in names if n not in info]
    if missing:
        raise SystemExit(f'missing nodes: {missing}')
    for name in names:
        print(f'=== {name} ===')
        print(json.dumps(info[name], indent=2, ensure_ascii=False))
        print()


if __name__ == '__main__':
    main(sys.argv[1:])
