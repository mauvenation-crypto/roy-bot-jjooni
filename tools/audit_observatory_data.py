#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from datetime import datetime, date
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
TOOLS=ROOT/'tools'
if str(TOOLS) not in sys.path:sys.path.insert(0,str(TOOLS))
import fedwatch_trade_calendar as fedwatch_calendar
from observatory_session import expected_completed_session
from regime_validity import regime_state

DATA=ROOT/'market-observatory'/'data'
OUT=DATA/'data-audit.json'
KST=ZoneInfo('Asia/Seoul'); ET=ZoneInfo('America/New_York')

EXPECTED_SERIES={
  'core_us':['NASDAQ100','SP500','VIX'],
  'us_supplement':['RUSSELL2000','DOW','NASDAQCOMPOSITE'],
  'kr_equity':['KOSPI','KOSDAQ'],
  'asia_equity':['NIKKEI225','HANGSENG','SHCOMP'],
  'fx':['DXY','USDKRW','USDJPY','JPYKRW'],
  'energy':['WTI','BRENT','NATGAS'],
  'metals':['GOLD','SILVER','COPPER'],
  'us_rates':['US3M','US2Y','US5Y_OFFICIAL','US10Y_OFFICIAL','US30Y_OFFICIAL','US_2S10S'],
  'kr_rates':['KR3Y','KR5Y','KR10Y','KR20Y','KR30Y','KR_3S10S'],
  'jp_rates':['JP2Y','JP5Y','JP10Y','JP20Y','JP30Y','JP_2S10S'],
  'crypto':['BTCUSD','ETHUSD'],
  'sentiment':['FEAR_GREED'],
}

def load(path, default=None):
    try:return json.loads(Path(path).read_text(encoding='utf-8'))
    except Exception:return {} if default is None else default

def days_between(a,b):
    try:return (date.fromisoformat(a)-date.fromisoformat(b)).days
    except Exception:return None

def parse_dt(v):
    try:return datetime.fromisoformat(str(v))
    except Exception:return None

def point(rows):
    rows=rows or []
    if not rows:return {'count':0,'last_date':None,'last_value':None}
    x=rows[-1] or {}
    return {'count':len(rows),'last_date':str(x.get('date') or '')[:10] or None,'last_value':x.get('value')}

def state_from_dates(dates,anchor=None,allow_lag_days=0):
    dates=[d for d in dates if d]
    if not dates:return 'UNAVAILABLE'
    if not anchor:return 'LIVE'
    lag=days_between(anchor,min(dates))
    if lag is None:return 'UNAVAILABLE'
    if max(dates)>anchor:return 'AHEAD_OF_ANCHOR'
    if lag>allow_lag_days:return 'LAGGING'
    return 'LIVE'

