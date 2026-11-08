#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from calendar_history_integrity import merge_history_observation

ROOT = Path(__file__).resolve().parents[1]
CAL = ROOT / 'market-observatory' / 'data' / 'economic-calendar.json'
OVR = ROOT / 'market-observatory' / 'data' / 'calendar-manual-overrides.json'
OUT = ROOT / 'market-observatory' / 'data' / 'economic-calendar-history.json'
KST = ZoneInfo('Asia/Seoul')
WINDOW_DAYS = 3650

MONTHS = 'january february march april may june july august september october november december jan feb mar apr jun jul aug sep sept oct nov dec'.split()
STOP = {'release','report','survey','preliminary','final','advance','revised','revision','estimate','estimates','data'}


def clean(v):
    if v is None:
        return None
    s = str(v).strip()
    return None if s in ('', '-', '—', 'None', 'null', 'N/A') else s


def event_date(e):
    return str(e.get('datetime_kst') or e.get('date') or '')[:10]


def canonical_title(title):
    s = str(title or '').lower()
    s = re.sub(r'\([^)]*\)', ' ', s)
    s = re.sub(r'\b20\d{2}\b', ' ', s)
    s = re.sub(r'\b(?:' + '|'.join(MONTHS) + r')\b', ' ', s, flags=re.I)
    s = re.sub(r'\b\d{1,2}(?:st|nd|rd|th)?\b', ' ', s)
    s = re.sub(r'\d{4}년\s*\d{1,2}월', ' ', s)
    s = re.sub(r'\d{1,2}월', ' ', s)
    s = re.sub(r'[^a-z0-9가-힣]+', ' ', s)
    parts = [p for p in s.split() if p not in STOP]
    return ' '.join(parts).strip()


def slug(text):
    s = canonical_title(text)
    s = re.sub(r'\s+', '-', s).strip('-')
    return s[:140] or 'event'


def event_ref(e):
    explicit = clean(e.get('history_ref'))
    if explicit:
        return explicit
    return f"{str(e.get('country') or 'XX').upper()}::{slug(e.get('title'))}"


def metric_ref(e, m):
    explicit = clean(m.get('history_ref'))
    if explicit:
        return explicit
    key = clean(m.get('key')) or slug(m.get('label'))
    return f"{event_ref(e)}::{key}"


def row_payload(e, obj, label, metric_key=None):
    return {
        'date': event_date(e),
        'datetime_kst': e.get('datetime_kst') or e.get('date'),
        'reference_period': obj.get('reference_period') or e.get('reference_period'),
        **{k: obj.get(k) or e.get(k) for k in ('checked_kst', 'observed_kst', 'value_vintage', 'series_id', 'source_url', 'official_url')},
        'previous': clean(obj.get('previous')),
        'consensus': clean(obj.get('consensus')),
        'actual': clean(obj.get('actual')),
        'te_forecast': clean(obj.get('te_forecast')),
        'surprise': clean(obj.get('surprise')),
        'source': obj.get('actual_source') or obj.get('market_value_source') or obj.get('source') or e.get('market_data_source') or e.get('source'),
        'source_tier': obj.get('source_tier') or e.get('source_tier'),
        'verification_status': obj.get('verification_status') or e.get('verification_status'),
        'metric_key': metric_key,
        'label': label,
    }


def has_values(row):
    return any(clean(row.get(k)) is not None for k in ('previous','consensus','actual','te_forecast'))


def add_series(series, ref, meta, row):
    bucket = series.setdefault(ref, {'ref': ref, **meta, 'rows': []})
    if not has_values(row):
        return
    key = (row.get('date'), row.get('metric_key'))
    existing = {(x.get('date'), x.get('metric_key')): i for i, x in enumerate(bucket['rows'])}
    if key in existing:
        old = bucket['rows'][existing[key]]
        bucket['rows'][existing[key]] = merge_history_observation(old, row)
    else:
        bucket['rows'].append(row)


