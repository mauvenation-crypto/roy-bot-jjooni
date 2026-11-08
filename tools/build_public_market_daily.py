#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import os
import statistics
import urllib.parse
import urllib.request
from datetime import datetime, date
from pathlib import Path
from zoneinfo import ZoneInfo
from tripod_rules import regime_for, target_for
from yahoo_bar_date import bar_date

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'public-market-daily.json'
KST = ZoneInfo('Asia/Seoul')
ET = ZoneInfo('America/New_York')
UA = 'Mozilla/5.0 JJOONI-Control-Tower-Public-Market/1.0'
YAHOO = 'https://query1.finance.yahoo.com/v8/finance/chart/'
CNN_FG = 'https://production.dataviz.cnn.io/index/fearandgreed/graphdata'

MARKET = (
    ('NASDAQ100', '^NDX', 'NASDAQ 100', 'index'),
    ('SP500', '^GSPC', 'S&P 500', 'index'),
    ('WTI', 'CL=F', 'WTI 유가', 'USD/bbl'),
    ('US10Y', '^TNX', '미국채 10년', '%'),
    ('VIX', '^VIX', 'VIX', 'index'),
    ('DXY', 'DX-Y.NYB', '달러인덱스', 'index'),
    ('DOW30', '^DJI', '다우 30', 'index'),
    ('NASDAQCOMP', '^IXIC', 'NASDAQ 종합', 'index'),
    ('RUSSELL2000', '^RUT', 'Russell 2000', 'index'),
    ('BRENT', 'BZ=F', '브렌트유', 'USD/bbl'),
    ('USDKRW', 'KRW=X', '원/달러', 'KRW/USD'),
)


def get_json(url: str, timeout: int = 15) -> dict:
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'application/json,text/plain,*/*'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def daily_rows(symbol: str, range_: str = '1mo') -> list[tuple[str, float]]:
    qs = urllib.parse.urlencode({'interval': '1d', 'range': range_, 'includePrePost': 'false', 'events': 'div,splits'})
    url = YAHOO + urllib.parse.quote(symbol, safe='') + '?' + qs
    obj = get_json(url)
    result = ((((obj or {}).get('chart') or {}).get('result') or []))
    if not result:
        raise RuntimeError(symbol + '_EMPTY')
    block = result[0]
    ts = block.get('timestamp') or []
    closes = (((block.get('indicators') or {}).get('quote') or [{}])[0].get('close') or [])
    out, seen = [], set()
    for t, c in zip(ts, closes):
        if c is None:
            continue
        try:
            v = float(c)
        except Exception:
            continue
        if not math.isfinite(v) or v <= 0:
            continue
        d = bar_date(t, block, ET)
        if d in seen:
            continue
        seen.add(d)
        out.append((d, v))
    if not out:
        raise RuntimeError(symbol + '_NO_CLOSES')
    return out


def market_item(symbol: str, label: str, unit: str) -> dict:
    rows = daily_rows(symbol, '1mo')
    cur_d, cur = rows[-1]
    prev = rows[-2][1] if len(rows) >= 2 else None
    change = cur - prev if prev else None
    change_pct = (cur / prev - 1) * 100 if prev else None
    return {
        'label': label,
        'value': cur,
        'prev_close': prev,
        'change': change,
        'change_pct': change_pct,
        'unit': unit,
        'source': 'YAHOO_PUBLIC_DAILY',
        'market_state': 'COMPLETED_DAILY_REFERENCE',
        'session_date': cur_d,
        'as_of_date': cur_d,
        'basis': 'LATEST_COMPLETED_DAILY_CLOSE_VS_PREVIOUS_CLOSE',
    }


def fear_greed() -> dict:
    req = urllib.request.Request(CNN_FG, headers={'User-Agent': UA, 'Accept': 'application/json', 'Origin': 'https://www.cnn.com', 'Referer': 'https://www.cnn.com/'})
    with urllib.request.urlopen(req, timeout=15) as r:
        obj = json.load(r)
    b = (obj or {}).get('fear_and_greed') or {}
    score = float(b['score'])
    prev = float(b['previous_close']) if b.get('previous_close') is not None else None
    return {
        'label': '공포탐욕지수',
        'value': score,
        'prev_close': prev,
        'change': score - prev if prev is not None else None,
        'change_pct': None,
        'rating': str(b.get('rating') or '').upper() or None,
        'unit': 'score',
        'source': 'CNN_FEAR_GREED_PUBLIC',
        'market_state': 'REFERENCE',
        'as_of_kst': b.get('timestamp'),
        'basis': 'CNN_COMPOSITE_SENTIMENT_0_100',
    }


