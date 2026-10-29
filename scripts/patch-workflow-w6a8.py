import json
import sys
from pathlib import Path

# The loader combo only accepts a bare file name; the download URL needs the
# repository subdirectory. Keeping them separate avoids the value_not_in_list
# error that occurs when a path is passed to UNETLoader.
LOADER_NAME = 'minimax_h3_fl2va_pruned_w6a8.safetensors'
REPO_PATH = 'diffusion_models/minimax_h3_fl2va_pruned_w6a8.safetensors'
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
                if isinstance(model, dict) and model.get('name') == DEFAULT:
                    model['name'] = LOADER_NAME
                    model['directory'] = 'diffusion_models'
                # Pin every Comfy-Org model URL, not just the swapped diffusion
                # model, so shared TE/VAE references cannot drift with main.
                url = model.get('url') if isinstance(model, dict) else None
                if isinstance(url, str) and f'{BASE_URL}main/' in url:
                    model['url'] = url.replace(f'{BASE_URL}main/', f'{BASE_URL}{REVISION}/')
        for child in node.values():
            patch(child, changed)
    elif isinstance(node, list):
        for child in node:
            patch(child, changed)


def verify(data):
    """Assert no loader receives a path and every URL carries the pinned revision."""
    problems = []

    def walk(value):
        if isinstance(value, dict):
            if value.get('type') == 'UNETLoader':
                for candidate in (value.get('widgets_values') or [])[:1]:
                    if isinstance(candidate, str) and '/' in candidate:
                        problems.append(f'UNETLoader widget contains a path: {candidate}')
                named = value.get('widgets_values_named') or {}
                name = named.get('unet_name')
                if isinstance(name, str) and '/' in name:
                    problems.append(f'UNETLoader named widget contains a path: {name}')
            if isinstance(value.get('models'), list):
                for model in value['models']:
                    url = model.get('url')
                    if isinstance(url, str) and 'huggingface.co/Comfy-Org/MiniMax-H3' in url:
                        if '/resolve/main/' in url:
                            problems.append(f'Model URL is not pinned to a revision: {url}')
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
