import pathlib
import sys
import unittest
from datetime import datetime
from unittest import mock
from zoneinfo import ZoneInfo

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from yahoo_bar_date import bar_date  # noqa: E402
import refresh_observatory_supplementals as sup  # noqa: E402

LON = ZoneInfo('Europe/London')
NY = ZoneInfo('America/New_York')


def ts(y, m, d, tz, h=0):
    return int(datetime(y, m, d, h, tzinfo=tz).timestamp())


class YahooBarDateTest(unittest.TestCase):
    def test_fx_bar_keeps_its_london_session_date(self):
        fx = {'meta': {'exchangeTimezoneName': 'Europe/London'}}
        # Friday 2026-11-06 FX bar opens 00:00 London = Thu 19:00 New York.
        self.assertEqual(bar_date(ts(2026, 11, 6, LON), fx), '2026-11-06')
        # Summer time (BST) too.
        self.assertEqual(bar_date(ts(2026, 7, 3, LON), fx), '2026-07-03')

    def test_us_bars_unchanged(self):
        us = {'meta': {'exchangeTimezoneName': 'America/New_York'}}
        self.assertEqual(bar_date(ts(2026, 11, 6, NY, 9), us), '2026-11-06')
        self.assertEqual(bar_date(ts(2026, 11, 6, NY, 9), {}), '2026-11-06')

    def test_fresh_fx_window_replaces_mislabelled_rows(self):
        old = [{'date': '2026-10-20', 'value': 0.5}, {'date': '2026-11-01', 'value': 1.0}, {'date': '2026-11-05', 'value': 2.0}]
        fresh = [{'date': '2026-11-02', 'value': 1.0}, {'date': '2026-11-06', 'value': 2.0}]
        data = {'series': {'USDKRW': old}, 'us_completed_session_date': '2026-11-06'}

        def fake(symbol):
            return fresh if symbol == 'KRW=X' else []

        with mock.patch.object(sup, 'yahoo_series', side_effect=fake):
            sup.refresh_yahoo(data)
        self.assertEqual([r['date'] for r in data['series']['USDKRW']], ['2026-10-20', '2026-11-02', '2026-11-06'])


if __name__ == '__main__':
    unittest.main()
