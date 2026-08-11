# Troubleshooting Guide — Automated Documentation Synchronization

## How to Use This Guide

Each section describes a symptom, its most likely causes, diagnostic commands that use the actual artifacts produced by the pipeline, and concrete resolution steps. For incident-level escalation procedures, refer to [runbooks/operations.md](../runbooks/operations.md).

---

## Diagnostic Quick Reference

Run these commands first to orient yourself after any pipeline failure.

```bash
# Overall pipeline result
cat docs/generated/workflow-summary.json

# Most recent audit events (last 20)
tail -20 docs/generated/audit-log.ndjson

# Aggregated step-level success/failure counts
python scripts/generate_monitoring.py
cat docs/generated/monitoring-metrics.json

# Latest backup location
cat docs/backups/latest-backup.json
```

---

## Artifact Inventory

Before diagnosing, confirm which artifacts were produced. Missing artifacts indicate the pipeline halted before that stage completed.

| Artifact | Produced by | Indicates |
| --- | --- | --- |
| `docs/generated/change-detection.json` | `detect_changes.py` | Change detection ran. |
| `docs/generated/doc-generation.json` | `generate_docs.py` | Doc generation completed. |
| `docs/generated/secret-scan-result.json` | `scan_secrets.py` | Secret scan ran. |
| `docs/generated/workflow-summary.json` | `run_workflow.py` | Pipeline reached its final step. |
| `docs/generated/pr-result.json` | `create_pr.py` | A PR was created (live runs only). |
| `docs/generated/audit-log.ndjson` | `audit.py` | At least one step executed. |
| `docs/backups/latest-backup.json` | `backup_docs.py` | A backup was successfully created. |

---

## Issue: Pipeline exits non-zero but no error message is visible

**Cause:** A subprocess step failed and its stderr was suppressed, or `workflow-summary.json` was not written because the failure occurred before the summary step.

**Diagnosis:**
```bash
# Check the last audit event to see which step failed
tail -5 docs/generated/audit-log.ndjson

# Run the workflow with verbose output
DRY_RUN=true BASE_REF=HEAD python scripts/run_workflow.py 2>&1 | tee /tmp/pipeline-debug.log
```

**Resolution:** Identify the failing step from the audit log and refer to the matching section below.

---

## Issue: `detect_changes.py` produces an empty change list

**Symptom:** `docs/generated/change-detection.json` exists but contains an empty `changed_files` array.

**Cause:**
- `BASE_REF` points to the same commit as `HEAD`.
- The compared commits share no changes in tracked paths.

**Diagnosis:**
```bash
cat docs/generated/change-detection.json
git diff --name-only $BASE_REF HEAD
```

**Resolution:**
- Set `BASE_REF` to the correct ancestor commit or branch (e.g., `origin/main`).
- In GitHub Actions, the default is `origin/main`; verify the environment variable is set correctly in the workflow definition.

---

## Issue: `generate_docs.py` fails or produces empty output

**Symptom:** `docs/generated/doc-generation.json` is missing or contains `"files": []`.

**Cause:**
- Source files under `docs/output/` are absent.
- A template under `config/templates/` is missing or malformed.
- The generator encountered a read error on a source file.

**Diagnosis:**
```bash
cat docs/generated/doc-generation.json 2>/dev/null
ls config/templates/
python scripts/generate_docs.py 2>&1
```

**Resolution:**
1. Ensure all three template files exist: `config/templates/readme-template.md`, `api-template.md`, `architecture-template.md`.
2. Confirm the source paths referenced in the generator are readable.
3. Re-run the generator in isolation and examine stderr for the specific error.

---

## Issue: `validate_docs.py` fails with a readability or formatting error

**Symptom:** Audit log shows `"step": "validate_docs", "status": "failed"`.

**Cause:**
- Generated markdown does not meet the `minimum_readability_score: 80` threshold in `config/policy-rules.yml`.
- Missing or broken links (`require_links_validation: true`).
- Markdown formatting errors (`require_markdown_formatting: true`).

