#!/usr/bin/env python3
"""Regression tests for the packaged SWT Skill v0.4."""

from __future__ import annotations

import copy
import importlib.util
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from compare_budget import calculate  # noqa: E402
from budget import calculate_net_income, format_calculation  # noqa: E402
from state_context import (  # noqa: E402
    MISSING_VALUE,
    REQUIRED_FIELDS,
    SECTIONS,
    compare_offer_wage,
    load_state_profile,
    render_state_reference,
    resolve_state,
)
from validate_records import validate  # noqa: E402


SKILLS = {
    "swt",
    "swt-application",
    "swt-position",
    "swt-english",
    "swt-visa",
    "swt-arrival",
}
INTENTS = {
    "NAVIGATION",
    "DOCUMENT_CHECK",
    "DECISION",
    "INTERVIEW",
    "ENGLISH_PRACTICE",
    "FORM_FILLING",
    "CONFLICT",
    "CALCULATION",
    "EMERGENCY",
    "GENERAL_QA",
}


class BudgetTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((ROOT / "assets/budget-example.json").read_text(encoding="utf-8"))

    def scenario(self):
        return self.data["offers"][0]["scenarios"]["base"]

    def result(self):
        return calculate(self.data)["offers"][0]["scenarios"]["base"]

    def test_independent_arithmetic(self):
        result = self.result()
        self.assertEqual(result["gross_earned_usd"], "4992.00")
        self.assertEqual(result["living_expenses_usd"], "3120.00")
        self.assertEqual(result["net_cash_change_usd"], "-1928.00")
        self.assertEqual(result["net_cash_change_cny"], "-13881.60")
        self.assertEqual(result["startup_cash_required_usd"], "4400.00")

    def test_first_pay_cash_not_double_counted(self):
        self.scenario()["cash_living_before_first_pay_usd"] += 100
        self.assertEqual(self.result()["net_cash_change_usd"], "-1928.00")
        self.assertEqual(self.result()["startup_cash_required_usd"], "4500.00")

    def test_refund_timing_and_unpaid_wages(self):
        self.scenario()["deposit_returned_by_end_usd"] = 300
        self.assertEqual(self.result()["net_cash_change_usd"], "-1628.00")
        self.scenario()["gross_pay_unreceived_usd"] = 200
        self.assertEqual(self.result()["net_cash_change_usd"], "-1828.00")

    def test_unknown_not_zero(self):
        for value in (None, "140", True, float("nan"), float("inf"), -1):
            with self.subTest(value=value):
                self.scenario()["housing_weekly_usd"] = value
                with self.assertRaises(ValueError):
                    calculate(self.data)

    def test_second_job_not_in_base(self):
        self.scenario()["second_job_income_usd"] = 1000
        with self.assertRaises(ValueError):
            calculate(self.data)

    def test_input_not_mutated_or_sorted(self):
        original = copy.deepcopy(self.data)
        result = calculate(self.data)
        self.assertEqual(self.data, original)
        self.assertEqual([x["id"] for x in result["offers"]], [x["id"] for x in original["offers"]])

    def test_budget_cli_smoke(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "budget.py"), "--json", str(ROOT / "assets/net-income-example.json")],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('"offers"', result.stdout)


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((ROOT / "assets/collection-record-example.json").read_text(encoding="utf-8"))

    def claim(self):
        return self.data["agencies"][0]["claims"][0]

    def test_empty_is_not_ready(self):
        empty = json.loads((ROOT / "assets/collection-records.json").read_text(encoding="utf-8"))
        self.assertEqual(validate(empty)["readiness"], "empty template")
        self.assertEqual(validate(self.data)["pending_claims"], 6)

    def test_missing_source_rejected(self):
        self.claim()["source_ids"] = ["does-not-exist"]
        with self.assertRaises(ValueError):
            validate(self.data)

    def test_unverified_cannot_be_upgraded(self):
        self.claim()["status"] = "verified"
        with self.assertRaises(ValueError):
            validate(self.data)

    def test_missing_foreign_entity_rejected(self):
        self.claim()["field"] = "sponsor_id"
        self.claim()["value"] = "missing-sponsor"
        with self.assertRaises(ValueError):
            validate(self.data)


