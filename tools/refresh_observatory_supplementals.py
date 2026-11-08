#!/usr/bin/env python3
"""Lightweight cross-market freshness refresh for Observatory.

This is deliberately separate from the heavy calendar/macro builder.  It may run
frequently and only updates market observations that are safe to refresh from
public market/official sources: core US indices, US supplemental indices, KR
indices, FX, energy, metals, current Japan MOF JGB yields, crypto spot and Fear
& Greed.  The existing historical rows are preserved and merged by date.
"""
from __future__ import annotations

import csv
import io
import json
import math
import re
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, time
from pathlib import Path
from zoneinfo import ZoneInfo
from yahoo_bar_date import bar_date

ROOT=Path(__file__).resolve().parents[1]
OBS=ROOT/'market-observatory'/'data'/'observatory.json'
KST=ZoneInfo('Asia/Seoul');ET=ZoneInfo('America/New_York')
UA='Mozilla/5.0 JJOONI-Market-Observatory-Freshness/2.1'
YAHOO='https://query1.finance.yahoo.com/v8/finance/chart/'
# MOF's canonical current file moved to the Japanese public path.  Keep the old
# English path as a fallback because it may still be mirrored intermittently.
JGB_CURRENT_URLS=(
 'https://www.mof.go.jp/jgbs/reference/interest_rate/jgbcm.csv',
 'https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/jgbcme.csv',
)

YAHOO_SYMBOLS={
 'NASDAQ100':'^NDX','SP500':'^GSPC','VIX':'^VIX',
 'RUSSELL2000':'^RUT','DOW':'^DJI','NASDAQCOMPOSITE':'^IXIC',
 'DXY':'DX-Y.NYB','USDKRW':'KRW=X','USDJPY':'JPY=X','JPYKRW':'JPYKRW=X',
 'WTI':'CL=F','BRENT':'BZ=F','NATGAS':'NG=F',
 'GOLD':'GC=F','SILVER':'SI=F','COPPER':'HG=F',
}
CORE=('NASDAQ100','SP500','VIX')
US_SUP=('RUSSELL2000','DOW','NASDAQCOMPOSITE')
CONTINUOUS=('DXY','USDKRW','USDJPY','JPYKRW','WTI','BRENT','NATGAS','GOLD','SILVER','COPPER')


def get_bytes(url,accept='*/*'):
    req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':accept})
    with urllib.request.urlopen(req,timeout=25) as r:return r.read()

def get_json(url):return json.loads(get_bytes(url,'application/json').decode('utf-8'))

def yahoo_series(symbol):
    qs=urllib.parse.urlencode({'interval':'1d','range':'3y','includePrePost':'false','events':'div,splits'})
    obj=get_json(YAHOO+urllib.parse.quote(symbol,safe='')+'?'+qs)
    result=(((obj.get('chart') or {}).get('result') or [None])[0])
    if not result:return []
    ts=result.get('timestamp') or [];closes=((((result.get('indicators') or {}).get('quote') or [{}])[0]).get('close') or [])
    out=[]
    for stamp,value in zip(ts,closes):
        if value is None:continue
        try:value=float(value)
        except Exception:continue
        if not math.isfinite(value) or value<=0:continue
        out.append({'date':bar_date(stamp,result,ET),'value':round(value,8)})
    ded={x['date']:x for x in out};return [ded[k] for k in sorted(ded)]

def merge_rows(old,new):
    ded={str(x.get('date') or '')[:10]:dict(x) for x in (old or []) if x.get('date') and x.get('value') is not None}
    for x in new or []:
        if x.get('date') and x.get('value') is not None:ded[str(x['date'])[:10]]=dict(x)
    return [ded[k] for k in sorted(ded)]

def completed_us_cutoff(now=None):
    now=(now or datetime.now(ET)).astimezone(ET)
    if now.time()<time(16,10):return (now.date()-timedelta(days=1)).isoformat()
    return now.date().isoformat()

