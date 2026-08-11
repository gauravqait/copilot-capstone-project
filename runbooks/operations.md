# Operations Runbook — Automated Documentation Synchronization

## Purpose

This runbook provides operational guidance for maintainers and administrators of the automated documentation synchronization workflow. It covers day-to-day operations, incident response, recovery procedures, configuration management, and monitoring practices.

---

## System Overview

The documentation synchronization pipeline runs on every push to the `main` branch. It executes the following stages in sequence:

1. **detect_changes** — Identifies changed files since the last known reference (`BASE_REF`).
2. **generate_docs** — Generates updated README, API, and architecture documentation.
3. **validate_docs** — Lints and quality-checks generated documentation.
4. **scan_secrets** — Scans generated content for credential or secret patterns.
5. **backup_docs** — Creates a timestamped backup of current documentation before replacement.
6. **create_pr** — Creates a branch and opens a Pull Request with generated changes (skipped in dry-run mode).
7. **approval_gate** — Verifies required review approvals before the PR can be merged.
8. **notify** — Sends GitHub check-run and PR comment notifications on success or failure.

All stages are orchestrated by `scripts/run_workflow.py`. Every stage appends a structured event to `docs/generated/audit-log.ndjson`.

---

## Key Files and Artifacts

| Path | Description |
| --- | --- |
| `scripts/run_workflow.py` | Main workflow orchestrator. |
| `scripts/backup_docs.py` | Backup and rollback utility. |
| `scripts/audit.py` | Appends NDJSON events to the audit log. |
| `scripts/generate_monitoring.py` | Aggregates audit events into `monitoring-metrics.json`. |
| `config/pipeline-config.yml` | Timeout, retry, path, and trigger settings. |
| `config/policy-rules.yml` | Approval, quality, and secret-scan policy rules. |
| `docs/generated/audit-log.ndjson` | Append-only audit log; one JSON object per line. |
| `docs/generated/workflow-summary.json` | Result summary written at the end of each run. |
| `docs/generated/change-detection.json` | Files changed in the triggering commit range. |
| `docs/generated/doc-generation.json` | Output manifest from the documentation generator. |
| `docs/generated/secret-scan-result.json` | Secret-scan pass/fail result and issue list. |
| `docs/generated/pr-result.json` | PR number, URL, and branch written after PR creation. |
| `docs/generated/monitoring-metrics.json` | Aggregated step-level success/failure counts. |
| `docs/backups/latest-backup.json` | Manifest pointing to the most recent backup. |
| `docs/backups/backup-<timestamp>/` | Timestamped backup directory with a per-backup manifest. |

---

## Configuration Reference

### `config/pipeline-config.yml`

```yaml
workflow:
  name: documentation-sync
  trigger_branch: main
  timeout_minutes: 15   # Maximum wall-clock time for one full run.
  retries: 2            # Automatic retries on transient failures.

repository:
  docs_output_path: docs/output
  docs_backup_path: docs/backups
  docs_generated_path: docs/generated
  templates_path: config/templates

security:
  require_branch_protection: true
  require_approval: true
  secret_scanning_enabled: true
```

### `config/policy-rules.yml`

```yaml
policies:
  require_review_for_generated_docs: true
  required_approvals: 1           # Minimum unique approvers before merge is allowed.
  requested_reviewers: []         # List of GitHub logins to auto-request review from.
  require_secret_scan: true
  require_backup_before_replace: true
  require_audit_logging: true

quality:
  minimum_readability_score: 80
  require_links_validation: true
  require_markdown_formatting: true
```

To change a policy, edit the file, open a PR for review, and merge into `main`. The next pipeline run picks up the new rules automatically.

---

