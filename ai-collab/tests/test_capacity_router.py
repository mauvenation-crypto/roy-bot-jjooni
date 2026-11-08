import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capacity_router import (check_transition, handoff_record,
                             normalized_capacity, route_task)

NOW = datetime(2026, 11, 8, 12, 0, tzinfo=timezone.utc)
SHA = "a" * 40


def evidence(actor, state, age=0, source=None, reset=None, verified=True):
    return {
        "actor": actor, "state": state, "verified": verified,
        "source": source or ("CLAUDE_RUN" if actor == "ROY" else "WORK_RUN"),
        "checked_at": (NOW - timedelta(minutes=age)).isoformat(),
        "limit_reset_at": reset,
    }


def route(origin="USER_TO_JJOONI", work_type="general", **kwargs):
    return route_task(origin=origin, work_type=work_type, now=NOW,
                      evidence_from_verified_runtime=True, **kwargs)


class RoutingTests(unittest.TestCase):
    def test_origin_does_not_lock_preferred_specialist(self):
        for origin in ("USER_TO_JJOONI", "USER_TO_ROY", "GITHUB_EVENT"):
            with self.subTest(origin=origin):
                self.assertEqual(route(origin, "backend")["preferred_agent"], "ROY")
                self.assertEqual(route(origin, "strategy_analysis")["preferred_agent"], "JJOONI")

    def test_known_available_specialist_selected(self):
        r = route(work_type="backend", capacities={"ROY": evidence("ROY", "AVAILABLE")})
        self.assertEqual(r["state"], "REQUESTED")
        self.assertEqual(r["assigned_agent"], "ROY")
        self.assertFalse(r["fallback_used"])
        self.assertFalse(r["safe_to_merge"])

    def test_roy_rate_limited_handoff_to_jjooni_read_only(self):
        a = {"ROY": evidence("ROY", "RATE_LIMITED"),
             "JJOONI": evidence("JJOONI", "AVAILABLE")}
        r = route(work_type="backend", origin="USER_TO_ROY", capacities=a)
        self.assertEqual(r["assigned_agent"], "JJOONI")
        self.assertEqual(r["independent_reviewer"], "ROY")
        self.assertTrue(r["fallback_used"])
        self.assertEqual(r["fallback_scope"], "READ_ONLY_PREPARATION")
        self.assertFalse(r["independent_review_completed"])

    def test_jjooni_rate_limited_handoff_to_roy_read_only(self):
        a = {"JJOONI": evidence("JJOONI", "RATE_LIMITED"),
             "ROY": evidence("ROY", "AVAILABLE")}
        r = route(work_type="strategy_analysis", capacities=a)
        self.assertEqual(r["assigned_agent"], "ROY")
        self.assertTrue(r["fallback_used"])
        self.assertTrue(r["owner_approval_required"])

    def test_no_evidence_is_unknown_not_available(self):
        r = route(work_type="backend")
        self.assertEqual(r["state"], "WAITING_EVENT")
        self.assertEqual(r["assigned_agent"], "ROY")
        self.assertEqual(r["capacity"]["ROY"]["state"], "UNKNOWN")

    def test_no_available_agents_keeps_task_pending(self):
        a = {"ROY": evidence("ROY", "RATE_LIMITED"),
             "JJOONI": evidence("JJOONI", "UNAVAILABLE")}
        r = route(capacities=a)
        self.assertEqual(r["state"], "WAITING_CAPACITY")
        self.assertIsNone(r["assigned_agent"])
        self.assertEqual(r["next_step"], "PRESERVE_AND_RETRY_WHEN_VERIFIED")

    def test_stale_quota_evidence_is_not_current(self):
        rec = evidence("ROY", "RATE_LIMITED", age=122)
        self.assertEqual(normalized_capacity("ROY", rec, now=NOW, trusted_runtime=True)["state"], "UNKNOWN")

    def test_expired_limit_reset_is_unconfirmed_not_available(self):
        rec = evidence("ROY", "RATE_LIMITED", reset=(NOW - timedelta(minutes=1)).isoformat())
        self.assertEqual(normalized_capacity("ROY", rec, now=NOW, trusted_runtime=True)["state"], "UNKNOWN")

    def test_untrusted_pr_json_even_with_verified_true_cannot_enable_capacity(self):
        rec = evidence("ROY", "AVAILABLE")
        self.assertEqual(normalized_capacity("ROY", rec, now=NOW)["state"], "UNKNOWN")
        decision = route_task(origin="USER_TO_ROY", work_type="backend",
                              capacities={"ROY": rec}, now=NOW)
        self.assertEqual(decision["capacity"]["ROY"]["state"], "UNKNOWN")
        self.assertEqual(decision["state"], "WAITING_EVENT")

    def test_unverified_owner_comment_cannot_claim_rate_limit(self):
        rec = evidence("ROY", "RATE_LIMITED", source="GITHUB_COMMENT")
        self.assertEqual(normalized_capacity("ROY", rec, now=NOW, trusted_runtime=True)["state"], "UNKNOWN")
        rec = evidence("ROY", "AVAILABLE", verified=False)
        self.assertEqual(normalized_capacity("ROY", rec, now=NOW, trusted_runtime=True)["state"], "UNKNOWN")

    def test_wrong_actor_evidence_rejected(self):
        rec = evidence("JJOONI", "AVAILABLE")
        self.assertEqual(normalized_capacity("ROY", rec, now=NOW, trusted_runtime=True)["state"], "UNKNOWN")

    def test_future_timestamp_does_not_enable_agent(self):
        rec = evidence("ROY", "AVAILABLE", age=-7)
        self.assertEqual(normalized_capacity("ROY", rec, now=NOW, trusted_runtime=True)["state"], "UNKNOWN")

    def test_no_automatic_escalation_to_edit_mode(self):
        with self.assertRaises(ValueError):
            route(mode="PR_BRANCH_EDIT_APPROVED")

    def test_transition_requires_human_gate(self):
        self.assertTrue(check_transition("AWAITING_INDEPENDENT_REVIEW", "READY_FOR_HUMAN_APPROVAL"))
        self.assertTrue(check_transition("READY_FOR_HUMAN_APPROVAL", "CLOSED"))
        with self.assertRaises(ValueError):
            check_transition("NEW", "READY_FOR_HUMAN_APPROVAL")
        with self.assertRaises(ValueError):
            check_transition("WAITING_CAPACITY", "CLOSED")

    def test_handoff_contains_verifiable_references_not_approval(self):
        a = handoff_record(task_id="T-1", origin="USER_TO_ROY",
                           from_role="ROY", to_role="JJOONI",
                           reason="RATE_LIMIT", head_sha=SHA,
                           requested_stage="Independent analysis",
                           event_id="comment-123",
                           source_url="https://github.com/mauveplace/jjooni-control-tower/pull/310")
        self.assertEqual(a["status"], "REQUESTED_NOT_CONFIRMED")
        self.assertFalse(a["code_write_allowed"])
        self.assertFalse(a["merge_allowed"])

    def test_handoff_rejects_self_approval_and_unknown_source(self):
        opts = dict(task_id="T-1", origin="USER_TO_JJOONI",
                    from_role="JJOONI", to_role="ROY", reason="SPECIALIST",
                    head_sha=SHA, requested_stage="Review", event_id="evt-1",
                    source_url="https://github.com/mauveplace/jjooni-control-tower/pull/310")
        for patch in ({"to_role": "JJOONI"},
                      {"source_url": "https://attacker.example/task"},
                      {"reason": "AUTO_MERGE"},
                      {"head_sha": "short"},
                      {"event_id": ""}):
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                handoff_record(**{**opts, **patch})


if __name__ == "__main__":
    unittest.main()
