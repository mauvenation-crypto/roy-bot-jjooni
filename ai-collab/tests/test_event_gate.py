"""Isolated, synthetic event and regression test matrix. No remote API calls."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from coordinator import template
from event_gate import active_task_path, bound_task_path, decide_event

SHA_A = "a" * 40
SHA_B = "b" * 40
SHA_C = "c" * 40
REPO = "mauveplace/jjooni-control-tower"


def task(**kwargs):
    d = {
        "schema": "JJOONI_COLLAB_V4",
        "task_id": "D-EXAMPLE",
        "repository": REPO,
        "base_branch": "main",
        "source_sha": None,
        "objective": "Verify changes without touching main",
        "mode": "SYSTEM_REVIEW_ONLY",
        "privacy": "PUBLIC_DATA_ONLY",
        "required_reviewers": ["ROY"],
        "optional_reviewers": ["JJANGGU"],
        "acceptance": ["Show reproducible evidence"],
        "release_gate": "USER_APPROVAL_REQUIRED",
    }
    d.update(kwargs)
    return d


def pr(head=SHA_A, title="[AI-COLLAB] source review"):
    return {"number": 432, "state": "open", "title": title,
            "base": {"ref": "main"}, "head": {"sha": head}}


def repo_event(**kwargs):
    d = {"repository": {"full_name": REPO}, "sender": {"login": "mauveplace"}}
    d.update(kwargs)
    return d


def comment_event(actor="ROY", head=SHA_A, cid=123, *, name="issue_comment"):
    body = template(task(), actor, head)
    raw = {"id": cid, "body": body, "user": {"login": "mauveplace"},
           "commit_id": head}
    if name == "issue_comment":
        return repo_event(action="created", issue={"number": 432, "pull_request": {"url": "https://api.github.com/foo"}},
                          comment=raw)
    if name == "pull_request_review_comment":
        return repo_event(action="created", pull_request={"number": 432}, comment=raw)
    return repo_event(action="submitted", pull_request={"number": 432}, review=raw)


def pull_event(action, head=SHA_A, **props):
    event = repo_event(action=action, pull_request={"number": 432, "head": {"sha": head}})
    event.update(props)
    return event


class EventGateTests(unittest.TestCase):
    def decide(self, name, event, current_pr=None, **kwargs):
        return decide_event(name, event, current_pr or pr(), task(), **kwargs)

    def test_new_pr_waits_for_roy(self):
        out = self.decide("pull_request", pull_event("opened"))
        self.assertEqual(out["decision"], "WAIT_ROY")
        self.assertFalse(out["safe_to_merge"])

    def test_new_comment_claim_requires_real_agent_provenance(self):
        out = self.decide("issue_comment", comment_event())
        self.assertEqual(out["decision"], "VERIFY_ROY")
        self.assertFalse(out["agent_authenticated"])

    def test_stale_comment_does_not_review_new_head(self):
        out = self.decide("issue_comment", comment_event(head=SHA_A),
                          current_pr=pr(SHA_B))
        self.assertEqual(out["decision"], "STALE")

    def test_duplicate_raw_comment_id_does_not_replay(self):
        ev = comment_event(cid=8722)
        old = self.decide("issue_comment", ev)
        newer = self.decide("issue_comment", ev, current_pr=pr(SHA_B),
                            known_event_keys={old["event_key"]})
        self.assertEqual(newer["decision"], "DUPLICATE")

    def test_self_comment_ignored(self):
        self.assertEqual(self.decide("issue_comment", comment_event("JJOONI"))["decision"], "IGNORE")

    def test_untrusted_commenter_cannot_claim_roy(self):
        ev = comment_event()
        ev["sender"]["login"] = ev["comment"]["user"]["login"] = "random-outsider"
        self.assertEqual(self.decide("issue_comment", ev)["decision"], "UNTRUSTED")

    def test_mismatched_sender_and_comment_author_blocked(self):
        ev = comment_event()
        ev["sender"]["login"] = "random-outsider"
        self.assertEqual(self.decide("issue_comment", ev)["decision"], "BLOCKED")

    def test_probe_is_not_code_review(self):
        ev = comment_event()
        ev["comment"]["body"] = "JJOONI GitHub webhook test\n<!-- JJOONI-COLLAB-PROBE-V4-TEST -->"
        out = self.decide("issue_comment", ev)
        self.assertEqual(out["decision"], "PROBE")
        self.assertFalse(out["safe_to_merge"])

    def test_non_pr_issue_comment_ignored(self):
        ev = comment_event()
        ev["issue"].pop("pull_request")
        self.assertEqual(self.decide("issue_comment", ev)["decision"], "IGNORE")

    def test_pr_number_mismatch_blocked(self):
        ev = comment_event()
        ev["issue"]["number"] = 999
        self.assertEqual(self.decide("issue_comment", ev)["decision"], "BLOCKED")

    def test_unsubscribed_title_ignored(self):
        self.assertEqual(self.decide("issue_comment", comment_event(),
                                     current_pr=pr(title="Not an AI collaboration task"))["decision"], "IGNORE")

    def test_other_repo_ignored(self):
        ev = comment_event()
        ev["repository"]["full_name"] = "outsider/fork"
        self.assertEqual(self.decide("issue_comment", ev)["decision"], "IGNORE")

    def test_review_submission_as_distinct_id(self):
        out = self.decide("pull_request_review", comment_event(name="pull_request_review"))
        self.assertEqual(out["decision"], "VERIFY_ROY")

    def test_old_review_commit_stale(self):
        ev = comment_event(name="pull_request_review")
        self.assertEqual(self.decide("pull_request_review", ev, current_pr=pr(SHA_B))["decision"], "STALE")

    def test_inline_review_comment(self):
        ev = comment_event(name="pull_request_review_comment")
        self.assertEqual(self.decide("pull_request_review_comment", ev)["decision"], "VERIFY_ROY")

    def test_ignore_unsubscribed_comment_edit(self):
        ev = comment_event()
        ev["action"] = "edited"
        self.assertEqual(self.decide("issue_comment", ev)["decision"], "IGNORE")

    def test_roy_is_not_dispatched_when_only_jjanggu_required(self):
        jj = task(required_reviewers=["JJANGGU"], optional_reviewers=["ROY"])
        self.assertEqual(decide_event("pull_request", pull_event("opened"), pr(), jj)["decision"], "IGNORE")
        label = pull_event("labeled", label={"name": "ai-collab:roy-request"})
        self.assertEqual(decide_event("pull_request", label, pr(), jj)["decision"], "IGNORE")

    def test_roy_label_only_from_owner(self):
        e = pull_event("labeled", label={"name": "ai-collab:roy-request"})
        self.assertEqual(self.decide("pull_request", e)["decision"], "REQUEST_ROY")
        e["sender"]["login"] = "another-user"
        self.assertEqual(self.decide("pull_request", e)["decision"], "UNTRUSTED")

    def test_wrong_label_ignored(self):
        e = pull_event("labeled", label={"name": "no-op"})
        self.assertEqual(self.decide("pull_request", e)["decision"], "IGNORE")

    def test_changed_head_requires_actual_tree_change_proof(self):
        e = pull_event("synchronize", head=SHA_B, before=SHA_A, after=SHA_B)
        self.assertEqual(self.decide("pull_request", e, current_pr=pr(SHA_B))["decision"], "NEED_EVIDENCE")
        self.assertEqual(self.decide("pull_request", e, current_pr=pr(SHA_B), tree_changed=False)["decision"], "IGNORE")
        self.assertEqual(self.decide("pull_request", e, current_pr=pr(SHA_B), tree_changed=True)["decision"], "REVIEW_CHANGED_HEAD")

    def test_malformed_or_outdated_synchronize_does_not_execute(self):
        e = pull_event("synchronize", head=SHA_A, before=SHA_A, after=SHA_C)
        self.assertEqual(self.decide("pull_request", e)["decision"], "NEED_EVIDENCE")
        self.assertEqual(self.decide("pull_request", e, current_pr=pr(SHA_C))["decision"], "STALE")

    def test_probe_substring_is_not_accepted_as_probe(self):
        ev = comment_event()
        ev["comment"]["body"] = "Text containing JJOONI-COLLAB-PROBE but no valid marker"
        self.assertEqual(self.decide("issue_comment", ev)["decision"], "IGNORE")

    def test_task_file_must_match_task_id(self):
        path = "ai-collab-dispatch/tasks/D-EXAMPLE.json"
        self.assertEqual(bound_task_path([path], task()), path)
        with self.assertRaises(ValueError):
            bound_task_path([path], task(task_id="D-DIFFERENT"))

    def test_task_path_disambiguation(self):
        paths = ["ai-collab-dispatch/tasks/TEMPLATE.json",
                 "ai-collab-dispatch/tasks/D-EXAMPLE.json"]
        self.assertEqual(active_task_path(paths), paths[1])
        for bad in ([paths[0]], paths + ["ai-collab-dispatch/tasks/D-SECOND.json"],
                    ["ai-collab-dispatch/tasks/../../evil.json"]):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                active_task_path(bad)

    def test_no_implicit_merge_or_trade_for_any_event(self):
        samples = [
            self.decide("pull_request", pull_event("opened")),
            self.decide("issue_comment", comment_event()),
            self.decide("pull_request", pull_event("synchronize", head=SHA_B,
                       before=SHA_A, after=SHA_B), current_pr=pr(SHA_B), tree_changed=True)
        ]
        for x in samples:
            self.assertFalse(x["safe_to_merge"])
            self.assertFalse(x["safe_to_deploy"])
            self.assertFalse(x["safe_to_trade"])


if __name__ == "__main__":
    unittest.main()