def refresh_yahoo(data):
    sm=data.setdefault('series',{});latest=data.setdefault('latest',{});quality=data.setdefault('cross_market_freshness_quality',{});legacy=data.setdefault('market_supplement_quality',{})
    previous={k:list(sm.get(k) or []) for k in YAHOO_SYMBOLS}
    cutoff=completed_us_cutoff()
    fetched={}
    for key,symbol in YAHOO_SYMBOLS.items():
        try:
            rows=yahoo_series(symbol);fetched[key]=rows
        except Exception as exc:
            fetched[key]=[];quality[key]={'status':'STALE' if previous[key] else 'UNAVAILABLE','source':'Yahoo public daily','fetch_error':f'{type(exc).__name__}: {exc}'}

    date_sets=[]
    for key in CORE:
        dates={x['date'] for x in fetched.get(key,[]) if x['date']<=cutoff}
        if dates:date_sets.append(dates)
    common=max(set.intersection(*date_sets)) if len(date_sets)==len(CORE) and set.intersection(*date_sets) else None
    if common:
        data['us_completed_session_date']=common
    else:
        common=str(data.get('us_completed_session_date') or '')[:10]

    for key in CORE+US_SUP:
        fresh=[x for x in fetched.get(key,[]) if x['date']<=common]
        rows=merge_rows(previous[key],fresh)
        if common:rows=[x for x in rows if x['date']<=common]
        sm[key]=rows;latest[key]=rows[-1]['value'] if rows else None
        quality[key]={'status':'LIVE' if rows and rows[-1]['date']==common else ('LAGGING' if rows else 'UNAVAILABLE'),'source':'Yahoo public completed daily','last_date':rows[-1]['date'] if rows else None,'target_session':common}
        if key in US_SUP:
            legacy[key]=dict(quality[key])

    for key in CONTINUOUS:
        fresh=[x for x in fetched.get(key,[]) if not common or x['date']<=common]
        # Inside the freshly fetched window the fetch is authoritative: rows
        # stored under an older date convention (FX was labelled one day early)
        # must be replaced, not merged, or one close would sit on two dates.
        # The 3-day margin drops a shifted boundary row just before the window.
        edge=(date.fromisoformat(fresh[0]['date'])-timedelta(days=3)).isoformat() if fresh else ''
        kept=[x for x in previous[key] if str(x.get('date') or '')<edge] if fresh else previous[key]
        rows=merge_rows(kept,fresh)
        if common:rows=[x for x in rows if x['date']<=common]
        sm[key]=rows;latest[key]=rows[-1]['value'] if rows else None
        last=rows[-1]['date'] if rows else None
        quality[key]={'status':'LIVE' if last and (not common or last>=common) else ('LAGGING' if rows else 'UNAVAILABLE'),'source':'Yahoo public completed daily','last_date':last,'target_session':common}
    return common

US_RATE_KEYS=('US2Y','US3M','US5Y_OFFICIAL','US10Y_OFFICIAL','US30Y_OFFICIAL','US5Y','US10Y','US30Y','US_2S10S')

def refresh_us_rates(data):
    """Refresh card sources independently of the heavy daily/calendar build."""
    from build_market_observatory import treasury_rows
    sm=data.setdefault('series',{});latest=data.setdefault('latest',{})
    quality=data.setdefault('cross_market_freshness_quality',{})
    cutoff=completed_us_cutoff()
    target=str(data.get('us_completed_session_date') or cutoff)
    def apply(key,fresh,source,error=None):
        fresh=[r for r in fresh if r['date']<=cutoff and r.get('value') is not None and math.isfinite(float(r['value']))]
        rows=merge_rows(sm.get(key),fresh)
        sm[key]=rows;latest[key]=rows[-1]['value'] if rows else None
        last=rows[-1]['date'] if rows else None
        quality[key]={'source':source,'last_date':last,'target_session':target,
                      'status':('STALE' if rows else 'UNAVAILABLE') if error else ('LIVE' if last and last>=target else 'LAGGING' if rows else 'UNAVAILABLE')}
        if error:quality[key]['fetch_error']=str(error)
    for key,symbol in {'US5Y':'^FVX','US10Y':'^TNX','US30Y':'^TYX'}.items():
        try:apply(key,yahoo_series(symbol),'Cboe / Yahoo completed daily')
        except Exception as exc:apply(key,[],'Cboe / Yahoo completed daily',exc)
    mapping={'US3M':'3 Mo','US2Y':'2 Yr','US5Y_OFFICIAL':'5 Yr','US10Y_OFFICIAL':'10 Yr','US30Y_OFFICIAL':'30 Yr'}
    try:
        # The cutoff year also handles the New Year before the first US close.
        rows=treasury_rows(int(cutoff[:4]))
        if not rows:raise RuntimeError('EMPTY_TREASURY_CURVE')
        for key,col in mapping.items():
            apply(key,[{'date':r['date'],'value':r['values'].get(col)} for r in rows],'US Treasury official daily')
    except Exception as exc:
        for key in mapping:apply(key,[],'US Treasury official daily',exc)
    a={r['date']:r['value'] for r in sm.get('US10Y_OFFICIAL',[])}
    b={r['date']:r['value'] for r in sm.get('US2Y',[])}
    sm['US_2S10S']=[{'date':d,'value':round(a[d]-b[d],8)} for d in sorted(set(a)&set(b))]
    latest['US_2S10S']=sm['US_2S10S'][-1]['value'] if sm['US_2S10S'] else None
    quality['US_2S10S']=dict(quality['US2Y'])
    quality['US_2S10S']['last_date']=sm['US_2S10S'][-1]['date'] if sm['US_2S10S'] else None
    data['us_rates_refreshed_kst']=datetime.now(KST).isoformat(timespec='seconds')


