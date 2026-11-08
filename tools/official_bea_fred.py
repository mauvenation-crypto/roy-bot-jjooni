"""BEA Personal Income and Outlays actuals from BEA series published on FRED.

The release title states its reference month ("Personal Income and Outlays,
August 2026"), so nothing is inferred from the announcement date. FRED carries
BEA's current vintage; values are therefore LATEST_REVISION and never displace
an AS_RELEASED official observation of the same tier.
"""
import calendar as months
import csv
import io
import re
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

FRED_CSV = 'https://fred.stlouisfed.org/graph/fredgraph.csv?id='
TITLE = re.compile(r'^Personal Income and Outlays,\s+([A-Za-z]+)\s+(\d{4})$')
MONTHS = {name.lower(): i for i, name in enumerate(months.month_name) if name}

# key -> (FRED series, lag in months for percent change)
SERIES = {
    'core_pce_mom': ('PCEPILFE', 1),
    'pce_yoy': ('PCEPI', 12),
    'personal_income': ('PI', 1),
    'personal_spending': ('PCE', 1),
}
KEYS = tuple(SERIES)


def reference_month(title):
    match = TITLE.match(str(title or '').strip())
    if not match or match.group(1).lower() not in MONTHS:
        return None
    return int(match.group(2)), MONTHS[match.group(1).lower()]


# One attempt per series per run, failures included: a slow FRED must not
# drain the shared official-collection time budget event after event.
_CACHE = {}


def fetch(series):
    if series not in _CACHE:
        try:
            _CACHE[series] = ('ok', _fetch(series))
        except Exception as exc:
            _CACHE[series] = ('error', exc)
    status, payload = _CACHE[series]
    if status == 'error':
        raise payload
    return payload


def _fetch(series):
    from official_calendar_collectors import raw_fetch
    # A bounded window keeps the CSV small; 3 years covers every YoY base.
    url = f'{FRED_CSV}{series}&cosd={datetime.now().year - 3}-01-01'
    text = raw_fetch(url).decode('utf-8', errors='replace')
    values = {}
    for row in csv.DictReader(io.StringIO(text)):
        day = row.get('observation_date') or row.get('DATE') or ''
        raw = row.get(series)
        if re.fullmatch(r'\d{4}-\d{2}-01', day) and raw and re.fullmatch(r'-?\d+(?:\.\d+)?', raw):
            values[(int(day[:4]), int(day[5:7]))] = Decimal(raw)
    if not values:
        raise ValueError('FRED_SERIES_EMPTY')
    return values, url


def pct_change(values, year, month, lag):
    if (year, month) not in values:
        raise ValueError('FRED_PERIOD_NOT_PUBLISHED')
    ordinal = year * 12 + month - 1 - lag
    base = values[(ordinal // 12, ordinal % 12 + 1)]
    value = (values[(year, month)] / base - 1) * 100
    return f'{value.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP):f}%'


def collect_pio(event, checks, fetcher=fetch):
    period = reference_month(event.get('title'))
    if not period:
        checks.append({'adapter': 'BEA_FRED', 'title': event.get('title'), 'result': 'REFERENCE_PERIOD_MISSING'})
        return None
    year, month = period
    rows = []
    for key, (series, lag) in SERIES.items():
        try:
            values, url = fetcher(series)
            rows.append(dict(key=key, label=key, actual=pct_change(values, year, month, lag),
                             source_url=url, official_url=url, source_tier='OFFICIAL',
                             source='BEA via FRED', verification_status='VERIFIED_OFFICIAL_REVISED',
                             value_vintage='LATEST_REVISION', reference_period=f'{year}-{month:02d}',
                             series_id=series))
            checks.append({'adapter': 'BEA_FRED', 'key': key, 'url': url, 'result': 'PARSED_REVISED_SERIES'})
        except Exception as exc:
            checks.append({'adapter': 'BEA_FRED', 'key': key, 'series_id': series,
                           'result': type(exc).__name__, 'error': str(exc)[:200]})
    return (rows, rows[0]['source_url']) if rows else None
