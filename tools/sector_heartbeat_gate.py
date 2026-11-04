#!/usr/bin/env python3
"""Recover sector snapshots independently of other Observatory datasets."""
import json
from datetime import datetime, timezone
from pathlib import Path
from build_observatory_sector_etf import completed_cutoff

PATH = Path('market-observatory/data/sector-etf.json')

def should_refresh(data, now, reference=None):
    cutoffs = data.get('completed_cutoffs') or {}
    if any(cutoffs.get(m, '') < completed_cutoff(m, now) for m in ('KR', 'US')):
        return True
    try:
        generated = datetime.fromisoformat(data['generated_kst'])
        if generated.tzinfo is None or generated > now:
            return True
        age = (now - generated).total_seconds()
    except (KeyError, TypeError, ValueError):
        return True
    quality = data.get('quality') or {}
    groups = data.get('groups') or []
    incomplete = not groups or any(not row.get('observed_date') for group in groups for row in group.get('rows', []))
    reference = reference or {}
    expected_us = str(reference.get('us_completed_session_date') or '')[:10]
    stale_us = bool(expected_us) and any(
        row.get('market') == 'US' and str(row.get('observed_date') or '')[:10] < expected_us
        for group in groups for row in group.get('rows', [])
    )
    return age >= 2700 and (bool(quality.get('fetch_error_count')) or incomplete or stale_us)

def main():
    try:
        data = json.loads(PATH.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        data = {}
    try:
        reference = json.loads(Path('market-observatory/data/observatory.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        reference = {}
    print('sector_should_refresh=' + str(should_refresh(data, datetime.now(timezone.utc), reference)).lower())

if __name__ == '__main__':
    main()
