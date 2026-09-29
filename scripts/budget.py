#!/usr/bin/env python3
"""Deterministic SWT estimated-net-income calculator.

This script estimates one first-job SWT work period from explicit offer inputs. It
does not fetch tax rates, file taxes, or treat payroll withholding as final tax
liability. It is deliberately usable for one or multiple offers.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any


ZERO = Decimal("0")
WEEK = Decimal("7")

STATE_ALIASES = {
    "alabama": "AL", "al": "AL", "alaska": "AK", "ak": "AK",
    "arizona": "AZ", "az": "AZ", "arkansas": "AR", "ar": "AR",
    "california": "CA", "ca": "CA", "colorado": "CO", "co": "CO",
    "connecticut": "CT", "ct": "CT", "delaware": "DE", "de": "DE",
    "florida": "FL", "fl": "FL", "georgia": "GA", "ga": "GA",
    "hawaii": "HI", "hi": "HI", "idaho": "ID", "id": "ID",
    "illinois": "IL", "il": "IL", "indiana": "IN", "in": "IN",
    "iowa": "IA", "ia": "IA", "kansas": "KS", "ks": "KS",
    "kentucky": "KY", "ky": "KY", "louisiana": "LA", "la": "LA",
    "maine": "ME", "me": "ME", "maryland": "MD", "md": "MD",
    "massachusetts": "MA", "ma": "MA", "michigan": "MI", "mi": "MI",
    "minnesota": "MN", "mn": "MN", "mississippi": "MS", "ms": "MS",
    "missouri": "MO", "mo": "MO", "montana": "MT", "mt": "MT",
    "nebraska": "NE", "ne": "NE", "nevada": "NV", "nv": "NV",
    "new hampshire": "NH", "nh": "NH", "new jersey": "NJ", "nj": "NJ",
    "new mexico": "NM", "nm": "NM", "new york": "NY", "ny": "NY",
    "north carolina": "NC", "nc": "NC", "north dakota": "ND", "nd": "ND",
    "ohio": "OH", "oh": "OH", "oklahoma": "OK", "ok": "OK",
    "oregon": "OR", "or": "OR", "pennsylvania": "PA", "pa": "PA",
    "rhode island": "RI", "ri": "RI", "south carolina": "SC", "sc": "SC",
    "south dakota": "SD", "sd": "SD", "tennessee": "TN", "tn": "TN",
    "texas": "TX", "tx": "TX", "utah": "UT", "ut": "UT",
    "vermont": "VT", "vt": "VT", "virginia": "VA", "va": "VA",
    "washington": "WA", "wa": "WA", "west virginia": "WV", "wv": "WV",
    "wisconsin": "WI", "wi": "WI", "wyoming": "WY", "wy": "WY",
}

# This small list intentionally only contains a state whose wage personal-income-tax
# status is documented by the Plugin reference. More states may be added only with
# a dated primary source, not by guessing a rate.
ASSISTED_ZERO_STATE_INCOME_TAX = {
    "TX": {
        "state": "Texas",
        "source": "Texas Comptroller, A Field Guide to the Taxes of Texas (FY 2025): no state or local income tax.",
    }
}


def _money(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return str(value.quantize(Decimal(".01"), rounding=ROUND_HALF_UP))


def _number(value: Any, path: str, *, positive: bool = False) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise ValueError(f"{path}: requires an explicit number")
    result = Decimal(str(value))
    if not result.is_finite() or result < ZERO or (positive and result == ZERO):
        qualifier = "positive finite" if positive else "finite nonnegative"
        raise ValueError(f"{path}: requires a {qualifier} number")
    return result


def _optional_number(data: dict[str, Any], key: str, path: str) -> Decimal | None:
    if key not in data:
        return None
    return _number(data[key], f"{path}.{key}")


def _exact_keys(data: dict[str, Any], allowed: set[str], required: set[str], path: str) -> None:
    unknown = set(data) - allowed
    missing = required - set(data)
    if unknown or missing:
        raise ValueError(f"{path}: missing={sorted(missing)}, unexpected={sorted(unknown)}")


def _state_code(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{path}: requires a U.S. state name or abbreviation")
    normalized = " ".join(value.lower().replace(".", "").split())
    if normalized not in STATE_ALIASES:
        raise ValueError(f"{path}: unsupported or unrecognized U.S. state")
    return STATE_ALIASES[normalized]


def _period(raw: dict[str, Any], path: str) -> dict[str, Any]:
    has_start, has_end, has_weeks = "start_date" in raw, "end_date" in raw, "work_weeks" in raw
    if has_start != has_end:
        raise ValueError(f"{path}: start_date and end_date must be provided together")
    if not has_start and not has_weeks:
        raise ValueError(f"{path}: provide start_date/end_date or work_weeks")

    date_weeks: Decimal | None = None
    calendar_days: int | None = None
    if has_start:
        if not isinstance(raw["start_date"], str) or not isinstance(raw["end_date"], str):
            raise ValueError(f"{path}: dates must use YYYY-MM-DD")
        start, end = date.fromisoformat(raw["start_date"]), date.fromisoformat(raw["end_date"])
        if end < start:
            raise ValueError(f"{path}: end_date must be on or after start_date")
        # A supplied end date is treated as the expected last paid work day.
        calendar_days = (end - start).days + 1
        date_weeks = Decimal(calendar_days) / WEEK

    supplied_weeks = _number(raw["work_weeks"], f"{path}.work_weeks", positive=True) if has_weeks else None
    if date_weeks is not None and supplied_weeks is not None and abs(date_weeks - supplied_weeks) > Decimal("0.01"):
        return {
            "status": "needs_confirmation",
            "calendar_days": calendar_days,
            "date_calculated_weeks": str(date_weeks),
            "provided_work_weeks": str(supplied_weeks),
            "message": "日期换算的工作周数与直接输入周数冲突；请确认以哪个口径计算。",
        }

    weeks = supplied_weeks if supplied_weeks is not None else date_weeks
    assert weeks is not None
    return {
        "status": "ready",
        "calendar_days": calendar_days,
        "work_weeks": str(weeks),
        "period_basis": "dates_inclusive" if date_weeks is not None else "provided_work_weeks",
    }


def _tax(raw: dict[str, Any], gross: Decimal, state: str, mode: str, path: str) -> dict[str, Any]:
    allowed = {
        "federal_income_tax_percent", "state_income_tax_percent",
        "known_federal_income_tax_withheld_usd", "known_state_income_tax_withheld_usd",
        "known_other_payroll_withheld_usd",
    }
    _exact_keys(raw, allowed, set(), path)
    if mode == "manual_rates":
        required = ("federal_income_tax_percent", "state_income_tax_percent")
        if any(key not in raw for key in required):
            return {
                "status": "needs_rates",
                "total_usd": None,
                "message": "简易估算模式需要用户明确提供联邦税率和州所得税率；不会默认 10%。",
            }
        federal_rate = _number(raw["federal_income_tax_percent"], f"{path}.federal_income_tax_percent")
        state_rate = _number(raw["state_income_tax_percent"], f"{path}.state_income_tax_percent")
        if federal_rate > 100 or state_rate > 100:
            raise ValueError(f"{path}: tax percentages cannot exceed 100")
        other = _optional_number(raw, "known_other_payroll_withheld_usd", path) or ZERO
        federal = gross * federal_rate / Decimal("100")
        state_tax = gross * state_rate / Decimal("100")
        total = federal + state_tax + other
        return {
            "status": "manual_rate_estimate",
            "federal_income_tax_usd": _money(federal),
            "state_income_tax_usd": _money(state_tax),
            "other_known_payroll_withheld_usd": _money(other),
            "total_usd": _money(total),
            "message": "这是用户设定的估算税率，不代表最终实际税额、工资单扣缴或退税。",
        }

    federal = _optional_number(raw, "known_federal_income_tax_withheld_usd", path)
    state_tax = _optional_number(raw, "known_state_income_tax_withheld_usd", path)
    other = _optional_number(raw, "known_other_payroll_withheld_usd", path) or ZERO
    bases: list[str] = []
    if federal is not None:
        bases.append("联邦金额来自用户提供的工资单／雇主扣缴信息，不等于最终联邦税负。")
    if state_tax is not None:
        bases.append("州金额来自用户提供的工资单／雇主扣缴信息，不等于最终州税负。")
    elif state in ASSISTED_ZERO_STATE_INCOME_TAX:
        state_tax = ZERO
        bases.append(f"{ASSISTED_ZERO_STATE_INCOME_TAX[state]['state']} 的工资州个人所得税按本地已核验来源暂估为 0。")

    missing: list[str] = []
    if federal is None:
        missing.append("联邦所得税")
    if state_tax is None:
        missing.append("州所得税")
    if missing:
        return {
            "status": "needs_verification",
            "federal_income_tax_usd": _money(federal),
            "state_income_tax_usd": _money(state_tax),
            "other_known_payroll_withheld_usd": _money(other),
            "total_usd": None,
            "pending_components": missing,
            "message": "数据辅助模式不会根据时薪自行猜测税率；请提供工资单扣缴、适用税率或当前官方核验结果。",
            "basis": bases,
        }

    total = federal + state_tax + other
    return {
        "status": "known_withholding",
        "federal_income_tax_usd": _money(federal),
        "state_income_tax_usd": _money(state_tax),
        "other_known_payroll_withheld_usd": _money(other),
        "total_usd": _money(total),
        "message": "这是已知／辅助的工资单扣缴估算，不等于最终税负或退税。",
        "basis": bases,
    }


def _offer(raw: dict[str, Any], tax_mode: str, fx: Decimal | None, path: str) -> dict[str, Any]:
    allowed = {
        "id", "label", "state", "wage_usd_per_hour", "hours_per_week", "rent_usd_per_week",
        "start_date", "end_date", "work_weeks", "overtime_hours_per_week",
        "overtime_wage_usd_per_hour", "transport_usd_per_week", "food_usd_per_week",
        "other_weekly_usd", "other_fixed_usd", "tax",
    }
    required = {"id", "label", "state", "wage_usd_per_hour", "hours_per_week", "rent_usd_per_week", "tax"}
    _exact_keys(raw, allowed, required, path)
    if not isinstance(raw["id"], str) or not raw["id"].strip() or not isinstance(raw["label"], str) or not raw["label"].strip():
        raise ValueError(f"{path}: id and label require nonempty strings")
    if not isinstance(raw["tax"], dict):
        raise ValueError(f"{path}.tax: requires an object")

    period = _period(raw, path)
    state = _state_code(raw["state"], f"{path}.state")
    output: dict[str, Any] = {"id": raw["id"], "label": raw["label"], "state": state, "period": period}
    if period["status"] != "ready":
        output["calculation_status"] = "needs_confirmation"
        return output

    weeks = Decimal(period["work_weeks"])
    wage = _number(raw["wage_usd_per_hour"], f"{path}.wage_usd_per_hour", positive=True)
    hours = _number(raw["hours_per_week"], f"{path}.hours_per_week", positive=True)
    rent = _number(raw["rent_usd_per_week"], f"{path}.rent_usd_per_week")
    overtime_hours = _optional_number(raw, "overtime_hours_per_week", path) or ZERO
    overtime_wage = _optional_number(raw, "overtime_wage_usd_per_hour", path) or ZERO
    if overtime_hours and not overtime_wage:
        raise ValueError(f"{path}: overtime needs an explicit hourly rate; the calculator never assumes 1.5x")
    if hours + overtime_hours > Decimal("168"):
        raise ValueError(f"{path}: weekly hours cannot exceed 168")
    transport = _optional_number(raw, "transport_usd_per_week", path) or ZERO
    food = _optional_number(raw, "food_usd_per_week", path) or ZERO
    other_weekly = _optional_number(raw, "other_weekly_usd", path) or ZERO
    other_fixed = _optional_number(raw, "other_fixed_usd", path) or ZERO

    gross = weeks * (wage * hours + overtime_wage * overtime_hours)
    housing = weeks * rent
    other = weeks * (transport + food + other_weekly) + other_fixed
    tax = _tax(raw["tax"], gross, state, tax_mode, f"{path}.tax")
    total_tax = Decimal(tax["total_usd"]) if tax["total_usd"] is not None else None
    net_before_tax = gross - housing - other
    net = net_before_tax - total_tax if total_tax is not None else None
    output.update({
        "calculation_status": "complete" if net is not None else "tax_pending",
        "inputs": {
            "wage_usd_per_hour": _money(wage), "hours_per_week": str(hours),
            "rent_usd_per_week": _money(rent), "overtime_hours_per_week": str(overtime_hours),
        },
        "gross_income_usd": _money(gross),
        "estimated_taxes": tax,
        "housing_cost_usd": _money(housing),
        "other_known_costs_usd": _money(other),
        "net_before_unverified_income_taxes_usd": _money(net_before_tax),
        "estimated_net_income_usd": _money(net),
        "estimated_net_income_cny": _money(net * fx) if net is not None and fx is not None else None,
        "fx_cny_per_usd": _money(fx),
    })
    if fx is None:
        output["fx_status"] = "needs_current_or_user_provided_rate"
    return output


def calculate_net_income(data: dict[str, Any]) -> dict[str, Any]:
    """Calculate net-income estimates. Raises ValueError for malformed input."""
    _exact_keys(data, {"tax_mode", "fx_cny_per_usd", "offers"}, {"tax_mode", "offers"}, "input")
    if data["tax_mode"] not in {"manual_rates", "data_assisted"}:
        raise ValueError("input.tax_mode: use manual_rates or data_assisted")
    if not isinstance(data["offers"], list) or not data["offers"]:
        raise ValueError("input.offers: requires at least one offer")
    fx = _optional_number(data, "fx_cny_per_usd", "input")
    if fx == ZERO:
        raise ValueError("input.fx_cny_per_usd: requires a positive number")

    ids: set[str] = set()
    offers = []
    for index, offer in enumerate(data["offers"]):
        if not isinstance(offer, dict):
            raise ValueError(f"input.offers[{index}]: requires an object")
        result = _offer(offer, data["tax_mode"], fx, f"input.offers[{index}]")
        if result["id"] in ids:
            raise ValueError("input.offers: duplicate id")
        ids.add(result["id"])
        offers.append(result)

    comparable = [item for item in offers if item.get("estimated_net_income_usd") is not None]
    comparison: dict[str, Any] = {"status": "not_requested" if len(offers) == 1 else "partial"}
    if len(offers) > 1:
        comparison["offers_with_net_estimate"] = [item["id"] for item in sorted(
            comparable, key=lambda item: Decimal(item["estimated_net_income_usd"]), reverse=True
        )]
        comparison["offers_pending_tax_or_period_confirmation"] = [
            item["id"] for item in offers if item not in comparable
        ]
        if len(comparable) == len(offers):
            comparison["status"] = "complete"
            comparison["message"] = "排序仅比较本次输入下的预计净结余，不代表岗位整体更适合。"
        else:
            comparison["message"] = "部分 Offer 的税或工作期未确认；暂不能做完整净结余排序。"

    return {
        "scope": "SWT 一工预计净收入；不含二工、未来退税、奖励或未明确成本。",
        "tax_mode": data["tax_mode"],
        "offers": offers,
        "comparison": comparison,
    }


def format_calculation(result: dict[str, Any]) -> str:
    """Render the compact user-facing Chinese format requested by this feature."""
    lines: list[str] = []
    for item in result["offers"]:
        if lines:
            lines.append("")
        lines.append(f"{item['label']}（{item['state']}）")
        period = item["period"]
        if period["status"] != "ready":
            lines.extend([
                "工作期：数据冲突，暂不计算", 
                f"日期换算：{period['date_calculated_weeks']} 周；直接输入：{period['provided_work_weeks']} 周",
                "请确认以日期还是直接输入周数为准。",
            ])
            continue
        days = f"（{period['calendar_days']} 天）" if period["calendar_days"] is not None else ""
        fields = item["inputs"]
        lines.extend([
            f"预计工作期：{item['period']['work_weeks']} 周{days}",
            f"时薪：${fields['wage_usd_per_hour']}；每周工时：{fields['hours_per_week']} h",
            f"税前收入：${item['gross_income_usd']}",
        ])
        tax = item["estimated_taxes"]
        if tax["total_usd"] is None:
            lines.append("预计税费：待核验（不会按固定比例猜测）")
        else:
            lines.append(f"预计税费：-${tax['total_usd']}")
        lines.extend([
            f"住宿：-${item['housing_cost_usd']}",
            f"其他已知成本：-${item['other_known_costs_usd']}",
        ])
        if item["estimated_net_income_usd"] is None:
            lines.append(f"税前待核验净结余：${item['net_before_unverified_income_taxes_usd']}")
        else:
            lines.append(f"预计美元净结余：${item['estimated_net_income_usd']}")
            if item["estimated_net_income_cny"] is not None:
                lines.append(f"按 ¥{item['fx_cny_per_usd']} / $：≈ ¥{item['estimated_net_income_cny']}")
            else:
                lines.append("人民币折算：待提供或核验当前汇率")
        lines.append(f"税务说明：{tax['message']}")
    if result["comparison"]["status"] != "not_requested":
        lines.extend(["", f"Offer 比较：{result['comparison']['message']}"])
        if result["comparison"].get("offers_with_net_estimate"):
            lines.append("按本次预计净结余：" + " > ".join(result["comparison"]["offers_with_net_estimate"]))
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    if len(argv) not in {2, 3} or (len(argv) == 3 and argv[1] != "--json"):
        print("Usage: python3 scripts/budget.py [--json] INPUT.json", file=sys.stderr)
        return 2
    json_output = argv[1] == "--json"
    input_path = argv[2] if json_output else argv[1]
    try:
        data = json.loads(Path(input_path).read_text(encoding="utf-8"), parse_float=Decimal)
        result = calculate_net_income(data)
        if json_output:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(format_calculation(result))
        return 0
    except (ValueError, TypeError, OSError, KeyError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
