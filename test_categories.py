#!/usr/bin/env python3
"""Phase 2 gate test — household tiles, thresholds, demo SKU flags."""

from __future__ import annotations

from phases.phase_2_data.loader import (
    address_to_catalog_location,
    confidence_threshold,
    is_location_unfamiliar,
    load_catalog,
    load_households,
    resolve_demo_skus,
    tiles_with_history,
    tiles_without_history,
)

DEMO_FLOWS = [
    {
        "name": "1. Ambiguous cart — Festival gifting (h1)",
        "household_id": "h1",
        "scenario": "festival_gifting",
        "skus": ["sku_027", "sku_028", "sku_029", "sku_030"],
    },
    {
        "name": "2. New delivery location — Moving in (h2)",
        "household_id": "h2",
        "scenario": "moving_in",
        "skus": ["sku_031", "sku_032", "sku_033", "sku_034", "sku_035", "sku_036", "sku_037"],
    },
    {
        "name": "3. No history — New cat (h3)",
        "household_id": "h3",
        "scenario": "new_pet",
        "skus": ["sku_012", "sku_014", "sku_015", "sku_038"],
    },
    {
        "name": "4. Incoherent cart — Cooking project (h1)",
        "household_id": "h1",
        "scenario": "cooking_project",
        "skus": ["sku_041", "sku_042"],
    },
    {
        "name": "5. Honest gap — Moving in partial (h2)",
        "household_id": "h2",
        "scenario": "moving_in",
        "skus": ["sku_031", "sku_036"],
        "note": "vacuum cleaner not in catalogue; mop resolves, vacuum is gap",
    },
    {
        "name": "6. Low signal — Staples only (h4)",
        "household_id": "h4",
        "scenario": "stocking",
        "skus": [],
        "note": "confidence below threshold; no strip",
    },
]


def print_household_summary(household: dict) -> None:
    location = address_to_catalog_location(household["current_address"])
    unfamiliar = is_location_unfamiliar(household)
    threshold = confidence_threshold(household["orders_per_month"])
    with_hist = tiles_with_history(household)
    without_hist = tiles_without_history(household)

    print(f"\n{'=' * 72}")
    print(f"Household: {household['name']} ({household['id']})")
    print(f"  Current location: {household['current_address']} -> {location}")
    print(f"  Unfamiliar address: {unfamiliar}")
    print(f"  Orders/month: {household['orders_per_month']}")
    print(f"  Confidence threshold: {threshold:.2f}")
    print(f"  Tiles WITH purchase history ({len(with_hist)}): {', '.join(with_hist)}")
    print(f"  Tiles WITHOUT history ({len(without_hist)}): {', '.join(without_hist)}")


def print_demo_flow(flow: dict, households_by_id: dict[str, dict]) -> None:
    household = households_by_id[flow["household_id"]]
    print(f"\n--- {flow['name']} ---")
    if flow.get("note"):
        print(f"  Note: {flow['note']}")
    if not flow["skus"]:
        print("  (no suggested SKUs — system stays silent)")
        return
    results = resolve_demo_skus(household, flow["skus"])
    new_count = sum(1 for r in results if r.get("flag") == "new_category")
    deep_count = sum(1 for r in results if r.get("flag") == "deepening")
    for r in results:
        if r["status"] == "resolved":
            print(
                f"  {r['sku']}  {r['flag']:14}  "
                f"[{r['category']}]  {r['name'][:48]}  ₹{r['price']}"
            )
        elif r["status"] == "gap":
            print(f"  {r['sku']}  GAP             not available in current location")
        else:
            print(f"  {r['sku']}  MISSING         not in catalogue")
    print(f"  Summary: {new_count} new_category, {deep_count} deepening")
    if flow["household_id"] in ("h1", "h2", "h3") and new_count == 0 and deep_count > 0:
        print("  WARNING: demo should lead with new_category items")


def main() -> None:
    households = load_households()
    households_by_id = {h["id"]: h for h in households}
    catalog = load_catalog()

    print("Blinkit Sense — Phase 2: test_categories")
    print(f"Catalog: {len(catalog)} products loaded")

    for household in households:
        print_household_summary(household)

    print(f"\n{'=' * 72}")
    print("DEMO FLOWS — resolvable SKUs with new_category / deepening flags")
    for flow in DEMO_FLOWS:
        print_demo_flow(flow, households_by_id)


if __name__ == "__main__":
    main()
