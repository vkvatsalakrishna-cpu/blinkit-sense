#!/usr/bin/env python3
"""Run all 12 SCENARIO_PRESETS through the full suggestion pipeline."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import date
from pathlib import Path

from engine import apply_household_filter, resolve_needs
from llm import plan_needs, read_situation
from phases.phase_2_data.loader import (
    address_to_catalog_location,
    all_tiles,
    catalog_by_id,
    is_location_unfamiliar,
    load_households,
    load_scenarios,
)

LOCATION = "Sarjapur, Bangalore"
TODAY = date.today().isoformat()
SLEEP_SEC = 30
RESULTS_PATH = Path("data/cache/scenario_preset_runs.json")

SCENARIO_PRESETS = [
    {"id": "scenario_1", "householdId": "h1", "skuIds": ["sku_3308", "sku_4878", "sku_22717", "sku_24301"]},
    {"id": "scenario_2", "householdId": "h2", "skuIds": ["sku_7488", "sku_15192", "sku_17135", "sku_11541"]},
    {"id": "scenario_3", "householdId": "h3", "skuIds": ["sku_21297", "sku_22341", "sku_10380", "sku_3708"]},
    {"id": "scenario_4", "householdId": "h4", "skuIds": ["sku_13951", "sku_13980", "sku_14202", "sku_18548"]},
    {"id": "scenario_5", "householdId": "h1", "skuIds": ["sku_2826", "sku_1876", "sku_12243"]},
    {"id": "scenario_6", "householdId": "h2", "skuIds": ["sku_20901", "sku_9712", "sku_20910", "sku_3889", "sku_4719"]},
    {"id": "scenario_7", "householdId": "h3", "skuIds": ["sku_253", "sku_263", "sku_1062", "sku_2210"]},
    {"id": "scenario_8", "householdId": "h4", "skuIds": ["sku_18488", "sku_10572", "sku_4682"]},
    {"id": "scenario_9", "householdId": "h1", "skuIds": ["sku_22656", "sku_12245", "sku_25638", "sku_24707"]},
    {"id": "scenario_10", "householdId": "h2", "skuIds": ["sku_11702", "sku_12100", "sku_2087", "sku_28965"]},
    {"id": "scenario_11", "householdId": "h3", "skuIds": ["sku_24002", "sku_17330", "sku_1324", "sku_22546"]},
    {"id": "scenario_12", "householdId": "h4", "skuIds": ["sku_19781", "sku_3308", "sku_19236", "sku_23564"]},
]


def household_by_id(household_id: str) -> dict:
    for household in load_households():
        if household["id"] == household_id:
            return household
    raise ValueError(f"Unknown household: {household_id}")


def scenario_by_id(situation_id: str) -> dict:
    for scenario in load_scenarios():
        if scenario["id"] == situation_id:
            return scenario
    raise ValueError(f"Unknown situation: {situation_id}")


def cart_items(sku_ids: list[str]) -> tuple[list[dict], list[str]]:
    by_id = catalog_by_id()
    items = []
    for sku in sku_ids:
        product = by_id[sku]
        items.append({"name": product["name"], "category": product["category"]})
    return items, sorted(sku_ids)


def run_preset(preset: dict) -> dict:
    household = {
        **household_by_id(preset["householdId"]),
        "current_cart": preset["skuIds"],
        "current_address": LOCATION,
    }
    cart_payload, cart_skus = cart_items(preset["skuIds"])
    catalog_location = address_to_catalog_location(LOCATION)

    situations = read_situation(
        cart_items=cart_payload,
        delivery_location=LOCATION,
        location_unfamiliar=is_location_unfamiliar(household),
        today=TODAY,
        household_id=household["id"],
        cart_skus=cart_skus,
    )
    if situations is None:
        return {"preset": preset["id"], "error": "read_situation failed"}

    top = situations["candidates"][0]
    scenario = scenario_by_id(top["id"])

    needs_result = plan_needs(
        situation_id=scenario["id"],
        situation_label=scenario["chip_label"],
        prompt_context=scenario["prompt_context"],
        tile_categories=all_tiles(),
        household_id=household["id"],
        cart_items=cart_payload,
        cart_skus=cart_skus,
    )
    if needs_result is None:
        return {
            "preset": preset["id"],
            "error": "plan_needs failed",
            "situation": top["label"],
            "situation_id": top["id"],
        }

    resolved = resolve_needs(
        needs_result["needs"],
        catalog_location,
        situation_id=scenario["id"],
    )
    filtered = apply_household_filter(resolved, household)

    suggestions = [
        {
            "name": item["resolved_name"],
            "category": item["category"],
            "sku": item["resolved_sku"],
            "need": item.get("need", ""),
        }
        for item in filtered["items"][:4]
    ]

    return {
        "preset": preset["id"],
        "household_id": household["id"],
        "confidence": situations["confidence"],
        "situation": top["label"],
        "situation_id": top["id"],
        "situation_reasoning": top.get("reasoning", ""),
        "planner_label": needs_result.get("situation_label", scenario["chip_label"]),
        "suggestions": suggestions,
        "gaps": len(filtered.get("gaps", [])),
    }


def print_result(out: dict) -> None:
    if out.get("error"):
        print(f"  ERROR: {out['error']}", flush=True)
        if out.get("situation"):
            print(f"  Situation (partial): {out['situation']}", flush=True)
        return
    print(f"  Situation: {out['situation']} ({out['situation_id']})", flush=True)
    print(f"  Confidence: {out['confidence']:.2f}", flush=True)
    if out.get("situation_reasoning"):
        print(f"  Reasoning: {out['situation_reasoning'][:120]}", flush=True)
    print(f"  Suggestions ({len(out['suggestions'])}):", flush=True)
    for i, s in enumerate(out["suggestions"], 1):
        print(f"    {i}. [{s['category']}] {s['name'][:55]}", flush=True)
    if out.get("gaps"):
        print(f"  ({out['gaps']} unresolved needs)", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, default=0, help="Preset index to start from")
    args = parser.parse_args()

    existing: list[dict] = []
    if RESULTS_PATH.exists() and args.start > 0:
        existing = json.loads(RESULTS_PATH.read_text())

    results = existing[: args.start] if existing else []
    for index in range(args.start, len(SCENARIO_PRESETS)):
        preset = SCENARIO_PRESETS[index]
        if index > args.start:
            time.sleep(SLEEP_SEC)
        print(f"\n{'=' * 72}", flush=True)
        print(f"{preset['id']} ({preset['householdId']})", flush=True)
        try:
            out = run_preset(preset)
        except Exception as exc:  # noqa: BLE001
            out = {"preset": preset["id"], "error": str(exc)}
        if len(results) > index:
            results[index] = out
        else:
            results.append(out)
        print_result(out)

        RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        RESULTS_PATH.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n")

    print(f"\nWrote {RESULTS_PATH}", flush=True)


if __name__ == "__main__":
    main()
