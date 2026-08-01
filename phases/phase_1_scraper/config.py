"""Catalogue build constants for Phase 1."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
APIFY_CSV = DATA_DIR / "blinkit_products.csv"
CATEGORIES_JSON = DATA_DIR / "categories.json"
CATALOG_JSON = DATA_DIR / "catalog.json"
RAW_DIR = DATA_DIR / "raw"

TARGET_CATALOG_SIZE = 250
USER_AGENT = "BlinkitSenseCatalogueBot/1.0"

# search_keyword -> tile (Apify rows have no category column)
APIFY_KEYWORD_TO_TILE = {
    "cat food": "Pet Store",
    "cat litter": "Pet Store",
    "litter tray": "Pet Store",
    "pet bowl": "Pet Store",
}

# Map CSV location short name -> catalog available_in name
LOCATION_NAMES = ["Sarjapur", "Whitefield", "Delhi NCR"]
ALL_LOCATIONS = LOCATION_NAMES
DELHI_HEAVY = ["Sarjapur", "Whitefield", "Delhi NCR"]
WHITEfield_AND_DELHI = ["Whitefield", "Delhi NCR"]
SARJAPUR_ONLY = ["Sarjapur"]

SCRAPE_BLOCKED = {
    "status": "blocked",
    "reason": "Storefront behind Cloudflare; search endpoint returns HTTP 403 without browser session",
    "investigated_endpoints": [
        "blinkit.com/v6/search/deeplink",
        "blinkit.com/v1/layout/search",
    ],
}