def build():
    now=datetime.now(KST); now_et=now.astimezone(ET); today=now.date().isoformat()
    obs=load(DATA/'observatory.json');pulse=load(DATA/'daily-market-pulse.json');public=load(ROOT/'public-market-daily.json')
    fed=load(DATA/'fed-watch.json');cal=load(DATA/'economic-calendar.json');sector=load(DATA/'sector-etf.json')
    macro=load(DATA/'official-macro.json');regime=load(DATA/'market-regime.json');fresh=load(DATA/'freshness-status.json');watchdog=load(DATA/'watchdog-status.json')
    series=obs.get('series') or {};latest=obs.get('latest') or {};session=str(obs.get('us_completed_session_date') or '')[:10] or None
    per_series={}
    for group,keys in EXPECTED_SERIES.items():
        for k in keys:
            p=point(series.get(k));p.update(group=group,latest_value=latest.get(k),latest_matches=(latest.get(k)==p['last_value']) if p['last_value'] is not None else False);per_series[k]=p
    groups={}
    def make_group(name,keys,anchor=None,allow_lag_days=0,critical=False):
        items={k:per_series.get(k,point(series.get(k))) for k in keys};dates=[v.get('last_date') for v in items.values()];missing=[k for k,v in items.items() if not v.get('last_date')];mismatched=[k for k,v in items.items() if v.get('last_value') is not None and latest.get(k)!=v.get('last_value')]
        state='UNAVAILABLE' if missing else state_from_dates(dates,anchor,allow_lag_days)
        if mismatched and state=='LIVE':state='INCONSISTENT'
        groups[name]={'state':state,'anchor':anchor,'allow_lag_days':allow_lag_days,'critical':critical,'items':items,'missing':missing,'latest_mismatch':mismatched}
    make_group('core_us',EXPECTED_SERIES['core_us'],expected_completed_session(now_et),0,True)
    make_group('us_supplement',EXPECTED_SERIES['us_supplement'],session,0,False)
    make_group('kr_equity',EXPECTED_SERIES['kr_equity'],today,4,True)
    # Reference only (regional comparison): never critical; local holidays differ.
    make_group('asia_equity',EXPECTED_SERIES['asia_equity'],today,4,False)
    make_group('fx',EXPECTED_SERIES['fx'],session,1,False)
    make_group('energy',EXPECTED_SERIES['energy'],session,1,False)
    make_group('metals',EXPECTED_SERIES['metals'],session,1,False)
    make_group('us_rates',EXPECTED_SERIES['us_rates'],session,3,False)
    make_group('kr_rates',EXPECTED_SERIES['kr_rates'],today,4,False)
    kr_fetch=(obs.get('cross_market_freshness_quality') or {}).get('KR_RATES') or {}
    if kr_fetch.get('fetch_succeeded') is False:
        groups['kr_rates']['state']='STALE'
        groups['kr_rates']['fetch_succeeded']=False
        groups['kr_rates']['failed_series']=kr_fetch.get('failed_series') or {}
    make_group('jp_rates',EXPECTED_SERIES['jp_rates'],today,5,False)
    # Historical dates within a five-calendar-day tolerance are not proof that
    # the latest completed Tokyo business day was actually collected.
    from refresh_observatory_supplementals import expected_jgb_business_date
    jp_expected=expected_jgb_business_date(now)
    jp_group=groups['jp_rates']
    jp_last=min((v.get('last_date') or '') for v in jp_group['items'].values())
    jp_quality=(obs.get('cross_market_freshness_quality') or {}).get('JP_RATES') or {}
    jp_group['expected_latest_weekday']=jp_expected
    jp_group['published_source_status']=jp_quality.get('status')
    if jp_quality.get('status') in ('STALE','UNAVAILABLE'):
        jp_group['state']=jp_quality['status']
    elif jp_last and jp_last<jp_expected:
        jp_group['state']='LAGGING'
    elif not jp_last:
        jp_group['state']='UNAVAILABLE'
    make_group('crypto',EXPECTED_SERIES['crypto'],None,0,False)
    # Sentiment is a latest published observation, not a completed cash close.
    # Accept today's published value, reject future dates and retain weekend tolerance.
    make_group('sentiment',EXPECTED_SERIES['sentiment'],today,4,False)

    pulse_session=str(pulse.get('market_date_us') or '')[:10] or None;tripod=(public.get('tripod_signal') or {});tripod_session=str(tripod.get('date') or tripod.get('session_date') or '')[:10] or None
    supplement=(obs.get('market_supplement_quality') or {});us_sup_quality={k:(supplement.get(k) or {}) for k in EXPECTED_SERIES['us_supplement']};kr_quality={k:(supplement.get(k) or {}) for k in EXPECTED_SERIES['kr_equity']}

    crypto_market=obs.get('crypto_market') or {};crypto_status={}
    for k in EXPECTED_SERIES['crypto']:
        raw=crypto_market.get(k) or {};qdt=parse_dt(raw.get('quote_as_of_kst'));age=None
        if qdt:
            if qdt.tzinfo is None:qdt=qdt.replace(tzinfo=KST)
            age=max(0,int((now-qdt.astimezone(KST)).total_seconds()))
        state='LIVE' if age is not None and age<=3600 else ('STALE' if raw else 'UNAVAILABLE')
        crypto_status[k]={'status':state,'producer_status':raw.get('status'),'quote_as_of_kst':raw.get('quote_as_of_kst'),'current_quote_age_seconds':age,'captured_quote_age_seconds':raw.get('quote_age_seconds')}
    if any(v['status']!='LIVE' for v in crypto_status.values()):groups['crypto']['state']='STALE'

    fed_expected=fedwatch_calendar._expected_latest_trade_date(now_et).isoformat();fed_asof=str(fed.get('market_data_as_of') or '')[:10] or None
    fed_state='UNAVAILABLE' if not fed_asof else ('LIVE' if fed_asof>=fed_expected else 'LAGGING')
    groups['fedwatch']={'state':fed_state,'anchor':fed_expected,'allow_lag_days':0,'critical':False,'items':{'FEDWATCH':{'last_date':fed_asof,'last_value':None}},'missing':[] if fed_asof else ['FEDWATCH'],'latest_mismatch':[]}

    cal_fresh=cal.get('actual_freshness') or {};cal_collection=cal.get('collection_health') or {}
    calendar_overdue_count=cal_fresh.get('overdue_count')
    if calendar_overdue_count is None:calendar_overdue_count=len(cal_fresh.get('overdue_events') or [])
    try:calendar_overdue_count=int(calendar_overdue_count or 0)
    except Exception:calendar_overdue_count=len(cal_fresh.get('overdue_events') or [])
    calendar_pending_count=cal_fresh.get('pending_count')
    if calendar_pending_count is None:calendar_pending_count=len(cal_fresh.get('pending_events') or [])
    try:calendar_pending_count=int(calendar_pending_count or 0)
    except Exception:calendar_pending_count=len(cal_fresh.get('pending_events') or [])
    failed_calendar_sources=cal_collection.get('failed_sources') or []

    file_status={'observatory':{'generated_kst':obs.get('generated_kst'),'session':session,'schema':obs.get('schema')},'daily_pulse':{'generated_kst':pulse.get('generated_kst'),'session':pulse_session,'snapshot_status':pulse.get('snapshot_status')},'public_tripod':{'generated_kst':public.get('generated_kst'),'session':tripod_session,'ok':tripod.get('ok'),'target':tripod.get('target')},'fedwatch':{'generated_kst':fed.get('generated_kst'),'source_kind':fed.get('source_kind'),'source_as_of_kst':fed.get('source_as_of_kst'),'market_data_as_of':fed_asof,'expected_market_data_date':fed.get('expected_market_data_date'),'audit_expected_market_data_date':fed_expected,'declared_freshness':fed.get('freshness'),'audit_state':fed_state},'calendar':{'generated_kst':cal.get('generated_kst'),'events':len(cal.get('events') or []),'actual_freshness':cal_fresh.get('status'),'overdue_count':calendar_overdue_count,'pending_count':calendar_pending_count,'collection_health':cal_collection.get('status'),'failed_source_count':len(failed_calendar_sources),'failed_sources':failed_calendar_sources},'sector':{'generated_kst':sector.get('generated_kst'),'as_of_date':sector.get('as_of_date'),'priced_count':(sector.get('summary') or {}).get('priced_count')},'official_macro':{'generated_kst':macro.get('generated_kst'),'schema':macro.get('schema')},'market_regime':{'status':regime_state(regime,now),'declared_status':regime.get('status'),'effective_window':regime.get('effective_window'),'source_generated_kst':(regime.get('source') or {}).get('generated_kst'),'monitoring_scope':'INVESTMENT_BOARD_REFERENCE_ONLY'},'freshness':{'generated_kst':fresh.get('generated_kst'),'overall':fresh.get('overall'),'critical_bad':fresh.get('critical_bad'),'warnings':fresh.get('warnings')},'watchdog':{'checked_kst':watchdog.get('checked_kst'),'result':watchdog.get('result'),'decision':watchdog.get('decision')}}

    issues=[]
    def issue(code,severity,detail):issues.append({'code':code,'severity':severity,'detail':detail})
    # Weekly analyst consensus is historical/reference context managed by the
    # Investment Board. Preserve expiry in file_status, but never count it as a
    # market-data or collection failure. Market/quote freshness remains strict.
    if not session:issue('NO_US_SESSION','CRITICAL','observatory.us_completed_session_date missing')
    if pulse_session!=session:issue('PULSE_SESSION_MISMATCH','CRITICAL',f'pulse={pulse_session} observatory={session}')
    if tripod_session!=session or tripod.get('ok') is not True:issue('TRIPOD_SESSION_MISMATCH','CRITICAL',f'tripod={tripod_session} ok={tripod.get("ok")} observatory={session}')
    for name,g in groups.items():
        if g['state']!='LIVE':issue('GROUP_'+name.upper()+'_'+g['state'],'CRITICAL' if g.get('critical') else 'WARN',f"anchor={g.get('anchor')} dates="+','.join(f"{k}:{v.get('last_date')}" for k,v in g.get('items',{}).items()))
    if fed.get('freshness')=='LIVE' and fed_state!='LIVE':issue('FEDWATCH_DECLARATION_INCONSISTENT','WARN',f'declared=LIVE audit={fed_state} expected={fed_expected} asof={fed_asof}')
    for k,q in us_sup_quality.items():
        if q.get('last_date')!=session or q.get('status')!='LIVE':issue('US_SUPPLEMENT_QUALITY_'+k,'WARN',str(q))
    if len({q.get('last_date') for q in kr_quality.values() if q.get('last_date')})>1:issue('KR_EQUITY_DATE_MISMATCH','CRITICAL',str({k:q.get('last_date') for k,q in kr_quality.items()}))
    for k,q in crypto_status.items():
        if q.get('status')!='LIVE':issue('CRYPTO_'+k+'_'+q['status'],'WARN',str(q))
    cal_state=cal_fresh.get('status')
    if cal_state in {'DEGRADED','FAILED','ERROR','STALE'}:issue('CALENDAR_ACTUAL_'+str(cal_state),'WARN',f'overdue_count={calendar_overdue_count} pending_count={calendar_pending_count}')
    if cal_collection.get('status') in {'DEGRADED','FAILED','ERROR','STALE'}:issue('CALENDAR_COLLECTION_'+str(cal_collection.get('status')),'WARN',f'failed_source_count={len(failed_calendar_sources)} sources='+','.join(str(x.get('source') or 'unknown') for x in failed_calendar_sources if isinstance(x,dict)))
    critical=[x for x in issues if x['severity']=='CRITICAL'];warnings=[x for x in issues if x['severity']=='WARN'];overall='FAIL' if critical else ('WARN' if warnings else 'PASS')
    return {'schema':'JJOONI_OBSERVATORY_DATA_AUDIT_V2','generated_kst':now.isoformat(timespec='seconds'),'overall':overall,'critical_count':len(critical),'warning_count':len(warnings),'observatory_session':session,'file_status':file_status,'groups':groups,'crypto_status':crypto_status,'issues':issues,'contracts':{'completed_session':'CORE_US_AND_US_SUPPLEMENT_MUST_MATCH_OBSERVATORY_SESSION','continuous_daily':'FX_ENERGY_METALS_MAY_LAG_CORE_BY_AT_MOST_1_CALENDAR_DAY','official_rates':'US_OFFICIAL_RATES_MAX_3_CALENDAR_DAYS_KR_MAX_4_JP_MAX_5','crypto':'QUOTE_AGE_RECOMPUTED_AT_AUDIT_TIME_MAX_3600S','fedwatch':'CME_FED_FUNDS_HOLIDAY_AWARE_EXPECTED_TRADE_DATE','calendar':'USES_CANONICAL_OVERDUE_COUNT_AND_OVERDUE_EVENTS_PLUS_COLLECTION_HEALTH','no_account_data':True,'read_only':True},'read_only':True}

def main():
    out=build();OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print('OBSERVATORY_DATA_AUDIT='+out['overall']);print('critical_count='+str(out['critical_count']));print('warning_count='+str(out['warning_count']));print('session='+str(out['observatory_session']))
    for x in out['issues']:print('ISSUE',x['severity'],x['code'],x['detail'])
if __name__=='__main__':main()

