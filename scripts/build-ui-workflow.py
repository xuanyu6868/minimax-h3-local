"""Build a minimal LiteGraph UI workflow from a validated API workflow.

ComfyUI's /prompt endpoint takes the API form, but the frontend canvas needs
the LiteGraph form (nodes, links, widget values, inputs/outputs). This script
emits that form for a linear graph made only of links, so the same controlled
test can be imported and run from the interface instead of only by API.

Only edges are supported: every input a node receives must come from another
node's output. Widget-only inputs keep their value from the API workflow.
"""

import argparse
import json
from pathlib import Path

# Socket order matches each node's INPUT_TYPES order, which is what the canvas
# uses to index inputs and outputs.
SOCKETS = {
    'UNETLoader': {'in': [], 'out': [('MODEL', 'MODEL')]},
    'CLIPLoader': {'in': [], 'out': [('CLIP', 'CLIP')]},
    'VAELoader': {'in': [], 'out': [('VAE', 'VAE')]},
    'LoadImage': {'in': [], 'out': [('IMAGE', 'IMAGE'), ('MASK', 'MASK')]},
    'LoadAudio': {'in': [], 'out': [('AUDIO', 'AUDIO')]},
    'RandomNoise': {'in': [], 'out': [('NOISE', 'NOISE')]},
    'KSamplerSelect': {'in': [], 'out': [('SAMPLER', 'SAMPLER')]},
    'BasicScheduler': {'in': [('model', 'MODEL')], 'out': [('SIGMAS', 'SIGMAS')]},
    'BasicGuider': {'in': [('model', 'MODEL'), ('conditioning', 'CONDITIONING')],
                    'out': [('GUIDER', 'GUIDER')]},
    'SamplerCustomAdvanced': {'in': [('noise', 'NOISE'), ('guider', 'GUIDER'),
                                     ('sampler', 'SAMPLER'), ('sigmas', 'SIGMAS'),
                                     ('latent_image', 'LATENT')],
                              'out': [('output', 'LATENT'), ('denoised_output', 'LATENT')]},
    'MiniMaxH3ImageToVideo': {'in': [('clip', 'CLIP'), ('vae', 'VAE'), ('first_frame', 'IMAGE'),
                                     ('last_frame', 'IMAGE')],
                              'out': [('positive', 'CONDITIONING'), ('LATENT', 'LATENT')]},
    'MiniMaxH3ReferenceToVideo': {'in': [('clip', 'CLIP'), ('vae', 'VAE'), ('audio_vae', 'VAE'),
                                         ('ref_image_1', 'IMAGE'), ('ref_image_2', 'IMAGE')],
                                  'out': [('positive', 'CONDITIONING'), ('LATENT', 'LATENT')]},
    'VAEDecode': {'in': [('samples', 'LATENT'), ('vae', 'VAE')], 'out': [('IMAGE', 'IMAGE')]},
    'VAEDecodeAudio': {'in': [('samples', 'LATENT'), ('vae', 'VAE')], 'out': [('AUDIO', 'AUDIO')]},
    'CreateVideo': {'in': [('images', 'IMAGE'), ('audio', 'AUDIO')], 'out': [('VIDEO', 'VIDEO')]},
    'SaveVideo': {'in': [('video', 'VIDEO')], 'out': []},
}

# Autogrow inputs must keep their group path in the canvas node. The official
# R2V template stores them as name="ref_images.ref_image_0" with a short
# label="ref_image_0" and shape=7, and the frontend turns that name into the
# nested key the backend expects. Renaming them to a bare "ref_image_0" loses
# the group path and makes the submitted prompt fail with
# "unexpected keyword argument 'ref_image_0'".
AUTOGROW = {
    'ref_images.ref_image_': ('IMAGE', 'ref_images', 'ref_image_'),
    'ref_videos.ref_video_': ('IMAGE', 'ref_videos', 'ref_video_'),
    'ref_video_audios.ref_video_audio_': ('AUDIO', 'ref_video_audios', 'ref_video_audio_'),
    'ref_audios.ref_audio_': ('AUDIO', 'ref_audios', 'ref_audio_'),
}
SHAPE_GRID = 7


def socket_for(key):
    """Return (name, label, type, shape) for a canvas input."""
    for prefix, (type_name, _group, _field) in AUTOGROW.items():
        if key.startswith(prefix):
            return key, key.split('.', 1)[1], type_name, SHAPE_GRID
    return key, None, None, None


def api_key_for(key):
    """Translate an API input key to the canvas socket name (same string)."""
    return key


