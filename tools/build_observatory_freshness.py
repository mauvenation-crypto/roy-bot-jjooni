#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from observatory_session import expected_completed_session
from regime_validity import regime_state

ROOT = Path(__file__).resolve().parents[1]
KST = ZoneInfo('Asia/Seoul')
OUT = ROOT / 'market-observatory' / 'data' / 'freshness-status.json'


def load(path: Path) -> dict:
    try:return json.loads(path.read_text(encoding='utf-8'))
    except Exception:return {}

def text(value):
    value=str(value or '').strip();return value or None

def group(label,state,generated_kst=None,as_of=None,detail=None,source=None,critical=False):
    return {'label':label,'state':text(state) or 'UNAVAILABLE','generated_kst':text(generated_kst),'as_of':text(as_of),'detail':text(detail),'source':text(source),'critical':bool(critical)}

def _aggregate_states(states):
    xs=[text(x) or 'UNAVAILABLE' for x in states]
    if any(x in {'UNAVAILABLE','FAILED','ERROR'} for x in xs):return 'UNAVAILABLE'
    if any(x in {'MISALIGNED','INCONSISTENT','AHEAD_OF_ANCHOR'} for x in xs):return 'MISALIGNED'
    if any(x in {'STALE'} for x in xs):return 'STALE'
    if any(x in {'FALLBACK','STALE_FALLBACK','DEGRADED'} for x in xs):return 'DEGRADED'
    if any(x in {'LAGGING'} for x in xs):return 'LAGGING'
    return 'LIVE'

def _audit_detail(audit_group):
    items=audit_group.get('items') or {}
    detail = ' · '.join(f"{k} {v.get('last_date') or '—'}" for k,v in items.items())
    failed = audit_group.get('failed_series') or {}
    if failed:
        detail += ' · 수집 실패: ' + ', '.join(f'{k} ({v})' for k, v in failed.items())
    return detail

def _audit_asof(audit_group):
    dates=[str(v.get('last_date') or '')[:10] for v in (audit_group.get('items') or {}).values() if v.get('last_date')]
    return min(dates) if dates else None

def _count_field(obj,count_key,list_key):
    value=obj.get(count_key)
    if value is None:value=len(obj.get(list_key) or [])
    try:return int(value or 0)
    except Exception:return len(obj.get(list_key) or [])



def calendar_probe_health(checks: list[dict], events: list[dict]) -> dict:
    """Keep BLS transport failures visible without hiding a verified official fallback.

    Only a same-release, same-value ECIALLCIV observation with official
    provenance can resolve a BLS ECI transport failure. Other releases and
    failed fallback attempts remain blocked.
    """
    failures = [c for c in checks if
                str(c.get('result') or '').startswith('HTTP_') or
                str(c.get('result') or '') in {'REFERENCE_PERIOD_MISSING','SERIES_NOT_CONFIGURED','PARTIAL'} or
                str(c.get('result') or '').endswith('Error')]

    def release_id(url):
        match = re.search(r'eci_(\d{8})\.(?:htm|pdf|txt)(?:$|\?)', str(url or ''), re.I)
        return match.group(1) if match else None

    verified = set()
    for check in checks:
        if check.get('adapter') != 'ECI_FRED' or check.get('result') != 'VERIFIED_BLS_TABLE1_FRED_MATCH':
            continue
        title = text(check.get('title'))
        release = release_id(check.get('bls_url'))
        if not title or not release:
            continue
        for event in events:
            if not isinstance(event, dict) or event.get('title') != title:
                continue
            if (event.get('verification_status') != 'VERIFIED_OFFICIAL' or
                    event.get('source_tier') != 'OFFICIAL' or
                    event.get('actual') != check.get('actual') or
                    release_id(event.get('official_url')) != release):
                continue
            if any(isinstance(m, dict) and m.get('series_id') == 'ECIALLCIV' and
                   m.get('reference_period') == check.get('reference_period') and
                   m.get('verification_status') == 'VERIFIED_OFFICIAL'
                   for m in event.get('market_metrics') or []):
                verified.add((title, release))

    def key(check):
        return text(check.get('title')) or text(check.get('adapter')) or 'unknown'

    unresolved = [c for c in failures if (key(c), release_id(c.get('url'))) not in verified]
    blocked = sorted({key(c) for c in unresolved})
    transport_blocked = sorted({key(c) for c in failures})
    return {
        'state': ('DEGRADED' if blocked else
                  'PASS_WITH_TRANSPORT_WARNINGS' if failures else
                  'PASS' if checks else 'NOT_CHECKED'),
        'failure_count': len(failures),
        'unresolved_failure_count': len(unresolved),
        'blocked_releases': blocked,
        'transport_blocked_releases': transport_blocked,
        'verified_fallback_releases': sorted({title for title, _ in verified}),
    }

