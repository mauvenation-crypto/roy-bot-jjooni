"""MOF official current/historical JGB CSV merge: append-only provenance guards."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import build_market_observatory as mod

HISTORICAL = 'Date,2Y,5Y,10Y,30Y\n2026/09/30,1.2,1.5,2.0,3.0\n'
CURRENT = 'Date,2Y,5Y,10Y,30Y\n2026/09/30,9.9,9.9,9.9,9.9\n2026/10/30,1.3,1.6,2.1,3.1\n'

class MofCurrentCsvTests(unittest.TestCase):
    def test_append_new_official_dates_without_rewriting_archive(self):
        with patch.object(mod, 'get_text', side_effect=[HISTORICAL, CURRENT]):
            rows = mod.jgb_rows()
        self.assertEqual([r['date'] for r in rows], ['2026-09-30', '2026-10-30'])
        self.assertEqual(rows[0]['values']['10Y'], 2.0)
        self.assertEqual(rows[-1]['values']['10Y'], 2.1)

    def test_current_source_unavailable_preserves_archive(self):
        with patch.object(mod, 'get_text', side_effect=[HISTORICAL, OSError('offline')]):
            rows = mod.jgb_rows()
        self.assertEqual(rows[-1]['date'], '2026-09-30')

    def test_both_sources_unavailable_fails_closed(self):
        with patch.object(mod, 'get_text', side_effect=[OSError('offline'), OSError('offline')]):
            with self.assertRaisesRegex(RuntimeError, 'JGB_MOF_NO_OFFICIAL_ROWS'):
                mod.jgb_rows()

    def test_malformed_current_never_creates_observations(self):
        with patch.object(mod, 'get_text', side_effect=[HISTORICAL, '<html>blocked</html>']):
            rows = mod.jgb_rows()
        self.assertEqual(len(rows), 1)

    def test_published_jp_observations_are_not_rewritten(self):
        prior = {'series': {
            'JP2Y': [{'date':'2026-10-29','value':1.901}],
            'JP10Y': [{'date':'2026-10-29','value':2.876}],
            'JP_2S10S': [{'date':'2026-10-29','value':0.975}],
        }}
        official = [
            {'date':'2026-10-29','values':{'2Y':9.9,'5Y':2.285,'10Y':9.9,'30Y':3.956}},
            {'date':'2026-10-30','values':{'2Y':1.875,'5Y':2.237,'10Y':2.817,'30Y':3.908}},
        ]
        with patch.object(mod, 'treasury_rows', return_value=[]), \
             patch.object(mod, 'jgb_rows', return_value=official), \
             patch.object(mod, 'load_prev', return_value=prior):
            result = {}
            mod.add_official_yields(result)
        self.assertEqual(result['JP10Y'][-2]['value'], 2.876)
        self.assertEqual(result['JP10Y'][-1], {'date':'2026-10-30','value':2.817})
        self.assertEqual(result['JP2Y'][-2]['value'], 1.901)
        self.assertEqual(result['JP_2S10S'][-2]['value'], 0.975)
        self.assertAlmostEqual(result['JP_2S10S'][-1]['value'], 0.942)

    def test_future_dated_observations_are_ignored(self):
        future = 'Date,2Y,5Y,10Y,30Y\n2099/12/31,1,2,3,4\n'
        with patch.object(mod, 'get_text', side_effect=[HISTORICAL, future]):
            rows = mod.jgb_rows()
        self.assertEqual(len(rows), 1)

if __name__ == '__main__':
    unittest.main()
