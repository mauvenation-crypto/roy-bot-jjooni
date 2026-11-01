"""Fail-closed tests for the 2026-09 KOSTAT industrial production release."""
import sys
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import enrich_calendar_from_official_macro as bridge

KST = ZoneInfo('Asia/Seoul')
URL = bridge.KOSTAT_INDUSTRIAL_RELEASES['2026-09-01'][1]
PAGE = (
    '<html><body><h3>2026년 9월 산업활동동향</h3>'
    '<div>게시일 2026-10-30</div>'
    '<p>□(생산)전산업생산은 광공업(9.0%)*과 서비스업(0.5%)** 등에서 '
    '생산이 늘어 전월대비 3.0% 증가</p></body></html>'
)


class KostatIndustrialFallbackTest(unittest.TestCase):
    def test_extracts_headline_not_manufacturing_component(self):
        self.assertEqual(
            bridge._parse_kostat_industrial_release(PAGE, '2026-09-01', '2026-10-30'),
            '3.0%',
        )

    def test_wrong_reference_period_fails_closed(self):
        with self.assertRaisesRegex(ValueError, 'REFERENCE_PERIOD_MISMATCH'):
            bridge._parse_kostat_industrial_release(PAGE, '2026-08-01', '2026-10-30')

    def test_wrong_publication_date_fails_closed(self):
        with self.assertRaisesRegex(ValueError, 'PUBLICATION_DATE_MISMATCH'):
            bridge._parse_kostat_industrial_release(PAGE, '2026-09-01', '2026-10-29')

    def test_missing_headline_fails_closed(self):
        with self.assertRaisesRegex(ValueError, 'HEADLINE_NOT_FOUND'):
            bridge._parse_kostat_industrial_release(
                PAGE.replace('전월대비 3.0% 증가', '전년동월대비 3.0% 증가'),
                '2026-09-01', '2026-10-30',
            )

    def test_decrease_has_negative_sign(self):
        self.assertEqual(
            bridge._parse_kostat_industrial_release(
                PAGE.replace('3.0% 증가', '1.2% 감소'),
                '2026-09-01', '2026-10-30',
            ),
            '-1.2%',
        )

    def test_no_network_by_default(self):
        calendar = {'events': [{'title': '2026년 9월 산업활동동향', 'country': 'KR', 'actual': None}]}
        macro = {'metrics': {'KR_INDUSTRIAL_PRODUCTION': {
            'release': {'reference_period': '2026-08-01', 'actual': -1.33}
        }}}
        report = bridge.apply(calendar, macro, datetime(2026, 10, 30, 10, tzinfo=KST))
        self.assertIsNone(calendar['events'][0]['actual'])
        self.assertIn('REFERENCE_PERIOD_MISMATCH', report['checks'][0]['status'])

    def test_official_page_fills_only_missing_exact_month(self):
        calendar = {'events': [{'title': '2026년 9월 산업활동동향', 'country': 'KR',
                                'actual': None, 'previous': '-1.33%', 'market_metrics': []}]}
        macro = {'metrics': {'KR_INDUSTRIAL_PRODUCTION': {
            'release': {'reference_period': '2026-08-01', 'actual': -1.33}
        }}}
        calls = []
        def fetch(url):
            calls.append(url)
            return PAGE
        report = bridge.apply(calendar, macro, datetime(2026, 10, 30, 10, tzinfo=KST),
                              official_release_fetcher=fetch)
        event = calendar['events'][0]
        self.assertEqual(calls, [URL])
        self.assertEqual(event['actual'], '3.0%')
        self.assertEqual(event['previous'], '-1.33%')
        self.assertEqual(event['reference_period'], '2026-09')
        self.assertEqual(event['value_vintage'], 'AS_RELEASED')
        self.assertEqual(event['source_tier'], 'OFFICIAL')
        self.assertEqual(event['official_url'], URL)
        self.assertEqual(report['checks'][0]['status'], 'APPLIED_OFFICIAL_RELEASE')
        self.assertEqual(report['updated_events'], 1)

    def test_page_unavailable_keeps_overdue_and_provenance_unchanged(self):
        calendar = {'events': [{'title': '2026년 9월 산업활동동향', 'country': 'KR',
                                'actual': None, 'source_tier': 'MARKET_FEED'}]}
        macro = {'metrics': {}}
        def unavailable(_url):
            raise OSError('HTTP 403')
        report = bridge.apply(calendar, macro, datetime(2026, 10, 30, 10, tzinfo=KST),
                              official_release_fetcher=unavailable)
        self.assertIsNone(calendar['events'][0]['actual'])
        self.assertEqual(calendar['events'][0]['source_tier'], 'MARKET_FEED')
        self.assertEqual(report['checks'][0]['status'], 'OFFICIAL_RELEASE_UNAVAILABLE')


if __name__ == '__main__':
    unittest.main()
