#!/usr/bin/env python3
from __future__ import annotations
import csv, io, json, math, urllib.parse, urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from yahoo_bar_date import bar_date

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'market-observatory'/'data';OBS=DATA/'observatory.json';ARCH=DATA/'history-30y.json'
KST=ZoneInfo('Asia/Seoul');ET=ZoneInfo('America/New_York')
UA='Mozilla/5.0 JJOONI-Market-Observatory-History/2.1';YAHOO='https://query1.finance.yahoo.com/v8/finance/chart/'
SYMBOLS={'NASDAQ100':'^NDX','SP500':'^GSPC','VIX':'^VIX','DXY':'DX-Y.NYB','USDKRW':'KRW=X','USDJPY':'JPY=X','JPYKRW':'JPYKRW=X','WTI':'CL=F','BRENT':'BZ=F','NATGAS':'NG=F','GOLD':'GC=F','COPPER':'HG=F','US3M':'^IRX','US5Y':'^FVX','US10Y':'^TNX','US30Y':'^TYX'}

def req(url,timeout=25,accept='*/*'):
    r=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':accept})
    with urllib.request.urlopen(r,timeout=timeout) as x:return x.read()
def get_json(url):return json.loads(req(url,accept='application/json').decode('utf-8'))
def get_text(url):return req(url).decode('utf-8-sig','ignore')
def merge(a,b):
    d={str(x.get('date')):x for x in(a or[]) if x.get('date')};d.update({str(x.get('date')):x for x in(b or[]) if x.get('date')});return[d[k] for k in sorted(d)]
def trim(xs,cutoff):return[x for x in xs if str(x.get('date',''))>=cutoff]

def yahoo_max(symbol):
    qs=urllib.parse.urlencode({'interval':'1d','range':'max','includePrePost':'false','events':'div,splits'});obj=get_json(YAHOO+urllib.parse.quote(symbol,safe='')+'?'+qs);rs=((obj.get('chart')or{}).get('result')or[])
    if not rs:return[]
    b=rs[0];ts=b.get('timestamp')or[];cs=((((b.get('indicators')or{}).get('quote')or[{}])[0]).get('close')or[]);out=[]
    for t,v in zip(ts,cs):
        if v is None:continue
        try:v=float(v)
        except:continue
        if math.isfinite(v):out.append({'date':bar_date(t,b,ET),'value':round(v,8)})
    return merge([],out)
def treasury_year(year):
    url=f'https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/{year}/all?type=daily_treasury_yield_curve&field_tdr_date_value={year}&page&_format=csv';rows=[]
    for r in csv.DictReader(io.StringIO(get_text(url))):
        try:d=datetime.strptime((r.get('Date')or'').strip(),'%m/%d/%Y').date().isoformat()
        except:continue
        vals={}
        for c in['2 Yr','5 Yr','10 Yr','30 Yr']:
            try:vals[c]=float(r.get(c)or'')
            except:vals[c]=None
        rows.append({'date':d,'values':vals})
    return rows
def fred_csv(series_id):
    out=[]
    for r in csv.DictReader(io.StringIO(get_text('https://fred.stlouisfed.org/graph/fredgraph.csv?id='+urllib.parse.quote(series_id)))):
        d=r.get('DATE')or r.get('observation_date')or''
        try:v=float(r.get(series_id))
        except:continue
        if d:out.append({'date':d,'value':round(v,8),'frequency':'monthly','source':'OECD/FRED'})
    return out

def main():
    o=json.loads(OBS.read_text(encoding='utf-8'))
    # Expensive 30Y archive is immutable after its first successful seed.
    if ARCH.exists():
        try:a=json.loads(ARCH.read_text(encoding='utf-8'))
        except:a={}
        if a.get('schema')=='JJOONI_MARKET_HISTORY_30Y_V1' and a.get('target_years')==30:
            o['history_contract']='IMMUTABLE_30Y_BASE_PLUS_RECENT_INCREMENT';o['history_target_years']=30;o['history_base_generated_kst']=a.get('generated_kst');o['history_base_path']='./data/history-30y.json'
            OBS.write_text(json.dumps(o,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            print('MARKET_HISTORY_30Y=REUSE_IMMUTABLE_BASE generated=',a.get('generated_kst'));return
    current=o.get('series')or{};series={};now=datetime.now(KST).date();cutoff=(now-timedelta(days=365*30+10)).isoformat();quality={}
    for k,sym in SYMBOLS.items():
        base=current.get(k,[])
        try:base=merge(base,yahoo_max(sym));quality[k]='BACKFILLED_MAX'
        except Exception as e:quality[k]='BACKFILL_FAILED:'+type(e).__name__
        series[k]=trim(base,cutoff)
    us=[]
    for y in range(now.year-30,now.year+1):
        try:us.extend(treasury_year(y))
        except:pass
    for key,col in [('US2Y','2 Yr'),('US5Y_OFFICIAL','5 Yr'),('US10Y_OFFICIAL','10 Yr'),('US30Y_OFFICIAL','30 Yr')]:
        fresh=[{'date':x['date'],'value':x['values'][col],'source':'US Treasury'} for x in us if x['values'].get(col)is not None];series[key]=trim(merge(current.get(key),fresh),cutoff)
    try:series['KR10Y']=trim(merge(fred_csv('IRLTLT01KRM156N'),current.get('KR10Y')),cutoff);quality['KR10Y_LONG']='OECD_FRED_MONTHLY_PLUS_ECOS_DAILY'
    except Exception as e:quality['KR10Y_LONG']='FAILED:'+type(e).__name__
    for k,v in current.items():series[k]=trim(merge(series.get(k),v),cutoff)
    def derive(a,b,name):
        ma={x['date']:x['value'] for x in series.get(a,[]) if x.get('value')is not None};mb={x['date']:x['value'] for x in series.get(b,[]) if x.get('value')is not None};series[name]=[{'date':d,'value':round(ma[d]-mb[d],8)} for d in sorted(set(ma)&set(mb))]
    derive('US10Y_OFFICIAL','US2Y','US_2S10S');derive('KR10Y','KR3Y','KR_3S10S');derive('JP10Y','JP2Y','JP_2S10S')
    a={'schema':'JJOONI_MARKET_HISTORY_30Y_V1','generated_kst':datetime.now(KST).isoformat(timespec='seconds'),'history_contract':'IMMUTABLE_BASE','target_years':30,'series':series,'quality':quality}
    ARCH.write_text(json.dumps(a,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    o['history_contract']='IMMUTABLE_30Y_BASE_PLUS_RECENT_INCREMENT';o['history_target_years']=30;o['history_base_generated_kst']=a['generated_kst'];o['history_base_path']='./data/history-30y.json';OBS.write_text(json.dumps(o,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('MARKET_HISTORY_30Y=SEEDED cutoff=',cutoff,'US10Y_oldest=',series.get('US10Y_OFFICIAL',[{}])[0].get('date'),'KR10Y_oldest=',series.get('KR10Y',[{}])[0].get('date'))
if __name__=='__main__':main()
