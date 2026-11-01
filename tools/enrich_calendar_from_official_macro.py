#!/usr/bin/env python3
"""Bridge verified official-macro releases into matching KR calendar events.

The official macro SSOT already carries identity-checked KOSTAT series through
BOK ECOS.  Some KOSTAT schedule events do not have a dedicated calendar
collector, so their event-level actual can remain overdue even though the same
release is already verified in official-macro.json.

This adapter is deliberately narrow and fail-closed:
- only explicitly mapped Korean releases are eligible;
- the year/month encoded in the calendar title must exactly match the official
  macro release reference period;
- only LIVE + OFFICIAL + identity-verified macro metrics are accepted;
- merge_observation owns precedence, so lower-quality data cannot overwrite a
  verified official actual;
- no value is inferred or invented.
"""
from __future__ import annotations

import html
import json
import math
import re
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from calendar_actual_contract import merge_observation

ROOT = Path(__file__).resolve().parents[1]
CAL = ROOT / 'market-observatory/data/economic-calendar.json'
MACRO = ROOT / 'market-observatory/data/official-macro.json'
KST = ZoneInfo('Asia/Seoul')

# Date-locked official press-release fallback for the 2026-09 industrial
# production release. Future months require their own verified official URL;
# an older BOK ECOS vintage must never be silently relabeled as September.
KOSTAT_INDUSTRIAL_RELEASES = {
    '2026-09-01': (
        '2026-10-30',
        'https://mods.go.kr/board.es?act=view&bid=216&list_no=447747&mainXml=Y&mid=a10301010000',
    ),
}


def _fetch_kostat_release(url: str) -> str:
    request = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 JJOONI-Official-Calendar/2.0'})
    with urllib.request.urlopen(request, timeout=12) as response:
        return response.read().decode('utf-8', errors='replace')


def _parse_kostat_industrial_release(page: str, expected_period: str, release_date: str) -> str:
    year, month, day = map(int, expected_period.split('-'))
    if day != 1:
        raise ValueError('REFERENCE_PERIOD_DAY_MISMATCH')
    clean_page = re.sub(r'<(script|style)\b[^>]*>.*?</\1>', ' ', page, flags=re.I | re.S)
    clean_page = re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', clean_page)))
    title = rf'{year}년\s*{month}월\s*산업활동동향'
    if not re.search(title, clean_page):
        raise ValueError('KOSTAT_INDUSTRIAL_REFERENCE_PERIOD_MISMATCH')
    if not re.search(rf'게시일\s*{re.escape(release_date)}(?!\d)', clean_page):
        raise ValueError('KOSTAT_INDUSTRIAL_PUBLICATION_DATE_MISMATCH')
    match = re.search(
        r'□\s*\(\s*생산\s*\)\s*전산업생산은.{0,250}?전월\s*대비\s*'
        r'(\d+(?:\.\d+)?)\s*%\s*(증가|감소)',
        clean_page,
    )
    if not match:
        raise ValueError('KOSTAT_INDUSTRIAL_MOM_HEADLINE_NOT_FOUND')
    value = float(match.group(1))
    if not 0 <= value <= 50:
        raise ValueError('KOSTAT_INDUSTRIAL_MOM_OUT_OF_RANGE')
    sign = '-' if match.group(2) == '감소' and value else ''
    return f'{sign}{match.group(1)}%'


def _apply_kostat_industrial_release(event: dict, expected: str, now: datetime, fetcher):
    if fetcher is None or event.get('title') != '2026년 9월 산업활동동향':
        return None
    if _clean(event.get('actual')) is not None:
        return None
    release = KOSTAT_INDUSTRIAL_RELEASES.get(expected)
    if not release:
        return None
    release_date, url = release
    if now.date().isoformat() < release_date:
        return None
    try:
        actual = _parse_kostat_industrial_release(fetcher(url), expected, release_date)
    except Exception as exc:
        return {'status': 'OFFICIAL_RELEASE_UNAVAILABLE', 'source_url': url,
                'reason': f'{type(exc).__name__}: {exc}'[:160]}
    checked = now.isoformat(timespec='seconds')
    source = 'KOSTAT official industrial activity press release'
    patch = {
        'actual': actual, 'source_tier': 'OFFICIAL', 'source': source,
        'market_data_source': source, 'actual_source': source,
        'official_actual_source': source, 'source_url': url,
        'official_url': url, 'official_actual_url': url,
        'checked_kst': checked, 'official_actual_checked_kst': checked,
        'verification_status': 'VERIFIED_OFFICIAL',
        'reference_period': expected[:7], 'value_vintage': 'AS_RELEASED',
        'market_value_status': 'ACTUAL_AVAILABLE',
    }
    event.update(merge_observation(event, patch))
    return {'status': 'APPLIED_OFFICIAL_RELEASE' if event.get('actual') == actual else 'MERGE_REJECTED',
            'actual': event.get('actual'), 'source_url': url, 'reference_period': expected}


MAPPINGS = (
    (re.compile(r'소비자물가동향'), 'KR_CPI'),
    (re.compile(r'산업활동동향'), 'KR_INDUSTRIAL_PRODUCTION'),
)


def _clean(v):
    if v is None:
        return None
    s = str(v).strip()
    return None if s in {'', '-', '—', 'None', 'null', 'N/A', 'nan'} else v


