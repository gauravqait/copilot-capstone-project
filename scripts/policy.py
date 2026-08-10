#!/usr/bin/env python3
"""Load and interpret policy rules for documentation-sync."""

import os
import re
from pathlib import Path
from typing import Any, Dict, List

POLICY_PATH = Path(os.environ.get("POLICY_RULES_PATH", "config/policy-rules.yml"))


def parse_scalar(value: str) -> Any:
    if value == "":
        return ""
    if value.lower() in ("true", "false"):
        return value.lower() == "true"
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if value.startswith("[") and value.endswith("]"):
        items = [item.strip() for item in value[1:-1].split(",") if item.strip()]
        return [parse_scalar(item) for item in items]
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    return value


def load_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Policy file not found: {path}")

    root: Dict[str, Any] = {}
    parents: List[Any] = [root]
    indents: List[int] = [-1]

    with path.open("r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.rstrip("\n")
            if not line.strip() or line.lstrip().startswith("#"):
                continue

            indent = len(line) - len(line.lstrip())
            text = line.lstrip()

            if text.startswith("- "):
                value = parse_scalar(text[2:].strip())
                while indent <= indents[-1]:
                    parents.pop()
                    indents.pop()
                container = parents[-1]
                if not isinstance(container, list):
                    raise ValueError("List item found in non-list container")
                container.append(value)
                continue

            if ":" not in text:
                continue

            key, raw_value = text.split(":", 1)
            key = key.strip()
            value_text = raw_value.strip()
            value: Any = parse_scalar(value_text) if value_text != "" else {}

            while indent <= indents[-1]:
                parents.pop()
                indents.pop()

            container = parents[-1]
            if isinstance(container, dict):
                container[key] = value
            else:
                raise ValueError("Mapping found in non-dict container")

            if value == {}:
                container[key] = []
                parents.append(container[key])
                indents.append(indent)

    return root


def load_policy() -> Dict[str, Any]:
    return load_yaml(POLICY_PATH)


def policy_value(path: List[str], default: Any = None) -> Any:
    policy = load_policy()
    current: Any = policy
    for segment in path:
        if isinstance(current, dict) and segment in current:
            current = current[segment]
        else:
            return default
    return current


def require_review() -> bool:
    return bool(policy_value(["policies", "require_review_for_generated_docs"], False))


def required_approvals() -> int:
    return int(policy_value(["policies", "required_approvals"], 1))


def requested_reviewers() -> List[str]:
    reviewers = policy_value(["policies", "requested_reviewers"], [])
    return list(reviewers) if isinstance(reviewers, list) else []


def require_secret_scan() -> bool:
    return bool(policy_value(["policies", "require_secret_scan"], True))


def require_backup_before_replace() -> bool:
    return bool(policy_value(["policies", "require_backup_before_replace"], True))