**Diagnosis:**
```bash
python scripts/validate_docs.py 2>&1
cat config/policy-rules.yml
```

**Resolution:**
1. Review the validation output for the specific check that failed.
2. Update the relevant template in `config/templates/` to produce compliant output.
3. If a link is permanently broken, remove or replace it in the template or the generated content.
4. If the threshold is too strict for the current content, adjust `minimum_readability_score` in `config/policy-rules.yml` and open a PR for review.
5. No rollback is needed — validation runs before any files are replaced.

---

## Issue: Secret scan fails — potential secret detected

**Symptom:** `docs/generated/secret-scan-result.json` shows `"status": "failed"` with one or more entries in `issues`.

**Cause:**
- A generated documentation file contains a string matching a known credential pattern (GitHub PATs, AWS keys, GCP API keys).
- A template or source file inadvertently includes a token or key as an example.

**Diagnosis:**
```bash
cat docs/generated/secret-scan-result.json
```
Inspect the listed files for the pattern mentioned in the issues list.

**Resolution:**
1. Open the flagged file and remove or mask the offending string (replace with a placeholder such as `<YOUR_TOKEN>`).
2. If the detection is a false positive, review the patterns in `scripts/scan_secrets.py` and open a PR to refine the regex.
3. **If a real secret was exposed**, rotate it immediately in the applicable service dashboard, then follow the organization's secret-compromise procedure.
4. Re-run the pipeline. Secret scan must pass before backup or PR creation proceeds.

---

## Issue: Backup step is skipped — "No documentation files found to backup"

**Symptom:** `backup_docs.py` returns `"status": "skipped"` and no backup directory is created.

**Cause:** `docs/output/` is empty or does not exist. The backup step only runs if there are existing files to preserve.

**Diagnosis:**
```bash
ls docs/output/
python scripts/backup_docs.py backup 2>&1
```

**Resolution:**
- If `docs/output/` is intentionally empty (first run), the skip is expected and benign. The workflow will continue.
- If `docs/output/` should have content, investigate why `generate_docs.py` did not write files there and resolve the generation issue first.

---

## Issue: Backup step fails with a permission or filesystem error

**Symptom:** `run_workflow.py` raises `RuntimeError: Backup step failed`.

**Diagnosis:**
```bash
python scripts/backup_docs.py backup 2>&1
ls -la docs/backups/
df -h .
```

**Resolution:**
1. Confirm the process has write permission to `docs/backups/`.
2. Check available disk space.
3. If running in a containerized environment, verify the volume is writable.
4. Resolve the filesystem issue and re-trigger the pipeline.

---

## Issue: PR creation fails — branch already exists

**Symptom:** `create_pr.py` fails with a GitHub API error referencing a branch that already exists.

**Diagnosis:**
```bash
cat docs/generated/audit-log.ndjson | grep create_pr
cat docs/generated/pr-result.json 2>/dev/null
```

**Resolution:**
```bash
# Delete the stale branch remotely (replace <branch-name> with the actual name)
git push origin --delete docs/update-<run-id>
```
Then re-trigger the pipeline. Alternatively, the stale PR can be closed via the GitHub UI and the branch deleted there.

---

## Issue: PR creation fails — `GITHUB_TOKEN` permission error (403)

**Symptom:** GitHub API returns HTTP 403 during branch creation or PR creation.

**Cause:** The token does not have `contents: write` or `pull-requests: write` permission.

**Resolution:**
1. For a Personal Access Token: regenerate with the required scopes at **GitHub → Settings → Developer settings → Personal access tokens**.
2. For GitHub Actions: verify the workflow YAML includes:
   ```yaml
   permissions:
     contents: write
     pull-requests: write
   ```
3. Update the token or workflow permissions, then re-trigger.

---

## Issue: Approval gate fails — PR has insufficient approvals

**Symptom:** `approval_gate.py` exits non-zero with a message about not meeting the required approval count.

**Diagnosis:**
```bash
cat docs/generated/pr-result.json
# Check current reviewer list
cat config/policy-rules.yml | grep required_approvals
```

