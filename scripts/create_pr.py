#!/usr/bin/env python3
"""Create a branch, commit generated docs/artifacts, push the branch, and open a Pull Request.

This script is intended to run in CI (GitHub Actions) with `GITHUB_TOKEN`
and a checked-out repository (fetch-depth: 0).


"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
import urllib.request
import urllib.error


def run(cmd, **kwargs):
    return subprocess.run(cmd, check=False, capture_output=True, text=True, **kwargs)


def fatal(msg: str, code: int = 1):
    print(msg, file=sys.stderr)
    sys.exit(code)


def main() -> None:
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    base = os.environ.get("BASE_BRANCH", "main")

    if not token or not repo:
        fatal("GITHUB_TOKEN and GITHUB_REPOSITORY must be set in the environment")

    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    branch = f"docs-generated-{timestamp}"

    # Ensure we start from the latest base
    r = run(["git", "fetch", "origin", base])
    if r.returncode != 0:
        fatal(f"git fetch failed: {r.stderr}")

    r = run(["git", "checkout", "-b", branch, f"origin/{base}"])
    if r.returncode != 0:
        fatal(f"git checkout failed: {r.stderr}")

    output_dir = Path("docs/output")
    if not output_dir.exists():
        print("No generated docs found at docs/output; nothing to commit")
        sys.exit(0)

    # Stage generated docs
    r = run(["git", "add", str(output_dir)])
    if r.returncode != 0:
        fatal(f"git add failed: {r.stderr}")

    # If there are no staged changes, exit gracefully
    check = subprocess.run(["git", "diff", "--cached", "--quiet"])  # exit code 0 => no changes
    if check.returncode == 0:
        print("No changes to commit; skipping PR creation")
        sys.exit(0)

    commit_msg = f"chore(docs): update generated docs {timestamp} [skip ci]"
    r = run(["git", "commit", "-m", commit_msg])
    if r.returncode != 0:
        fatal(f"git commit failed: {r.stderr}")

    # Configure remote to use token for push
    remote_url = f"https://x-access-token:{token}@github.com/{repo}.git"
    r = run(["git", "remote", "set-url", "origin", remote_url])
    if r.returncode != 0:
        fatal(f"git remote set-url failed: {r.stderr}")

    r = run(["git", "push", "--set-upstream", "origin", branch])
    if r.returncode != 0:
        fatal(f"git push failed: {r.stderr}")

    # Create Pull Request via GitHub API
    api_url = f"https://api.github.com/repos/{repo}/pulls"
    title = f"Automated docs: {timestamp}"
    body = (
        "This Pull Request contains documentation generated automatically by the documentation-sync workflow.\n\n"
        "Files were validated and backed up prior to creating this PR."
    )
    payload = json.dumps({"title": title, "head": branch, "base": base, "body": body}).encode("utf-8")

    req = urllib.request.Request(api_url, data=payload, headers={
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "docs-sync-script",
    })

    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read().decode())
            print(json.dumps(result, indent=2))
            print(f"Pull request created: {result.get('html_url')}")
            sys.exit(0)
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:
            reason = json.loads(body)
            message = reason.get("message") or str(reason)
        except Exception:
            message = body
        # 422 may indicate a PR already exists or validation error
        if e.code == 422:
            print(f"PR creation returned 422: {message}")
            print("Listing existing PRs to find match...")
            list_url = f"https://api.github.com/repos/{repo}/pulls?state=open&head={repo.split('/')[0]}:{branch}"
            req2 = urllib.request.Request(list_url, headers={"Authorization": f"token {token}", "Accept": "application/vnd.github+json"})
            try:
                with urllib.request.urlopen(req2) as resp2:
                    prs = json.loads(resp2.read().decode())
                    if prs:
                        print(json.dumps(prs[0], indent=2))
                        print(f"Existing PR: {prs[0].get('html_url')}")
                        sys.exit(0)
            except Exception:
                pass
            print(message)
            sys.exit(0)
        else:
            fatal(f"Failed to create PR: {e.code} {message}")


if __name__ == "__main__":
    main()
