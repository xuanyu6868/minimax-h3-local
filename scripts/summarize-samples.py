"""Recompute resource statistics from a sampler CSV inside a run's time window.

The sampler writes local timestamps with an offset, so comparisons are done in
UTC. Statistics are reported for the whole file, the generation window, and the
idle periods before and after it, so an idle reading is never quoted as a
generation peak.

Mean and peak are reported separately: a mean difference and a peak difference
can point in opposite directions, and quoting one as the other misreports the
run.
"""

import argparse
import csv
import json
from datetime import datetime, timedelta, timezone


def to_utc(value):
    return datetime.fromisoformat(value).astimezone(timezone.utc)


def number(row, key):
    raw = (row.get(key) or '').strip()
    if raw == '':
        return None
    try:
        return float(raw)
    except ValueError:
        return None


# max: report max + mean; min: report min + mean; both: report all three.
FIELDS = {
    'gpu_used_MiB': 'both',
    'gpu_util_pct': 'both',
    'comfy_ws_MiB': 'both',
    'comfy_private_MiB': 'both',
    'os_free_MiB': 'both',
    'os_commit_MiB': 'both',
    'committed_MiB': 'both',
    'commit_limit_MiB': 'both',
    'commit_headroom_MiB': 'both',
    'commit_ratio': 'both',
}

#: Readings are 2 s apart, so two consecutive samples above this commit ratio
#: mean the margin has been gone for at least one full interval.
DEFAULT_RATIO_THRESHOLD = 0.97
DEFAULT_HEADROOM_MIB = 512


def summarize(rows):
    result = {'samples': len(rows)}
    if not rows:
        return result
    for field, mode in FIELDS.items():
        values = [v for v in (number(r, field) for r in rows) if v is not None]
        if not values:
            result[field] = None
            continue
        result[field + '_max'] = round(max(values), 1)
        result[field + '_min'] = round(min(values), 1)
        result[field + '_avg'] = round(sum(values) / len(values), 1)
        if mode == 'max':
            result.pop(field + '_min')
        elif mode == 'min':
            result.pop(field + '_max')
    return result


def extremes(rows):
    """Time-stamped extremes for the commit margin."""
    out = {}
    pairs = [((number(r, 'committed_MiB'), number(r, 'commit_limit_MiB')), r) for r in rows]
    pairs = [(p, r) for p, r in pairs if p[0] is not None and p[1] is not None]
    if not pairs:
        return out
    headroom = [((p[1] - p[0]), r) for p, r in pairs]
    ratio = [((p[0] / p[1]), r) for p, r in pairs]
    low_head = min(headroom, key=lambda x: x[0])
    high_ratio = max(ratio, key=lambda x: x[0])
    out['min_headroom'] = {'MiB': round(low_head[0], 1), 'timestamp': low_head[1]['timestamp']}
    out['max_ratio'] = {'ratio': round(high_ratio[0], 4), 'timestamp': high_ratio[1]['timestamp']}
    return out


def consecutive_breaches(rows, ratio_threshold, headroom_threshold):
    """Samples where the margin rule is tripped, with run lengths."""
    hits = []
    streak = 0
    for row in rows:
        committed = number(row, 'committed_MiB')
        limit = number(row, 'commit_limit_MiB')
        if committed is None or limit is None:
            streak = 0
            continue
        headroom = limit - committed
        ratio = committed / limit
        if headroom < headroom_threshold or ratio >= ratio_threshold:
            streak += 1
            hits.append({'timestamp': row['timestamp'], 'streak': streak,
                         'headroom_MiB': round(headroom, 1), 'ratio': round(ratio, 4)})
        else:
            streak = 0
    return {
        'ratio_threshold': ratio_threshold,
        'headroom_threshold_MiB': headroom_threshold,
        'breach_samples': len(hits),
        'longest_streak': max((h['streak'] for h in hits), default=0),
        'first_breach': hits[0] if hits else None,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--csv', required=True)
    parser.add_argument('--record', required=True)
    parser.add_argument('--interval', type=int, default=2)
    parser.add_argument('--ratio-threshold', type=float, default=DEFAULT_RATIO_THRESHOLD)
    parser.add_argument('--headroom-threshold', type=float, default=DEFAULT_HEADROOM_MIB)
    args = parser.parse_args()

    with open(args.csv, encoding='utf-8-sig', newline='') as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        row['_ts'] = to_utc(row['timestamp'])

    with open(args.record, encoding='utf-8') as handle:
        record = json.load(handle)
    start = to_utc(record['submitted_at'])
    end = start + timedelta(seconds=record['elapsed_seconds'])

    during = [r for r in rows if start <= r['_ts'] <= end]
    before = [r for r in rows if r['_ts'] < start]
    after = [r['_ts'] for r in rows if r['_ts'] > end]

    gaps = [(b['_ts'] - a['_ts']).total_seconds() for a, b in zip(rows, rows[1:])]
    output = {
        'csv': args.csv,
        'rows_total': len(rows),
        'first_timestamp': rows[0]['timestamp'] if rows else None,
        'last_timestamp': rows[-1]['timestamp'] if rows else None,
        'nominal_interval_seconds': args.interval,
        'observed_median_gap_seconds': round(sorted(gaps)[len(gaps) // 2], 3) if gaps else None,
        'observed_max_gap_seconds': round(max(gaps), 3) if gaps else None,
        'record_submitted_at': record['submitted_at'],
        'record_elapsed_seconds': record['elapsed_seconds'],
        'window_utc': {'start': start.isoformat(), 'end': end.isoformat()},
        'all': summarize(rows),
        'generation_window': summarize(during),
        'generation_window_extremes': extremes(during),
        'idle_before': summarize(before),
        'idle_after_samples': len(after),
        'margin_rule_generation_window': consecutive_breaches(
            during, args.ratio_threshold, args.headroom_threshold),
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
