#!/usr/bin/env python3
"""Phase 6+7 gate test — full chain across demo households and situations."""

from __future__ import annotations

import io
import json
import time
from contextlib import redirect_stdout

from engine import (
    _match_key,
    _matched_words,
    _tokenize_need,
    apply_household_filter,
    resolve_needs,
)
from llm import NEED_PLANNER_SYSTEM, _chat, _extract_json, _parse_needs_response
from phases.phase_2_data.loader import (
    address_to_catalog_location,
    all_tiles,
    load_catalog,
    load_households,
    load_scenarios,
)

RUNS = [
    ("h1", "Festival gifting"),
    ("h1", "Eating better"),
    ("h1", "Just stocking up"),
    ("h1", "Cooking something"),
    ("h2", "Moving in"),
    ("h3", "New Pet"),
]


def household_by_id(household_id: str) -> dict:
    for household in load_households():
        if household["id"] == household_id:
            return household
    raise ValueError(f"Household not found: {household_id}")


def scenario_by_label(label: str) -> dict:
    normalized = label.strip().lower()
    for scenario in load_scenarios():
        chip = scenario["chip_label"].lower()
        scenario_id = scenario["id"].lower()
        if (
            chip == normalized
            or scenario_id == normalized.replace(" ", "_")
            or normalized in chip
            or normalized.replace(" ", "") in chip.replace(" ", "")
        ):
            return scenario
    raise ValueError(f"Scenario not found: {label}")


def invalid_expected_tiles(raw: str | None, valid_tiles: set[str]) -> list[str]:
    if not raw:
        return []
    extracted = _extract_json(raw)
    if not extracted:
        return []
    try:
        data = json.loads(extracted)
    except json.JSONDecodeError:
        return []
    invalid: list[str] = []
    for need in data.get("needs", []) or []:
        if not isinstance(need, dict):
            continue
        tiles = need.get("expected_tiles", [])
        if not isinstance(tiles, list):
            continue
        for tile in tiles:
            if not isinstance(tile, str):
                continue
            name = tile.strip()
            if name and name not in valid_tiles:
                invalid.append(name)
    return invalid


def plan_needs_with_validation(
    scenario: dict,
    tile_categories: list[str],
    valid_tiles: set[str],
) -> tuple[dict | None, list[str]]:
    payload = {
        "situation_id": scenario["id"],
        "situation_label": scenario["chip_label"],
        "prompt_context": scenario["prompt_context"],
        "tile_categories": tile_categories,
    }
    raw = _chat(NEED_PLANNER_SYSTEM, payload)
    invalid = invalid_expected_tiles(raw, valid_tiles)
    parsed = _parse_needs_response(raw) if raw else None
    return parsed, invalid


def top_rejected_candidates(
    need: dict,
    location: str,
    catalog: list[dict],
) -> list[dict]:
    available = [
        item for item in catalog if location in item.get("available_in", [])
    ]
    content_words = _tokenize_need(need.get("need", ""))

    scored: list[tuple[tuple, dict]] = []
    for item in available:
        matched = _matched_words(content_words, item["name"])
        if not matched:
            continue
        key = _match_key(content_words, matched, item["name"], item["price"])
        scored.append((key, item))

    scored.sort(key=lambda row: row[0], reverse=True)
    return [item for _, item in scored[:3]]


def _format_tiles(tiles: list[str]) -> str:
    return ", ".join(tiles) if tiles else "(none)"


def print_need_diagnostics(
    needs_result: dict,
    resolved: list[dict],
    location: str,
    catalog: list[dict],
) -> None:
    resolved_by_need = {entry["need"]: entry for entry in resolved}

    print(f"  Needs from planner ({len(needs_result['needs'])}):")
    for need in needs_result["needs"]:
        need_text = need["need"]
        expected = need.get("expected_tiles", [])
        entry = resolved_by_need.get(need_text)

        if entry and entry.get("status") == "matched":
            print(f"    MATCH  need={need_text!r}")
            print(f"           expected_tiles: {_format_tiles(expected)}")
            print(
                f"           sku={entry['resolved_sku']}  "
                f"category={entry['category']!r}"
            )
            continue

        print(f"    GAP    need={need_text!r}")
        print(f"           expected_tiles: {_format_tiles(expected)}")
        rejected = top_rejected_candidates(need, location, catalog)
        if rejected:
            categories = [item["category"] for item in rejected]
            print(f"           top rejected categories: {', '.join(categories)}")
        else:
            print("           top rejected categories: (none with word overlap)")


