# Pages deployment migration (staged; not active)

## Objective
Separate the static GitHub Pages publish cadence from frequent data commits to `main`.
The current branch-based Pages source spawns `pages build and deployment`
for almost every commit; superseded builds can be cancelled. This is not
a quote collection failure.

## Current safety state
- `.github/workflows/pages-controlled-deploy.yml` exists but its deploy job
  is **disabled** unless `PAGES_ACTIONS_ENABLED=true` is set in Actions variables.
- The existing Pages source and live website are **unchanged**.
- The old root export is `path: .` with `.nojekyll`; the replacement keeps
  that exact site root.
- BTCUSD/ETHUSD and other supported current quotes already use the separate
  read-only Cloud Run `/observatory/quotes` endpoint on the Observatory UI.
  The 15-minute cadence applies to published static JSON, not to live quotes.
- The repository is public; review published paths as before.

## Human activation (do both in the same maintenance window)
1. GitHub repository **Settings > Pages > Build and deployment > Source**:
   select **GitHub Actions** (instead of Deploy from a branch).
2. GitHub repository **Settings > Secrets and variables > Actions > Variables**:
   create or set `PAGES_ACTIONS_ENABLED` to the literal `true`.
   This is a non-secret opt-in flag.
3. Open **Actions > Pages Controlled Deployment**, choose **Run workflow**
   on `main`, and verify a completed **SUCCESS** deployment.
4. Verify the Control Tower root and `/market-observatory/` both load,
   and compare source-generated timestamps with deployed JSON. Probe BTCUSD
   and ETHUSD runtime quotes separately from the Pages publish timestamp.

**Do not** set the variable before changing Pages Source; otherwise an Actions
deployment can be attempted against branch-source configuration.
If the variable is missing or is not `true`, scheduled executions skip
the deployment job and do not replace the current website.

## Behavior after activation
- Controlled Pages deployment runs every 15 minutes and on manual dispatch.
- Each run checks out current `main` and deploys the same root `.`.
- Deployment concurrency prevents overlapping deploy jobs.
- Data jobs may continue to publish `main`; they no longer separately
  trigger a Pages deployment once the Pages Source setting is switched.
- Latest Pages JSON can lag up to the 15-minute interval plus scheduling,
  runner and deployment delays; timestamps and LIVE/STALE labels remain
  authoritative. Do not promise a hard freshness SLA from cron.

## Rollback
1. Set `PAGES_ACTIONS_ENABLED=false` to disable the Actions deployment.
2. In **Settings > Pages**, change Source back to **Deploy from a branch**
   using the original branch and root directory.
3. Verify the built-in `pages build and deployment` run succeeds.
4. Investigate missing files / URL paths before any future reactivation.

## Monitoring
Track actual deploy successes and failures separately from collectors.
A superseded branch Pages run that is cancelled should not be recorded
as an upstream price collection error. Keep an independent stale-data
signal based on `quote_as_of_kst` and the published data's `generated_kst`.