class NetIncomeCalculatorTests(unittest.TestCase):
    def manual_offer(self, **overrides):
        offer = {
            "id": "offer-a",
            "label": "Offer A",
            "state": "Texas",
            "wage_usd_per_hour": 16,
            "hours_per_week": 40,
            "start_date": "2027-06-01",
            "end_date": "2027-09-01",
            "rent_usd_per_week": 150,
            "transport_usd_per_week": 10,
            "food_usd_per_week": 50,
            "other_fixed_usd": 100,
            "tax": {
                "federal_income_tax_percent": 10,
                "state_income_tax_percent": 0,
            },
        }
        offer.update(overrides)
        return offer

    def calculate(self, offers, tax_mode="manual_rates", fx=7.2):
        data = {"tax_mode": tax_mode, "offers": offers}
        if fx is not None:
            data["fx_cny_per_usd"] = fx
        return calculate_net_income(data)

    def test_dates_calculate_days_weeks_and_full_net_income(self):
        item = self.calculate([self.manual_offer()])["offers"][0]
        self.assertEqual(item["period"]["calendar_days"], 93)
        self.assertEqual(item["period"]["work_weeks"], "13.28571428571428571428571429")
        self.assertEqual(item["gross_income_usd"], "8502.86")
        self.assertEqual(item["estimated_taxes"]["total_usd"], "850.29")
        self.assertEqual(item["housing_cost_usd"], "1992.86")
        self.assertEqual(item["other_known_costs_usd"], "897.14")
        self.assertEqual(item["estimated_net_income_usd"], "4762.57")
        self.assertEqual(item["estimated_net_income_cny"], "34290.48")

    def test_date_and_direct_weeks_conflict_needs_confirmation(self):
        offer = self.manual_offer(work_weeks=13)
        item = self.calculate([offer])["offers"][0]
        self.assertEqual(item["calculation_status"], "needs_confirmation")
        self.assertEqual(item["period"]["status"], "needs_confirmation")
        self.assertIsNone(item.get("estimated_net_income_usd"))

    def test_manual_mode_never_defaults_federal_tax_rate(self):
        offer = self.manual_offer(tax={"state_income_tax_percent": 0})
        item = self.calculate([offer])["offers"][0]
        self.assertEqual(item["calculation_status"], "tax_pending")
        self.assertEqual(item["estimated_taxes"]["status"], "needs_rates")
        self.assertIsNone(item["estimated_taxes"]["total_usd"])
        self.assertIsNone(item["estimated_net_income_usd"])

    def test_data_assisted_texas_uses_only_documented_state_zero(self):
        offer = self.manual_offer(
            work_weeks=13,
            tax={"known_federal_income_tax_withheld_usd": 500},
        )
        offer.pop("start_date")
        offer.pop("end_date")
        item = self.calculate([offer], tax_mode="data_assisted", fx=None)["offers"][0]
        self.assertEqual(item["estimated_taxes"]["status"], "known_withholding")
        self.assertEqual(item["estimated_taxes"]["federal_income_tax_usd"], "500.00")
        self.assertEqual(item["estimated_taxes"]["state_income_tax_usd"], "0.00")
        self.assertEqual(item["estimated_net_income_usd"], "4990.00")
        self.assertIsNone(item["estimated_net_income_cny"])
        self.assertEqual(item["fx_status"], "needs_current_or_user_provided_rate")

    def test_data_assisted_nonzero_state_stays_pending_without_evidence(self):
        offer = self.manual_offer(
            state="California",
            work_weeks=13,
            tax={"known_federal_income_tax_withheld_usd": 500},
        )
        offer.pop("start_date")
        offer.pop("end_date")
        item = self.calculate([offer], tax_mode="data_assisted")["offers"][0]
        self.assertEqual(item["calculation_status"], "tax_pending")
        self.assertIn("州所得税", item["estimated_taxes"]["pending_components"])
        self.assertIsNone(item["estimated_net_income_usd"])

    def test_named_work_states_are_accepted_without_inventing_rates(self):
        expected_codes = {
            "Texas": "TX", "California": "CA", "South Carolina": "SC", "New York": "NY",
        }
        for state, code in expected_codes.items():
            with self.subTest(state=state):
                offer = self.manual_offer(state=state, work_weeks=13, tax={})
                offer.pop("start_date")
                offer.pop("end_date")
                item = self.calculate([offer], tax_mode="data_assisted")["offers"][0]
                self.assertEqual(item["state"], code)
                if code == "TX":
                    self.assertEqual(item["estimated_taxes"]["state_income_tax_usd"], "0.00")
                else:
                    self.assertIn("州所得税", item["estimated_taxes"]["pending_components"])

    def test_multiple_offers_compare_only_complete_net_estimates(self):
        data = json.loads((ROOT / "assets/net-income-example.json").read_text(encoding="utf-8"))
        result = calculate_net_income(data)
        self.assertEqual(result["comparison"]["status"], "complete")
        self.assertEqual(result["comparison"]["offers_with_net_estimate"], ["offer-a", "offer-b"])
        output = format_calculation(result)
        self.assertIn("Offer 比较", output)
        self.assertIn("Offer A", output)
        self.assertIn("按 ¥7.20 / $", output)

    def test_overtime_requires_explicit_rate(self):
        offer = self.manual_offer(overtime_hours_per_week=2)
        with self.assertRaises(ValueError):
            self.calculate([offer])


