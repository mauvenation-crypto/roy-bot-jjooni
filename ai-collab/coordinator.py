#!/usr/bin/env python3
"""Public-only, read-only collaboration contract checker.

Pure standard library. No network calls, secrets, PR writes, deployments,
agent execution, code generation, broker orders or automated approval.
"""
import argparse
import json
import re
from collections import Counter
from pathlib import Path

REPO = "mauveplace/jjooni-control-tower"
ACTORS = frozenset(("ROY", "JJANGGU", "JJOONI"))
REQUIRED_ACTORS = frozenset(("ROY", "JJANGGU", "JJOONI"))
ALLOWED_ORIGINS = frozenset(("USER_TO_JJOONI", "USER_TO_ROY", "GITHUB_EVENT", "UNKNOWN"))
ALLOWED_MODES = frozenset(("SYSTEM_REVIEW_ONLY",))
TASK_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
SHA_RE = re.compile(r"^[a-f0-9]{40}$")
MARKER_RE = re.compile(
    r"\A<!-- JJOONI-COLLAB-V4 task=([A-Za-z0-9][A-Za-z0-9._-]{0,127}) "
    r"actor=(ROY|JJANGGU|JJOONI) stage=(review|independent-review) "
    r"head=([a-f0-9]{40}) -->\r?\n"
)
MAX_COMMENT_SIZE = 16000


def validate_task(task):
    if not isinstance(task, dict) or task.get("schema") != "JJOONI_COLLAB_V4":
        raise ValueError("Expected JJOONI_COLLAB_V4 task object")
    if not isinstance(task.get("task_id"), str) or not TASK_RE.fullmatch(task["task_id"]) or task["task_id"].startswith("REPLACE-"):
        raise ValueError("Invalid or placeholder task_id")
    if task.get("repository") != REPO or task.get("base_branch") != "main":
        raise ValueError("Unexpected repository or target branch")
    if not isinstance(task.get("objective"), str) or not task["objective"].strip():
        raise ValueError("Missing objective")
    if task.get("privacy") != "PUBLIC_DATA_ONLY":
        raise ValueError("Only public data is permitted")
    mode = task.get("mode")
    if mode not in ALLOWED_MODES:
        raise ValueError("Unsupported task mode")
    required, optional = task.get("required_reviewers"), task.get("optional_reviewers", [])
    if not isinstance(required, list) or not required or not all(isinstance(x, str) for x in required) or len(required) != len(set(required)):
        raise ValueError("Required reviewer list must be unique and non-empty")
    if not isinstance(optional, list) or not all(isinstance(x, str) for x in optional) or len(optional) != len(set(optional)):
        raise ValueError("Optional reviewers must be a unique list")
    if any(role not in REQUIRED_ACTORS for role in required + optional):
        raise ValueError("Unsupported role")
    if set(required).intersection(optional):
        raise ValueError("Required and optional reviewers overlap")
    origin = task.get("origin", "USER_TO_JJOONI")  # Legacy tasks predate origin field.
    if origin not in ALLOWED_ORIGINS:
        raise ValueError("Unrecognized task origin")
    if origin == "USER_TO_ROY":
        if "JJOONI" not in required:
            raise ValueError("ROY-first work requires an independent JJOONI reviewer")
        if "ROY" in required + optional:
            raise ValueError("ROY-first author cannot also review the same work")
    elif "JJOONI" in required + optional:
        raise ValueError("JJOONI review role requires authenticated USER_TO_ROY routing")
    if not isinstance(task.get("acceptance"), list) or not task["acceptance"]:
        raise ValueError("Explicit acceptance checks are mandatory")
    if any(not isinstance(x, str) or not x.strip() for x in task["acceptance"]):
        raise ValueError("Empty acceptance criterion")
    source = task.get("source_sha")
    if source is not None and (not isinstance(source, str) or not SHA_RE.fullmatch(source)):
        raise ValueError("source_sha must be null or 40-char SHA")
    # A PR-authored task is untrusted and can never authorize agent code edits.
    # Real owner-authenticated branch-edit approvals require a separate verified workflow.
    if task.get("release_gate") != "USER_APPROVAL_REQUIRED":
        raise ValueError("Human approval gate is mandatory")
    return task


