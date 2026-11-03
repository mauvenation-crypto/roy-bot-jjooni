import sys
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from observatory_session import expected_completed_session,readiness,refresh_decision,require_current

ET=ZoneInfo('America/New_York');KST=ZoneInfo('Asia/Seoul')


def snapshot(day,stamp):
    obs={'generated_kst':stamp,'us_completed_session_date':day,
         'series':{k:[{'date':day,'value':100}] for k in ('NASDAQ100','SP500','VIX')}}
    return obs,{'market_date_us':day,'snapshot_status':'FINAL'},{'tripod_signal':{'date':day,'ok':True}}


class CompletedSessionRecoveryTests(unittest.TestCase):
    def test_incident_0514_kst_cannot_claim_todays_close_before_0515(self):
        self.assertEqual(expected_completed_session(datetime(2026,10,22,5,14,tzinfo=KST)),'2026-10-20')
        self.assertEqual(expected_completed_session(datetime(2026,10,22,5,15,tzinfo=KST)),'2026-10-21')

    def test_recently_generated_old_session_requires_immediate_recovery(self):
        args=snapshot('2026-10-20','2026-10-22T05:14:23+09:00')
        result=refresh_decision(*args,now=datetime(2026,10,22,5,26,tzinfo=KST))
        self.assertLess(result['age_min'],45)
        self.assertTrue(result['should_refresh']);self.assertFalse(result['healthy'])
        with self.assertRaisesRegex(ValueError,'NOT_CURRENT'):require_current(*args,now=datetime(2026,10,22,6,28,tzinfo=KST))

    def test_delayed_recovery_after_old_1705_deadline_remains_required(self):
        args=snapshot('2026-10-20','2026-10-21T17:25:00-04:00')
        self.assertTrue(refresh_decision(*args,now=datetime(2026,10,21,17,28,tzinfo=ET))['should_refresh'])
        args=snapshot('2026-10-21','2026-10-21T17:25:00-04:00')
        self.assertFalse(refresh_decision(*args,now=datetime(2026,10,21,17,28,tzinfo=ET))['should_refresh'])

    def test_aligned_prior_close_is_valid_while_us_market_is_open(self):
        args=snapshot('2026-10-20','2026-10-21T15:30:00-04:00')
        self.assertFalse(refresh_decision(*args,now=datetime(2026,10,21,15,40,tzinfo=ET))['should_refresh'])

    def test_header_cannot_hide_stale_core_bars(self):
        args=snapshot('2026-10-21','2026-10-21T17:25:00-04:00')
        args[0]['series']['VIX']=[{'date':'2026-10-20','value':17}]
        self.assertFalse(readiness(*args,now=datetime(2026,10,21,17,28,tzinfo=ET))['healthy'])

    def test_dst_and_standard_time_share_one_close_grace(self):
        self.assertEqual(expected_completed_session(datetime(2026,1,23,6,14,tzinfo=KST)),'2026-01-21')
        self.assertEqual(expected_completed_session(datetime(2026,1,23,6,15,tzinfo=KST)),'2026-01-22')

    def test_november_2026_dst_rollover_never_finalizes_at_old_kst_close(self):
        # 2026-11-02 is the first US cash session after DST ends on Nov 1.
        self.assertEqual(expected_completed_session(datetime(2026,11,3,5,40,tzinfo=KST)),'2026-10-30')
        self.assertEqual(expected_completed_session(datetime(2026,11,3,6,14,tzinfo=KST)),'2026-10-30')
        self.assertEqual(expected_completed_session(datetime(2026,11,3,6,15,tzinfo=KST)),'2026-11-02')
        args=snapshot('2026-11-02','2026-11-03T05:40:00+09:00')
        self.assertFalse(readiness(*args,now=datetime(2026,11,3,5,40,tzinfo=KST))['healthy'])
        self.assertTrue(readiness(*args,now=datetime(2026,11,3,6,40,tzinfo=KST))['healthy'])

    def test_holidays_weekends_and_bank_holidays(self):
        for day,expected in [('2026-04-03','2026-04-02'),('2026-06-19','2026-06-18'),
                             ('2026-10-25','2026-10-23'),('2026-10-12','2026-10-12'),
                             ('2026-11-11','2026-11-11'),('2027-12-31','2027-12-31')]:
            with self.subTest(day=day):self.assertEqual(expected_completed_session(datetime.fromisoformat(day+'T17:30:00').replace(tzinfo=ET)),expected)

    def test_early_close_uses_the_same_fifteen_minute_grace(self):
        self.assertEqual(expected_completed_session(datetime(2026,11,27,13,14,tzinfo=ET)),'2026-11-25')
        self.assertEqual(expected_completed_session(datetime(2026,11,27,13,15,tzinfo=ET)),'2026-11-27')


if __name__=='__main__':unittest.main()
