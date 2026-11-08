#!/usr/bin/env python3
"""Pure acceptance gate for PRE-AUTHENTICATED GitHub events; never a webhook server.

A caller must verify webhook signing, call GitHub again for the current PR,
check authentic Claude/Work session provenance, and persist event keys.
This module provides a deterministic, fail-closed decision only.
"""
import re
from pathlib import PurePosixPath

from coordinator import REPO, SHA_RE, parse_comment, validate_task

TASK_DIR = "ai-collab-dispatch/tasks/"
PROBE_RE = re.compile(r"(?m)^<!-- JJOONI-COLLAB-PROBE-[A-Za-z0-9-]{1,80} -->$")
REVIEW_LABEL = "ai-collab:roy-request"


def active_task_path(paths):
    """Require one unambiguous active task; TEMPLATE.json is not a task."""
    if not isinstance(paths, (list, tuple)):
        raise ValueError("File paths must be a list")
    tasks = [
        path for path in paths
        if isinstance(path, str) and path.startswith(TASK_DIR)
        and path.endswith(".json")
        and path != TASK_DIR + "TEMPLATE.json"
        and str(PurePosixPath(path)) == path
        and path.count("/") == 2
    ]
    if len(tasks) != 1:
        raise ValueError("Expected exactly one active collaboration task")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\.json", tasks[0][len(TASK_DIR):]):
        raise ValueError("Unsafe task file name")
    return tasks[0]


def bound_task_path(paths, task):
    """Reject task-id/file-name mismatch, including reused stale task JSON."""
    validate_task(task)
    path = active_task_path(paths)
    expected = TASK_DIR + task["task_id"] + ".json"
    if path != expected:
        raise ValueError("Task filename does not match declared task_id")
    return path


def get(obj, *keys):
    cur = obj
    for key in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def output(kind, *, event_key=None, pr=None, head=None, reason=""):
    return {
        "decision": kind, "event_key": event_key,
        "pr_number": pr, "current_head": head,
        "reason": reason, "agent_authenticated": False,
        "safe_to_merge": False, "safe_to_deploy": False, "safe_to_trade": False,
    }


