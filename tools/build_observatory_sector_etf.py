#!/usr/bin/env python3
from __future__ import annotations

import json
import calendar
import math
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'market-observatory' / 'data' / 'sector-etf.json'
KST = ZoneInfo('Asia/Seoul')
ET = ZoneInfo('America/New_York')
UA = 'Mozilla/5.0 JJOONI-Market-Observatory-Sector/1.1'
YAHOO = 'https://query1.finance.yahoo.com/v8/finance/chart/'

BENCHMARKS = {
    'SPY': 'SPDR S&P 500 ETF Trust',
    'QQQ': 'Invesco QQQ Trust',
}

GROUPS = [
    # Account-independent registry: broad KR indices and KRX sector-index ETF
    # families. Fixed membership is versioned, never derived from account holdings
    # or today's turnover. Names below describe exposure, not a buy ranking.
    ('kr_index', '한국 대표 지수', [
        ('069500', 'KOSPI 200'), ('229200', 'KOSDAQ 150'),
        ('133690', 'TIGER 미국나스닥100'),
    ]),
    ('kr_sector', '한국 KRX 섹터 지수', [
        ('091160', '반도체'), ('091170', '은행'), ('091180', '자동차'),
        ('102960', 'KODEX 기계장비'),
        ('117460', '에너지·화학'), ('117680', '철강'), ('117700', '건설'),
        ('140700', '보험'), ('266360', '미디어·엔터테인먼트'),
        ('266410', '필수소비재'),
    ]),
    # Benchmark exposure must be investable in the default catalog.
    ('benchmark', '미국 벤치마크 노출', [('QQQ', BENCHMARKS['QQQ'])]),
    ('classic', 'S&P 500 섹터', [
        ('XLK', 'Technology'),
        ('XLC', 'Communication Services'),
        ('XLY', 'Consumer Discretionary'),
        ('XLF', 'Financials'),
        ('XLI', 'Industrials'),
        ('XLE', 'Energy'),
        ('XLB', 'Materials'),
        ('XLV', 'Health Care'),
        ('XLP', 'Consumer Staples'),
        ('XLU', 'Utilities'),
        ('XLRE', 'Real Estate'),
    ]),
    ('semiconductor', '반도체·메모리', [
        ('SMH', 'VanEck Semiconductor ETF'),
        ('SOXX', 'iShares Semiconductor ETF'),
    ]),
    ('software', '소프트웨어·클라우드·사이버', [
        ('IGV', 'iShares Expanded Tech-Software Sector ETF'),
        ('SKYY', 'First Trust Cloud Computing ETF'),
        ('HACK', 'ETFMG Prime Cyber Security ETF'),
    ]),
    ('biotech', '바이오', [
        ('XBI', 'SPDR S&P Biotech ETF'),
    ]),
    ('financial', '지역은행', [
        ('KRE', 'SPDR S&P Regional Banking ETF'),
    ]),
    ('defense_infra', '방산·인프라·에너지', [
        ('ITA', 'iShares U.S. Aerospace & Defense ETF'),
        ('XAR', 'SPDR S&P Aerospace & Defense ETF'),
        ('PAVE', 'Global X U.S. Infrastructure Development ETF'),
        ('XOP', 'SPDR S&P Oil & Gas Exploration & Production ETF'),
    ]),
    ('robotics', '로봇·자동화', [
        ('BOTZ', 'Global X Robotics & Artificial Intelligence ETF'),
        ('ROBO', 'ROBO Global Robotics and Automation Index ETF'),
    ]),
    ('country', '국가별 대표 ETF', [
        ('SPY', '미국 · SPDR S&P 500 ETF Trust'),
        ('EWY', '한국 · iShares MSCI South Korea ETF'),
        ('EWJ', '일본 · iShares MSCI Japan ETF'),
        ('MCHI', '중국 · iShares MSCI China ETF'),
        ('EWT', '대만 · iShares MSCI Taiwan ETF'),
        ('INDA', '인도 · iShares MSCI India ETF'),
        ('EWZ', '브라질 · iShares MSCI Brazil ETF'),
        ('VGK', '유럽 · Vanguard FTSE Europe ETF'),
    ]),
]

HORIZONS = (1, 5, 10, 20, 50, 100)


def market_of(ticker):
    return 'KR' if str(ticker).isdigit() and len(str(ticker)) == 6 else 'US'


