#!/usr/bin/env python3
"""Phase 3 gate test — situation reader across all five households."""

from __future__ import annotations

from datetime import date

from llm import is_unambiguous, read_situation
from phases.phase_2_data.loader import (
    catalog_by_id,
    confidence_threshold,
    is_location_unfamiliar,
    load_households,
)


def cart_items_for_household(household: dict) -> list[dict]:
    by_id = catalog_by_id()
    items = []
    for sku in household["current_cart"]:
        product = by_id.get(sku)
        if product is None:
            raise ValueError(f"Unknown cart SKU {sku} for {household['id']}")
        items.append({"name": product["name"], "category": product["category"]})
    return items


def print_candidates(result: dict) -> None:
    for i, cand in enumerate(result["candidates"], start=1):
        print(
            f"    {i}. [{cand['score']:.2f}] {cand['label']} ({cand['id']}) — {cand['reasoning']}"
        )


def main() -> None:
    today = date.today().isoformat()
    households = load_households()

    print("Blinkit Sense — Phase 3: test_situation")
    print(f"Date: {today}\n")

    for household in households:
        threshold = confidence_threshold(household["orders_per_month"])
        unfamiliar = is_location_unfamiliar(household)
        cart = cart_items_for_household(household)

        print("=" * 72)
        print(f"{household['name']} ({household['id']})")
        print(f"  Location: {household['current_address']}  unfamiliar={unfamiliar}")
        print(f"  Cart ({len(cart)} items):")
        for item in cart:
            print(f"    - {item['name'][:55]}  [{item['category']}]")

        result = read_situation(
            cart_items=cart,
            delivery_location=household["current_address"],
            location_unfamiliar=unfamiliar,
            today=today,
        )

        if result is None:
            print(f"  confidence: —")
            print(f"  threshold:  {threshold:.2f}")
            print(f"  fires:      NO (parse/API failure)")
            print(f"  unambiguous: —")
            print("  candidates: —")
            continue

        conf = result["confidence"]
        fires = conf >= threshold
        unamb = is_unambiguous(result) if fires else False

        print(f"  confidence: {conf:.2f}")
        print(f"  threshold:  {threshold:.2f}")
        print(f"  fires:      {'YES' if fires else 'NO'}")
        print(f"  unambiguous: {'YES' if unamb else 'NO'}")
        print("  candidates:")
        print_candidates(result)
        print()


if __name__ == "__main__":
    main()
