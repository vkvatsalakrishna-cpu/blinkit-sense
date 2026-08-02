#!/usr/bin/env python3
"""Phase 5 gate test — need planner for Moving in and Gifting."""

from __future__ import annotations

from llm import plan_needs
from phases.phase_2_data.loader import all_tiles, load_scenarios


def scenario_by_label(label: str) -> dict:
    for scenario in load_scenarios():
        if scenario["chip_label"] == label:
            return scenario
    raise ValueError(f"Scenario not found: {label}")


def print_needs(result: dict) -> None:
    by_role: dict[str, list[dict]] = {}
    for need in result["needs"]:
        by_role.setdefault(need["role"], []).append(need)

    for role, needs in by_role.items():
        print(f"  [{role}]")
        for need in needs:
            print(f"    • {need['need']}")
            print(f"      qty: {need['quantity_reasoning']}")

    if result.get("unavailable"):
        print("  unavailable:")
        for item in result["unavailable"]:
            print(f"    - {item}")


def run_scenario(label: str, tiles: list[str]) -> None:
    scenario = scenario_by_label(label)
    print("=" * 72)
    print(f"Scenario: {label} ({scenario['id']})")
    print(f"  Context: {scenario['prompt_context']}")

    result = plan_needs(
        situation_id=scenario["id"],
        situation_label=scenario["chip_label"],
        prompt_context=scenario["prompt_context"],
        tile_categories=tiles,
    )

    if result is None:
        print("  RESULT: parse/API failure (None)")
        print()
        return

    print(f"  Situation label: {result['situation_label']}")
    print(f"  Needs ({len(result['needs'])}):")
    print_needs(result)
    print()


def main() -> None:
    tiles = all_tiles()
    print("Blinkit Sense — Phase 5: test_needs")
    print(f"Tile categories passed to planner: {len(tiles)}\n")

    run_scenario("Moving in", tiles)
    run_scenario("Gifting", tiles)


if __name__ == "__main__":
    main()
