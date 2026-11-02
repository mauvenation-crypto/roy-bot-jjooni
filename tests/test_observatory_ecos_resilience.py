import copy
import io
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import refresh_observatory_kr_rates as kr
import accept_observatory_sources as health
import publish_observatory_data as publisher
import build_market_observatory as market


class EcosResilienceTest(unittest.TestCase):
    def test_official_endpoint_fallback_recovers_after_transport_outage(self):
        with patch.object(kr.urllib.request, 'urlopen', side_effect=TimeoutError()), \
             patch.object(kr.time, 'sleep'), \
             patch.object(kr, '_fallback_json', return_value={'StatisticSearch': {}}) as fallback:
            self.assertEqual(kr._get_json('https://ecos.bok.or.kr/api/secret'), {'StatisticSearch': {}})
            fallback.assert_called_once()

    def test_permanent_outage_preserves_values_and_limits_ecos_requests(self):
        data = {'series': {k: [{'date': '2026-10-13', 'value': 4.0}] for k in kr.KR_RATES},
                'latest': {k: 4.0 for k in kr.KR_RATES}}
        old = copy.deepcopy(data)
        with patch.object(kr, 'fetch_ecos_series', side_effect=RuntimeError('ECOS_TRANSPORT_FAILED_AFTER_3_ATTEMPTS')) as fetch:
            kr.refresh(data, 'sample')
        self.assertEqual(fetch.call_count, 1)
        for name in kr.KR_RATES:
            self.assertEqual(data['series'][name], old['series'][name])
            self.assertEqual(data['latest'][name], old['latest'][name])
            self.assertFalse(data['cross_market_freshness_quality'][name]['fetch_succeeded'])

    def test_cached_current_history_uses_short_incremental_request(self):
        data = {'series': {k: [{'date': '2026-10-13', 'value': 4.0}] for k in kr.KR_RATES}}
        with patch.object(kr, '_age_days', return_value=1), \
             patch.object(kr, 'fetch_ecos_series', return_value=[{'date': '2026-10-13', 'value': 4.1}]) as fetch:
            kr.refresh(data, 'sample')
        from datetime import datetime, timedelta
        self.assertEqual(fetch.call_args.args[2], (datetime.now(kr.KST).date() - timedelta(days=14)).strftime('%Y%m%d'))

    def test_cached_kr_history_does_not_repeat_five_full_ecos_downloads(self):
        cached = {k: [{'date': '2026-10-30', 'value': 3.1}] for k in market.KR_ECOS}
        with patch.object(market, 'load_prev', return_value={'series': cached}), \
             patch.object(market, 'yahoo_series', return_value=[]), \
             patch.object(market, 'ecos_series') as fetch:
            result = market.series_map()
        fetch.assert_not_called()
        self.assertEqual(result['KR10Y'], cached['KR10Y'])
        self.assertEqual(result['KR_3S10S'][-1]['value'], 0.0)

    def test_missing_kr_history_still_bootstraps_from_official_ecos(self):
        cached = {k: [{'date': '2026-10-30', 'value': 3.1}] for k in market.KR_ECOS if k != 'KR30Y'}
        rows = [{'date': '2026-10-30', 'value': 3.4}]
        with patch.object(market, 'load_prev', return_value={'series': cached}), \
             patch.object(market, 'yahoo_series', return_value=[]), \
             patch.object(market, 'ecos_series', return_value=rows) as fetch:
            result = market.series_map()
        fetch.assert_called_once()
        self.assertEqual(fetch.call_args.args[0], market.KR_ECOS['KR30Y'])
        self.assertEqual(result['KR30Y'], rows)

    def test_network_diagnostic_dns_failure_without_secret(self):
        with patch.object(kr.socket, 'getaddrinfo', side_effect=OSError('lookup failed')):
            self.assertEqual(kr._diagnose_ecos_connectivity(), 'DNS_UNAVAILABLE')
        with patch.object(kr.urllib.request, 'urlopen', side_effect=TimeoutError()), \
             patch.object(kr.time, 'sleep'), \
             patch.object(kr, '_fallback_json', side_effect=RuntimeError('ECOS_CURL_FALLBACK_Timeout')), \
             patch.object(kr, '_diagnose_ecos_connectivity', return_value='DNS_UNAVAILABLE'):
            with self.assertRaisesRegex(RuntimeError, 'ECOS_NETWORK_DNS_UNAVAILABLE') as error:
                kr._get_json('https://ecos.bok.or.kr/api/secret-key-value/json/kr')
        self.assertNotIn('secret-key-value', str(error.exception))

    def test_only_ecos_degrades_while_publication_succeeds(self):
        audit = {'schema': 'JJOONI_OBSERVATORY_DATA_AUDIT_V2', 'critical_count': 0,
                 'warning_count': 1, 'groups': {'core_us': {'state': 'LIVE'}, 'kr_rates': {'state': 'STALE'}}}
        result = health.acceptance(audit, {'KR_RATES': 'failure', 'SUPPLEMENTAL': 'success'})
        self.assertEqual(result['publication'], 'PASS')
        self.assertEqual(result['degraded_sources'], {'kr_rates': 'STALE'})
        self.assertEqual(result['collector_failures'], {'KR_RATES': 'failure'})
        audit['critical_count'] = 1
        with self.assertRaisesRegex(RuntimeError, 'CRITICAL_PUBLICATION'):
            health.acceptance(audit, {})

    def test_health_is_rebuilt_after_source_merge_in_order(self):
        with patch.object(publisher.subprocess, 'run') as run:
            publisher.materialize_health([publisher.DATA + 'data-audit.json', publisher.DATA + 'freshness-status.json'])
        self.assertEqual([Path(c.args[0][-1]).name for c in run.call_args_list],
                         ['audit_observatory_data.py', 'build_observatory_freshness.py'])


if __name__ == '__main__':
    unittest.main()
