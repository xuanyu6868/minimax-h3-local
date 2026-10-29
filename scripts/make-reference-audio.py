"""Generate a deterministic, non-personal reference audio clip.

The clip is synthesized from sine tones with an envelope, so the bytes are
reproducible from this script alone and contain no third-party material.
"""

import math
import struct
import sys
import wave

RATE = 32000
SECONDS = 3.0
# A short two-note motif: a rising major third, repeated, so the clip has a
# recognisable pitch contour rather than untuned noise.
NOTES = [(440.0, 0.0, 1.0), (554.37, 1.0, 2.0), (659.25, 2.0, 3.0)]


def sample(t):
    value = 0.0
    for freq, start, end in NOTES:
        if start <= t < end:
            local = t - start
            env = min(1.0, local / 0.05, (end - t) / 0.2)
            value += 0.45 * env * math.sin(2 * math.pi * freq * local)
    return value


def main(path):
    frames = bytearray()
    total = int(RATE * SECONDS)
    for i in range(total):
        v = sample(i / RATE)
        frames += struct.pack('<h', max(-32768, min(32767, int(v * 32767))))
    with wave.open(path, 'wb') as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(RATE)
        handle.writeframes(bytes(frames))
    print(f'{path} {RATE} Hz mono {SECONDS} s {len(frames) + 44} bytes')


if __name__ == '__main__':
    main(sys.argv[1])
