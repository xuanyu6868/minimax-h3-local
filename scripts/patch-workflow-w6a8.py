import json
import sys
from pathlib import Path

TARGET = 'diffusion_models/minimax_h3_fl2va_pruned_w6a8.safetensors'
DEFAULT = 'minimax_h3_fl2va_pruned_int8_convrot.safetensors'


def patch(node, changed):
    if isinstance(node, dict):
        if node.get('type') == 'UNETLoader':
            values = node.get('widgets_values')
            if isinstance(values, list) and values and values[0] == DEFAULT:
                values[0] = TARGET
                changed.append(node.get('id'))
            named = node.get('widgets_values_named')
            if isinstance(named, dict) and named.get('unet_name') == DEFAULT:
                named['unet_name'] = TARGET
        if isinstance(node.get('models'), list):
            for model in node['models']:
                if isinstance(model, dict) and model.get('name') == DEFAULT:
                    model['name'] = TARGET
                    model['url'] = ('https://huggingface.co/Comfy-Org/MiniMax-H3/resolve/main/'
                                    + TARGET)
        for child in node.values():
            patch(child, changed)
    elif isinstance(node, list):
        for child in node:
            patch(child, changed)


if __name__ == '__main__':
    source, target = Path(sys.argv[1]), Path(sys.argv[2])
    data = json.loads(source.read_text(encoding='utf-8-sig'))
    changed = []
    patch(data, changed)
    if not changed:
        raise SystemExit(f'No UNETLoader set to {DEFAULT} in {source.name}')
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'source': source.name, 'target': target.name, 'patched_nodes': changed}))