**Resolution:**
1. Open the PR in GitHub and confirm no blocking reviews (changes-requested) exist.
2. Have the required number of reviewers (default: 1) submit an **Approve** review.
3. Re-run the approval gate check or wait for the next pipeline trigger.
4. To add automatic review requests, add GitHub usernames to `requested_reviewers` in `config/policy-rules.yml`.

---

## Issue: Notifications not delivered — check run not visible on GitHub

**Symptom:** The pipeline completed (exit 0) but no GitHub check run or PR comment appeared.

**Cause:**
- `GITHUB_TOKEN` lacks `checks: write` permission.
- `GITHUB_SHA` is not set or is incorrect.
- GitHub API is experiencing degraded availability.

**Diagnosis:**
```bash
# Manually test notification delivery
GITHUB_TOKEN=<token> GITHUB_REPOSITORY=owner/repo GITHUB_SHA=<sha> \
  python scripts/notify.py workflow_success 2>&1
```

**Resolution:**
1. Confirm all three required environment variables are set correctly.
2. Check the token's `checks` scope.
3. Check [githubstatus.com](https://www.githubstatus.com) for platform incidents.
4. The pipeline result is unaffected; only the notification surface is impacted.

---

## Issue: Workflow exceeds the 15-minute timeout

**Symptom:** GitHub Actions cancels the job. `workflow-summary.json` is absent.

**Diagnosis:**
- Review the Actions step timing panel in the GitHub UI.
- Identify the longest-running stage.

**Resolution by stage:**

| Slow stage | Resolution |
| --- | --- |
| `detect_changes` | Confirm `BASE_REF` is not pointing too far back in history. |
| `generate_docs` | Reduce the scope of generation by setting `BASE_REF` closer to `HEAD`. |
| `validate_docs` | Temporarily disable `require_links_validation` in `config/policy-rules.yml`. |
| `backup_docs` | Check for large files in `docs/output/`. Remove stale files that no longer need to be backed up. |

If the workload legitimately requires more time, increase `timeout_minutes` in `config/pipeline-config.yml` and document the change.

---

## Issue: Audit log is missing or incomplete

**Symptom:** `docs/generated/audit-log.ndjson` does not exist, or is empty after a run.

**Cause:**
- The pipeline failed before any audit event was written (unlikely; events are written at each step boundary).
- `AUDIT_LOG_PATH` is overridden to a path that is not writable.
- The `docs/generated/` directory was deleted or is not writable.

**Diagnosis:**
```bash
echo $AUDIT_LOG_PATH
ls -la docs/generated/
python -c "from scripts import audit; audit.append_event({'step': 'test', 'status': 'ok'}); print('Write OK')"
```

**Resolution:**
1. Ensure `docs/generated/` exists and is writable.
2. If `AUDIT_LOG_PATH` is overridden, confirm the target path is accessible.
3. The audit module creates the directory on import; if the directory is absent, a filesystem permission issue is the root cause.

---

## Collecting a Full Debug Bundle

When escalating an issue, collect the following files to give the Pipeline Maintainer complete context:

```bash
mkdir -p /tmp/debug-bundle
cp docs/generated/workflow-summary.json /tmp/debug-bundle/ 2>/dev/null
cp docs/generated/audit-log.ndjson /tmp/debug-bundle/ 2>/dev/null
cp docs/generated/secret-scan-result.json /tmp/debug-bundle/ 2>/dev/null
cp docs/generated/monitoring-metrics.json /tmp/debug-bundle/ 2>/dev/null
cp docs/generated/pr-result.json /tmp/debug-bundle/ 2>/dev/null
cp config/pipeline-config.yml /tmp/debug-bundle/
cp config/policy-rules.yml /tmp/debug-bundle/
echo "Bundle ready at /tmp/debug-bundle/"
ls /tmp/debug-bundle/
```

Attach the contents of `/tmp/debug-bundle/` to the incident ticket or GitHub Issue.
