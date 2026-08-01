"""Phase 2 — data layer loader and helpers."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"

BASE_CONFIDENCE_THRESHOLD = 0.4
MIN_CONFIDENCE_THRESHOLD = 0.25
THRESHOLD_REFERENCE_ORDERS = 12


def load_json(name: str) -> dict | list:
    return json.loads((DATA_DIR / name).read_text())


def load_categories() -> dict:
    return load_json("categories.json")


def load_locations() -> dict:
    return load_json("locations.json")


def load_households() -> list[dict]:
    data = load_json("households.json")
    return data["households"] if isinstance(data, dict) else data


def load_scenarios() -> list[dict]:
    data = load_json("scenarios.json")
    return data["scenarios"] if isinstance(data, dict) else data


def load_catalog() -> list[dict]:
    return load_json("catalog.json")


def all_tiles(categories: dict | None = None) -> list[str]:
    categories = categories or load_categories()
    tiles = [t for g in categories["groups"] for t in g["tiles"]]
    tiles.extend(categories["stores"])
    return tiles


def catalog_by_id(catalog: list[dict] | None = None) -> dict[str, dict]:
    catalog = catalog or load_catalog()
    return {item["id"]: item for item in catalog}


def address_to_catalog_location(address: str, locations: dict | None = None) -> str:
    locations = locations or load_locations()
    for loc in locations["locations"]:
        if loc["display_address"] == address:
            return loc["name"]
    return address.split(",")[0].strip()


def is_location_unfamiliar(household: dict) -> bool:
    return household["current_address"] not in household["known_addresses"]


def confidence_threshold(orders_per_month: int) -> float:
    adjusted = BASE_CONFIDENCE_THRESHOLD - max(
        0, (THRESHOLD_REFERENCE_ORDERS - orders_per_month)
    ) * 0.02
    return max(MIN_CONFIDENCE_THRESHOLD, adjusted)


def purchased_tiles(household: dict, catalog: list[dict] | None = None) -> set[str]:
    by_id = catalog_by_id(catalog)
    return {
        by_id[entry["sku"]]["category"]
        for entry in household["order_history"]
        if entry["sku"] in by_id
    }


def tiles_with_history(household: dict, catalog: list[dict] | None = None) -> list[str]:
    return sorted(purchased_tiles(household, catalog))


def tiles_without_history(
    household: dict, categories: dict | None = None, catalog: list[dict] | None = None
) -> list[str]:
    bought = purchased_tiles(household, catalog)
    return sorted(t for t in all_tiles(categories) if t not in bought)


def flag_sku(
    sku_id: str, household: dict, catalog: list[dict] | None = None
) -> str:
    by_id = catalog_by_id(catalog)
    item = by_id[sku_id]
    tile = item["category"]
    if tile in purchased_tiles(household, catalog):
        return "deepening"
    return "new_category"


def is_available_at_location(item: dict, location_name: str) -> bool:
    return location_name in item.get("available_in", [])


def resolve_demo_skus(
    household: dict,
    sku_ids: list[str],
    catalog: list[dict] | None = None,
) -> list[dict]:
    """Return resolvable SKUs at the household's current location with flags."""
    catalog = catalog or load_catalog()
    by_id = catalog_by_id(catalog)
    location = address_to_catalog_location(household["current_address"])
    results = []
    for sku_id in sku_ids:
        item = by_id.get(sku_id)
        if item is None:
            results.append({"sku": sku_id, "status": "missing_from_catalog"})
            continue
        if not is_available_at_location(item, location):
            results.append(
                {
                    "sku": sku_id,
                    "name": item["name"],
                    "status": "gap",
                    "reason": f"not available in {location}",
                }
            )
            continue
        results.append(
            {
                "sku": sku_id,
                "name": item["name"],
                "category": item["category"],
                "price": item["price"],
                "flag": flag_sku(sku_id, household, catalog),
                "status": "resolved",
            }
        )
    return results
