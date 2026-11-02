#!/usr/bin/env python3
"""Refresh the Korean Treasury yield curve in Observatory from BOK ECOS.

Uses the canonical BOK series identities, validates item identity, merges only
verified observations and never fabricates/interpolates yields.  The public
ECOS `sample` key is limited to 10 rows per request, so freshness uses a cheap
head request to discover `list_total_count` followed by an explicit tail page.
Registered keys retain the normal larger page size.
"""
from __future__ import annotations

import json
import math
import os
import urllib.parse
import urllib.request
import urllib.error
import socket
import ssl
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
OBS = ROOT / 'market-observatory' / 'data' / 'observatory.json'
KST = ZoneInfo('Asia/Seoul')
UA = 'Mozilla/5.0 JJOONI-KR-Rates-Freshness/1.1'
STAT_CODE = '817Y002'
KR_RATES = {
    'KR3Y': '010200000',
    'KR5Y': '010200001',
    'KR10Y': '010210000',
    'KR20Y': '010220000',
    'KR30Y': '010230000',
}
REGISTERED_MAX_PAGE = 1000
SAMPLE_MAX_PAGE = 10
LOOKBACK_DAYS = 500
INCREMENTAL_LOOKBACK_DAYS = 14


def _fallback_json(url: str) -> dict:
    """Same official HTTPS endpoint through libcurl; never expose the key URL."""
    try:
        from curl_cffi import requests
        response = requests.get(url, headers={'User-Agent': UA, 'Accept': 'application/json'},
                                impersonate='chrome', timeout=(5, 15))
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        # Exception strings may embed the registered key. Keep only the class.
        raise RuntimeError('ECOS_CURL_FALLBACK_' + type(exc).__name__) from None



def _diagnose_ecos_connectivity() -> str:
    """Secret-free diagnostics against the documented official HTTPS origin.

    No registered-key URL or API request is issued by this probe. A successful
    TLS connection is NOT treated as evidence that StatisticSearch works.
    """
    host = 'ecos.bok.or.kr'
    try:
        socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except OSError:
        return 'DNS_UNAVAILABLE'
    try:
        with socket.create_connection((host, 443), timeout=3) as sock:
            with ssl.create_default_context().wrap_socket(sock, server_hostname=host):
                return 'TLS_OK_API_RESPONSE_UNVERIFIED'
    except ssl.SSLError:
        return 'TLS_FAILURE'
    except TimeoutError:
        return 'TCP_OR_TLS_TIMEOUT'
    except OSError:
        return 'TCP_FAILURE'


def _get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'application/json'})
    # Retry transient transport errors only, with a bounded per-request budget.
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return json.loads(r.read().decode('utf-8'))
        except urllib.error.HTTPError as exc:
            if exc.code not in {429, 500, 502, 503, 504}:
                raise RuntimeError(f'ECOS_HTTP_{exc.code}') from None
        except (urllib.error.URLError, TimeoutError, OSError):
            pass
        if attempt < 2:
            time.sleep(0.5 * (attempt + 1))
    # Never include the URL (which contains the registered API key) in errors.
    try:
        result = _fallback_json(url)
        print('ECOS_TRANSPORT_RECOVERED=HTTPS_LIBCURL_FALLBACK')
        return result
    except RuntimeError as exc:
        diagnostic = _diagnose_ecos_connectivity()
        # A key is a path segment in ECOS URLs; never log the request or exception
        # object from a network library. Emit only fixed diagnostic categories.
        print('ECOS_NETWORK_DIAGNOSTIC=' + diagnostic)
        raise RuntimeError('ECOS_TRANSPORT_FAILED_AFTER_3_ATTEMPTS;' + str(exc) +
                           ';ECOS_NETWORK_' + diagnostic) from None


def _url(key: str, start_count: int, end_count: int, start: str, end: str, item: str) -> str:
    safe_key = urllib.parse.quote(key, safe='')
    return (
        'https://ecos.bok.or.kr/api/StatisticSearch/' + safe_key +
        f'/json/kr/{start_count}/{end_count}/{STAT_CODE}/D/{start}/{end}/{item}'
    )


