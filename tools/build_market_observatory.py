#!/usr/bin/env python3
from __future__ import annotations
import csv, io, json, math, os, re, urllib.parse, urllib.request
from datetime import datetime, date, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from calendar_actual_contract import merge_observation, retain_calendar, PROVENANCE
from observatory_session import expected_completed_session

ROOT=Path(__file__).resolve().parents[1]
OUT_DIR=ROOT/'market-observatory'/'data'; OUT_DIR.mkdir(parents=True,exist_ok=True)
OBS=OUT_DIR/'observatory.json'; CAL=OUT_DIR/'economic-calendar.json'
KST=ZoneInfo('Asia/Seoul'); ET=ZoneInfo('America/New_York')
UA='Mozilla/5.0 JJOONI-Market-Observatory/1.0'
YAHOO='https://query1.finance.yahoo.com/v8/finance/chart/'

SYMBOLS={
 'NASDAQ100':'^NDX','SP500':'^GSPC','VIX':'^VIX','DXY':'DX-Y.NYB',
 'USDKRW':'KRW=X','USDJPY':'JPY=X','JPYKRW':'JPYKRW=X',
 'WTI':'CL=F','BRENT':'BZ=F','NATGAS':'NG=F',
 'GOLD':'GC=F','COPPER':'HG=F',
 'US3M':'^IRX','US5Y':'^FVX','US10Y':'^TNX','US30Y':'^TYX'
}
KR_ECOS={'KR3Y':'010200000','KR5Y':'010200001','KR10Y':'010210000','KR20Y':'010220000','KR30Y':'010230000'}
US_COMPLETED_SESSION_KEYS=('NASDAQ100','SP500','VIX')
US_REGULAR_CLOSE_GRACE=(16,15)


def req(url,timeout=20,accept='*/*'):
    r=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':accept})
    with urllib.request.urlopen(r,timeout=timeout) as x:return x.read()

def get_text(url,enc='utf-8'):
    b=req(url); 
    for e in (enc,'utf-8-sig','cp932','euc-kr'):
        try:return b.decode(e)
        except Exception:pass
    return b.decode('utf-8','ignore')

def get_json(url):return json.loads(req(url,accept='application/json').decode('utf-8'))

def yahoo_series(symbol,range_='3y'):
    qs=urllib.parse.urlencode({'interval':'1d','range':range_,'includePrePost':'false','events':'div,splits'})
    obj=get_json(YAHOO+urllib.parse.quote(symbol,safe='')+'?'+qs)
    rs=((obj.get('chart') or {}).get('result') or [])
    if not rs:return []
    b=rs[0]; ts=b.get('timestamp') or []; cs=((((b.get('indicators') or {}).get('quote') or [{}])[0]).get('close') or [])
    out=[]
    for t,v in zip(ts,cs):
        if v is None:continue
        try:v=float(v)
        except:continue
        if not math.isfinite(v):continue
        d=datetime.fromtimestamp(int(t),ET).date().isoformat()
        out.append({'date':d,'value':round(v,8)})
    ded={x['date']:x for x in out}; return [ded[k] for k in sorted(ded)]

def completed_us_session_cutoff(now_et=None):
    """Return the latest date that may contain a completed US regular session.

    Yahoo can expose a provisional same-day daily bar before the cash session has
    closed (VIX commonly arrives before the index bars).  A small grace period
    after 16:00 ET keeps provisional values out of EOD/TRI-POD calculations.
    """
    return expected_completed_session(now_et)

def completed_us_bars(rows,now_et=None):
    cutoff=completed_us_session_cutoff(now_et)
    return [x for x in (rows or []) if str(x.get('date') or '')[:10]<=cutoff]

