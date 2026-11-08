"""Regression tests for false-red freshness alarms (JGB holidays, BTC/ETH, BLS UA)."""
import sys
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import japan_business_calendar as jcal
import refresh_observatory_supplementals as supp
import add_observatory_equities as equities
import official_calendar_collectors as official

KST = ZoneInfo('Asia/Seoul')


def at(text):
    return datetime.fromisoformat(text).replace(tzinfo=KST)


class JapanCalendarTest(unittest.TestCase):
    def test_2026_holidays_including_substitute_and_citizens_day(self):
        expected = {date(2026, m, d) for m, d in [
            (1, 1), (1, 12), (2, 11), (2, 23), (3, 20), (4, 29), (5, 3), (5, 4), (5, 5),
            (5, 6), (7, 20), (8, 11), (9, 21), (9, 22), (9, 23), (10, 12), (11, 3), (11, 23)]}
        self.assertEqual(set(jcal.national_holidays(2026)), expected)

    def test_year_end_market_closure(self):
        for d in (date(2026, 12, 31), date(2027, 1, 1), date(2027, 1, 2), date(2027, 1, 3)):
            self.assertTrue(jcal.is_jgb_market_holiday(d))
        self.assertEqual(jcal.previous_jgb_business_day(date(2027, 1, 4)), date(2026, 12, 30))

    def test_out_of_range_year_is_explicit(self):
        with self.assertRaises(ValueError):
            jcal.national_holidays(2021)


class ExpectedJgbDateTest(unittest.TestCase):
    def test_holiday_is_not_required_as_an_observation(self):
        # 2026-11-03 Culture Day: MOF publishes no yield, so 11/4 expects 11/2.
        self.assertEqual(supp.expected_jgb_business_date(at('2026-11-04T12:00')), '2026-11-02')
        self.assertEqual(supp.expected_jgb_business_date(at('2026-11-05T08:00')), '2026-11-02')
        self.assertEqual(supp.expected_jgb_business_date(at('2026-11-05T10:00')), '2026-11-04')
        self.assertEqual(supp.expected_jgb_business_date(at('2026-11-24T12:00')), '2026-11-20')

    def test_weekend_and_next_day_publication(self):
        self.assertEqual(supp.expected_jgb_business_date(at('2026-11-08T13:00')), '2026-11-05')
        self.assertEqual(supp.expected_jgb_business_date(at('2026-11-09T09:00')), '2026-11-05')
        self.assertEqual(supp.expected_jgb_business_date(at('2026-11-09T10:00')), '2026-11-06')

    def test_empty_month_file_is_not_a_collection_failure(self):
        with patch.object(supp, 'get_bytes', return_value='基準日,1年,2年\n'.encode('utf-8')):
            rows, url = supp.fetch_current_jgb_rows()
        self.assertEqual(rows, [])
        self.assertEqual(url, supp.JGB_CURRENT_URLS[0])

    def test_transport_failure_is_still_a_failure(self):
        with patch.object(supp, 'get_bytes', side_effect=OSError('down')):
            with self.assertRaises(RuntimeError):
                supp.fetch_current_jgb_rows()

    def test_all_mof_tenors_normalize(self):
        got = [supp._normalize_tenor(x) for x in ['1年', '4年', '15年', '20年', '40年', '10Y', '2-year']]
        self.assertEqual(got, ['1Y', '4Y', '15Y', '20Y', '40Y', '10Y', '2Y'])


class CryptoHistoryRepairTest(unittest.TestCase):
    def test_existing_history_repairs_only_recent_range(self):
        utc = ZoneInfo('UTC')
        now = datetime(2026, 11, 8, 2, 0, tzinfo=utc)
        quotes = {key: ([{'date': '2026-11-08', 'value': 1.0, 'session_status': 'IN_PROGRESS'}],
                        {'status': 'LIVE', 'price': 1.0, 'source': 'CoinGecko',
                         'quote_as_of_kst': now.astimezone(KST).isoformat()})
                  for key in equities.CRYPTO_SYMBOLS}
        start = date(2026, 9, 1)
        history = [{'date': (start + timedelta(days=i)).isoformat(), 'value': 1.0,
                    'session_status': 'COMPLETED'} for i in range(60)]
        data = {'series': {k: list(history) for k in equities.CRYPTO_SYMBOLS}}
        ranges = []

        def stub(symbol, now=None, history_range='3y'):
            ranges.append(history_range)
            return [], {}
        with patch.object(equities, 'coingecko_spot_observations', return_value=quotes), \
             patch.object(equities, 'crypto_observation', side_effect=stub):
            equities.enrich_crypto(data)
        self.assertEqual(ranges, ['1mo', '1mo'])


class OfficialUserAgentTest(unittest.TestCase):
    def test_contact_comes_from_configuration_not_code(self):
        bare = official.official_user_agent('')
        self.assertTrue(bare.startswith('jjooni-control-tower/2.0 (+https://github.com/'))
        self.assertNotIn('Mozilla', bare)
        self.assertTrue(official.official_user_agent('ops contact').endswith('; ops contact)'))
        self.assertNotIn('\n', official.official_user_agent('a\nb'))


class CryptoWorkflowContractTest(unittest.TestCase):
    def test_pages_probe_is_advisory_and_collection_still_gates(self):
        text = (ROOT / '.github/workflows/observatory-crypto-refresh.yml').read_text()
        probe = text.split('id: runtime_probe', 1)[1].split('- name:', 1)[0]
        self.assertIn('continue-on-error: true', probe)
        self.assertIn('test "$COLLECTION_OUTCOME" = success', text)


if __name__ == '__main__':
    unittest.main()