def build(api):
    nodes, links = [], []
    link_id = 0
    # Map "node_id:output_index" -> (link_id, slot, type)
    produced = {}
    positions = {}

    order = sorted(api, key=lambda k: int(k))
    # Output identities are known from the class alone, so register them before
    # wiring: the API form does not guarantee that producers appear first.
    for node_id in order:
        for out_index, (_n, type_name) in enumerate(SOCKETS[api[node_id]['class_type']]['out']):
            produced[f'{node_id}:{out_index}'] = (None, out_index, type_name)

    for index, node_id in enumerate(order):
        spec = api[node_id]
        cls = spec['class_type']
        if cls not in SOCKETS:
            raise SystemExit(f'unsupported node type for UI export: {cls}')
        sock = SOCKETS[cls]
        inputs, widgets, link_inputs = [], [], []

        for key, value in spec['inputs'].items():
            if isinstance(value, list) and len(value) == 2 and isinstance(value[0], str):
                source_id, slot = value
                src = produced.get(f'{source_id}:{slot}')
                if not src:
                    raise SystemExit(f'{node_id}.{key} references unknown node {source_id}:{slot}')
                link_id += 1
                name, label, autogrow_type, shape = socket_for(key)
                entry = {'name': name}
                if label:
                    entry['label'] = label
                if shape is not None:
                    entry['shape'] = shape
                entry['type'] = autogrow_type or src[2]
                entry['link'] = link_id
                inputs.append(entry)
                links.append([link_id, int(source_id), src[1], int(node_id),
                              len(inputs) - 1, entry['type']])
                link_inputs.append((link_id, int(source_id), src[1], len(inputs) - 1, entry['type']))
            else:
                widgets.append(value)
                inputs.append({'name': key, 'type': 'WIDGET', 'link': None})

        for out_index, (name, type_name) in enumerate(sock['out']):
            produced[f'{node_id}:{out_index}'] = (link_id, out_index, type_name)

        positions[node_id] = [200 + (index % 5) * 320, 100 + (index // 5) * 260]
        nodes.append({
            'id': int(node_id),
            'type': cls,
            'pos': positions[node_id],
            'size': [300, 200],
            'flags': {},
            'order': index,
            'mode': 0,
            'inputs': inputs,
            'outputs': [{'name': n, 'type': t, 'links': [], 'slot_index': i}
                        for i, (n, t) in enumerate(sock['out'])],
            'properties': {'Node name for S&R': cls},
            'widgets_values': widgets,
        })

    by_id = {n['id']: n for n in nodes}
    for lid, src, sslot, dst, dslot, _t in links:
        outs = by_id[src]['outputs'][sslot]['links']
        if outs is None:
            by_id[src]['outputs'][sslot]['links'] = [lid]
        else:
            outs.append(lid)

    return {
        'id': 'h3-ui-controlled',
        'revision': 0,
        'last_node_id': max(n['id'] for n in nodes),
        'last_link_id': link_id,
        'nodes': nodes,
        'links': links,
        'groups': [],
        'config': {},
        'extra': {'ds': {'scale': 0.8, 'offset': [0, 0]}},
        'version': 0.4,
    }


def verify(ui):
    """Fail if any Autogrow socket lost its group path.

    A bare name such as 'ref_image_0' is rejected, because the frontend would
    submit it as a flat key and the backend would refuse it.
    """
    groups = {group for _t, group, _f in AUTOGROW.values()}
    bare_fields = {field + str(i)
                   for _t, _g, field in AUTOGROW.values() for i in range(100)}
    problems = []
    for node in ui['nodes']:
        for entry in node['inputs']:
            name = entry.get('name') or ''
            if '.' in name:
                group, field = name.split('.', 1)
                if group not in groups:
                    problems.append(f"node {node['id']}: unknown group '{group}' in '{name}'")
                if entry.get('shape') != SHAPE_GRID:
                    problems.append(f"node {node['id']}: '{name}' missing shape={SHAPE_GRID}")
            elif name in bare_fields:
                problems.append(f"node {node['id']}: '{name}' lost its Autogrow group path")
    if problems:
        raise SystemExit('UI verification failed:\n  ' + '\n  '.join(problems))
    return True


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--api', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    api = json.loads(args.api.read_text(encoding='utf-8'))
    ui = build(api)
    verify(ui)
    args.output.write_text(json.dumps(ui, ensure_ascii=False, indent=1), encoding='utf-8')
    autogrow = [e['name'] for n in ui['nodes'] for e in n['inputs']
                if any(e['name'].startswith(p) for p in AUTOGROW)]
    print(json.dumps({'output': str(args.output), 'nodes': len(ui['nodes']),
                      'links': len(ui['links']), 'autogrow_sockets': autogrow},
                     ensure_ascii=False))
