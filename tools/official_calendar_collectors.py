"""Date-bound official adapters. Failed requests are observable, never empty success."""
import html
import json
import os
import time
import io
import re
import urllib.request
import urllib.parse
from datetime import timedelta
from html.parser import HTMLParser
from calendar_actual_contract import KST, release_time, merge_observation, clean, actual_expected

def official_user_agent(contact=None):
    """Identify this collector honestly; agencies such as BLS reject anonymous
    browser-like scripted user agents. The contact comes from the repository
    secret OFFICIAL_SOURCE_CONTACT and is never hard-coded here."""
    contact = (os.environ.get('OFFICIAL_SOURCE_CONTACT') if contact is None else contact) or ''
    contact = ' '.join(contact.split())[:120]
    base = 'jjooni-control-tower/2.0 (+https://github.com/mauveplace/jjooni-control-tower'
    return base + (f'; {contact})' if contact else ')')

UA = official_user_agent()

class Links(HTMLParser):
    def __init__(self, raw):
        super().__init__(); self.rows=[]; self.href=None; self.label=''; self.feed(raw)
    def handle_starttag(self, tag, attrs):
        if tag=='a': self.href=dict(attrs).get('href'); self.label=''
    def handle_data(self, data):
        if self.href: self.label+=data
    def handle_endtag(self, tag):
        if tag=='a' and self.href: self.rows.append((self.href,self.label.strip())); self.href=None

def raw_fetch(url):
    req=urllib.request.Request(url,headers={'User-Agent':UA})
    with urllib.request.urlopen(req,timeout=12) as r:
        raw=r.read()
    return raw

def text_fetch(url):
    raw=raw_fetch(url)
    if raw.startswith(b'%PDF'):
        from pypdf import PdfReader
        text=' '.join(p.extract_text() or '' for p in PdfReader(io.BytesIO(raw)).pages)
    else:
        text=raw.decode('utf-8',errors='replace')
        text=re.sub(r'<(script|style)\b[^>]*>.*?</\1>',' ',text,flags=re.I|re.S)
        text=html.unescape(re.sub('<[^>]+>',' ',text))
    return re.sub(r'\s+',' ',text).strip()

def metric(key,label,actual,**kw):
    return dict(key=key,label=label,actual=actual,**kw)

def parse_claims(text,dt):
    # data.pdf rolls weekly: require the embargo/release date, not only a number.
    stamp=rf'{dt:%B}\s+{dt.day}\s*,?\s*{dt.year}'
    if not re.search(stamp,text[:1000],re.I): raise ValueError('RELEASE_DATE_MISMATCH')
    m=re.search(r'advance figure for seasonally adjusted initial claims was\s+([\d,]+)',text,re.I)
    if not m: raise ValueError('INITIAL_CLAIMS_PARSE_MISS')
    val=f'{int(m[1].replace(",",""))/1000:g}K'
    p=re.search(r"previous week.s (?:unrevised|revised) level of\s+([\d,]+)",text,re.I)
    return [metric('initial_claims','Initial Jobless Claims',val,**({'previous':f'{int(p[1].replace(",",""))/1000:g}K'} if p else {}))]

def parse_boj(text,dt):
    # PDF glyph spacing can split the year ("202 6"). Normalize only
    # whitespace; keep the complete release date bound to this event.
    header=re.sub(r'\s+','',text[:500])
    if not re.search(rf'{dt:%B}{dt.day},?{dt.year}(?!\d)',header,re.I): raise ValueError('RELEASE_DATE_MISMATCH')
    m=re.search(r'uncollateralized overnight call rate.{0,100}?around\s+([\d.]+)\s*percent',text,re.I)
    if not m: raise ValueError('BOJ_RATE_PARSE_MISS')
    return [metric('boj_policy_rate','BOJ overnight call rate target',f'{float(m[1]):.2f}%')]

