"""Fail-closed tests for the verified 2026-10 KOSTAT headline CPI release."""
import sys
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import enrich_calendar_from_official_macro as bridge

KST = ZoneInfo('Asia/Seoul')
URL = bridge.KOSTAT_CPI_RELEASES['2026-10-01'][1]
PAGE = (
    '<html><body><h3>2026년 10월 소비자물가동향</h3>'
    '<div>게시일 2026-11-03</div>'
    '<p>□ 10월 소비자물가지수는 전월대비 0.2%, '
    '전년동월대비 2.8% 각각 상승</p>'
    '<p>□ 식료품및에너지제외지수는 전월대비 0.4%, '
    '전년동월대비 2.8% 각각 상승</p></body></html>'
)


def calendar_event(actual=None, release='2026-11-03T08:00+09:00'):
    return {'title': '2026년 10월 소비자물가동향', 'country': 'KR',
            'datetime_kst': release, 'actual': actual,
            'previous': '3.1%', 'market_metrics': []}


class KostatCpiFallbackTest(unittest.TestCase):
    def test_extracts_headline_yoy_not_mom_or_core(self):
        self.assertEqual(bridge._parse_kostat_cpi_release(
            PAGE, '2026-10-01', '2026-11-03'), '2.8%')

    def test_rejects_wrong_period(self):
        with self.assertRaisesRegex(ValueError, 'REFERENCE_PERIOD_MISMATCH'):
            bridge._parse_kostat_cpi_release(PAGE, '2026-09-01', '2026-11-03')

    def test_rejects_wrong_publication_date(self):
        with self.assertRaisesRegex(ValueError, 'PUBLICATION_DATE_MISMATCH'):
            bridge._parse_kostat_cpi_release(PAGE, '2026-10-01', '2026-11-02')

    def test_rejects_missing_or_ambiguous_headline(self):
        with self.assertRaisesRegex(ValueError, 'HEADLINE_MISSING_OR_AMBIGUOUS'):
            bridge._parse_kostat_cpi_release(
                PAGE.replace('소비자물가지수는', '근원소비자물가지수는'),
                '2026-10-01', '2026-11-03')
        with self.assertRaisesRegex(ValueError, 'HEADLINE_MISSING_OR_AMBIGUOUS'):
            bridge._parse_kostat_cpi_release(
                PAGE + PAGE, '2026-10-01', '2026-11-03')

    def test_negative_yoy_and_out_of_range(self):
        self.assertEqual(bridge._parse_kostat_cpi_release(
            PAGE.replace('전년동월대비 2.8% 각각 상승</p>',
                         '전년동월대비 1.2% 각각 하락</p>', 1),
            '2026-10-01', '2026-11-03'), '-1.2%')
        with self.assertRaisesRegex(ValueError, 'OUT_OF_RANGE'):
            bridge._parse_kostat_cpi_release(
                PAGE.replace('전년동월대비 2.8% 각각 상승</p>',
                             '전년동월대비 88.0% 각각 상승</p>', 1),
                '2026-10-01', '2026-11-03')

    def test_no_network_by_default(self):
        cal = {'events': [calendar_event()]}
        macro = {'metrics': {'KR_CPI': {
            'release': {'reference_period': '2026-09-01', 'actual': 2.9}
        }}}
        report = bridge.apply(cal, macro, datetime(2026, 11, 3, 9, tzinfo=KST))
        self.assertIsNone(cal['events'][0]['actual'])
        self.assertIn('REFERENCE_PERIOD_MISMATCH', report['checks'][0]['status'])

    def test_official_page_fills_only_missing_exact_release(self):
        cal = {'events': [calendar_event()]}
        macro = {'metrics': {'KR_CPI': {
            'release': {'reference_period': '2026-09-01', 'actual': 2.9}
        }}}
        calls = []
        def fetch(url):
            calls.append(url)
            return PAGE
        report = bridge.apply(cal, macro, datetime(2026, 11, 3, 9, tzinfo=KST),
                              official_release_fetcher=fetch)
        event = cal['events'][0]
        self.assertEqual(calls, [URL])
        self.assertEqual(event['actual'], '2.8%')
        self.assertEqual(event['previous'], '3.1%')  # no historical rewrite
        self.assertEqual(event['reference_period'], '2026-10')
        self.assertEqual(event['value_vintage'], 'AS_RELEASED')
        self.assertEqual(event['source_tier'], 'OFFICIAL')
        self.assertEqual(event['official_url'], URL)
        self.assertEqual(report['checks'][0]['status'], 'APPLIED_OFFICIAL_RELEASE')
        self.assertEqual(report['updated_events'], 1)

    def test_release_date_guard_and_existing_actual(self):
        for row in [calendar_event(release='2026-11-02T08:00+09:00'),
                    calendar_event(actual='2.8%')]:
            cal = {'events': [row]}
            calls = []
            bridge.apply(cal, {'metrics': {}}, datetime(2026, 11, 3, 9, tzinfo=KST),
                         official_release_fetcher=lambda url: calls.append(url) or PAGE)
            self.assertEqual(calls, [])

    def test_network_failure_preserves_missing_value(self):
        cal = {'events': [calendar_event()]}
        def unavailable(_url):
            raise OSError('HTTP 403')
        report = bridge.apply(cal, {'metrics': {}},
                              datetime(2026, 11, 3, 9, tzinfo=KST),
                              official_release_fetcher=unavailable)
        self.assertIsNone(cal['events'][0]['actual'])
        self.assertEqual(report['checks'][0]['status'], 'OFFICIAL_RELEASE_UNAVAILABLE')


if __name__ == '__main__':
    unittest.main()