def calendar_official_evidence(events, now):
    """Summarize stored provenance, never claim a new network check took place."""
    rows=[]
    for event in events:
        if (not isinstance(event,dict) or event.get('source_tier')!='OFFICIAL' or
                event.get('verification_status')!='VERIFIED_OFFICIAL' or
                event.get('actual') is None or str(event.get('actual')).strip() in ('','—','-') or
                not (event.get('official_url') or event.get('source_url'))):
            continue
        stamp=event.get('official_actual_checked_kst') or event.get('checked_kst')
        try:
            dt=datetime.fromisoformat(str(stamp))
            if dt.tzinfo is None or dt>now:continue
        except (TypeError,ValueError):continue
        rows.append((dt,stamp))
    latest=max(rows,key=lambda row:row[0])[1] if rows else None
    return {'scope':'STORED_EVENT_PROVENANCE_NOT_CURRENT_NETWORK_CHECK',
            'verified_event_count':len(rows),'latest_verified_kst':latest,
            'note': '기존 공식 검증 이력 · 이번 실행의 원천 접속 성공을 뜻하지 않습니다.'}

def build_status(root: Path = ROOT, now=None) -> dict:
    now = now or datetime.now(KST)
    data=root/'market-observatory'/'data'
    obs=load(data/'observatory.json');pulse=load(data/'daily-market-pulse.json');fed=load(data/'fed-watch.json');cal=load(data/'economic-calendar.json');sector=load(data/'sector-etf.json');public=load(root/'public-market-daily.json');audit=load(data/'data-audit.json');macro=load(data/'official-macro.json')

    obs_fresh=obs.get('freshness') or {};fgq=(obs.get('quality') or {}).get('fear_greed') or {};tripod=obs.get('tripod_latest') or {};public_tripod=public.get('tripod_signal') or {};supp=obs.get('market_supplement_quality') or {};ag=audit.get('groups') or {}
    session=text(obs.get('us_completed_session_date'));pulse_session=text(pulse.get('market_date_us'));tripod_session=text(public_tripod.get('date') or tripod.get('date'))
    pulse_aligned=bool(session and pulse_session==session and pulse.get('snapshot_status')=='FINAL');tripod_aligned=bool(session and tripod_session==session and public_tripod.get('ok') is True);source_session=text(public_tripod.get('date'));market_aligned=bool(session and (not source_session or session>=source_session))

    kr_kospi=supp.get('KOSPI') or {};kr_kosdaq=supp.get('KOSDAQ') or {};kr_state=(ag.get('kr_equity') or {}).get('state') or _aggregate_states([kr_kospi.get('status'),kr_kosdaq.get('status')]);kr_asof=_audit_asof(ag.get('kr_equity') or {}) or max([x for x in [text(kr_kospi.get('last_date')),text(kr_kosdaq.get('last_date'))] if x],default=None)
    us_keys=('RUSSELL2000','DOW','NASDAQCOMPOSITE');us_items=[supp.get(k) or {} for k in us_keys];us_supplement_aligned=bool(session and all(text(x.get('last_date'))==session for x in us_items));us_state=(ag.get('us_supplement') or {}).get('state') or _aggregate_states([x.get('status') for x in us_items])
    if session and not us_supplement_aligned and us_state!='UNAVAILABLE':us_state='LAGGING'
    aligned=bool(market_aligned and pulse_aligned and tripod_aligned and us_supplement_aligned)

    market_state=(ag.get('core_us') or {}).get('state') or text(obs_fresh.get('status')) or ('LIVE' if obs.get('generated_kst') else 'UNAVAILABLE')
    if not market_aligned:market_state='MISALIGNED' if session and source_session else 'UNAVAILABLE'
    pulse_state='LIVE' if pulse_aligned else ('MISALIGNED' if session and pulse_session else 'UNAVAILABLE')
    fg_state=(ag.get('sentiment') or {}).get('state') or text(fgq.get('state')) or ('LIVE' if (obs.get('latest') or {}).get('FEAR_GREED') is not None else 'UNAVAILABLE')
    fed_state=(ag.get('fedwatch') or {}).get('state') or text(fed.get('freshness')) or ('LIVE' if fed.get('market_data_as_of') else 'UNAVAILABLE')
    tripod_state='LIVE' if tripod_aligned else ('MISALIGNED' if session and tripod_session else 'UNAVAILABLE')
    expected=expected_completed_session(now)
    if session and session!=expected:
        if market_state!='MISALIGNED':market_state='LAGGING' if session<expected else 'AHEAD_OF_ANCHOR'
        if pulse_state=='LIVE':pulse_state='LAGGING' if session<expected else 'AHEAD_OF_ANCHOR'
        if tripod_state=='LIVE':tripod_state='LAGGING' if session<expected else 'AHEAD_OF_ANCHOR'
        aligned=False
    cal_fresh=cal.get('actual_freshness') or {};cal_collection=cal.get('collection_health') or {};cal_state=text(cal_fresh.get('status')) or ('LIVE' if cal.get('generated_kst') else 'UNAVAILABLE');sector_state='LIVE' if sector.get('as_of_date') else 'UNAVAILABLE'
    cal_overdue=_count_field(cal_fresh,'overdue_count','overdue_events');cal_pending=_count_field(cal_fresh,'pending_count','pending_events');cal_failed_sources=len(cal_collection.get('failed_sources') or [])
    # Release-actual completeness and official-document accessibility are independent.
    # Do not call a calendar wholly LIVE when its BLS release probes are blocked.
    cal_official_checks=[c for c in (cal_fresh.get('official_checks') or []) if isinstance(c,dict)]
    cal_probe=calendar_probe_health(cal_official_checks, cal.get('events') or [])
    cal_probe_blocked=cal_probe['blocked_releases']
    cal_actual_state=cal_state
    if cal_probe_blocked and cal_state=='LIVE':
        cal_state='DEGRADED'

    # The crypto provider can switch per symbol (CoinGecko primary / Yahoo fallback).
    # Never hard-code Yahoo or substitute a market-wide timestamp for the quote writer.
    crypto_quotes=obs.get('crypto_market') or {}
    crypto_sources=' · '.join(
        f"{key}: {str((crypto_quotes.get(key) or {}).get('source') or 'UNKNOWN')}"
        for key in ('BTCUSD','ETHUSD')
    )
    crypto_generated=obs.get('crypto_enriched_kst') or obs.get('supplemental_refreshed_kst') or obs.get('equity_enriched_kst')

    groups={
        'market':group('Market SSOT',market_state,obs.get('generated_kst'),session,'미국 핵심 완료세션 NDX/SPX/VIX','observatory.json',True),
        'kr_equity':group('KR Equity',kr_state,obs.get('supplemental_refreshed_kst') or obs.get('equity_enriched_kst'),kr_asof,_audit_detail(ag.get('kr_equity') or {}) or f"KOSPI {kr_kospi.get('last_date') or '—'} · KOSDAQ {kr_kosdaq.get('last_date') or '—'}",'Naver Finance primary',True),
        'us_supplement':group('US Supplement',us_state,obs.get('supplemental_refreshed_kst') or obs.get('equity_enriched_kst'),_audit_asof(ag.get('us_supplement') or {}) or session,_audit_detail(ag.get('us_supplement') or {}) or f"RUT {us_items[0].get('last_date') or '—'} · DOW {us_items[1].get('last_date') or '—'} · IXIC {us_items[2].get('last_date') or '—'}",'Yahoo completed cash-session daily',False),
        'energy':group('Energy',(ag.get('energy') or {}).get('state'),obs.get('supplemental_refreshed_kst') or obs.get('generated_kst'),_audit_asof(ag.get('energy') or {}),_audit_detail(ag.get('energy') or {}),'Yahoo CL=F / BZ=F / NG=F',False),
        'fx':group('FX / DXY',(ag.get('fx') or {}).get('state'),obs.get('supplemental_refreshed_kst') or obs.get('generated_kst'),_audit_asof(ag.get('fx') or {}),_audit_detail(ag.get('fx') or {}),'Yahoo DXY / FX daily',False),
        'metals':group('Metals',(ag.get('metals') or {}).get('state'),obs.get('supplemental_refreshed_kst') or obs.get('generated_kst'),_audit_asof(ag.get('metals') or {}),_audit_detail(ag.get('metals') or {}),'Yahoo Gold / Silver / Copper',False),
        'us_rates':group('US Rates',(ag.get('us_rates') or {}).get('state'),obs.get('generated_kst'),_audit_asof(ag.get('us_rates') or {}),_audit_detail(ag.get('us_rates') or {}),'U.S. Treasury official',False),
        'kr_rates':group('KR Rates',(ag.get('kr_rates') or {}).get('state'),obs.get('kr_rates_refreshed_kst') or obs.get('generated_kst'),_audit_asof(ag.get('kr_rates') or {}),_audit_detail(ag.get('kr_rates') or {}),'BOK ECOS',False),
        'jp_rates':group('JP Rates',(ag.get('jp_rates') or {}).get('state'),obs.get('supplemental_refreshed_kst') or obs.get('generated_kst'),_audit_asof(ag.get('jp_rates') or {}),_audit_detail(ag.get('jp_rates') or {}),'Japan MOF current JGB CSV',False),
        'crypto':group('Crypto',(ag.get('crypto') or {}).get('state'),crypto_generated,None,' · '.join(f"{k} age={v.get('current_quote_age_seconds','—')}s" for k,v in (audit.get('crypto_status') or {}).items()),crypto_sources,False),
        'pulse':group('Daily Pulse',pulse_state,pulse.get('generated_kst'),pulse_session,f"snapshot={pulse.get('snapshot_status') or '—'} · Observatory session={session or '—'}",'daily-market-pulse.json',True),
        'fear_greed':group('Fear & Greed',fg_state,obs.get('supplemental_refreshed_kst') or obs.get('generated_kst'),_audit_asof(ag.get('sentiment') or {}) or fgq.get('observed_at') or session,f"{(obs.get('latest') or {}).get('FEAR_GREED','—')}/100 · {(obs.get('latest') or {}).get('FEAR_GREED_RATING') or ''}".strip(),fgq.get('source') or 'Fear & Greed public',False),
        'fedwatch':group('FedWatch',fed_state,fed.get('generated_kst'),fed.get('market_data_as_of'),f"expected={(audit.get('file_status') or {}).get('fedwatch',{}).get('audit_expected_market_data_date') or '—'} · FOMC {fed.get('meeting_date') or '—'}",text(fed.get('source')) or 'CME Fed Funds settlement',False),
        'tripod':group('TRI-POD',tripod_state,public.get('generated_kst') or obs.get('generated_kst'),tripod_session,f"{tripod.get('regime') or public_tripod.get('regime') or '—'} · {tripod.get('target') or public_tripod.get('target') or '—'}",'public-market-daily.json + observatory.json',True),
        'sector':group('Sector ETF',sector_state,sector.get('generated_kst'),sector.get('as_of_date'),f"priced={(sector.get('summary') or {}).get('priced_count','—')}",'sector-etf.json',False),
        'official_macro':group('Official Macro','LIVE' if macro.get('generated_kst') else 'UNAVAILABLE',macro.get('generated_kst'),None,macro.get('schema'),'official-macro.json',False),
        'calendar':group('Economic Calendar',cal_state,cal.get('generated_kst'),cal_fresh.get('latest_released_at') or cal.get('generated_kst'),f"events={len(cal.get('events') or [])} · overdue={cal_overdue} · pending={cal_pending} · source_failures={cal_failed_sources} · official_probe_blocked={len(cal_probe_blocked)}",'economic-calendar.json',False),
        'audit':group('Full Data Audit',audit.get('overall') or 'UNAVAILABLE',audit.get('generated_kst'),session,f"critical={audit.get('critical_count','—')} · warnings={audit.get('warning_count','—')}",'data-audit.json',True),
    }
    evidence=calendar_official_evidence(cal.get('events') or [],now)
    groups['calendar']['official_probe_scope']='LATEST_COLLECTION_ATTEMPTS_ONLY'
    groups['calendar']['official_verification_evidence']=evidence
    groups['calendar']['detail']+=f" · 기존 공식 검증 {evidence['verified_event_count']}건 · 이번 원천 조회 {cal_probe['state']}"
    groups['calendar']['actual_completeness_state']=cal_actual_state
    groups['calendar']['official_probe_state']=cal_probe['state']
    groups['calendar']['official_probe_failure_count']=cal_probe['failure_count']
    groups['calendar']['official_probe_unresolved_failure_count']=cal_probe['unresolved_failure_count']
    groups['calendar']['official_probe_blocked_releases']=cal_probe_blocked
    groups['calendar']['official_probe_transport_blocked_releases']=cal_probe['transport_blocked_releases']
    groups['calendar']['official_probe_verified_fallback_releases']=cal_probe['verified_fallback_releases']
    regime = load(data/'market-regime.json')
    window = regime.get('effective_window') or {}
    groups['market_regime'] = group('과거 주간 분석 · 투자보드 관리', regime_state(regime, now), regime.get('generated_kst'), window.get('end_kst'), '이력 참고용 · 최신 시장/계좌 판정과 별개 · 투자보드에서 주간 전략 관리', 'market-regime.json', False)
    groups['market_regime']['informational'] = True
    groups['market_regime']['monitoring_scope'] = 'INVESTMENT_BOARD_REFERENCE_ONLY'
    groups['market_regime']['consensus_status'] = (regime.get('source') or {}).get('consensus_status')
    groups['market_regime']['authority'] = regime.get('authority')
    groups['market_regime']['valid_from_kst'] = window.get('start_kst')
    groups['market_regime']['valid_until_kst'] = window.get('end_kst')
    # Quote timestamps travel with the SSOT so a viewer can re-evaluate the age
    # against its own clock. The producer's LIVE verdict is only a point-in-time audit.
    groups['crypto']['quotes'] = {
        k: {'status': v.get('status'), 'quote_as_of_kst': v.get('quote_as_of_kst')}
        for k, v in (audit.get('crypto_status') or {}).items()
    }
    groups['crypto']['max_age_seconds'] = 3600
    hard_bad={'UNAVAILABLE','FAILED','ERROR','MISALIGNED','FAIL','INCONSISTENT','AHEAD_OF_ANCHOR'};soft_bad={'WARN','LAGGING','STALE','STALE_FALLBACK','DEGRADED','PENDING','FALLBACK','EXPIRED'}
    critical_bad=[k for k,v in groups.items() if v['critical'] and v['state'] in (hard_bad|{'LAGGING','STALE'})];warnings=[k for k,v in groups.items() if not v.get('informational') and (v['state'] in soft_bad or (not v['critical'] and v['state'] in hard_bad))]
    overall='DEGRADED' if critical_bad else ('LIVE_WITH_WARNINGS' if warnings else 'LIVE')
    return {'schema':'JJOONI_OBSERVATORY_FRESHNESS_STATUS_V2','generated_kst':now.astimezone(KST).isoformat(timespec='seconds'),'freshness_policy':{'max_status_age_seconds':7200,'scope':'STATUS_ASSESSMENT_NOT_OBSERVATION_AGE','watchdog_scope':'US_CLOSE_RECOVERY_ONLY'},'overall':overall,'critical_bad':critical_bad,'warnings':warnings,'watchdog_required':bool(critical_bad),'session_alignment':{'expected_session':expected,'source_session':source_session,'market_aligned':market_aligned,'observatory':session,'daily_market_pulse':pulse_session,'tripod':tripod_session,'pulse_aligned':pulse_aligned,'tripod_aligned':tripod_aligned,'us_supplement_aligned':us_supplement_aligned,'kr_kospi':kr_kospi.get('last_date'),'kr_kosdaq':kr_kosdaq.get('last_date'),'aligned':aligned},'groups':groups,'audit_schema':audit.get('schema'),'contract':'DISPLAY_ALL_MARKET_FAMILY_SOURCE_ASOF_STATE_AND_WATCHDOG_DECISION_V3','read_only':True}

def main():
    status=build_status(ROOT);OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(status,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print('OBSERVATORY_FRESHNESS_STATUS=PASS',status['overall'],'aligned=',status['session_alignment']['aligned'],'warnings=',status['warnings'])

if __name__=='__main__':main()

