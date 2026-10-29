"""Recompute resource statistics from a sampler CSV inside a run's time window.

The sampler writes local timestamps with an offset, so comparisons are done in
UTC. Statistics are reported for the whole file, the generation window, and the
idle periods before and after it, so an idle reading is never quoted as a
generation peak.
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


FIELDS = {
    'gpu_used_MiB': 'max',
    'gpu_util_pct': 'max',
    'comfy_ws_MiB': 'max',
    'comfy_private_MiB': 'max',
    'os_free_MiB': 'min',
    'os_commit_MiB': 'max',
    'committed_MiB': 'max',
    'commit_limit_MiB': 'min',
}


def summarize(rows):
    result = {'samples': len(rows)}
    if not rows:
        return result
    for field, mode in FIELDS.items():
        values = [v for v in (number(r, field) for r in rows) if v is not None]
        if not values:
            result[field] = None
            continue
        if mode == 'max':
            result[field + '_max'] = round(max(values), 1)
            result[field + '_avg'] = round(sum(values) / len(values), 1)
        else:
            result[field + '_min'] = round(min(values), 1)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--csv', required=True)
    parser.add_argument('--record', required=True)
    parser.add_argument('--interval', type=int, default=2)
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
        'idle_before': summarize(before),
        'idle_after_samples': len(after),
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
