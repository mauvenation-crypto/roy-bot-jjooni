import pathlib
import sys
import unittest
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import reconcile_bls_official_history as rec  # noqa: E402
from calendar_market_events import sync_representative_values  # noqa: E402

NOW = datetime(2026, 11, 8, 15, 0, tzinfo=ZoneInfo('Asia/Seoul'))


def index_series(sep, aug, sep_prev_year):
    return {(2026, 9): Decimal(sep), (2026, 8): Decimal(aug), (2025, 9): Decimal(sep_prev_year)}


# Official September 2026 PPI: MoM +1.3%, YoY +6.3% (BLS 2026-10-15).
FAKE = {
    'WPUFD4': index_series('106.3', '105.0', '100.0'),
    'WPSFD4': index_series('101.3', '100.0', '95.0'),
    'WPUFD49104': index_series('105.0', '104.5', '100.0'),
    'WPSFD49104': index_series('100.7', '100.0', '96.0'),
}


def fake_fetch(series, year):
    return FAKE[series], f'https://api.bls.gov/{series}'


def ppi_event(**over):
    metrics = [
        {'key': 'ppi_mom', 'actual': '1.3%', 'history_ref': 'US::ppi::ppi_mom', 'source': 'FairEconomy/ForexFactory'},
        {'key': 'ppi_yoy', 'actual': '3.7%', 'history_ref': 'US::ppi::ppi_yoy', 'source': 'FairEconomy/ForexFactory'},
        {'key': 'core_ppi_mom', 'actual': '0.7%', 'history_ref': 'US::ppi::core_ppi_mom'},
        {'key': 'core_ppi_yoy', 'actual': '2.6%', 'history_ref': 'US::ppi::core_ppi_yoy'},
    ]
    e = {'title': 'Producer Price Index', 'country': 'US', 'actual_status': 'RELEASED',
         'datetime_kst': '2026-10-15T21:30+09:00', 'market_metrics': metrics}
    e.update(over)
    return e


class ReconcileTest(unittest.TestCase):
    def test_market_feed_sibling_value_replaced_by_official(self):
        cal = {'events': [ppi_event()]}
        hist = {'series': {'US::ppi::ppi_yoy': {'rows': [{'date': '2026-10-15', 'actual': '3.7%'}]}}}
        report = rec.apply(cal, hist, NOW, fake_fetch)
        m = {x['key']: x for x in cal['events'][0]['market_metrics']}
        self.assertEqual(m['ppi_yoy']['actual'], '6.3%')
        self.assertEqual(m['ppi_yoy']['market_feed_actual'], '3.7%')
        self.assertEqual(m['core_ppi_yoy']['actual'], '5.0%')
        self.assertEqual(m['ppi_mom']['verification_status'], 'VERIFIED_OFFICIAL_REVISED')
        self.assertEqual(cal['events'][0]['official_reconcile']['reference_period'], '2026-09')
        self.assertEqual(hist['series']['US::ppi::ppi_yoy']['rows'][0]['actual'], '6.3%')
        self.assertEqual(report['history_rows_changed'], 1)

    def test_no_anchor_means_no_change(self):
        e = ppi_event()
        for m in e['market_metrics']:
            m['actual'] = '9.9%'
        cal = {'events': [e]}
        report = rec.apply(cal, {'series': {}}, NOW, fake_fetch)
        self.assertEqual(e['market_metrics'][1]['actual'], '9.9%')
        self.assertTrue(report['anchor_failed'])
        # Retry is throttled.
        self.assertEqual(rec.apply(cal, {'series': {}}, NOW, fake_fetch)['events_checked'], 0)

    def test_api_failure_never_falls_back_to_partial_values(self):
        def failing(series, year):
            if series == 'WPUFD4':
                raise ValueError('daily threshold')
            return fake_fetch(series, year)
        e = ppi_event()
        report = rec.apply({'events': [e]}, {'series': {}}, NOW, failing)
        self.assertEqual(e['market_metrics'][1]['actual'], '3.7%')
        self.assertIn('BLS_API_UNAVAILABLE', report['anchor_failed'][0])

    def test_already_official_event_makes_no_request(self):
        e = ppi_event()
        for m in e['market_metrics']:
            m['verification_status'] = 'VERIFIED_OFFICIAL'

        def boom(series, year):
            raise AssertionError('no request expected')
        self.assertEqual(rec.apply({'events': [e]}, {'series': {}}, NOW, boom)['events_checked'], 0)


class RepresentativeValueTest(unittest.TestCase):
    def test_card_previous_and_consensus_come_from_one_metric(self):
        e = {'title': 'Consumer Price Index', 'previous': '3.7%', 'consensus': '0.2%',
             'market_metrics': [
                 {'key': 'cpi_yoy', 'previous': '3.7%', 'consensus': None},
                 {'key': 'cpi_mom', 'previous': '0.6%', 'consensus': '0.3%'},
                 {'key': 'core_cpi_mom', 'previous': '0.3%', 'consensus': '0.2%'}]}
        sync_representative_values(e)
        self.assertEqual((e['representative_metric_key'], e['previous'], e['consensus']), ('cpi_mom', '0.6%', '0.3%'))

    def test_stale_foreign_consensus_is_cleared(self):
        e = {'previous': '3.7%', 'consensus': '0.2%',
             'market_metrics': [{'key': 'a', 'previous': '3.7%'}, {'key': 'b', 'previous': '0.6%'}]}
        sync_representative_values(e)
        self.assertIsNone(e['consensus'])

    def test_previous_provenance_follows_metric(self):
        e = {'previous': '194K', 'previous_observed_date': '2026-10-08',
             'market_metrics': [{'key': 'claims', 'previous': '194K', 'previous_observed_date': '2026-10-29'}]}
        sync_representative_values(e)
        self.assertEqual(e['previous_observed_date'], '2026-10-29')


if __name__ == '__main__':
    unittest.main()
