#!/usr/bin/env python3
from __future__ import annotations
import json, math, urllib.parse, urllib.request
from copy import deepcopy
from datetime import datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
OBS=ROOT/'market-observatory'/'data'/'observatory.json'
KST=ZoneInfo('Asia/Seoul');ET=ZoneInfo('America/New_York');UTC=ZoneInfo('UTC')
YAHOO='https://query1.finance.yahoo.com/v8/finance/chart/'
NAVER_INDEX='https://m.stock.naver.com/api/index/{code}/price'
FEAR_GREED='https://fearandgreedgraph.com/api/fear-greed'
UA='Mozilla/5.0 JJOONI-Market-Observatory/1.0'

SYMBOLS={
    'KOSPI':'^KS11','KOSDAQ':'^KQ11','RUSSELL2000':'^RUT',
    'DOW':'^DJI','NASDAQCOMPOSITE':'^IXIC','SILVER':'SI=F',
}
KR_KEYS=('KOSPI','KOSDAQ')
US_CASH_KEYS=('RUSSELL2000','DOW','NASDAQCOMPOSITE')


def get_json(url):
    req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'application/json','Accept-Language':'ko-KR,ko;q=0.9,en;q=0.8'})
    with urllib.request.urlopen(req,timeout=20) as r:return json.loads(r.read().decode('utf-8'))


def yahoo_series(symbol,date_zone=ET):
    qs=urllib.parse.urlencode({'interval':'1d','range':'3y','includePrePost':'false','events':'div,splits'})
    obj=get_json(YAHOO+urllib.parse.quote(symbol,safe='')+'?'+qs)
    rs=((obj.get('chart') or {}).get('result') or [])
    if not rs:return []
    b=rs[0];ts=b.get('timestamp') or [];cs=((((b.get('indicators') or {}).get('quote') or [{}])[0]).get('close') or [])
    out=[]
    for t,v in zip(ts,cs):
        if v is None:continue
        try:v=float(v)
        except:continue
        if not math.isfinite(v):continue
        d=datetime.fromtimestamp(int(t),date_zone).date().isoformat()
        out.append({'date':d,'value':round(v,8)})
    ded={x['date']:x for x in out}
    return [ded[k] for k in sorted(ded)]


def naver_index_recent(code,page_size=60):
    url=NAVER_INDEX.format(code=code)+'?'+urllib.parse.urlencode({'pageSize':page_size,'page':1})
    obj=get_json(url)
    if not isinstance(obj,list) or not obj:raise ValueError('NAVER_INDEX_EMPTY')
    out=[]
    for row in obj:
        d=str(row.get('localTradedAt') or '')[:10]
        raw=str(row.get('closePrice') or '').replace(',','').strip()
        if len(d)!=10 or not raw:continue
        try:v=float(raw)
        except:continue
        if math.isfinite(v) and v>0:out.append({'date':d,'value':round(v,8)})
    if not out:raise ValueError('NAVER_INDEX_NO_VALID_ROWS')
    ded={x['date']:x for x in out}
    return [ded[k] for k in sorted(ded)],url


def merge_rows(old,new):
    ded={str(x.get('date'))[:10]:dict(x) for x in (old or []) if x.get('date') and x.get('value') is not None}
    for x in new or []:ded[str(x['date'])[:10]]=dict(x)
    return [ded[k] for k in sorted(ded)]


def completed_us_cutoff(now=None):
    now=(now or datetime.now(ET)).astimezone(ET)
    if now.time()<time(16,15):
        from datetime import timedelta
        return (now.date()-timedelta(days=1)).isoformat()
    return now.date().isoformat()


def completed_us_rows(rows,target_session=None):
    cutoff=min(completed_us_cutoff(),str(target_session or '9999-12-31')[:10])
    return [x for x in (rows or []) if str(x.get('date') or '')[:10]<=cutoff]


CRYPTO_SYMBOLS={'BTCUSD':'BTC-USD','ETHUSD':'ETH-USD'}
COINGECKO_IDS={'BTCUSD':'bitcoin','ETHUSD':'ethereum'}
COINGECKO_SPOT='https://api.coingecko.com/api/v3/simple/price'