## Environment Variables

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `GITHUB_TOKEN` | Yes (live runs) | — | PAT or Actions token with `contents: write` and `pull-requests: write`. |
| `GITHUB_REPOSITORY` | Yes (live runs) | — | `owner/repo` for GitHub API calls. |
| `GITHUB_SHA` | Yes (live runs) | — | Commit SHA for check-run anchoring. |
| `BASE_REF` | No | `origin/main` | Git ref used by change detection as the comparison base. |
| `DRY_RUN` | No | `false` | Set to `true` to run the full pipeline without creating a PR or notifying. |
| `WORKFLOW_RUN_ID` | No | Auto-generated | Identifier stamped on every audit event for this run. |
| `AUDIT_LOG_PATH` | No | `docs/generated/audit-log.ndjson` | Override the audit log output path. |
| `POLICY_RULES_PATH` | No | `config/policy-rules.yml` | Override the policy rules file path. |
| `PR_RESULT_PATH` | No | `docs/generated/pr-result.json` | Override the PR result file path read by the approval gate and notifier. |

---

## Day-to-Day Operations

### Run the workflow in dry-run mode (safe local validation)

```bash
DRY_RUN=true BASE_REF=HEAD python scripts/run_workflow.py
```

This exercises the full pipeline without creating a PR, posting GitHub notifications, or modifying the `docs/output` directory.

### Check the latest workflow result

```bash
cat docs/generated/workflow-summary.json
```

### View the audit log (most recent 20 events)

```bash
tail -20 docs/generated/audit-log.ndjson | python -m json.tool --no-ensure-ascii
```

### Generate aggregated monitoring metrics

```bash
python scripts/generate_monitoring.py
cat docs/generated/monitoring-metrics.json
```

### List available backups

```bash
ls -lt docs/backups/
cat docs/backups/latest-backup.json
```

### Send a manual success notification

```bash
GITHUB_TOKEN=<token> GITHUB_REPOSITORY=owner/repo GITHUB_SHA=<sha> \
  python scripts/notify.py workflow_success
```

---

## Incident Response Playbooks

### INC-01 — Validation failure (`validate_docs` step fails)

**Symptoms:**
- `workflow-summary.json` shows `status: failed` with `step: validate_docs`.
- GitHub check run is marked as failed.
- Maintainers receive a `workflow_failure` notification.

**Diagnosis:**
```bash
cat docs/generated/workflow-summary.json
cat docs/generated/audit-log.ndjson | grep validate_docs
```

**Remediation:**
1. Identify the specific validation error from the audit log or GitHub Actions output.
2. If the failure is a linting issue in generated content, review `config/policy-rules.yml` and the template files under `config/templates/`.
3. Correct the template or source content causing the issue.
4. Push a fix commit to `main` to trigger a fresh run, or run the workflow locally in dry-run mode to confirm the fix.
5. If the validator is flagging a false positive, update `config/policy-rules.yml` with the appropriate threshold adjustment and open a PR for review.

**No rollback required** — validation failures halt the pipeline before any files are replaced.

---

### INC-02 — Secret detected (`scan_secrets` step fails)

**Symptoms:**
- `docs/generated/secret-scan-result.json` shows `status: failed` with a list of issues.
- PR creation is blocked.
- A `workflow_failure` notification is dispatched.

**Diagnosis:**
```bash
cat docs/generated/secret-scan-result.json
```

**Remediation:**
1. Inspect the listed files for credential patterns (GitHub PATs matching `ghp_*`, AWS keys matching `AKIA*`, etc.).
2. Remove or mask the offending content from the source files or templates.
3. If the detected value is a false positive, review the pattern list in `scripts/scan_secrets.py` and open a PR to refine it.
4. Re-trigger the pipeline. Do **not** push the flagged content to the repository.
5. If a real secret was committed, rotate it immediately through the applicable service (GitHub, AWS, GCP) and follow the organization's secret-compromise runbook.

**No rollback required** — secret-scan failures halt the pipeline before backup or PR creation.

---

### INC-03 — Backup failure (`backup_docs` step fails)

**Symptoms:**
- `run_workflow.py` raises `RuntimeError: Backup step failed`.
- `workflow-summary.json` may be absent or incomplete.

**Diagnosis:**
```bash
cat docs/generated/audit-log.ndjson | grep backup_docs
ls docs/backups/
```

