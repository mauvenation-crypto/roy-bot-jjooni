import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import publish_observatory_data as pub


class ObservatoryPublisherCleanlinessTest(unittest.TestCase):
    def test_market_source_always_publishes_atomic_health(self):
        source = 'market-observatory/data/observatory.json'
        audit = 'market-observatory/data/data-audit.json'
        status = 'market-observatory/data/freshness-status.json'
        # A crypto-only writer must not rely on a subsequent GitHub Actions
        # push trigger to update the published quote timestamps and verdict.
        self.assertEqual(pub.publication_paths([source]), [source, audit, status])
        self.assertEqual(pub.publication_paths([source, status]), [source, status, audit])
        self.assertEqual(len(pub.publication_paths([source, audit, status])), 3)
        # The canonical market consumers must be derived from the same source.
        bundle = pub.publication_paths(['public-market-daily.json'])
        self.assertTrue({source, audit, status, 'public-market-daily.json',
                         'market-observatory/data/daily-market-pulse.json'}.issubset(set(bundle)))

    def test_calendar_only_does_not_claim_unrelated_market_health(self):
        calendar = 'market-observatory/data/economic-calendar.json'
        self.assertEqual(pub.publication_paths([calendar]), [calendar])

    def test_unselected_generated_json_is_restored_before_rebase(self):
        calls=[]
        old=pub.git
        def fake_git(*args,check=True):
            calls.append(args)
            if args[:2]==('status','--porcelain=v1'):
                return SimpleNamespace(stdout=' M market-observatory/data/economic-calendar-history.json\n',stderr='',returncode=0)
            return SimpleNamespace(stdout='',stderr='',returncode=0)
        try:
            pub.git=fake_git
            discarded=pub.clean_unselected_generated(['market-observatory/data/observatory.json'])
        finally:
            pub.git=old
        self.assertEqual(discarded,['market-observatory/data/economic-calendar-history.json'])
        self.assertIn(('restore','--worktree','--','market-observatory/data/economic-calendar-history.json'),calls)

    def test_python_cache_artifacts_are_disposable(self):
        old=pub.git
        def fake_git(*args,check=True):
            if args[:2]==('status','--porcelain=v1'):
                return SimpleNamespace(
                    stdout='?? tests/__pycache__/test_x.cpython-312.pyc\n?? tools/__pycache__/x.cpython-312.pyc\n',
                    stderr='',returncode=0)
            return SimpleNamespace(stdout='',stderr='',returncode=0)
        try:
            pub.git=fake_git
            discarded=pub.clean_unselected_generated(['market-observatory/data/observatory.json'])
        finally:
            pub.git=old
        self.assertEqual(len(discarded),2)
        self.assertTrue(all(pub.is_ephemeral_build_artifact(x) for x in discarded))

    def test_non_generated_dirty_file_still_fails_closed(self):
        old=pub.git
        def fake_git(*args,check=True):
            if args[:2]==('status','--porcelain=v1'):
                return SimpleNamespace(stdout=' M market-observatory/index.html\n',stderr='',returncode=0)
            return SimpleNamespace(stdout='',stderr='',returncode=0)
        try:
            pub.git=fake_git
            with self.assertRaisesRegex(RuntimeError,'index.html'):
                pub.clean_unselected_generated(['market-observatory/data/observatory.json'])
        finally:
            pub.git=old

    def test_selected_dirty_payload_is_not_silently_discarded(self):
        old=pub.git
        def fake_git(*args,check=True):
            if args[:2]==('status','--porcelain=v1'):
                return SimpleNamespace(stdout=' M market-observatory/data/observatory.json\n',stderr='',returncode=0)
            return SimpleNamespace(stdout='',stderr='',returncode=0)
        try:
            pub.git=fake_git
            with self.assertRaisesRegex(RuntimeError,'observatory.json'):
                pub.clean_unselected_generated(['market-observatory/data/observatory.json'])
        finally:
            pub.git=old


if __name__=='__main__':
    unittest.main()


class CanonicalCalendarSerializationTest(__import__('unittest').TestCase):
    def test_calendar_files_ignore_key_order_but_keep_arrays(self):
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
        from publish_observatory_data import serialize
        a = {'series': {'x': {'rows': [{'date': '1', 'source_tier': 'OFFICIAL', 'value_vintage': 'AS_RELEASED'},
                                       {'date': '2'}]}}, 'schema': 'S'}
        b = {'schema': 'S', 'series': {'x': {'rows': [{'value_vintage': 'AS_RELEASED', 'date': '1', 'source_tier': 'OFFICIAL'},
                                                      {'date': '2'}]}}}
        for path in ('market-observatory/data/economic-calendar-history.json', 'market-observatory/data/economic-calendar.json'):
            self.assertEqual(serialize(path, a), serialize(path, b))
        self.assertLess(serialize('market-observatory/data/economic-calendar.json', a).index('"1"'),
                        serialize('market-observatory/data/economic-calendar.json', a).index('"2"'))
        # Other files keep writer order.
        self.assertNotEqual(serialize('market-observatory/data/observatory.json', a),
                            serialize('market-observatory/data/observatory.json', b))
