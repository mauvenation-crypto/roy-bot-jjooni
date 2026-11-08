"""Regression tests for the 2026-11-08 calendar value-integrity repair.

Covers: quarantining market values copied across metrics before the #236
identity guard, BEA PIO actuals via
FRED, previous values that follow the history SSOT, and history quarantine.
"""
import importlib
import json
import sys
import tempfile
import unittest
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from calendar_actual_contract import KST
from calendar_metric_quarantine import quarantine_cross_metric_copies
import official_bls_api as bls_api
import official_bea_fred as bea


def legacy(key, label, **values):
    # Shape of a value written by the pre-#236 generic matcher.
    return dict(key=key, label=label, generic_match_score=62.52, source_tier='MARKET_FEED', **values)


class QuarantineTest(unittest.TestCase):
    def test_yoy_holding_mom_values_is_quarantined_and_mom_is_kept(self):
        mom = legacy('avg_hourly_mom', 'Average Hourly Earnings MoM', actual='0.1%', consensus='0.3%', previous='0.3%')
        yoy = legacy('avg_hourly_yoy', 'Average Hourly Earnings YoY', actual='0.1%', consensus='0.3%', previous='0.3%')
        cal = {'events': [{'title': 'Employment Situation', 'datetime_kst': '2026-10-02T21:30+09:00',
                           'market_metrics': [mom, yoy]}]}
        audit = quarantine_cross_metric_copies(cal, 'now')
        self.assertEqual({(a['key'], a['field']) for a in audit},
                         {('avg_hourly_yoy', 'actual'), ('avg_hourly_yoy', 'consensus'), ('avg_hourly_yoy', 'previous')})
        self.assertEqual(mom['actual'], '0.1%')
        self.assertIsNone(yoy['actual'])
        self.assertEqual(yoy['quarantined_values']['actual']['value'], '0.1%')
        self.assertNotIn('source_tier', yoy)  # provenance follows the cleared actual

    def test_owner_with_recorded_row_title_keeps_value(self):
        imp = dict(key='us_import_price_mom', label='Import Prices MoM', event_title='Import Prices m/m',
                   actual='1.1%', source_tier='MARKET_FEED')
        exp = legacy('us_export_price_mom', 'Export Prices MoM', actual='1.1%')
        cal = {'events': [{'title': 'X', 'datetime_kst': '2026-10-16', 'market_metrics': [imp, exp]}]}
        quarantine_cross_metric_copies(cal)
        self.assertEqual(imp['actual'], '1.1%')
        self.assertIsNone(exp['actual'])

    def test_official_actual_and_coincidental_equal_values_are_untouched(self):
        mom = legacy('cpi_mom', 'CPI MoM', actual='0.3%')
        official = dict(key='cpi_yoy', label='CPI YoY', generic_match_score=60, source_tier='OFFICIAL', actual='0.3%')
        compatible = legacy('core_cpi_mom', 'Core CPI MoM', actual='0.3%')
        cal = {'events': [{'title': 'CPI', 'datetime_kst': 'x', 'market_metrics': [mom, official, compatible]}]}
        audit = quarantine_cross_metric_copies(cal)
        self.assertEqual(official['actual'], '0.3%')
        self.assertEqual(compatible['actual'], '0.3%')
        self.assertFalse([a for a in audit if a['field'] == 'actual'])

    def test_idempotent(self):
        mom = legacy('pce_mom', 'PCE MoM', actual='0.2%')
        yoy = legacy('pce_yoy', 'PCE YoY', actual='0.2%')
        cal = {'events': [{'title': 'P', 'datetime_kst': 'x', 'market_metrics': [mom, yoy]}]}
        self.assertEqual(len(quarantine_cross_metric_copies(cal)), 1)
        self.assertEqual(quarantine_cross_metric_copies(cal), [])