def build_tripod(observatory=None) -> dict:
    if observatory is None:
        ndx_all = daily_rows('^NDX', '2y')
        vix_all = daily_rows('^VIX', '6mo')
    else:
        anchor = observatory['us_completed_session_date']
        series = observatory['series']
        ndx_all = [(r['date'], float(r['value'])) for r in series['NASDAQ100'] if r['date'] <= anchor]
        vix_all = [(r['date'], float(r['value'])) for r in series['VIX'] if r['date'] <= anchor]
    common = sorted(set(d for d, _ in ndx_all) & set(d for d, _ in vix_all))
    if not common:
        raise RuntimeError('TRIPOD_NO_COMMON_SESSION')
    session_date = common[-1]
    if observatory is not None and session_date != observatory['us_completed_session_date']:
        raise RuntimeError('TRIPOD_CANONICAL_SESSION_MISMATCH')
    ndx = [(d, v) for d, v in ndx_all if d <= session_date]
    vix = [(d, v) for d, v in vix_all if d <= session_date]
    ndx_c = [v for _, v in ndx]
    if len(ndx_c) < 253 or len(vix) < 11:
        raise RuntimeError('TRIPOD_HISTORY_INCOMPLETE')

    states = []
    state = '상승' if ndx_c[249] >= statistics.fmean(ndx_c[:250]) else '하락'
    for i in range(249, len(ndx_c)):
        ma = statistics.fmean(ndx_c[i-249:i+1])
        px = ndx_c[i]
        state = regime_for(px, ma, state)
        states.append(state)

    regime = states[-1]
    prev_regime = states[-2] if len(states) > 1 else regime
    ndx_px = ndx_c[-1]
    prev_ndx = ndx_c[-2]
    ma250 = statistics.fmean(ndx_c[-250:])
    prev_ma250 = statistics.fmean(ndx_c[-251:-1])
    vix10 = statistics.fmean(v for _, v in vix[-10:])

    prev_date = ndx[-2][0]
    prev_vix = [(d, v) for d, v in vix_all if d <= prev_date]
    if len(prev_vix) < 10:
        raise RuntimeError('TRIPOD_PREVIOUS_VIX_WINDOW_INCOMPLETE')
    prev_vix10 = statistics.fmean(v for _, v in prev_vix[-10:])
    vix_latest = vix[-1][1]

    high52 = max(ndx_c[-252:])
    prev_window = ndx_c[-253:-1]
    prev_high52 = max(prev_window)
    dd = (ndx_px / high52 - 1) * 100
    prev_dd = (prev_ndx / prev_high52 - 1) * 100
    target = target_for(regime, vix10, dd)
    previous_target = target_for(prev_regime, prev_vix10, prev_dd)
    changed = target != previous_target

    age = (datetime.now(KST).date() - date.fromisoformat(session_date)).days
    if age < 0 or age > 4:
        raise RuntimeError('TRIPOD_SESSION_STALE_' + str(age))

    return {
        'ok': True,
        'date': session_date,
        'session_date': session_date,
        'regime': regime,
        'previous_regime': prev_regime,
        'target': target,
        'previous_target': previous_target,
        'action': 'REBALANCE_CHECK' if changed else 'HOLD_NO_TRADE',
        'signal_changed': changed,
        'target_changed': changed,
        'ndx': ndx_px,
        'ma250': ma250,
        'previous_ma250': prev_ma250,
        'vix10': vix10,
        'previous_vix10': prev_vix10,
        'vix_latest_close': vix_latest,
        'vix_window_count': 10,
        'drawdown_52w_pct': dd,
        'previous_drawdown_52w_pct': prev_dd,
        'source': 'PUBLIC_MARKET_DAILY_V1',
        'vix_basis': 'LAST_10_DAILY_CLOSES_ARITHMETIC_MEAN',
        'data_alignment': 'NDX_VIX_SAME_COMPLETED_SESSION',
        'observed_at': datetime.now(KST).isoformat(timespec='seconds'),
    }


def load_previous(path=None) -> dict:
    try:
        return json.loads((OUT if path is None else Path(path)).read_text(encoding='utf-8'))
    except Exception:
        return {}


