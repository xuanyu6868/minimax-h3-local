import argparse
import json
import urllib.request
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--base-url', required=True)
parser.add_argument('--workflow-dir', type=Path, required=True)
args = parser.parse_args()

required_nodes = {'MiniMaxH3ImageToVideo', 'MiniMaxH3ReferenceToVideo', 'MiniMaxH3AddGuide'}
with urllib.request.urlopen(args.base_url + '/object_info', timeout=30) as response:
    object_info = json.load(response)
missing = sorted(required_nodes - object_info.keys())
if missing:
    raise SystemExit('Missing H3 nodes: ' + ', '.join(missing))
print(json.dumps({
    'url': args.base_url,
    'h3_nodes': {name: object_info[name].get('description', '') for name in sorted(required_nodes)},
}, ensure_ascii=False, indent=2))

for name in ('t2v', 'i2v', 'r2v'):
    workflow = json.loads((args.workflow_dir / f'video_minimax_h3_{name}.json').read_text(encoding='utf-8-sig'))
    node_types = set()
    model_names = set()
    def visit(value):
        if isinstance(value, dict):
            if isinstance(value.get('type'), str):
                node_types.add(value['type'])
            if isinstance(value.get('models'), list):
                for model in value['models']:
                    if isinstance(model, dict) and isinstance(model.get('name'), str):
                        model_names.add(model['name'])
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)
    visit(workflow)
    print(json.dumps({'workflow': name, 'node_types': sorted(node_types), 'model_names': sorted(model_names)}, ensure_ascii=False))
