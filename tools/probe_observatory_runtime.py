#!/usr/bin/env python3
"""Read-only public runtime proof, executed by the existing crypto collector.

No account APIs, credentials, cloud resources or market observations are written.
The log receipt lets restricted monitoring environments verify a recent external
check without treating their own DNS failure as a production-service outage.
"""
from __future__ import annotations
import json
import math
import os
import socket
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ORIGIN = 'https://mauveplace.github.io'
PAGES = ORIGIN + '/jjooni-control-tower/market-observatory/data/'
API = 'https://jjooni-ct-fast-apgynr7pea-du.a.run.app/observatory/quotes'
SYMBOLS = {'BTCUSD': 'BTC-USD', 'ETHUSD': 'ETH-USD'}
ROOT = Path(__file__).resolve().parents[1]


def stamp(value):
    dt = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if dt.tzinfo is None:
        raise ValueError('UNZONED_OBSERVATION')
    return dt


def age(value, now, limit):
    seconds = (now - stamp(value)).total_seconds()
    if seconds < -30:
        raise ValueError('FUTURE_OBSERVATION')
    if seconds > limit:
        raise ValueError('STALE_OBSERVATION')
    return max(0, int(seconds))


def fetch_json(url, timeout=10):
    # All callers use the fixed public endpoints above; no token/auth headers.
    req = urllib.request.Request(url, headers={
        'User-Agent': 'JJOONI-Observatory-Runtime-Probe/1.0',
        'Accept': 'application/json', 'Origin': ORIGIN, 'Cache-Control': 'no-cache'})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        raw = response.read(3_000_001)
        if len(raw) > 3_000_000:
            raise ValueError('RESPONSE_TOO_LARGE')
        return json.loads(raw), response.status, dict(response.headers.items())


def category(exc):
    if isinstance(exc, urllib.error.HTTPError):
        return 'HTTP_' + str(exc.code)
    reason = getattr(exc, 'reason', exc)
    if isinstance(reason, socket.gaierror):
        return 'PROBE_DNS_FAILURE'
    if isinstance(reason, (TimeoutError, socket.timeout)):
        return 'PROBE_TIMEOUT'
    if isinstance(exc, ValueError):
        # Our fixed validation errors only; parser messages need not enter logs.
        message = str(exc)
        return message if message.isupper() and len(message) < 80 else 'INVALID_RESPONSE'
    return 'PROBE_TRANSPORT_FAILURE'


def validate_api(payload, status, headers, now):
    if status != 200:
        raise ValueError('API_HTTP_NOT_200')
    if payload.get('schema') != 'JJOONI_OBSERVATORY_QUOTES_V1':
        raise ValueError('API_SCHEMA_MISMATCH')
    cors = {k.lower(): v for k, v in headers.items()}.get('access-control-allow-origin')
    if cors != ORIGIN:
        raise ValueError('API_PAGES_CORS_MISMATCH')
    rows = {}
    for key, symbol in SYMBOLS.items():
        row = payload.get('quotes', {}).get(key) or {}
        value = row.get('value')
        if (row.get('key') != key or row.get('symbol') != symbol or
                isinstance(value, bool) or not isinstance(value, (int, float)) or
                not math.isfinite(value) or value <= 0):
            raise ValueError('API_CRYPTO_IDENTITY_OR_VALUE_INVALID')
        seconds = age(row.get('observed_at'), now, 600)
        if not row.get('source') or row.get('market_state') != 'CONTINUOUS':
            raise ValueError('API_CRYPTO_PROVENANCE_MISSING')
        if row.get('refresh_status') != 'FETCHED' or row.get('quality') == 'STALE':
            raise ValueError('API_CRYPTO_RETAINED_OR_STALE')
        rows[key] = {'observed_at': row['observed_at'], 'age_seconds': seconds,
                     'source': row.get('source')}
    return {'status': 'PASS', 'http_status': status, 'cors_origin': cors,
            'coverage': payload.get('status'),
            'fetched_count': payload.get('fetched_count'),
            'expected_count': payload.get('expected_count'),
            'unavailable_keys': sorted((payload.get('failures') or {}).keys()), 'quotes': rows}