def apply_quarantine(series, calendar):
    """Drop history copies of values the calendar quarantined as cross-metric copies.

    The history merge never erases facts, so a quarantined calendar value would
    otherwise live on here and be propagated back as the next release's prior.
    Official observations are never touched.
    """
    cleared = 0
    for e in calendar.get('events') or []:
        for m in e.get('market_metrics') or []:
            bad = (m.get('quarantined_values') or {}) if isinstance(m, dict) else {}
            if not bad:
                continue
            bucket = series.get(metric_ref(e, m)) or {}
            for row in bucket.get('rows') or []:
                if row.get('date') != event_date(e):
                    continue
                for field, info in bad.items():
                    if field == 'actual' and row.get('source_tier') == 'OFFICIAL':
                        continue
                    if clean(row.get(field)) is not None and clean(row.get(field)) == clean(info.get('value')):
                        row[field] = None
                        cleared += 1
            if bucket.get('rows'):
                bucket['rows'] = [r for r in bucket['rows'] if has_values(r)]
    return cleared


def source_events(calendar, overrides):
    seen = set()
    for e in calendar.get('events') or []:
        key = (event_date(e), e.get('country'), e.get('title'))
        seen.add(key)
        yield e
    for o in overrides.get('overrides') or []:
        e = o.get('event')
        if not isinstance(e, dict):
            continue
        clone = dict(e)
        if o.get('market_metrics') and not clone.get('market_metrics'):
            clone['market_metrics'] = o['market_metrics']
        for k in ('previous','consensus','actual'):
            if clean(o.get(k)) is not None and clean(clone.get(k)) is None:
                clone[k] = o[k]
        key = (event_date(clone), clone.get('country'), clone.get('title'))
        if key in seen:
            continue
        seen.add(key)
        yield clone


