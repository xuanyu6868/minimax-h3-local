"""Compare two rendered videos frame by frame.

Reference conditioning must change the output; an identical result means the
reference did not reach the sampler. Pixel comparison is evidence of a change,
never of correctness: it cannot show that the reference was interpreted as
intended.
"""

import argparse
import hashlib
import json

import av


def frames(path):
    with av.open(path) as container:
        stream = container.streams.video[0]
        for frame in container.decode(stream):
            yield frame.to_ndarray(format='rgb24')


def compare(a_path, b_path):
    a_frames = list(frames(a_path))
    b_frames = list(frames(b_path))
    count = min(len(a_frames), len(b_frames))
    diffs = []
    for i in range(count):
        a, b = a_frames[i], b_frames[i]
        if a.shape != b.shape:
            diffs.append(1.0)
            continue
        delta = abs(a.astype('int16') - b.astype('int16'))
        diffs.append(float(delta.mean()) / 255.0)
    return {
        'a': a_path,
        'b': b_path,
        'frames_a': len(a_frames),
        'frames_b': len(b_frames),
        'frames_compared': count,
        'identical_frames': sum(1 for d in diffs if d == 0.0),
        'mean_abs_diff_ratio': round(sum(diffs) / len(diffs), 6) if diffs else None,
        'max_abs_diff_ratio': round(max(diffs), 6) if diffs else None,
        'first_frame_diff_ratio': round(diffs[0], 6) if diffs else None,
    }


def audio_summary(path):
    with av.open(path) as container:
        if not container.streams.audio:
            return None
        stream = container.streams.audio[0]
        samples = []
        for frame in container.decode(stream):
            arr = frame.to_ndarray()
            samples.append(arr.reshape(-1))
        if not samples:
            return {'frames': 0}
        import numpy as np
        data = np.concatenate(samples).astype('float64')
        peak = float(np.abs(data).max())
        return {
            'sample_rate': stream.rate,
            'channels': stream.channels,
            'samples': int(data.size),
            'duration_seconds': round(data.size / (stream.rate * (stream.channels or 1)), 3),
            'rms': round(float(np.sqrt((data ** 2).mean())), 6),
            'peak': round(peak, 6),
            'pcm_sha256': hashlib.sha256(data.tobytes()).hexdigest(),
        }


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--a', required=True)
    parser.add_argument('--b', required=True)
    parser.add_argument('--out')
    args = parser.parse_args()
    result = {
        'frame_compare': compare(args.a, args.b),
        'audio_a': audio_summary(args.a),
        'audio_b': audio_summary(args.b),
    }
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        with open(args.out, 'w', encoding='utf-8') as handle:
            handle.write(text)
    print(text)