**Remediation:**
1. Check disk space and write permissions on `docs/backups/`.
2. Verify the `docs/output/` directory exists and is readable.
3. Run the backup step in isolation to collect the full error:
   ```bash
   python scripts/backup_docs.py backup
   ```
4. Resolve the underlying filesystem or permission issue.
5. Re-trigger the full pipeline.

---

### INC-04 — PR creation failure (`create_pr` step fails)

**Symptoms:**
- `docs/generated/pr-result.json` is absent or contains an error.
- No PR appears in the repository.
- A `workflow_failure` notification is sent.

**Diagnosis:**
```bash
cat docs/generated/audit-log.ndjson | grep create_pr
cat docs/generated/pr-result.json 2>/dev/null
```

**Common causes and fixes:**
| Cause | Fix |
| --- | --- |
| `GITHUB_TOKEN` lacks `pull-requests: write` | Re-issue or update the token scope. |
| Branch already exists from a previous partial run | Delete the stale branch via GitHub UI or `git push origin --delete <branch>`, then re-trigger. |
| Base branch protection rules block force-push | Confirm the token belongs to an actor with bypass rights, or delete the conflicting branch manually. |
| GitHub API rate limit exceeded | Wait for the rate limit window to reset (check `X-RateLimit-Reset` header) and re-trigger. |

---

### INC-05 — Approval gate not satisfied (`approval_gate` step fails)

**Symptoms:**
- `approval_gate.py` exits non-zero.
- PR exists but does not meet the required approvals.

**Diagnosis:**
```bash
cat docs/generated/pr-result.json
```
Check the PR on GitHub: confirm the required number of unique approvers have approved (default: 1).

**Remediation:**
1. Request review from the designated reviewer(s) listed in `config/policy-rules.yml` under `requested_reviewers`.
2. After the required approvals are in place, re-run the approval gate step or allow the workflow to re-trigger on the next push.
3. If the policy threshold needs adjustment, update `required_approvals` in `config/policy-rules.yml` and open a PR for review.

---

### INC-06 — Notification delivery failure (`notify` step fails)

**Symptoms:**
- `notify.py` exits non-zero.
- No GitHub check run or PR comment is visible.

**Diagnosis:**
```bash
cat docs/generated/audit-log.ndjson | grep notify
```

