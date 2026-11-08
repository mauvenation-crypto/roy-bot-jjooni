import json
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import fill_calendar_previous_from_history as filler  # noqa: E402

REF = 'US::consumer-price-index::cpi_yoy'


class CalendarPreviousRefreshTest(unittest.TestCase):
    def run_filler(self, event):
        hist = {'series': {REF: {'rows': [
            {'date': '2026-09-11', 'actual': '3.4%'},
            {'date': '2026-10-14', 'actual': '3.7%'},
        ]}}}
        with tempfile.TemporaryDirectory() as d:
            cal_p = pathlib.Path(d) / 'cal.json'
            hist_p = pathlib.Path(d) / 'hist.json'
            cal_p.write_text(json.dumps({'events': [event]}), encoding='utf-8')
            hist_p.write_text(json.dumps(hist), encoding='utf-8')
            with mock.patch.object(filler, 'CAL', cal_p), mock.patch.object(filler, 'HIST', hist_p):
                filler.main()
            return json.loads(cal_p.read_text(encoding='utf-8'))['events'][0]

    def scheduled(self, previous, source, observed):
        return {'title': 'Consumer Price Index', 'datetime_kst': '2026-11-10T22:30:00+09:00',
                'actual': None, 'previous': previous, 'previous_source': source,
                'previous_observed_date': observed,
                'market_metrics': [{'key': 'cpi_yoy', 'history_ref': REF, 'previous': previous,
                                    'previous_source': source, 'previous_observed_date': observed}]}

    def test_stale_history_previous_is_refreshed_after_newer_release(self):
        e = self.run_filler(self.scheduled('3.4%', filler.HISTORY_SOURCE, '2026-09-11'))
        self.assertEqual(e['market_metrics'][0]['previous'], '3.7%')
        self.assertEqual(e['market_metrics'][0]['previous_observed_date'], '2026-10-14')
        self.assertEqual(e['previous'], '3.7%')

    def test_previous_from_other_source_is_never_overwritten(self):
        e = self.run_filler(self.scheduled('3.6%', 'BLS official release', None))
        self.assertEqual(e['market_metrics'][0]['previous'], '3.6%')
        self.assertEqual(e['previous'], '3.6%')

    def test_empty_previous_still_filled(self):
        e = self.run_filler(self.scheduled(None, None, None))
        self.assertEqual(e['previous'], '3.7%')


if __name__ == '__main__':
    unittest.main()
