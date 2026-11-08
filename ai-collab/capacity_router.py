#!/usr/bin/env python3
"""PR-agnostic collaboration planning, capacity and handoff decisions.

This module does not trigger models, fetch quotas, persist state, merge PRs,
access financial accounts, or authorize new write privileges. It is a pure
function layer for authenticated agents and human operators.
"""
from datetime import datetime, timedelta, timezone

ROLES = ("JJOONI", "ROY")
CAPACITY = frozenset(("AVAILABLE", "BUSY", "RATE_LIMITED", "UNAVAILABLE", "UNKNOWN"))
ORIGINS = frozenset(("USER_TO_JJOONI", "USER_TO_ROY", "GITHUB_EVENT", "UNKNOWN"))
WORK_TYPES = {
    "architecture": ("JJOONI", "ROY"),
    "product": ("JJOONI", "ROY"),
    "strategy_analysis": ("JJOONI", "ROY"),
    "data_integrity": ("JJOONI", "ROY"),
    "security_review": ("ROY", "JJOONI"),
    "backend": ("ROY", "JJOONI"),
    "frontend": ("ROY", "JJOONI"),
    "testing": ("ROY", "JJOONI"),
    "documentation": ("JJOONI", "ROY"),
    "general": ("JJOONI", "ROY"),
}
STATES = frozenset((
    "NEW", "TRIAGED", "REQUESTED", "IN_PROGRESS", "NEEDS_CHANGES",
    "WAITING_CAPACITY", "WAITING_EVENT", "AWAITING_INDEPENDENT_REVIEW",
    "READY_FOR_HUMAN_APPROVAL", "BLOCKED", "CLOSED",
))
TRANSITIONS = {
    "NEW": {"TRIAGED", "BLOCKED"},
    "TRIAGED": {"REQUESTED", "WAITING_CAPACITY", "WAITING_EVENT", "BLOCKED"},
    "REQUESTED": {"IN_PROGRESS", "WAITING_CAPACITY", "WAITING_EVENT", "BLOCKED"},
    "IN_PROGRESS": {"NEEDS_CHANGES", "AWAITING_INDEPENDENT_REVIEW", "WAITING_CAPACITY", "BLOCKED"},
    "NEEDS_CHANGES": {"REQUESTED", "WAITING_CAPACITY", "BLOCKED"},
    "WAITING_CAPACITY": {"REQUESTED", "BLOCKED"},
    "WAITING_EVENT": {"REQUESTED", "BLOCKED"},
    "AWAITING_INDEPENDENT_REVIEW": {"NEEDS_CHANGES", "READY_FOR_HUMAN_APPROVAL", "WAITING_CAPACITY", "BLOCKED"},
    "READY_FOR_HUMAN_APPROVAL": {"CLOSED", "NEEDS_CHANGES", "BLOCKED"},
    "BLOCKED": {"TRIAGED", "REQUESTED", "CLOSED"},
    "CLOSED": set(),
}
VERIFIED_SOURCES = frozenset(("CLAUDE_RUN", "WORK_RUN", "OWNER_CONFIRMATION"))
FRESHNESS_MINUTES = 120


def _parse_time(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc) if parsed.tzinfo else None
    except ValueError:
        return None


def normalized_capacity(actor, record, *, now=None, trusted_runtime=False):
    """Only fresh verified first-party run evidence can establish capacity.

    A GitHub comment or an actor=ROY claim alone is not evidence.
    UNKNOWN is an explicit first-class state, never interpreted as AVAILABLE.
    """
    if actor not in ROLES:
        raise ValueError("Unsupported collaborator")
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("now must be timezone aware")
    default = {"actor": actor, "state": "UNKNOWN", "provenance": "NOT_VERIFIED",
               "checked_at": None, "limit_reset_at": None}
    # PR tasks/comments may contain forged verified:true. Only a caller that
    # independently authenticated first-party run evidence can enable this gate.
    if trusted_runtime is not True or not isinstance(record, dict) or record.get("actor") != actor:
        return default
    state = record.get("state")
    checked = _parse_time(record.get("checked_at"))
    source = record.get("source")
    if (state not in CAPACITY or not checked
            or source not in VERIFIED_SOURCES
            or record.get("verified") is not True
            or checked > now + timedelta(minutes=2)
            or now - checked > timedelta(minutes=FRESHNESS_MINUTES)):
        return default
    reset = _parse_time(record.get("limit_reset_at"))
    if state == "RATE_LIMITED" and reset and reset <= now:
        # The advertised reset time has passed; not proof that access recovered.
        state = "UNKNOWN"
    return {"actor": actor, "state": state, "provenance": source,
            "checked_at": checked.isoformat(),
            "limit_reset_at": reset.isoformat() if reset and state == "RATE_LIMITED" else None}


