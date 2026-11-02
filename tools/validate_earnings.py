#!/usr/bin/env python3
"""Public earnings contract: never invent dates, quarter identity or comparisons."""
import json, math, sys
from datetime import datetime, date
from pathlib import Path
from urllib.parse import urlparse
ROOT=Path(__file__).resolve().parents[1]
ALLOWED={'schema','updated_kst','universe','events','coverage_note','privacy'}
EVENT={'id','symbol','fiscal_period','status','date_kst','time_status','release_at_kst','call_at_kst','sources','metrics','facts','analysis','risks','next_checks','updated_kst'}
METRIC={'label','actual','unit','basis','yoy_pct','consensus','consensus_basis'}
UNITS={'KRW_TRILLION','KRW_BILLION','USD_BILLION','USD_MILLION','USD_PER_SHARE','PERCENT'}
DOMAINS={'samsung.com','skhynix.com','skhynix.co.kr','microsoft.com','sec.gov','dart.fss.or.kr','kind.krx.co.kr','nvidia.com','aboutamazon.com','abc.xyz','apple.com','investor.fb.com','investor.atmeta.com','tesla.com','broadcom.com','amd.com','micron.com','asml.com','palantir.com','netflix.net','netflix.com','costco.com','intuitive.com','arm.com','vertiv.com','eaton.com','tsmc.com','lgen-sol.com','samsungbiologics.com','hyundai.com','kia.com','kbfg.com','navercorp.com','hanwhaaerospace.com','ls-electric.com','hd-hyundaielectric.com','doosanenerbility.com','lumentum.com','coherent.com','arista.com','marvell.com','credosemi.com','onsemi.com'}
def stamp(v):
 d=datetime.fromisoformat(v);assert d.tzinfo is not None,'timestamp requires timezone';return d

def validate(d):
 assert set(d)<=ALLOWED,'unknown/private top-level fields'
 assert d['schema']=='OBS_EARNINGS_V1' and d['privacy']=='PUBLIC_MARKET_INFORMATION_ONLY'
 stamp(d['updated_kst']);symbols=set()
 for c in d['universe']:
  assert set(c)=={'symbol','name','market','theme','scope'},'universe contains private fields'
  assert c['symbol'] not in symbols and c['market'] in {'KR','US'}
  symbols.add(c['symbol'])
 ids=set()
 for e in d['events']:
  assert set(e)<=EVENT,'unknown/private event fields'
  assert e['id']==e['symbol']+':'+e['fiscal_period'] and e['id'] not in ids
  ids.add(e['id']);assert e['symbol'] in symbols
  assert e['status'] in {'SCHEDULED','RELEASED'}
  date.fromisoformat(e['date_kst']);stamp(e['updated_kst'])
  assert e['time_status'] in {'DATE_ONLY','CONFIRMED','APPROXIMATE'}
  for k in ['release_at_kst','call_at_kst']:
   if e.get(k):stamp(e[k])
  assert e['sources'],'official source required'
  for s in e['sources']:
   u=urlparse(s['url']);host=(u.hostname or '').lower()
   assert u.scheme=='https' and any(host==h or host.endswith('.'+h) for h in DOMAINS),'unapproved source domain'
   assert s['kind']=='OFFICIAL';stamp(s['checked_kst'])
  if e['status']=='RELEASED':assert e['metrics'] and e['facts'],'released results need verified metrics and facts'
  else:assert not e['metrics'],'scheduled event cannot contain reported results'
  for m in e['metrics']:
   assert set(m)<=METRIC and m['unit'] in UNITS
   assert m['basis'] in {'REPORTED','GAAP','NON_GAAP'}
   for k in ['actual','consensus','yoy_pct']:
    v=m.get(k);assert v is None or (isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v))
   assert m['actual'] is not None
   if m.get('consensus') is not None:assert m.get('consensus_basis')==m['basis'],'comparison basis mismatch'
 return d
if __name__=='__main__':
 p=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'market-observatory/data/earnings.json'
 d=validate(json.loads(p.read_text()));print('EARNINGS_CONTRACT_PASS',len(d['events']),'events',len(d['universe']),'companies')