def completed_cutoff(market, now=None):
    zone = KST if market == 'KR' else ET
    local = (now or datetime.now(KST)).astimezone(zone)
    # Conservative normal close +10m. Early US closes are delayed, never
    # promoted before completion. Nontrading dates have no Yahoo daily bar.
    close = (15, 40) if market == 'KR' else (16, 10)
    day = local.date()
    if (local.hour, local.minute) < close:
        day -= timedelta(days=1)
    while day.weekday() > 4:
        day -= timedelta(days=1)
    return day.isoformat()


def completed_points(points, market, now=None):
    cutoff = completed_cutoff(market, now)
    return [p for p in points if str(p.get('date') or '')[:10] <= cutoff]


def request_json(url: str, timeout: int = 20):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode('utf-8'))


def yahoo_series(symbol: str, range_: str = '1y', now=None):
    qs = urllib.parse.urlencode({
        'interval': '1d',
        'range': range_,
        'includePrePost': 'false',
        'events': 'div,splits',
    })
    url = YAHOO + urllib.parse.quote(symbol, safe='') + '?' + qs
    last_error = None
    for attempt in range(3):
        try:
            obj = request_json(url)
            rs = ((obj.get('chart') or {}).get('result') or [])
            if not rs:
                raise RuntimeError('empty Yahoo result')
            block = rs[0]
            ts = block.get('timestamp') or []
            closes = ((((block.get('indicators') or {}).get('quote') or [{}])[0]).get('close') or [])
            out = []
            for t, v in zip(ts, closes):
                if v is None:
                    continue
                try:
                    v = float(v)
                except Exception:
                    continue
                if not math.isfinite(v):
                    continue
                zone = KST if symbol.endswith(('.KS', '.KQ')) else ET
                d = datetime.fromtimestamp(int(t), zone).date().isoformat()
                out.append({'date': d, 'value': round(v, 8)})
            dedup = {x['date']: x for x in out}
            rows = completed_points([dedup[k] for k in sorted(dedup)],
                                    'KR' if symbol.endswith(('.KS', '.KQ')) else 'US', now)
            if len(rows) < 101:
                raise RuntimeError(f'insufficient points for 100d horizon: {len(rows)}')
            return rows
        except Exception as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(0.7 * (attempt + 1))
    raise RuntimeError(f'Yahoo fetch failed for {symbol}: {last_error}')


def load_previous():
    try:
        return json.loads(OUT.read_text(encoding='utf-8'))
    except Exception:
        return {}


def pct_from_points(points, sessions):
    if not points or len(points) <= sessions:
        return None
    a = points[-1]['value']
    b = points[-1 - sessions]['value']
    if not b:
        return None
    return (a / b - 1.0) * 100.0


def calendar_return(points, months):
    """Last completed close compared with last close on/before calendar date."""
    if not points:
        return None
    end = date.fromisoformat(points[-1]['date'])
    month_index = end.year * 12 + end.month - 1 - months
    year, month = divmod(month_index, 12)
    month += 1
    target = date(year, month, min(end.day, calendar.monthrange(year, month)[1]))
    candidates = [p for p in points if date.fromisoformat(p['date']) <= target]
    if not candidates:
        return None
    base = candidates[-1]
    base_date = date.fromisoformat(base['date'])
    if (target - base_date).days > 7 or not base.get('value'):
        return None
    return {'pct': rounded((points[-1]['value'] / base['value'] - 1) * 100),
            'base_date': base['date'], 'end_date': points[-1]['date']}


def ytd_return(points):
    if not points:
        return None
    current_date = points[-1]['date']
    year = current_date[:4]
    base = next((x['value'] for x in points if x['date'].startswith(year)), None)
    if base in (None, 0):
        return None
    return (points[-1]['value'] / base - 1.0) * 100.0


def avg(values):
    xs = [x for x in values if x is not None]
    return sum(xs) / len(xs) if xs else None


def rounded(v, digits=4):
    return None if v is None or not math.isfinite(v) else round(v, digits)