class StateContextTests(unittest.TestCase):
    STATES_ROOT = ROOT / "references/knowledge/state_context/states"
    EXPECTED_CODES = {
        "AK", "AL", "AZ", "CA", "CO", "CT", "DE", "FL", "GA", "IA", "ID", "IL",
        "KY", "LA", "MA", "MD", "ME", "MI", "MN", "MO", "MT", "NC", "ND", "NH",
        "NJ", "NV", "NY", "OH", "PA", "SC", "SD", "TN", "TX", "UT", "VA", "VT",
        "WA", "WI", "WY",
    }

    def test_common_swt_locations_route_to_the_expected_state_profile(self):
        for location, code in {
            "Myrtle Beach": "SC",
            "Wisconsin Dells": "WI",
            "Ocean City": "MD",
        }.items():
            with self.subTest(location=location):
                resolution = resolve_state(location)
                self.assertIsNotNone(resolution)
                self.assertEqual(resolution.code, code)
                self.assertEqual(resolution.source, "state_index")
                self.assertTrue((self.STATES_ROOT / f"{code}.md").is_file())

    def test_state_index_points_only_to_existing_profiles(self):
        index = ROOT / "references/knowledge/state_context/STATE_INDEX.md"
        entries = []
        for line in index.read_text(encoding="utf-8").splitlines():
            if not line.startswith("|"):
                continue
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            if len(cells) == 2 and cells[0] not in {"地点", "---"}:
                entries.append(cells[1])
        self.assertTrue(entries)
        self.assertTrue(all((self.STATES_ROOT / f"{code}.md").is_file() for code in entries))

    def test_explicit_state_beats_the_index(self):
        resolution = resolve_state("Myrtle Beach, South Carolina")
        self.assertIsNotNone(resolution)
        self.assertEqual((resolution.code, resolution.source), ("SC", "explicit_state_name"))
        direct_code = resolve_state("SC")
        self.assertIsNotNone(direct_code)
        self.assertEqual((direct_code.code, direct_code.source), ("SC", "explicit_state_code"))

    def test_unknown_location_does_not_guess_a_state(self):
        self.assertIsNone(resolve_state("A made-up resort town"))

    def test_offer_wage_stays_authoritative_when_compared_with_state_context(self):
        profile = load_state_profile("SC")
        self.assertEqual(profile["常见时薪"], "$10–12.99/h")
        self.assertEqual(compare_offer_wage(15, profile["常见时薪"]), "higher")
        self.assertEqual(profile["常见时薪"], "$10–12.99/h")

    def test_missing_state_field_renders_the_required_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            profile_path = Path(directory) / "SC.md"
            profile_path.write_text("# South Carolina\n\n州: South Carolina\n州缩写: SC\n常见时薪: \n", encoding="utf-8")
            profile = load_state_profile("SC", Path(directory))
        self.assertEqual(profile["常见时薪"], MISSING_VALUE)
        self.assertEqual(profile["医疗"], MISSING_VALUE)

    def test_every_excel_covered_state_has_the_exact_product_schema(self):
        profiles = {path.stem for path in self.STATES_ROOT.glob("*.md")}
        self.assertEqual(profiles, self.EXPECTED_CODES)
        forbidden = ("overtime", "tips", "水电", "押金", "居住条件", "Uber", "是否依赖汽车", "淡旺季", "排班兼容度", "evidence")
        for code in profiles:
            content = (self.STATES_ROOT / f"{code}.md").read_text(encoding="utf-8")
            with self.subTest(state=code):
                for section in SECTIONS:
                    self.assertIn(f"## {section}", content)
                for field in REQUIRED_FIELDS:
                    self.assertEqual(len(re.findall(rf"^{re.escape(field)}:", content, re.MULTILINE)), 1)
                self.assertFalse(any(term.casefold() in content.casefold() for term in forbidden))

    def test_state_reference_is_never_written_as_city_level_data(self):
        output = render_state_reference(load_state_profile("SC"))
        self.assertIn("## 州级参考｜South Carolina", output)
        self.assertIn("根据 Howard SWT 数据库中的州级数据：", output)
        for city in ("Myrtle Beach", "Wisconsin Dells", "Ocean City"):
            self.assertNotIn(city, output)
        position = (ROOT / "skills/swt-position/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("具体 Offer 数据优先于州级常见数据", position)
        self.assertIn("绝不猜测", position)
        self.assertIn("禁止把州级资料写成“某城市平均工资”", position)

class PackageTests(unittest.TestCase):
    def test_manifests_agree(self):
        portable = json.loads((ROOT / "plugin.json").read_text(encoding="utf-8"))
        compat = json.loads((ROOT / ".codex-plugin/plugin.json").read_text(encoding="utf-8"))
        for key in ("name", "version", "description", "author"):
            self.assertEqual(portable[key], compat[key])
        self.assertEqual(portable["name"], "swt-skill")
        self.assertEqual(portable["version"], "0.4.0")
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
            self.assertIn("runtime-version: 0.4.0", runtime)

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
            "swt-position": {"location-offer.md", "budget-method.md", "tax-estimation.md", "state-income-tax.md"},
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
        data = json.loads((ROOT / "tests/evals/evals.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(data["cases"]), 24)
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
        ):
            self.assertIn(case_id, ids)
        result = json.loads((ROOT / "tests/evals/results/v0.4-plugin-author-smoke.json").read_text(encoding="utf-8"))
        self.assertEqual(result["summary"], {"cases_run": 11, "passed": 11, "failed": 0})
        self.assertTrue(all(item["status"] == "passed" for item in result["results"]))
        runtime = json.loads((ROOT / "tests/evals/results/v0.4-installed-runtime.json").read_text(encoding="utf-8"))
        self.assertEqual(runtime["summary"], {"cases_run": 3, "passed": 3, "failed": 0})
        self.assertTrue(all(item["status"] == "passed" for item in runtime["results"]))

    def test_net_income_calculator_is_packaged(self):
        self.assertTrue((SCRIPTS / "budget.py").is_file())
        self.assertTrue((ROOT / "assets/net-income-example.json").is_file())
        position = (ROOT / "skills/swt-position/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("CALCULATION", position)
        self.assertIn("scripts/budget.py", position)

    def test_no_legacy_layout_references(self):
        for path in ROOT.rglob("*.md"):
            content = path.read_text(encoding="utf-8")
            self.assertNotIn("swt-skill/references", content, str(path))
            self.assertNotIn("evidence-boundaries.md", content, str(path))
        for path in (ROOT / "plugin.json", ROOT / ".codex-plugin/plugin.json"):
            content = path.read_text(encoding="utf-8")
            self.assertIn('"version": "0.4.0"', content)


if __name__ == "__main__":
    unittest.main(verbosity=2)
