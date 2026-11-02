"""Atomic publisher must not drop a newer official JGB date on concurrent rebase."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from publish_observatory_data import merge_generated

class JgbAtomicPublishTests(unittest.TestCase):
    def test_older_supplemental_attempt_cannot_erase_new_mof_date(self):
        remote={
            'us_completed_session_date':'2026-10-30',
            'generated_kst':'2026-11-02T08:44:00+09:00',
            'supplemental_refreshed_kst':'2026-11-02T08:44:00+09:00',
            'series':{'JP2Y':[{'date':'2026-10-29','value':1.901}],
                      'JP10Y':[{'date':'2026-10-29','value':2.876}],
                      'JP5Y':[{'date':'2026-10-29','value':2.285}],
                      'JP30Y':[{'date':'2026-10-29','value':3.956}]},
            'latest':{'JP2Y':1.901,'JP10Y':2.876},
            'cross_market_freshness_quality':{'JP_RATES':{'status':'LAGGING','last_date':'2026-10-29','expected_latest_weekday':'2026-10-30','source_url':'old-mirror'}},
        }
        local={
            'us_completed_session_date':'2026-10-30',
            'generated_kst':'2026-11-02T11:39:00+09:00',
            'series':{'JP2Y':[{'date':'2026-10-29','value':9.999},{'date':'2026-10-30','value':1.875}],
                      'JP10Y':[{'date':'2026-10-29','value':9.999},{'date':'2026-10-30','value':2.817}],
                      'JP5Y':[{'date':'2026-10-29','value':9.999},{'date':'2026-10-30','value':2.237}],
                      'JP30Y':[{'date':'2026-10-29','value':9.999},{'date':'2026-10-30','value':3.908}]},
            'latest':{'JP2Y':1.875,'JP10Y':2.817},
        }
        result=merge_generated('market-observatory/data/observatory.json',local,remote)
        self.assertEqual(result['series']['JP10Y'],[
            {'date':'2026-10-29','value':2.876},
            {'date':'2026-10-30','value':2.817},
        ])
        self.assertEqual(result['latest']['JP10Y'],2.817)
        self.assertEqual(result['latest']['JP2Y'],1.875)
        quality=result['cross_market_freshness_quality']['JP_RATES']
        self.assertEqual(quality['status'],'LIVE')
        self.assertEqual(quality['last_date'],'2026-10-30')
        self.assertNotIn('source_url',quality)

if __name__=='__main__':
    unittest.main()