def parse_boe(text,dt):
    if not re.search(rf'Published on\s+{dt.day}\s+{dt:%B}\s+{dt.year}',text,re.I): raise ValueError('RELEASE_DATE_MISMATCH')
    # Read decision paragraph, never the current-rate navigation badge.
    m=re.search(r'MPC\).*?voted.{0,100}?(maintain|increase|reduce).*?Bank Rate.*?(?:at|to)\s+([\d.]+)%',text,re.I)
    if not m: raise ValueError('BOE_RATE_PARSE_MISS')
    out=[metric('boe_bank_rate','Bank of England Bank Rate',f'{float(m[2]):.2f}%')]
    para=text[m.start():m.start()+650]
    majority=re.search(r'majority of\s+(\d+)\s*[–−-]\s*(\d+)',para)
    nums={'one':1,'two':2,'three':3,'four':4,'five':5,'six':6,'seven':7,'eight':8,'nine':9}
    votes={'increase':0,'reduce':0,'maintain':0}
    if majority:
        votes[m[1].lower()]=int(majority[1])
        others=list(re.finditer(r'(One|Two|Three|Four|Five|Six|Seven|Eight|Nine|\d+) members? (?:preferred|voted) to (increase|reduce|maintain)',para,re.I))
        for v in others: votes[v[2].lower()]=nums.get(v[1].lower(),int(v[1]) if v[1].isdigit() else 0)
        if sum(votes.values())==9:
            out.append(metric('boe_vote_split','MPC 금리투표 (인상-인하-동결)',f'{votes["increase"]}-{votes["reduce"]}-{votes["maintain"]}'))
    elif re.search(r'voted unanimously',para,re.I):
        votes[m[1].lower()]=9
        out.append(metric('boe_vote_split','MPC 금리투표 (인상-인하-동결)',f'{votes["increase"]}-{votes["reduce"]}-{votes["maintain"]}'))
    return out

def parse_bok(text,year,month):
    if not re.search(rf'{year}\s*년\s*{month}\s*월.*?생산자물가',text,re.S): raise ValueError('REFERENCE_PERIOD_MISMATCH')
    # Match total headline; sector-level inflation must not become the headline.
    part=re.split(rf'{year}\s*년\s*{month}\s*월\s*생산자물가지수',text,maxsplit=1)[-1][:1200]
    out=[]
    for key,label,pat in [('kr_ppi_mom','PPI MoM',r'전월\s*대비'),('kr_ppi_yoy','PPI YoY',r'전년\s*동월\s*대비')]:
        m=re.search(pat+r'\s*([\d.]+)\s*%\s*(상승|하락)',part)
        if m: out.append(metric(key,label,('-' if m[2]=='하락' else '')+m[1]+'%'))
        elif re.search(pat+r'\s*보합',part): out.append(metric(key,label,'0.0%'))
    idx=re.search(r'(?:생산자물가지수.{0,30}?\(2020\s*=\s*100\).{0,20}?|지수는\s*)(1\d{2}\.\d+)\b',part)
    if idx: out.append(metric('kr_ppi_index','PPI index (2020=100)',idx[1]))
    if not out: raise ValueError('BOK_HEADLINE_PARSE_MISS')
    return out


# Exact official release verified against the BOK statistics press release board.
# This mapping is deliberately limited to the confirmed Q3 2026 preliminary vintage.
BOK_GDP_RELEASES = {
    (2026, 3): ('2026-10-27',
        'https://www.bok.or.kr/portal/bbs/B0000501/view.do?menuNo=201264&nttId=11065944')
}

def parse_bok_gdp(text, year, quarter, publication_date):
    compact = re.sub(r'\s+', '', text)
    if not re.search(rf'{year}년{quarter}/4분기실질국내총생산\(속보\)', compact):
        raise ValueError('BOK_GDP_REFERENCE_PERIOD_MISMATCH')
    if '등록일' + publication_date.replace('-', '.') not in compact:
        raise ValueError('BOK_GDP_PUBLICATION_DATE_MISMATCH')
    # The first GDP headline is authoritative; GDI and YoY are different measures.
    m = re.search(
        r'◈실질국내총생산\(GDP\)은전기대비([0-9]+(?:\.[0-9]+)?)%'
        r'(성장|증가|감소),?전년동기대비([0-9]+(?:\.[0-9]+)?)%(성장|증가|감소)',
        compact)
    if not m:
        raise ValueError('BOK_GDP_QOQ_HEADLINE_PARSE_MISS')
    qoq = ('-' if m[2] == '감소' else '') + m[1]
    return [metric('gdp_qoq', 'Real GDP QoQ (preliminary)', qoq + '%')]

