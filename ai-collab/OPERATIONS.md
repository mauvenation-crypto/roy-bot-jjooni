# JJOONI × ROY: dual-entry, quota-safe collaboration operations

## Objective

Either agent may receive a request first. Both follow the same task/PR contract regardless of origin, expertise or temporary model subscription limits. **No assumption that GitHub can read ChatGPT or Claude usage meters.** The two subscription services are independent and can drop event deliveries; no paid model API, external webhook relay or persistent server is introduced.

## Authoritative work record

- Every substantive task has a durable public-only GitHub PR with `[AI-COLLAB]` opt-in and **exactly one active task introduced/modified in that PR's verified changed-file diff** under `ai-collab-dispatch/tasks/<task_id>.json`. An inherited base-branch task, a deleted task or `TEMPLATE.json` is not the current task. Completed contracts are archived under `ai-collab-dispatch/archive/`. `task_id`, `origin`, `work_type` and immutable event IDs must be verified at the current full PR HEAD.
- A GitHub task is the work order; the linked PR and actual revisions are the provenance. The **Claude/Work session** is agent-run evidence, not the durable queue. A run ending or a model rate limit does not delete the GitHub work order.
- If the request starts with **JJOONI**, JJOONI creates the contract and ROY gets the review task. If it starts with **ROY**, ROY creates/updates the same kind of contract with `origin=USER_TO_ROY`, `required_reviewers=["JJOONI"]` and no ROY reviewer (no self-review). `JJANGGU` is optional, never a fake required placeholder. JJOONI checks the new PR/HEAD when the repo-wide Work PR.opened subscription is actually proven; a user-directed manual review or hourly scan is labelled as such, never called an automatic event receipt. The model contacted first does **not** gain merge authority.
- A task contract in an untrusted PR controls only the public read-only *subject*. It cannot authorize new writes, secret access, production deployment or a budget increase.

## Expertise-aware routing (policy, not self-executing model dispatch)

| Work type | Preferred first pass | Independent counterpart |
| --- | --- | --- |
| Architecture, product/business, trading-strategy interpretation, market-data integrity | JJOONI | ROY |
| Python/JS coding, automation, UI implementation, tests, code security review | ROY | JJOONI |
| Highly consequential data/model corrections | Specialist plus **mandatory** independent challenge | Other agent |
| Ambiguous/mixed | JJOONI triages and defines acceptance, ROY inspects code | Both provide separate evidence |

The rules are explicit in `capacity_router.py` and can be overridden only by owner-authorized scope changes. With both agents available, assigning an expert for the first pass does not waive a real second independent review.

## Quota / outage / asynchronous handoff

| Observed condition | Mandatory response | What is NOT allowed |
| --- | --- | --- |
| ROY session explicitly reports `RATE_LIMITED` | Preserve task/HEAD; hand over read-only preparation to JJOONI if available; resume ROY review after verified recovery | Treat JJOONI-only output as an independently reviewed final result |
| JJOONI Work reports verified capacity limit | ROY may preserve/test/review public code, but mark JJOONI independent decision **pending** | Claim that user approved merging or JJOONI reviewed it |
| Both agents rate-limited/unavailable | `WAITING_CAPACITY`; keep GitHub task and link; no repeated trigger storm | Use paid APIs or additional billable cloud services as a hidden fallback |
| One agent busy | Queue or assign a read-only preparatory task to the other with a handoff receipt | Duplicate writes and racing branches |
| Missing expected webhook or no reply | `WAITING_EVENT`/`UNKNOWN` and inspect event filters, GitHub logs and platform session history | Diagnose usage exhaustion solely from silence |
| Quota reset timestamp passed | Set availability to `UNKNOWN`, re-verify with actual provider run | Assume the agent is AVAILABLE or relaunch many times |
| User starts request directly with ROY | ROY creates a normal `[AI-COLLAB]` PR/task, origin `USER_TO_ROY`; JJOONI handles review on real event | Require user to paste the same request to ChatGPT |
| User starts request directly with JJOONI | JJOONI creates same task/PR, origin `USER_TO_JJOONI`; Claude follows configured PR event | Require manual second Claude chat for normal tasks |

**Why conservative:** Anthropic routines consume account subscription + daily run allowances. GitHub event caps may drop deliveries; missing output can mean quota, unsupported trigger, webhook filters or execution failure. Only source-verified run evidence may set `AVAILABLE`, `BUSY`, `RATE_LIMITED` or `UNAVAILABLE`. Verified records expire after 120 minutes; expired reset time becomes UNKNOWN rather than automatically AVAILABLE. See https://code.claude.com/docs/ko/routines.

