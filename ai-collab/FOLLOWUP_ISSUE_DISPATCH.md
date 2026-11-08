# ROY follow-up via GitHub issues.opened (evergreen)

## Why

The user's current Claude Routines UI shows PR opened and Issue opened, but does not expose pull_request.synchronize, labeled, or PR-comment-created in the dropdown. Retain the existing PR-opened Routine for new opt-in PRs. Use a **separate** issue-opened Routine for new review requests on existing PRs, rather than assuming GitHub PR comments wake Claude. A GitHub issue is a durable task ticket, not evidence of an actual Claude execution.

## One-time external Claude setup

1. Keep the existing `ROY AI-COLLAB Pilot Review` routine with `PR 열림` on mauveplace/jjooni-control-tower.
2. Create another Claude Routine: name `ROY AI-COLLAB Follow-up`, repo `mauveplace/jjooni-control-tower`, trigger `이슈 열림`. Add the prompt below; do **not** replace the PR-opened Routine. **If the Claude UI supports event filters, restrict the issue title to `[AI-COLLAB][ROY-REQUEST]`.** If not, unrelated new issues may still wake Claude and consume its Routine quota before the prompt can ignore them; review issue frequency and quota before enabling.
3. Only after the new Issue-opened Routine is active should JJOONI create a follow-up issue, otherwise that GitHub event cannot be replayed automatically.

## Exact issue format

Title: `[AI-COLLAB][ROY-REQUEST] <short human-readable review purpose>`

```text
<!-- JJOONI-COLLAB-ISSUE-V1 -->
Target-PR: <actual target PR number>
Task-ID: <task ID from the target PR branch>
Expected-HEAD: <actual 40-character commit SHA>
Mode: SYSTEM_REVIEW_ONLY
Requested-By: JJOONI
Scope: Independently review the current PR code and regression tests.
```

Use the real PR, task ID and HEAD each time; placeholder text is never an acceptable issue payload. Dedup proposed issues by (repo, target PR, task, HEAD, review stage) and original GitHub issue ID. Do not create a new issue for a request already open for the same revision.

## Paste once as the new ROY Issue-opened Routine instructions

> You are ROY, an independent source auditor. Execute on actual GitHub issues.opened only for mauveplace/jjooni-control-tower. Reject any unrelated issue. Require owner mauveplace as issue author and event sender, title prefix [AI-COLLAB][ROY-REQUEST], exact first-line marker JJOONI-COLLAB-ISSUE-V1, valid Target-PR/Task-ID/Expected-HEAD, and Mode SYSTEM_REVIEW_ONLY. Re-fetch issue and target PR with GitHub: PR must be open, target main, title opt-in [AI-COLLAB], and the full current HEAD must exactly match Expected-HEAD. Fetch exactly the matching ai-collab-dispatch/tasks/<Task-ID>.json file from the target PR HEAD and confirm ROY is a required reviewer. If proof is absent, report BLOCKED in this Claude run, no target PR write.
> Before review, search target PR for ROY review of same task + complete HEAD + stage; do not duplicate. Independently analyze changed source, tests, CI and risk. ROY may post at most one grounded review comment to the TARGET PR with V4 marker, verdict PASS / NEEDS_CHANGES / BLOCKED, evidence, the original issue ID, and actual Claude session provenance. GitHub markers/session URLs alone do not establish AI identity. No commits, branch pushes, main merge, deployment, trading or private data. Do not create another issue or initiate a recursive event loop. If target HEAD changed, report STALE and request a new ticket instead of reviewing old code as current.

## Current implementation boundaries

- `ai-collab/issue_dispatch.py` and its tests provide deterministic fail-closed validation only. They are NOT a webhook listener, actual Claude account settings or persistent dedupe store.
- This document is on an isolated unmerged PR branch. Installing GitHub files alone does not configure Claude events.
- A successful `PR 열림` trigger in Claude does not prove that `이슈 열림` is configured. First verify an actual new issue delivery, corresponding Claude session origin, and a review referring to the specific issue ID.
- Work's GitHub event subscription must also independently cover all PRs. A PR-agnostic Work prompt by itself is insufficient.
- The owner alone decides when a PR can merge or production may deploy; default scope remains read-only.