def collect_bok_gdp(e, checks):
    title = e.get('title', '')
    match = re.fullmatch(r'(\d{4})년\s*([1-4])/4분기\s*실질\s*GDP\(속보\)', title)
    if not match:
        checks.append(dict(adapter='BOK_GDP', title=title, result='EVENT_IDENTITY_MISMATCH'))
        return None
    year, quarter = map(int, match.groups())
    official = BOK_GDP_RELEASES.get((year, quarter))
    if not official:
        checks.append(dict(adapter='BOK_GDP', title=title, result='OFFICIAL_RELEASE_NOT_VERIFIED_FOR_PERIOD'))
        return None
    date, url = official
    dt = release_time(e)
    if not dt or dt.date().isoformat() != date:
        checks.append(dict(adapter='BOK_GDP', title=title, result='RELEASE_DATE_MISMATCH'))
        return None
    # The 2026-Q3 seed carried a Q4 slug with no actual/previous/consensus
    # observations. Repair only that exact empty, one-metric identity, with
    # independently verified period/date. All other mismatches fail closed.
    ref = e.get('history_ref', '')
    expected_ref = f'KR::{year}년-{quarter}분기-실질-gdp'
    wrong_q4_ref = 'KR::2026년-4분기-실질-gdp'
    if ref == wrong_q4_ref and (year, quarter) == (2026, 3):
        metrics = e.get('market_metrics') or []
        metric_row = metrics[0] if len(metrics) == 1 else {}
        all_empty = all(clean(e.get(k)) is None for k in ('previous', 'consensus', 'actual'))
        metric_empty = all(clean(metric_row.get(k)) is None for k in ('previous', 'consensus', 'actual'))
        if (all_empty and metric_empty and metric_row.get('key') == 'gdp_qoq'
                and metric_row.get('history_ref') == wrong_q4_ref + '::gdp_qoq'):
            e['history_ref'] = expected_ref
            metric_row['history_ref'] = expected_ref + '::gdp_qoq'
            checks.append(dict(adapter='BOK_GDP', title=title, url=url,
                               result='EMPTY_HISTORY_REF_IDENTITY_CORRECTED',
                               from_ref=wrong_q4_ref, to_ref=expected_ref))
            ref = expected_ref
    if ref and ref != expected_ref:
        checks.append(dict(adapter='BOK_GDP', title=title, url=url,
                           result='HISTORY_REF_QUARTER_MISMATCH', history_ref=ref))
        return None
    try:
        rows = parse_bok_gdp(text_fetch(url), year, quarter, date)
        checks.append(dict(adapter='BOK_GDP', title=title, url=url, result='PARSED'))
        return rows, url
    except Exception as exc:
        checks.append(dict(adapter='BOK_GDP', title=title, url=url,
                           result=type(exc).__name__, error=str(exc)[:200]))
        return None

def parse_ccsi(text,year,month):
    compact=re.sub(r'\s+','',text)
    if not re.search(rf'{year}년{month}월소비자동향조사',compact):
        raise ValueError('REFERENCE_PERIOD_MISMATCH')
    m=re.search(rf'{month}월(?:중)?소비자심리지수(?:\(CCSI[^)]*\))?는([0-9]+(?:\.[0-9]+)?)',compact)
    if not m: raise ValueError('BOK_CCSI_HEADLINE_PARSE_MISS')
    row=metric('kr_ccsi','소비자심리지수 (CCSI)',m[1])
    delta=re.search(r'전월대비([0-9.]+)(?:p|포인트)(상승|하락)',compact[m.end():m.end()+100])
    if delta:
        change=float(delta[1]) * (1 if delta[2]=='상승' else -1)
        row['previous']=f'{float(m[1])-change:.1f}'
    return [row]