def parse_comment(comment):
    """Marker is an unverified role claim, never AI-agent authentication."""
    if not isinstance(comment, dict):
        return None
    body = comment.get("body")
    if not isinstance(body, str) or not 0 < len(body) <= MAX_COMMENT_SIZE:
        return None
    found = MARKER_RE.match(body)
    if not found or not body[found.end():].strip():
        return None
    task_id, actor, stage, head = found.groups()
    if (actor == "JJOONI") != (stage == "independent-review"):
        return None
    user = comment.get("user")
    return {
        "task_id": task_id, "actor_claim": actor, "stage": stage,
        "head_sha": head, "comment_id": str(comment.get("id", "")),
        "url": str(comment.get("html_url") or comment.get("url") or ""),
        "github_user": user.get("login") if isinstance(user, dict) else None,
        "provenance": "UNVERIFIED_ROLE_CLAIM",
    }


def summarize(task, comments, head_sha):
    validate_task(task)
    if not isinstance(head_sha, str) or not SHA_RE.fullmatch(head_sha):
        raise ValueError("Full 40-character PR HEAD is required")
    if not isinstance(comments, list):
        raise ValueError("Comments must be a JSON array")
    relevant = [
        parsed for comment in comments if (parsed := parse_comment(comment))
        and parsed["task_id"] == task["task_id"] and parsed["head_sha"] == head_sha
    ]
    required = task["required_reviewers"]
    owner_login = REPO.split("/", 1)[0]
    trusted = [x for x in relevant if x["github_user"] == owner_login]
    untrusted = [x for x in relevant if x["github_user"] != owner_login]
    self_claims = [x for x in trusted if task.get("origin") == "USER_TO_ROY" and x["actor_claim"] == "ROY"]
    trusted = [x for x in trusted if x not in self_claims]
    counts = Counter(x["actor_claim"] for x in trusted)
    missing = [actor for actor in required if not counts[actor]]
    duplicates = {k: v for k, v in counts.items() if v > 1}
    if duplicates:
        state = "DUPLICATE_CLAIMS_REVIEW_REQUIRED"
    elif missing:
        state = "WAITING_FOR_REQUIRED_REVIEWERS"
    else:
        state = "AWAITING_SOURCE_VERIFICATION"
    return {
        "task_id": task["task_id"], "pr_head_sha": head_sha,
        "required_reviewers": required, "missing_reviewers": missing,
        "duplicate_claims": duplicates, "state": state,
        "review_claims": trusted, "ignored_untrusted_claims": untrusted,
        "ignored_self_review_claims": self_claims,
        "authenticated_agent_origin": False,
        "safe_to_merge": False, "safe_to_deploy": False,
        "safe_to_trade": False,
        "provenance_note": "Check actual Claude/Work session events separately",
    }


def template(task, actor, head_sha):
    validate_task(task)
    if actor not in ACTORS or not isinstance(head_sha, str) or not SHA_RE.fullmatch(head_sha):
        raise ValueError("Invalid actor or PR head")
    stage = "independent-review" if actor == "JJOONI" else "review"
    return (
        f"<!-- JJOONI-COLLAB-V4 task={task['task_id']} actor={actor} "
        f"stage={stage} head={head_sha} -->\n"
        f"## {actor} / {'INDEPENDENT REVIEW' if actor == 'JJOONI' else 'REVIEW'}\n\n"
        "Verdict: [PASS / NEEDS_CHANGES / BLOCKED]\n"
        "Evidence: [reproducible source, tests or UNKNOWN]\n"
        "Risks: [impact and unresolved uncertainty]\n"
        "Recommendation: [no main merge without owner approval]\n"
        "Session provenance: [verified event/session link or UNKNOWN]\n"
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("status", "template", "validate"))
    parser.add_argument("--task", required=True, type=Path)
    parser.add_argument("--comments", type=Path)
    parser.add_argument("--head")
    parser.add_argument("--actor", choices=sorted(ACTORS))
    args = parser.parse_args(argv)
    try:
        task = validate_task(json.loads(args.task.read_text(encoding="utf-8")))
        if args.command == "validate":
            result = {"valid": True, "task_id": task["task_id"]}
        elif args.command == "template":
            if not args.head or not args.actor:
                parser.error("template requires --head and --actor")
            print(template(task, args.actor, args.head))
            return
        else:
            if not args.head or not args.comments:
                parser.error("status requires --head and --comments")
            comments = json.loads(args.comments.read_text(encoding="utf-8"))
            result = summarize(task, comments, args.head)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