def _decode_csv(blob):
    for enc in ('utf-8-sig','cp932','shift_jis','utf-8'):
        try:return blob.decode(enc)
        except Exception:pass
    return blob.decode('utf-8','ignore')

def _normalize_tenor(raw):
    s=str(raw or '').strip().lower().replace('years','y').replace('year','y').replace('年','y').replace(' ','').replace('-','')
    m=re.fullmatch(r'(\d{1,2})(?:y|yr)?',s) or re.match(r'(\d{1,2})y',s)
    if m:return f'{int(m.group(1))}Y'
    return str(raw or '').strip()

def _parse_jgb_date(raw):
    s=str(raw or '').strip()
    for fmt in ('%Y/%m/%d','%Y-%m-%d','%Y.%m.%d'):
        try:return datetime.strptime(s,fmt).date().isoformat()
        except Exception:pass
    m=re.fullmatch(r'R\s*(\d{1,2})[./-](\d{1,2})[./-](\d{1,2})',s,re.I)
    if not m:
        m=re.fullmatch(r'令和\s*(\d{1,2})年\s*(\d{1,2})月\s*(\d{1,2})日',s)
    if m:
        y,mo,da=map(int,m.groups())
        return datetime(2018+y,mo,da).date().isoformat()
    return None

def _parse_jgb_csv(blob):
    text=_decode_csv(blob);reader=csv.reader(io.StringIO(text));header=None;rows=[]
    for row in reader:
        if not row:continue
        first=str(row[0] or '').strip()
        if header is None:
            if 'date' in first.lower() or first in {'年月日','基準日'}:
                header=[_normalize_tenor(x) for x in row]
            continue
        d=_parse_jgb_date(first)
        if not d:continue
        vals={}
        for i,name in enumerate(header[1:],1):
            if i>=len(row):continue
            try:vals[name]=float(str(row[i]).replace('%','').strip())
            except Exception:vals[name]=None
        rows.append({'date':d,'values':vals})
    if not rows:raise RuntimeError('JGB_CURRENT_CSV_NO_ROWS')
    return sorted(rows,key=lambda x:x['date'])

def fetch_current_jgb_rows():
    # The Japanese and English MOF mirrors do not always refresh together.
    # Prefer the newest *actual official observation* rather than accepting a
    # successfully downloaded but lagging primary file as current.
    errors=[];best=None;expected=expected_jgb_business_date()
    for url in JGB_CURRENT_URLS:
        try:
            rows=_parse_jgb_csv(get_bytes(url,'text/csv,*/*'))
            last=rows[-1]['date']
            if best is None or last>best[0]:best=(last,rows,url)
            if last>=expected:break
        except Exception as exc:errors.append(f'{url}:{type(exc).__name__}:{exc}')
    if best:return best[1],best[2]
    # The current CSV only carries the current month. Right after a month
    # rollover it can be an empty template: that is "no new rows yet", not a
    # collection failure. Stored rows are then graded by date against the
    # business-day calendar instead of being forced to STALE.
    if errors and all('JGB_CURRENT_CSV_NO_ROWS' in e for e in errors):
        print('JGB_CURRENT_REFRESH=EMPTY_MONTH_FILE '+JGB_CURRENT_URLS[0])
        return [],JGB_CURRENT_URLS[0]
    raise RuntimeError('JGB_CURRENT_ALL_SOURCES_FAILED|'+'|'.join(errors))

def expected_jgb_business_date(now=None):
    """Latest JGB observation expected under the MOF publication timetable.

    Japan MOF publishes a reference day's yield on the NEXT business day at
    about 09:30 JST (MOF FAQ /faq/jgbs/04hf.htm). A current-day yield must
    not be required after the Tokyo market closes. Holidays and exceptional
    publication delays remain nonfatal source warnings, not proxy prices.
    """
    # Business days follow the Tokyo JGB market calendar (national holidays
    # and Dec 31-Jan 3 closed), validated against MOF history since 2022.
    from japan_business_calendar import is_jgb_business_day, previous_jgb_business_day
    local=(now or datetime.now(KST)).astimezone(KST)
    release_day=local.date()
    if local.time()<time(9,30) or not is_jgb_business_day(release_day):
        release_day=previous_jgb_business_day(release_day)
    return previous_jgb_business_day(release_day).isoformat()


