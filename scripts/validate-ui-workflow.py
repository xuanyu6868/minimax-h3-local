import argparse
import json
import urllib.error
import urllib.request
from pathlib import Path


def object_info(base_url):
    with urllib.request.urlopen(f'{base_url}/object_info', timeout=60) as response:
        return json.load(response)


def iter_nodes(value):
    """Yield real graph nodes from node lists only.

    Subgraph definitions also carry 'id'/'type' for inputs and outputs, so a
    blind recursive walk produces false 'missing node type' reports.
    """
    if isinstance(value, dict):
        for child in value.values():
            yield from iter_nodes(child)
        return
    if not isinstance(value, list):
        return
    for child in value:
        if isinstance(child, dict) and {'type', 'id'} <= set(child.keys()):
            yield child
        if isinstance(child, dict):
            for key in ('nodes',):
                if isinstance(child.get(key), list):
                    yield from iter_nodes(child[key])


def check(path, info):
    data = json.loads(path.read_text(encoding='utf-8'))
    issues = []
    warnings = []
    subgraph_ids = {g.get('id') for g in data.get('definitions', {}).get('subgraphs', []) or []}
    installed = set(info.keys())
    # Frontend-only nodes never appear in /object_info and cannot block loading.
    frontend_only = {'MarkdownNote', 'Note'}
    unet_values = {}
    for node in iter_nodes(data):
        node_type = node['type']
        if node_type in frontend_only or node_type in subgraph_ids or '-' in node_type:
            continue
        if node_type not in installed:
            issues.append(f'missing node type: {node_type}')
        if node_type == 'UNETLoader':
            widget = (node.get('widgets_values') or [None])[0]
            choices = info['UNETLoader']['input']['required']['unet_name'][0]
            unet_values[node.get('id')] = widget
            if widget not in choices:
                issues.append(f'UNETLoader value not selectable: {widget}')
            for model in (node.get('properties', {}) or {}).get('models', []) or []:
                if '/' in str(model.get('name', '')):
                    issues.append(f'model name contains a path: {model.get("name")}')
                url = model.get('url') or ''
                if '/resolve/main/' in url:
                    issues.append(f'model URL not pinned: {url}')
    # Optional LoRA must not be required for the base graph to load.
    loras = [n for n in iter_nodes(data) if n.get('type') == 'LoraLoaderModelOnly']
    for node in loras:
        name = (node.get('widgets_values') or [None])[0]
        if name not in (info.get('LoraLoaderModelOnly', {}).get('input', {})
                        .get('required', {}).get('lora_name', [[]])[0]):
            warnings.append(f'optional LoRA not installed: {name} (base mode via turbo_mode=false)')
    return {
        'workflow': path.name,
        'workflow_sha256_hint': str(path.stat().st_size),
        'subgraphs': len(subgraph_ids),
        'unet_values': unet_values,
        'missing_nodes': issues,
        'warnings': warnings,
        'ok': not issues,
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-url', default='http://127.0.0.1:8188')
    parser.add_argument('paths', nargs='+')
    args = parser.parse_args()
    info = object_info(args.base_url)
    results = [check(Path(p), info) for p in args.paths]
    print(json.dumps(results, ensure_ascii=False, indent=1))
    if not all(r['ok'] for r in results):
        raise SystemExit(1)