def validate_pages(fresh, recent, expected, now):
    if fresh.get('schema') != 'JJOONI_OBSERVATORY_FRESHNESS_STATUS_V2':
        raise ValueError('PAGES_FRESHNESS_SCHEMA_MISMATCH')
    if recent.get('schema') != 'JJOONI_MARKET_OBSERVATORY_V1':
        raise ValueError('PAGES_MARKET_SCHEMA_MISMATCH')
    quotes = {}
    for key in SYMBOLS:
        baseline = expected.get('crypto_market', {}).get(key) or {}
        base_time = stamp(baseline.get('quote_as_of_kst'))
        if baseline.get('status') != 'LIVE':
            raise ValueError('COLLECTED_BASELINE_NOT_LIVE')
        for row in [(fresh.get('groups', {}).get('crypto', {}).get('quotes') or {}).get(key) or {},
                    (recent.get('crypto_market') or {}).get(key) or {}]:
            age(row.get('quote_as_of_kst'), now, 3600)
            if row.get('status') != 'LIVE' or stamp(row.get('quote_as_of_kst')) < base_time:
                raise ValueError('PAGES_AWAITING_COLLECTED_OBSERVATION')
        row = recent['crypto_market'][key]
        price = row.get('price')
        if (isinstance(price, bool) or not isinstance(price, (int, float)) or
                not math.isfinite(price) or price <= 0 or not row.get('source')):
            raise ValueError('PAGES_CRYPTO_VALUE_OR_SOURCE_INVALID')
        if stamp(row['quote_as_of_kst']) == base_time:
            if price != baseline.get('price') or row['source'] != baseline.get('source'):
                raise ValueError('PAGES_SAME_OBSERVATION_MISMATCH')
        quotes[key] = {'quote_as_of_kst': row['quote_as_of_kst'], 'source': row['source']}
    return {'status': 'PASS', 'http_status': 200, 'quotes': quotes,
            'basis': 'PUBLISHED_BASELINE_OR_NEWER_NOT_DEPLOYMENT_STATUS_ONLY'}


def probe(expected, fetch=fetch_json, clock=lambda: datetime.now(timezone.utc),
          monotonic=time.monotonic, pause=time.sleep, pages_budget=150):
    result = {'schema': 'JJOONI_OBSERVATORY_RUNTIME_PROOF_V1',
              'run_id': os.getenv('GITHUB_RUN_ID'), 'run_attempt': os.getenv('GITHUB_RUN_ATTEMPT'),
              'checked_at': clock().isoformat(), 'orders': 'NONE', 'read_only': True}
    for attempt in (1, 2):
        try:
            payload, status, headers = fetch(API, 10)
            result['api'] = validate_api(payload, status, headers, clock())
            result['api'].update(checked_at=clock().isoformat(), attempts=attempt)
            break
        except Exception as exc:
            result['api'] = {'status': 'FAIL', 'reason': category(exc),
                             'checked_at': clock().isoformat(), 'attempts': attempt}
            if attempt == 1:
                pause(5)
    deadline = monotonic() + pages_budget
    attempts = 0
    while True:
        attempts += 1
        try:
            suffix = '?runtime_probe=' + str(os.getenv('GITHUB_RUN_ID', 'local')) + '.' + str(os.getenv('GITHUB_RUN_ATTEMPT', '1'))
            fresh, status, _ = fetch(PAGES + 'freshness-status.json' + suffix, 10)
            if status != 200:
                raise ValueError('PAGES_HTTP_NOT_200')
            recent, status, _ = fetch(PAGES + 'observatory-recent.json' + suffix, 10)
            if status != 200:
                raise ValueError('PAGES_HTTP_NOT_200')
            result['pages'] = validate_pages(fresh, recent, expected, clock())
            result['pages'].update(attempts=attempts, checked_at=clock().isoformat())
            break
        except Exception as exc:
            result['pages'] = {'status': 'FAIL', 'reason': category(exc), 'attempts': attempts}
            if monotonic() >= deadline:
                break
            pause(min(5, max(0, deadline - monotonic())))
    result['checked_at'] = clock().isoformat()
    result['status'] = 'PASS' if all(result[k]['status'] == 'PASS' for k in ('api', 'pages')) else 'FAIL'
    return result


def main():
    expected = json.loads((ROOT / 'market-observatory/data/observatory.json').read_text())
    receipt = probe(expected)
    commit = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True)
    receipt['published_commit'] = commit.stdout.strip() if commit.returncode == 0 else None
    print('OBSERVATORY_RUNTIME_PROOF=' + json.dumps(receipt, ensure_ascii=False, separators=(',', ':')), flush=True)
    raise SystemExit(0 if receipt['status'] == 'PASS' else 1)


if __name__ == '__main__':
    main()
