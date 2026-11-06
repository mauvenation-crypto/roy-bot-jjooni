"""Publish market-only TRI-POD comparison inputs from completed US sessions."""
import json
import math
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, time, timedelta
from functools import lru_cache
from pathlib import Path

from build_market_observatory import ET, get_json, tripod_history
from observatory_session import holidays

DATA = Path(__file__).resolve().parents[1] / 'market-observatory/data'
OUT = DATA / 'tripod-comparison.json'
ETFS = ('QQQ', 'QLD', 'TQQQ')
SIGNAL_SYMBOLS = {'NASDAQ100': '^NDX', 'VIX': '^VIX'}
MARKET_HOLIDAYS = lru_cache(None)(holidays)


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def yahoo_daily(symbol, *, adjusted, **window):
    query = urllib.parse.urlencode({'interval': '1d', 'includePrePost': 'false', **window})
    for host in ('query1.finance.yahoo.com', 'query2.finance.yahoo.com'):
        try:
            ticker = urllib.parse.quote(symbol, safe='')
            chart = get_json(f'https://{host}/v8/finance/chart/{ticker}?{query}')['chart']['result'][0]
            granularity = chart.get('meta', {}).get('dataGranularity')
            if granularity and granularity != '1d':
                raise ValueError(f'Expected 1d, received {granularity}')
            indicators = chart['indicators']
            closes = indicators['quote'][0]['close']
            adjusted_closes = indicators['adjclose'][0]['adjclose'] if adjusted else closes
            rows = {}
            for stamp, close, adj in zip(chart['timestamp'], closes, adjusted_closes, strict=True):
                if all(isinstance(value, (int, float)) and math.isfinite(value) and value > 0
                       for value in (close, adj)):
                    day = datetime.fromtimestamp(stamp, ET).date().isoformat()
                    rows[day] = [round(close, 8), round(adj, 8)]
            if rows:
                return rows
        except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
            print(f'TRI-POD comparison {symbol} {host}: {exc}')
    raise RuntimeError(f'Completed close/adjusted-close history unavailable for {symbol}')


def daily_bars(symbol, end, *, start, adjusted=True):
    # Yahoo may coarsen a max-range request to monthly observations even when
    # interval=1d is requested. Collect bounded, overlapping daily windows.
    bars = {}
    right = end + timedelta(days=1)
    while right > start:
        left = max(start, right - timedelta(days=3 * 365))
        try:
            segment = yahoo_daily(
                symbol, adjusted=adjusted, period1=int(datetime.combine(left, time.min, ET).timestamp()),
                period2=int(datetime.combine(right, time.min, ET).timestamp()))
            segment = {d: value for d, value in segment.items()
                       if left.isoformat() <= d < right.isoformat()}
            if len(segment) < (right - left).days * 0.50:
                raise ValueError(f'Sparse daily window {left} to {right}: {len(segment)} rows')
        except (RuntimeError, ValueError) as exc:
            if not bars:
                bars = yahoo_daily(symbol, adjusted=adjusted, range='3y')
                print(f'TRI-POD comparison {symbol} used recent daily window: {exc}')
            else:
                print(f'TRI-POD comparison {symbol} ended older backfill: {exc}')
            break
        if not bars:
            bars = segment
        else:
            overlap = set(bars).intersection(segment)
            if not overlap:
                break
            anchor = max(overlap)
            ratio = bars[anchor][1] / segment[anchor][1]
            for d, (close, adjusted) in segment.items():
                bars.setdefault(d, [close, adjusted * ratio])
        if left == start:
            break
        right = left + timedelta(days=10)
    if end.isoformat() not in bars:
        try:
            recent = yahoo_daily(symbol, adjusted=adjusted, range='1mo')
            overlap = set(bars).intersection(recent)
            if overlap:
                anchor = max(overlap)
                ratio = bars[anchor][1] / recent[anchor][1]
                for d, (close, adjusted) in recent.items():
                    bars.setdefault(d, [close, adjusted * ratio])
        except RuntimeError as exc:
            print(f'TRI-POD comparison recent check {symbol}: {exc}')
    return bars


def is_trading_date(day):
    stamp = date.fromisoformat(day)
    return stamp.weekday() < 5 and stamp not in MARKET_HOLIDAYS(stamp.year)


