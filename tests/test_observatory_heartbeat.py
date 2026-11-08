import pathlib
import sys
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import observatory_heartbeat_decision as hb  # noqa: E402

NOW = datetime(2026, 11, 8, 7, 0, tzinfo=timezone.utc)


def obs(quote_age_min):
    stamp = (NOW - timedelta(minutes=quote_age_min)).astimezone(timezone(timedelta(hours=9))).isoformat()
    return {'crypto_market': {s: {'status': 'LIVE', 'quote_as_of_kst': stamp} for s in ('BTCUSD', 'ETHUSD')}}


class HeartbeatDecisionTest(unittest.TestCase):
    def run_decide(self, data):
        files = {'observatory.json': data}
        with mock.patch.object(hb, 'load', side_effect=lambda p: files.get(pathlib.Path(p).name, {})), \
             mock.patch.object(hb, 'refresh_decision', return_value={'should_refresh': False, 'age_min': 10}), \
             mock.patch.object(hb.sector_heartbeat_gate, 'should_refresh', return_value=False):
            return hb.decide(NOW)

    def test_stale_quote_requests_crypto_refresh(self):
        self.assertEqual(self.run_decide(obs(77))['crypto'], 'refresh')

    def test_fresh_quote_requests_nothing(self):
        d = self.run_decide(obs(10))
        self.assertEqual((d['crypto'], d['market']), ('ok', 'ok'))


class HeartbeatWorkflowContractTest(unittest.TestCase):
    def test_relay_never_writes_and_hands_over(self):
        wf = yaml.safe_load((ROOT / '.github/workflows/observatory-heartbeat.yml').read_text())
        self.assertEqual(wf['permissions'], {'contents': 'read', 'actions': 'write'})
        steps = wf['jobs']['relay']['steps']
        self.assertIn('gh workflow run observatory-heartbeat.yml', steps[-1]['run'])
        self.assertLess(int(wf['jobs']['relay']['env']['LOOP_SECONDS']) / 60, wf['jobs']['relay']['timeout-minutes'])

    def test_heartbeat_dispatch_runs_only_hourly_gate(self):
        text = (ROOT / '.github/workflows/market-observatory-daily.yml').read_text()
        wf = yaml.safe_load(text)
        self.assertIn("inputs.heartbeat", wf['jobs']['hourly_gate']['if'])
        self.assertIn("!(github.event_name == 'workflow_dispatch' && inputs.heartbeat)", wf['jobs']['build']['if'])


if __name__ == '__main__':
    unittest.main()
