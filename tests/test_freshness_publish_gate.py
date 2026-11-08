import copy
import pathlib
import sys
import unittest
from datetime import datetime, timedelta, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from freshness_publish_gate import decide  # noqa: E402

NOW = datetime(2026, 11, 8, 8, 30, tzinfo=timezone.utc)
KST = timezone(timedelta(hours=9))


def docs(minutes_ago, crypto='LIVE', critical=0):
    stamp = (NOW - timedelta(minutes=minutes_ago)).astimezone(KST).isoformat()
    f = {'generated_kst': stamp, 'overall': 'LIVE', 'groups': {
        'crypto': {'state': crypto, 'detail': f'BTCUSD age={minutes_ago}s', 'generated_kst': stamp,
                   'quotes': {'BTCUSD': {'status': crypto, 'quote_as_of_kst': stamp}}}}}
    a = {'generated_kst': stamp, 'overall': 'PASS', 'critical_count': critical, 'issues': [],
         'groups': {'fx': {'state': 'LIVE', 'anchor': '2026-11-06'}}}
    return f, a


class FreshnessPublishGateTest(unittest.TestCase):
    def test_only_clock_and_age_changed_is_skipped(self):
        old_f, old_a = docs(10)
        new_f, new_a = docs(0)
        self.assertEqual(decide(new_f, new_a, old_f, old_a, NOW)[0], False)

    def test_state_change_publishes(self):
        old_f, old_a = docs(10)
        new_f, new_a = docs(0, crypto='STALE')
        self.assertEqual(decide(new_f, new_a, old_f, old_a, NOW), (True, 'freshness state changed'))

    def test_audit_change_publishes(self):
        old_f, old_a = docs(10)
        new_f, new_a = docs(0, critical=1)
        self.assertEqual(decide(new_f, new_a, old_f, old_a, NOW), (True, 'audit state changed'))

    def test_old_committed_check_publishes(self):
        old_f, old_a = docs(31)
        new_f, new_a = docs(0)
        self.assertTrue(decide(new_f, new_a, old_f, old_a, NOW)[0])

    def test_missing_committed_files_publish(self):
        new_f, new_a = docs(0)
        self.assertTrue(decide(new_f, new_a, None, None, NOW)[0])


if __name__ == '__main__':
    unittest.main()