def _page_size(key: str) -> int:
    return SAMPLE_MAX_PAGE if str(key or '').strip().lower() == 'sample' else REGISTERED_MAX_PAGE


def _api_mode(key: str) -> str:
    return 'sample' if str(key or '').strip().lower() == 'sample' else 'registered'


def _result_error(obj: dict) -> str | None:
    result = obj.get('RESULT') or {}
    code = str(result.get('CODE') or '').strip()
    if code and code not in {'INFO-000'}:
        return code
    return None


def _extract_rows(obj: dict, item: str) -> tuple[list[dict], int]:
    block = obj.get('StatisticSearch') or {}
    raw = block.get('row') or []
    total = int(block.get('list_total_count') or len(raw) or 0)
    out = []
    for r in raw:
        if r.get('STAT_CODE') and str(r.get('STAT_CODE')) != STAT_CODE:
            continue
        if r.get('ITEM_CODE1') and str(r.get('ITEM_CODE1')) != item:
            continue
        t = str(r.get('TIME') or '').strip()
        if len(t) == 8 and t.isdigit():
            d = f'{t[:4]}-{t[4:6]}-{t[6:8]}'
        else:
            d = t[:10]
        try:
            v = float(r.get('DATA_VALUE'))
        except Exception:
            continue
        if len(d) != 10 or not math.isfinite(v) or v <= -20 or v >= 50:
            continue
        out.append({'date': d, 'value': round(v, 8)})
    return out, total


def fetch_ecos_series(key: str, item: str, start: str, end: str) -> list[dict]:
    page_size = _page_size(key)
    first = _get_json(_url(key, 1, page_size, start, end, item))
    err = _result_error(first)
    if err:
        raise RuntimeError(f'ECOS_{item}_{err}')
    rows, total = _extract_rows(first, item)

    # ECOS is ascending.  We only need the latest verified observations for the
    # freshness repair, so jump directly to the tail instead of crawling pages.
    if total > page_size:
        begin = max(1, total - page_size + 1)
        tail = _get_json(_url(key, begin, total, start, end, item))
        err = _result_error(tail)
        if err:
            raise RuntimeError(f'ECOS_{item}_{err}')
        tail_rows, _ = _extract_rows(tail, item)
        rows.extend(tail_rows)

    ded = {x['date']: x for x in rows}
    result = [ded[d] for d in sorted(ded)]
    if not result:
        raise RuntimeError(f'ECOS_{item}_NO_VERIFIED_ROWS')
    return result


def merge_rows(old: list[dict] | None, fresh: list[dict] | None) -> list[dict]:
    ded = {
        str(x.get('date') or '')[:10]: dict(x)
        for x in (old or [])
        if x.get('date') and x.get('value') is not None
    }
    for x in fresh or []:
        if x.get('date') and x.get('value') is not None:
            ded[str(x['date'])[:10]] = dict(x)
    return [ded[d] for d in sorted(ded)]


def _age_days(d: str | None) -> int | None:
    try:
        return (datetime.now(KST).date() - date.fromisoformat(str(d)[:10])).days
    except Exception:
        return None