def collect_ccsi(e,checks):
    period=re.search(r'(\d{4})년\s*(\d+)월',e['title'])
    year,month=map(int,period.groups())
    query=f'{year}년 {month}월 소비자동향조사'
    index='https://www.bok.or.kr/portal/bbs/P0000559/list.do?menuNo=200690&searchCnd=1&searchKwd='+urllib.parse.quote(query)
    try:
        raw=raw_fetch(index).decode('utf-8',errors='replace')
        link=next((u for u,t in Links(raw).rows if re.search(rf'{year}년\s*{month}월\s*소비자동향조사',t)),None)
        if not link: raise ValueError('BOK_CCSI_RELEASE_NOT_FOUND')
        page=urllib.parse.urljoin(index,html.unescape(link))
        raw=raw_fetch(page).decode('utf-8',errors='replace')
        urls=[urllib.parse.urljoin(page,html.unescape(u)) for u,t in Links(raw).rows if '.pdf' in t.lower()]
        for url in urls+[page]:
            try:
                rows=parse_ccsi(text_fetch(url),year,month)
                checks.append(dict(adapter='BOK_CCSI',title=e['title'],url=url,result='PARSED'))
                return rows,url
            except Exception as exc:
                checks.append(dict(adapter='BOK_CCSI',title=e['title'],url=url,result=type(exc).__name__,error=str(exc)[:200]))
    except Exception as exc:
        checks.append(dict(adapter='BOK_CCSI',title=e['title'],url=index,result=type(exc).__name__,error=str(exc)[:200]))
    # Official ECOS series is a separate fallback when the release board is
    # unavailable. Accept only this exact reference period and CCSI identity.
    period=f'{year}{month:02d}'
    api=f'https://ecos.bok.or.kr/api/StatisticSearch/sample/json/kr/1/10/511Y002/M/{period}/{period}/FME'
    try:
        obj=json.loads(raw_fetch(api))
        rows=(obj.get('StatisticSearch') or {}).get('row',[])
        row=next((r for r in rows if r.get('TIME')==period and r.get('ITEM_CODE1')=='FME'
                  and re.fullmatch(r'소비자심리지수(?:\(CCSI\))?',re.sub(r'\s+','',r.get('ITEM_NAME1','')))),None)
        if row is None: raise ValueError('BOK_CCSI_ECOS_IDENTITY_OR_PERIOD_MISSING')
        value=float(row['DATA_VALUE'])
        if not 0<value<300: raise ValueError('BOK_CCSI_ECOS_VALUE_INVALID')
        checks.append(dict(adapter='BOK_CCSI',title=e['title'],url=api,result='PARSED'))
        return [metric('kr_ccsi','소비자심리지수 (CCSI)',f'{value:g}')],api
    except Exception as exc:
        checks.append(dict(adapter='BOK_CCSI',title=e['title'],url=api,result=type(exc).__name__,error=str(exc)[:200]))
    return None

def parse_kr_employment(text, year, month):
    compact=re.sub(r'\s+', '', text)
    heading=rf'\[{year}년0?{month}월고용동향\]'
    match=re.search(heading,compact)
    if not match: raise ValueError('KR_EMPLOYMENT_REFERENCE_PERIOD_MISMATCH')
    body=compact[match.end():match.end()+1800]
    definitions=(
        ('kr_unemployment_sa','실업률 (계절조정)',r'계절조정실업률은([\d.]+)%','%'),
        ('kr_unemployment','실업률 (비계절조정)',r'(?:▣|○)실업률은([\d.]+)%','%'),
        ('kr_employment_rate','15~64세 고용률 (OECD)',r'15[~～∼]64세고용률\(OECD비교기준\)은([\d.]+)%','%'),
        ('kr_employed','취업자 수 (천명)',r'취업자는([\d,]+)천명',''),
    )
    rows=[]
    for key,label,pattern,suffix in definitions:
        m=re.search(pattern,body)
        if not m: raise ValueError('KR_EMPLOYMENT_HEADLINE_MISSING:'+key)
        value=float(m[1].replace(',',''))
        if not 0<=value<=(100 if suffix else 100000): raise ValueError('KR_EMPLOYMENT_VALUE_INVALID')
        rows.append(metric(key,label,f'{value:g}'+suffix,
                           reference_period=f'{year}-{month:02d}',value_vintage='AS_RELEASED'))
    return rows


def collect_kr_employment(e,checks):
    period=re.search(r'(20\d{2})년\s*(\d{1,2})월\s*고용동향',e['title'])
    if not period: raise ValueError('KR_EMPLOYMENT_TITLE_PERIOD_MISSING')
    year,month=map(int,period.groups())
    index='https://mods.go.kr/board.es?mid=a10301030200&bid=210&act=list'
    try:
        page=e.get('official_release_url')
        if not page:
            raw=raw_fetch(index).decode('utf-8',errors='replace')
            link=next((u for u,t in Links(raw).rows if re.fullmatch(rf'{year}년\s*0?{month}월\s*고용동향',t.strip())),None)
            if not link: raise ValueError('KR_EMPLOYMENT_RELEASE_NOT_FOUND')
            page=urllib.parse.urljoin(index,html.unescape(link))
        parsed=urllib.parse.urlparse(page)
        if parsed.scheme!='https' or parsed.hostname not in ('mods.go.kr','www.mods.go.kr','kostat.go.kr','www.kostat.go.kr'):
            raise ValueError('KR_EMPLOYMENT_OFFICIAL_HOST_REQUIRED')
        rows=parse_kr_employment(text_fetch(page),year,month)
        e['official_release_url']=page
        checks.append(dict(adapter='KOSTAT_EMPLOYMENT',title=e['title'],url=page,result='PARSED'))
        return rows,page
    except Exception as exc:
        checks.append(dict(adapter='KOSTAT_EMPLOYMENT',title=e['title'],url=locals().get('page') or index,result=type(exc).__name__,error=str(exc)[:200]))
        return None