def align_completed_us_market_series(series):
    """Align NDX, S&P 500 and VIX to one common completed trading date."""
    date_sets=[]
    for key in US_COMPLETED_SESSION_KEYS:
        rows=series.get(key) or []
        if not rows:return None
        date_sets.append({str(x.get('date') or '')[:10] for x in rows if x.get('date')})
    common=set.intersection(*date_sets)
    if not common:return None
    aligned=max(common)
    for key in US_COMPLETED_SESSION_KEYS:
        series[key]=[x for x in series[key] if str(x.get('date') or '')[:10]<=aligned]
    return aligned

def load_prev():
    try:return json.loads(OBS.read_text(encoding='utf-8'))
    except:return {}

def treasury_rows(year):
    url=f'https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/{year}/all?type=daily_treasury_yield_curve&field_tdr_date_value={year}&page&_format=csv'
    txt=get_text(url); rows=[]
    for r in csv.DictReader(io.StringIO(txt)):
        raw=r.get('Date') or r.get('DATE') or ''
        try:d=datetime.strptime(raw.strip(),'%m/%d/%Y').date().isoformat()
        except:continue
        vals={}
        for label in ['1 Mo','2 Mo','3 Mo','4 Mo','6 Mo','1 Yr','2 Yr','3 Yr','5 Yr','7 Yr','10 Yr','20 Yr','30 Yr']:
            try:vals[label]=float(r.get(label) or '')
            except:vals[label]=None
        rows.append({'date':d,'values':vals})
    return sorted(rows,key=lambda x:x['date'])

def jgb_rows():
    """Merge MOF archived and current official JGB rates without revising archive rows."""
    urls = (
        'https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/historical/jgbcme_all.csv',
        'https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/jgbcme.csv',
    )
    by_date = {}
    failures = []
    today = datetime.now(KST).date().isoformat()
    for url in urls:
        source = url.rsplit('/', 1)[-1]
        try:
            rows = []
            header = None
            for row in csv.reader(io.StringIO(get_text(url, 'cp932'))):
                if not row:
                    continue
                if header is None and ('Date' in row[0] or '年月日' in row[0]):
                    header = row
                    continue
                if header is None:
                    continue
                raw = row[0].strip()
                date_value = None
                for fmt in ('%Y/%m/%d', '%Y-%m-%d'):
                    try:
                        date_value = datetime.strptime(raw, fmt).date().isoformat()
                        break
                    except ValueError:
                        pass
                if not date_value or date_value > today:
                    continue
                vals = {}
                for i, name in enumerate(header[1:], 1):
                    key = name.strip().replace('year', 'Y').replace('Year', 'Y').replace('years', 'Y')
                    if i >= len(row):
                        continue
                    try:
                        vals[key] = float(row[i])
                    except (ValueError, TypeError):
                        vals[key] = None
                if any(v is not None for v in vals.values()):
                    rows.append({'date': date_value, 'values': vals})
            if not rows:
                raise ValueError('JGB_MOF_NO_VALID_DATED_ROWS')
            # The archived series wins for overlapping dates. Only append
            # genuinely new current observations; never rewrite past yields.
            overlap = sum(1 for item in rows if item['date'] in by_date)
            for item in rows:
                by_date.setdefault(item['date'], item)
            print(f'JGB_MOF_SOURCE=OK file={source} rows={len(rows)} latest={rows[-1]["date"]} archive_preserved={overlap}')
        except Exception as exc:
            failures.append(f'{source}:{type(exc).__name__}')
    if failures:
        print('JGB_MOF_SOURCE=WARN ' + ','.join(failures))
    if not by_date:
        raise RuntimeError('JGB_MOF_NO_OFFICIAL_ROWS')
    return [by_date[day] for day in sorted(by_date)]

def nearest_snapshot(rows,target):
    xs=[x for x in rows if x['date']<=target]
    return xs[-1] if xs else (rows[0] if rows else None)

