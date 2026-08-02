"""Build data/catalog.json from Apify CSV + generated products."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from phases.phase_1_scraper.config import (
    APIFY_CSV,
    APIFY_KEYWORD_TO_TILE,
    CATALOG_JSON,
    CATEGORIES_JSON,
    DATA_DIR,
    RAW_DIR,
    SCRAPE_BLOCKED,
    TARGET_CATALOG_SIZE,
    USER_AGENT,
)
from phases.phase_1_scraper.generated_products import GENERATED_PRODUCTS

ALL_LOCATIONS = ["Sarjapur", "Whitefield", "Delhi NCR"]


def load_tiles() -> set[str]:
    data = json.loads(CATEGORIES_JSON.read_text())
    tiles = {t for g in data["groups"] for t in g["tiles"]}
    tiles.update(data["stores"])
    return tiles


def parse_int(value: str | None) -> int:
    if value is None or value == "":
        return 0
    return int(float(value))


def load_apify_rows() -> list[dict]:
    rows: list[dict] = []
    with APIFY_CSV.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    rows.sort(key=lambda r: int(r["product_id"]))
    return rows


def apify_to_catalog(rows: list[dict], fetched_at: str, tiles: set[str]) -> list[dict]:
    catalog: list[dict] = []
    for idx, row in enumerate(rows, start=1):
        keyword = (row.get("search_keyword") or "").strip().lower()
        category = APIFY_KEYWORD_TO_TILE.get(keyword, "Pet Store")
        if category not in tiles:
            raise ValueError(f"Unknown tile for Apify row: {category}")

        location = (row.get("location") or "Sarjapur").strip()
        if location not in ALL_LOCATIONS:
            location = "Sarjapur"

        catalog.append(
            {
                "id": f"sku_{idx:03d}",
                "name": row["name"].strip(),
                "brand": (row.get("brand") or "").strip() or "Unknown",
                "category": category,
                "price": parse_int(row.get("price")),
                "mrp": parse_int(row.get("mrp")),
                "unit": (row.get("variant") or "1 pc").strip(),
                "available_in": [location],
                "fetched_at": fetched_at,
                "source": "apify",
                "blinkit_product_id": row["product_id"],
                "popularity_rank": None,
            }
        )
    return catalog


def generated_to_catalog(start_idx: int, fetched_at: str, tiles: set[str]) -> list[dict]:
    catalog: list[dict] = []
    for offset, item in enumerate(GENERATED_PRODUCTS):
        name, brand, category, price, mrp, unit, locations = item
        if category not in tiles:
            raise ValueError(f"Unknown tile in generated product: {category} ({name})")
        available = locations if locations is not None else ALL_LOCATIONS
        catalog.append(
            {
                "id": f"sku_{start_idx + offset:03d}",
                "name": name,
                "brand": brand,
                "category": category,
                "price": price,
                "mrp": mrp,
                "unit": unit,
                "available_in": available,
                "fetched_at": fetched_at,
                "source": "generated",
                "popularity_rank": None,
            }
        )
    return catalog


def trim_to_target(catalog: list[dict], target: int) -> list[dict]:
    if len(catalog) <= target:
        return catalog
    # Keep all Apify rows; trim generated from the end
    apify = [p for p in catalog if p["source"] == "apify"]
    generated = [p for p in catalog if p["source"] == "generated"]
    keep_generated = max(0, target - len(apify))
    return apify + generated[:keep_generated]


def build_manifest(
    run_id: str,
    started_at: str,
    completed_at: str,
    apify_count: int,
    generated_count: int,
    total: int,
    tiles_covered: list[str],
) -> dict:
    return {
        "run_id": run_id,
        "started_at": started_at,
        "completed_at": completed_at,
        "direct_scrape": SCRAPE_BLOCKED,
        "sources": {
            "apify": {
                "file": "data/blinkit_products.csv",
                "count": apify_count,
            },
            "generated": {
                "module": "phases/phase_1_scraper/generated_products.py",
                "count": generated_count,
            },
        },
        "total_products": total,
        "target_size": TARGET_CATALOG_SIZE,
        "tiles_covered": tiles_covered,
        "user_agent": USER_AGENT,
    }


def main() -> None:
    started = datetime.now(timezone.utc)
    fetched_at = started.strftime("%Y-%m-%dT%H:%M:%SZ")
    run_id = started.strftime("%Y%m%dT%H%M%S")

    tiles = load_tiles()
    apify_rows = load_apify_rows()
    apify_catalog = apify_to_catalog(apify_rows, fetched_at, tiles)
    generated_catalog = generated_to_catalog(
        start_idx=len(apify_catalog) + 1,
        fetched_at=fetched_at,
        tiles=tiles,
    )
    catalog = trim_to_target(apify_catalog + generated_catalog, TARGET_CATALOG_SIZE)

    # Validate
    for product in catalog:
        if product["category"] not in tiles:
            raise ValueError(f"Invalid category: {product['category']}")
        if not product["available_in"]:
            raise ValueError(f"Empty available_in for {product['id']}")

    tiles_covered = sorted({p["category"] for p in catalog})
    missing_tiles = tiles - set(tiles_covered)

    CATALOG_JSON.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + "\n")

    run_dir = RAW_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    completed = datetime.now(timezone.utc)
    manifest = build_manifest(
        run_id=run_id,
        started_at=fetched_at,
        completed_at=completed.strftime("%Y-%m-%dT%H:%M:%SZ"),
        apify_count=len([p for p in catalog if p["source"] == "apify"]),
        generated_count=len([p for p in catalog if p["source"] == "generated"]),
        total=len(catalog),
        tiles_covered=tiles_covered,
    )
    if missing_tiles:
        manifest["missing_tiles"] = sorted(missing_tiles)
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")

    print(f"Wrote {len(catalog)} products -> {CATALOG_JSON}")
    print(f"  apify: {manifest['sources']['apify']['count']}")
    print(f"  generated: {manifest['sources']['generated']['count']}")
    print(f"  tiles covered: {len(tiles_covered)} / {len(tiles)}")
    if missing_tiles:
        print(f"  missing tiles: {sorted(missing_tiles)}")


if __name__ == "__main__":
    main()
