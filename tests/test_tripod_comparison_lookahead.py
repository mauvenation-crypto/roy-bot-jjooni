import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from build_tripod_comparison import daily_suffix, verified_daily_signal_rows, require_full_coverage  # noqa: E402


class DailySuffixTest(unittest.TestCase):
    def test_period_bars_before_daily_tail_are_dropped(self):
        rows = [{'date': '2020-01-01', 'value': 1}, {'date': '2020-04-01', 'value': 2},  # quarterly
                {'date': '2023-09-08', 'value': 3}, {'date': '2023-09-11', 'value': 4},  # daily (weekend gap)
                {'date': '2023-09-12', 'value': 5}]
        self.assertEqual([r['date'] for r in daily_suffix(rows)], ['2023-09-08', '2023-09-11', '2023-09-12'])

    def test_all_coarse_or_single_row_yields_nothing(self):
        self.assertEqual(daily_suffix([{'date': '2020-01-01', 'value': 1}, {'date': '2020-04-01', 'value': 2}]), [])
        self.assertEqual(daily_suffix([{'date': '2020-01-01', 'value': 1}]), [])

    def test_real_archive_contributes_only_daily_rows(self):
        archive = json.loads((ROOT / 'market-observatory/data/history-30y.json').read_text(encoding='utf-8'))
        for key in ('NASDAQ100', 'VIX'):
            rows = daily_suffix(archive['series'][key])
            self.assertTrue(rows)
            self.assertGreaterEqual(rows[0]['date'], '2023-09-01', key)


class PublishedComparisonTest(unittest.TestCase):
    def test_no_quarter_start_spike_reversals(self):
        """Lookahead signature: a period-start row jumps and the next day undoes it."""
        rows = json.loads((ROOT / 'market-observatory/data/tripod-comparison.json').read_text(encoding='utf-8'))['rows']
        bad = []
        for prev, cur, nxt in zip(rows, rows[1:], rows[2:]):
            r1, r2 = cur[1] / prev[1] - 1, nxt[1] / cur[1] - 1
            period_start = cur[0][:7] != prev[0][:7]
            if period_start and abs(r1) > 0.08 and r1 * r2 < 0 and abs(r2) > 0.07:
                bad.append(cur[0])
        self.assertEqual(bad, [])


class SourceProvenanceTest(unittest.TestCase):
    def test_month_start_archive_future_close_cannot_enter_daily_replay(self):
        # Example: archive month-start row is really month-end VIX (lookahead).
        mixed_archive = {'2023-09-01': 987.65, '2023-10-01': 999.99}
        independent_daily = {'2023-09-01': [16.5, 16.5],
                             '2023-09-05': [18.2, 18.2]}
        canonical = [{'date': '2023-09-06', 'value': 17.4}]
        rows = verified_daily_signal_rows(independent_daily, canonical)
        self.assertEqual(rows['2023-09-01']['value'], 16.5)
        self.assertEqual(rows['2023-09-05']['value'], 18.2)
        self.assertEqual(rows['2023-09-06']['value'], 17.4)
        self.assertTrue(all(item['value'] not in mixed_archive.values()
                            for item in rows.values()))

    def test_vix_daily_variation_not_overwritten_by_monthly_archive(self):
        dates = ['2023-09-01', '2023-09-05', '2023-09-06',
                 '2023-09-07', '2023-09-08', '2023-09-11',
                 '2023-09-12', '2023-09-13', '2023-09-14', '2023-09-15']
        vix_daily = {day: [14 + i * .5, 14 + i * .5] for i, day in enumerate(dates)}
        result = verified_daily_signal_rows(vix_daily, [])
        vix10 = sum(result[d]['value'] for d in dates) / 10
        self.assertAlmostEqual(vix10, 16.25)
        self.assertNotEqual(vix10, 35.0)  # A monthly/period-end contamination.

    def test_short_yahoo_fallback_cannot_replace_long_history(self):
        old = {'schema': 'JJOONI_TRIPOD_COMPARISON_V1', 'rows': [
            ['2010-02-11'], ['2010-02-12'], ['2026-11-06']]}
        truncated = {'schema': 'JJOONI_TRIPOD_COMPARISON_V1', 'rows': [
            ['2023-09-08'], ['2026-11-06'], ['2026-11-09']]}
        with self.assertRaisesRegex(RuntimeError, 'DEGRADED'):
            require_full_coverage(old, truncated)

    def test_length_loss_also_fails_closed(self):
        old = {'schema': 'JJOONI_TRIPOD_COMPARISON_V1', 'rows': [
            ['2010-02-11'], ['2010-02-12'], ['2026-11-06']]}
        shorter = {'schema': 'JJOONI_TRIPOD_COMPARISON_V1', 'rows': [
            ['2010-02-11'], ['2026-11-09']]}
        with self.assertRaisesRegex(RuntimeError, 'DEGRADED'):
            require_full_coverage(old, shorter)

    def test_full_history_expansion_and_operator_explicit_trim(self):
        old = {'schema': 'JJOONI_TRIPOD_COMPARISON_V1', 'rows': [
            ['2010-02-11'], ['2010-02-12']]}
        extended = {'schema': 'JJOONI_TRIPOD_COMPARISON_V1', 'rows': [
            ['2010-02-11'], ['2010-02-12'], ['2026-11-09']]}
        self.assertIs(require_full_coverage(old, extended), extended)
        short = {'schema': 'JJOONI_TRIPOD_COMPARISON_V1', 'rows': [
            ['2026-11-09']]}
        self.assertIs(require_full_coverage(old, short, allow_explicit_shrink=True), short)


if __name__ == '__main__':
    unittest.main()
