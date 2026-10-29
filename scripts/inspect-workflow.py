import argparse
import json
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

SKIP_TYPES = {'MarkdownNote', 'Note'}


def links_by_id(workflow):
    """Map link id -> [origin_node_id, origin_slot, target_node_id, target_slot, type]."""
    links = {}
    for link in workflow.get('links', []):
        if isinstance(link, list) and len(link) >= 5:
            links[link[0]] = link
    return links


def build_api_prompt(workflow, subgraph_defs):
    nodes = {}
    for node in workflow.get('nodes', []):
        node_type = node.get('type')
        if node_type in SKIP_TYPES:
            continue
        values = node.get('widgets_values')
        named = node.get('widgets_values_named') or {}
        inputs = {}
        if isinstance(named, dict):
            for key, value in named.items():
                inputs[key] = value
        elif isinstance(values, dict):
            inputs.update(values)
        elif isinstance(values, list):
            inputs['_widgets'] = values
        nodes[node['id']] = {'node': node, 'inputs': inputs, 'type': node_type}
    return nodes


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--workflow', type=Path, required=True)
    args = parser.parse_args()
    data = json.loads(args.workflow.read_text(encoding='utf-8-sig'))
    print(json.dumps({'top_level_keys': sorted(data.keys()),
                      'node_count': len(data.get('nodes', [])),
                      'subgraphs': [g.get('id') for g in data.get('definitions', {}).get('subgraphs', [])]},
                     ensure_ascii=False, indent=1))