def main(observatory=None, *, out=None) -> int:
    output_path = OUT if out is None else Path(out)
    previous = load_previous(output_path)
    old_items = ((previous.get('market_context') or {}).get('items') or {})
    items, errors = {}, {}
    for key, symbol, label, unit in MARKET:
        try:
            if observatory is None:
                items[key] = market_item(symbol, label, unit)
            else:
                canonical_key = {'DOW30': 'DOW', 'NASDAQCOMP': 'NASDAQCOMPOSITE', 'US10Y': 'US10Y_OFFICIAL'}.get(key, key)
                rows = observatory['series'].get(canonical_key) or []
                if not rows:
                    raise RuntimeError('CANONICAL_MARKET_MISSING_' + key)
                cur = float(rows[-1]['value'])
                prev = float(rows[-2]['value']) if len(rows) > 1 else None
                items[key] = {'label': label, 'value': cur, 'prev_close': prev,
                    'change': cur - prev if prev is not None else None,
                    'change_pct': (cur / prev - 1) * 100 if prev else None,
                    'unit': unit, 'source': 'OBSERVATORY_CANONICAL',
                    'session_date': rows[-1]['date'], 'as_of_date': rows[-1]['date'],
                    'market_state': 'COMPLETED_DAILY_REFERENCE',
                    'basis': 'LATEST_COMPLETED_DAILY_CLOSE_VS_PREVIOUS_CLOSE'}
        except Exception as exc:
            errors[key] = type(exc).__name__
            old = old_items.get(key)
            if isinstance(old, dict) and isinstance(old.get('value'), (int, float)):
                items[key] = {**old, 'data_state': 'STALE_FALLBACK', 'fallback_reason': type(exc).__name__}
    try:
        if observatory is None:
            items['FEAR_GREED'] = fear_greed()
        else:
            rows = observatory['series'].get('FEAR_GREED') or []
            if not rows:
                raise RuntimeError('CANONICAL_SENTIMENT_MISSING')
            items['FEAR_GREED'] = {'label': '공포탐욕지수', 'value': rows[-1]['value'],
                'unit': 'score', 'source': 'OBSERVATORY_CANONICAL', 'as_of_date': rows[-1]['date']}
    except Exception as exc:
        errors['FEAR_GREED'] = type(exc).__name__
        old = old_items.get('FEAR_GREED')
        if isinstance(old, dict) and isinstance(old.get('value'), (int, float)):
            items['FEAR_GREED'] = {**old, 'data_state': 'STALE_FALLBACK', 'fallback_reason': type(exc).__name__}

    # TRI-POD is the critical contract: never publish a newly generated file if
    # NDX/VIX daily history cannot produce one aligned, fresh, completed-session signal.
    tripod = build_tripod(observatory)
    critical = ('NASDAQ100', 'VIX')
    for key in critical:
        if not isinstance((items.get(key) or {}).get('value'), (int, float)):
            raise RuntimeError('CRITICAL_MARKET_MISSING_' + key)

    expected = [x[0] for x in MARKET] + ['FEAR_GREED']
    available = sum(1 for k in expected if isinstance((items.get(k) or {}).get('value'), (int, float)))
    now = datetime.now(KST).isoformat(timespec='seconds')
    out = {
        'schema': 'JJOONI_PUBLIC_MARKET_DAILY_V1',
        'generated_kst': now,
        'read_only': True,
        'contains_account_data': False,
        'market_context': {
            'state': 'FULL' if available == len(expected) else 'PARTIAL',
            'expected_count': len(expected),
            'available_count': available,
            'items': items,
            'errors': errors,
            'basis': 'PUBLIC_MARKET_COMPLETED_DAILY_SIDECAR',
        },
        'tripod_signal': tripod,
    }
    tmp = output_path.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    tmp.replace(output_path)
    print('PUBLIC_MARKET_DAILY=PASS')
    print('generated_kst=' + now)
    print('market=%s/%s' % (available, len(expected)))
    print('tripod_date=' + str(tripod.get('date')))
    print('vix_close=%.4f' % float(tripod['vix_latest_close']))
    print('vix10=%.4f' % float(tripod['vix10']))
    print('ndx=%.4f ma250=%.4f dd=%.4f' % (tripod['ndx'], tripod['ma250'], tripod['drawdown_52w_pct']))
    print('regime=%s target=%s action=%s' % (tripod['regime'], tripod['target'], tripod['action']))
    if errors:
        print('noncritical_errors=' + json.dumps(errors, sort_keys=True))
    return 0


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Build public market facts and TRI-POD from one source.')
    parser.add_argument('--canonical', type=Path, help='Use this Observatory snapshot without another network read.')
    args = parser.parse_args()
    raise SystemExit(main(json.loads(args.canonical.read_text()) if args.canonical else None))

