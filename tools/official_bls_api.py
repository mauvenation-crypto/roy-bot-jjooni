"""Official series fallback, explicitly distinguished from release-vintage data.

A reference month must come from the official schedule/release or from the
newest period the BLS API itself has published (latest_published_period).
Never infer it from the announcement month: shutdowns and postponements break
that assumption. BLS release pages reject GitHub-hosted runners with HTTP 403,
so the API path is the only official route available to scheduled jobs.
"""
import calendar
import json
import os
import re
from decimal import Decimal, ROUND_HALF_UP
from functools import lru_cache

API = 'https://api.bls.gov/publicAPI/v2/timeseries/data/'
# key: (official series, comparison months, display unit)
SERIES = {
    'cpi': {'cpi_yoy': ('CUUR0000SA0', 12, '%'),
            'cpi_mom': ('CUSR0000SA0', 1, '%'),
            'core_cpi_yoy': ('CUUR0000SA0L1E', 12, '%'),
            'core_cpi_mom': ('CUSR0000SA0L1E', 1, '%')},
    'ppi': {'ppi_yoy': ('WPUFD4', 12, '%'), 'ppi_mom': ('WPSFD4', 1, '%'),
            'core_ppi_yoy': ('WPUFD49104', 12, '%'),
            'core_ppi_mom': ('WPSFD49104', 1, '%')},
    'empsit': {'nfp': ('CES0000000001', 1, 'K'),
               'unemployment': ('LNS14000000', 0, '%'),
               'avg_hourly_mom': ('CES0500000003', 1, '%'),
               'avg_hourly_yoy': ('CES0500000003', 12, '%')},
    'ximpim': {'us_import_price_mom': ('EIUIR', 1, '%'),
               'us_export_price_mom': ('EIUIQ', 1, '%')},
    'jolts': {'jolts': ('JTS000000000000000JOL', 0, 'M')},
    # Published BLS quarterly SAAR changes; do NOT compute these as month-on-month.
    'prod2': {'productivity': ('PRS85006092', 0, '%'),
              'unit_labor': ('PRS85006112', 0, '%')},
}


def reference_month(value):
    names = '|'.join(calendar.month_name[1:])
    match = re.search(r'\b(' + names + r')\s+(20\d{2})\b', str(value), re.I)
    if match:
        month = list(calendar.month_name).index(match[1].capitalize())
        return int(match[2]), month
    match = re.fullmatch(r'(20\d{2})-(0[1-9]|1[0-2])', str(value).strip())
    return tuple(map(int, match.groups())) if match else None


def reference_quarter(value):
    """Only parse an explicit quarter (never infer it from a release date)."""
    s = str(value or '').strip()
    m = re.search(r'\b(First|Second|Third|Fourth)\s+Quarter\s+(20\d{2})\b', s, re.I)
    if m:
        return int(m[2]), ('first', 'second', 'third', 'fourth').index(m[1].lower()) + 1
    m = re.search(r'\b(20\d{2})[ -]?Q0?([1-4])\b', s, re.I)
    return (int(m[1]), int(m[2])) if m else None


@lru_cache(maxsize=32)
def fetch_series(series, year):
    from official_calendar_collectors import raw_fetch
    url = f'{API}{series}?startyear={year-1}&endyear={year}'
    # Keyless v2 allows 25 requests/day per IP (shared by GitHub runners); a
    # free registration key (secret BLS_API_KEY) raises it to 500. The key is
    # sent in the query only, never stored in the published source_url.
    key = os.environ.get('BLS_API_KEY', '').strip()
    data = json.loads(raw_fetch(url + (f'&registrationkey={key}' if key else '')))
    if data.get('status') != 'REQUEST_SUCCEEDED':
        raise ValueError('BLS_API_REQUEST_FAILED: ' + str(data.get('message')))
    results = data.get('Results', {})
    if isinstance(results, list):
        results = results[0] if results else {}
    rows = next((x['data'] for x in results.get('series', []) if x.get('seriesID') == series), [])
    values = {(int(x['year']), int(x['period'][1:])): Decimal(x['value'])
              for x in rows if re.fullmatch(r'(?:M(?:0[1-9]|1[0-2])|Q0[1-4])', x['period'])
              and re.fullmatch(r'-?\d+(?:\.\d+)?', x['value'])}
    return values, url


