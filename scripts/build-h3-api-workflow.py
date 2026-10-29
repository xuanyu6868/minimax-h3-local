import argparse
import json
from pathlib import Path


def build(width, height, length, steps, prefix, unet, prompt, first_frame=None, last_frame=None):
    api = {
        '1': {'class_type': 'UNETLoader',
              'inputs': {'unet_name': unet, 'weight_dtype': 'default'}},
        '2': {'class_type': 'CLIPLoader',
              'inputs': {'clip_name': 'qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors',
                         'type': 'minimax'}},
        '3': {'class_type': 'VAELoader',
              'inputs': {'vae_name': 'minimax_h3_video_vae_int8_convrot.safetensors'}},
        '4': {'class_type': 'VAELoader',
              'inputs': {'vae_name': 'minimax_h3_audio_vae_fp32.safetensors'}},
        '5': {'class_type': 'MiniMaxH3ImageToVideo',
              'inputs': {'clip': ['2', 0], 'vae': ['3', 0], 'prompt': prompt,
                         'width': width, 'height': height, 'length': length}},
        '6': {'class_type': 'RandomNoise', 'inputs': {'noise_seed': 12345}},
        '7': {'class_type': 'KSamplerSelect', 'inputs': {'sampler_name': 'res_multistep'}},
        '8': {'class_type': 'BasicScheduler',
              'inputs': {'model': ['1', 0], 'scheduler': 'simple', 'steps': steps, 'denoise': 1.0}},
        '9': {'class_type': 'BasicGuider',
              'inputs': {'model': ['1', 0], 'conditioning': ['5', 0]}},
        '10': {'class_type': 'SamplerCustomAdvanced',
               'inputs': {'noise': ['6', 0], 'guider': ['9', 0], 'sampler': ['7', 0],
                          'sigmas': ['8', 0], 'latent_image': ['5', 1]}},
        '11': {'class_type': 'VAEDecode',
               'inputs': {'samples': ['10', 0], 'vae': ['3', 0]}},
        '12': {'class_type': 'VAEDecodeAudio',
               'inputs': {'samples': ['10', 0], 'vae': ['4', 0]}},
        '13': {'class_type': 'CreateVideo',
               'inputs': {'images': ['11', 0], 'audio': ['12', 0], 'fps': 24.0}},
        '14': {'class_type': 'SaveVideo',
               'inputs': {'video': ['13', 0], 'filename_prefix': prefix,
                          'format': 'auto', 'codec': 'auto'}},
    }
    if first_frame:
        api['5']['inputs']['first_frame'] = ['15', 0]
        api['15'] = {'class_type': 'LoadImage', 'inputs': {'image': first_frame}}
    if last_frame:
        api['5']['inputs']['last_frame'] = ['16', 0]
        api['16'] = {'class_type': 'LoadImage', 'inputs': {'image': last_frame}}
    return api


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--width', type=int, default=416)
    parser.add_argument('--height', type=int, default=224)
    parser.add_argument('--length', type=int, default=39)
    parser.add_argument('--steps', type=int, default=4)
    parser.add_argument('--prefix', default='h3/t2v_smoke')
    parser.add_argument('--unet', default='minimax_h3_fl2va_pruned_w6a8.safetensors')
    parser.add_argument('--prompt', default='A red ball rolling slowly on a wooden table, soft daylight.')
    parser.add_argument('--first-frame')
    parser.add_argument('--last-frame')
    args = parser.parse_args()
    data = build(args.width, args.height, args.length, args.steps, args.prefix,
                 args.unet, args.prompt, args.first_frame, args.last_frame)
    args.output.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps({'output': str(args.output), 'nodes': len(data),
                      'width': args.width, 'height': args.height,
                      'length': args.length, 'steps': args.steps}))