def adapter_id(e):
    t=e.get('title',''); c=e.get('country')
    from official_bls_actuals import DEFS
    if c=='US' and t in DEFS: return 'BLS_'+DEFS[t][0]
    if c=='US' and 'Initial Jobless Claims' in t: return 'DOL'
    if c=='US' and re.match(r'^Personal Income and Outlays,\s+[A-Za-z]+\s+\d{4}$',t): return 'BEA_PIO'
    if c=='KR' and t=='한국은행 통화정책방향 결정회의': return 'BOK_RATE'
    if c=='KR' and re.fullmatch(r'\d{4}년\s*[1-4]/4분기\s*실질\s*GDP\(속보\)',t): return 'BOK_GDP'
    if c=='KR' and '생산자물가' in t: return 'BOK'
    if c=='KR' and '소비자동향조사' in t: return 'BOK_CCSI'
    if c=='KR' and re.search(r'고용동향',t): return 'KOSTAT_EMPLOYMENT'
    if c=='JP' and ('BOJ' in t or 'Bank of Japan' in t): return 'BOJ'
    if c=='GB' and 'Bank of England' in t: return 'BOE'
    return None

REGISTRY={'DOL':('initial_claims',),'BOK':('kr_ppi_mom','kr_ppi_yoy'),'BOJ':('boj_policy_rate',),'BOE':('boe_bank_rate','boe_vote_split')}

from official_bls_actuals import DEFS as BLS_DEFS
REGISTRY.update({'BLS_'+code:keys for code,keys in BLS_DEFS.values()})
REGISTRY['BOK_RATE']=('bok_base_rate',)
REGISTRY['BOK_CCSI']=('kr_ccsi',)
REGISTRY['BOK_GDP']=('gdp_qoq',)
REGISTRY['KOSTAT_EMPLOYMENT']=('kr_unemployment_sa',)
from official_bea_fred import KEYS as BEA_PIO_KEYS
REGISTRY['BEA_PIO']=BEA_PIO_KEYS

def discover_bok(e):
    period=re.search(r'(\d{4})년\s*(\d+)월',e['title'])
    if not period: raise ValueError('REFERENCE_PERIOD_MISSING')
    y,m=map(int,period.groups())
    url='https://www.bok.or.kr/portal/bbs/B0000501/list.do?menuNo=201264&searchCnd=1&searchKwd='+urllib.parse.quote(f'{y}년 {m}월 생산자물가지수')
    raw=raw_fetch(url).decode('utf-8',errors='replace')
    links=Links(raw).rows
    match=next((u for u,t in links if re.search(rf'{y}년\s*{m}월\s*생산자물가지수',t)),None)
    if not match: raise ValueError('BOK_RELEASE_LINK_NOT_FOUND')
    return urllib.parse.urljoin(url,html.unescape(match)),y,m

