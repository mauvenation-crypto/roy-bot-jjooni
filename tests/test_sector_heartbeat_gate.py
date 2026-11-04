import sys
import unittest
from datetime import datetime, timezone
sys.path.insert(0, 'tools')
from sector_heartbeat_gate import should_refresh

class SectorGateTest(unittest.TestCase):
    def test_after_us_close_requires_refresh(self):
        now = datetime.fromisoformat('2026-11-04T21:30:00+00:00')
        data = {'completed_cutoffs': {'KR': '2026-11-04', 'US': '2026-11-03'}}
        self.assertTrue(should_refresh(data, now))

    def test_same_cutoffs_healthy_does_not_refresh(self):
        now = datetime.fromisoformat('2026-11-04T21:30:00+00:00')
        data = {'completed_cutoffs': {'KR': '2026-11-04', 'US': '2026-11-04'}, 'generated_kst': '2026-11-05T06:20:00+09:00', 'groups': [{'rows': [{'observed_date': '2026-11-04'}]}]}
        self.assertFalse(should_refresh(data, now))
        data['quality'] = {'fetch_error_count': 1}
        self.assertFalse(should_refresh(data, now))
        data['generated_kst'] = '2026-11-05T05:40:00+09:00'
        self.assertTrue(should_refresh(data, now))

    def test_missing_snapshot_refreshes(self):
        self.assertTrue(should_refresh({}, datetime.now(timezone.utc)))

if __name__ == '__main__': unittest.main()
