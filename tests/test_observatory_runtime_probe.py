import copy
import json
import socket
import sys
import unittest
import urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import probe_observatory_runtime as p

NOW = datetime(2026, 11, 3, 1, 0, tzinfo=timezone.utc)
STAMP = (NOW-timedelta(seconds=30)).isoformat()


def fixture():
    quotes = {k: {'key':k, 'symbol':v, 'value':100, 'observed_at':STAMP,
                  'source':'YAHOO_CHART_QUOTE', 'market_state':'CONTINUOUS',
                  'refresh_status':'FETCHED','quality':'DELAY_POSSIBLE'} for k,v in p.SYMBOLS.items()}
    api = {'schema':'JJOONI_OBSERVATORY_QUOTES_V1','status':'COMPLETE','quotes':quotes,
           'fetched_count':20,'expected_count':20,'failures':{}}
    expected = {'schema':'JJOONI_MARKET_OBSERVATORY_V1','crypto_market':{
        k:{'quote_as_of_kst':STAMP,'status':'LIVE','price':100,'source':'CoinGecko'} for k in p.SYMBOLS}}
    fresh = {'schema':'JJOONI_OBSERVATORY_FRESHNESS_STATUS_V2',
             'groups':{'crypto':{'quotes':copy.deepcopy(expected['crypto_market'])}}}
    return api, expected, fresh, copy.deepcopy(expected)


class RuntimeProbeTests(unittest.TestCase):
    def test_api_requires_real_cors_and_valid_fresh_symbol_provenance(self):
        api, _, _, _ = fixture()
        good = {'Access-Control-Allow-Origin':p.ORIGIN}
        self.assertEqual(p.validate_api(api,200,good,NOW)['status'],'PASS')
        for bad in [dict(api,schema='wrong')]:
            with self.assertRaises(ValueError): p.validate_api(bad,200,good,NOW)
        with self.assertRaisesRegex(ValueError,'CORS'): p.validate_api(api,200,{},NOW)
        for fields in [{'value':True},{'value':float('nan')},{'symbol':'ETH-USD'},
                       {'observed_at':'2026-11-03T01:00:00'},
                       {'observed_at':(NOW+timedelta(minutes=1)).isoformat()},
                       {'observed_at':(NOW-timedelta(minutes=11)).isoformat()},
                       {'source':None},{'refresh_status':'RETAINED'}]:
            bad=copy.deepcopy(api);bad['quotes']['BTCUSD'].update(fields)
            with self.assertRaises(ValueError):p.validate_api(bad,200,good,NOW)

    def test_noncrypto_partial_failure_stays_visible_without_claiming_all_quotes_healthy(self):
        api, _, _, _ = fixture();api.update(status='PARTIAL',fetched_count=19,failures={'USDJPY':'SOURCE_UNAVAILABLE'})
        result=p.validate_api(api,200,{'access-control-allow-origin':p.ORIGIN},NOW)
        self.assertEqual(result['status'],'PASS')
        self.assertEqual(result['coverage'],'PARTIAL')
        self.assertEqual(result['unavailable_keys'],['USDJPY'])

    def test_pages_requires_actual_data_not_successful_deployment_or_frozen_live(self):
        _, expected, fresh, recent=fixture()
        self.assertEqual(p.validate_pages(fresh,recent,expected,NOW)['status'],'PASS')
        for fields in [{'quote_as_of_kst':(NOW-timedelta(hours=2)).isoformat()},
                       {'quote_as_of_kst':(NOW-timedelta(minutes=1)).isoformat()},
                       {'price':99},{'source':'Unverified'},{'status':'STALE'}]:
            bad=copy.deepcopy(recent);bad['crypto_market']['BTCUSD'].update(fields)
            with self.assertRaises(ValueError):p.validate_pages(fresh,bad,expected,NOW)
        with self.assertRaises(ValueError):p.validate_pages({'status':'SUCCESS'},recent,expected,NOW)

    def test_newer_concurrent_publication_is_accepted_without_rewriting_baseline(self):
        _, expected, fresh, recent=fixture();before=copy.deepcopy(expected)
        later=(NOW-timedelta(seconds=5)).isoformat()
        for key in p.SYMBOLS:
            fresh['groups']['crypto']['quotes'][key]['quote_as_of_kst']=later
            recent['crypto_market'][key].update(quote_as_of_kst=later,price=101)
        self.assertEqual(p.validate_pages(fresh,recent,expected,NOW)['status'],'PASS')
        self.assertEqual(expected,before)

    def test_dns_failure_is_classified_separately_and_does_not_hide_successful_pages(self):
        _, expected, fresh, recent=fixture()
        def fetch(url,timeout):
            if url==p.API:raise urllib.error.URLError(socket.gaierror('test-only'))
            return (fresh if 'freshness-status' in url else recent),200,{}
        receipt=p.probe(expected,fetch=fetch,clock=lambda:NOW,pause=lambda _:None,pages_budget=0)
        self.assertEqual(receipt['status'],'FAIL')
        self.assertEqual(receipt['api']['reason'],'PROBE_DNS_FAILURE')
        self.assertEqual(receipt['pages']['status'],'PASS')

    def test_transient_api_and_pages_delay_recover_with_bounded_reads(self):
        api, expected, fresh, recent=fixture();ticks=[0];calls={'api':0,'pages':0}
        def pause(seconds):ticks[0]+=seconds
        def fetch(url,timeout):
            if url==p.API:
                calls['api']+=1
                if calls['api']==1:raise TimeoutError('transient')
                return api,200,{'Access-Control-Allow-Origin':p.ORIGIN}
            if 'freshness-status' in url:
                calls['pages']+=1
                if calls['pages']==1:return {},200,{}
                return fresh,200,{}
            return recent,200,{}
        receipt=p.probe(expected,fetch=fetch,clock=lambda:NOW,monotonic=lambda:ticks[0],pause=pause,pages_budget=10)
        self.assertEqual(receipt['status'],'PASS')
        self.assertEqual(calls,{'api':2,'pages':2})
        self.assertTrue(receipt['read_only']);self.assertEqual(receipt['orders'],'NONE')

    def test_pages_delay_expires_and_never_reports_success_from_main_only(self):
        api, expected, _, _=fixture();ticks=[0]
        def fetch(url,timeout):
            return (api,200,{'Access-Control-Allow-Origin':p.ORIGIN}) if url==p.API else ({},200,{})
        def pause(seconds):ticks[0]+=seconds
        receipt=p.probe(expected,fetch=fetch,clock=lambda:NOW,monotonic=lambda:ticks[0],pause=pause,pages_budget=10)
        self.assertEqual(receipt['status'],'FAIL');self.assertEqual(receipt['api']['status'],'PASS')
        self.assertEqual(receipt['pages']['status'],'FAIL');self.assertEqual(receipt['pages']['attempts'],3)
        self.assertLessEqual(ticks[0],10)


if __name__=='__main__':unittest.main()
