#!/usr/bin/env python3
"""Reassert event-level value semantics after retention/history merges.

For multi-metric releases, the compact event-level Previous/Consensus/Actual
must mirror the first populated non-probability market metric. Market-probability
snapshots such as CME FedWatch are auxiliary overlays and can never become the
representative value of a policy-decision card.
"""
from __future__ import annotations

import json
from pathlib import Path

from calendar_market_events import representative_metric, sync_representative_values

ROOT = Path(__file__).resolve().parents[1]
CAL = ROOT / 'market-observatory' / 'data' / 'economic-calendar.json'


def clean(v):
    if v is None:
        return None
    s = str(v).strip()
    return None if s in ('', '-', '—', 'None', 'null', 'N/A') else s


def primary_metric(event):
    return representative_metric(event)


def main():
    data = json.loads(CAL.read_text(encoding='utf-8'))
    synced = 0
    policy_guarded = 0
    for event in data.get('events') or []:
        before = tuple(clean(event.get(k)) for k in ('previous', 'consensus', 'actual'))
        primary = primary_metric(event)
        if primary:
            sync_representative_values(event)
            after = tuple(clean(event.get(k)) for k in ('previous', 'consensus', 'actual'))
            synced += int(before != after)
            # Explicitly document the semantic split for policy cards: FedWatch
            # probability remains an auxiliary metric and the policy-rate metric
            # is the compact representative value.
            if any((m or {}).get('metric_type') == 'market_probability_snapshot'
                   for m in (event.get('market_metrics') or []) if isinstance(m, dict)):
                event['representative_value_contract'] = 'PRIMARY_NON_PROBABILITY_METRIC_V1'
                event['representative_metric_key'] = primary.get('key') or primary.get('label')
                policy_guarded += 1
        else:
            event.setdefault('representative_value_contract', 'EVENT_LEVEL_VALUE_V1')

    data['representative_value_contract'] = 'PRIMARY_NON_PROBABILITY_METRIC_AFTER_MERGE_V1'
    data['representative_value_sync'] = {
        'events_changed': synced,
        'probability_overlay_events_guarded': policy_guarded,
    }
    CAL.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('CALENDAR_REPRESENTATIVE_SYNC=PASS changed=', synced, 'probability_guarded=', policy_guarded)


if __name__ == '__main__':
    main()
