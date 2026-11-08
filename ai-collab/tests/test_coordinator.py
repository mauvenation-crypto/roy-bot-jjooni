import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from coordinator import parse_comment, summarize, template, validate_task

SHA_A = "a" * 40
SHA_B = "b" * 40


def task(**changes):
    t = {
        "schema": "JJOONI_COLLAB_V4",
        "task_id": "D-COLLAB-EVERGREEN",
        "repository": "mauveplace/jjooni-control-tower",
        "base_branch": "main",
        "source_sha": None,
        "objective": "Audit a public-only repo task",
        "mode": "SYSTEM_REVIEW_ONLY",
        "privacy": "PUBLIC_DATA_ONLY",
        "required_reviewers": ["ROY"],
        "optional_reviewers": ["JJANGGU"],
        "acceptance": ["Report source-grounded findings"],
        "release_gate": "USER_APPROVAL_REQUIRED",
    }
    t.update(changes)
    return t


def comment(actor, head=SHA_A, cid=101, task_id="D-COLLAB-EVERGREEN"):
    x = task(task_id=task_id)
    body = template(x, actor, head).replace(
        "Verdict: [PASS / NEEDS_CHANGES / BLOCKED]", "Verdict: PASS"
    )
    return {"id": cid, "body": body, "user": {"login": "mauveplace"}}


class EvergreenContractTests(unittest.TestCase):
    def test_one_required_actor_does_not_wait_for_optional_gemini(self):
        s = summarize(task(), [comment("ROY")], SHA_A)
        self.assertEqual(s["state"], "AWAITING_SOURCE_VERIFICATION")
        self.assertEqual(s["missing_reviewers"], [])
        self.assertFalse(s["authenticated_agent_origin"])
        self.assertFalse(s["safe_to_merge"])

    def test_future_head_is_not_hardcoded(self):
        reviews = [comment("ROY", SHA_A, 1), comment("ROY", SHA_B, 2)]
        self.assertEqual(len(summarize(task(), reviews, SHA_A)["review_claims"]), 1)
        self.assertEqual(len(summarize(task(), reviews, SHA_B)["review_claims"]), 1)

    def test_unseen_head_requires_new_review(self):
        s = summarize(task(), [comment("ROY", SHA_A)], SHA_B)
        self.assertEqual(s["state"], "WAITING_FOR_REQUIRED_REVIEWERS")
        self.assertEqual(s["missing_reviewers"], ["ROY"])

    def test_duplicate_claims_do_not_auto_approve(self):
        s = summarize(task(), [comment("ROY", cid=1), comment("ROY", cid=2)], SHA_A)
        self.assertEqual(s["state"], "DUPLICATE_CLAIMS_REVIEW_REQUIRED")
        self.assertFalse(s["safe_to_merge"])

    def test_another_task_is_not_this_task(self):
        s = summarize(task(), [comment("ROY", task_id="D-OTHER")], SHA_A)
        self.assertEqual(s["missing_reviewers"], ["ROY"])

    def test_jjooni_independent_review_cannot_impersonate_roy(self):
        s = summarize(task(), [comment("JJOONI")], SHA_A)
        self.assertEqual(s["missing_reviewers"], ["ROY"])
        self.assertEqual(s["review_claims"][0]["actor_claim"], "JJOONI")

    def test_invalid_marker_or_empty_body_ignored(self):
        self.assertIsNone(parse_comment({"body": None}))
        self.assertIsNone(parse_comment({"body": "ROY / REVIEW\nNo marker"}))
        self.assertIsNone(parse_comment({"body": template(task(), "ROY", SHA_A).split("\n")[0] + "\n"}))
        self.assertIsNone(parse_comment({"body": template(task(), "ROY", SHA_A).replace("actor=ROY stage=review", "actor=ROY stage=independent-review")}))

    def test_invalid_head_and_wrong_task_id_type_fail_closed(self):
        for head in (None, 3, "", "a" * 39):
            with self.subTest(head=head), self.assertRaises(ValueError):
                summarize(task(), [], head)
            with self.subTest(head=head), self.assertRaises(ValueError):
                template(task(), "ROY", head)
        for task_id in (3, None, ["bad"]):
            with self.subTest(task_id=task_id), self.assertRaises(ValueError):
                validate_task(task(task_id=task_id))

    def test_invalid_task_denied(self):
        for patch in (
            {"privacy": "PRIVATE_DATA"},
            {"repository": "untrusted/repo"},
            {"base_branch": "production"},
            {"required_reviewers": ["ROY", "ROY"]},
            {"required_reviewers": ["ROY"], "optional_reviewers": ["ROY"]},
            {"mode": "AUTO_TRADE"},
            {"release_gate": "AUTO_MERGE"},
            {"source_sha": "short"},
        ):
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                validate_task(task(**patch))

    def test_untrusted_pr_task_never_authorizes_code_edits(self):
        with self.assertRaises(ValueError):
            validate_task(task(mode="PR_BRANCH_EDIT_APPROVED"))
        with self.assertRaises(ValueError):
            validate_task(task(mode="PR_BRANCH_EDIT_APPROVED", owner_approval_evidence="https://github.com/mauveplace/jjooni-control-tower/issues/1"))

    def test_outside_author_cannot_suppress_roy_review(self):
        spoof = comment("ROY")
        spoof["user"] = {"login": "random-outsider"}
        status = summarize(task(), [spoof], SHA_A)
        self.assertEqual(status["missing_reviewers"], ["ROY"])
        self.assertEqual(len(status["review_claims"]), 0)
        self.assertEqual(len(status["ignored_untrusted_claims"]), 1)

    def test_placeholder_and_unhashable_reviewers_rejected(self):
        for patch in ({"task_id": "REPLACE-WITH-UNIQUE-TASK-ID"},
                      {"required_reviewers": [{}]},
                      {"optional_reviewers": [{}]}):
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                validate_task(task(**patch))

    def test_marker_header_matches_roy_pr_contract(self):
        self.assertIn("## ROY / REVIEW", template(task(), "ROY", SHA_A))
        self.assertIn("## JJOONI / INDEPENDENT REVIEW", template(task(), "JJOONI", SHA_A))

    def test_reviewer_list_can_expand_later(self):
        t = task(required_reviewers=["ROY", "JJANGGU"], optional_reviewers=[])
        self.assertEqual(summarize(t, [comment("ROY")], SHA_A)["missing_reviewers"], ["JJANGGU"])
        r = summarize(t, [comment("ROY"), comment("JJANGGU", cid=102)], SHA_A)
        self.assertEqual(r["missing_reviewers"], [])
        self.assertEqual(r["state"], "AWAITING_SOURCE_VERIFICATION")


if __name__ == "__main__":
    unittest.main()