def collect(e,kind,checks,release_calendar=None):
    dt=release_time(e)
    if kind=='KOSTAT_EMPLOYMENT':
        return collect_kr_employment(e,checks)
    if kind=='BOK_CCSI':
        return collect_ccsi(e,checks)
    if kind=='BOK_GDP':
        return collect_bok_gdp(e,checks)
    if kind=='BOK_RATE':
        from official_bok_policy import collect_policy
        return collect_policy(e,checks)
    if kind=='BEA_PIO':
        from official_bea_fred import collect_pio
        return collect_pio(e,checks)
    if kind.startswith('BLS_'):
        from official_bls_actuals import collect_bls
        return collect_bls(e,kind,checks,release_calendar)
    if kind=='DOL':
        urls=[f'https://oui.doleta.gov/press/{dt.year}/{dt:%m%d%y}.pdf',f'https://www.dol.gov/sites/dolgov/files/OPA/newsreleases/ui-claims/{dt.year}/ui-claims-{dt:%Y%m%d}.pdf','https://www.dol.gov/ui/data.pdf']
        parser=lambda t:parse_claims(t,dt)
    elif kind=='BOJ':
        urls=[f'https://www.boj.or.jp/en/mopo/mpmdeci/mpr_{dt.year}/k{dt:%y%m%d}a.pdf']
        parser=lambda t:parse_boj(t,dt)
    elif kind=='BOE':
        urls=[f'https://www.bankofengland.co.uk/monetary-policy-summary-and-minutes/{dt.year}/{dt:%B}'.lower()+f'-{dt.year}']
        parser=lambda t:parse_boe(t,dt)
    else:
        try:
            # A previously discovered official release URL remains valid after list rollover.
            url=e.get('official_release_url')
            if url:
                period=re.search(r'(\d{4})년\s*(\d+)월',e['title']); y,m=map(int,period.groups())
            else: url,y,m=discover_bok(e)
            raw=raw_fetch(url).decode('utf-8',errors='replace')
            urls=[urllib.parse.urljoin(url,html.unescape(u)) for u,t in Links(raw).rows if '.pdf' in t.lower()]
            urls.append(url)
            e['official_release_url']=url
            parser=lambda t:parse_bok(t,y,m)
        except Exception as exc:
            checks.append({'adapter':kind,'title':e['title'],'result':type(exc).__name__,'error':str(exc)[:200]}); return None
    for url in urls:
        check={'adapter':kind,'title':e['title'],'url':url}
        try:
            document=text_fetch(url)
            rows=parser(document); check['result']='PARSED'; checks.append(check)
            return rows,url
        except Exception as exc:
            if isinstance(exc,ValueError): check['document_prefix']=document[:300]
            check.update(result=f'HTTP_{exc.code}' if hasattr(exc,'code') else type(exc).__name__,error=str(exc)[:200]); checks.append(check)
    return None