def curve_payload(rows,tenor_keys,label_map=None):
    if not rows:return {'tenors':[],'snapshots':[]}
    last=date.fromisoformat(rows[-1]['date']); targets=[('현재',last),('1개월 전',last-timedelta(days=30)),('3개월 전',last-timedelta(days=90)),('1년 전',last-timedelta(days=365))]
    snaps=[]
    for label,t in targets:
        s=nearest_snapshot(rows,t.isoformat())
        if not s:continue
        vals=[]
        for k in tenor_keys:vals.append((s.get('values') or {}).get(k))
        snaps.append({'label':label,'date':s['date'],'values':vals})
    return {'tenors':[label_map.get(k,k) if label_map else k for k in tenor_keys],'snapshots':snaps}

def ecos_series(item,start,end,key):
    url=f'https://ecos.bok.or.kr/api/StatisticSearch/{key}/json/kr/1/1000/817Y002/D/{start}/{end}/{item}'
    obj=get_json(url); rows=((obj.get('StatisticSearch') or {}).get('row') or [])
    out=[]
    for r in rows:
        try:v=float(r['DATA_VALUE'])
        except:continue
        t=str(r.get('TIME') or '');
        if len(t)==8:t=f'{t[:4]}-{t[4:6]}-{t[6:8]}'
        out.append({'date':t,'value':v})
    return sorted(out,key=lambda x:x['date'])

def series_map():
    prev=(load_prev().get('series') or {}); out={}
    for k,s in SYMBOLS.items():
        try:
            rows=yahoo_series(s,'3y')
            out[k]=completed_us_bars(rows) if k in US_COMPLETED_SESSION_KEYS else rows
        except Exception:out[k]=prev.get(k,[])
    key=os.getenv('BOK_ECOS_API_KEY','sample'); end=datetime.now(KST).strftime('%Y%m%d'); start=(datetime.now(KST)-timedelta(days=1100)).strftime('%Y%m%d')
    for k,item in KR_ECOS.items():
        try:out[k]=ecos_series(item,start,end,key)
        except Exception:out[k]=prev.get(k,[])
    # derived spreads
    def derive(a,b,name):
        ma={x['date']:x['value'] for x in out.get(a,[])}; mb={x['date']:x['value'] for x in out.get(b,[])}
        out[name]=[{'date':d,'value':round(ma[d]-mb[d],8)} for d in sorted(set(ma)&set(mb))]
    # Yahoo does not expose a stable 2Y yield symbol; US2Y is injected from Treasury below.
    derive('KR10Y','KR3Y','KR_3S10S')
    align_completed_us_market_series(out)
    return out

def add_official_yields(series):
    now=datetime.now(KST).date(); us=[]
    for y in (now.year-3,now.year-2,now.year-1,now.year):
        try:us.extend(treasury_rows(y))
        except:pass
    us=sorted({x['date']:x for x in us}.values(),key=lambda x:x['date'])
    for key,col in [('US3M','3 Mo'),('US2Y','2 Yr'),('US5Y_OFFICIAL','5 Yr'),('US10Y_OFFICIAL','10 Yr'),('US30Y_OFFICIAL','30 Yr')]:
        series[key]=[{'date':x['date'],'value':x['values'].get(col)} for x in us if x['values'].get(col) is not None]
    if series.get('US2Y') and series.get('US10Y_OFFICIAL'):
        a={x['date']:x['value'] for x in series['US10Y_OFFICIAL']};b={x['date']:x['value'] for x in series['US2Y']};series['US_2S10S']=[{'date':d,'value':round(a[d]-b[d],8)} for d in sorted(set(a)&set(b))]
    jp=[]
    try:jp=jgb_rows()
    except:pass
    # flexible header matching
    def find_key(sample,cands):
        ks=list((sample.get('values') or {}).keys()) if sample else []
        for c in cands:
            for k in ks:
                if c.lower().replace(' ','') in k.lower().replace(' ',''):return k
        return None
    if jp:
        k2=find_key(jp[-1],['2Y','2-year','2 years']);k5=find_key(jp[-1],['5Y','5-year','5 years']);k10=find_key(jp[-1],['10Y','10-year','10 years']);k30=find_key(jp[-1],['30Y','30-year','30 years'])
        previous_jp = (load_prev().get('series') or {})
        def append_jp(name, fresh):
            # Existing published observations are immutable in this change.
            # A changed official overlap must be reviewed as a separate revision.
            existing = {x['date']: x for x in (previous_jp.get(name) or []) if x.get('date')}
            conflicts = sum(1 for x in fresh if x['date'] in existing and existing[x['date']].get('value') != x['value'])
            for x in fresh:
                existing.setdefault(x['date'], x)
            series[name] = [existing[d] for d in sorted(existing)]
            if conflicts:
                print(f'JGB_MOF_EXISTING_PRESERVED={name} conflicts={conflicts}')
        for name,k in [('JP2Y',k2),('JP5Y',k5),('JP10Y',k10),('JP30Y',k30)]:
            if k:
                append_jp(name, [{'date':x['date'],'value':x['values'].get(k)} for x in jp if x['values'].get(k) is not None])
        if k2 and k10:
            a={x['date']:x['value'] for x in series['JP10Y']};b={x['date']:x['value'] for x in series['JP2Y']}
            append_jp('JP_2S10S', [{'date':d,'value':round(a[d]-b[d],8)} for d in sorted(set(a)&set(b))])
    return us,jp

