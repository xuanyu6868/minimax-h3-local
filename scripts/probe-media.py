import argparse
import json
from fractions import Fraction
from pathlib import Path

import av


def probe(path):
    if not path.is_file():
        return {'error': 'file not found'}
    with av.open(str(path)) as container:
        summary = {
            'format': container.format.name,
            'duration_seconds': round(float(container.duration or 0) / av.time_base, 3),
            'size_bytes': path.stat().st_size,
            'streams': [],
        }
        for stream in container.streams:
            if stream.type == 'video':
                fps = stream.average_rate or stream.guessed_rate
                frames = stream.frames
                if not frames:
                    frames = sum(1 for _ in container.decode(stream)) if stream.frames == 0 else None
                summary['streams'].append({
                    'type': 'video',
                    'codec': stream.codec_context.name,
                    'width': stream.codec_context.width,
                    'height': stream.codec_context.height,
                    'fps': str(Fraction(fps)) if fps else None,
                    'fps_float': round(float(fps), 3) if fps else None,
                    'nb_frames': frames,
                    'duration_seconds': round(float(stream.duration * stream.time_base), 3)
                    if stream.duration else None,
                })
            elif stream.type == 'audio':
                summary['streams'].append({
                    'type': 'audio',
                    'codec': stream.codec_context.name,
                    'sample_rate': stream.codec_context.sample_rate,
                    'channels': stream.codec_context.channels,
                    'duration_seconds': round(float(stream.duration * stream.time_base), 3)
                    if stream.duration else None,
                })
        summary['has_audio'] = any(s['type'] == 'audio' for s in summary['streams'])
        video = next((s for s in summary['streams'] if s['type'] == 'video'), None)
        summary['video'] = video
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('paths', nargs='+')
    args = parser.parse_args()
    for raw in args.paths:
        path = Path(raw)
        print(json.dumps({'path': str(path), 'probe': probe(path)}, ensure_ascii=False, indent=1))