def decide_event(event_name, event, current_pr, task, *, known_event_keys=(),
                 tree_changed=None):
    """Return a decision; NEVER acts on GitHub or authenticates an AI.

    event is the actual GitHub webhook payload with a verified signature.
    current_pr is a fresh, independently fetched GitHub PR JSON object.
    tree_changed must come from a Git tree comparison, not webhook text.
    known_event_keys must be a durable, caller-maintained set of prior events.
    """
    validate_task(task)
    if not isinstance(event, dict) or not isinstance(current_pr, dict):
        return output("BLOCKED", reason="Missing GitHub event or PR evidence")
    if not isinstance(known_event_keys, (set, frozenset, list, tuple)):
        return output("BLOCKED", reason="No usable deduplication ledger")
    number = current_pr.get("number")
    head = get(current_pr, "head", "sha")
    if isinstance(number, bool) or not isinstance(number, int) or number < 1:
        return output("BLOCKED", reason="Invalid PR number")
    if not isinstance(head, str) or not SHA_RE.fullmatch(head):
        return output("BLOCKED", pr=number, reason="Invalid full PR HEAD")
    if (get(event, "repository", "full_name") != REPO
            or get(current_pr, "base", "ref") != "main"
            or current_pr.get("state") != "open"):
        return output("IGNORE", pr=number, head=head,
                      reason="Not open on the configured repository/main base")
    if "[AI-COLLAB]" not in str(current_pr.get("title", "")):
        return output("IGNORE", pr=number, head=head, reason="PR is not opted in")
    if (task["repository"] != REPO or task["base_branch"] != "main"):
        return output("BLOCKED", pr=number, head=head, reason="Task scope mismatch")
    action = event.get("action")
    actor_login = get(event, "sender", "login")
    id_source = None
    raw = None
    if event_name == "issue_comment":
        if action != "created" or not get(event, "issue", "pull_request"):
            return output("IGNORE", pr=number, head=head,
                          reason="Not a newly created PR conversation comment")
        if get(event, "issue", "number") != number:
            return output("BLOCKED", pr=number, head=head, reason="PR ID mismatch")
        raw = event.get("comment")
        id_source = get(event, "comment", "id")
    elif event_name == "pull_request_review":
        if action != "submitted":
            return output("IGNORE", pr=number, head=head, reason="Not a submitted review")
        if get(event, "pull_request", "number") != number:
            return output("BLOCKED", pr=number, head=head, reason="PR ID mismatch")
        raw = event.get("review")
        id_source = get(event, "review", "id")
        if get(event, "review", "commit_id") != head:
            return output("STALE", pr=number, head=head, reason="Review is for an older HEAD")
    elif event_name == "pull_request_review_comment":
        if action != "created":
            return output("IGNORE", pr=number, head=head, reason="Not a new inline comment")
        if get(event, "pull_request", "number") != number:
            return output("BLOCKED", pr=number, head=head, reason="PR ID mismatch")
        raw = event.get("comment")
        id_source = get(event, "comment", "id")
        if get(event, "comment", "commit_id") != head:
            return output("STALE", pr=number, head=head, reason="Inline comment is for an older HEAD")
    elif event_name == "pull_request":
        if action not in ("opened", "synchronize", "labeled"):
            return output("IGNORE", pr=number, head=head, reason="Unsubscribed PR action")
        if get(event, "pull_request", "number") != number:
            return output("BLOCKED", pr=number, head=head, reason="PR ID mismatch")
        if get(event, "pull_request", "head", "sha") != head:
            return output("STALE", pr=number, head=head, reason="Webhook HEAD is superseded")
        if action == "synchronize":
            before = event.get("before")
            after = event.get("after")
            if not (isinstance(before, str) and SHA_RE.fullmatch(before)
                    and isinstance(after, str) and SHA_RE.fullmatch(after)
                    and after == head):
                return output("NEED_EVIDENCE", pr=number, head=head,
                              reason="Missing verified before/after PR SHA")
            id_source = before + ">" + after
        elif action == "labeled":
            if get(event, "label", "name") != REVIEW_LABEL:
                return output("IGNORE", pr=number, head=head, reason="Not the ROY request label")
            if actor_login != REPO.split("/", 1)[0]:
                return output("UNTRUSTED", pr=number, head=head,
                              reason="Request label was not applied by repo owner")
            id_source = REVIEW_LABEL + ":" + head
        else:
            id_source = head
    else:
        return output("IGNORE", pr=number, head=head, reason="Unsupported event type")

    if not isinstance(id_source, (str, int)) or not str(id_source):
        return output("NEED_EVIDENCE", pr=number, head=head,
                      reason="Missing original immutable event/comment ID")
    event_key = "|".join((REPO, str(number), event_name, str(action), str(id_source)))
    if event_key in known_event_keys:
        return output("DUPLICATE", event_key=event_key, pr=number, head=head,
                      reason="Original event already processed")

    if event_name == "pull_request":
        if action == "opened":
            if "ROY" not in task["required_reviewers"]:
                return output("IGNORE", event_key=event_key, pr=number, head=head,
                              reason="ROY is not a required reviewer for this task")
            return output("WAIT_ROY", event_key=event_key, pr=number, head=head,
                          reason="First PR review belongs to ROY")
        if action == "labeled":
            if "ROY" not in task["required_reviewers"]:
                return output("IGNORE", event_key=event_key, pr=number, head=head,
                              reason="ROY is not a required reviewer for this task")
            return output("REQUEST_ROY", event_key=event_key, pr=number, head=head,
                          reason="Explicit owner-origin request label")
        if tree_changed is None:
            return output("NEED_EVIDENCE", event_key=event_key, pr=number, head=head,
                          reason="Git tree comparison is required")
        if tree_changed is not True:
            return output("IGNORE", event_key=event_key, pr=number, head=head,
                          reason="No proven semantic code/tree change")
        return output("REVIEW_CHANGED_HEAD", event_key=event_key, pr=number, head=head,
                      reason="New code HEAD; independently audit without assuming ROY identity")

    if not isinstance(raw, dict) or actor_login != get(raw, "user", "login"):
        return output("BLOCKED", event_key=event_key, pr=number, head=head,
                      reason="Event sender and original comment author differ")
    if actor_login != REPO.split("/", 1)[0]:
        return output("UNTRUSTED", event_key=event_key, pr=number, head=head,
                      reason="Review claim not authored by the allowed GitHub account")

    body = raw.get("body")
    if isinstance(body, str) and PROBE_RE.search(body):
        return output("PROBE", event_key=event_key, pr=number, head=head,
                      reason="Webhook receipt only; no actual code review")
    parsed = parse_comment(raw)
    if not parsed:
        return output("IGNORE", event_key=event_key, pr=number, head=head,
                      reason="No valid versioned review marker")
    if parsed["actor_claim"] == "JJOONI":
        return output("IGNORE", event_key=event_key, pr=number, head=head,
                      reason="Self-comment must not trigger feedback loop")
    if parsed["actor_claim"] not in task["required_reviewers"]:
        return output("IGNORE", event_key=event_key, pr=number, head=head,
                      reason="Actor not required for this task")
    if parsed["task_id"] != task["task_id"] or parsed["head_sha"] != head:
        return output("STALE", event_key=event_key, pr=number, head=head,
                      reason="Wrong task ID or obsolete review HEAD")
    return output("VERIFY_ROY" if parsed["actor_claim"] == "ROY" else "VERIFY_REVIEWER",
                  event_key=event_key, pr=number, head=head,
                  reason="Review claim received; agent session verification REQUIRED")