def tripod_history(series):
    from tripod_rules import regime_for, target_for
    from statistics import fmean
    ndx=series.get('NASDAQ100',[]);vix=series.get('VIX',[]); vm={x['date']:x['value'] for x in vix}; vals=[x['value'] for x in ndx]; out=[];state=None; last_target=None;log=[]
    for i,x in enumerate(ndx):
        if i<249:continue
        ma=fmean(vals[i-249:i+1]); px=x['value'];state=regime_for(px,ma,state)
        # NDX regime evolves even if a VIX observation is absent that day.
        # Missing VIX suppresses that day's signal, not future regime history.
        if x['date'] not in vm:continue
        vx=[p['value'] for p in vix if p['date']<=x['date']][-10:]
        if len(vx)<10:continue
        v10=fmean(vx); high=max(vals[max(0,i-251):i+1]);dd=(px/high-1)*100
        target=target_for(state,v10,dd)
        out.append({'date':x['date'],'ndx':px,'ma250':ma,'vix':vm[x['date']],'vix10':v10,'drawdown_52w_pct':dd,'regime':state,'target':target})
        if target!=last_target:log.append({'date':x['date'],'regime':state,'target':target,'reason':'regime/vix10/drawdown 조건 변경'});last_target=target
    return out,log

# ---- Calendar ----
def add_event(events,dt,title,country,category,importance=2,source='',ref='',**extra):
    key=(dt,title,country)
    if any((e['datetime_kst'],e['title'],e['country'])==key for e in events):return
    payload={
        'datetime_kst':dt,'title':title,'country':country,'category':category,'importance':importance,
        'source':source,'reference_period':ref,
        'previous':None,'consensus':None,'actual':None,'te_forecast':None,'surprise':None,
        'market_data_source':None,'market_metrics':[],
    }
    payload.update(extra)
    events.append(payload)

def parse_ics_dt(v):
    v=v.strip();
    for f in ('%Y%m%dT%H%M%SZ','%Y%m%dT%H%M%S','%Y%m%d'):
        try:
            d=datetime.strptime(v,f)
            if f.endswith('Z'):d=d.replace(tzinfo=ZoneInfo('UTC')).astimezone(KST)
            elif 'T' in v:d=d.replace(tzinfo=ET).astimezone(KST)
            else:d=d.replace(tzinfo=KST)
            return d.isoformat(timespec='minutes')
        except:pass
    return ''

