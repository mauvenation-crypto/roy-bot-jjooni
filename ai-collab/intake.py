"""Cross-entrypoint task reconciliation for ROY-first and JJOONI-first requests.

Exact keys/fingerprints detect potentially duplicated work. They do NOT
perform semantic similarity, read private chats, query GitHub, or auto-merge
tasks. False positives always require a human/agent to verify scope.
"""
import hashlib
import json
import re

ALLOWED_ORIGINS = frozenset(("USER_TO_JJOONI", "USER_TO_ROY", "GITHUB_EVENT", "UNKNOWN"))


def canonical_text(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Expected nonblank task text")
    normalized = re.sub(r"\s+", " ", value.strip()).casefold()
    if len(normalized) > 6000:
        raise ValueError("Intake text exceeds safe bound")
    return normalized


def intake_key(repository, request_anchor):
    if repository != "mauveplace/jjooni-control-tower":
        raise ValueError("Unexpected repository")
    if not isinstance(request_anchor, str) or not re.fullmatch(r"(issue|pr):[1-9][0-9]{0,8}", request_anchor):
        raise ValueError("Require an immutable GitHub issue or PR anchor")
    return repository + "#" + request_anchor


def fingerprint(*, objective, work_type, scope):
    if work_type not in ("architecture", "product", "strategy_analysis", "data_integrity",
                        "security_review", "backend", "frontend", "testing",
                        "documentation", "general"):
        raise ValueError("Unrecognized work type")
    body = {"objective": canonical_text(objective),
            "work_type": work_type, "scope": canonical_text(scope)}
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def reconcile(new, existing):
    """Return match confidence, not a task assignment or permission grant.

    Same anchor and conflicting content is a BLOCKED conflict. Identical
    fingerprints are only POSSIBLE_DUPLICATE, not automatic consolidation.
    """
    if not isinstance(new, dict) or not isinstance(existing, list):
        raise ValueError("Invalid intake registry input")
    for key in ("key", "fingerprint", "origin"):
        if not isinstance(new.get(key), str):
            raise ValueError("Missing canonical intake record field")
    if new["origin"] not in ALLOWED_ORIGINS:
        raise ValueError("Invalid origin")
    if not re.fullmatch(r"[a-f0-9]{64}", new["fingerprint"]):
        raise ValueError("Invalid fingerprint")
    for row in existing:
        if (not isinstance(row, dict) or not isinstance(row.get("key"), str)
                or not isinstance(row.get("fingerprint"), str)
                or not re.fullmatch(r"[a-f0-9]{64}", row["fingerprint"])):
            raise ValueError("Malformed existing intake")
        if row.get("key") == new["key"]:
            if row.get("fingerprint") != new["fingerprint"]:
                return {"decision": "CONFLICT", "matched_key": row["key"],
                        "reason": "Same work order anchor with different scope; manual reconciliation required",
                        "safe_to_merge": False}
            return {"decision": "SAME_WORK_ORDER", "matched_key": row["key"],
                    "reason": "Same immutable GitHub anchor; use the existing PR/task",
                    "safe_to_merge": False}
        if row.get("fingerprint") == new["fingerprint"]:
            return {"decision": "POSSIBLE_DUPLICATE", "matched_key": row.get("key"),
                    "reason": "Exact normalized objective/scope match; verify before joining",
                    "safe_to_merge": False}
    return {"decision": "NEW_INTAKE", "matched_key": None,
            "reason": "No exact match; paraphrased duplicates remain possible",
            "safe_to_merge": False}