def metrics(points):
    if not points:
        return {}
    values = [x['value'] for x in points]
    price = values[-1]
    ma20 = avg(values[-20:]) if len(values) >= 20 else None
    ma60 = avg(values[-60:]) if len(values) >= 60 else None
    high20 = max(values[-20:]) if len(values) >= 20 else None
    out = {
        'price': rounded(price, 4),
        'ytd_pct': rounded(ytd_return(points)),
        'ma20': rounded(ma20, 4),
        'ma60': rounded(ma60, 4),
        'vs_ma20_pct': rounded((price / ma20 - 1.0) * 100.0) if ma20 else None,
        'vs_ma60_pct': rounded((price / ma60 - 1.0) * 100.0) if ma60 else None,
        'high20_gap_pct': rounded((price / high20 - 1.0) * 100.0) if high20 else None,
        'above_ma20': bool(ma20 is not None and price >= ma20),
        'above_ma60': bool(ma60 is not None and price >= ma60),
        'observed_date': points[-1]['date'],
    }
    for d in HORIZONS:
        out[f'ret_{d}d_pct'] = rounded(pct_from_points(points, d))
    out['calendar_returns'] = {str(m): calendar_return(points, m) for m in (1, 3, 12)}
    # Legacy fields retained for existing consumers/QA.
    out['ret_1m_pct'] = rounded(pct_from_points(points, 21))
    out['ret_3m_pct'] = rounded(pct_from_points(points, 63))
    return out


def relative(row, bench, key):
    a = row.get(key)
    b = bench.get(key)
    return rounded(a - b) if a is not None and b is not None else None


