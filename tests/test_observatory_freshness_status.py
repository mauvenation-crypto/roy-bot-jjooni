#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))

import build_observatory_freshness as freshness  # noqa: E402


class ObservatoryFreshnessStatusTest(unittest.TestCase):
    def test_same_old_session_across_all_files_cannot_validate_itself_as_live(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            self.write(root,'market-observatory/data/observatory.json',{
                'generated_kst':'2026-10-22T05:14:23+09:00','us_completed_session_date':'2026-10-20','freshness':{'status':'LIVE'},'market_supplement_quality':self.supplements('2026-10-20','2026-10-21')})
            self.write(root,'market-observatory/data/daily-market-pulse.json',{'market_date_us':'2026-10-20','snapshot_status':'FINAL'})
            self.write(root,'public-market-daily.json',{'tripod_signal':{'ok':True,'date':'2026-10-20'}})
            self.write_v2_support(root)
            out=freshness.build_status(root,now=datetime(2026,10,22,6,28,tzinfo=ZoneInfo('Asia/Seoul')))
            for key in ('market','pulse','tripod'):self.assertEqual(out['groups'][key]['state'],'LAGGING')
            self.assertFalse(out['session_alignment']['aligned']);self.assertTrue(out['watchdog_required'])

    def test_regime_expiry_boundaries_and_invalid_windows(self):
        regime={'source':{'consensus_status':'CLOSED'},'effective_window':{'start_kst':'2026-10-12T00:00:00+09:00','end_kst':'2026-10-16T23:59:59+09:00'}}
        for stamp, expected in [('2026-10-11T23:59:59+09:00','PENDING'),('2026-10-12T00:00:00+09:00','LIVE'),('2026-10-16T23:59:59+09:00','LIVE'),('2026-10-17T00:00:00+09:00','EXPIRED')]:
            self.assertEqual(freshness.regime_state(regime,datetime.fromisoformat(stamp)),expected)
        self.assertEqual(freshness.regime_state({}), 'UNAVAILABLE')
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            self.write(root,'market-observatory/data/market-regime.json',regime)
            out=freshness.build_status(root,now=datetime.fromisoformat('2026-10-25T07:00:00+09:00'))
            self.assertEqual(out['generated_kst'],'2026-10-25T07:00:00+09:00')
            self.assertEqual(out['freshness_policy']['max_status_age_seconds'],7200)
            self.assertEqual(out['groups']['market_regime']['valid_from_kst'],'2026-10-12T00:00:00+09:00')
            self.assertEqual(out['groups']['market_regime']['state'],'EXPIRED')
            self.assertNotIn('market_regime',out['warnings'])
            self.assertTrue(out['groups']['market_regime']['informational'])
            self.assertEqual(out['groups']['market_regime']['monitoring_scope'], 'INVESTMENT_BOARD_REFERENCE_ONLY')
            self.assertNotIn('market_regime',out['critical_bad'])

    def test_time_window_cannot_promote_provisional_or_unknown_consensus(self):
        now=datetime.fromisoformat('2026-10-27T12:00:00+09:00')
        window={'start_kst':'2026-10-26T00:00:00+09:00','end_kst':'2026-10-30T23:59:59+09:00'}
        self.assertEqual(freshness.regime_state({'effective_window':window,'source':{'consensus_status':'PARTIAL_PENDING_JJANGGU'}},now),'PROVISIONAL')
        self.assertEqual(freshness.regime_state({'effective_window':window},now),'UNAVAILABLE')
        self.assertEqual(freshness.regime_state({'effective_window':window,'authority':'ANALYST_PROVISIONAL','source':{'consensus_status':'CLOSED'}},now),'PROVISIONAL')

    def test_crypto_freshness_reports_actual_provider_and_quote_collection_time(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            self.write(root,'market-observatory/data/observatory.json',{
                'generated_kst':'2026-11-01T17:00:00+09:00',
                'supplemental_refreshed_kst':'2026-11-01T16:40:00+09:00',
                'crypto_enriched_kst':'2026-11-01T18:43:41+09:00',
                'crypto_market':{
                    'BTCUSD':{'source':'CoinGecko public simple/price USD spot'},
                    'ETHUSD':{'source':'Yahoo Finance spot crypto quote + UTC daily candles'},
                },
            })
            self.write_v2_support(root)
            out=freshness.build_status(root,now=datetime.fromisoformat('2026-11-01T18:44:00+09:00'))
            crypto=out['groups']['crypto']
            self.assertEqual(crypto['generated_kst'],'2026-11-01T18:43:41+09:00')
            self.assertIn('BTCUSD: CoinGecko',crypto['source'])
            self.assertIn('ETHUSD: Yahoo Finance',crypto['source'])
            self.assertNotEqual(crypto['generated_kst'],'2026-11-01T16:40:00+09:00')

    def write(self, root: Path, rel: str, obj: dict):
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(obj), encoding='utf-8')

    def supplements(self, us_date='2026-10-08', kr_date='2026-10-08'):
        return {
            'KOSPI': {'status': 'LIVE', 'last_date': kr_date, 'source': 'Naver Finance index daily'},
            'KOSDAQ': {'status': 'LIVE', 'last_date': kr_date, 'source': 'Naver Finance index daily'},
            'RUSSELL2000': {'status': 'LIVE', 'last_date': us_date, 'source': 'Yahoo completed cash-session daily'},
            'DOW': {'status': 'LIVE', 'last_date': us_date, 'source': 'Yahoo completed cash-session daily'},
            'NASDAQCOMPOSITE': {'status': 'LIVE', 'last_date': us_date, 'source': 'Yahoo completed cash-session daily'},
        }

    def write_v2_support(self, root: Path, fed_state='LIVE'):
        self.write(root, 'market-observatory/data/market-regime.json', {'source':{'consensus_status':'CLOSED'},'effective_window': {'start_kst':'2026-01-01T00:00:00+09:00', 'end_kst':'2026-12-31T23:59:59+09:00'}})
        groups = {
            name: {'state': 'LIVE', 'items': {}}
            for name in (
                'core_us', 'us_supplement', 'kr_equity', 'fx', 'energy', 'metals',
                'us_rates', 'kr_rates', 'jp_rates', 'crypto', 'sentiment', 'fedwatch'
            )
        }
        groups['fedwatch']['state'] = fed_state
        overall = 'PASS' if fed_state == 'LIVE' else 'WARN'
        self.write(root, 'market-observatory/data/data-audit.json', {
            'schema': 'JJOONI_OBSERVATORY_DATA_AUDIT_V2',
            'generated_kst': '2026-10-09T06:12:00+09:00',
            'overall': overall,
            'critical_count': 0,
            'warning_count': 0 if overall == 'PASS' else 1,
            'groups': groups,
            'file_status': {'fedwatch': {'audit_expected_market_data_date': '2026-10-08'}},
            'crypto_status': {},
        })
        self.write(root, 'market-observatory/data/official-macro.json', {
            'schema': 'JJOONI_OFFICIAL_MACRO_V1',
            'generated_kst': '2026-10-09T06:12:00+09:00',
        })

    def test_old_downstream_cannot_be_live_against_new_source(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.write(root, 'market-observatory/data/observatory.json', {
                'generated_kst': '2026-10-10T06:00:00+09:00',
                'us_completed_session_date': '2026-10-08',
                'freshness': {'status': 'LIVE'},
                'market_supplement_quality': self.supplements(),
            })
            self.write(root, 'market-observatory/data/daily-market-pulse.json', {
                'market_date_us': '2026-10-08', 'snapshot_status': 'FINAL',
            })
            self.write(root, 'public-market-daily.json', {
                'tripod_signal': {'ok': True, 'date': '2026-10-09'},
            })
            self.write_v2_support(root)
            out = freshness.build_status(root, now=datetime(2026,10,9,6,15,tzinfo=ZoneInfo("Asia/Seoul")))
            self.assertEqual(out['overall'], 'DEGRADED')
            self.assertEqual(out['groups']['market']['state'], 'MISALIGNED')
            self.assertIn('market', out['critical_bad'])
            self.assertFalse(out['session_alignment']['market_aligned'])
            self.assertFalse(out['session_alignment']['aligned'])
            self.assertTrue(out['watchdog_required'])

    def test_aligned_live_inputs_are_live(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.write(root, 'market-observatory/data/observatory.json', {
                'generated_kst': '2026-10-09T06:10:00+09:00',
                'equity_enriched_kst': '2026-10-09T06:10:00+09:00',
                'us_completed_session_date': '2026-10-08',
                'freshness': {'status': 'LIVE'},
                'latest': {'FEAR_GREED': 38.1, 'FEAR_GREED_RATING': 'FEAR'},
                'quality': {'fear_greed': {'state': 'LIVE', 'source': 'CNN', 'observed_at': '2026-10-08'}},
                'tripod_latest': {'date': '2026-10-08', 'regime': '상승', 'target': 'TQQQ 100%'},
                'market_supplement_quality': self.supplements(),
            })
            self.write(root, 'market-observatory/data/daily-market-pulse.json', {
                'generated_kst': '2026-10-09T06:11:00+09:00',
                'market_date_us': '2026-10-08',
                'snapshot_status': 'FINAL',
            })
            self.write(root, 'public-market-daily.json', {
                'generated_kst': '2026-10-09T06:12:00+09:00',
                'tripod_signal': {'ok': True, 'date': '2026-10-08'},
            })
            self.write(root, 'market-observatory/data/fed-watch.json', {
                'freshness': 'LIVE', 'market_data_as_of': '2026-10-08', 'meeting_date': '2026-10-28'
            })
            self.write(root, 'market-observatory/data/economic-calendar.json', {
                'generated_kst': '2026-10-09T06:12:00+09:00', 'events': [], 'actual_freshness': {'status': 'LIVE'}
            })
            self.write(root, 'market-observatory/data/sector-etf.json', {'as_of_date': '2026-10-08'})
            self.write_v2_support(root)

            out = freshness.build_status(root, now=datetime(2026,10,9,6,15,tzinfo=ZoneInfo("Asia/Seoul")))

            self.assertEqual(out['overall'], 'LIVE')
            self.assertTrue(out['session_alignment']['aligned'])
            self.assertTrue(out['session_alignment']['pulse_aligned'])
            self.assertTrue(out['session_alignment']['tripod_aligned'])
            self.assertTrue(out['session_alignment']['us_supplement_aligned'])
            self.assertEqual(out['groups']['kr_equity']['state'], 'LIVE')
            self.assertEqual(out['groups']['us_supplement']['state'], 'LIVE')
            self.assertEqual(out['groups']['pulse']['state'], 'LIVE')
            self.assertEqual(out['groups']['tripod']['state'], 'LIVE')
            self.assertFalse(out['watchdog_required'])

    def test_pulse_misalignment_is_critical_without_blaming_tripod(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.write(root, 'market-observatory/data/observatory.json', {
                'generated_kst': '2026-10-09T06:10:00+09:00',
                'us_completed_session_date': '2026-10-08',
                'freshness': {'status': 'LIVE'},
                'latest': {'FEAR_GREED': 38.1},
                'tripod_latest': {'date': '2026-10-08'},
                'market_supplement_quality': self.supplements(),
            })
            self.write(root, 'market-observatory/data/daily-market-pulse.json', {
                'market_date_us': '2026-10-07', 'snapshot_status': 'FINAL'
            })
            self.write(root, 'public-market-daily.json', {'tripod_signal': {'ok': True, 'date': '2026-10-08'}})
            self.write_v2_support(root)

            out = freshness.build_status(root, now=datetime(2026,10,9,6,15,tzinfo=ZoneInfo("Asia/Seoul")))

            self.assertEqual(out['overall'], 'DEGRADED')
            self.assertEqual(out['groups']['pulse']['state'], 'MISALIGNED')
            self.assertEqual(out['groups']['tripod']['state'], 'LIVE')
            self.assertIn('pulse', out['critical_bad'])
            self.assertNotIn('tripod', out['critical_bad'])
            self.assertFalse(out['session_alignment']['pulse_aligned'])
            self.assertTrue(out['session_alignment']['tripod_aligned'])

    def test_tripod_misalignment_is_critical(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.write(root, 'market-observatory/data/observatory.json', {
                'generated_kst': '2026-10-09T06:10:00+09:00',
                'us_completed_session_date': '2026-10-08',
                'freshness': {'status': 'LIVE'},
                'latest': {'FEAR_GREED': 38.1},
                'tripod_latest': {'date': '2026-10-08'},
                'market_supplement_quality': self.supplements(),
            })
            self.write(root, 'market-observatory/data/daily-market-pulse.json', {
                'market_date_us': '2026-10-08', 'snapshot_status': 'FINAL'
            })
            self.write(root, 'public-market-daily.json', {'tripod_signal': {'ok': True, 'date': '2026-10-07'}})
            self.write_v2_support(root)

            out = freshness.build_status(root, now=datetime(2026,10,9,6,15,tzinfo=ZoneInfo("Asia/Seoul")))

            self.assertEqual(out['overall'], 'DEGRADED')
            self.assertFalse(out['session_alignment']['aligned'])
            self.assertTrue(out['session_alignment']['pulse_aligned'])
            self.assertFalse(out['session_alignment']['tripod_aligned'])
            self.assertEqual(out['groups']['pulse']['state'], 'LIVE')
            self.assertEqual(out['groups']['tripod']['state'], 'MISALIGNED')
            self.assertTrue(out['watchdog_required'])

    def test_fedwatch_lagging_is_warning_not_hard_failure(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.write(root, 'market-observatory/data/observatory.json', {
                'generated_kst': '2026-10-09T06:10:00+09:00',
                'us_completed_session_date': '2026-10-08',
                'freshness': {'status': 'LIVE'},
                'latest': {'FEAR_GREED': 38.1},
                'tripod_latest': {'date': '2026-10-08'},
                'market_supplement_quality': self.supplements(),
            })
            self.write(root, 'market-observatory/data/daily-market-pulse.json', {
                'market_date_us': '2026-10-08', 'snapshot_status': 'FINAL'
            })
            self.write(root, 'public-market-daily.json', {'tripod_signal': {'ok': True, 'date': '2026-10-08'}})
            self.write(root, 'market-observatory/data/fed-watch.json', {'freshness': 'LAGGING', 'market_data_as_of': '2026-10-07'})
            self.write_v2_support(root, fed_state='LAGGING')

            out = freshness.build_status(root, now=datetime(2026,10,9,6,15,tzinfo=ZoneInfo("Asia/Seoul")))

            self.assertEqual(out['overall'], 'LIVE_WITH_WARNINGS')
            self.assertIn('fedwatch', out['warnings'])
            self.assertFalse(out['watchdog_required'])


    def test_official_bls_probe_failures_are_visible_despite_complete_actuals(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            self.write(root,'market-observatory/data/economic-calendar.json',{
                'generated_kst':'2026-10-28T08:50:00+09:00',
                'events':[],
                'actual_freshness':{
                    'status':'LIVE','overdue_count':0,'pending_count':0,
                    'official_checks':[
                        {'adapter':'BLS_cpi','title':'Consumer Price Index','result':'HTTP_403'},
                        {'adapter':'BLS_API','title':'Consumer Price Index','result':'REFERENCE_PERIOD_MISSING'},
                        {'adapter':'BLS_ppi','title':'Producer Price Index','result':'PARSED'},
                    ]},
                'collection_health':{'status':'LIVE','failed_sources':[]},
            })
            out=freshness.build_status(root,now=datetime.fromisoformat('2026-10-28T09:00:00+09:00'))
            cal=out['groups']['calendar']
            self.assertEqual(cal['state'],'DEGRADED')
            self.assertEqual(cal['actual_completeness_state'],'LIVE')
            self.assertEqual(cal['official_probe_state'],'DEGRADED')
            self.assertEqual(cal['official_probe_failure_count'],2)
            self.assertEqual(cal['official_probe_blocked_releases'],['Consumer Price Index'])
            self.assertIn('calendar',out['warnings'])
            self.assertFalse(cal['critical'])

    def test_successful_official_probe_does_not_create_false_alarm(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            self.write(root,'market-observatory/data/economic-calendar.json',{
                'generated_kst':'2026-10-28T08:50:00+09:00','events':[],
                'actual_freshness':{'status':'LIVE','official_checks':[
                    {'adapter':'BLS_cpi','title':'Consumer Price Index','result':'PARSED'}]},
                'collection_health':{'failed_sources':[]},
            })
            out=freshness.build_status(root,now=datetime.fromisoformat('2026-10-28T09:00:00+09:00'))
            cal=out['groups']['calendar']
            self.assertEqual(cal['state'],'LIVE')
            self.assertEqual(cal['official_probe_state'],'PASS')
            self.assertEqual(cal['official_probe_failure_count'],0)
            self.assertNotIn('calendar',out['warnings'])


if __name__ == '__main__':
    unittest.main()