def coingecko_spot_observations(now=None):
    """One public request for both USD spot quotes; never invent provider timestamps.

    CoinGecko simple/price does not supply historical daily closes. Its spot
    observations may replace only the same UTC day's in-progress row; older
    stored daily rows retain their existing provenance and status.
    """
    now=(now or datetime.now(UTC)).astimezone(UTC)
    url=COINGECKO_SPOT+'?'+urllib.parse.urlencode({
        'ids':','.join(COINGECKO_IDS.values()),
        'vs_currencies':'usd',
        'include_last_updated_at':'true',
    })
    payload=get_json(url)
    if not isinstance(payload,dict):raise ValueError('COINGECKO_RESPONSE_INVALID')
    observations={}
    for key,coin_id in COINGECKO_IDS.items():
        try:
            item=payload[coin_id]
            raw_price=item['usd'];raw_stamp=item['last_updated_at']
            if isinstance(raw_price,bool) or isinstance(raw_stamp,bool):
                raise ValueError('COINGECKO_QUOTE_INVALID_TYPE')
            price=float(raw_price);stamp=int(raw_stamp)
            if not math.isfinite(price) or price<=0 or stamp<=0:
                raise ValueError('COINGECKO_QUOTE_INVALID')
            observed=datetime.fromtimestamp(stamp,UTC)
            age=(now-observed).total_seconds()
            if age < -300:raise ValueError('COINGECKO_QUOTE_FUTURE_TIMESTAMP')
            if age>3600:raise ValueError('COINGECKO_QUOTE_STALE')
            if observed.date()!=now.date():raise ValueError('COINGECKO_QUOTE_UTC_DATE_MISMATCH')
            date=observed.date().isoformat()
            observed_kst=observed.astimezone(KST).isoformat(timespec='seconds')
            row={'date':date,'value':round(price,8),'session_status':'IN_PROGRESS',
                 'date_basis':'UTC','observed_kst':observed_kst,
                 'observation_type':'SPOT_SNAPSHOT','source':'CoinGecko'}
            snapshot={'symbol':CRYPTO_SYMBOLS[key],'source':'CoinGecko public simple/price USD spot',
                      'source_url':url,'price':price,'quote_as_of_kst':observed_kst,
                      'captured_kst':now.astimezone(KST).isoformat(timespec='seconds'),
                      'status':'LIVE','quote_age_seconds':max(0,int(age)),
                      'comparison_basis':'UTC_DAILY_CLOSE_NOT_ROLLING_24H','market_hours':'24/7'}
            observations[key]=([row],snapshot)
        except (KeyError,TypeError,ValueError,OverflowError,OSError) as exc:
            print('COINGECKO_QUOTE=WARN',key,type(exc).__name__,str(exc))
    return observations

def crypto_observation(symbol, now=None):
    qs=urllib.parse.urlencode({'interval':'1d','range':'3y','includePrePost':'false'})
    url=YAHOO+urllib.parse.quote(symbol,safe='')+'?'+qs
    obj=get_json(url);now=now or datetime.now(UTC)
    rs=((obj.get('chart') or {}).get('result') or [])
    if not rs:raise ValueError('CRYPTO_SOURCE_EMPTY')
    result=rs[0];meta=result.get('meta') or {};closes=(((result.get('indicators') or {}).get('quote') or [{}])[0]).get('close') or []
    rows={};today=now.astimezone(UTC).date().isoformat()
    for stamp,value in zip(result.get('timestamp') or [],closes):
        if value is None:continue
        value=float(value)
        if not math.isfinite(value) or value<=0:continue
        day=datetime.fromtimestamp(int(stamp),UTC).date().isoformat()
        if day>today:continue
        rows[day]={'date':day,'value':round(value,8),'session_status':'IN_PROGRESS' if day==today else 'COMPLETED','date_basis':'UTC'}
    price=meta.get('regularMarketPrice');stamp=meta.get('regularMarketTime')
    if price is None or stamp is None:raise ValueError('CRYPTO_QUOTE_METADATA_MISSING')
    price=float(price)
    if not math.isfinite(price) or price<=0:raise ValueError('CRYPTO_QUOTE_INVALID')
    observed=datetime.fromtimestamp(int(stamp),UTC);age=(now.astimezone(UTC)-observed).total_seconds()
    if age < -300:raise ValueError('CRYPTO_QUOTE_FUTURE_TIMESTAMP')
    day=observed.date().isoformat();rows[day]={'date':day,'value':round(price,8),'session_status':'IN_PROGRESS' if day==today else 'COMPLETED','date_basis':'UTC','observed_kst':observed.astimezone(KST).isoformat(timespec='seconds')}
    snapshot={'symbol':symbol,'source':'Yahoo Finance spot crypto quote + UTC daily candles','source_url':url,'price':price,'quote_as_of_kst':observed.astimezone(KST).isoformat(timespec='seconds'),'captured_kst':now.astimezone(KST).isoformat(timespec='seconds'),'status':'LIVE' if age<=3600 else 'STALE','quote_age_seconds':max(0,int(age)),'comparison_basis':'UTC_DAILY_CLOSE_NOT_ROLLING_24H','market_hours':'24/7'}
    return [rows[d] for d in sorted(rows)],snapshot


