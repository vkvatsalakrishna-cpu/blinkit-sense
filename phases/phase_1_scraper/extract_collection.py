"""Extract category, subcategory, products, and inventory from Blinkit /dc/ URLs.

Blinkit blocks plain HTTP clients (Cloudflare). This script uses Playwright with a
real browser session and follows the listing_widgets pagination API.

Usage:
    python -m phases.phase_1_scraper.extract_collection URL -o data/extracted.json
    python -m phases.phase_1_scraper.extract_collection --batch
    python -m phases.phase_1_scraper.extract_collection --dump-raw URL

Requires: playwright (pip install playwright && playwright install chromium)
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[2]
SAMPLE_PRODUCT_PATH = ROOT / "data" / "raw" / "sample_product.json"
CATEGORY_URLS_PATH = ROOT / "data" / "category_urls.json"
RAW_DIR = ROOT / "data" / "raw"

DEFAULT_LAT = 12.912118
DEFAULT_LON = 77.644554
MAX_PRODUCTS_PER_SUBCATEGORY = 500
BATCH_DELAY_MIN_S = 1.0
BATCH_DELAY_MAX_S = 2.0

LISTING_API = "/v1/layout/listing_widgets"
FETCH_HEADERS = (
    "app_client",
    "app_version",
    "auth_key",
    "device_id",
    "lat",
    "lon",
    "session_uuid",
    "content-type",
)


def load_category_urls(path: Path = CATEGORY_URLS_PATH) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"{path} must contain a JSON array")
    entries: list[dict[str, Any]] = []
    for row in data:
        if not isinstance(row, dict):
            continue
        category = row.get("category")
        subcategory = row.get("subcategory")
        url = row.get("url")
        if not all(isinstance(value, str) and value.strip() for value in (category, subcategory, url)):
            raise ValueError(f"Invalid category_urls row: {row!r}")
        entries.append(
            {
                "category": category.strip(),
                "subcategory": subcategory.strip(),
                "url": url.strip(),
            }
        )
    return entries


def lookup_category_meta(url: str, entries: list[dict[str, Any]] | None = None) -> dict[str, str]:
    entries = entries if entries is not None else load_category_urls()
    normalized = url.split("?", 1)[0].rstrip("/")
    for row in entries:
        if row["url"].split("?", 1)[0].rstrip("/") == normalized:
            return {"category": row["category"], "subcategory": row["subcategory"]}
    parsed = urlparse(url)
    parts = [part for part in parsed.path.strip("/").split("/") if part]
    category_slug = parts[1] if len(parts) > 1 else "unknown"
    subcategory_slug = parts[2] if len(parts) > 2 else "all"
    return {
        "category": category_slug.replace("-", " ").title(),
        "subcategory": subcategory_slug.replace("-", " ").title(),
    }


def parse_dc_url(url: str) -> dict[str, Any]:
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    labels = lookup_category_meta(url)
    return {
        "url": url,
        "category": labels["category"],
        "subcategory": labels["subcategory"],
        "collection_uuid": (query.get("collection_uuid") or [None])[0],
        "collection_group_id": (query.get("collection_group_id") or [None])[0],
    }


def _walk(obj: Any):
    if isinstance(obj, dict):
        yield obj
        for value in obj.values():
            yield from _walk(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from _walk(item)


def _cart_item(data: dict[str, Any]) -> dict[str, Any] | None:
    atc = data.get("atc_action")
    if not isinstance(atc, dict):
        return None
    add = atc.get("add_to_cart")
    if not isinstance(add, dict):
        return None
    item = add.get("cart_item")
    return item if isinstance(item, dict) else None


def _image_url(data: dict[str, Any], cart_item: dict[str, Any]) -> str | None:
    image_url = cart_item.get("image_url")
    if isinstance(image_url, str) and image_url.strip():
        return image_url.strip()
    media = data.get("media_container")
    if isinstance(media, dict):
        items = media.get("items")
        if isinstance(items, list) and items:
            first = items[0]
            if isinstance(first, dict):
                image = first.get("image")
                if isinstance(image, dict):
                    url = image.get("url")
                    if isinstance(url, str) and url.strip():
                        return url.strip()
    image = data.get("image")
    if isinstance(image, dict):
        url = image.get("url")
        if isinstance(url, str) and url.strip():
            return url.strip()
    return None


def _tracking_click_map(snippet: dict[str, Any]) -> dict[str, Any]:
    tracking = snippet.get("tracking")
    if not isinstance(tracking, dict):
        return {}
    click_map = tracking.get("click_map")
    return click_map if isinstance(click_map, dict) else {}


def _normalize_snippet(snippet: dict[str, Any], meta: dict[str, Any]) -> dict[str, Any] | None:
    data = snippet.get("data")
    if not isinstance(data, dict):
        return None
    cart_item = _cart_item(data)
    if cart_item is None:
        return None

    product_id = cart_item.get("product_id")
    name = cart_item.get("product_name")
    if product_id is None or not isinstance(name, str) or not name.strip():
        return None

    click_map = _tracking_click_map(snippet)
    is_sold_out = data.get("is_sold_out")

    return {
        "product_id": str(product_id),
        "name": name.strip(),
        "brand": cart_item.get("brand") or None,
        "unit": cart_item.get("unit") or None,
        "price": cart_item.get("price"),
        "mrp": cart_item.get("mrp"),
        "inventory": cart_item.get("inventory"),
        "image_url": _image_url(data, cart_item),
        "in_stock": False if is_sold_out is True else True,
        "blinkit_l0": click_map.get("l0_category"),
        "blinkit_l1": click_map.get("l1_category"),
        "blinkit_l2": click_map.get("l2_category"),
        "category": meta["category"],
        "subcategory": meta["subcategory"],
        "collection_uuid": meta.get("collection_uuid"),
        "collection_group_id": meta.get("collection_group_id"),
    }


def _extract_products_from_listing_payload(
    payload: Any,
    meta: dict[str, Any],
) -> list[dict[str, Any]]:
    snippets = payload.get("response", {}).get("snippets", [])
    if not isinstance(snippets, list):
        return []
    products: list[dict[str, Any]] = []
    for snippet in snippets:
        if not isinstance(snippet, dict):
            continue
        product = _normalize_snippet(snippet, meta)
        if product is not None:
            products.append(product)
    return products


def _pagination_next_url(payload: Any) -> str | None:
    pagination = payload.get("response", {}).get("pagination")
    if not isinstance(pagination, dict):
        return None
    next_url = pagination.get("next_url")
    if isinstance(next_url, str) and next_url.strip():
        return next_url.strip()
    return None


def _body_from_next_url(next_url: str) -> dict[str, str]:
    query = parse_qs(urlparse(f"https://blinkit.com{next_url}").query)
    body: dict[str, str] = {}
    for key, values in query.items():
        if not values:
            continue
        value = values[0]
        if key == "total_pagination_items" and "?" in value:
            value = value.split("?", 1)[0]
        body[key] = value
    return body


def _merge_post_body(template: dict[str, str], next_url: str) -> dict[str, str]:
    body = dict(template)
    body.update(_body_from_next_url(next_url))
    return body


class _ListingCapture:
    payloads: list[Any]
    paginated_post_template: dict[str, str] | None
    paginated_headers: dict[str, str]

    def __init__(self) -> None:
        self.payloads = []
        self.paginated_post_template = None
        self.paginated_headers = {}

    def on_response(self, response: Any) -> None:
        if response.status != 200:
            return
        if LISTING_API not in response.url:
            return
        content_type = response.headers.get("content-type", "")
        if "json" not in content_type:
            return
        try:
            self.payloads.append(response.json())
        except Exception:
            return

    def on_request(self, request: Any) -> None:
        if LISTING_API not in request.url or "offset=" not in request.url:
            return
        if request.post_data:
            try:
                parsed = json.loads(request.post_data)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, dict):
                self.paginated_post_template = {
                    str(key): str(value) for key, value in parsed.items()
                }
        for key, value in request.headers.items():
            lower = key.lower()
            if lower in FETCH_HEADERS and key not in self.paginated_headers:
                self.paginated_headers[key] = value


def _fetch_listing_page(page: Any, next_url: str, body: dict[str, str], headers: dict[str, str]) -> dict[str, Any]:
    result = page.evaluate(
        """async ({ path, body, headers }) => {
            const response = await fetch(path, {
                method: "POST",
                credentials: "include",
                headers,
                body: JSON.stringify(body),
            });
            const text = await response.text();
            let data = null;
            try { data = JSON.parse(text); } catch (err) { data = { parse_error: String(err), raw: text }; }
            return { status: response.status, data };
        }""",
        {"path": next_url, "body": body, "headers": headers},
    )
    if result["status"] != 200:
        raise RuntimeError(f"listing_widgets page failed with HTTP {result['status']}")
    return result["data"]


def _paginate_collection(
    page: Any,
    capture: _ListingCapture,
    meta: dict[str, Any],
    *,
    max_products: int = MAX_PRODUCTS_PER_SUBCATEGORY,
) -> tuple[list[dict[str, Any]], int]:
    by_id: dict[str, dict[str, Any]] = {}
    pages_fetched = 0

    def merge(products: list[dict[str, Any]]) -> int:
        added = 0
        for product in products:
            key = product["product_id"]
            if key in by_id:
                continue
            by_id[key] = product
            added += 1
        return added

    for payload in capture.payloads:
        pages_fetched += 1
        merge(_extract_products_from_listing_payload(payload, meta))
        if len(by_id) >= max_products:
            return list(by_id.values()), pages_fetched

    post_template = capture.paginated_post_template
    if post_template is None:
        return list(by_id.values()), pages_fetched

    headers = dict(capture.paginated_headers)
    if "content-type" not in {key.lower() for key in headers}:
        headers["content-type"] = "application/json"

    next_url = None
    for payload in reversed(capture.payloads):
        next_url = _pagination_next_url(payload)
        if next_url:
            break

    while next_url and len(by_id) < max_products:
        body = _merge_post_body(post_template, next_url)
        payload = _fetch_listing_page(page, next_url, body, headers)
        pages_fetched += 1
        added = merge(_extract_products_from_listing_payload(payload, meta))
        if added == 0:
            break
        next_url = _pagination_next_url(payload)

    return list(by_id.values()), pages_fetched


def _first_raw_product_snippet(payloads: list[Any]) -> dict[str, Any]:
    for payload in payloads:
        snippets = payload.get("response", {}).get("snippets", [])
        if not isinstance(snippets, list):
            continue
        for snippet in snippets:
            if not isinstance(snippet, dict):
                continue
            data = snippet.get("data")
            if isinstance(data, dict) and _cart_item(data) is not None:
                return snippet
    raise RuntimeError("No raw product object found in captured API responses")


def _field_paths(value: Any, prefix: str = "") -> list[str]:
    paths: list[str] = []
    if isinstance(value, dict):
        if prefix:
            paths.append(f"{prefix} (object, {len(value)} keys)")
        else:
            paths.append(f"(root object, {len(value)} keys)")
        for key in sorted(value):
            child_prefix = f"{prefix}.{key}" if prefix else str(key)
            paths.extend(_field_paths(value[key], child_prefix))
    elif isinstance(value, list):
        paths.append(f"{prefix} (array, {len(value)} items)")
        if value:
            paths.extend(_field_paths(value[0], f"{prefix}[0]"))
    else:
        type_name = type(value).__name__
        paths.append(f"{prefix} ({type_name})")
    return paths


def _capture_listing_payloads(
    url: str,
    *,
    lat: float = DEFAULT_LAT,
    lon: float = DEFAULT_LON,
    wait_ms: int = 8000,
) -> tuple[Any, Any, Any, _ListingCapture]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "Playwright is required. Run: pip install playwright && playwright install chromium"
        ) from exc

    capture = _ListingCapture()

    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context(
        geolocation={"latitude": lat, "longitude": lon},
        permissions=["geolocation"],
        locale="en-IN",
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    )
    page = context.new_page()

    page.on("response", capture.on_response)
    page.on("request", capture.on_request)
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(wait_ms)
    page.mouse.wheel(0, 4500)
    page.wait_for_timeout(1500)
    page.remove_listener("request", capture.on_request)

    return playwright, browser, page, capture


def _close_browser(playwright: Any, browser: Any) -> None:
    browser.close()
    playwright.stop()


def dump_raw_product(
    url: str,
    output_path: Path = SAMPLE_PRODUCT_PATH,
    *,
    lat: float = DEFAULT_LAT,
    lon: float = DEFAULT_LON,
    wait_ms: int = 8000,
) -> dict[str, Any]:
    playwright, browser, page, capture = _capture_listing_payloads(
        url, lat=lat, lon=lon, wait_ms=wait_ms
    )
    try:
        product = _first_raw_product_snippet(capture.payloads)
    finally:
        _close_browser(playwright, browser)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(product, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return product


def fetch_collection(
    url: str,
    *,
    lat: float = DEFAULT_LAT,
    lon: float = DEFAULT_LON,
    wait_ms: int = 8000,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    collection_meta = dict(meta or parse_dc_url(url))
    playwright, browser, page, capture = _capture_listing_payloads(
        url, lat=lat, lon=lon, wait_ms=wait_ms
    )
    try:
        products, pages_fetched = _paginate_collection(page, capture, collection_meta)
    finally:
        _close_browser(playwright, browser)

    collection_meta["product_count"] = len(products)
    collection_meta["scraped_at"] = datetime.now(timezone.utc).isoformat()
    collection_meta["location"] = {"lat": lat, "lon": lon}
    return {
        **collection_meta,
        "products": products,
        "pages_fetched": pages_fetched,
    }


def run_batch(
    *,
    lat: float = DEFAULT_LAT,
    lon: float = DEFAULT_LON,
    wait_ms: int = 8000,
    category_urls_path: Path = CATEGORY_URLS_PATH,
    output_root: Path = RAW_DIR,
    skip_categories: list[str] | None = None,
) -> Path:
    entries = load_category_urls(category_urls_path)
    skip = set(skip_categories or [])
    if skip:
        entries = [entry for entry in entries if entry["category"] not in skip]

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    run_dir = output_root / stamp
    run_dir.mkdir(parents=True, exist_ok=True)

    manifest: dict[str, Any] = {
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "location": {"lat": lat, "lon": lon},
        "source": str(category_urls_path),
        "skipped_categories": sorted(skip),
        "collections": [],
    }

    for index, entry in enumerate(entries):
        url = entry["url"]
        slug = entry["subcategory"].lower().replace(" & ", "-").replace(" ", "-")
        outfile = run_dir / f"{index:02d}_{slug}.json"
        print(f"[{index + 1}/{len(entries)}] {entry['category']} / {entry['subcategory']}", file=sys.stderr)
        try:
            result = fetch_collection(
                url,
                lat=lat,
                lon=lon,
                wait_ms=wait_ms,
                meta={
                    **parse_dc_url(url),
                    "category": entry["category"],
                    "subcategory": entry["subcategory"],
                },
            )
            outfile.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            manifest["collections"].append(
                {
                    "category": entry["category"],
                    "subcategory": entry["subcategory"],
                    "url": url,
                    "product_count": result["product_count"],
                    "pages_fetched": result["pages_fetched"],
                    "file": outfile.name,
                    "status": "ok",
                }
            )
            print(f"  → {result['product_count']} products ({result['pages_fetched']} pages)", file=sys.stderr)
        except Exception as exc:
            manifest["collections"].append(
                {
                    "category": entry["category"],
                    "subcategory": entry["subcategory"],
                    "url": url,
                    "status": "error",
                    "error": str(exc),
                }
            )
            print(f"  → failed: {exc}", file=sys.stderr)

        if index + 1 < len(entries):
            time.sleep(random.uniform(BATCH_DELAY_MIN_S, BATCH_DELAY_MAX_S))

    manifest_path = run_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote batch output to {run_dir}", file=sys.stderr)
    return run_dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extract Blinkit /dc/ collection data")
    parser.add_argument("urls", nargs="*", help="Blinkit collection URLs")
    parser.add_argument("-o", "--output", type=Path, help="Write JSON output to this file")
    parser.add_argument("--lat", type=float, default=DEFAULT_LAT)
    parser.add_argument("--lon", type=float, default=DEFAULT_LON)
    parser.add_argument("--wait-ms", type=int, default=8000)
    parser.add_argument(
        "--dump-raw",
        action="store_true",
        help="Write the first unmodified product snippet to data/raw/sample_product.json",
    )
    parser.add_argument(
        "--batch",
        action="store_true",
        help="Read data/category_urls.json and scrape every URL into data/raw/<timestamp>/",
    )
    parser.add_argument(
        "--skip-category",
        action="append",
        default=[],
        metavar="CATEGORY",
        help="Skip URLs for this category during --batch (repeatable)",
    )
    args = parser.parse_args(argv)

    if args.batch:
        run_batch(lat=args.lat, lon=args.lon, wait_ms=args.wait_ms, skip_categories=args.skip_category)
        return 0

    if not args.urls:
        parser.error("Provide at least one URL, or use --batch")

    if args.dump_raw:
        url = args.urls[0]
        print(f"Dumping raw product from {url} ...", file=sys.stderr)
        product = dump_raw_product(url, lat=args.lat, lon=args.lon, wait_ms=args.wait_ms)
        print(f"Wrote {SAMPLE_PRODUCT_PATH}", file=sys.stderr)
        for path in _field_paths(product):
            print(path)
        if len(args.urls) == 1 and not args.output:
            return 0

    results = []
    for url in args.urls:
        print(f"Fetching {url} ...", file=sys.stderr)
        try:
            results.append(fetch_collection(url, lat=args.lat, lon=args.lon, wait_ms=args.wait_ms))
            print(
                f"  → {results[-1]['category']} / {results[-1]['subcategory']}: "
                f"{results[-1]['product_count']} products ({results[-1]['pages_fetched']} pages)",
                file=sys.stderr,
            )
        except Exception as exc:
            print(f"  → failed: {exc}", file=sys.stderr)
            results.append({"url": url, "error": str(exc)})

    payload = results[0] if len(results) == 1 else {"collections": results}
    text = json.dumps(payload, indent=2, ensure_ascii=False)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
        print(f"Wrote {args.output}", file=sys.stderr)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
