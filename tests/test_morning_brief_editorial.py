import copy
import json
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from validate_morning_brief import validate_report

class EditorialAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.report=json.loads((ROOT/'market-observatory/data/morning-brief/20261103.json').read_text())

    def test_new_format_and_historic_archive_both_remain_readable(self):
        validate_report(self.report)
        validate_report(json.loads((ROOT/'market-observatory/data/morning-brief/20261031.json').read_text()))

    def test_old_layout_cannot_silently_replace_new_report(self):
        self.report.pop('editorial_contract')
        with self.assertRaisesRegex(AssertionError,'EDITORIAL_VERSION'):validate_report(self.report)

    def test_issue_explanation_cannot_be_only_headings_and_tables(self):
        self.report['body_markdown']=self.report['body_markdown'].replace('**반대 해석:**','반대 해석')
        with self.assertRaisesRegex(AssertionError,'ISSUE_EXPLANATION'):validate_report(self.report)

    def test_wrong_previous_close_or_change_is_rejected(self):
        self.report['editorial_contract']['close_checks'][0]['change_pct']=.65
        with self.assertRaisesRegex(AssertionError,'ARITHMETIC'):validate_report(self.report)

    def test_same_site_mirrors_do_not_count_as_independent_proof(self):
        self.report['editorial_contract']['close_checks'][0]['source_urls']=['https://indexes.nasdaq.com/a','https://indexes.nasdaq.com/b']
        with self.assertRaisesRegex(AssertionError,'INDEPENDENT'):validate_report(self.report)

    def test_missing_proof_is_allowed_only_with_disclosed_reason(self):
        check=self.report['editorial_contract']['close_checks'][0]
        check.clear();check.update(symbol='NDX',session_date='2026-11-02',status='MISSING',reason='provider conflict')
        validate_report(self.report)
        check.pop('reason')
        with self.assertRaisesRegex(AssertionError,'REASON'):validate_report(self.report)

    def test_est_0540_cannot_verify_same_day_us_close(self):
        self.report['editorial_contract']['verified_at_kst']='2026-11-03T05:40:00+09:00'
        with self.assertRaisesRegex(AssertionError,'UNFINISHED_US_SESSION'):validate_report(self.report)

    def test_different_market_session_is_rejected(self):
        self.report['editorial_contract']['close_checks'][1]['session_date']='2026-10-30'
        with self.assertRaisesRegex(AssertionError,'SESSION_MISMATCH'):validate_report(self.report)

if __name__=='__main__':unittest.main()