def refresh_jgb(data):
    sm=data.setdefault('series',{});latest=data.setdefault('latest',{});quality=data.setdefault('cross_market_freshness_quality',{})
    try:
        rows,source_url=fetch_current_jgb_rows();mapping={'JP2Y':'2Y','JP5Y':'5Y','JP10Y':'10Y','JP20Y':'20Y','JP30Y':'30Y'}
        for key,tenor in mapping.items():
            fresh=[{'date':x['date'],'value':x['values'].get(tenor)} for x in rows if x['values'].get(tenor) is not None]
            merged=merge_rows(sm.get(key),fresh);sm[key]=merged;latest[key]=merged[-1]['value'] if merged else None
        if sm.get('JP2Y') and sm.get('JP10Y'):
            a={x['date']:x['value'] for x in sm['JP10Y']};b={x['date']:x['value'] for x in sm['JP2Y']};sm['JP_2S10S']=[{'date':d,'value':round(a[d]-b[d],8)} for d in sorted(set(a)&set(b))];latest['JP_2S10S']=sm['JP_2S10S'][-1]['value'] if sm['JP_2S10S'] else None
        dates=[(sm.get(k) or [{}])[-1].get('date','') for k in mapping]
        last=min(dates) if all(dates) else None
        expected=expected_jgb_business_date()
        state='LIVE' if last and last>=expected else ('LAGGING' if last else 'UNAVAILABLE')
        quality['JP_RATES']={'status':state,'source':'Japan MOF current JGB yield CSV','source_url':source_url,'last_date':last,'expected_latest_weekday':expected,'timing_note':'Japanese holidays or publication delays can cause a nonfatal LAGGING warning'}
        data.setdefault('sources',{})['JP_JGB_CURRENT']='Japan MOF current JGB yield CSV (jgbcm.csv primary) merged with historical series'
        print('JGB_CURRENT_REFRESH='+state+' last_date='+str(last)+' expected='+expected+' source='+source_url)
    except Exception as exc:
        old=max(((sm.get(k) or [{}])[-1].get('date','') for k in ('JP2Y','JP5Y','JP10Y','JP30Y')),default='')
        quality['JP_RATES']={'status':'STALE' if old else 'UNAVAILABLE','source':'Japan MOF current JGB yield CSV','source_urls':list(JGB_CURRENT_URLS),'last_date':old or None,'expected_latest_weekday':expected_jgb_business_date(),'fetch_error':f'{type(exc).__name__}: {exc}'}
        print('JGB_CURRENT_REFRESH=WARN',quality['JP_RATES'])

def refresh_kr_and_sentiment_and_crypto(data):
    from add_observatory_equities import naver_index_recent, merge_rows as eq_merge, fear_greed_series, enrich_crypto
    sm=data.setdefault('series',{});latest=data.setdefault('latest',{});quality=data.setdefault('cross_market_freshness_quality',{});legacy=data.setdefault('market_supplement_quality',{})
    for key in ('KOSPI','KOSDAQ'):
        try:
            fresh,url=naver_index_recent(key);rows=eq_merge(sm.get(key),fresh);sm[key]=rows;latest[key]=rows[-1]['value'];quality[key]={'status':'LIVE','source':'Naver Finance index daily','last_date':rows[-1]['date'],'source_url':url}
        except Exception as exc:quality[key]={'status':'STALE' if sm.get(key) else 'UNAVAILABLE','source':'Naver Finance index daily','last_date':(sm.get(key) or [{}])[-1].get('date'),'fetch_error':f'{type(exc).__name__}: {exc}'}
        legacy[key]=dict(quality[key])
    try:
        fg=fear_greed_series();sm['FEAR_GREED']=fg;latest['FEAR_GREED']=fg[-1]['value'] if fg else None;quality['FEAR_GREED']={'status':'LIVE' if fg else 'UNAVAILABLE','source':'FearAndGreedGraph public JSON','last_date':fg[-1]['date'] if fg else None}
    except Exception as exc:quality['FEAR_GREED']={'status':'STALE' if sm.get('FEAR_GREED') else 'UNAVAILABLE','fetch_error':f'{type(exc).__name__}: {exc}'}
    enrich_crypto(data)

def main():
    data=json.loads(OBS.read_text(encoding='utf-8'))
    session=refresh_yahoo(data)
    refresh_us_rates(data)
    refresh_jgb(data)
    refresh_kr_and_sentiment_and_crypto(data)
    data['supplemental_refreshed_kst']=datetime.now(KST).isoformat(timespec='seconds')
    data['supplemental_refresh_contract']='ALL_MARKET_FAMILIES_COMPLETED_SESSION_PLUS_24X7_CRYPTO_V1'
    OBS.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('OBSERVATORY_SUPPLEMENTAL_REFRESH=PASS session='+str(session)+' refreshed_kst='+data['supplemental_refreshed_kst'])

if __name__=='__main__':main()