def retain_crypto_observations(current, previous):
    for key in CRYPTO_SYMBOLS:
        rows=(previous.get('series') or {}).get(key)
        if rows and not (current.get('series') or {}).get(key):
            current.setdefault('series',{})[key]=deepcopy(rows);current.setdefault('latest',{})[key]=rows[-1]['value']
            old=deepcopy((previous.get('crypto_market') or {}).get(key) or {});old.update(status='STALE',refresh_state='AWAITING_REFRESH');current.setdefault('crypto_market',{})[key]=old
    return current


def enrich_crypto(data):
    series_map=data.setdefault('series',{});latest=data.setdefault('latest',{});snapshots=data.setdefault('crypto_market',{})
    try:
        coingecko=coingecko_spot_observations()
    except Exception as exc:
        coingecko={}
        print('COINGECKO_FETCH=WARN',type(exc).__name__,str(exc))
    for key,symbol in CRYPTO_SYMBOLS.items():
        try:
            if key in coingecko:
                fresh,snapshot=coingecko[key]
                rows=series_map.get(key,[])
                # Only repair missing completed daily history. A successful spot
                # refresh must not download three years twice every heartbeat.
                previous_day=(datetime.fromisoformat(fresh[0]['date']).date()-timedelta(days=1)).isoformat()
                history_ready=any(r.get('date')==previous_day and r.get('session_status')=='COMPLETED' for r in rows)
                try:
                    yahoo_rows=[] if history_ready else crypto_observation(symbol)[0]
                    completed=[r for r in yahoo_rows if r.get('date','')<fresh[0]['date']
                               and r.get('session_status')=='COMPLETED']
                    rows=merge_rows(rows,completed)
                except Exception as history_exc:
                    print('CRYPTO_DAILY_HISTORY=WARN',key,type(history_exc).__name__,str(history_exc))
                rows=merge_rows(rows,fresh)
            else:
                rows,snapshot=crypto_observation(symbol)
            if not rows:raise ValueError('CRYPTO_SERIES_EMPTY')
            series_map[key]=rows;latest[key]=rows[-1]['value'];snapshots[key]=snapshot
            print('CRYPTO_QUOTE=PASS',key,snapshot['status'],'price=',snapshot['price'],'as_of=',snapshot['quote_as_of_kst'],'source=',snapshot['source'])
        except Exception as exc:
            old=dict(snapshots.get(key) or {});old.update(status='STALE' if series_map.get(key) else 'UNAVAILABLE',fetch_error=f'{type(exc).__name__}: {exc}',last_attempt_kst=datetime.now(KST).isoformat(timespec='seconds'));snapshots[key]=old
            print('CRYPTO_QUOTE=WARN',key,old['status'],old['fetch_error'])
    data.setdefault('sources',{})['CRYPTO_SPOT']='CoinGecko simple/price USD spot primary; Yahoo Finance spot + UTC daily candles fallback; provider observation timestamps preserved'
    data['crypto_contract']='SPOT_QUOTE_WITH_UTC_DAILY_COMPARISON_V1'
    data['crypto_enriched_kst']=datetime.now(KST).isoformat(timespec='seconds')


def fear_greed_series():
    obj=get_json(FEAR_GREED);dates=obj.get('dates') or [];values=obj.get('values') or [];out=[]
    for d,v in zip(dates,values):
        try:v=float(v)
        except:continue
        if not math.isfinite(v):continue
        d=str(d)[:10]
        if len(d)==10:out.append({'date':d,'value':round(v,4)})
    ded={x['date']:x for x in out};return [ded[k] for k in sorted(ded)]