def bls_events(events):
    try:txt=get_text('https://www.bls.gov/schedule/news_release/bls.ics')
    except:return
    # RFC 5545 folded lines can otherwise lose the reference period.
    blocks=re.sub(r'\n[ \t]', '', txt.replace('\r','')).split('BEGIN:VEVENT')
    allow=['Consumer Price Index','Employment Situation','Producer Price Index','Job Openings and Labor Turnover','Employment Cost Index','Productivity and Costs','U.S. Import and Export Price Indexes']
    for b in blocks[1:]:
        sm=re.search(r'\nSUMMARY:(.+)',b);dm=re.search(r'\nDTSTART[^:]*:(.+)',b)
        if not sm or not dm:continue
        title=sm.group(1).strip().replace('\\,',',');
        if not any(x.lower() in title.lower() for x in allow):continue
        dt=parse_ics_dt(dm.group(1)); imp=3 if any(x in title for x in ['Consumer Price Index','Employment Situation']) else 2
        description=re.search(r'\nDESCRIPTION:(.+)',b)
        ref=description.group(1).strip().replace('\\n',' ') if description else ''
        add_event(events,dt,title,'US','물가/고용',imp,'BLS',ref)

def fixed_policy_events(events):
    # 2026 official calendars; yearly source refresh is explicit in metadata.
    for md in ['01-28','03-18','04-29','06-17','07-29','09-16','10-28','12-09']:
        d='2026-'+md+'T15:00+09:00';add_event(events,d,'FOMC 정책결정','US','중앙은행',3,'Federal Reserve')
    for md in ['01-15','02-26','04-10','05-28','07-16','08-27','10-22','11-26']:
        d='2026-'+md+'T10:00+09:00';add_event(events,d,'한국은행 통화정책방향 결정회의','KR','중앙은행',3,'BOK')

def korea_core_events(events):
    core=[
      ('2026-09-02T08:00+09:00','2026년 8월 소비자물가동향','물가',3),('2026-09-09T08:00+09:00','2026년 8월 고용동향','고용',2),('2026-09-30T08:00+09:00','2026년 8월 산업활동동향','경기',2),
      ('2026-10-02T08:00+09:00','2026년 9월 소비자물가동향','물가',3),('2026-10-16T08:00+09:00','2026년 9월 고용동향','고용',2),('2026-10-30T08:00+09:00','2026년 9월 산업활동동향','경기',2),
      ('2026-11-03T08:00+09:00','2026년 10월 소비자물가동향','물가',3),('2026-11-11T08:00+09:00','2026년 10월 고용동향','고용',2),('2026-11-30T08:00+09:00','2026년 10월 산업활동동향','경기',2),
      ('2026-12-02T08:00+09:00','2026년 11월 소비자물가동향','물가',3),('2026-12-16T08:00+09:00','2026년 11월 고용동향','고용',2),('2026-12-30T08:00+09:00','2026년 11월 산업활동동향','경기',2),('2026-12-31T08:00+09:00','2026년 12월 및 연간 소비자물가동향','물가',3)]
    for dt,t,c,i in core:add_event(events,dt,t,'KR',c,i,'KOSTAT')
    bok=[('2026-09-15T06:00+09:00','2026년 8월 수출입물가지수 및 무역지수(잠정)','물가/무역',2),('2026-09-18T06:00+09:00','2026년 8월 생산자물가지수(잠정)','물가',2),('2026-09-23T06:00+09:00','2026년 9월 소비자동향조사 결과','심리',1),('2026-09-29T06:00+09:00','2026년 9월 기업경기조사 및 ESI','심리',1),('2026-10-27T08:00+09:00','2026년 3/4분기 실질 GDP(속보)','GDP',3)]
    for dt,t,c,i in bok:add_event(events,dt,t,'KR',c,i,'BOK')

