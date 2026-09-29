#!/usr/bin/env python3
"""Validate plugin manifests, six Skill frontmatters and eval fixture links."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from paths import PLUGIN_ROOT, REFERENCES_ROOT, SKILLS_ROOT, TESTS_ROOT


SKILL_NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")
LEGACY_TEST_FILE = re.compile(r"(?:_before|_after(?:_editorial_only)?|_old|_backup|_v1|_temp)\.")


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_frontmatter(path: Path) -> dict[str, str]:
    content = path.read_text(encoding="utf-8")
    match = re.match(r"\A---\n(.*?)\n---\n", content, re.DOTALL)
    if not match:
        raise ValueError(f"{path.relative_to(PLUGIN_ROOT)}: missing YAML frontmatter")
    yaml_text = match.group(1)
    ruby = shutil.which("ruby")
    if ruby:
        check = subprocess.run(
            [ruby, "-e", 'require "yaml"; data = YAML.safe_load(STDIN.read); abort "frontmatter must be a mapping" unless data.is_a?(Hash); abort "name and description must be strings" unless data["name"].is_a?(String) && data["description"].is_a?(String)'],
            input=yaml_text, text=True, capture_output=True, check=False,
        )
        if check.returncode:
            raise ValueError(f"{path.relative_to(PLUGIN_ROOT)}: invalid YAML frontmatter: {check.stderr.strip()}")
    fields: dict[str, str] = {}
    for line in yaml_text.splitlines():
        key, separator, value = line.partition(":")
        if not separator or key not in {"name", "description"} or key in fields:
            raise ValueError(f"{path.relative_to(PLUGIN_ROOT)}: frontmatter supports one name and one description")
        fields[key] = value.strip().strip("\"'")
    if set(fields) != {"name", "description"} or not all(fields.values()):
        raise ValueError(f"{path.relative_to(PLUGIN_ROOT)}: name and description are required")
    if not SKILL_NAME.fullmatch(fields["name"]):
        raise ValueError(f"{path.relative_to(PLUGIN_ROOT)}: invalid Skill name {fields['name']!r}")
    if len(fields["description"]) > 1024 or "<" in fields["description"] or ">" in fields["description"]:
        raise ValueError(f"{path.relative_to(PLUGIN_ROOT)}: description violates Skill frontmatter limits")
    return fields


def validate_plugin() -> int:
    portable = _load_json(PLUGIN_ROOT / "plugin.json")
    codex = _load_json(PLUGIN_ROOT / ".codex-plugin" / "plugin.json")
    if portable.get("name") != codex.get("name"):
        raise ValueError("plugin.json and .codex-plugin/plugin.json names differ")
    for manifest in (portable, codex):
        if not isinstance(manifest.get("version"), str) or not SEMVER.fullmatch(manifest["version"]):
            raise ValueError("plugin manifest version must be semantic versioning")
        if not isinstance(manifest.get("description"), str) or not manifest["description"].strip():
            raise ValueError("plugin manifest description is required")
    if portable["version"].split("+", 1)[0] != codex["version"].split("+", 1)[0]:
        raise ValueError("portable and Codex plugin version prefixes differ")
    paths = list(SKILLS_ROOT.glob("*/SKILL.md"))
    if len(paths) != 6:
        raise ValueError(f"expected six discoverable Skills, found {len(paths)}")
    for path in paths:
        frontmatter = _parse_frontmatter(path)
        if frontmatter["name"] != path.parent.name:
            raise ValueError(f"{path}: frontmatter name must match its Skill directory")
    return len(paths)


def validate_generated() -> int:
    runtime_root = REFERENCES_ROOT / "shared-runtime"
    paths = sorted(runtime_root.glob("*.md")) if runtime_root.is_dir() else []
    if len(paths) != 6:
        raise ValueError(f"expected six generated shared-runtime files, found {len(paths)}")
    for path in paths:
        content = path.read_text(encoding="utf-8")
        for marker in ("GENERATED FILE: DO NOT EDIT", "<!-- Source: shared/", "Regenerate with: python3 scripts/sync_shared.py"):
            if marker not in content:
                raise ValueError(f"{path.relative_to(PLUGIN_ROOT)} missing generated marker {marker!r}")
    return len(paths)


def validate_evals() -> int:
    spec_path = TESTS_ROOT / "evals" / "cases" / "evals.json"
    spec = _load_json(spec_path)
    cases = spec.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("eval cases must be a non-empty array")
    ids = [case.get("id") for case in cases if isinstance(case, dict)]
    if len(ids) != len(cases) or any(not isinstance(item, str) or not item for item in ids) or len(ids) != len(set(ids)):
        raise ValueError("eval case IDs must be non-empty and unique")
    for case in cases:
        for field in ("input_fixture", "expected_fixture"):
            rel = case.get(field)
            if rel:
                path = (PLUGIN_ROOT / rel).resolve()
                if not path.is_file() or PLUGIN_ROOT.resolve() not in path.parents:
                    raise ValueError(f"{case['id']}: invalid {field} path {rel!r}")
    legacy = [path for path in (TESTS_ROOT / "evals").rglob("*") if path.is_file() and LEGACY_TEST_FILE.search(path.name)]
    if legacy:
        raise ValueError("legacy before/after/backup test files remain: " + ", ".join(str(path.relative_to(PLUGIN_ROOT)) for path in legacy))
    return len(cases)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="print the validation summary as JSON")
    args = parser.parse_args()
    plugin_name = _load_json(PLUGIN_ROOT / "plugin.json")["name"]
    summary = {"plugin": plugin_name, "skills": validate_plugin(), "generated_runtime_files": validate_generated(), "eval_cases": validate_evals()}
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"Plugin {summary['plugin']}: {summary['skills']} Skills, {summary['generated_runtime_files']} generated files, {summary['eval_cases']} eval cases valid")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(2) from error