class BeaFredTest(unittest.TestCase):
    def fetcher(self, series):
        base = {'PCEPILFE': 100, 'PCEPI': 100, 'PI': 100, 'PCE': 100}[series]
        values = {(2025, 8): Decimal(base), (2026, 7): Decimal('103.0'), (2026, 8): Decimal('103.309')}
        return values, f'fred/{series}'

    def test_reference_month_comes_only_from_title(self):
        self.assertEqual(bea.reference_month('Personal Income and Outlays, August 2026'), (2026, 8))
        self.assertIsNone(bea.reference_month('Personal Income and Outlays'))

    def test_values_are_official_latest_revision(self):
        rows, url = bea.collect_pio({'title': 'Personal Income and Outlays, August 2026'}, [], self.fetcher)
        by_key = {r['key']: r for r in rows}
        self.assertEqual(by_key['pce_yoy']['actual'], '3.3%')
        self.assertEqual(by_key['core_pce_mom']['actual'], '0.3%')
        self.assertEqual(by_key['pce_yoy']['value_vintage'], 'LATEST_REVISION')
        self.assertEqual(by_key['pce_yoy']['reference_period'], '2026-08')

    def test_unpublished_month_fails_closed(self):
        checks = []
        result = bea.collect_pio({'title': 'Personal Income and Outlays, September 2026'}, checks, self.fetcher)
        self.assertIsNone(result)
        self.assertTrue(all(c['result'] == 'ValueError' for c in checks))

    def test_fetch_failures_are_attempted_once_per_run(self):
        bea._CACHE.clear()
        with patch('official_bea_fred._fetch', side_effect=TimeoutError('slow')) as slow:
            for _ in range(3):
                with self.assertRaises(TimeoutError):
                    bea.fetch('PCEPI')
            self.assertEqual(slow.call_count, 1)
        bea._CACHE.clear()


class PreviousAndHistoryTest(unittest.TestCase):
    def run_tool(self, module, calendar, history):
        with tempfile.TemporaryDirectory() as d:
            cal, hist = Path(d) / 'cal.json', Path(d) / 'hist.json'
            cal.write_text(json.dumps(calendar)); hist.write_text(json.dumps(history))
            mod = importlib.import_module(module)
            with patch.object(mod, 'CAL', cal), patch.object(mod, 'HIST', hist):
                mod.main()
            return json.loads(cal.read_text())

    def test_derived_previous_follows_latest_history_but_provider_previous_is_kept(self):
        ref = 'US::x::nfp'
        history = {'series': {ref: {'rows': [{'date': '2026-09-04', 'actual': '162K'},
                                              {'date': '2026-11-06', 'actual': '165K'}]}}}
        derived = dict(key='nfp', history_ref=ref, previous='162K', previous_source='CALENDAR_HISTORY_LAST_ACTUAL',
                       previous_observed_date='2026-09-04')
        provider = dict(key='nfp2', history_ref=ref, previous='60K', previous_source='FairEconomy')
        cal = {'events': [{'datetime_kst': '2026-12-04T22:30+09:00', 'market_metrics': [derived, provider]}]}
        out = self.run_tool('fill_calendar_previous_from_history', cal, history)
        metrics = {m['key']: m for m in out['events'][0]['market_metrics']}
        self.assertEqual(metrics['nfp']['previous'], '165K')
        self.assertEqual(metrics['nfp']['previous_observed_date'], '2026-11-06')
        self.assertEqual(metrics['nfp2']['previous'], '60K')

    def test_history_drops_quarantined_copy(self):
        import build_calendar_history as bch
        event = {'title': 'T', 'country': 'US', 'datetime_kst': '2026-10-16T21:30+09:00',
                 'market_metrics': [{'key': 'us_export_price_mom', 'history_ref': 'R', 'actual': None,
                                     'quarantined_values': {'actual': {'value': '1.1%'}}}]}
        series = {'R': {'rows': [{'date': '2026-10-16', 'actual': '1.1%', 'source_tier': 'MARKET_FEED'},
                                 {'date': '2026-09-16', 'actual': '0.6%', 'source_tier': 'MARKET_FEED'}]}}
        self.assertEqual(bch.apply_quarantine(series, {'events': [event]}), 1)
        self.assertEqual([r['date'] for r in series['R']['rows']], ['2026-09-16'])


if __name__ == '__main__':
    unittest.main()
