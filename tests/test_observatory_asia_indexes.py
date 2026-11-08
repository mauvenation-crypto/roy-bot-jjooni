import pathlib
import sys
import unittest
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import add_observatory_equities as eq  # noqa: E402

ROWS = [{'date': '2026-11-05', 'value': 61077.9}, {'date': '2026-11-06', 'value': 57434.8}]


class AsiaIndexTest(unittest.TestCase):
    def test_session_counts_only_after_local_close(self):
        def fetch(symbol, zone):
            return ROWS
        # 2026-11-06 06:00 UTC = 15:00 JST: Tokyo still trading -> 11/06 row excluded.
        data = {}
        eq.refresh_asia_indexes(data, {}, fetch, datetime(2026, 11, 6, 6, 0, tzinfo=timezone.utc))
        self.assertEqual(data['series']['NIKKEI225'][-1]['date'], '2026-11-05')
        # 07:30 UTC = 16:30 JST: close + 30 min passed -> included.
        data = {}
        eq.refresh_asia_indexes(data, {}, fetch, datetime(2026, 11, 6, 7, 30, tzinfo=timezone.utc))
        self.assertEqual(data['latest']['NIKKEI225'], 57434.8)
        self.assertEqual(data['cross_market_freshness_quality']['NIKKEI225']['status'], 'LIVE')

    def test_fetch_failure_keeps_last_verified_rows(self):
        def boom(symbol, zone):
            raise OSError('down')
        data = {}
        eq.refresh_asia_indexes(data, {'HANGSENG': ROWS}, boom, datetime(2026, 11, 8, tzinfo=timezone.utc))
        self.assertEqual(data['series']['HANGSENG'], ROWS)
        self.assertEqual(data['cross_market_freshness_quality']['HANGSENG']['status'], 'STALE')
        self.assertEqual(data['cross_market_freshness_quality']['SHCOMP']['status'], 'UNAVAILABLE')
        self.assertNotIn('SHCOMP', data['series'])


if __name__ == '__main__':
    unittest.main()
