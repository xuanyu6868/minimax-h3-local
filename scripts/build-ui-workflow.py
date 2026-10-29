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

# API input key -> canvas socket name, where they differ.
RENAME = {'ref_images.ref_image_1': 'ref_image_1', 'ref_images.ref_image_2': 'ref_image_2'}


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
                name = RENAME.get(key, key)
                inputs.append({'name': name, 'type': src[2], 'link': link_id})
                links.append([link_id, int(source_id), src[1], int(node_id),
                              len(inputs) - 1, src[2]])
                link_inputs.append((link_id, int(source_id), src[1], len(inputs) - 1, src[2]))
            else:
                name = RENAME.get(key, key)
                widgets.append(value)
                inputs.append({'name': name, 'type': 'WIDGET', 'link': None})

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


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--api', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    api = json.loads(args.api.read_text(encoding='utf-8'))
    ui = build(api)
    args.output.write_text(json.dumps(ui, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps({'output': str(args.output), 'nodes': len(ui['nodes']),
                      'links': len(ui['links'])}, ensure_ascii=False))