def calculate(values, year, month, lag, unit):
    value = values[(year, month)]
    if lag:
        ordinal = year * 12 + month - 1 - lag
        previous = values[(ordinal // 12, ordinal % 12 + 1)]
        value = value - previous if unit == 'K' else (value / previous - 1) * 100
    if unit == 'M':
        value /= 1000
    if unit == 'K':
        return f'{value.normalize():f}K'
    return f'{value.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP):f}{unit}'


def latest_published_period(event, code, now=None):
    """Reference month as published by the BLS API itself, not inferred.

    Right after a monthly release (and before the next one) the newest period
    in the official series IS the released reference month. Guarded so a
    later release can never be attributed to an older event: only events
    released within 25 days qualify, and the period must sit 1-4 months
    before the release (covers shutdown postponements).
    """
    from datetime import datetime
    from zoneinfo import ZoneInfo
    if code not in SERIES:
        return None
    try:
        released = datetime.fromisoformat(str(event.get('datetime_kst')))
    except ValueError:
        return None
    if released.tzinfo is None:
        released = released.replace(tzinfo=ZoneInfo('Asia/Seoul'))
    now = now or datetime.now(ZoneInfo('Asia/Seoul'))
    age_days = (now - released).total_seconds() / 86400
    if not 0 <= age_days <= 25:
        return None
    release_et = released.astimezone(ZoneInfo('America/New_York'))
    series = next(iter(SERIES[code].values()))[0]
    values, _ = fetch_series(series, release_et.year)
    if not values:
        return None
    year, period = max(values)
    # For prod2 the BLS API period is Q01-Q04, where 3*quarter is the
    # reference quarter's final month. The 25-day age gate prevents attaching
    # a later revision to an older release.
    reference_end_month = period * 3 if code == 'prod2' else period
    lag = (release_et.year * 12 + release_et.month) - (year * 12 + reference_end_month)
    return (year, period) if 1 <= lag <= 4 else None


def collect_api(event, code, checks, now=None):
    period = (reference_quarter(event.get('reference_period')) if code == 'prod2'
              else reference_month(event.get('reference_period')))
    if not period and code in SERIES:
        try:
            period = latest_published_period(event, code, now)
        except Exception as exc:
            checks.append({'adapter': 'BLS_API', 'title': event['title'],
                           'result': 'LATEST_PERIOD_LOOKUP_FAILED', 'error': str(exc)[:200]})
            period = None
        if period:
            checks.append({'adapter': 'BLS_API', 'title': event['title'],
                           'result': 'REFERENCE_PERIOD_FROM_API',
                           'reference_period': (f'{period[0]}-Q{period[1]}' if code == 'prod2'
                                                else f'{period[0]}-{period[1]:02d}')})
    if not period or code not in SERIES:
        checks.append({'adapter': 'BLS_API', 'title': event['title'],
                       'result': 'REFERENCE_PERIOD_MISSING' if not period else 'SERIES_NOT_CONFIGURED'})
        return None
    year, month = period
    period_text = f'{year}-Q{month}' if code == 'prod2' else f'{year}-{month:02d}'
    rows = []
    for key, (series, lag, unit) in SERIES[code].items():
        try:
            values, url = fetch_series(series, year)
            actual = calculate(values, year, month, lag, unit)
            rows.append(dict(key=key, label=key, actual=actual, source_url=url,
                             official_url=url, source_tier='OFFICIAL',
                             verification_status='VERIFIED_OFFICIAL_REVISED',
                             value_vintage='LATEST_REVISION',
                             reference_period=period_text, series_id=series))
            checks.append(dict(adapter='BLS_API', title=event.get('title'),
                               event_kst=event.get('datetime_kst'), reference_period=period_text,
                               url=url, result='PARSED_REVISED_SERIES', key=key))
        except Exception as exc:
            checks.append(dict(adapter='BLS_API', series_id=series, key=key,
                               result=type(exc).__name__, error=str(exc)[:200]))
    return (rows, rows[0]['source_url']) if rows else None
