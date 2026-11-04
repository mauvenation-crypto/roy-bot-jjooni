import unittest
from datetime import datetime, timedelta
from unittest.mock import patch
from tools import build_observatory_sector_etf as sector


class SectorContractTests(unittest.TestCase):
    def test_kr_registry_account_independent_and_unranked(self):
        codes = [t for key, _, members in sector.GROUPS if key.startswith('kr_') for t, _ in members]
        self.assertEqual(len(codes), 13)
        self.assertEqual(len(set(codes)), 13)
        self.assertTrue(all(sector.market_of(t) == 'KR' for t in codes))
        self.assertIn('069500', codes)
        self.assertIn('229200', codes)
        self.assertIn('133690', codes)
        all_codes = {t for _, _, members in sector.GROUPS for t, _ in members}
        self.assertIn('QQQ', all_codes)

    def test_us_dst_preclose_and_postclose(self):
        rows = [{'date': '2026-09-30', 'value': 100}, {'date': '2026-10-01', 'value': 999}]
        pre = datetime.fromisoformat('2026-10-01T23:04:00+09:00')
        post = datetime.fromisoformat('2026-10-02T05:10:00+09:00')
        self.assertEqual(sector.completed_points(rows, 'US', pre), rows[:1])
        self.assertEqual(sector.completed_points(rows, 'US', post), rows)
        winter = datetime.fromisoformat('2026-12-02T05:10:00+09:00')
        self.assertEqual(sector.completed_cutoff('US', winter), '2026-11-30')

    def test_calendar_return_uses_prior_trading_date_and_preserves_missing_history(self):
        rows = [{'date': '2025-11-03', 'value': 100},
                {'date': '2026-10-02', 'value': 110},
                {'date': '2026-11-03', 'value': 121}]
        result = sector.calendar_return(rows, 1)
        self.assertEqual(result['base_date'], '2026-10-02')
        self.assertEqual(result['end_date'], '2026-11-03')
        self.assertAlmostEqual(result['pct'], 10.0)
        self.assertAlmostEqual(sector.calendar_return(rows, 12)['pct'], 21.0)
        self.assertIsNone(sector.calendar_return(rows[1:], 12))

    def test_kr_cutoff_and_weekend(self):
        pre = datetime.fromisoformat('2026-10-01T15:39:00+09:00')
        post = datetime.fromisoformat('2026-10-01T15:40:00+09:00')
        self.assertEqual(sector.completed_cutoff('KR', pre), '2026-09-30')
        self.assertEqual(sector.completed_cutoff('KR', post), '2026-10-01')
        self.assertEqual(sector.completed_cutoff('US', datetime.fromisoformat('2026-10-04T20:00:00+09:00')), '2026-10-02')

    def test_generation_does_not_promote_legacy_partial_fallback(self):
        previous = {'generated_kst': '2026-10-01T23:04:00+09:00',
                    'series': {'XLK': [{'date': '2026-09-30', 'value': 100},
                                       {'date': '2026-10-01', 'value': 999}]}}
        now = datetime.fromisoformat('2026-10-02T06:30:00+09:00')
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp, patch.object(sector, 'OUT', Path(tmp)/'sector.json'), \
             patch.object(sector, 'load_previous', return_value=previous), \
             patch.object(sector, 'yahoo_series', side_effect=OSError('offline')):
            result = sector.build(now)
        self.assertEqual(result['series']['XLK'], previous['series']['XLK'][:1])
        self.assertEqual(result['daily_bar_contract'], 'PER_MARKET_COMPLETED_CUTOFF_V1')
        kr = [r for g in result['groups'] for r in g['rows'] if r['market'] == 'KR']
        self.assertEqual(len(kr), 13)  # Missing quotes do not erase membership.


if __name__ == '__main__':
    unittest.main()
