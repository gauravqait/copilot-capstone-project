#!/usr/bin/env python3
"""Generate documentation artifacts by rendering templates with repository context."""

import json
import os
from pathlib import Path
from datetime import datetime


TEMPLATES_DIR = Path(os.environ.get("TEMPLATES_PATH", "config/templates"))

TEMPLATE_MAP = {
    "README.generated.md": "readme-template.md",
    "API.generated.md": "api-template.md",
    "ARCHITECTURE.generated.md": "architecture-template.md",
}


def load_change_context() -> dict:
    path = Path("docs/generated/change-detection.json")
    if not path.exists():
        return {"should_generate_docs": False, "changed_files": []}
    return json.loads(path.read_text(encoding="utf-8"))


def render_template(template_path: Path, substitutions: dict) -> str:
    """Read a template file and replace {{key}} placeholders with context values."""
    content = template_path.read_text(encoding="utf-8")
    for key, value in substitutions.items():
        content = content.replace(f"{{{{{key}}}}}", value)
    return content


def generate_docs() -> dict:
    context = load_change_context()
    if not context.get("should_generate_docs", False):
        return {"status": "skipped", "reason": "No relevant changes detected"}

    output_dir = Path("docs/output")
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    repository = os.environ.get("GITHUB_REPOSITORY", "unknown/repository")
    changed_files = context.get("changed_files", [])
    changed_files_list = (
        "\n".join(f"- `{f}`" for f in changed_files) if changed_files else "- *(no changes detected)*"
    )

    substitutions = {
        "repository": repository,
        "timestamp": timestamp,
        "changed_files": changed_files_list,
    }

    written_files = []
    for output_name, template_name in TEMPLATE_MAP.items():
        template_path = TEMPLATES_DIR / template_name
        output_path = output_dir / output_name
        if template_path.exists():
            content = render_template(template_path, substitutions)
        else:
            # Graceful fallback: write a minimal stub if the template is missing.
            content = f"# {output_name}\n\nGenerated for `{repository}` at {timestamp}.\n"
        output_path.write_text(content, encoding="utf-8")
        written_files.append(str(output_path))

    return {
        "status": "generated",
        "timestamp": timestamp,
        "repository": repository,
        "changed_files_count": len(changed_files),
        "files": written_files,
    }


def main() -> None:
    result = generate_docs()
    output_path = Path("docs/generated/doc-generation.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
