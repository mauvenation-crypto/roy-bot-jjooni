import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from issue_dispatch import decide, parse_request, ISSUE_MARKER, TITLE_PREFIX

SHA="a"*40
REPO="mauveplace/jjooni-control-tower"
def pr(head=SHA):
    return {"number":310,"title":"[AI-COLLAB] review","state":"open",
            "base":{"ref":"main"},"head":{"sha":head}}
def ev(body=None,title=None,number=345,id=82312):
    if body is None:
        body=(ISSUE_MARKER+"\nTarget-PR: 310\nTask-ID: D-TEST-010\n"
              "Expected-HEAD: "+SHA+"\nMode: SYSTEM_REVIEW_ONLY\n"
              "Requested-By: JJOONI\nScope: Independent code audit and test report")
    return {"action":"opened","repository":{"full_name":REPO},
            "sender":{"login":"mauveplace"},
            "issue":{"id":id,"number":number,"user":{"login":"mauveplace"},
                     "title":title or TITLE_PREFIX+"PR 310 review",
                     "body":body}}
class IssueDispatchTests(unittest.TestCase):
    def test_valid_followup_issue_is_read_only_request(self):
        result=decide(ev(),pr())
        self.assertEqual(result["decision"],"REQUEST_ROY_REVIEW")
        self.assertFalse(result["execution_confirmed"])
        self.assertFalse(result["merge_allowed"])
        self.assertEqual(result["target_pr"],310)

    def test_unrelated_open_issue_ignored(self):
        self.assertEqual(decide(ev(title="Bug report"),pr())["decision"],"IGNORE")

    def test_replay_issue_deduped(self):
        self.assertEqual(decide(ev(),pr(),known_issue_ids={82312})["decision"],"DUPLICATE")

    def test_pr_update_makes_old_issue_stale(self):
        self.assertEqual(decide(ev(),pr("b"*40))["decision"],"STALE")

    def test_non_owner_issue_does_not_dispatch(self):
        x=ev();x["sender"]["login"]=x["issue"]["user"]["login"]="attacker"
        self.assertEqual(decide(x,pr())["decision"],"UNTRUSTED")

    def test_sender_mismatch_denied(self):
        x=ev();x["sender"]["login"]="attacker"
        self.assertEqual(decide(x,pr())["decision"],"UNTRUSTED")

    def test_unexpected_mode_does_not_grant_code_edit(self):
        s=ev()["issue"]["body"].replace("SYSTEM_REVIEW_ONLY","PR_BRANCH_EDIT_APPROVED")
        self.assertEqual(decide(ev(body=s),pr())["decision"],"BLOCKED")

    def test_bad_sha_rejected(self):
        s=ev()["issue"]["body"].replace(SHA,"shortsha")
        self.assertEqual(decide(ev(body=s),pr())["decision"],"BLOCKED")

    def test_duplicate_fields_rejected(self):
        s=ev()["issue"]["body"]+"\nTarget-PR: 311"
        self.assertEqual(decide(ev(body=s),pr())["decision"],"BLOCKED")

    def test_missing_marker_rejected(self):
        s=ev()["issue"]["body"].replace(ISSUE_MARKER+"\n","")
        self.assertEqual(decide(ev(body=s),pr())["decision"],"BLOCKED")

    def test_not_open_event_ignored(self):
        x=ev();x["action"]="edited"
        self.assertEqual(decide(x,pr())["decision"],"IGNORE")

    def test_issue_reference_mismatch_blocked(self):
        x=ev();x["issue"]["body"]=x["issue"]["body"].replace("Target-PR: 310","Target-PR: 309")
        self.assertEqual(decide(x,pr())["decision"],"BLOCKED")

    def test_pr_closed_does_not_dispatch(self):
        x=pr();x["state"]="closed"
        self.assertEqual(decide(ev(),x)["decision"],"BLOCKED")

    def test_crlf_issue_is_accepted_with_strict_marker(self):
        original=ev()["issue"]["body"]
        converted=original.replace("\\n","\\r\\n")
        self.assertEqual(decide(ev(body=converted),pr())["decision"],"REQUEST_ROY_REVIEW")

    def test_marker_must_remain_exact_first_line_with_crlf(self):
        original=ev()["issue"]["body"].replace(ISSUE_MARKER, " " + ISSUE_MARKER)
        self.assertEqual(decide(ev(body=original.replace("\\n","\\r\\n")),pr())["decision"],"BLOCKED")

    def test_draft_pr_does_not_dispatch(self):
        target=pr(); target["draft"]=True
        self.assertEqual(decide(ev(),target)["decision"],"BLOCKED")

    def test_merged_pr_does_not_dispatch_even_with_stale_open_state(self):
        target=pr(); target["merged"]=True
        self.assertEqual(decide(ev(),target)["decision"],"BLOCKED")

    def test_not_collab_pr_does_not_dispatch(self):
        x=pr();x["title"]="regular PR"
        self.assertEqual(decide(ev(),x)["decision"],"BLOCKED")

    def test_PR_is_not_ordinary_issue(self):
        x=ev();x["issue"]["pull_request"]={"url":"https://api.github.com/repos/foo/pulls/1"}
        self.assertEqual(decide(x,pr())["decision"],"IGNORE")

    def test_invalid_original_issue_id_fails_closed(self):
        self.assertEqual(decide(ev(id=None),pr())["decision"],"BLOCKED")

if __name__=="__main__":
    unittest.main()
