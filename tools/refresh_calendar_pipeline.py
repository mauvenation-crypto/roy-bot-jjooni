#!/usr/bin/env python3
"""One ordered calendar pipeline shared by routine publishing workflows.

Schedule seed -> restore observations -> collect official/secondary/feed once ->
merge curated forecasts + generic all-event fallback -> retain -> recent historical
recovery -> verified official-macro bridge -> representative sync -> compute health
-> archive -> rolling 10Y history -> previous-value fallback -> representative sync
-> validate.

The expensive 10-year source crawl is intentionally decoupled into its own
resumable workflow. Routine calendar refreshes preserve and extend the 10-year
SSOT without re-downloading hundreds of historical weekly pages.  A lightweight
recent-overdue bridge may fetch only weeks containing currently unresolved
releases so weekly-feed rollover cannot leave market actuals permanently blank.
The official-macro bridge fills only exact-reference-period KOSTAT events from
identity-verified official series already present in the Observatory SSOT.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
CAL = ROOT / 'market-observatory/data/economic-calendar.json'


def run(script, *args):
    subprocess.run([sys.executable, str(ROOT / script), *map(str, args)], cwd=ROOT, check=True)


def normalize_calendar_contract():
    data = json.loads(CAL.read_text(encoding='utf-8'))
    normalized = 0
    for event in data.get('events', []):
        for key in ['previous', 'consensus', 'actual', 'te_forecast', 'surprise', 'market_data_source']:
            if key not in event:
                event[key] = None
                normalized += 1
        if 'market_metrics' not in event or not isinstance(event.get('market_metrics'), list):
            event['market_metrics'] = []
            normalized += 1
    CAL.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'CALENDAR_CONTRACT_NORMALIZE=PASS fields={normalized}')


def refresh(previous=None, seed=False):
    with TemporaryDirectory(prefix='calendar-refresh-') as directory:
        snapshot = Path(directory) / 'before.json'
        snapshot.write_bytes(CAL.read_bytes())
        if seed:
            run('tools/calendar_market_events.py', 'seed')
        run('tools/persist_calendar_history.py', snapshot)
        if previous:
            run('tools/persist_calendar_history.py', previous)
        run('tools/enrich_calendar_with_all_events.py')
        run('tools/calendar_market_events.py', 'refresh')
        # The public this-week feed rolls off old releases. Revisit only weeks
        # containing currently overdue events through the existing browser-grade
        # ForexFactory historical collector before we finalize freshness.
        run('tools/refresh_calendar_recent_forexfactory.py')
        # Some Korean schedule events have no dedicated calendar collector even
        # though the same release is already verified in official-macro.json.
        # Exact reference-period matching keeps this bridge fail-closed.
        run('tools/enrich_calendar_from_official_macro.py')
        run('tools/persist_calendar_history.py', snapshot)
        normalize_calendar_contract()
        run('tools/sync_calendar_representative_values.py')
        run('tools/refresh_official_central_bank_actuals.py', '--health-only')
        run('tools/archive_calendar_actuals.py')
        # Market-feed values on past BLS releases are replaced by the official
        # BLS API series (anchored reference month) before they become the
        # "previous" of the next release.
        run('tools/reconcile_bls_official_history.py')
        # Preserve/extend the 10-year SSOT from all observations already captured.
        # Deep historical source crawling is handled by the dedicated backfill job.
        run('tools/build_calendar_history.py')
        run('tools/fill_calendar_previous_from_history.py')
        run('tools/sync_calendar_representative_values.py')
        run('tools/build_calendar_history.py')
        # Optional weekly blog source: review missing future events only.
        # Never change official event/actual fields or fail for an unavailable blog.
        run('tools/calendar_stockchild_gap_watch.py')
        run('tests/test_calendar_data_quality.py')
    data = json.loads(CAL.read_text(encoding='utf-8'))
    health = data['actual_freshness']
    recovery = data.get('recent_historical_recovery') or {}
    bridge = data.get('official_macro_calendar_bridge') or {}
    print(f'CALENDAR_PIPELINE=PASS health={health["status"]} '
          f'pending={health["pending_count"]} overdue={health["overdue_count"]} '
          f'recent_recovery={recovery.get("overdue_before")}->{recovery.get("overdue_after")} '
          f'official_macro_updates={bridge.get("updated_events")}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--previous', type=Path)
    parser.add_argument('--seed', action='store_true')
    args = parser.parse_args()
    refresh(args.previous, args.seed)