def bea_events(events):
    # resilient extraction from current schedule page; if layout changes, fixed policy/KR/BLS still publish.
    try:txt=re.sub('<[^>]+>',' ',get_text('https://www.bea.gov/news/schedule'));txt=re.sub(r'\s+',' ',txt)
    except:return
    months='January|February|March|April|May|June|July|August|September|October|November|December'
    for m in re.finditer(rf'({months})\s+(\d{{1,2}})\s+8:30 AM\s+(.{{0,180}}?)(?=({months})\s+\d{{1,2}}\s+|To Be Announced|$)',txt):
        mon,day,title=m.group(1),int(m.group(2)),m.group(3).strip();title=re.sub(r'^N\s*ews\s*','',title,flags=re.I)
        if not any(x in title for x in ['GDP','Personal Income and Outlays','International Trade']):continue
        try:d=datetime.strptime(f'2026 {mon} {day} 08:30','%Y %B %d %H:%M').replace(tzinfo=ET).astimezone(KST)
        except:continue
        imp=3 if ('GDP' in title or 'Personal Income and Outlays' in title) else 2
        add_event(events,d.isoformat(timespec='minutes'),title,'US','GDP/PCE/무역',imp,'BEA')

def _observed_fixed_holiday(day):
    if day.weekday()==5:return day-timedelta(days=1)
    if day.weekday()==6:return day+timedelta(days=1)
    return day

def _nth_weekday(year,month,weekday,n):
    d=date(year,month,1)
    d+=timedelta(days=(weekday-d.weekday())%7+7*(n-1))
    return d

def _us_schedule_holidays(year):
    return {
        _observed_fixed_holiday(date(year,1,1)),
        _observed_fixed_holiday(date(year,7,4)),
        _nth_weekday(year,9,0,1),
        _nth_weekday(year,11,3,4),
        _observed_fixed_holiday(date(year,12,25)),
    }

def _nth_us_working_day(year,month,n):
    holidays=_us_schedule_holidays(year)
    d=date(year,month,1);seen=0
    while True:
        if d.weekday()<5 and d not in holidays:
            seen+=1
            if seen==n:return d
        d+=timedelta(days=1)

def _shift_month(year,month,offset):
    idx=year*12+(month-1)+offset
    return idx//12,idx%12+1

def us_claims_events(events,today=None,horizon_days=180):
    """Seed the recurring DOL weekly Initial Jobless Claims release schedule."""
    today=today or datetime.now(KST).date()
    start=today-timedelta(days=35);end=today+timedelta(days=horizon_days)
    d=start+timedelta(days=(3-start.weekday())%7)
    while d<=end:
        release=d
        if d in _us_schedule_holidays(d.year):
            release=d-timedelta(days=1)
        dt=datetime(release.year,release.month,release.day,8,30,tzinfo=ET).astimezone(KST)
        add_event(
            events,dt.isoformat(timespec='minutes'),'U.S. Initial Jobless Claims','US','고용',2,
            'U.S. Department of Labor','weekly',
            schedule_source_url='https://www.dol.gov/ui/data.pdf',
            schedule_rule='WEEKLY_THURSDAY_0830_ET_HOLIDAY_ADJUSTED',
            actual_watch=True,
        )
        d+=timedelta(days=7)

def spglobal_pmi_events(events,today=None,months_ahead=6):
    """Seed S&P Global final U.S. PMI releases from its published working-day rule."""
    today=today or datetime.now(KST).date()
    source_url='https://pmi.spglobal.com/Public/Release/ReleaseDates?language=en'
    for offset in range(-1,months_ahead+1):
        year,month=_shift_month(today.year,today.month,offset)
        survey_end=date(year,month,1)-timedelta(days=1)
        ref=survey_end.strftime('%B %Y final')
        for workday,title,importance,rule in [
            (1,'S&P Global US Manufacturing PMI',2,'FIRST_WORKING_DAY_0945_ET'),
            (3,'S&P Global US Services & Composite PMI',3,'THIRD_WORKING_DAY_0945_ET'),
        ]:
            release=_nth_us_working_day(year,month,workday)
            dt=datetime(release.year,release.month,release.day,9,45,tzinfo=ET).astimezone(KST)
            add_event(
                events,dt.isoformat(timespec='minutes'),title,'US','경기/PMI',importance,
                'S&P Global Market Intelligence',ref,
                schedule_source_url=source_url,
                schedule_rule=rule,
                actual_watch=True,
            )

