#!/usr/bin/env python3
"""Plugin packaging, generation and eval-contract integration tests."""
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
from budget import calculate_position_overview, format_position_overview  # noqa: E402

SKILLS = {"swt", "swt-application", "swt-position", "swt-english", "swt-visa", "swt-arrival"}
INTENTS = {"NAVIGATION", "DOCUMENT_CHECK", "DECISION", "INTERVIEW", "ENGLISH_PRACTICE", "FORM_FILLING", "CONFLICT", "CALCULATION", "EMERGENCY", "GENERAL_QA"}

class PackageTests(unittest.TestCase):
    def test_manifests_agree(self):
        portable = json.loads((ROOT / "plugin.json").read_text(encoding="utf-8"))
        compat = json.loads((ROOT / ".codex-plugin/plugin.json").read_text(encoding="utf-8"))
        for key in ("name", "version", "description", "author"):
            if key == "version":
                self.assertEqual(portable[key].split("+", 1)[0], compat[key].split("+", 1)[0])
            else:
                self.assertEqual(portable[key], compat[key])
        self.assertEqual(portable["name"], "swt-plugin")
        self.assertEqual(portable["version"], "0.5.0")
        self.assertEqual(compat["skills"], "./skills/")
        self.assertEqual(compat["author"]["name"], "Howard")

    def test_exactly_six_discoverable_skills(self):
        found = {p.parent.name for p in (ROOT / "skills").glob("*/SKILL.md")}
        self.assertEqual(found, SKILLS)
        for skill in SKILLS:
            content = (ROOT / "skills" / skill / "SKILL.md").read_text(encoding="utf-8")
            match = re.match(r"^---\n(.*?)\n---\n", content, re.DOTALL)
            self.assertIsNotNone(match)
            frontmatter = match.group(1)
            self.assertRegex(frontmatter, rf"(?m)^name:\s*{re.escape(skill)}$")
            self.assertRegex(frontmatter, r"(?m)^description:\s*\S+")

    def test_shared_runtime_is_current(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "sync_shared.py"), "--check"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for skill in SKILLS:
            self.assertTrue((ROOT / "references/shared-runtime" / f"{skill}.md").is_file())

    def test_shared_single_source_and_attribution_injection(self):
        source = (ROOT / "shared/creator-attribution.md").read_text(encoding="utf-8")
        marker = "SWT Skill -作者：Howard 欢迎关注我的账号：@哎哟不想上早八啊（全平台同名）"
        self.assertEqual(source.count(marker), 1)
        for skill in SKILLS:
            runtime = (ROOT / "references/shared-runtime" / f"{skill}.md").read_text(encoding="utf-8")
            self.assertEqual(runtime.count(marker), 1)
            self.assertIn("GENERATED FILE: DO NOT EDIT", runtime)
            self.assertIn("runtime-version: 0.5.0", runtime)
            self.assertIn("source: shared/editorial-policy.md", runtime)

    def test_structured_compression_architecture_and_fixture(self):
        framework = (ROOT / "shared/answer-framework.md").read_text(encoding="utf-8")
        policy = (ROOT / "shared/editorial-policy.md").read_text(encoding="utf-8")
        for stage in ("Analyze", "Compress", "Present", "Edit"):
            self.assertIn(stage, framework)
        for priority in ("P1", "P2", "P3", "P4"):
            self.assertIn(priority, framework)
        self.assertIn("RAW INFORMATION ≠ USER ANSWER", framework)
        self.assertIn("Clarity Gate", policy)
        self.assertIn("若否，重新组织回答", policy)

        fixture = ROOT / "tests/evals/fixtures"
        after = (ROOT / "tests/evals/expected/position_compare_ssn_dependency_expected.md").read_text(encoding="utf-8")
        input_data = json.loads((fixture / "position_compare_ssn_dependency_input.json").read_text(encoding="utf-8"))
        self.assertEqual(after.strip(), format_position_overview(calculate_position_overview(input_data)).strip())
        self.assertEqual(re.findall(r"(?m)^## \d\. [^\n]+", after), [
            "## 1. 核心数据", "## 2. 回本测算", "## 3. 注意事项", "## 4. 继续看什么？",
        ])
        self.assertEqual(len(re.findall(r"(?m)^\|---(?:\|---)+\|$", after)), 3)
        self.assertIn("Hotel B（City B）的预计缺口最小", after.splitlines()[0])
        self.assertIn("最终预计结余", after)
        self.assertIn("预计税费", after)
        self.assertIn("¥20,000", after)
        self.assertIn("延迟到账不等于工资损失", after)
        self.assertIn("Restaurant A", after)
        self.assertIn("Hotel B", after)

    def test_detail_cli_does_not_reprint_overview(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "budget.py"), "--detail", "housing", str(ROOT / "assets/position-overview-example.json")],
            cwd=ROOT, text=True, capture_output=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("住宿按", result.stdout)
        self.assertNotIn("## 1.", result.stdout)

    def test_router_contract(self):
        router = (ROOT / "shared/routing-policy.md").read_text(encoding="utf-8")
        for intent in INTENTS:
            self.assertIn(intent, router)
        for dimension in ("Task Type", "SWT Stage", "Known Context", "Risk Level"):
            self.assertIn(dimension, router)
        for skill in SKILLS:
            self.assertIn(f"`{skill}`", router + (ROOT / "skills/swt/SKILL.md").read_text(encoding="utf-8"))

    def test_canonical_references_are_root_owned(self):
        expected = {
            "swt-application": {"agency-sponsor.md", "application-materials.md"},
            "swt-position": {"location-offer.md", "budget-method.md", "tax-estimation.md", "state-income-tax.md", "default-assumptions.json"},
            "swt-english": {"english-practice.md"},
            "swt-visa": {"visa-ds2019.md"},
            "swt-arrival": {"predeparture-program.md"},
            "swt": set(),
        }
        for skill, references in expected.items():
            root = ROOT / "skills" / skill
            content = (root / "SKILL.md").read_text(encoding="utf-8")
            self.assertEqual([path.name for path in root.iterdir()], ["SKILL.md"])
            self.assertIn(f"../../references/shared-runtime/{skill}.md", content)
            for name in references:
                self.assertTrue((ROOT / "references" / name).is_file())
                self.assertIn(f"../../references/{name}", content)

    def test_flat_runtime_mapping_rewrites_only_deployment_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [sys.executable, str(SCRIPTS / "sync_shared.py"), "--runtime-root", directory],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            installed = Path(directory) / "swt-position"
            position = (installed / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn("references/shared-runtime.md", position)
            self.assertNotIn("../../references/", position)
            self.assertTrue((installed / "references/knowledge/state_context/STATE_INDEX.md").is_file())
            self.assertTrue((installed / "references/budget-method.md").is_file())
            self.assertTrue((installed / "references/default-assumptions.json").is_file())
            self.assertTrue((installed / "scripts/state_context.py").is_file())
            self.assertFalse((installed / "scripts/sync_shared.py").exists())
            self.assertTrue((installed / "assets/net-income-example.json").is_file())
            route = subprocess.run(
                [sys.executable, str(installed / "scripts/state_context.py"), "resolve", "Myrtle Beach"],
                cwd=installed,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(route.returncode, 0, route.stdout + route.stderr)
            self.assertIn('"state": "SC"', route.stdout)
            overview = subprocess.run(
                [sys.executable, str(installed / "scripts/budget.py"), str(installed / "assets/position-overview-example.json")],
                cwd=installed, text=True, capture_output=True, check=False,
            )
            self.assertEqual(overview.returncode, 0, overview.stdout + overview.stderr)
            self.assertIn("## 2. 回本测算", overview.stdout)

    def test_no_duplicate_state_or_shared_scripts_in_source(self):
        self.assertEqual(len(list((ROOT / "references/knowledge/state_context").glob("STATE_INDEX.md"))), 1)
        self.assertEqual(len(list(ROOT.rglob("state_context.py"))), 1)
        self.assertEqual(len(list(ROOT.rglob("budget.py"))), 1)
        self.assertFalse(any((ROOT / "skills").rglob("references")))

    def test_local_markdown_links_resolve(self):
        pattern = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
        for path in ROOT.rglob("*.md"):
            for target in pattern.findall(path.read_text(encoding="utf-8")):
                target = target.strip("<>")
                if target.startswith(("http://", "https://", "#", "mailto:")):
                    continue
                target = target.split("#", 1)[0]
                self.assertTrue((path.parent / target).resolve().exists(), f"{path}: {target}")

    def test_behavior_contract_has_all_required_cases(self):
        data = json.loads((ROOT / "tests/evals/cases/evals.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(data["cases"]), 24)
        self.assertEqual(len(data["reader_facing_rubric"]), 5)
        ids = {case["id"] for case in data["cases"]}
        self.assertEqual(len(ids), len(data["cases"]))
        for case_id in (
            "calculation-12-direct-net-income", "calculation-13-choice-first-missing-fields",
            "calculation-14-date-week-conflict", "calculation-15-tax-modes",
            "calculation-16-state-assisted-pending", "calculation-17-multiple-offers-and-fx",
            "state-context-18-myrtle-beach", "state-context-19-wisconsin-dells",
            "state-context-20-ocean-city", "state-context-21-explicit-state",
            "state-context-22-offer-priority", "state-context-23-unknown-location",
            "state-context-24-schema-and-wording",
            "position-27-ssn-dependency-overview",
            "compression-28-navigation", "compression-29-visa-conflict",
            "compression-30-application-status", "compression-31-english-feedback",
            "position-overview-32-minimum-input", "position-overview-33-rent-override",
            "position-overview-34-state-over-global", "position-overview-35-two-offers-three-tables",
            "position-overview-36-caution-dash", "position-overview-37-housing-followup",
            "position-overview-38-hours-recalculation", "position-overview-39-food-override",
        ):
            self.assertIn(case_id, ids)
        fixture_paths = (
            ROOT / "tests/evals/fixtures/position_compare_ssn_dependency_input.json",
            ROOT / "tests/evals/expected/position_compare_ssn_dependency_expected.md",
            ROOT / "tests/evals/cases/position_compare_ssn_dependency.md",
        )
        self.assertTrue(all(path.is_file() for path in fixture_paths))
        self.assertEqual(len(json.loads((ROOT / "tests/evals/cases/evals.json").read_text(encoding="utf-8"))["cases"]), len(ids))

    def test_net_income_calculator_is_packaged(self):
        self.assertTrue((SCRIPTS / "budget.py").is_file())
        self.assertTrue((ROOT / "assets/net-income-example.json").is_file())
        self.assertTrue((ROOT / "assets/position-overview-example.json").is_file())
        position = (ROOT / "skills/swt-position/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("position_overview", position)
        self.assertIn("scripts/budget.py", position)

    def test_no_legacy_layout_references(self):
        for path in ROOT.rglob("*.md"):
            content = path.read_text(encoding="utf-8")
            self.assertNotIn("swt-skill/references", content, str(path))
            self.assertNotIn("evidence-boundaries.md", content, str(path))
        for path in (ROOT / "plugin.json", ROOT / ".codex-plugin/plugin.json"):
            content = path.read_text(encoding="utf-8")
            self.assertIn('"version": "0.5.0"', content)
        for path in (SCRIPTS / "budget.py", SCRIPTS / "state_context.py", SCRIPTS / "sync_shared.py"):
            self.assertNotIn("Path(__file__).resolve().parents[1]", path.read_text(encoding="utf-8"), str(path))
