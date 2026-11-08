#!/usr/bin/env python3
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from calendar_market_events import representative_metric  # noqa: E402

ROOT=Path(__file__).resolve().parents[1]
CAL=ROOT/'market-observatory'/'data'/'economic-calendar.json'
OVR=ROOT/'market-observatory'/'data'/'calendar-manual-overrides.json'
NOW=datetime.now(ZoneInfo('Asia/Seoul'))

def clean(value):
    if value is None:return None
    value=str(value).strip()
    return None if value in ('','-','—','None','null','N/A') else value

c=json.loads(CAL.read_text(encoding='utf-8'))
events=c.get('events') or []
keys=[(str(e.get('datetime_kst') or '')[:16],e.get('country'),re.sub(r'\s+',' ',str(e.get('title') or '').strip().lower())) for e in events]
assert not [k for k,n in Counter(keys).items() if n>1],Counter(keys)
assert all(datetime.fromisoformat(e['datetime_kst']).utcoffset() is not None for e in events)
assert not [e.get('title') for e in events if re.match(r'^N\s*ews\b',str(e.get('title') or ''),re.I)]

future_actual=[];probability_actual=[];duplicate_sources=[];primary_mismatch=[]
for e in events:
    dt=datetime.fromisoformat(e['datetime_kst'])
    metrics=[m for m in e.get('market_metrics') or [] if isinstance(m,dict)]
    official=[m for m in metrics if m.get('metric_type')!='market_probability_snapshot']
    if dt>NOW and (clean(e.get('actual')) or any(clean(m.get('actual')) for m in official)):
        future_actual.append(e.get('title'))
    probability_actual.extend((e.get('title'),m.get('key')) for m in metrics if
                              m.get('metric_type')=='market_probability_snapshot' and clean(m.get('actual')))
    parts=[x.strip() for x in str(e.get('market_data_source') or '').split(' + ') if x.strip()]
    if len(parts)!=len(set(parts)):duplicate_sources.append(e.get('title'))
    # Same rule as the sync step: the card follows ONE representative metric
    # (first with a consensus), so previous and consensus share a measure.
    primary=representative_metric(e)
    if primary:
        assert clean(e.get('market_data_source')),('missing market_data_source',e.get('title'),primary)
        for key in ['previous','consensus','actual']:
            if clean(primary.get(key)) is not None and clean(e.get(key))!=clean(primary.get(key)):
                primary_mismatch.append((e.get('title'),key,e.get(key),primary.get(key)))

assert not future_actual,future_actual
assert not probability_actual,probability_actual
assert not duplicate_sources,duplicate_sources
assert not primary_mismatch,primary_mismatch

overrides=json.loads(OVR.read_text(encoding='utf-8')).get('overrides') or []
targets=[((o.get('match') or {}).get('date'),(o.get('match') or {}).get('country'),
          (o.get('match') or {}).get('title_contains')) for o in overrides]
assert not [k for k,n in Counter(targets).items() if n>1],Counter(targets)
assert not [(o.get('match'),m) for o in overrides for m in o.get('market_metrics') or [] if
            m.get('metric_type')=='market_probability_snapshot' and clean(m.get('actual'))]
print('CALENDAR_DATA_QUALITY=PASS events=',len(events),'duplicates=0 future_actual=0 probability_actual=0 source_duplicates=0 primary_mismatch=0')