def main():
    data=json.loads(OBS.read_text(encoding='utf-8'));sm=data.setdefault('series',{});latest=data.setdefault('latest',{});src=data.setdefault('sources',{});prev=dict(sm)
    quality={};us_session=str(data.get('us_completed_session_date') or '')[:10]

    for key in KR_KEYS:
        try:
            fresh,url=naver_index_recent(key);xs=merge_rows(prev.get(key,[]),fresh);state='LIVE';source='Naver Finance index daily';err=None
        except Exception as e:
            try:
                xs=yahoo_series(SYMBOLS[key],KST);state='FALLBACK';source='Yahoo Finance daily fallback';err=f'Naver {type(e).__name__}: {e}'
            except Exception as e2:
                xs=prev.get(key,[]);state='STALE' if xs else 'UNAVAILABLE';source='last verified snapshot';err=f'Naver {type(e).__name__}: {e}; Yahoo {type(e2).__name__}: {e2}'
        sm[key]=xs;latest[key]=xs[-1]['value'] if xs else None
        quality[key]={'status':state,'source':source,'last_date':xs[-1]['date'] if xs else None,'fetch_error':err,'date_basis':'Asia/Seoul trading date'}
        print('KR_EQUITY=',key,state,'last_date=',quality[key]['last_date'],'value=',latest[key])

    for key in US_CASH_KEYS:
        try:
            xs=completed_us_rows(yahoo_series(SYMBOLS[key],ET),us_session);state='LIVE' if xs and xs[-1]['date']==us_session else 'LAGGING';err=None
        except Exception as e:
            xs=completed_us_rows(prev.get(key,[]),us_session);state='STALE' if xs else 'UNAVAILABLE';err=f'{type(e).__name__}: {e}'
        sm[key]=xs;latest[key]=xs[-1]['value'] if xs else None
        quality[key]={'status':state,'source':'Yahoo Finance completed cash-session daily','last_date':xs[-1]['date'] if xs else None,'target_session':us_session,'fetch_error':err,'date_basis':'America/New_York'}

    try:xs=yahoo_series(SYMBOLS['SILVER'],ET);silver_state='LIVE'
    except Exception as e:print(f'SILVER_FETCH_WARN={e}');xs=prev.get('SILVER',[]);silver_state='STALE' if xs else 'UNAVAILABLE'
    sm['SILVER']=xs;latest['SILVER']=xs[-1]['value'] if xs else None;quality['SILVER']={'status':silver_state,'source':'Yahoo Finance SI=F','last_date':xs[-1]['date'] if xs else None}

    enrich_crypto(data)
    try:fg=fear_greed_series()
    except Exception as e:print(f'FEAR_GREED_FETCH_WARN={e}');fg=prev.get('FEAR_GREED',[])
    sm['FEAR_GREED']=fg;latest['FEAR_GREED']=fg[-1]['value'] if fg else None

    src['KR_EQUITY']='Naver Finance KOSPI/KOSDAQ daily primary; Yahoo Finance fallback'
    src['GLOBAL_EQUITY_SUPPLEMENT']='Yahoo Finance completed US cash-session daily (^RUT/^DJI/^IXIC)'
    src['SILVER']='Yahoo public daily (SI=F)';src['FEAR_GREED']='FearAndGreedGraph public JSON (CNN-derived sentiment reference)'
    data['market_supplement_quality']=quality
    # Preserve the established field/value for downstream acceptance compatibility;
    # the stricter date/source semantics are versioned separately.
    data['equity_enrichment_contract']='KOSPI_KOSDAQ_DAILY_REFERENCE_V1'
    data['equity_session_contract']='KR_TRADING_DATE_NAVER_PRIMARY_YAHOO_FALLBACK_V2'
    data['market_supplement_contract']='US_SUPPLEMENT_MATCH_COMPLETED_CORE_SESSION_V3'
    data['equity_enriched_kst']=datetime.now(KST).isoformat(timespec='seconds')
    OBS.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('OBSERVATORY_MARKET_SUPPLEMENT=PASS','KOSPI=',latest.get('KOSPI'),'KOSDAQ=',latest.get('KOSDAQ'),'RUT=',latest.get('RUSSELL2000'),'DOW=',latest.get('DOW'),'IXIC=',latest.get('NASDAQCOMPOSITE'),'US_SESSION=',us_session,'SILVER=',latest.get('SILVER'),'FEAR_GREED=',latest.get('FEAR_GREED'))

if __name__=='__main__':main()