def refresh(data: dict, api_key: str | None = None) -> dict:
    api_key = (api_key or os.getenv('BOK_ECOS_API_KEY') or 'sample').strip()
    api_mode = _api_mode(api_key)
    end_d = datetime.now(KST).date()
    start_d = end_d - timedelta(days=LOOKBACK_DAYS)
    start = start_d.strftime('%Y%m%d')
    end = end_d.strftime('%Y%m%d')
    series = data.setdefault('series', {})
    latest = data.setdefault('latest', {})
    quality = data.setdefault('cross_market_freshness_quality', {})
    source = 'BOK ECOS 817Y002 daily market rates'
    failures = {}
    last_dates = {}
    refreshed_status = {}

    transport_unavailable = False
    for name, item in KR_RATES.items():
        try:
            if transport_unavailable:
                raise RuntimeError('ECOS_TRANSPORT_CIRCUIT_OPEN_THIS_RUN')
            old_last = str(((series.get(name) or [{}])[-1]).get('date') or '')[:10]
            old_age = _age_days(old_last)
            request_start = ((end_d - timedelta(days=INCREMENTAL_LOOKBACK_DAYS)).strftime('%Y%m%d')
                             if old_age is not None and 0 <= old_age <= 10 else start)
            fresh = fetch_ecos_series(api_key, item, request_start, end)
            merged = merge_rows(series.get(name), fresh)
            series[name] = merged
            latest[name] = merged[-1]['value'] if merged else None
            last = merged[-1]['date'] if merged else None
            last_dates[name] = last
            age = _age_days(last)
            status = 'LIVE' if age is not None and age <= 4 else ('LAGGING' if last else 'UNAVAILABLE')
            refreshed_status[name] = status
            quality[name] = {
                'status': status,
                'source': source,
                'stat_code': STAT_CODE,
                'item_code': item,
                'last_date': last,
                'age_days': age,
                'verified_rows': len(fresh),
                'api_mode': api_mode,
                'fetch_succeeded': True,
            }
            print(f'KR_RATE_REFRESH={name} status={status} last_date={last} rows={len(fresh)} api_mode={api_mode}')
        except Exception as exc:
            if str(exc).startswith('ECOS_TRANSPORT_FAILED_AFTER_3_ATTEMPTS'):
                transport_unavailable = True
            old = series.get(name) or []
            last = str((old[-1] if old else {}).get('date') or '')[:10] or None
            last_dates[name] = last
            failures[name] = f'{type(exc).__name__}:{exc}'
            refreshed_status[name] = 'STALE' if last else 'UNAVAILABLE'
            quality[name] = {
                'status': refreshed_status[name],
                'source': source,
                'stat_code': STAT_CODE,
                'item_code': item,
                'last_date': last,
                'api_mode': api_mode,
                'fetch_succeeded': False,
                'fetch_error': failures[name],
            }
            print(f'KR_RATE_REFRESH={name} status={quality[name]["status"]} last_date={last} api_mode={api_mode} error={failures[name]}')

    # Derived spread only from observations sharing the exact same date.
    kr3 = {x['date']: x['value'] for x in series.get('KR3Y', []) if x.get('date') and x.get('value') is not None}
    kr10 = {x['date']: x['value'] for x in series.get('KR10Y', []) if x.get('date') and x.get('value') is not None}
    common = sorted(set(kr3) & set(kr10))
    series['KR_3S10S'] = [{'date': d, 'value': round(kr10[d] - kr3[d], 8)} for d in common]
    latest['KR_3S10S'] = series['KR_3S10S'][-1]['value'] if common else None
    last_dates['KR_3S10S'] = common[-1] if common else None

    group_live = (
        not failures
        and set(refreshed_status) == set(KR_RATES)
        and all(refreshed_status.get(k) == 'LIVE' for k in KR_RATES)
    )
    quality['KR_RATES'] = {
        'status': 'LIVE' if group_live else 'LAGGING',
        'source': source,
        'api_mode': api_mode,
        'fetch_succeeded': not failures,
        'last_dates': last_dates,
        'refreshed_status': refreshed_status,
        'failed_series': failures,
        'spread_contract': 'SAME_DATE_KR10Y_MINUS_KR3Y_NO_INTERPOLATION',
    }
    data.setdefault('sources', {})['KR_RATES_CURRENT'] = source
    data['kr_rates_refreshed_kst'] = datetime.now(KST).isoformat(timespec='seconds')
    return data


def main() -> None:
    data = json.loads(OBS.read_text(encoding='utf-8'))
    refresh(data)
    OBS.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    q = (data.get('cross_market_freshness_quality') or {}).get('KR_RATES') or {}
    print(
        'KR_RATES_REFRESH=' + str(q.get('status')) +
        ' api_mode=' + str(q.get('api_mode')) +
        ' fetch_succeeded=' + str(q.get('fetch_succeeded')) +
        ' last_dates=' + json.dumps(q.get('last_dates') or {}, ensure_ascii=False, sort_keys=True)
    )


if __name__ == '__main__':
    main()