def calendar_build():
    ev=[];bls_events(ev);fixed_policy_events(ev);korea_core_events(ev);bea_events(ev);us_claims_events(ev);spglobal_pmi_events(ev)
    ev.sort(key=lambda x:x['datetime_kst'])
    return {'schema':'JJOONI_ECONOMIC_CALENDAR_V1','generated_kst':datetime.now(KST).isoformat(timespec='seconds'),'timezone':'Asia/Seoul','events':ev,'sources':['Federal Reserve','BLS','BEA','BOK','KOSTAT','U.S. Department of Labor','S&P Global Market Intelligence'],'schedule_contract':'US_RECURRING_CLAIMS_SP_GLOBAL_PMI_V1','schedule_sources':{'US_JOBLESS_CLAIMS':'https://www.dol.gov/ui/data.pdf','SP_GLOBAL_PMI':'https://pmi.spglobal.com/Public/Release/ReleaseDates?language=en','US_EMPLOYMENT_SITUATION':'https://www.bls.gov/schedule/news_release/empsit.htm'},'note':'All displayed times are KST. Official schedules may change; builder refreshes automatically.'}

def main():
    previous_observations=json.loads(OBS.read_text(encoding='utf-8')) if OBS.exists() else {}
    series=series_map();us,jp=add_official_yields(series)
    th,log=tripod_history(series)
    latest={k:(v[-1]['value'] if v else None) for k,v in series.items()}
    if latest.get('KR10Y') is not None and latest.get('US10Y_OFFICIAL') is not None:latest['KR_US_10Y']=latest['KR10Y']-latest['US10Y_OFFICIAL']
    public={}
    try:public=json.loads((ROOT/'public-market-daily.json').read_text(encoding='utf-8'))
    except:pass
    sig=public.get('tripod_signal') or (th[-1] if th else {})
    us_session_dates={k:(series.get(k) or [{}])[-1].get('date') for k in US_COMPLETED_SESSION_KEYS}
    us_completed_session_date=next(iter(set(us_session_dates.values()))) if len(set(us_session_dates.values()))==1 else None
    out={'schema':'JJOONI_MARKET_OBSERVATORY_V1','generated_kst':datetime.now(KST).isoformat(timespec='seconds'),'read_only':True,'contains_account_data':False,'us_market_session_contract':'COMMON_LAST_COMPLETED_US_SESSION_V1','us_completed_session_date':us_completed_session_date,'latest':latest,'series':series,'curves':{'US_CURVE':curve_payload(us,['3 Mo','2 Yr','5 Yr','10 Yr','30 Yr']),'JP_CURVE':curve_payload(jp,['2Y','5Y','10Y','20Y','30Y'])},'tripod_latest':sig,'tripod_history':th[-800:],'signal_log':log[-100:],'sources':{'US_TREASURY':'US Treasury','JP_JGB':'Japan MOF','KR_RATES':'BOK ECOS','MARKETS':'Yahoo public daily','TRIPOD':'derived completed-session daily'}}
    from add_observatory_equities import retain_crypto_observations
    retain_crypto_observations(out,previous_observations)
    OBS.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    old_calendar=json.loads(CAL.read_text(encoding='utf-8')) if CAL.exists() else {'events':[]}
    calendar=retain_calendar(calendar_build(),old_calendar)
    CAL.write_text(json.dumps(calendar,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('MARKET_OBSERVATORY_BUILD=PASS');print('generated_kst='+out['generated_kst']);print('series='+str(len(series)));print('calendar_events='+str(len(json.loads(CAL.read_text())['events'])))
if __name__=='__main__':main()