def main():
    now = datetime.now(KST)
    today = now.date()
    start = today - timedelta(days=WINDOW_DAYS)
    calendar = json.loads(CAL.read_text(encoding='utf-8'))
    overrides = json.loads(OVR.read_text(encoding='utf-8')) if OVR.exists() else {'overrides': []}
    old = json.loads(OUT.read_text(encoding='utf-8')) if OUT.exists() else {'series': {}}
    series = {}

    # Preserve prior archived rows first. The archive is intentionally ten years:
    # PB/analyst consumers need cycle-to-cycle comparisons, not only the latest year.
    for ref, bucket in (old.get('series') or {}).items():
        meta = {k: v for k, v in bucket.items() if k not in ('rows', 'count', 'available_from', 'available_to')}
        for row in bucket.get('rows') or []:
            day = str(row.get('date') or '')[:10]
            if start.isoformat() <= day <= today.isoformat():
                add_series(series, ref, meta, dict(row))

    # Preserve original generic buckets, while explicitly connecting NFP aliases.
    nfp_refs = {metric_ref(e, m) for e in calendar.get('events') or []
                for m in e.get('market_metrics') or []
                if e.get('country') == 'US' and m.get('key') == 'nfp'}
    if len(nfp_refs) == 1:
        nfp_ref = next(iter(nfp_refs))
        for ref, bucket in list(series.items()):
            title = re.sub(r'[^a-z0-9]+', ' ', str(bucket.get('label') or bucket.get('event_title') or '').lower()).strip()
            if ref.startswith('FF::US::') and title in ('non farm employment change', 'nonfarm payrolls', 'non farm payrolls'):
                bucket['canonical_ref'] = nfp_ref
                for row in bucket.get('rows') or []:
                    linked = {**row, 'metric_key': 'nfp', 'linked_from_ref': ref}
                    add_series(series, nfp_ref, {'country': 'US', 'label': 'Nonfarm Payrolls', 'metric_key': 'nfp', 'kind': 'metric'}, linked)

    event_count = metric_count = 0
    for e in source_events(calendar, overrides):
        day = event_date(e)
        if not day or day > today.isoformat() or day < start.isoformat():
            continue
        eref = event_ref(e)
        e['history_ref'] = eref
        erow = row_payload(e, e, e.get('title') or 'Event')
        add_series(series, eref, {
            'country': e.get('country'), 'event_title': e.get('title'), 'label': e.get('title'),
            'kind': 'event', 'category': e.get('category'),
        }, erow)
        if has_values(erow):
            event_count += 1

        for m in e.get('market_metrics') or []:
            if not isinstance(m, dict) or m.get('metric_type') == 'market_probability_snapshot':
                continue
            mref = metric_ref(e, m)
            m['history_ref'] = mref
            mrow = row_payload(e, m, m.get('label') or m.get('key') or 'Metric', m.get('key'))
            add_series(series, mref, {
                'country': e.get('country'), 'event_title': e.get('title'),
                'label': m.get('label') or m.get('key'), 'metric_key': m.get('key'),
                'kind': 'metric', 'category': e.get('category'),
            }, mrow)
            if has_values(mrow):
                metric_count += 1

    # Add refs to every current event, including future events, so the UI can
    # resolve their historical records immediately.
    for e in calendar.get('events') or []:
        e['history_ref'] = event_ref(e)
        for m in e.get('market_metrics') or []:
            if isinstance(m, dict) and m.get('metric_type') != 'market_probability_snapshot':
                m['history_ref'] = metric_ref(e, m)

    quarantined = apply_quarantine(series, calendar)
    if quarantined:
        print(f'CALENDAR_HISTORY_QUARANTINE cleared_fields={quarantined}')

    total_rows = 0
    earliest = None
    latest = None
    for bucket in series.values():
        bucket['rows'].sort(key=lambda x: (str(x.get('date') or ''), str(x.get('datetime_kst') or '')))
        bucket['count'] = len(bucket['rows'])
        bucket['available_from'] = bucket['rows'][0]['date'] if bucket['rows'] else None
        bucket['available_to'] = bucket['rows'][-1]['date'] if bucket['rows'] else None
        rows = bucket['rows']
        days = sorted(set(r['date'] for r in rows))
        bucket['quality'] = {
            'status': 'OBSERVED_ONLY_NOT_VALIDATED_COMPLETE',
            'actual_count': sum(clean(r.get('actual')) is not None for r in rows),
            'consensus_count': sum(clean(r.get('consensus')) is not None for r in rows),
            'rows_by_year': {year: sum(str(r.get('date', '')).startswith(year) for r in rows) for year in sorted(set(d[:4] for d in days))},
            'max_observed_gap_days': max(((datetime.fromisoformat(b) - datetime.fromisoformat(a)).days for a, b in zip(days, days[1:])), default=0),
            'frequency_validation': 'NOT_VALIDATED',
            'backtest_policy': 'AS_RELEASED_VINTAGE_REQUIRED',
        }
        total_rows += bucket['count']
        if bucket['available_from']:
            earliest = min(earliest, bucket['available_from']) if earliest else bucket['available_from']
        if bucket['available_to']:
            latest = max(latest, bucket['available_to']) if latest else bucket['available_to']

    failed_weeks = ((old.get('backfill') or {}).get('failed_weeks') or [])
    early_enough = bool(earliest and earliest <= (start + timedelta(days=14)).isoformat())
    coverage = 'FULL' if early_enough and not failed_weeks else ('PARTIAL_GAPS' if early_enough else 'PARTIAL')
    out = {
        'schema': 'JJOONI_ECONOMIC_CALENDAR_HISTORY_V1',
        'generated_kst': now.isoformat(timespec='seconds'),
        'timezone': 'Asia/Seoul',
        'window_days': WINDOW_DAYS,
        'window_years': 10,
        'window_start': start.isoformat(),
        'window_end': today.isoformat(),
        'coverage_status': coverage,
        'coverage_scope': 'ARCHIVE_BOUNDARY_AND_FETCH_ERRORS_ONLY',
        'series_completeness_status': 'NOT_VALIDATED',
        'available_from': earliest,
        'available_to': latest,
        'series_count': len(series),
        'row_count': total_rows,
        'series': series,
        'contract': 'ROLLING_3650D_EVENT_AND_METRIC_HISTORY_PRESERVE_V2',
        'missing_policy': 'Historical consensus/actual is shown only when captured or verified; values are never synthesized.',
    }
    # Keep resumable backfill state across routine calendar refreshes.
    for key in ('backfill_status', 'backfill_contract', 'backfill_checked_kst', 'backfill'):
        if key in old:
            out[key] = old[key]
    CAL.write_text(json.dumps(calendar, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('CALENDAR_HISTORY_10Y=PASS series=', len(series), 'rows=', total_rows,
          'coverage=', coverage, 'available_from=', earliest, 'event_rows=', event_count, 'metric_rows=', metric_count)


if __name__ == '__main__':
    main()

