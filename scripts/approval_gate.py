#!/usr/bin/env python3
"""Approval gate logic for documentation-sync PRs."""

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, List

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.policy import require_review, requested_reviewers, required_approvals

DRY_RUN = os.environ.get("DRY_RUN", "false").strip().lower() in ("1", "true", "yes", "on")


def request_json(url: str, token: str, method: str = "GET", data=None):
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "docs-sync-approval",
    }
    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        payload = exc.read().decode()
        raise RuntimeError(f"GitHub API request failed: {exc.code} {payload}") from exc


def load_pr_result(path: Path) -> Dict:
    if not path.exists():
        raise RuntimeError(f"PR result file missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def get_pr_reviews(repo: str, pr_number: int, token: str) -> List[Dict]:
    url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}/reviews"
    return request_json(url, token)


def has_required_approvals(reviews: List[Dict], approvals_needed: int) -> bool:
    approvals = [r for r in reviews if r.get("state") == "APPROVED"]
    unique_approvers = set(r.get("user", {}).get("login") for r in approvals if r.get("user"))
    return len(unique_approvers) >= approvals_needed


def add_reviewers(repo: str, pr_number: int, token: str, reviewers: List[str]) -> None:
    if not reviewers:
        return
    url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}/requested_reviewers"
    request_json(url, token, method="POST", data={"reviewers": reviewers})


def main() -> None:
    pr_path = Path(os.environ.get("PR_RESULT_PATH", "docs/generated/pr-result.json"))
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")

    if not token or not repo:
        raise RuntimeError("GITHUB_TOKEN and GITHUB_REPOSITORY are required")

    if DRY_RUN:
        print("Dry-run mode: approval gate skipped because no PR will be created.")
        sys.exit(0)

    policy_review = require_review()
    if not policy_review:
        print("Review not required by policy. Approval gate passes.")
        sys.exit(0)

    pr_result = load_pr_result(pr_path)
    pr_status = pr_result.get("status")
    if pr_status == "skipped":
        print("No PR was created, so approval gating is not required.")
        sys.exit(0)
    if pr_status != "passed":
        raise RuntimeError("No successful PR available for approval gating")

    pr_number = pr_result.get("pr_number")
    if not pr_number:
        raise RuntimeError("PR number missing from PR result")

    reviewers = requested_reviewers()
    if reviewers:
        add_reviewers(repo, pr_number, token, reviewers)
        print(f"Requested reviewers: {reviewers}")

    approvals_needed = required_approvals()
    reviews = get_pr_reviews(repo, pr_number, token)
    if has_required_approvals(reviews, approvals_needed):
        print(f"Approval gate passed with {approvals_needed} approvals")
        sys.exit(0)

    print(f"Approval gate pending: {approvals_needed} approvals required")
    sys.exit(1)


if __name__ == "__main__":
    main()
