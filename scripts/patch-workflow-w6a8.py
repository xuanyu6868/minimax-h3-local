"""Rewrite a UI workflow so its UNETLoader selects the W6A8 diffusion model.

The loader combo only accepts a bare file name, while the download metadata
needs the repository subdirectory. Both must name the same *W6A8* file: an
earlier version swapped only the loader name and left the URL pointing at the
INT8 checkpoint, which would fetch the wrong weights on a fresh download.
"""

import json
import sys
from pathlib import Path

LOADER_NAME = 'minimax_h3_fl2va_pruned_w6a8.safetensors'
REPO_DIR = 'diffusion_models'
REPO_PATH = f'{REPO_DIR}/{LOADER_NAME}'
DEFAULT_DIR = 'diffusion_models'
DEFAULT = 'minimax_h3_fl2va_pruned_int8_convrot.safetensors'
REVISION = 'e5eb578a89295337b8ff433a035929ce0279e0b6'
BASE_URL = 'https://huggingface.co/Comfy-Org/MiniMax-H3/resolve/'


def patch(node, changed):
    if isinstance(node, dict):
        if node.get('type') == 'UNETLoader':
            values = node.get('widgets_values')
            if isinstance(values, list) and values and values[0] == DEFAULT:
                values[0] = LOADER_NAME
                changed.append(node.get('id'))
            named = node.get('widgets_values_named')
            if isinstance(named, dict) and named.get('unet_name') == DEFAULT:
                named['unet_name'] = LOADER_NAME
        if isinstance(node.get('models'), list):
            for model in node['models']:
                if not isinstance(model, dict):
                    continue
                url = model.get('url') or ''
                if model.get('name') == DEFAULT:
                    model['name'] = LOADER_NAME
                if DEFAULT in url or model.get('name') == LOADER_NAME:
                    # Force the canonical W6A8 path: the loader name, the URL
                    # file name, the directory and the revision must all agree.
                    model['name'] = LOADER_NAME
                    model['directory'] = REPO_DIR
                    model['url'] = f'{BASE_URL}{REVISION}/{REPO_PATH}'
                elif f'{BASE_URL}main/' in url:
                    model['url'] = url.replace(f'{BASE_URL}main/', f'{BASE_URL}{REVISION}/')
        for child in node.values():
            patch(child, changed)
    elif isinstance(node, list):
        for child in node:
            patch(child, changed)


def verify(data):
    """Every loader name, URL file name, directory and revision must agree."""
    problems = []

    def check_unet(node):
        for candidate in (node.get('widgets_values') or [])[:1]:
            if isinstance(candidate, str) and '/' in candidate:
                problems.append(f'UNETLoader widget contains a path: {candidate}')
            elif isinstance(candidate, str) and candidate not in (LOADER_NAME, DEFAULT):
                problems.append(f'unexpected UNETLoader value: {candidate}')
        named = (node.get('widgets_values_named') or {}).get('unet_name')
        if isinstance(named, str) and '/' in named:
            problems.append(f'UNETLoader named widget contains a path: {named}')

    def check_model(model):
        name = model.get('name')
        url = model.get('url') or ''
        directory = model.get('directory')
        if isinstance(name, str) and '/' in name:
            problems.append(f'model name contains a path: {name}')
        if 'huggingface.co/Comfy-Org/MiniMax-H3' not in url:
            return
        if '/resolve/main/' in url:
            problems.append(f'model URL is not pinned to a revision: {url}')
        if LOADER_NAME in (name or '') or f'/{LOADER_NAME}' in url:
            if name != LOADER_NAME:
                problems.append(f'W6A8 model name mismatch: {name}')
            if not url.endswith(f'/{REPO_PATH}'):
                problems.append(f'W6A8 URL file name mismatch: {url}')
            if directory != REPO_DIR:
                problems.append(f'W6A8 model directory mismatch: {directory}')
        if DEFAULT in url:
            problems.append(f'URL still points at the INT8 checkpoint: {url}')

    def walk(value):
        if isinstance(value, dict):
            if value.get('type') == 'UNETLoader':
                check_unet(value)
            if isinstance(value.get('models'), list):
                for model in value['models']:
                    if isinstance(model, dict):
                        check_model(model)
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(data)
    return problems


if __name__ == '__main__':
    source, target = Path(sys.argv[1]), Path(sys.argv[2])
    data = json.loads(source.read_text(encoding='utf-8-sig'))
    changed = []
    patch(data, changed)
    if not changed:
        raise SystemExit(f'No UNETLoader set to {DEFAULT} in {source.name}')
    problems = verify(data)
    if problems:
        raise SystemExit('; '.join(problems))
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'source': source.name, 'target': target.name,
                      'patched_nodes': changed, 'loader_name': LOADER_NAME,
                      'url': f'{BASE_URL}{REVISION}/{REPO_PATH}'}))
