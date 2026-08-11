# Production Rollout Plan — Automated Documentation Synchronization

## Purpose

This document covers everything needed to carry T16 from validated implementation to live production operation. It is structured as five sequential sections:

1. [Rollout Plan](#1-rollout-plan) — phased approach and go/no-go criteria.
2. [Deployment Checklist](#2-deployment-checklist) — step-by-step actions with sign-off fields.
3. [Initial Monitoring Plan](#3-initial-monitoring-plan) — what to watch and for how long.
4. [Rollback Readiness Checklist](#4-rollback-readiness-checklist) — confirm rollback works before going live.
5. [Stabilization Guidance](#5-stabilization-guidance) — operating practices for the first 30 days.

**Cross-references:**
- Day-to-day operations: [runbooks/operations.md](../runbooks/operations.md)
- Incident troubleshooting: [docs/troubleshooting.md](troubleshooting.md)
- Roles and contacts: [docs/ownership.md](ownership.md)

---

## 1. Rollout Plan

### 1.1 Rollout Phases

#### Phase 0 — Local Dry-Run Validation (pre-deployment gate)

Run the entire pipeline locally in dry-run mode against the production repository clone. This is the final pre-flight check before any live configuration is applied.

```bash
# Clone the target production repository
git clone https://github.com/<owner>/<repo>.git prod-repo
cd prod-repo

# Copy the workflow scripts and config from this implementation
cp -r <impl-root>/scripts ./scripts
cp -r <impl-root>/config ./config

# Run the pipeline end-to-end in dry-run mode
DRY_RUN=true BASE_REF=HEAD python scripts/run_workflow.py
```

**Gate criteria — all must pass before proceeding to Phase 1:**
- [ ] Exit code is 0.
- [ ] `docs/generated/workflow-summary.json` shows `"status": "completed"` and `"dry_run": true`.
- [ ] `docs/generated/change-detection.json` is present.
- [ ] `docs/generated/doc-generation.json` is present.
- [ ] `docs/generated/secret-scan-result.json` shows `"status": "passed"`.
- [ ] `docs/generated/audit-log.ndjson` contains events for all five pipeline steps.
- [ ] No errors in stderr.

#### Phase 1 — Staging Repository (smoke test on a non-critical repo)

Enable the workflow on a low-risk or internal repository first. This validates GitHub Actions integration, token permissions, and PR automation end-to-end without risk to production documentation.

**Gate criteria — all must pass before proceeding to Phase 2:**
- [ ] GitHub Actions workflow triggers on push to `main`.
- [ ] All pipeline stages complete without error.
- [ ] A documentation PR is opened automatically.
- [ ] The PR receives the correct check-run status via `notify.py`.
- [ ] A backup is created in `docs/backups/` within the staging repository.
- [ ] The PR can be reviewed and merged through the normal approval gate.
- [ ] No production documentation was modified.

#### Phase 2 — Production Repository (live rollout)

Apply the workflow to the target production repository after Phase 1 passes. Monitor closely for the first 14 days (see [Section 3](#3-initial-monitoring-plan)).

**Rollout approach:** Enable the workflow on one production repository at a time. Do not batch-enable across multiple repositories simultaneously. This limits blast radius if a configuration issue is discovered.

### 1.2 Go/No-Go Criteria

The Repository Owner (see [docs/ownership.md](ownership.md)) makes the final go/no-go decision before each phase transition.

| Criterion | Required for Phase 1 | Required for Phase 2 |
| --- | --- | --- |
| Phase 0 dry-run passes | Yes | Yes |
| Phase 1 staging run passes | — | Yes |
| Rollback readiness confirmed | Yes | Yes |
| Pipeline Maintainer available during rollout window | Yes | Yes |
| All credentials rotated or confirmed current | Yes | Yes |
| Runbook reviewed by incoming team | Yes | Yes |
| Branch protection enabled on target repo | — | Yes |

### 1.3 Rollout Window

Perform each phase transition during a low-traffic window (e.g., beginning of a sprint, Tuesday–Thursday, business hours). Avoid rollout on Fridays, immediately before holidays, or during active release periods. The Pipeline Maintainer must be available for the first two hours after each phase transition.

---

## 2. Deployment Checklist

Complete each item in order. Record the date and approver initials in the **Done / By** column before proceeding to the next item.

### 2.1 Repository and Access Setup

| # | Action | Done / By |
| --- | --- | --- |
| 1 | Confirm target repository exists and the rollout team has the correct access level (see [docs/ownership.md](ownership.md) access table). | |
| 2 | Enable branch protection on `main`: require PR reviews, require status checks to pass, disallow direct pushes. | |
| 3 | Add `GITHUB_TOKEN` (or a repository-scoped PAT) to the repository's Actions secrets with `contents: write`, `pull-requests: write`, and `checks: write` scope. | |
| 4 | Confirm `GITHUB_REPOSITORY` and `GITHUB_SHA` are available as standard GitHub Actions context variables (they are injected automatically by GitHub). | |
| 5 | Add required reviewers to `config/policy-rules.yml` under `requested_reviewers`. | |

### 2.2 Configuration Verification

| # | Action | Done / By |
| --- | --- | --- |
| 6 | Open `config/pipeline-config.yml`. Confirm `trigger_branch: main`, `timeout_minutes: 15`, and `retries: 2` are appropriate for the target repository. | |
| 7 | Open `config/policy-rules.yml`. Confirm `require_review_for_generated_docs: true` and `required_approvals: 1` match the team's governance requirements. | |
| 8 | Confirm all three template files exist: `config/templates/readme-template.md`, `config/templates/api-template.md`, `config/templates/architecture-template.md`. | |
| 9 | Confirm `docs/output/`, `docs/backups/`, and `docs/generated/` directories exist (they can be empty). | |

### 2.3 Pre-Deployment Validation

| # | Action | Done / By |
| --- | --- | --- |
| 10 | Run Phase 0 dry-run validation locally (see [Section 1.1](#11-rollout-phases)) and confirm all gate criteria pass. | |
| 11 | Run the rollback readiness checklist ([Section 4](#4-rollback-readiness-checklist)) and confirm all items pass. | |
| 12 | Confirm `python scripts/generate_monitoring.py` runs without error. | |
| 13 | Confirm `docs/backups/latest-backup.json` can be created by running `python scripts/backup_docs.py backup` once manually (even against an empty `docs/output/`). | |

### 2.4 GitHub Actions Workflow Activation

| # | Action | Done / By |
| --- | --- | --- |
| 14 | Copy `.github/workflows/documentation-sync.yml` into the target repository. Confirm it references `scripts/run_workflow.py` as its main entry point. | |
| 15 | Push the workflow file to `main` via a reviewed PR. Do **not** bypass branch protection for this push. | |
| 16 | Trigger a manual workflow run from **Actions → documentation-sync → Run workflow** using `DRY_RUN=true` to validate the GitHub Actions environment. | |
| 17 | Confirm the manual run exits successfully and produces `docs/generated/workflow-summary.json` with `"status": "completed"`. | |
| 18 | Remove `DRY_RUN=true` from the workflow trigger inputs (or set the default to `false`) so that live runs create PRs. | |

### 2.5 First Live Run

| # | Action | Done / By |
| --- | --- | --- |
| 19 | Push a trivial change to `main` (e.g., update a comment in a script) to trigger the first live pipeline run. | |
| 20 | Confirm the pipeline completes without error in GitHub Actions. | |
| 21 | Confirm a documentation PR is opened with the correct description and CI check-run status. | |
| 22 | Confirm the audit log (`docs/generated/audit-log.ndjson`) contains events for all pipeline stages. | |
| 23 | Confirm a backup was created in `docs/backups/`. | |
| 24 | Merge the generated PR through the normal review process. | |
| 25 | Record the first successful run ID and PR number in this document for reference. | |

**First live run result (fill in after run):**

| Field | Value |
| --- | --- |
| Run date | |
| GitHub Actions run ID | |
| PR number | |
| Duration (seconds) | |
| Approver | |

### 2.6 Post-Deployment Sign-Off

| # | Action | Done / By |
| --- | --- | --- |
| 26 | Repository Owner confirms the rollout is complete and the workflow is operating as expected. | |
| 27 | Update [docs/ownership.md](ownership.md) contact table with production team names and handles. | |
| 28 | Notify all stakeholders that the workflow is live. | |
| 29 | Schedule the first monitoring review (7 days after live rollout). | |

---

## 3. Initial Monitoring Plan

### 3.1 Monitoring Windows

| Window | Focus | Responsible |
| --- | --- | --- |
| Days 1–3 (hypercare) | Watch every run. Confirm artifacts, audit log, and PR creation for each push to `main`. | Pipeline Maintainer |
| Days 4–7 | Daily spot-check of `monitoring-metrics.json`. Triage any failures. | Pipeline Maintainer |
| Days 8–14 | Every-other-day review. Confirm success rate ≥ 99%. | Pipeline Maintainer |
| Days 15–30 | Weekly review. Compare metrics against targets. Update runbook if new failure modes are observed. | Pipeline Maintainer / Repository Owner |

### 3.2 Daily Monitoring Commands (Days 1–7)

Run each morning during hypercare:

```bash
# Check overall pipeline health
python scripts/generate_monitoring.py
cat docs/generated/monitoring-metrics.json

# Tail the audit log for recent events
tail -30 docs/generated/audit-log.ndjson

# Confirm latest backup exists and is recent
cat docs/backups/latest-backup.json
```

### 3.3 Key Metrics and Targets

| Metric | Target | Alert if |
| --- | --- | --- |
| Pipeline success rate | ≥ 99% | < 95% over any 7-day window |
| End-to-end duration | ≤ 5 min (NFR-1) | > 10 min on two consecutive runs |
| Validation failure rate | < 5% | > 15% over 7 days |
| Secret-scan block rate | 0% (expected) | Any single occurrence |
| Backup creation success rate | 100% | Any single failure |
| PR creation success rate | 100% (non-dry-run) | Any single failure |
| Audit log written per run | All stages present | Any missing stage |

### 3.4 Monitoring Log Template

Record each review in this table during the 30-day stabilization window. Add rows as needed.

| Date | Runs | Pass | Fail | Avg duration | Issues noted | Action taken |
| --- | --- | --- | --- | --- | --- | --- |
| | | | | | | |
| | | | | | | |
| | | | | | | |

### 3.5 End-of-Stabilization Review (Day 30)

At the end of the 30-day window the Pipeline Maintainer and Repository Owner conduct a joint review:

1. Calculate the 30-day success rate from `monitoring-metrics.json`.
2. Review all incidents logged during the window.
3. Update `runbooks/operations.md` with any new incident playbooks discovered.
4. Update `docs/troubleshooting.md` with any new failure modes.
5. Adjust `config/pipeline-config.yml` thresholds if warranted.
6. Confirm whether NFR-1 (≤ 5 min), NFR-2 (up to 10,000 files), and NFR-3 (≥ 99% reliability) are being met.
7. Declare the workflow stable or open a follow-up work item for remediation.

---

## 4. Rollback Readiness Checklist

Verify rollback capability **before** enabling the workflow in production. This checklist must pass during Phase 0 and again during Phase 1.

### 4.1 Backup Mechanism

| # | Check | Pass / Fail |
| --- | --- | --- |
| 1 | `python scripts/backup_docs.py backup` exits 0. | |
| 2 | A timestamped directory is created under `docs/backups/`. | |
| 3 | `docs/backups/latest-backup.json` is written and points to the new backup directory. | |
| 4 | A `backup-manifest.json` exists inside the backup directory listing all copied files. | |

### 4.2 Rollback Mechanism

| # | Check | Pass / Fail |
| --- | --- | --- |
| 5 | With at least one backup present, `python scripts/backup_docs.py rollback` exits 0. | |
| 6 | Files from the most recent backup are copied back to `docs/output/`. | |
| 7 | The restored files match the originals (spot-check content of one restored file). | |
| 8 | A second rollback with no newer backup still exits cleanly (idempotent behavior). | |

### 4.3 Pipeline Rollback (GitHub)

| # | Check | Pass / Fail |
| --- | --- | --- |
| 9 | The Pipeline Maintainer can delete a stale branch: `git push origin --delete docs-generated-<timestamp>`. | |
| 10 | A PR created by the pipeline can be closed and its branch deleted from the GitHub UI without repository-level errors. | |
| 11 | After closing a pipeline-created PR, a new push to `main` triggers a fresh pipeline run without carryover state. | |

### 4.4 Configuration Rollback

| # | Check | Pass / Fail |
| --- | --- | --- |
| 12 | A previous version of `config/pipeline-config.yml` or `config/policy-rules.yml` can be restored from Git history with `git checkout <hash> -- config/<file>`. | |
| 13 | After restoring a configuration file, the pipeline runs correctly with the restored settings. | |

**Rollback sign-off:** All 13 checks must be marked Pass before the workflow is enabled on a production repository.

| Verified by | Date |
| --- | --- |
| | |

---

## 5. Stabilization Guidance

### 5.1 First 72 Hours (Hypercare)

- The Pipeline Maintainer monitors **every** pipeline run and confirms artifacts.
- Any failure is triaged immediately using `docs/troubleshooting.md`.
- P1 and P2 failures are escalated within the timeframes defined in `runbooks/operations.md`.
- No non-emergency changes are made to `scripts/`, `config/`, or the workflow definition during this window.

### 5.2 Configuration Freeze

During the 30-day stabilization window, changes to the following files require Repository Owner approval (elevated from the normal Pipeline Maintainer approval):

- `config/pipeline-config.yml`
- `config/policy-rules.yml`
- `.github/workflows/documentation-sync.yml`
- Any file under `scripts/`

The rationale: changes to these files during stabilization can make it harder to distinguish regressions from new configuration behavior. Freeze the baseline, observe, then adjust.

### 5.3 Handling the First Failure

When the first live failure occurs:

1. **Do not disable the workflow immediately.** Check whether the failure is a transient or consistent issue.
2. Run `cat docs/generated/workflow-summary.json` and `tail -20 docs/generated/audit-log.ndjson` to identify the failing stage.
3. Consult `docs/troubleshooting.md` for the matching symptom.
4. If the failure is a consistent bug, disable the workflow trigger temporarily by setting `DRY_RUN=true` in the workflow inputs while the fix is developed.
5. Apply the fix via a reviewed PR. Run the pipeline in dry-run mode to confirm the fix before re-enabling live runs.
6. Document the failure and resolution in the monitoring log ([Section 3.4](#34-monitoring-log-template)).

### 5.4 Scaling to Additional Repositories

After the first production repository is stable (Day 30 review passed):

1. Apply the same deployment checklist ([Section 2](#2-deployment-checklist)) to each additional repository. Do not skip any steps.
2. Run Phase 0 dry-run validation against each new target repository before enabling the workflow.
3. Add the new repository to the monitoring log as a separate entry.
4. Ensure `config/policy-rules.yml` is reviewed for repository-specific approval requirements before rollout.
5. The NFR-7 requirement (scalable to multiple repositories) is satisfied when each repository has its own isolated configuration, backup store, and audit log — do not share `docs/generated/` or `docs/backups/` across repositories.

### 5.5 Post-Stabilization Improvements

After the 30-day window closes, the following improvements are recommended for consideration. They are outside the T16 scope but documented here for continuity:

| Improvement | Benefit | Effort |
| --- | --- | --- |
| External audit log aggregator (e.g., CloudWatch, Elastic) | Longer retention, cross-repo search, dashboard support | Medium |
| Slack or Teams webhook notification channel | Faster failure alerting, reduces GitHub API dependency | Low |
| Automated backup retention cleanup | Prevents `docs/backups/` from growing unbounded | Low |
| OIDC-based authentication for workflow token | Eliminates long-lived PAT, improves security posture | Medium |
| Module-level incremental generation | Reduces runtime for large repositories, supports NFR-2 at scale | High |
| Performance SLO dashboard | Continuous visibility into NFR-1 and NFR-3 compliance | Medium |

---

## Completion Criteria for T16

T16 is complete when all of the following conditions are met:

- [ ] Phase 0 (local dry-run) passes all gate criteria.
- [ ] Phase 1 (staging repository) passes all gate criteria.
- [ ] Phase 2 (production repository) is enabled and the first live run succeeds.
- [ ] Deployment checklist ([Section 2](#2-deployment-checklist)) is fully signed off.
- [ ] Rollback readiness checklist ([Section 4](#4-rollback-readiness-checklist)) is fully verified.
- [ ] 7-day monitoring review is completed and success rate ≥ 99%.
- [ ] 30-day stabilization review is completed and all NFRs are confirmed as met or remediated.
- [ ] Repository Owner signs off on production readiness.

**Production readiness sign-off:**

| Role | Name | Date |
| --- | --- | --- |
| Repository Owner | | |
| Pipeline Maintainer | | |
