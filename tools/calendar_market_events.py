#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from calendar_actual_contract import merge_observation, retain_calendar, PROVENANCE

ROOT = Path(__file__).resolve().parents[1]
CAL = ROOT / 'market-observatory' / 'data' / 'economic-calendar.json'
OVR = ROOT / 'market-observatory' / 'data' / 'calendar-manual-overrides.json'
FEDWATCH = ROOT / 'market-observatory' / 'data' / 'fed-watch.json'
KST = ZoneInfo('Asia/Seoul')
ET = ZoneInfo('America/New_York')
UA = 'Mozilla/5.0 JJOONI-Market-Observatory-KeyEvents/1.0'

FOMC_2026_KST = [
    '2026-01-29T04:00+09:00',
    '2026-03-19T03:00+09:00',
    '2026-04-30T03:00+09:00',
    '2026-06-18T03:00+09:00',
    '2026-07-30T03:00+09:00',
    '2026-09-17T03:00+09:00',
    '2026-10-29T03:00+09:00',
    '2026-12-10T04:00+09:00',
]


def clean(v):
    if v is None:
        return None
    s = str(v).strip()
    return None if s in ('', '-', '—', 'None', 'null', 'N/A') else s


def event_date(e):
    return str(e.get('datetime_kst') or e.get('date') or '')[:10]


def ensure_fields(e):
    for k in ['previous', 'consensus', 'actual', 'te_forecast', 'surprise', 'market_data_source']:
        e.setdefault(k, None)
    e.setdefault('market_metrics', [])
    return e


def upsert(events, payload):
    dt = payload['datetime_kst']
    title = payload['title']
    country = payload['country']
    for e in events:
        if e.get('datetime_kst') == dt and e.get('title') == title and e.get('country') == country:
            e.update(merge_observation(e, payload))
            return e
    events.append(payload)
    return payload