def apply_official_actuals(calendar,now):
    checks=[]; updates=0; candidates=[]; historical_attempts=0
    # Copied market values make a release look complete and block re-collection.
    from calendar_metric_quarantine import quarantine_cross_metric_copies
    quarantined=quarantine_cross_metric_copies(calendar,now.isoformat(timespec='seconds'))
    for row in quarantined:
        print(f"CALENDAR_QUARANTINE {row['datetime_kst'][:10]} {row['key']}.{row['field']}={row['value']} copied_from={row['copied_from']}")
    historical_limit=int(os.getenv('CALENDAR_HISTORICAL_BATCH','12'))
    stop_at=time.monotonic()+float(os.getenv('CALENDAR_OFFICIAL_BUDGET_SECONDS','120'))
    def priority(event):
        dt=release_time(event)
        return (bool(dt and now-dt>timedelta(days=14)),event.get('actual_backfill_checked_kst',''))
    for e in sorted(calendar.get('events',[]),key=priority):
        kind=adapter_id(e); dt=release_time(e)
        if not dt or not actual_expected(e): continue
        # Older completed rows may use a different employment headline. Never
        # relabel their existing actual as seasonally adjusted unemployment or
        # retroactively turn completed observations into missing metric rows.
        if kind=='KOSTAT_EMPLOYMENT' and clean(e.get('actual')) is not None and not any(
            m.get('key')=='kr_unemployment_sa' for m in e.get('market_metrics',[])):
            continue
        if kind=='BOK_RATE':
            try:
                from official_bok_policy import correct_date
                correct_date(e,now);dt=release_time(e)
            except Exception as exc:
                checks.append(dict(adapter=kind,title=e['title'],result='SCHEDULE_LOOKUP_FAILED',error=str(exc)[:200]))
                continue
        if kind:
            e['actual_watch']=True
            e['actual_expected']=True
        expected=REGISTRY.get(kind,())
        if kind=='BLS_jltst':
            from official_bls_actuals import cached_document,release_url
            document=cached_document(release_url(e))
            if document and re.search(r'ANNUAL\s+\d{4}',document[1]['text'][:1000]):
                expected=('state_jolts_annual_publication',)
                e['release_kind']='annual_data_publication'
                e['actual_contract_note']='Official annual dataset publication notice; no monthly national JOLTS headline is announced.'
        if e.get('time_status')=='TBD':
            e['sort_datetime_kst']=e['datetime_kst']; e['release_date']=dt.date().isoformat()
        if kind in ('BLS_jltst','BLS_vet','BLS_prin','BLS_prin1'):
            wrong=[m for m in e.get('market_metrics',[]) if m.get('key') not in expected]
            if wrong:
                removed=set((e.get('metric_contract_correction') or {}).get('removed_keys',[]))
                removed.update(m.get('key') for m in wrong)
                e['metric_contract_correction']={'reason':'TITLE_SUBSTRING_COLLISION','removed_keys':sorted(removed)}
                e['market_metrics']=[m for m in e.get('market_metrics',[]) if m.get('key') in expected]
        old={m.get('key'):m for m in e.get('market_metrics',[])}
        for key in expected:
            old.setdefault(key,metric(key,key,None))
        e['market_metrics']=list(old.values())
        start=dt.replace(hour=0,minute=0,second=0) if e.get('time_status')=='TBD' else dt
        if now<start: continue
        incomplete=clean(e.get('actual')) is None or any(actual_expected(m) and clean(m.get('actual')) is None for m in old.values())
        # Inspect recent window each refresh and keep older unresolved work observable.
        historical=now-dt>timedelta(days=14)
        cached=False
        if kind and kind.startswith('BLS_'):
            from official_bls_actuals import release_documents,release_url
            cached=release_url(e) in release_documents()
        if historical and (not incomplete or (not cached and historical_attempts>=historical_limit)): continue
        if incomplete:
            candidates.append({'title':e['title'],'date':dt.date().isoformat(),'adapter':kind,
                               'official_adapter_status':'REGISTERED' if kind else 'NOT_REGISTERED',
                               'fallback_tiers':['SECONDARY','MARKET_FEED']})
        if not kind: continue
        if not incomplete and e.get('source_tier')=='OFFICIAL':
            # An old NOT_PUBLISHED display flag must not survive a verified
            # official GDP observation. Repair metadata, never the measured value.
            if kind == 'BOK_GDP' and e.get('verification_status') == 'VERIFIED_OFFICIAL':
                if clean(e.get('actual')) is not None:
                    e['market_value_status'] = 'ACTUAL_AVAILABLE'
                for row in old.values():
                    if (row.get('key') == 'gdp_qoq' and
                            row.get('source_tier') == 'OFFICIAL' and
                            clean(row.get('actual')) is not None):
                        row['market_value_status'] = 'ACTUAL_AVAILABLE'
            continue
        if not cached and time.monotonic()>=stop_at:
            checks.append(dict(adapter=kind,title=e['title'],result='BUDGET_DEFERRED'))
            continue
        if historical and not cached: historical_attempts+=1
        e['actual_backfill_checked_kst']=now.isoformat(timespec='seconds')
        try:
            result=collect(e,kind,checks,calendar)
        except Exception as exc:
            checks.append(dict(adapter=kind,title=e['title'],result='ADAPTER_FAILED',error=str(exc)[:200]))
            continue
        if not result: continue
        rows,url=result
        provenance={'source_tier':'OFFICIAL','source_url':url,'official_url':url,'checked_kst':now.isoformat(timespec='seconds'),'verification_status':'VERIFIED_OFFICIAL','source':kind+' official release'}
        for m in rows:
            m={**provenance,**m}
            if kind == 'BOK_GDP' and clean(m.get('actual')) is not None:
                m['market_value_status'] = 'ACTUAL_AVAILABLE'
            old[m['key']]=merge_observation(old.get(m['key'],{}),m)
        representative=old[expected[0]]
        source_label=representative.get('source') or kind+' official release'
        patch=dict(provenance,actual=representative['actual'],market_metrics=list(old.values()),
                   source=source_label,actual_source=source_label)
        if kind == 'BOK_GDP' and clean(representative.get('actual')) is not None:
            patch['market_value_status'] = 'ACTUAL_AVAILABLE'
        from calendar_actual_contract import PROVENANCE
        patch.update({k:representative[k] for k in PROVENANCE if k in representative})
        if clean(representative.get('previous')) is not None: patch['previous']=representative['previous']
        # Keep compact previous/consensus identical to primary metric.
        for f in ('previous','consensus'):
            if clean(representative.get(f)) is None and clean(e.get(f)) is not None: representative[f]=e[f]
        e.update(merge_observation(e,patch)); e['market_data_source']=source_label
        updates+=1
    calendar['actual_backfill']={'lookback_days':14,'unresolved_candidates':candidates,'checks':checks,'checked_kst':now.isoformat(timespec='seconds'),'quarantined':quarantined}
    return updates,checks
