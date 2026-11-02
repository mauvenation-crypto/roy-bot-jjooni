#!/usr/bin/env python3
"""Read-only integration probe of MOF's current JGB CSV; no writes or fallback."""
import csv
import io
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_market_observatory import get_text

URL = 'https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/jgbcme.csv'
expected = os.environ.get('MOF_EXPECTED_OBSERVATION_DATE')
records = list(csv.reader(io.StringIO(get_text(URL, 'cp932'))))
header = next((r for r in records if r and ('Date' in r[0] or '年月日' in r[0])), None)
if not header:
    raise SystemExit('MOF_CURRENT_CSV_HEADER_MISSING')
by_date = {}
for row in records:
    if not row:
        continue
    raw_date = row[0].strip().replace('/', '-')
    try:
        date_key = datetime.strptime(raw_date, '%Y-%m-%d').date().isoformat()
    except ValueError:
        continue
    date_values = by_date.setdefault(date_key, {})
    for idx, col in enumerate(header[1:], 1):
        name = col.strip().replace('year','Y').replace('Year','Y').replace('years','Y')
        if idx < len(row):
            try:
                date_values[name] = float(row[idx])
            except (TypeError, ValueError):
                pass
if not by_date:
    raise SystemExit('MOF_CURRENT_CSV_NO_DATED_OBSERVATIONS')
selected = expected or max(by_date)
if selected not in by_date:
    raise SystemExit(f'MOF_CURRENT_CSV_EXPECTED_DATE_MISSING={selected}')
date_values = by_date[selected]
today = datetime.now(ZoneInfo('Asia/Seoul')).date()
age = (today - datetime.strptime(selected, '%Y-%m-%d').date()).days
if age < 0 or age > 10:
    raise SystemExit(f'MOF_CURRENT_CSV_OUTDATED_OR_FUTURE={selected},age={age}')
for tenor in ('2Y','5Y','10Y','30Y'):
    if not any(tenor.lower() in k.lower().replace(' ','') for k in date_values):
        raise SystemExit(f'MOF_CURRENT_CSV_TENOR_MISSING={tenor}')
print('MOF_CURRENT_OFFICIAL_PROBE=PASS', 'observation_date=', selected, 'source=', URL, 'values=', date_values)
