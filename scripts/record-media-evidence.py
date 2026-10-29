"""Record media probe JSON plus byte and normalized content hashes.

Byte hashes differ across platforms because of CRLF/LF conversion; the
normalized hash re-serializes JSON with sorted keys and LF newlines so a
reviewer on another OS can compare content, not checkout encoding.

Each video entry also carries the hashes of the images that were fed to it, so
the reference inputs are pinned to the artefact they produced.
"""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

PROBE = Path(r'd:\Minimax H3\scripts\probe-media.py')
PYTHON = r'D:\AI\MiniMaxH3\.venv\Scripts\python.exe'
INPUT_DIR = Path(r'D:\AI\MiniMaxH3\ComfyUI\input')


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


def describe_json(path):
    path = Path(path)
    if not path.is_file():
        return {'path': str(path), 'exists': False}
    return {
        'path': str(path),
        'exists': True,
        'size_bytes': path.stat().st_size,
        'sha256_bytes': byte_hash(path),
        'sha256_normalized': normalized_hash(path),
    }


def describe_input(name):
    path = INPUT_DIR / name
    if not path.is_file():
        return {'name': name, 'exists': False}
    return {'name': name, 'exists': True, 'size_bytes': path.stat().st_size,
            'sha256': byte_hash(path)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--video', action='append', default=[])
    parser.add_argument('--workflow-json', action='append', default=[])
    parser.add_argument('--input-image', action='append', default=[])
    parser.add_argument('--video-input', action='append', default=[],
                        help='name=video.mp4::image1.png,image2.png')
    parser.add_argument('--out', default=r'd:\Minimax H3\reports\evidence\media-probe.json')
    args = parser.parse_args()

    inputs_by_video = {}
    for spec in args.video_input:
        name, _, images = spec.partition('::')
        inputs_by_video[name] = [i for i in images.split(',') if i]

    result = {'videos': [], 'workflows': [], 'inputs': []}
    for raw in args.video:
        path = Path(raw)
        probe = subprocess.run([PYTHON, str(PROBE), str(path)],
                               capture_output=True, text=True, check=False)
        data = json.loads(probe.stdout) if probe.returncode == 0 else {'error': probe.stderr}
        entry = {
            'path': str(path),
            'sha256': byte_hash(path) if path.is_file() else None,
            'probe': data.get('probe'),
        }
        if path.name in inputs_by_video:
            entry['input_images'] = [describe_input(n) for n in inputs_by_video[path.name]]
        result['videos'].append(entry)

    for raw in args.workflow_json:
        result['workflows'].append(describe_json(raw))

    for name in args.input_image:
        result['inputs'].append(describe_input(name))

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({
        'out': str(out),
        'videos': len(result['videos']),
        'workflows': len(result['workflows']),
        'inputs': len(result['inputs']),
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
