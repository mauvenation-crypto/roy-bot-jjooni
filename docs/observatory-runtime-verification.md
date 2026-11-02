# Observatory runtime verification

`Observatory BTC ETH Quote Refresh` runs a read-only production probe **after**
publishing observations. Market publication remains independent of probe health;
a failed API/Pages probe is a distinct failed step, not a rollback of valid quotes.
No scheduler, cloud resource, credential, account or trading endpoint is added.

The job log contains one `OBSERVATORY_RUNTIME_PROOF=` JSON receipt:

- schema: `JJOONI_OBSERVATORY_RUNTIME_PROOF_V1`
- run_id, run_attempt, published_commit, checked_at
- api: HTTP status, Pages-origin CORS, schema/identity checks, fresh BTC/ETH
  provider timestamps, total quote coverage and any other failed symbols
- pages: directly read freshness-status.json **and** observatory-recent.json;
  both must expose the published BTC/ETH baseline or newer observations
- api.checked_at / pages.checked_at distinguish component checks; a stored proof
  is historical evidence, not a continuously live status

The API gets one bounded retry. Pages publication gets a bounded 150-second
window. A deployment SUCCESS, repository-main JSON, frozen LIVE status, missing
provider time, retained API quote or stale observation cannot satisfy this proof.
API prices and CoinGecko publication prices have different providers and are not
required to be identical. Same-timestamp Pages observations must match their
published price and source; newer concurrent publication is accepted.

## Restricted monitoring environments

Attempt direct public reads first. If the monitoring environment cannot resolve
the hosts, fetch the latest eligible crypto run's Job/Step log through GitHub.
Parse the real receipt after publication, not test fixture output. Verify the run,
attempt, published commit and component timestamps. Report a recent proof's exact
check time, provider times, API coverage and Pages status. Never turn an old proof
or deployment status into current availability. If the current run has no proof,
keep that component unverified. A PROBE_DNS_FAILURE is the probe environment's
failure, not proof that the service is down.

## Scheduling contract

GitHub cron is best effort. The existing hourly external error-monitor automation
can re-run only the dedicated `crypto` Job after matching the old/current workflow
definition and rejecting active/ambiguous jobs. Replays use an old run ID with a
new attempt and Job ID. Runner/source availability and the hourly watchdog mean
that this setup does not guarantee a hard 60-minute freshness SLA. Preserve the
60-minute stale threshold and use actual provider time; do not inflate it to hide
gaps. Report current observation breaches and failed recovery, rather than
repeating historical fixed CI failures or an unchanged known cron limitation as
new incidents. First successful recovery is reportable.
