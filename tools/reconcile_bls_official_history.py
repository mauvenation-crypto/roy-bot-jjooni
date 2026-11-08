#!/usr/bin/env python3
"""Replace market-feed values on past BLS releases with official BLS API values.

ForexFactory does not publish every sub-metric BLS releases, and its weekly
rows were attached to neighbouring metrics. October 2026 shows the damage:
PPI YoY carried CPI YoY (3.7% vs official 6.3%), Core PPI YoY carried Core
CPI YoY, export prices copied import prices (1.1% vs 2.2%) and average hourly
earnings YoY copied MoM. Those values then became the "previous" of the next
release. The live official path only reaches the newest release, so older
releases were never corrected.

For every RELEASED BLS event in the calendar window whose metrics are not yet
official, this tool:
  1. tries reference months 1-3 months before the release and accepts one only
     when at least one market-feed metric equals the official value for that
     month (anchor check: never attach a release to the wrong month);
  2. writes the official values to the event metrics and to the matching
     calendar-history rows (same history_ref and release date).

Requests are bounded: only unverified events are looked at, every series-year
is fetched once per run (BLS API v2 keyless limit is 25 queries/day), and an
event whose lookup or anchor fails is retried at most every 3 hours.
"""
import json
import sys
from datetime import datetime, timedelta, date
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
from official_bls_actuals import DEFS  # noqa: E402
from official_bls_api import SERIES, fetch_series, calculate  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CAL = ROOT / 'market-observatory' / 'data' / 'economic-calendar.json'
HIST = ROOT / 'market-observatory' / 'data' / 'economic-calendar-history.json'
KST = ZoneInfo('Asia/Seoul')
SOURCE = 'BLS_API official series (reconciled)'
MONTHLY = {code for code in SERIES if code != 'prod2'}
LOOKBACK_DAYS = 400
RETRY_AFTER = timedelta(hours=3)


def clean(v):
    if v is None:
        return None
    s = str(v).strip()
    return None if s in ('', 'None', 'null', 'nan', 'N/A', '-') else s


def norm(v):
    s = clean(v)
    if s is None:
        return None
    s = s.replace('+', '')
    try:
        unit = ''.join(ch for ch in s if ch.isalpha() or ch == '%')
        num = float(s.replace(unit, '')) if unit else float(s)
        return f'{num:.1f}{unit}'
    except ValueError:
        return s


def is_official(m):
    return str(m.get('verification_status') or '').startswith('VERIFIED_OFFICIAL')


# Usual publication lag in months, tried first (JOLTS trails by two months).
FIRST_LAG = {'jolts': 2}


def candidate_months(day, code=None):
    y, m = day.year, day.month
    first = FIRST_LAG.get(code, 1)
    for back in [first] + [b for b in (1, 2, 3) if b != first]:
        o = y * 12 + (m - 1) - back
        yield o // 12, o % 12 + 1


def official_values(code, year, month, fetch=fetch_series):
    """All metrics of the release for one month, or None if any is missing.

    A partial answer (API throttling, month not yet published) must never be
    used: with fewer metrics a coincidental match can anchor the wrong month.
    """
    out = {}
    for key, (series, lag, unit) in SERIES[code].items():
        try:
            values, url = fetch(series, year)
            out[key] = (calculate(values, year, month, lag, unit), url, series)
        except KeyError:
            return None
        except Exception as exc:
            raise RuntimeError(f'BLS_API_UNAVAILABLE {series}: {exc}') from exc
    return out


def resolve(event, code, fetch=fetch_series, claimed=()):
    """Pick the reference month with the most exact market-feed matches.

    Ties go to the usual publication lag. Months already owned by another
    officially verified release of the same series are excluded.
    """
    day = date.fromisoformat(str(event.get('datetime_kst'))[:10])
    feed = {m.get('key'): norm(m.get('actual')) for m in event.get('market_metrics') or []
            if isinstance(m, dict) and clean(m.get('actual')) is not None}
    best = (None, {}, [])
    for year, month in candidate_months(day, code):
        if f'{year}-{month:02d}' in claimed:
            continue
        vals = official_values(code, year, month, fetch)
        if not vals:
            continue
        anchors = [k for k, (v, _, _) in vals.items() if feed.get(k) is not None and feed[k] == norm(v)]
        if len(anchors) > len(best[2]):
            best = ((year, month), vals, anchors)
    return best