def check_transition(before, after):
    if before not in STATES or after not in STATES:
        raise ValueError("Unknown collaboration state")
    if after not in TRANSITIONS[before]:
        raise ValueError("Forbidden transition: %s -> %s" % (before, after))
    return True


def route_task(*, origin, work_type, capacities=None, required_independent_review=True,
               mode="SYSTEM_REVIEW_ONLY", now=None, evidence_from_verified_runtime=False):
    """Deterministic recommendation only. No network calls or autonomous dispatch.

    When the preferred agent is limited, the other may do read-only
    preparation. It never satisfies an independent dual-review gate by itself.
    """
    if origin not in ORIGINS:
        raise ValueError("Invalid task origin")
    if work_type not in WORK_TYPES:
        raise ValueError("Unknown work type")
    if mode != "SYSTEM_REVIEW_ONLY":
        raise ValueError("PR-controlled code-write approvals are not accepted")
    capacities = capacities or {}
    status = {actor: normalized_capacity(actor, capacities.get(actor), now=now,
                                         trusted_runtime=evidence_from_verified_runtime)
              for actor in ROLES}
    preferred, alternate = WORK_TYPES[work_type]
    chosen = None
    state = "WAITING_CAPACITY"
    reason = "Both agents have verified capacity limitations"
    for actor in (preferred, alternate):
        if status[actor]["state"] == "AVAILABLE":
            chosen = actor
            state = "REQUESTED"
            reason = "Selected a verified available agent"
            break
    if chosen is None:
        for actor in (preferred, alternate):
            if status[actor]["state"] == "UNKNOWN":
                chosen = actor
                state = "WAITING_EVENT"
                reason = "Capacity is unknown; request may be queued but not called running"
                break
    if chosen is None and any(status[x]["state"] == "BUSY" for x in ROLES):
        state = "WAITING_CAPACITY"
        reason = "Known busy agents; preserve task for a later attempt"
    fallback = chosen is not None and chosen != preferred
    independent = alternate if chosen == preferred else preferred
    return {
        "origin": origin, "work_type": work_type, "preferred_agent": preferred,
        "assigned_agent": chosen, "independent_reviewer": independent,
        "state": state, "reason": reason,
        "fallback_used": fallback, "fallback_scope": "READ_ONLY_PREPARATION" if fallback else "NONE",
        "required_independent_review": bool(required_independent_review),
        "independent_review_completed": False,
        "capacity": status, "owner_approval_required": True,
        "safe_to_merge": False, "safe_to_deploy": False, "safe_to_trade": False,
        "next_step": ("VERIFY_ACTUAL_RUN_EVENT" if chosen else "PRESERVE_AND_RETRY_WHEN_VERIFIED"),
    }


def handoff_record(*, task_id, origin, from_role, to_role, reason, head_sha,
                   requested_stage, event_id, source_url):
    """Structured PR handoff receipt; never silently alters owner or privileges."""
    from coordinator import SHA_RE, TASK_RE
    if (not isinstance(task_id, str) or not TASK_RE.fullmatch(task_id)
            or from_role not in ROLES or to_role not in ROLES or from_role == to_role
            or origin not in ORIGINS or reason not in
            ("SPECIALIST", "RATE_LIMIT", "BUSY", "EXPLICIT_USER_REQUEST", "RECOVERY")
            or not isinstance(head_sha, str) or not SHA_RE.fullmatch(head_sha)
            or not isinstance(requested_stage, str) or not requested_stage.strip()
            or not isinstance(event_id, str) or not event_id.strip()
            or not isinstance(source_url, str)
            or not source_url.startswith("https://github.com/mauveplace/jjooni-control-tower/")):
        raise ValueError("Unsafe or incomplete handoff request")
    return {
        "schema": "JJOONI_COLLAB_HANDOFF_V1", "task_id": task_id,
        "origin": origin, "from_role": from_role, "to_role": to_role,
        "reason": reason, "head_sha": head_sha,
        "requested_stage": requested_stage, "event_id": event_id,
        "source_url": source_url, "status": "REQUESTED_NOT_CONFIRMED",
        "code_write_allowed": False, "merge_allowed": False,
        "agent_session_provenance": "UNKNOWN",
    }