def build(obs, archive, etfs, supplement=None):
    latest = obs['tripod_latest']
    session = obs['us_completed_session_date']
    if latest.get('ok') is not True or (latest.get('session_date') or latest.get('date')) != session:
        raise ValueError('Canonical completed TRI-POD signal unavailable')
    series = {}
    etf_calendar = set.union(*(set(etfs[key]) for key in ETFS))
    for key in SIGNAL_SYMBOLS:
        merged = {d: {'date': d, 'value': quote[0]} for d, quote in (supplement or {}).get(key, {}).items()}
        merged.update((r['date'], r) for source in (archive, obs) for r in source['series'].get(key, []))
        merged = {d: r for d, r in merged.items() if d <= session and (d in etf_calendar or is_trading_date(d))}
        series[key] = [merged[d] for d in sorted(merged)]
    replay, _ = tripod_history(series)
    signals = {r['date']: r for r in replay}
    signals.update((r['date'], r) for r in obs['tripod_history'] if r['date'] <= session)
    signals[session] = latest
    # Use the continuous common-date suffix. An interior data gap cannot be
    # treated as one trading session or silently filled with a proxy.
    ndx_dates = {item['date'] for item in series['NASDAQ100']}
    first_possible = max(min(etfs[key]) for key in ETFS)
    completed = sorted(day for day in ndx_dates | etf_calendar if first_possible <= day <= session)
    last_common = next((d for d in reversed(completed)
                        if d in signals and all(d in etfs[key] for key in ETFS)), None)
    coverage = {key: [min(etfs[key]), max(etfs[key]), len(etfs[key])] for key in ETFS}
    print(f'TRI-POD comparison source coverage: canonical={session} '
          f'last_common={last_common} ETF={coverage}')
    if last_common is None:
        raise ValueError('ETF and canonical signals share no completed sessions')
    rows = []
    for day in reversed(completed):
        if day > last_common:
            continue
        signal = signals.get(day)
        quotes = [etfs[key].get(day) for key in ETFS]
        if not signal or any(q is None for q in quotes):
            print(f'TRI-POD comparison continuity boundary {day}: '
                  f'NDX={day in ndx_dates}, signal={bool(signal)}, '
                  f'missing ETFs={[key for key, quote in zip(ETFS, quotes) if quote is None]}')
            break
        rows.append([day, signal['ndx'], signal['ma250'], signal['target'], *quotes])
    rows.reverse()
    if len(rows) < 2:
        raise ValueError(f'ETF and canonical signals lack a continuous window through {last_common}')
    return {'schema': 'JJOONI_TRIPOD_COMPARISON_V1', 'session': last_common,
            'canonical_session': session, 'rows': rows}


def main():
    obs = read(DATA / 'observatory.json')
    if OUT.exists():
        previous = read(OUT)
        if (previous.get('schema') == 'JJOONI_TRIPOD_COMPARISON_V1' and
                previous.get('session', '') >= obs['us_completed_session_date']):
            print('TRI-POD comparison already has the latest completed US session')
            return
    archive = read(DATA / 'history-30y.json')
    end = date.fromisoformat(obs['us_completed_session_date'])
    with ThreadPoolExecutor(max_workers=len(ETFS)) as pool:
        etfs = dict(zip(ETFS, pool.map(
            lambda key: daily_bars(key, end, start=date(2010, 1, 1)), ETFS), strict=True))
        try:
            payload = build(obs, archive, etfs)
        except ValueError as exc:
            print(f'TRI-POD comparison canonical archive: {exc}')
            payload = None
        earliest = date.fromisoformat(max(min(etfs[key]) for key in ETFS))
        if not payload or (date.fromisoformat(payload['rows'][0][0]) - earliest).days > 30:
            # Only supply missing observations. Published same-date index/VIX
            # bars and all published official targets keep precedence.
            def backfill(key):
                return daily_bars(SIGNAL_SYMBOLS[key], end, start=earliest - timedelta(days=550), adjusted=False)

            try:
                supplement = dict(zip(SIGNAL_SYMBOLS, pool.map(backfill, SIGNAL_SYMBOLS), strict=True))
                extended = build(obs, archive, etfs, supplement)
                if not payload or len(extended['rows']) > len(payload['rows']):
                    payload = extended
            except (RuntimeError, ValueError) as exc:
                if not payload:
                    raise
                print(f'TRI-POD comparison retained verified coverage after backfill error: {exc}')
    OUT.write_text(json.dumps(payload, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
    print(f'TRI-POD comparison {payload["rows"][0][0]} through {payload["session"]}: {len(payload["rows"])} sessions')


if __name__ == '__main__':
    main()