def apply(cal, hist, now=None, fetch=fetch_series):
    now = (now or datetime.now(KST)).astimezone(KST)
    series = (hist or {}).get('series') or {}
    report = {'events_checked': 0, 'events_reconciled': 0, 'metrics_changed': 0,
              'history_rows_changed': 0, 'anchor_failed': [], 'changes': []}
    for e in cal.get('events') or []:
        code = (DEFS.get(e.get('title')) or (None,))[0]
        if code not in MONTHLY or e.get('country') != 'US':
            continue
        if str(e.get('actual_status') or '').upper() != 'RELEASED':
            continue
        day = str(e.get('datetime_kst') or '')[:10]
        try:
            age = (now.date() - date.fromisoformat(day)).days
        except ValueError:
            continue
        if age < 0 or age > LOOKBACK_DAYS:
            continue
        metrics = [m for m in e.get('market_metrics') or [] if isinstance(m, dict) and m.get('key') in SERIES[code]]
        if not metrics or all(is_official(m) for m in metrics):
            continue
        last_fail = str(e.get('official_reconcile_failed_kst') or '')
        if last_fail and (now - datetime.fromisoformat(last_fail)) < RETRY_AFTER:
            continue
        report['events_checked'] += 1
        claimed = {str(x.get('reference_period') or '')[:7]
                   for o in cal.get('events') or [] if o is not e and DEFS.get(o.get('title'), (None,))[0] == code
                   for x in o.get('market_metrics') or [] if isinstance(x, dict) and is_official(x)}
        try:
            period, vals, anchors = resolve(e, code, fetch, claimed)
        except RuntimeError as exc:
            e['official_reconcile_failed_kst'] = now.isoformat(timespec='seconds')
            report['anchor_failed'].append(f"{day} {e.get('title')} ({exc})"[:200])
            continue
        if not period:
            e['official_reconcile_failed_kst'] = now.isoformat(timespec='seconds')
            report['anchor_failed'].append(f"{day} {e.get('title')}")
            continue
        e.pop('official_reconcile_failed_kst', None)
        ref_text = f'{period[0]}-{period[1]:02d}'
        e['official_reconcile'] = {'reference_period': ref_text, 'anchors': anchors,
                                   'checked_kst': now.isoformat(timespec='seconds')}
        report['events_reconciled'] += 1
        for m in metrics:
            if m['key'] not in vals:
                continue
            value, url, sid = vals[m['key']]
            old = clean(m.get('actual'))
            prov = {'actual_source': SOURCE, 'source': SOURCE, 'source_tier': 'OFFICIAL',
                    'verification_status': 'VERIFIED_OFFICIAL_REVISED', 'value_vintage': 'LATEST_REVISION',
                    'reference_period': ref_text, 'series_id': sid, 'official_url': url}
            if norm(old) != norm(value):
                m['market_feed_actual'] = old
                report['metrics_changed'] += 1
                report['changes'].append(f"{day} {m['key']}: {old} -> {value}")
            m['actual'] = value
            m.update(prov)
            bucket = series.get(m.get('history_ref')) or {}
            for row in bucket.get('rows') or []:
                if str(row.get('date') or '')[:10] != day:
                    continue
                if norm(row.get('actual')) != norm(value):
                    row['market_feed_actual'] = clean(row.get('actual'))
                    report['history_rows_changed'] += 1
                row['actual'] = value
                row.update(prov)
                row['checked_kst'] = now.isoformat(timespec='seconds')
    return report


def main():
    if not CAL.exists() or not HIST.exists():
        print('BLS_OFFICIAL_RECONCILE=SKIP missing file')
        return 0
    cal = json.loads(CAL.read_text(encoding='utf-8'))
    hist = json.loads(HIST.read_text(encoding='utf-8'))
    report = apply(cal, hist)
    if report['events_checked']:
        CAL.write_text(json.dumps(cal, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        if report['history_rows_changed'] or report['events_reconciled']:
            HIST.write_text(json.dumps(hist, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    for line in report['changes']:
        print('BLS_OFFICIAL_RECONCILE_CHANGE', line)
    print('BLS_OFFICIAL_RECONCILE=PASS ' + json.dumps({k: v for k, v in report.items() if k != 'changes'}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