def _reference_period_from_title(title: str) -> str | None:
    m = re.search(r'(20\d{2})년\s*(\d{1,2})월', str(title or ''))
    if not m:
        return None
    year, month = int(m.group(1)), int(m.group(2))
    if not 1 <= month <= 12:
        return None
    return f'{year:04d}-{month:02d}-01'


def _metric_key(event: dict) -> str | None:
    if str(event.get('country') or '').upper() != 'KR':
        return None
    title = str(event.get('title') or '')
    return next((key for pattern, key in MAPPINGS if pattern.search(title)), None)


def _format_actual(value, measure: str | None):
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if not math.isfinite(number):
        return None
    # Preserve the verified value's numerical precision; display code may round.
    raw = f'{number:.8f}'.rstrip('0').rstrip('.')
    return raw + ('%' if '%' in str(measure or '') else '')


def _eligible_release(metric: dict, expected_period: str) -> tuple[bool, str]:
    release = metric.get('release') or {}
    latest = metric.get('latest') or {}
    period = str(release.get('reference_period') or latest.get('period') or '')[:10]
    if period != expected_period:
        return False, f'REFERENCE_PERIOD_MISMATCH:{period or "NONE"}!={expected_period}'
    if metric.get('status') != 'LIVE':
        return False, 'METRIC_NOT_LIVE'
    if metric.get('source_tier') != 'OFFICIAL' and release.get('source_tier') != 'OFFICIAL':
        return False, 'METRIC_NOT_OFFICIAL'
    verification = str(metric.get('verification_status') or '')
    if verification not in {'OFFICIAL_SERIES_IDENTITY_VERIFIED', 'VERIFIED_OFFICIAL'}:
        return False, 'IDENTITY_NOT_VERIFIED'
    if _clean(release.get('actual')) is None:
        return False, 'OFFICIAL_ACTUAL_MISSING'
    return True, 'PASS'


def apply(calendar: dict, macro: dict, now: datetime | None = None, official_release_fetcher=None) -> dict:
    now = (now or datetime.now(KST)).astimezone(KST)
    metrics = macro.get('metrics') or {}
    checked = now.isoformat(timespec='seconds')
    matched = updated = 0
    checks = []

    for event in calendar.get('events') or []:
        key = _metric_key(event)
        if not key:
            continue
        expected = _reference_period_from_title(event.get('title'))
        if not expected:
            checks.append({'title': event.get('title'), 'metric': key, 'status': 'TITLE_PERIOD_UNPARSEABLE'})
            continue
        metric = metrics.get(key) or {}
        ok, reason = _eligible_release(metric, expected)
        check = {'title': event.get('title'), 'metric': key, 'reference_period': expected, 'status': reason}
        if not ok:
            fallback = _apply_kostat_industrial_release(event, expected, now, official_release_fetcher)
            if fallback:
                check.update(fallback)
                if fallback['status'] == 'APPLIED_OFFICIAL_RELEASE':
                    matched += 1
                    updated += 1
            checks.append(check)
            continue

        release = metric.get('release') or {}
        actual = _format_actual(release.get('actual'), release.get('measure'))
        source_url = release.get('source_url') or metric.get('source_url') or (metric.get('transport_source') or {}).get('url')
        source_name = f"{(metric.get('primary_source') or {}).get('institution') or 'KOSTAT'} via BOK ECOS official API"
        before = _clean(event.get('actual'))
        patch = {
            'actual': actual,
            'source_tier': 'OFFICIAL',
            'source': source_name,
            'market_data_source': source_name,
            'actual_source': source_name,
            'official_actual_source': source_name,
            'source_url': source_url,
            'official_url': source_url,
            'official_actual_url': source_url,
            'checked_kst': release.get('checked_kst') or metric.get('checked_kst') or checked,
            'official_actual_checked_kst': release.get('checked_kst') or metric.get('checked_kst') or checked,
            'verification_status': 'VERIFIED_OFFICIAL',
            'reference_period': expected[:7],
            'series_id': metric.get('series_identity') or (metric.get('transport_source') or {}).get('series_id'),
            'value_vintage': 'LATEST_REVISION',
            '_verified_override': True,
            'market_value_status': 'ACTUAL_AVAILABLE',
        }
        event.update(merge_observation(event, patch))
        after = _clean(event.get('actual'))
        matched += 1
        if after is not None and after != before:
            updated += 1
        check.update(status='APPLIED' if after is not None else 'MERGE_REJECTED', actual=after, source_url=source_url)
        checks.append(check)

    report = {
        'schema': 'JJOONI_CALENDAR_OFFICIAL_MACRO_BRIDGE_V1',
        'checked_kst': checked,
        'macro_generated_kst': macro.get('generated_kst'),
        'eligible_mapping_count': len(MAPPINGS),
        'matched_events': matched,
        'updated_events': updated,
        'checks': checks,
        'contract': 'EXACT_REFERENCE_PERIOD_VERIFIED_OFFICIAL_ONLY_NO_INFERENCE',
    }
    calendar['official_macro_calendar_bridge'] = report
    return report


def main():
    calendar = json.loads(CAL.read_text(encoding='utf-8'))
    macro = json.loads(MACRO.read_text(encoding='utf-8'))
    report = apply(calendar, macro, official_release_fetcher=_fetch_kostat_release)
    CAL.write_text(json.dumps(calendar, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('CALENDAR_OFFICIAL_MACRO_BRIDGE=PASS',
          'matched=', report['matched_events'],
          'updated=', report['updated_events'],
          'macro_generated=', report['macro_generated_kst'])


if __name__ == '__main__':
    main()