def build(now=None):
    now = now or datetime.now(KST)
    previous = load_previous()
    prev_series = previous.get('series') or {}
    series = {}
    fetch_errors = {}

    tickers = list(BENCHMARKS.keys())
    for _, _, rows in GROUPS:
        tickers.extend(t for t, _ in rows)

    for ticker in dict.fromkeys(tickers):
        try:
            symbol = ticker + '.KS' if market_of(ticker) == 'KR' else ticker
            series[ticker] = yahoo_series(symbol, '2y', now)
            time.sleep(0.12)
        except Exception as exc:
            # Legacy fallback may itself contain a provisional bar. Filter by
            # its generation time as well as today's cutoff; do not turn an
            # old provisional bar into a completed close merely by waiting.
            try:
                prior_at = datetime.fromisoformat(previous['generated_kst'])
                if prior_at.tzinfo is None or prior_at > now:
                    raise ValueError('PRIOR_TIMESTAMP_INVALID')
                fallback = completed_points(prev_series.get(ticker) or [], market_of(ticker), prior_at)
                fallback = completed_points(fallback, market_of(ticker), now)
            except (KeyError, TypeError, ValueError):
                fallback = []
            if fallback:
                series[ticker] = fallback
            else:
                series[ticker] = []
            fetch_errors[ticker] = str(exc)

    bm_metrics = {ticker: metrics(series.get(ticker) or []) for ticker in BENCHMARKS}
    spy = bm_metrics.get('SPY') or {}
    qqq = bm_metrics.get('QQQ') or {}

    group_payload = []
    all_rows = []
    for key, label, members in GROUPS:
        rows = []
        for ticker, name in members:
            m = metrics(series.get(ticker) or [])
            if m:
                m.update({
                    'ticker': ticker,
                    'name': name,
                    'group': label,
                    'group_key': key,
                    'source': 'Yahoo public daily',
                    'market': market_of(ticker), 'asset_class': 'ETF',
                    'bar_status': 'COMPLETED_DAILY',
                    'completed_cutoff': completed_cutoff(market_of(ticker), now),
                })
                for d in HORIZONS:
                    key_name = f'ret_{d}d_pct'
                    m[f'rs_spy_{d}d_pct'] = relative(m, spy, key_name) if market_of(ticker) == 'US' else None
                    m[f'rs_qqq_{d}d_pct'] = relative(m, qqq, key_name) if market_of(ticker) == 'US' else None
                # Legacy fields retained for existing consumers/QA.
                m['rs_spy_1m_pct'] = relative(m, spy, 'ret_1m_pct') if market_of(ticker) == 'US' else None
                m['rs_qqq_1m_pct'] = relative(m, qqq, 'ret_1m_pct') if market_of(ticker) == 'US' else None
            else:
                m = {'ticker': ticker, 'name': name, 'group': label, 'group_key': key,
                     'market': market_of(ticker), 'asset_class': 'ETF', 'source': 'UNAVAILABLE'}
            rows.append(m)
            all_rows.append(m)
        group_payload.append({'key': key, 'label': label, 'rows': rows})

    classic = next((g['rows'] for g in group_payload if g['key'] == 'classic'), [])
    ranked_20d = sorted([r for r in classic if r.get('rs_spy_20d_pct') is not None], key=lambda r: r['rs_spy_20d_pct'], reverse=True)
    ranked_1m = sorted([r for r in classic if r.get('rs_spy_1m_pct') is not None], key=lambda r: r['rs_spy_1m_pct'], reverse=True)
    priced = [r for r in all_rows if r.get('price') is not None]
    above_ma20 = [r for r in classic if r.get('above_ma20') is True]

    growth_20d = [r.get('ret_20d_pct') for r in classic if r.get('ticker') in {'XLK', 'XLC', 'XLY'}]
    defensive_20d = [r.get('ret_20d_pct') for r in classic if r.get('ticker') in {'XLV', 'XLP', 'XLU'}]
    growth_defense_spread_20d = None
    if avg(growth_20d) is not None and avg(defensive_20d) is not None:
        growth_defense_spread_20d = avg(growth_20d) - avg(defensive_20d)

    growth_1m = [r.get('ret_1m_pct') for r in classic if r.get('ticker') in {'XLK', 'XLC', 'XLY'}]
    defensive_1m = [r.get('ret_1m_pct') for r in classic if r.get('ticker') in {'XLV', 'XLP', 'XLU'}]
    growth_defense_spread_1m = None
    if avg(growth_1m) is not None and avg(defensive_1m) is not None:
        growth_defense_spread_1m = avg(growth_1m) - avg(defensive_1m)

    latest_dates = [r.get('observed_date') for r in priced if r.get('observed_date')]
    as_of_date = max(latest_dates) if latest_dates else None

    out = {
        'schema': 'JJOONI_OBSERVATORY_SECTOR_ETF_V1',
        'generated_kst': now.isoformat(timespec='seconds'),
        'as_of_date': as_of_date,
        'read_only': True,
        'contains_account_data': False,
        'universe_version': 'SONG_SECTOR_UNIVERSE_V2_COUNTRY',
        'catalog_revision': 'KR_INDEX_SECTOR_BENCHMARK_V2_US_V3',
        'membership_policy': 'VERSIONED_INDEX_SECTOR_REGISTRY_NO_RANKING_NO_ACCOUNT_INPUT',
        'daily_bar_contract': 'PER_MARKET_COMPLETED_CUTOFF_V1',
        'completed_cutoffs': {m: completed_cutoff(m, now) for m in ('KR', 'US')},
        'source_contract': 'YAHOO_PUBLIC_COMPLETED_DAILY_REFERENCE',
        'horizons_sessions': list(HORIZONS),
        'benchmarks': {
            ticker: {'ticker': ticker, 'name': name, **(bm_metrics.get(ticker) or {}), 'source': 'Yahoo public daily'}
            for ticker, name in BENCHMARKS.items()
        },
        'summary': {
            'classic_count': len(classic),
            'priced_count': len(priced),
            'total_count': len(all_rows),
            'classic_above_ma20': len(above_ma20),
            'leaders_20d_rs_spy': [{'ticker': r['ticker'], 'value': r['rs_spy_20d_pct']} for r in ranked_20d[:3]],
            'laggards_20d_rs_spy': [{'ticker': r['ticker'], 'value': r['rs_spy_20d_pct']} for r in ranked_20d[-3:][::-1]],
            'growth_defense_spread_20d_pct': rounded(growth_defense_spread_20d),
            'leaders_1m_rs_spy': [{'ticker': r['ticker'], 'value': r['rs_spy_1m_pct']} for r in ranked_1m[:3]],
            'laggards_1m_rs_spy': [{'ticker': r['ticker'], 'value': r['rs_spy_1m_pct']} for r in ranked_1m[-3:][::-1]],
            'growth_defense_spread_1m_pct': rounded(growth_defense_spread_1m),
        },
        'groups': group_payload,
        'series': {ticker: (points[-400:] if points else []) for ticker, points in series.items()},
        'quality': {
            'fetch_error_count': len(fetch_errors),
            'fetch_errors': fetch_errors,
            'expected_classic_count': 11,
            'classic_priced_count': len([r for r in classic if r.get('price') is not None]),
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return out


def main():
    out = build()
    print('OBSERVATORY_SECTOR_ETF_BUILD=PASS')
    print('generated_kst=' + out['generated_kst'])
    print('as_of_date=' + str(out.get('as_of_date')))
    print('horizons=' + ','.join(str(x) for x in out.get('horizons_sessions', [])))
    print('classic=' + str(out['quality']['classic_priced_count']) + '/11')
    print('priced=' + str(out['summary']['priced_count']) + '/' + str(out['summary']['total_count']))
    print('fetch_errors=' + str(out['quality']['fetch_error_count']))


if __name__ == '__main__':
    main()
