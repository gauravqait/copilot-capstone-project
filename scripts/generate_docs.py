#!/usr/bin/env python3
"""Generate starter documentation artifacts from templates and repository context."""
"""creates initial documentation artifacts when relevant changes are detected."""

import json
import os
from pathlib import Path
from datetime import datetime


def load_change_context() -> dict:
    path = Path("docs/generated/change-detection.json")
    if not path.exists():
        return {"should_generate_docs": False, "changed_files": []}
    return json.loads(path.read_text(encoding="utf-8"))


def generate_docs() -> dict:
    context = load_change_context()
    if not context.get("should_generate_docs", False):
        return {"status": "skipped", "reason": "No relevant changes detected"}

    output_dir = Path("docs/output")
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    readme_path = output_dir / "README.generated.md"
    api_path = output_dir / "API.generated.md"
    architecture_path = output_dir / "ARCHITECTURE.generated.md"

    readme_path.write_text(
        "# Generated README\n\nThis file was generated as part of the core workflow execution phase.\n",
        encoding="utf-8",
    )
    api_path.write_text(
        "# Generated API Documentation\n\nThis file was generated as part of the core workflow execution phase.\n",
        encoding="utf-8",
    )
    architecture_path.write_text(
        "# Generated Architecture Documentation\n\nThis file was generated as part of the core workflow execution phase.\n",
        encoding="utf-8",
    )

    return {
        "status": "generated",
        "timestamp": timestamp,
        "files": [str(readme_path), str(api_path), str(architecture_path)],
    }


def main() -> None:
    result = generate_docs()
    output_path = Path("docs/generated/doc-generation.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
