"""Merge raw scrape runs into data/catalog.json, preserving existing SKUs."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

from phases.phase_1_scraper.config import CATALOG_JSON, CATEGORIES_JSON, RAW_DIR

MIN_CATALOG_SIZE = 100
SKU_RE = re.compile(r"^sku_(\d+)$")


def load_tiles() -> set[str]:
    data = json.loads(CATEGORIES_JSON.read_text(encoding="utf-8"))
    tiles = {t for g in data["groups"] for t in g["tiles"]}
    tiles.update(data["stores"])
    return tiles


def max_sku_index(catalog: list[dict]) -> int:
    highest = 0
    for item in catalog:
        match = SKU_RE.match(item.get("id", ""))
        if match:
            highest = max(highest, int(match.group(1)))
    return highest


def load_raw_files(run_dir: Path) -> list[tuple[Path, dict]]:
    files: list[tuple[Path, dict]] = []
    for path in sorted(run_dir.glob("*.json")):
        if path.name == "manifest.json":
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        files.append((path, payload))
    files.sort(key=lambda pair: (pair[1].get("subcategory") == "All", pair[0].name))
    return files


def raw_product_to_catalog(
    product: dict,
    *,
    category: str,
    subcategory: str,
    fetched_at: str,
    sku_id: str,
) -> dict:
    brand = product.get("brand")
    if not isinstance(brand, str) or not brand.strip():
        brand = "Unknown"

    return {
        "id": sku_id,
        "name": product["name"],
        "brand": brand.strip(),
        "category": category,
        "subcategory": subcategory,
        "price": int(product["price"]),
        "mrp": int(product["mrp"]),
        "unit": product["unit"],
        "image_url": product.get("image_url"),
        "in_stock": bool(product.get("in_stock", True)),
        "inventory": product.get("inventory"),
        "available_in": ["Sarjapur"],
        "blinkit_product_id": str(product["product_id"]),
        "source": "blinkit_api",
        "fetched_at": fetched_at,
    }


def merge_raw_runs(
    run_dirs: list[Path],
    *,
    catalog_path: Path = CATALOG_JSON,
    min_size: int = MIN_CATALOG_SIZE,
) -> list[dict]:
    tiles = load_tiles()
    existing = json.loads(catalog_path.read_text(encoding="utf-8"))
    seen_blinkit_ids = {
        str(item["blinkit_product_id"])
        for item in existing
        if item.get("blinkit_product_id") is not None
    }

    next_idx = max_sku_index(existing) + 1
    appended: list[dict] = []

    for run_dir in run_dirs:
        if not run_dir.is_dir():
            raise FileNotFoundError(f"Raw run directory not found: {run_dir}")

        for path, payload in load_raw_files(run_dir):
            category = payload["category"]
            subcategory = payload["subcategory"]
            if category not in tiles:
                raise ValueError(f"Unknown category {category!r} in {path}")

            fetched_at = payload.get("scraped_at") or payload.get("fetched_at")
            if not fetched_at:
                raise ValueError(f"Missing scraped_at in {path}")

            for product in payload.get("products", []):
                blinkit_id = str(product["product_id"])
                if blinkit_id in seen_blinkit_ids:
                    continue
                seen_blinkit_ids.add(blinkit_id)

                sku_id = f"sku_{next_idx:03d}"
                next_idx += 1
                appended.append(
                    raw_product_to_catalog(
                        product,
                        category=category,
                        subcategory=subcategory,
                        fetched_at=fetched_at,
                        sku_id=sku_id,
                    )
                )

    merged = existing + appended
    if len(merged) < min_size:
        raise ValueError(
            f"Refusing to write catalog with {len(merged)} products (< {min_size})"
        )

    for item in merged:
        if item["category"] not in tiles:
            raise ValueError(f"Invalid category in merged catalog: {item['category']}")

    catalog_path.write_text(
        json.dumps(merged, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return merged


def print_summary(catalog: list[dict]) -> None:
    counts = Counter(item["category"] for item in catalog)
    print(f"Total SKUs: {len(catalog)}")
    print("Per category:")
    for category, count in sorted(counts.items()):
        print(f"  {category}: {count}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Merge raw scrape runs into catalog.json")
    parser.add_argument(
        "run_dirs",
        nargs="+",
        type=Path,
        help="Raw run directories under data/raw/ (e.g. 20260801T094548)",
    )
    parser.add_argument(
        "--catalog",
        type=Path,
        default=CATALOG_JSON,
        help="Path to catalog.json (default: data/catalog.json)",
    )
    args = parser.parse_args(argv)

    run_dirs = [(RAW_DIR / path.name if not path.is_absolute() else path) for path in args.run_dirs]
    try:
        catalog = merge_raw_runs(run_dirs, catalog_path=args.catalog)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1

    print_summary(catalog)
    print(f"Wrote {args.catalog}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
