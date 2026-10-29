"""Redact local account names from launch records before committing them.

The interpreter path under a user profile leaks the account name, which is not
needed to verify which model set or flags a run used. The replacement keeps the
structure readable so the record still proves what it is meant to prove.
"""

import json
import sys
from pathlib import Path

REDACTIONS = [
    ('C:\\\\Users\\\\22846', '<USER>'),
    ('C:\\Users\\22846', '<USER>'),
]


def scrub(text):
    for source, target in REDACTIONS:
        text = text.replace(source, target)
    return text


def main(paths):
    for raw in paths:
        path = Path(raw)
        data = json.loads(path.read_text(encoding='utf-8-sig'))
        text = json.dumps(data, ensure_ascii=False, indent=2)
        path.write_text(scrub(text) + '\n', encoding='utf-8')
        print(f'redacted {path}')


if __name__ == '__main__':
    main(sys.argv[1:])
