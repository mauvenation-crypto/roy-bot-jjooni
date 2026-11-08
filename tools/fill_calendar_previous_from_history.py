#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CAL=ROOT/'market-observatory'/'data'/'economic-calendar.json'
HIST=ROOT/'market-observatory'/'data'/'economic-calendar-history.json'


def clean(v):
    if v is None:return None
    s=str(v).strip()
    return None if s in ('','-','—','None','null','N/A') else s


def latest_actual(bucket,before_day):
    rows=[]
    for row in (bucket or {}).get('rows') or []:
        day=str(row.get('date') or '')[:10]
        if day and day < before_day and clean(row.get('actual')) is not None:
            rows.append(row)
    rows.sort(key=lambda x:(str(x.get('date') or ''),str(x.get('datetime_kst') or '')))
    return rows[-1] if rows else None


HISTORY_SOURCE='CALENDAR_HISTORY_LAST_ACTUAL'


def refreshable(holder,row):
    """May a history-derived previous be (re)written from ``row``?

    Empty previous: yes. A previous this tool wrote earlier: only when the
    history now holds a newer release (the event was scheduled before the
    latest release, so its first fill went stale). Previous values from any
    other source (official release, ForexFactory) are never overwritten.
    """
    if clean(holder.get('previous')) is None:return True
    if holder.get('previous_source')!=HISTORY_SOURCE or not row:return False
    newer=str(row.get('date') or '')[:10]>str(holder.get('previous_observed_date') or '')[:10]
    # Same release, corrected value (e.g. market feed replaced by official BLS).
    corrected=str(row.get('date') or '')[:10]==str(holder.get('previous_observed_date') or '')[:10] and clean(row.get('actual'))!=clean(holder.get('previous'))
    return newer or corrected


def history_source(row):
    return clean((row or {}).get('source')) or 'Calendar history / captured prior actual'


def main():
    if not CAL.exists() or not HIST.exists():
        print('CALENDAR_PREVIOUS_FROM_HISTORY=SKIP missing file')
        return
    cal=json.loads(CAL.read_text(encoding='utf-8'))
    hist=json.loads(HIST.read_text(encoding='utf-8'))
    series=hist.get('series') or {}
    filled_event=filled_metric=0
    for e in cal.get('events') or []:
        day=str(e.get('datetime_kst') or e.get('date') or '')[:10]
        if not day:continue
        for m in e.get('market_metrics') or []:
            if not isinstance(m,dict) or m.get('metric_type')=='market_probability_snapshot':continue
            ref=m.get('history_ref')
            row=latest_actual(series.get(ref),day) if ref else None
            if row and refreshable(m,row):
                src=history_source(row)
                m['previous']=row['actual']
                m['previous_source']='CALENDAR_HISTORY_LAST_ACTUAL'
                m['previous_value_source']=src
                m['previous_observed_date']=row.get('date')
                m.setdefault('market_value_source',src)
                m.setdefault('source',src)
                if m.get('market_value_status')=='NOT_PUBLISHED':m['market_value_status']='PREVIOUS_ONLY'
                filled_metric+=1
        stale_event=(e.get('previous_source')==HISTORY_SOURCE or e.get('previous_source')=='METRIC_REPRESENTATIVE') and clean(e.get('actual')) is None
        if clean(e.get('previous')) is None or stale_event:
            primary=next((m for m in (e.get('market_metrics') or []) if isinstance(m,dict) and clean(m.get('previous')) is not None),None)
            if primary:
                e['previous']=primary['previous']
                e['previous_source']=primary.get('previous_source') or 'METRIC_REPRESENTATIVE'
                e['previous_observed_date']=primary.get('previous_observed_date')
                src=clean(primary.get('previous_value_source')) or clean(primary.get('market_value_source')) or clean(primary.get('actual_source')) or clean(primary.get('source'))
                if src and clean(e.get('market_data_source')) is None:e['market_data_source']=src
                filled_event+=1
            else:
                ref=e.get('history_ref');row=latest_actual(series.get(ref),day) if ref else None
                if row and refreshable(e,row):
                    src=history_source(row)
                    e['previous']=row['actual']
                    e['previous_source']='CALENDAR_HISTORY_LAST_ACTUAL'
                    e['previous_value_source']=src
                    e['previous_observed_date']=row.get('date')
                    if clean(e.get('market_data_source')) is None:e['market_data_source']=src
                    filled_event+=1
        if clean(e.get('actual')) is not None:e['market_value_status']='ACTUAL_AVAILABLE'
        elif clean(e.get('consensus')) is not None:e['market_value_status']='CONSENSUS_AVAILABLE'
        elif clean(e.get('previous')) is not None:e['market_value_status']='PREVIOUS_ONLY'
        else:e['market_value_status']='NOT_PUBLISHED'
    cal['previous_value_contract']='LATEST_PRIOR_VERIFIED_ACTUAL_AS_PREVIOUS_FALLBACK_V1'
    cal['previous_value_fill']={'event_rows':filled_event,'metric_rows':filled_metric,'provenance':'SOURCE_OF_PRIOR_ACTUAL_PROPAGATED'}
    CAL.write_text(json.dumps(cal,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('CALENDAR_PREVIOUS_FROM_HISTORY=PASS event=',filled_event,'metric=',filled_metric)

if __name__=='__main__':main()