## Status machine / handoff

- `NEW → TRIAGED → REQUESTED → IN_PROGRESS → AWAITING_INDEPENDENT_REVIEW → READY_FOR_HUMAN_APPROVAL → CLOSED` is the normal path. `WAITING_CAPACITY`, `WAITING_EVENT`, `NEEDS_CHANGES` and `BLOCKED` preserve incomplete work without silently treating it as done.
- A PR can forge `verified=true`. `capacity_router.py` therefore ignores even well-formed capacity claims unless the calling runtime passes `evidence_from_verified_runtime=True` **after independently validating a first-party run**. That argument is a caller trust boundary, not an automated identity proof; a run ingestion connector is still required for real availability signals.
- `capacity_router.py` never calls an agent. It produces a read-only suggested `assigned_agent`, `independent_reviewer`, `capacity`, `fallback_used`, `next_step` and an always-false safe-to-merge/deploy/trade gate.
- `handoff_record()` makes a stable `task_id + full_head_sha + event_id + from_role + to_role + reason` receipt with `status=REQUESTED_NOT_CONFIRMED`. A request is not a completed handoff until the recipient acknowledges it with independently verifiable run metadata.
- No self-approval: if ROY prepares work while JJOONI is unavailable, ROY's own review does not count as JJOONI's independent challenge, and vice versa.

## Visibility: what the dashboard actually shows

Open `ai-collab/status.html` **after PR merge and verified static-site publication**, or use its standalone HTML file. It fetches the latest **public GitHub** open PRs and their issue comments/reviews only when opened or manually refreshed; no tokens or background polling.

1. Select any PR: see current full HEAD, last update, latest ROY/JJOONI *claimed* review, PASS/NEEDS_CHANGES/BLOCKED when present, and direct GitHub comment/Claude session URLs.
2. When a review marker HEAD differs from the current PR HEAD, see `과거 HEAD 회신` — this is NOT current approval.
3. Every actor claim is labelled **unverified provenance**; even a link to a Claude session posted in a public comment does not independently certify the origin.
4. Actual Work/Claude **running** or real **remaining usage** cannot be determined from the public GitHub API; show UNKNOWN rather than inventing a progress percentage.
5. GitHub anonymous API is limited (commonly 60 requests/hour per originating IP); the dashboard uses manual refresh with a minimum interval and restricts detail requests to the selected PR.

## Operator acceptance checklist

1. In Claude Routines: repository-wide opt-in PR opened + supported labeled/synchronize triggers, correct task path, no PR number filter, no paid extra usage. Actual subscriptions are still external account settings.
2. In ChatGPT Work: repo-wide relevant PR/comment/review/HEAD events, no PR #309-only filter. The existing prompt has been made PR-agnostic, but the provider event subscription **has not yet been proven repo-wide**.
3. **Full round trip** on a fresh unrelated PR: ROY session automatically started → ROY report → Work session automatically started with true original event ID → JJOONI independently evaluates that exact HEAD → no duplicate on JJOONI self-comment.
4. Simulate rate-limit evidence and both agent directions in unit tests. Verify the screen says UNKNOWN if platform usage data cannot be read.
5. Only after all technical and independent reviews are PASS and the user explicitly approves should an authorized, separate actor merge or deploy.

## Security / privacy / cost guardrails

- Only public GitHub data in this dashboard; **never publish bank/customer/company secrets, PB account JSON, private portfolio snapshots, credentials, provider tokens, or medical data**.
- Neither this dashboard nor the Python modules perform any writes or trades. Future developer edits require separate verified owner permission and a restricted workflow; PR JSON is untrusted.
- Do not enable extra Claude usage billing or additional Cloud Run/model APIs to overcome limits without explicit budget approval.
- If the site is deployed, validate `ai-collab/status.html` responds and displays current content. A GitHub code commit or Actions green check does not prove GitHub Pages has deployed the change.

## Remaining verified gaps

- The **GitHub→ROY initial PR.opened path** was observed in the #310 pilot. A ROY `synchronize/labeled` follow-up launch is unverified until its Claude settings are adjusted and real run metadata is correlated.
- The **GitHub→JJOONI Work webhook** was confirmed for #309, but **repo-wide PR event subscription** has not been demonstrated: #310's comment did not produce a visible Work run in the accessible execution history.
- Neither service supplies a connected usage-meters read API to this current integration. Real-time remaining quotas and actual running session phase require first-party service evidence to be integrated, not inferred from silence.
