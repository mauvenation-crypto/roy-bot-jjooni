#!/usr/bin/env python3
"""One-line decision for the heartbeat relay, from the writers' own gates.

Read-only. Uses exactly the gates the Daily hourly watchdog uses, so the relay
never refreshes anything the existing schedule would not have refreshed:
  crypto=refresh  BTC/ETH quote older than the crypto gate threshold (45 min)
  market=refresh  market snapshot or sector board stale (Daily hourly path)
  alert=...       data is actually stale for users, not just due a refresh:
                  crypto  BTC/ETH quote >= 60 min old (or unreadable)
                  market  market snapshot behind the expected session for
                          >= 90 min after collection
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from crypto_heartbeat_gate import crypto_refresh_decision  # noqa: E402
from observatory_session import refresh_decision  # noqa: E402
import sector_heartbeat_gate  # noqa: E402

DATA = ROOT / 'market-observatory' / 'data'
CRYPTO_ALERT_MIN = 60
MARKET_ALERT_MIN = 90


def load(path):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def decide(now=None):
    now = now or datetime.now(timezone.utc)
    obs = load(DATA / 'observatory.json')
    crypto = crypto_refresh_decision(obs, now)
    market = refresh_decision(obs, load(DATA / 'daily-market-pulse.json'), load(ROOT / 'public-market-daily.json'))
    try:
        sector = bool(sector_heartbeat_gate.should_refresh(load(DATA / 'sector-etf.json'), now, obs))
    except Exception:
        sector = False
    ages = [v['age_seconds'] for v in crypto['details'].values() if v['age_seconds'] is not None]
    crypto_age = max(ages) / 60 if len(ages) == len(crypto['details']) else None
    alerts = []
    if crypto_age is None or crypto_age >= CRYPTO_ALERT_MIN:
        alerts.append('crypto')
    market_age = market.get('age_min')
    if not market.get('healthy', True) and (market_age is None or market_age >= MARKET_ALERT_MIN):
        alerts.append('market')
    return {
        'crypto': 'refresh' if crypto['should_refresh'] else 'ok',
        'market': 'refresh' if (market['should_refresh'] or sector) else 'ok',
        'crypto_max_age_min': round(max(ages) / 60, 1) if ages else None,
        'market_age_min': None if market_age is None else round(market_age, 1),
        'alert': ','.join(alerts) or 'none',
    }


def main():
    d = decide()
    print(' '.join(f'{k}={v}' for k, v in d.items()))


if __name__ == '__main__':
    main()