def print_result(
    household: dict,
    scenario: dict,
    needs_result: dict,
    resolved: list[dict],
    filtered: dict,
    location: str,
    catalog: list[dict],
) -> None:
    print(f"  Location: {household['current_address']} -> {location}")
    print(f"  Situation: {scenario['chip_label']} ({scenario['id']})")
    print(f"  Cart subtotal: ₹{filtered['cart_subtotal']}")
    print(f"  Suggested add-on: ₹{filtered['suggested_total']}")
    fee = filtered["fee"]
    print(
        f"  Fees: delivery ₹{fee['delivery']} + handling ₹{fee['handling']}"
        + (f" + small-cart ₹{fee['small_cart']}" if fee["small_cart"] else "")
        + f" = ₹{fee['total_fees']}"
    )
    if fee["gap_to_threshold"]:
        print(f"  Gap to ₹99 threshold: ₹{fee['gap_to_threshold']}")

    print_need_diagnostics(needs_result, resolved, location, catalog)

    print(f"  Composed items after filter ({len(filtered['items'])}):")
    for item in filtered["items"]:
        expected = item.get("expected_tiles", [])
        print(
            f"    {item['resolved_sku']}  {item['flag']:14}  "
            f"[{item['category']}]  {item['resolved_name'][:40]}  ₹{item['price']}"
        )
        print(
            f"      need={item['need']!r}  expected_tiles={_format_tiles(expected)}"
        )

    if filtered["sensitive_guidance"]:
        print("  Sensitive-category guidance:")
        for line in filtered["sensitive_guidance"]:
            print(f"    - {line}")


def run_chain(
    household_id: str,
    scenario_label: str,
    tiles: list[str],
    valid_tiles: set[str],
    catalog: list[dict],
) -> tuple[list[str], str]:
    household = household_by_id(household_id)
    scenario = scenario_by_label(scenario_label)
    location = address_to_catalog_location(household["current_address"])

    lines: list[str] = []
    lines.append("=" * 72)
    lines.append(f"{household['name']} ({household_id}) — {scenario_label}")

    needs_result, invalid = plan_needs_with_validation(scenario, tiles, valid_tiles)
    if needs_result is None:
        lines.append("  RESULT: plan_needs failed (None)")
        lines.append("")
        return invalid, "\n".join(lines)

    resolved = resolve_needs(
        needs_result["needs"], location, situation_id=scenario["id"]
    )
    filtered = apply_household_filter(resolved, household)

    buf = io.StringIO()
    with redirect_stdout(buf):
        print_result(
            household, scenario, needs_result, resolved, filtered, location, catalog
        )
    lines.append(buf.getvalue().rstrip())
    lines.append("")
    return invalid, "\n".join(lines)


def main() -> None:
    tiles = all_tiles()
    valid_tiles = set(tiles)
    catalog = load_catalog()

    print("Blinkit Sense — Phase 6+7: test_engine")
    print(f"Valid tiles in categories.json: {len(tiles)}")
    print()

    all_invalid: set[str] = set()
    scenario_blocks: list[str] = []
    for index, (household_id, scenario_label) in enumerate(RUNS):
        if index > 0:
            time.sleep(30)
        invalid, block = run_chain(
            household_id, scenario_label, tiles, valid_tiles, catalog
        )
        all_invalid.update(invalid)
        scenario_blocks.append(block)

    print("=" * 72)
    print("expected_tiles validation (LLM values vs categories.json)")
    if all_invalid:
        for name in sorted(all_invalid):
            print(f"  INVALID: {name!r} — not in categories.json")
    else:
        print("  All expected_tiles values matched categories.json")
    print()

    for block in scenario_blocks:
        print(block)


if __name__ == "__main__":
    main()
