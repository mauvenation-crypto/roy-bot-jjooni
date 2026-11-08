#!/usr/bin/env python3
"""Read-only validator for a Claude Routine triggered by GitHub issues.opened.

GitHub's configured issue-opened event is an *alternative* to unsupported
follow-up PR-comment triggers, NOT proof that Claude or Work executed.
It does not receive webhooks, sign requests, query GitHub or post comments.
"""
import re
from coordinator import SHA_RE, TASK_RE, REPO

TITLE_PREFIX = "[AI-COLLAB][ROY-REQUEST] "
ISSUE_MARKER = "<!-- JJOONI-COLLAB-ISSUE-V1 -->"
SUPPORTED_MODE = "SYSTEM_REVIEW_ONLY"
PERMITTED_FIELDS = ("Target-PR", "Task-ID", "Expected-HEAD", "Mode", "Requested-By", "Scope")

def parse_request(title, body):
    if not isinstance(title, str) or not title.startswith(TITLE_PREFIX):
        return None
    if not isinstance(body, str):
        raise ValueError("Missing exact task marker on first line")
    # Normalize line endings without relaxing the exact first-line trust marker.
    body = body.replace("\r\n", "\n").replace("\r", "\n")
    if not body.startswith(ISSUE_MARKER + "\n"):
        raise ValueError("Missing exact task marker on first line")
    fields = {}
    for line in body.splitlines()[1:]:
        m = re.fullmatch(r"(Target-PR|Task-ID|Expected-HEAD|Mode|Requested-By|Scope):[ \t]*(.*)", line)
        if m:
            key, val = m.groups()
            if key in fields:
                raise ValueError("Duplicate task field")
            fields[key] = val.strip()
    if any(not fields.get(k) for k in PERMITTED_FIELDS):
        raise ValueError("Missing required issue dispatch fields")
    pr = fields["Target-PR"]
    if not re.fullmatch(r"[1-9][0-9]{0,8}", pr):
        raise ValueError("Invalid target PR")
    if not TASK_RE.fullmatch(fields["Task-ID"]) or fields["Task-ID"].startswith("REPLACE-"):
        raise ValueError("Invalid task ID")
    if not SHA_RE.fullmatch(fields["Expected-HEAD"]):
        raise ValueError("Expected-HEAD must be full 40-char SHA")
    if fields["Mode"] != SUPPORTED_MODE:
        raise ValueError("Only read-only issue dispatch is allowed")
    if fields["Requested-By"] not in ("JJOONI", "ROY", "USER"):
        raise ValueError("Unknown claimed requester")
    if len(fields["Scope"]) > 1500:
        raise ValueError("Scope too long")
    return {"pr_number": int(pr), "task_id": fields["Task-ID"],
            "expected_head": fields["Expected-HEAD"],
            "mode": SUPPORTED_MODE, "claimed_requester": fields["Requested-By"],
            "scope": fields["Scope"], "title": title}

def decide(event, target_pr, *, known_issue_ids=()):
    """Caller must independently validate GitHub webhook and fetched PR.

    The issue creator must be repository owner. The target PR must be OPEN,
    target main and at the pinned HEAD. Dedupe requires a durable issue ledger
    maintained by caller; this function does not store state. A REQUEST_ROY_REVIEW
    is only a candidate: caller MUST separately fetch and validate the exact
    ai-collab-dispatch/tasks/<task_id>.json at pinned HEAD (task_id/filename,
    repository/base/mode/required_reviewers and scope), authenticate the Claude
    session, re-fetch the still-open non-draft non-merged PR before posting, and
    check GitHub comments plus an external durable dedup ledger. Never treat
    the return value alone as permission to execute, merge or deploy.
    """
    if not isinstance(event, dict) or not isinstance(target_pr, dict):
        return {"decision":"BLOCKED", "reason":"Missing event or target PR evidence"}
    if event.get("action") != "opened" or not isinstance(event.get("issue"), dict):
        return {"decision":"IGNORE", "reason":"Not issues.opened"}
    if event.get("repository",{}).get("full_name") != REPO:
        return {"decision":"IGNORE", "reason":"Other repository"}
    issue = event["issue"]
    issue_id = issue.get("id")
    issue_no = issue.get("number")
    if (not isinstance(issue_id,int) or isinstance(issue_id,bool) or issue_id <= 0 or
            not isinstance(issue_no,int) or isinstance(issue_no,bool) or issue_no <= 0):
        return {"decision":"BLOCKED","reason":"Missing authentic GitHub issue identity"}
    if isinstance(issue.get("pull_request"), dict):
        return {"decision":"IGNORE","reason":"A PR is not a follow-up issue"}
    if issue_id in known_issue_ids:
        return {"decision":"DUPLICATE", "issue_id":issue_id}
    who = event.get("sender",{}).get("login")
    author = issue.get("user",{}).get("login")
    if who != REPO.split("/",1)[0] or author != who:
        return {"decision":"UNTRUSTED","issue_id":issue_id,
                "reason":"Only repository owner may create dispatched issues"}
    try:
        task = parse_request(issue.get("title"),issue.get("body"))
    except ValueError as exc:
        return {"decision":"BLOCKED","issue_id":issue_id,"reason":str(exc)}
    if task is None:
        return {"decision":"IGNORE","issue_id":issue_id,"reason":"Not an AI collaboration issue"}
    head=target_pr.get("head",{}).get("sha")
    if (target_pr.get("number")!=task["pr_number"] or
            target_pr.get("state")!="open" or
            target_pr.get("merged") is True or
            target_pr.get("draft") is True or
            target_pr.get("base",{}).get("ref")!="main" or
            "[AI-COLLAB]" not in str(target_pr.get("title",""))):
        return {"decision":"BLOCKED","issue_id":issue_id,"reason":"PR target/opt-in mismatch"}
    if head!=task["expected_head"]:
        return {"decision":"STALE","issue_id":issue_id,
                "reason":"Issue references an older PR HEAD; use a fresh issue"}
    return {"decision":"REQUEST_ROY_REVIEW", "issue_id":issue_id,
            "issue_number":issue_no, "target_pr":task["pr_number"],
            "task_id":task["task_id"],"head_sha":head,
            "role_claim_unverified":True,"execution_confirmed":False,
            "merge_allowed":False,"deploy_allowed":False,
            "reason":"Valid public read-only issue dispatch; Claude run is not yet proven"}
