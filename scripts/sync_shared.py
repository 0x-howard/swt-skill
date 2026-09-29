#!/usr/bin/env python3
"""Build canonical shared runtime references and optional flat deployments."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SHARED_ROOT = PLUGIN_ROOT / "shared"
SKILLS_ROOT = PLUGIN_ROOT / "skills"
REFERENCES_ROOT = PLUGIN_ROOT / "references"
RUNTIME_ROOT = REFERENCES_ROOT / "shared-runtime"
CURRENT_VERSION = json.loads((PLUGIN_ROOT / "plugin.json").read_text(encoding="utf-8"))["version"]

COMMON_SOURCES = (
    "interaction-protocol.md",
    "answer-framework.md",
    "creator-attribution.md",
    "risk-policy.md",
    "evidence-policy.md",
    "state-schema.md",
)

SOURCES_BY_SKILL = {
    "swt": COMMON_SOURCES + ("routing-policy.md", "stage-model.md"),
    "swt-application": COMMON_SOURCES,
    "swt-position": COMMON_SOURCES,
    "swt-english": COMMON_SOURCES,
    "swt-visa": COMMON_SOURCES + ("official-sources.md",),
    "swt-arrival": COMMON_SOURCES + ("official-sources.md",),
}

DOMAIN_REFERENCES_BY_SKILL = {
    "swt": (),
    "swt-application": ("agency-sponsor.md", "application-materials.md"),
    "swt-position": ("location-offer.md", "budget-method.md", "tax-estimation.md", "state-income-tax.md"),
    "swt-english": ("english-practice.md",),
    "swt-visa": ("visa-ds2019.md",),
    "swt-arrival": ("predeparture-program.md",),
}


def render(skill: str, sources: tuple[str, ...]) -> str:
    chunks: list[str] = []
    digest = hashlib.sha256()
    for filename in sources:
        path = SHARED_ROOT / filename
        if not path.is_file():
            raise FileNotFoundError(f"missing shared source: {path}")
        body = path.read_text(encoding="utf-8").strip()
        digest.update(filename.encode("utf-8"))
        digest.update(b"\0")
        digest.update(body.encode("utf-8"))
        chunks.append(f"<!-- source: shared/{filename} -->\n\n{body}")

    checksum = digest.hexdigest()
    header = (
        "# Generated Shared Runtime\n\n"
        "<!-- GENERATED FILE: DO NOT EDIT. -->\n"
        f"<!-- runtime-version: {CURRENT_VERSION} -->\n"
        "<!-- Source maintenance: run `python3 scripts/sync_shared.py` from the source root after editing shared/. -->\n"
        f"<!-- skill: {skill}; source-sha256: {checksum} -->"
    )
    return header + "\n\n" + "\n\n---\n\n".join(chunks) + "\n"


def sync(check: bool) -> list[str]:
    stale: list[str] = []
    for skill, sources in SOURCES_BY_SKILL.items():
        skill_root = SKILLS_ROOT / skill
        if not (skill_root / "SKILL.md").is_file():
            raise FileNotFoundError(f"missing Skill: {skill_root / 'SKILL.md'}")
        output = RUNTIME_ROOT / f"{skill}.md"
        expected = render(skill, sources)
        if check:
            if not output.is_file() or output.read_text(encoding="utf-8") != expected:
                stale.append(str(output.relative_to(PLUGIN_ROOT)))
            continue
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(expected, encoding="utf-8")
    return stale


def _copy_tree(source: Path, destination: Path) -> None:
    if source.is_dir():
        shutil.copytree(source, destination, dirs_exist_ok=True)
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def map_runtime(runtime_root: Path) -> None:
    """Materialize the source into WorkBuddy's flat per-Skill layout.

    The source remains canonical and is never flattened.  Each mapped Skill gets
    the same local ``references/``, ``scripts/`` and ``assets/`` roots, while its
    SKILL.md links are rewritten from source-root paths to those local roots.
    """
    destination = runtime_root.expanduser().resolve()
    if destination == PLUGIN_ROOT or PLUGIN_ROOT in destination.parents:
        raise ValueError("--runtime-root must be outside the source plugin root")
    if not RUNTIME_ROOT.exists():
        sync(check=False)

    state_context = REFERENCES_ROOT / "knowledge" / "state_context"
    scripts = PLUGIN_ROOT / "scripts"
    assets = PLUGIN_ROOT / "assets"
    for skill, domain_refs in DOMAIN_REFERENCES_BY_SKILL.items():
        skill_destination = destination / skill
        skill_destination.mkdir(parents=True, exist_ok=True)
        skill_text = (SKILLS_ROOT / skill / "SKILL.md").read_text(encoding="utf-8")
        skill_text = skill_text.replace(
            f"../../references/shared-runtime/{skill}.md", "references/shared-runtime.md"
        )
        skill_text = skill_text.replace("../../references/", "references/")
        (skill_destination / "SKILL.md").write_text(skill_text, encoding="utf-8")

        references_destination = skill_destination / "references"
        _copy_tree(RUNTIME_ROOT / f"{skill}.md", references_destination / "shared-runtime.md")
        for filename in domain_refs:
            _copy_tree(REFERENCES_ROOT / filename, references_destination / filename)
        _copy_tree(state_context, references_destination / "knowledge" / "state_context")
        for script in scripts.glob("*.py"):
            if script.name == "sync_shared.py":
                continue
            _copy_tree(script, skill_destination / "scripts" / script.name)
        _copy_tree(assets, skill_destination / "assets")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail when generated references are stale")
    parser.add_argument(
        "--runtime-root",
        type=Path,
        help="also materialize a flat per-Skill runtime under this deployment directory",
    )
    args = parser.parse_args()
    if args.check and args.runtime_root:
        parser.error("--check and --runtime-root cannot be combined")
    stale = sync(args.check)
    if stale:
        print("stale generated references:")
        for path in stale:
            print(f"- {path}")
        return 1
    if args.runtime_root:
        map_runtime(args.runtime_root)
        print(f"flat Skill runtime mapped to {args.runtime_root}")
    else:
        print("shared runtime references are current" if args.check else "shared runtime references updated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
