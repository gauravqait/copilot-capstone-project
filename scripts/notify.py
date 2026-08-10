#!/usr/bin/env python3
"""Send GitHub-native workflow and PR notifications for documentation-sync."""
"""notify.py making sure success/failure signals are emitted consistently."""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional


def get_env(name: str, default: Optional[str] = None) -> str:
    value = os.environ.get(name, default)
    if value is None:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def request_json(url: str, token: str, method: str = "GET", data: Any = None) -> Dict[str, Any]:
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "docs-sync-notify",
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


def create_check_run(repo: str, sha: str, token: str, name: str, status: str, conclusion: str, summary: str, details: Dict[str, Any] = None) -> None:
    api_url = f"https://api.github.com/repos/{repo}/check-runs"
    payload: Dict[str, Any] = {
        "name": name,
        "head_sha": sha,
        "status": status,
        "conclusion": conclusion,
        "output": {
            "title": name,
            "summary": summary,
        },
    }
    if details:
        payload["output"]["text"] = json.dumps(details, indent=2)
    request_json(api_url, token, method="POST", data=payload)


def create_pr_comment(repo: str, pr_number: int, token: str, body: str) -> None:
    api_url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
    request_json(api_url, token, method="POST", data={"body": body})


def load_pr_result(result_path: Path) -> Dict[str, Any]:
    if not result_path.exists():
        raise RuntimeError(f"PR result not found at {result_path}")
    return json.loads(result_path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Send GitHub notifications for documentation-sync")
    parser.add_argument("event", choices=["workflow_success", "workflow_failure", "pr_ready"])
    parser.add_argument("--pr-result", default="docs/generated/pr-result.json")
    args = parser.parse_args()

    token = get_env("GITHUB_TOKEN")
    repo = get_env("GITHUB_REPOSITORY")
    sha = get_env("GITHUB_SHA")
    run_id = os.environ.get("GITHUB_RUN_ID", "unknown")
    server = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
    run_url = f"{server}/{repo}/actions/runs/{run_id}"
    check_name = "documentation-sync"

    if args.event == "workflow_success":
        summary = f"Documentation sync workflow completed successfully. [Run details]({run_url})"
        create_check_run(repo, sha, token, check_name, status="completed", conclusion="success", summary=summary, details={"run_url": run_url})
        print(summary)
        return

    if args.event == "workflow_failure":
        summary = f"Documentation sync workflow failed. [Run details]({run_url})"
        create_check_run(repo, sha, token, check_name, status="completed", conclusion="failure", summary=summary, details={"run_url": run_url})
        print(summary)
        return

    if args.event == "pr_ready":
        pr_result = load_pr_result(Path(args.pr_result))
        status = pr_result.get("status")
        if status == "skipped":
            print("PR creation was skipped; no PR-ready notification needed.")
            sys.exit(0)
        if status != "passed":
            raise RuntimeError("PR was not created successfully; cannot notify PR ready state")

        pr_url = pr_result.get("pr_url")
        pr_number = pr_result.get("pr_number")
        if not pr_url or not pr_number:
            raise RuntimeError("PR result does not contain required pr_url and pr_number")

        summary = f"Documentation Pull Request is ready for review: {pr_url}"
        create_check_run(repo, sha, token, check_name, status="completed", conclusion="neutral", summary=summary, details={"pr_url": pr_url})
        comment_body = (
            f"A documentation PR has been created and is ready for review.\n\n"
            f"Pull request: {pr_url}\n\n"
            f"Workflow run: {run_url}"
        )
        create_pr_comment(repo, int(pr_number), token, comment_body)
        print(summary)
        return


if __name__ == "__main__":
    main()
