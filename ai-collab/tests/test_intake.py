import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from intake import canonical_text, fingerprint, intake_key, reconcile


def record(key, text, origin="USER_TO_ROY", category="backend", scope="public repo"):
    return {"key": key, "fingerprint": fingerprint(objective=text, work_type=category, scope=scope),
            "origin": origin}


class IntakeTests(unittest.TestCase):
    def test_either_origin_same_anchor_is_one_work_order(self):
        first = record("repo#issue:123", "Investigate GitHub event limits")
        second = record("repo#issue:123", "Investigate GitHub event limits", origin="USER_TO_JJOONI")
        self.assertEqual(reconcile(second, [first])["decision"], "SAME_WORK_ORDER")

    def test_duplicate_objective_different_anchors_needs_review(self):
        first = record("repo#issue:123", "  Fix  concurrency   guards ")
        second = record("repo#pr:412", "fix CONCURRENCY guards", origin="USER_TO_JJOONI")
        self.assertEqual(reconcile(second, [first])["decision"], "POSSIBLE_DUPLICATE")

    def test_same_anchor_conflicting_objective_is_blocked(self):
        first = record("repo#issue:123", "Audit a bug")
        second = record("repo#issue:123", "Rewrite production")
        self.assertEqual(reconcile(second, [first])["decision"], "CONFLICT")
        self.assertFalse(reconcile(second, [first])["safe_to_merge"])

    def test_new_work_is_not_silent_merge(self):
        new = record("repo#pr:777", "Refactor the UI")
        self.assertEqual(reconcile(new, [])["decision"], "NEW_INTAKE")
        self.assertFalse(reconcile(new, [])["safe_to_merge"])

    def test_fingerprint_is_stable_across_whitespace_and_case(self):
        a = fingerprint(objective="Analyse GitHub  retries", work_type="architecture", scope="Public repo")
        b = fingerprint(objective="analyse github retries", work_type="architecture", scope="public   REPO")
        self.assertEqual(a, b)

    def test_fingerprint_changes_with_scope_or_work_type(self):
        a = fingerprint(objective="One task", work_type="backend", scope="public repo")
        b = fingerprint(objective="One task", work_type="frontend", scope="public repo")
        c = fingerprint(objective="One task", work_type="backend", scope="private repo")
        self.assertNotEqual(a, b)
        self.assertNotEqual(a, c)

    def test_intake_anchor_validation(self):
        repo = "mauveplace/jjooni-control-tower"
        self.assertEqual(intake_key(repo, "issue:123"), repo+"#issue:123")
        for invalid in ("https://attacker.invalid", "issue:0", "pr:abc", "issue:-1"):
            with self.subTest(value=invalid), self.assertRaises(ValueError):
                intake_key(repo, invalid)

    def test_untrusted_origin_rejected(self):
        with self.assertRaises(ValueError):
            reconcile(record("repo#pr:1","Audit"), [{"key": "okay"}])
        with self.assertRaises(ValueError):
            reconcile({**record("repo#pr:1", "Audit"), "origin": "UNLIMITED_ACCESS"}, [])

    def test_no_semantic_equivalence_is_claimed(self):
        first = record("repo#pr:1","Review a historical backtest")
        second = record("repo#pr:2","Validate a strategy's past performance")
        self.assertEqual(reconcile(second, [first])["decision"], "NEW_INTAKE")


if __name__ == "__main__":
    unittest.main()