def seed():
    c = json.loads(CAL.read_text(encoding='utf-8'))
    events = c.setdefault('events', [])

    # The base builder historically stored the U.S. local meeting date with an
    # arbitrary KST clock time. Replace it with the actual 2:00pm ET statement
    # release converted to Korea time. This avoids duplicate/wrong FOMC cards.
    events[:] = [e for e in events if not (e.get('country') == 'US' and e.get('title') == 'FOMC 정책결정')]
    for dt in FOMC_2026_KST:
        upsert(events, {
            'datetime_kst': dt,
            'title': 'FOMC 정책결정',
            'country': 'US',
            'category': '중앙은행',
            'importance': 3,
            'source': 'Federal Reserve',
            'reference_period': '',
        })

    fixed = [
        {
            'datetime_kst': '2026-09-11T23:00+09:00',
            'title': 'University of Michigan Consumer Sentiment (Preliminary)',
            'country': 'US', 'category': '심리/기대인플레', 'importance': 3,
            'source': 'University of Michigan', 'reference_period': '2026-09 preliminary',
        },
        {
            'datetime_kst': '2026-09-25T23:00+09:00',
            'title': 'University of Michigan Consumer Sentiment (Final)',
            'country': 'US', 'category': '심리/기대인플레', 'importance': 2,
            'source': 'University of Michigan', 'reference_period': '2026-09 final',
        },
        {
            'datetime_kst': '2026-09-17T20:00+09:00',
            'title': 'Bank of England 금리 결정',
            'country': 'GB', 'category': '중앙은행', 'importance': 3,
            'source': 'Bank of England', 'reference_period': 'September 2026 MPC',
        },
        {
            'datetime_kst': '2026-09-17T21:30+09:00',
            'title': 'U.S. Initial Jobless Claims',
            'country': 'US', 'category': '고용', 'importance': 2,
            'source': 'U.S. Department of Labor', 'reference_period': 'weekly',
        },
        {
            # BOJ policy decisions are released after the meeting ends; the
            # exact intraday release time is not pre-announced. Noon is only a
            # sorting placeholder and the UI-visible title says time TBD.
            'datetime_kst': '2026-09-18T12:00+09:00',
            'title': 'BOJ 금융정책결정회의 결과 (발표시간 미정)',
            'country': 'JP', 'category': '중앙은행', 'importance': 3,
            'source': 'Bank of Japan', 'reference_period': 'Sep 17-18, 2026 meeting',
            'time_status': 'TBD',
            'release_date': '2026-09-18',
            'sort_datetime_kst': '2026-09-18T12:00+09:00',
            'actual_due_policy': 'MEETING_DAY_END_KST',
        },
        {
            # Micron officially scheduled its FY2026 Q4 call for Sep 30,
            # 2:30pm Mountain Time, which is Oct 1 05:30 KST.
            'datetime_kst': '2026-10-01T05:30+09:00',
            'title': 'Micron FY2026 Q4 실적 컨퍼런스콜 (미 현지 9/30)',
            'country': 'US', 'category': '기업실적', 'importance': 2,
            'actual_expected': False, 'value_role': 'schedule_only',
            'source': 'Micron Investor Relations', 'reference_period': 'FY2026 Q4',
        },
    ]
    for e in fixed:
        upsert(events, e)

    # Remove the incorrect 9/23 Micron date if it was ever seeded manually.
    events[:] = [e for e in events if not (
        event_date(e) == '2026-09-23' and 'Micron' in str(e.get('title') or '')
    )]

    for e in events:
        # Some BEA page headings were parsed as "N ews GDP ...". Repair both
        # newly generated and already committed rows during every refresh.
        e['title'] = re.sub(r'^N\s*ews\s*', '', str(e.get('title') or ''), flags=re.I)
        ensure_fields(e)
    events.sort(key=lambda x: str(x.get('datetime_kst') or ''))
    c['key_event_contract'] = 'VERIFIED_KST_POLICY_AND_SENTIMENT_CALENDAR_V1'
    c['key_event_seeded_kst'] = datetime.now(KST).isoformat(timespec='seconds')
    CAL.write_text(json.dumps(c, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('KEY_MARKET_EVENTS_SEED=PASS events=', len(events))


def ff_rows():
    out = []
    for name in ['thisweek', 'nextweek']:
        try:
            req = urllib.request.Request(
                f'https://nfs.faireconomy.media/ff_calendar_{name}.json',
                headers={'User-Agent': UA, 'Accept': 'application/json'},
            )
            with urllib.request.urlopen(req, timeout=25) as r:
                xs = json.load(r)
            if isinstance(xs, list):
                out.extend(xs)
        except Exception:
            pass
    return out


def row_kst_date(row):
    try:
        return datetime.fromisoformat(str(row.get('date'))).astimezone(KST).date().isoformat()
    except Exception:
        return ''


def ff_match(rows, day, country, contains):
    for r in rows:
        if str(r.get('country') or '').upper() != country:
            continue
        if row_kst_date(r) != day:
            continue
        title = str(r.get('title') or '').lower()
        if all(x.lower() in title for x in contains):
            return r
    return None


def merge_metric(event, metric):
    if metric.get('key') in (event.get('metric_contract_correction') or {}).get('removed_keys', []):
        return
    rows = event.setdefault('market_metrics', [])
    key = metric.get('key') or metric.get('label')
    for i, old in enumerate(rows):
        if (old.get('key') or old.get('label')) == key:
            rows[i] = merge_observation(old, metric)
            return
    rows.append(metric)


def merge_sources(*values):
    out = []
    for value in values:
        for part in str(value or '').split(' + '):
            part = part.strip()
            if part and part not in out:
                out.append(part)
    # Drop a generic source token when a more descriptive token already
    # contains it (for example "한국은행" beside the full release title).
    out = [part for part in out if not any(part != other and part in other for other in out)]
    return ' + '.join(out) or None


def probability_pct(value):
    try:
        return f'{float(value) * 100:.1f}%'
    except (TypeError, ValueError):
        return None


def apply_fedwatch_metric(calendar, fedwatch=None):
    """Attach market-implied probability as a forecast, never as an actual."""
    if fedwatch is None:
        try:
            fedwatch = json.loads(FEDWATCH.read_text(encoding='utf-8'))
        except Exception:
            return False
    meeting_date = clean(fedwatch.get('meeting_date'))
    if not meeting_date:
        return False
    try:
        release_kst = datetime.fromisoformat(meeting_date + 'T14:00:00').replace(tzinfo=ET).astimezone(KST)
    except ValueError:
        return False
    target = next((e for e in calendar.get('events') or [] if
                   e.get('country') == 'US' and e.get('title') == 'FOMC 정책결정' and
                   event_date(e) == release_kst.date().isoformat()), None)
    if target is None:
        return False
    current = fedwatch.get('hike_25bp_probability')
    as_of = clean(fedwatch.get('market_data_as_of'))
    history = [x for x in (fedwatch.get('history') or []) if
               clean(x.get('trade_date')) and (not as_of or x.get('trade_date') <= as_of) and
               x.get('hike_25bp_probability') is not None]
    history.sort(key=lambda x: x.get('trade_date'))
    previous = history[-2].get('hike_25bp_probability') if len(history) >= 2 else None
    metric = {
        'key': 'fedwatch_hike_25bp',
        'label': f'CME FedWatch 25bp 인상확률 ({as_of or "최신"} 기준)',
        'previous': probability_pct(previous),
        'consensus': probability_pct(current),
        'actual': None,
        'source': 'CME Fed Funds futures settlement-derived',
        'observed_date': as_of,
        'previous_observed_date': history[-2].get('trade_date') if len(history) >= 2 else None,
        'metric_type': 'market_probability_snapshot',
        'value_role': 'market_forecast',
    }
    rows = [m for m in (target.get('market_metrics') or []) if
            (m.get('key') or m.get('label')) != 'fedwatch_hike_25bp']
    rows.append(metric)
    target['market_metrics'] = rows
    target['market_data_source'] = merge_sources(
        target.get('market_data_source'), 'CME Fed Funds futures settlement-derived')
    target['fedwatch_as_of'] = as_of
    return True


def representative_metric(event):
    """The one metric whose previous/consensus/actual the event card shows.

    Prefer CPI headline YoY when present. If only the monthly forecast is
    published, leave the YoY consensus blank rather than silently switching
    the whole CPI card to a different metric. For other releases, prefer a
    forecast-bearing measure; never mix YoY previous with MoM consensus.
    """
    metrics = [m for m in event.get('market_metrics') or [] if isinstance(m, dict) and
               m.get('metric_type') != 'market_probability_snapshot' and
               any(clean(m.get(k)) is not None for k in ['previous','consensus','actual'])]
    if event.get('country') == 'US' and event.get('title') == 'Consumer Price Index':
        headline = next((m for m in metrics if m.get('key') == 'cpi_yoy'), None)
        if headline is not None:
            return headline
    return next((m for m in metrics if clean(m.get('consensus')) is not None), metrics[0] if metrics else None)


def sync_representative_values(event):
    primary = representative_metric(event)
    if not primary:
        return False
    changed = False
    multi = sum(1 for m in event.get('market_metrics') or [] if isinstance(m, dict) and
                m.get('metric_type') != 'market_probability_snapshot') > 1
    if multi:
        # previous/consensus come from the representative metric only, even when
        # it has none: a value left over from a sibling measure is worse than a blank.
        for key in ['previous','consensus']:
            value = clean(primary.get(key))
            if clean(event.get(key)) != value:
                event[key] = primary.get(key) if value is not None else None
                changed = True
        if event.get('representative_metric_key') != primary.get('key'):
            event['representative_metric_key'] = primary.get('key')
            changed = True
    for key in ['previous','consensus','actual']:
        value = clean(primary.get(key))
        if value is not None and clean(event.get(key)) != value:
            if key == 'actual':
                merged = merge_observation(event, {k:primary[k] for k in ['actual',*PROVENANCE] if k in primary})
                event.update(merged)
            else:
                event[key] = primary[key]
            changed = True
    if clean(event.get('previous')) is not None and clean(event.get('previous')) == clean(primary.get('previous')):
        # Same value, same provenance: the card's "previous" observed date must
        # be the metric's, not a stale one from an earlier fill.
        for key in ['previous_source','previous_observed_date','previous_value_source']:
            if key in primary and event.get(key) != primary.get(key):
                event[key] = primary.get(key)
                changed = True
    source = clean(primary.get('source'))
    merged_source = merge_sources(event.get('market_data_source'), source)
    if merged_source != clean(event.get('market_data_source')):
        event['market_data_source'] = merged_source
        changed = True
    return changed


def add_ff_metric(event, row, key, label, source='FairEconomy/ForexFactory'):
    if not row:
        return False
    metric = {
        'key': key,
        'label': label,
        'previous': clean(row.get('previous')),
        'consensus': clean(row.get('forecast')),
        'actual': clean(row.get('actual')),
        'source': source,
        'source_tier': 'MARKET_FEED',
        'event_title': clean(row.get('title')),
        'datetime_source': clean(row.get('date')),
        'impact': clean(row.get('impact')),
    }
    merge_metric(event, metric)
    return True


def apply_overrides(c):
    if not OVR.exists():
        return 0
    o = json.loads(OVR.read_text(encoding='utf-8'))
    applied = 0
    for override in o.get('overrides') or []:
        m = override.get('match') or {}
        target = None
        for e in c.get('events') or []:
            if m.get('date') and event_date(e) != m.get('date'):
                continue
            if m.get('country') and e.get('country') != m.get('country'):
                continue
            if m.get('title_contains') and m.get('title_contains') not in str(e.get('title') or ''):
                continue
            target = e
            break
        if target is None and override.get('event'):
            target = ensure_fields(dict(override['event']))
            c.setdefault('events', []).append(target)
        if target is None:
            continue
        ensure_fields(target)
        for metric in override.get('market_metrics') or []:
            merge_metric(target, metric)
        patch = {k:override[k] for k in ['previous','consensus','actual',*PROVENANCE] if k in override}
        target.update(merge_observation(target, patch))
        src = clean(override.get('source'))
        target['market_data_source'] = merge_sources(target.get('market_data_source'), src)
        # Compact clients get the first populated metric as representative.
        primary = next((x for x in target.get('market_metrics') or [] if
                        x.get('metric_type') != 'market_probability_snapshot' and
                        any(clean(x.get(k)) is not None for k in ['previous','consensus','actual'])), None)
        if primary:
            for k in ['previous', 'consensus', 'actual']:
                if clean(primary.get(k)) is not None:
                    if k == 'actual':
                        target.update(merge_observation(target,{f:primary[f] for f in ['actual',*PROVENANCE] if f in primary}))
                    else:
                        target[k] = primary[k]
        target['_verified_override'] = True
        applied += 1
    return applied


def refresh():
    c = json.loads(CAL.read_text(encoding='utf-8'))
    rows = ff_rows()
    dynamic = 0
    for e in c.get('events') or []:
        ensure_fields(e)
        day = event_date(e)
        title = str(e.get('title') or '')
        if title.startswith('University of Michigan Consumer Sentiment'):
            dynamic += int(add_ff_metric(e, ff_match(rows, day, 'USD', ['uom', 'consumer sentiment']), 'umich_sentiment', 'UoM Consumer Sentiment'))
            dynamic += int(add_ff_metric(e, ff_match(rows, day, 'USD', ['uom', 'inflation expectations']), 'umich_inflation_1y', 'UoM 1Y Inflation Expectations'))
        elif title == 'U.S. Initial Jobless Claims':
            dynamic += int(add_ff_metric(e, ff_match(rows, day, 'USD', ['unemployment claims']), 'initial_claims', 'Initial Jobless Claims'))

    applied = apply_overrides(c)
    fedwatch_applied = apply_fedwatch_metric(c)
    representative_synced = sum(int(sync_representative_values(e)) for e in c.get('events') or [])
    c.setdefault('events', []).sort(key=lambda x: str(x.get('datetime_kst') or ''))
    c['verified_override_contract'] = 'SERVER_SIDE_VERIFIED_OVERRIDE_MERGE_V1'
    c['market_event_refresh'] = {
        'faireconomy_rows': len(rows),
        'dynamic_metric_matches': dynamic,
        'verified_overrides_applied': applied,
        'fedwatch_forecast_applied': fedwatch_applied,
        'representative_values_synced': representative_synced,
        'refreshed_kst': datetime.now(KST).isoformat(timespec='seconds'),
    }
    CAL.write_text(json.dumps(c, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('KEY_MARKET_EVENTS_REFRESH=PASS ff_rows=', len(rows), 'dynamic=', dynamic, 'overrides=', applied)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else 'refresh'
    if mode == 'seed':
        seed()
    elif mode == 'refresh':
        refresh()
    else:
        raise SystemExit('usage: calendar_market_events.py [seed|refresh]')


if __name__ == '__main__':
    main()