**Remediation:**
1. Verify `GITHUB_TOKEN`, `GITHUB_REPOSITORY`, and `GITHUB_SHA` are correctly set in the runner environment.
2. Check GitHub API status at [githubstatus.com](https://www.githubstatus.com).
3. Re-run the notifier manually once the token or API issue is resolved:
   ```bash
   GITHUB_TOKEN=<token> GITHUB_REPOSITORY=owner/repo GITHUB_SHA=<sha> \
     python scripts/notify.py workflow_failure
   ```
4. The core pipeline result is unaffected; notifications are a delivery concern only.

---

### INC-07 — Workflow exceeds timeout (15-minute limit)

**Symptoms:**
- GitHub Actions cancels the job at the `timeout-minutes: 15` boundary.
- No `workflow-summary.json` is produced.

**Diagnosis:**
Review the GitHub Actions step timing breakdown. Identify the stage that ran longest.

**Remediation:**
1. For generation timeouts: check if the repository has grown significantly. Enable incremental generation by narrowing `BASE_REF` to target only recent changes.
2. For validation timeouts: disable expensive link checks temporarily via `config/policy-rules.yml` (`require_links_validation: false`) until the cause is resolved.
3. Increase `timeout_minutes` in `config/pipeline-config.yml` if the workload legitimately requires more time, and document the change.

---

## Recovery Procedures

### Rollback documentation to the last known good state

Use this procedure when generated content has been committed but must be reverted.

```bash
# Restore docs/output from the most recent backup
python scripts/backup_docs.py rollback
```

This command reads `docs/backups/latest-backup.json`, finds the most recent `backup-<timestamp>` directory, and copies its contents back to `docs/output/`.

To roll back to a specific backup rather than the latest:

```bash
# List available backups
ls docs/backups/

# Manually copy from a specific backup
cp docs/backups/backup-20241201120000/* docs/output/
```

After rollback, verify the restored content:
```bash
ls -la docs/output/
```
Then open a PR or push the restored files to `main` following normal review procedures.

### Recover from a partial pipeline run

If the pipeline was interrupted mid-run and left artifacts in an inconsistent state:

1. Check which steps completed successfully:
   ```bash
   cat docs/generated/audit-log.ndjson | grep -E '"status"'
   ```
2. If backup completed but PR creation did not, the documentation on disk is already backed up. Re-trigger the pipeline normally.
3. If generation completed but validation did not, no files were replaced. Re-trigger the pipeline normally.
4. If a branch was created but the PR was not, delete the stale branch and re-trigger:
   ```bash
   git push origin --delete docs/update-<run-id>
   ```

### Clear a stale audit log

The audit log is append-only. For long-running repositories it may grow large. To archive and reset:

```bash
# Archive the current log
cp docs/generated/audit-log.ndjson docs/backups/audit-log-$(date +%Y%m%d).ndjson
# Remove the active log (a new one will be created on the next run)
rm docs/generated/audit-log.ndjson
```

Retain archived logs for at least 90 days to satisfy NFR-4 (auditability).

---

## Monitoring and Alerting

### Generate a metrics snapshot

```bash
python scripts/generate_monitoring.py
```

Output is written to `docs/generated/monitoring-metrics.json` with counts per step:

```json
{
  "total_events": 42,
  "by_step": {
    "generate_docs": {"ok": 10, "failed": 1, "other": 0, "total": 11},
    "validate_docs": {"ok": 9, "failed": 2, "other": 0, "total": 11}
  },
  "last_event": { ... }
}
```

### Key metrics to track

| Metric | Target | Alert Threshold |
| --- | --- | --- |
| Pipeline success rate | ≥ 99% | < 95% over 7 days |
| End-to-end duration | ≤ 5 min | > 10 min (two consecutive runs) |
| Validation failure rate | < 5% | > 15% over 7 days |
| Backup creation success rate | 100% | Any single failure |
| Secret-scan block rate | 0% (expected) | Any occurrence triggers review |

### Reviewing GitHub Actions logs

Navigate to **Repository → Actions → documentation-sync** in the GitHub UI. Each run lists step-level timing and output. Failed steps display the relevant error in the logs panel.

---

## Configuration Management

- All configuration lives in `config/pipeline-config.yml` and `config/policy-rules.yml`.
- Changes to either file must go through a PR reviewed by at least one designated administrator (see [docs/ownership.md](../docs/ownership.md)).
- Template files under `config/templates/` follow the same review process.
- After merging a configuration change, run the pipeline in dry-run mode to validate the new configuration before the next live run.
- Configuration files are version-controlled alongside the codebase; no out-of-band changes are permitted.

---

## Change Control for the Workflow Itself

- Changes to any file under `scripts/` or `.github/workflows/` require a PR with at least one reviewer from the **Pipeline Maintainer** role.
- Non-trivial changes (new stages, new integrations, timeout changes) must be validated in dry-run mode before merging to `main`.
- Breaking changes should be announced to all **Repository Owners** listed in [docs/ownership.md](../docs/ownership.md) at least one business day before deployment.
- Workflow version history is tracked through Git commit history. Tag major releases with `workflow-vX.Y` for easy rollback reference.

---

## Escalation Path

| Severity | Condition | First Responder | Escalation |
| --- | --- | --- | --- |
| P1 — Critical | Secret detected in generated docs; pipeline blocked across all repos | Pipeline Maintainer on-call | Repository Owner + Security team within 1 hour |
| P2 — High | Pipeline failure rate > 20% over 1 hour | Pipeline Maintainer | Repository Owner within 4 hours |
| P3 — Medium | Single pipeline failure; PR not created | On-duty maintainer | Pipeline Maintainer within 1 business day |
| P4 — Low | Notification delivery issue; core pipeline unaffected | Any maintainer | Log in issue tracker; no immediate escalation |

See [docs/ownership.md](../docs/ownership.md) for role definitions and contact information.
