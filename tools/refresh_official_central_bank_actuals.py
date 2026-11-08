#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import re
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
CAL = ROOT / 'market-observatory' / 'data' / 'economic-calendar.json'
KST = ZoneInfo('Asia/Seoul')
ET = ZoneInfo('America/New_York')
from official_calendar_collectors import official_user_agent
UA = official_user_agent()
GRACE_MINUTES = 45
# Unresolved actuals have no expiry.
from calendar_actual_contract import build_freshness
from official_calendar_collectors import apply_official_actuals


def clean(v):
    if v is None:
        return None
    s = str(v).strip()
    return None if s in ('', 'None', 'null', 'nan', 'N/A', '-') else s


def fetch_text(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={
            'User-Agent': UA,
            'Accept': 'text/html,application/xhtml+xml',
        },
    )
    with urllib.request.urlopen(req, timeout=25) as response:
        raw = response.read().decode('utf-8', errors='replace')
    text = re.sub(r'<script\b[^>]*>.*?</script>', ' ', raw, flags=re.I | re.S)
    text = re.sub(r'<style\b[^>]*>.*?</style>', ' ', text, flags=re.I | re.S)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = html.unescape(text)
    return re.sub(r'\s+', ' ', text).strip()


def mixed_number(token: str) -> float:
    t = str(token).strip().replace('–', '-').replace('—', '-')
    m = re.fullmatch(r'(\d+)-(\d+)/(\d+)', t)
    if m:
        whole, numerator, denominator = map(int, m.groups())
        if denominator == 0:
            raise ValueError(f'invalid mixed number: {token}')
        return whole + numerator / denominator
    return float(t)


def fed_target_upper_from_statement(text: str) -> float | None:
    text = re.sub(r"[‐‑‒–—−]", "-", text)
    patterns = [
        r'target range for the federal funds rate.{0,220}?(?:to|at)\s+'
        r'(\d+(?:-\d+/\d+|\.\d+)?)\s+to\s+'
        r'(\d+(?:-\d+/\d+|\.\d+)?)\s+percent',
        r'federal funds rate in a target range of\s+'
        r'(\d+(?:-\d+/\d+|\.\d+)?)\s+to\s+'
        r'(\d+(?:-\d+/\d+|\.\d+)?)\s+percent',
    ]
    for pattern in patterns:
        m = re.search(pattern, text, flags=re.I | re.S)
        if m:
            return mixed_number(m.group(2))
    return None


def event_dt(event: dict) -> datetime | None:
    raw = str(event.get('datetime_kst') or '').strip()
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw)
        return dt if dt.tzinfo else dt.replace(tzinfo=KST)
    except ValueError:
        return None


def append_source(existing, source: str) -> str:
    current = str(existing or '').strip()
    if not current:
        return source
    if source.lower() in current.lower():
        return current
    return f'{current} + {source}'


def apply_fomc_official_actual(calendar: dict, now: datetime) -> tuple[int, list[dict]]:
    updates = 0
    checks: list[dict] = []
    for event in calendar.get('events') or []:
        if event.get('country') != 'US' or event.get('title') != 'FOMC 정책결정':
            continue
        dt = event_dt(event)
        if not dt:
            continue
        age = now - dt.astimezone(KST)
        rate = next((m for m in event.get('market_metrics', []) if m.get('key') == 'fed_rate'), {})
        complete = clean(event.get('actual')) is not None and clean(rate.get('actual')) is not None
        if age < timedelta(0) or (complete and event.get('source_tier') == 'OFFICIAL' and rate.get('source_tier') == 'OFFICIAL'):
            continue

        release_day = dt.astimezone(ET).strftime('%Y%m%d')
        url = f'https://www.federalreserve.gov/newsevents/pressreleases/monetary{release_day}a.htm'
        status = {'event_kst': dt.astimezone(KST).isoformat(), 'url': url, 'result': 'NOT_FOUND'}
        try:
            text = fetch_text(url)
            upper = fed_target_upper_from_statement(text)
            if upper is None:
                status['result'] = 'PARSE_MISS'
                checks.append(status)
                continue
            actual = f'{upper:.2f}%'
            before = clean(event.get('actual'))
            event['actual'] = actual
            provenance = {'source_tier': 'OFFICIAL', 'source_url': url, 'official_url': url, 'checked_kst': now.isoformat(timespec='seconds'), 'verification_status': 'VERIFIED_OFFICIAL'}
            event.update(provenance)
            event['official_actual_source'] = 'Federal Reserve official FOMC statement'
            event['official_actual_url'] = url
            event['official_actual_checked_kst'] = now.isoformat(timespec='seconds')
            event['market_data_source'] = append_source(event.get('market_data_source'), 'Federal Reserve official')
            if not rate:
                event.setdefault('market_metrics', []).append({'key': 'fed_rate', 'label': 'Federal Funds Rate'})
            for metric in event.get('market_metrics') or []:
                if metric.get('key') == 'fed_rate':
                    metric['actual'] = actual
                    metric.update(provenance)
                    metric['source'] = 'Federal Reserve official FOMC statement'
                    metric['official_url'] = url
            if before != actual:
                updates += 1
            status['result'] = 'UPDATED' if before != actual else 'CONFIRMED'
            status['actual'] = actual
        except urllib.error.HTTPError as exc:
            status['result'] = f'HTTP_{exc.code}'
        except Exception as exc:
            status['result'] = f'ERROR_{type(exc).__name__}'
        checks.append(status)
    return updates, checks


def expected_actual_metrics(event: dict) -> list[dict]:
    metrics = []
    for metric in event.get('market_metrics') or []:
        if not isinstance(metric, dict):
            continue
        if metric.get('metric_type') == 'market_probability_snapshot':
            continue
        if metric.get('value_role') == 'market_forecast':
            continue
        metrics.append(metric)
    return metrics


def build_actual_freshness(calendar: dict, now: datetime, official_checks: list[dict]) -> dict:
    return build_freshness(calendar, now, official_checks)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--health-only', action='store_true')
    parser.add_argument('--strict', action='store_true', help='exit non-zero when a major actual is overdue')
    args = parser.parse_args()

    calendar = json.loads(CAL.read_text(encoding='utf-8'))
    now = datetime.now(KST)
    updates, official_checks = (0, []) if args.health_only else apply_fomc_official_actual(calendar, now)
    extra, checks = (0, []) if args.health_only else apply_official_actuals(calendar, now)
    updates += extra
    official_checks += checks
    if args.health_only:
        official_checks = (calendar.get('actual_freshness') or {}).get('official_checks', [])
    freshness = build_actual_freshness(calendar, now, official_checks)
    calendar['actual_freshness'] = freshness
    calendar['generated_kst'] = now.isoformat(timespec='seconds')
    calendar['official_actual_contract'] = 'OFFICIAL_REGISTRY_BACKFILL_V2'
    calendar['official_actual_updated_kst'] = now.isoformat(timespec='seconds')
    CAL.write_text(json.dumps(calendar, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    print(
        'OFFICIAL_ACTUAL_REFRESH=PASS',
        f'fomc_updates={updates}',
        f'status={freshness["status"]}',
        f'pending={freshness["pending_count"]}',
        f'overdue={freshness["overdue_count"]}',
    )
    if args.strict and freshness['status'] == 'DEGRADED':
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
