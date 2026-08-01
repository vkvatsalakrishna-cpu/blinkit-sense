"""Extract category, subcategory, products, and inventory from Blinkit collection URLs.

Supports /dc/...?collection_uuid=... URLs and /cn/.../cid/... category URLs.
Blinkit blocks plain HTTP clients (Cloudflare). This script uses Playwright with a
real browser session and follows the listing_widgets pagination API.

Usage:
    python -m phases.phase_1_scraper.extract_collection URL -o data/extracted.json
    python -m phases.phase_1_scraper.extract_collection --batch
    python -m phases.phase_1_scraper.extract_collection --resolve-group-ids

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
from urllib.parse import parse_qs, unquote, urlparse

ROOT = Path(__file__).resolve().parents[2]
SAMPLE_PRODUCT_PATH = ROOT / "data" / "raw" / "sample_product.json"
CATEGORY_URLS_PATH = ROOT / "data" / "category_urls.json"
RAW_DIR = ROOT / "data" / "raw"

DEFAULT_LAT = 12.912118
DEFAULT_LON = 77.644554
# Sarjapur dark-store service area (lat/lon above). Catalog rows tag this as "Sarjapur".
DEFAULT_PINCODE = "560102"
DEFAULT_LOCATION_NAME = "Sarjapur"
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


def parse_cn_url(url: str) -> dict[str, Any]:
    parsed = urlparse(url)
    parts = [part for part in parsed.path.strip("/").split("/") if part]
    labels = lookup_category_meta(url)
    meta: dict[str, Any] = {
        "url": url,
        "category": labels["category"],
        "subcategory": labels["subcategory"],
        "collection_uuid": None,
        "collection_group_id": None,
    }
    if "cid" in parts:
        cid_index = parts.index("cid")
        if cid_index + 2 < len(parts):
            meta["cn_cid_l0"] = parts[cid_index + 1]
            meta["cn_cid_l1"] = parts[cid_index + 2]
        if cid_index >= 2 and parts[0] == "cn":
            slug = parts[1]
            if slug not in {"cid", "null"} and slug:
                meta["cn_slug"] = slug
    return meta


def parse_collection_url(url: str) -> dict[str, Any]:
    path = urlparse(url).path
    if "/cn/" in path:
        return parse_cn_url(url)
    return parse_dc_url(url)


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


def _subcategory_slug(url: str) -> str | None:
    parts = [part for part in urlparse(url).path.strip("/").split("/") if part]
    if len(parts) >= 3 and parts[0] == "dc":
        return parts[2]
    return None


def _tile_slug(url: str) -> str | None:
    parts = [part for part in urlparse(url).path.strip("/").split("/") if part]
    if len(parts) >= 2 and parts[0] == "dc":
        return parts[1]
    return None


def _collection_uuid_from_url(url: str) -> str | None:
    query = parse_qs(urlparse(url).query)
    values = query.get("collection_uuid") or []
    return values[0] if values else None


def _url_tab_key(url: str) -> str | None:
    slug = _subcategory_slug(url)
    if slug:
        return slug
    parts = [part for part in urlparse(url).path.strip("/").split("/") if part]
    if parts == ["dc"]:
        return "all"
    return None


def _normalize_uuid(uuid: str) -> str:
    return unquote(uuid)


# Parent tile pages used to discover subcategory tab links (slug -> href with group id).
TILE_SEED_URLS: dict[tuple[str, str], str] = {
    (
        "kitchenware-appliances",
        _normalize_uuid("OTg3NjU0MzIxMjM0NTI5ODI%3D"),
    ): (
        "https://blinkit.com/dc/kitchenware-appliances/cookware-sets/"
        "?collection_uuid=OTg3NjU0MzIxMjM0NTI5ODI%3D&collection_group_id=620091"
    ),
    (
        "stationery-games",
        _normalize_uuid("OTg3NjU0MzIxMjM0NTMzMjU%3D"),
    ): "https://blinkit.com/dc/?collection_uuid=OTg3NjU0MzIxMjM0NTMzMjU%3D",
}


def _seed_url_for_tile(tile_key: str, uuid: str) -> str | None:
    normalized = _normalize_uuid(uuid)
    return TILE_SEED_URLS.get((tile_key, normalized))


_COLLECT_TABS_JS = """({ tileSlug, uuid }) => {
    const out = {};
    const encoded = encodeURIComponent(decodeURIComponent(uuid));
    for (const link of document.querySelectorAll('a[href]')) {
        const href = link.href;
        if (!href.includes('collection_group_id=')) continue;
        if (!href.includes(uuid) && !href.includes(encoded)) continue;
        const parts = new URL(href).pathname.split('/').filter(Boolean);
        if (parts[0] !== 'dc') continue;
        let slug;
        if (parts.length >= 3) {
            if (tileSlug && parts[1] !== tileSlug) continue;
            slug = parts[2];
        } else if (parts.length === 1) {
            slug = 'all';
        } else {
            continue;
        }
        const label = (link.textContent || '').trim().replace(/\\s+/g, ' ');
        out[slug] = { href, label };
    }
    return out;
}"""


_SCROLL_TAB_CONTAINERS_JS = """(delta) => {
    for (const el of document.querySelectorAll('*')) {
        if (el.scrollWidth > el.clientWidth + 8) {
            el.scrollLeft += delta;
        }
    }
}"""


def _scroll_tab_bar(page: Any, *, delta: int = 320) -> None:
    page.evaluate(_SCROLL_TAB_CONTAINERS_JS, delta)
    page.mouse.wheel(delta, 0)
    page.wait_for_timeout(200)


def _reset_tab_bar_scroll(page: Any) -> None:
    page.evaluate(
        """() => {
            for (const el of document.querySelectorAll('*')) {
                if (el.scrollWidth > el.clientWidth + 8) {
                    el.scrollLeft = 0;
                }
            }
        }"""
    )
    page.wait_for_timeout(200)


def _dismiss_overlays(page: Any) -> None:
    try:
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)
    except Exception:
        return


def _ensure_delivery_location(page: Any, pincode: str = DEFAULT_PINCODE) -> None:
    """Set delivery location via browser geolocation, falling back to pincode if needed."""
    try:
        detect = page.locator('button:has-text("Detect my location")').first
        if detect.count() and detect.is_visible(timeout=2000):
            detect.click(timeout=5000)
            page.wait_for_timeout(2500)
    except Exception:
        pass

    try:
        input_box = page.locator('input[type="text"]').first
        if input_box.count() and input_box.is_visible(timeout=1500):
            input_box.fill(pincode)
            page.keyboard.press("Enter")
            page.wait_for_timeout(2000)
    except Exception:
        pass

    page.evaluate(
        """() => {
            for (const el of document.querySelectorAll('[class*="LocationOverlay"]')) {
                el.remove();
            }
        }"""
    )
    page.wait_for_timeout(300)


def _click_subcategory_tab(page: Any, label: str) -> bool:
    try:
        tab = page.locator('div[data-pf="reset"].tw-text-100', has_text=label).first
        if tab.count() == 0:
            tab = page.get_by_text(label, exact=True).first
        tab.click(timeout=5000)
        page.wait_for_timeout(1800)
        return True
    except Exception:
        return False


def _resolve_entry_group_id(
    page: Any,
    *,
    seed_url: str,
    subcategory_label: str,
    original_url: str,
) -> str | None:
    page.goto(seed_url, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(1500)
    _ensure_delivery_location(page)
    if _url_tab_key(original_url) == "all":
        page.wait_for_timeout(2000)
        group_id = page.evaluate(
            """() => {
                const meta = window.grofers?.PRELOADED_STATE?.ui?.plp?.pageMeta?.custom_data;
                return meta?.collection_group_id || meta?.subcategory_id || null;
            }"""
        )
        if group_id:
            resolved = f"{original_url.split('?', 1)[0]}?collection_uuid={_collection_uuid_from_url(original_url)}&collection_group_id={group_id}"
            return _normalize_resolved_url(original_url, resolved)
        if not _click_subcategory_tab(page, subcategory_label):
            _click_subcategory_tab(page, "Stationery & Games")
    elif not _click_subcategory_tab(page, subcategory_label):
        return None
    resolved = page.url
    if not _group_id_from_url(resolved):
        return None
    return _normalize_resolved_url(original_url, resolved)


def _clean_dc_url(url: str) -> str:
    if "/dc" not in url:
        return url
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    group_id = (query.get("collection_group_id") or [""])[0]
    if not group_id:
        return url
    uuid_token = parsed.query.split("collection_uuid=", 1)[-1].split("&", 1)[0] if "collection_uuid=" in parsed.query else (query.get("collection_uuid") or [""])[0]
    if uuid_token.endswith("=") and "%3D" not in uuid_token:
        uuid_token = uuid_token[:-1] + "%3D"
    if not uuid_token:
        return url
    return parsed._replace(query=f"collection_uuid={uuid_token}&collection_group_id={group_id}").geturl()


def _slug_from_resolved_url(url: str, *, tile_slug: str | None) -> str | None:
    parts = [part for part in urlparse(url).path.strip("/").split("/") if part]
    if len(parts) >= 3 and parts[0] == "dc":
        return parts[2]
    if parts == ["dc"]:
        return "all"
    return None


def _collect_tab_labels(page: Any) -> list[str]:
    """Scroll the tab bar and return visible subcategory labels without navigating away."""
    _reset_tab_bar_scroll(page)
    labels: list[str] = []
    seen: set[str] = set()
    stagnant = 0
    for _ in range(35):
        tab_locator = page.locator('div[data-pf="reset"].tw-text-100')
        found = 0
        for index in range(tab_locator.count()):
            element = tab_locator.nth(index)
            try:
                box = element.bounding_box()
                if not box or box["y"] < 140 or box["y"] > 240 or box["height"] < 18 or box["height"] > 50:
                    continue
                label = element.inner_text(timeout=1000).strip()
                if not label or label in seen:
                    continue
                seen.add(label)
                labels.append(label)
                found += 1
            except Exception:
                continue
        if found == 0:
            stagnant += 1
        else:
            stagnant = 0
        if stagnant >= 6:
            break
        _scroll_tab_bar(page)
    return labels


def _collect_subcategory_tabs(
    page: Any,
    *,
    seed_url: str,
    tile_slug: str | None,
    collection_uuid: str,
) -> dict[str, dict[str, str]]:
    """Click each subcategory tab on the parent tile page; return slug -> {href, label}."""
    _dismiss_overlays(page)
    _ensure_delivery_location(page)
    labels = _collect_tab_labels(page)
    tabs: dict[str, dict[str, str]] = {}

    for label in labels:
        page.goto(seed_url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(1500)
        _ensure_delivery_location(page)
        try:
            tab = page.locator('div[data-pf="reset"].tw-text-100', has_text=label).first
            tab.click(timeout=5000)
            page.wait_for_timeout(1800)
            resolved = page.url
            if not _group_id_from_url(resolved):
                continue
            if _normalize_uuid(_collection_uuid_from_url(resolved) or "") != _normalize_uuid(collection_uuid):
                continue
            slug = _slug_from_resolved_url(resolved, tile_slug=tile_slug)
            if not slug:
                continue
            if tile_slug and slug != "all":
                parts = [part for part in urlparse(resolved).path.strip("/").split("/") if part]
                if len(parts) >= 2 and parts[1] != tile_slug:
                    continue
            tabs[slug] = {"href": resolved, "label": label}
        except Exception:
            continue

    return tabs


def _normalize_resolved_url(original_url: str, tab_href: str) -> str:
    """Keep the original path; attach collection_uuid and collection_group_id from the tab navigation."""
    original = urlparse(original_url)
    tab = urlparse(tab_href)
    tab_query = parse_qs(tab.query)
    original_query = parse_qs(original.query)
    uuid = (original_query.get("collection_uuid") or tab_query.get("collection_uuid") or [""])[0]
    group_id = (tab_query.get("collection_group_id") or [""])[0]
    if not uuid or not group_id:
        return original._replace(query=tab.query).geturl()
    # Preserve encoded uuid from the original URL when present.
    uuid_token = original.query.split("collection_uuid=", 1)[-1].split("&", 1)[0] if "collection_uuid=" in original.query else uuid
    if uuid_token.endswith("=") and "%3D" not in uuid_token:
        uuid_token = uuid_token[:-1] + "%3D"
    query = f"collection_uuid={uuid_token}&collection_group_id={group_id}"
    return original._replace(query=query).geturl()


def _new_browser_page(*, lat: float, lon: float) -> tuple[Any, Any, Any]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "Playwright is required. Run: pip install playwright && playwright install chromium"
        ) from exc

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
    return playwright, browser, context.new_page()


def resolve_missing_group_ids(
    path: Path = CATEGORY_URLS_PATH,
    *,
    lat: float = DEFAULT_LAT,
    lon: float = DEFAULT_LON,
) -> list[dict[str, Any]]:
    """Fill collection_group_id on /dc/ URLs by reading subcategory tabs from the parent tile page."""
    entries = load_category_urls(path)
    missing: list[tuple[int, dict[str, Any]]] = []
    for index, entry in enumerate(entries):
        url = entry["url"]
        if "/dc" not in url or _group_id_from_url(url):
            continue
        missing.append((index, entry))

    if not missing:
        print("No /dc/ URLs missing collection_group_id.", file=sys.stderr)
        return []

    reports: list[dict[str, Any]] = []
    groups: dict[tuple[str, str], list[tuple[int, dict[str, Any]]]] = {}
    for index, entry in missing:
        url = entry["url"]
        uuid = _collection_uuid_from_url(url)
        if not uuid:
            reports.append(
                {
                    "category": entry["category"],
                    "subcategory": entry["subcategory"],
                    "before": url,
                    "after": None,
                    "status": "unresolved",
                    "reason": "missing collection_uuid",
                }
            )
            continue
        tile_key = _tile_slug(url)
        if not tile_key and _normalize_uuid(uuid) == _normalize_uuid("OTg3NjU0MzIxMjM0NTMzMjU%3D"):
            tile_key = "stationery-games"
        if not tile_key:
            reports.append(
                {
                    "category": entry["category"],
                    "subcategory": entry["subcategory"],
                    "before": url,
                    "after": None,
                    "status": "unresolved",
                    "reason": "cannot infer tile slug from URL path",
                }
            )
            continue
        groups.setdefault((tile_key, uuid), []).append((index, entry))

    playwright, browser, page = _new_browser_page(lat=lat, lon=lon)

    try:
        for (tile_key, uuid), group_entries in groups.items():
            seed_url = _seed_url_for_tile(tile_key, uuid)
            if not seed_url:
                for _, entry in group_entries:
                    reports.append(
                        {
                            "category": entry["category"],
                            "subcategory": entry["subcategory"],
                            "before": entry["url"],
                            "after": None,
                            "status": "unresolved",
                            "reason": f"no seed URL for tile {tile_key!r}",
                        }
                    )
                continue

            print(f"Using tile seed: {seed_url}", file=sys.stderr)

            for index, entry in group_entries:
                url = entry["url"]
                before = url
                after = _resolve_entry_group_id(
                    page,
                    seed_url=seed_url,
                    subcategory_label=entry["subcategory"],
                    original_url=url,
                )
                if after and _group_id_from_url(after):
                    entries[index]["url"] = after
                    status = "resolved"
                    reason = None
                else:
                    status = "unresolved"
                    reason = f"could not click tab {entry['subcategory']!r} on tile page"

                print(f"[{status.upper()}] {entry['category']} / {entry['subcategory']}")
                print(f"  before: {before}")
                print(f"  after:  {after or '(unchanged)'}")
                if reason:
                    print(f"  !! {reason}")
                reports.append(
                    {
                        "category": entry["category"],
                        "subcategory": entry["subcategory"],
                        "before": before,
                        "after": after,
                        "status": status,
                        "reason": reason,
                    }
                )
    finally:
        _close_browser(playwright, browser)

    for index, entry in enumerate(entries):
        if isinstance(entry.get("url"), str) and "/dc" in entry["url"]:
            entries[index]["url"] = _clean_dc_url(entry["url"])

    path.write_text(json.dumps(entries, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote updated URLs to {path}", file=sys.stderr)
    unresolved = [row for row in reports if row["status"] != "resolved"]
    if unresolved:
        print(f"\n{len(unresolved)} URL(s) could not be resolved:", file=sys.stderr)
        for row in unresolved:
            print(f"  - {row['category']} / {row['subcategory']}: {row['reason']}", file=sys.stderr)
    return reports


def _activate_subcategory_tab(page: Any, url: str) -> None:
    """Blinkit /dc/ pages without collection_group_id default to the first tab."""
    query = parse_qs(urlparse(url).query)
    if query.get("collection_group_id"):
        return

    slug = _url_tab_key(url)
    if not slug or slug == "all":
        return

    _reset_tab_bar_scroll(page)
    for _ in range(30):
        tab_href = page.evaluate(
            """(slug) => {
                for (const link of document.querySelectorAll('a[href]')) {
                    const href = link.href;
                    if (href.includes(slug) && href.includes('collection_group_id=')) {
                        return href;
                    }
                }
                return null;
            }""",
            slug,
        )
        if isinstance(tab_href, str) and tab_href:
            if tab_href.rstrip("/") != page.url.rstrip("/"):
                page.goto(tab_href, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(2000)
            return
        _scroll_tab_bar(page)


def _group_id_from_url(url: str) -> str | None:
    query = parse_qs(urlparse(url).query)
    values = query.get("collection_group_id") or []
    return values[0] if values else None


class _ListingCapture:
    payloads: list[Any]
    paginated_post_template: dict[str, str] | None
    paginated_headers: dict[str, str]

    def __init__(self) -> None:
        self.payloads = []
        self.paginated_post_template = None
        self.paginated_headers = {}
        self.resolved_url: str | None = None

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
    pincode: str = DEFAULT_PINCODE,
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
    page.wait_for_timeout(2000)
    _ensure_delivery_location(page, pincode)
    _activate_subcategory_tab(page, url)
    page.wait_for_timeout(max(0, wait_ms - 2000))
    page.mouse.wheel(0, 4500)
    page.wait_for_timeout(1500)
    page.remove_listener("request", capture.on_request)
    capture.resolved_url = page.url

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
    pincode: str = DEFAULT_PINCODE,
    wait_ms: int = 8000,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    collection_meta = dict(meta or parse_collection_url(url))
    playwright, browser, page, capture = _capture_listing_payloads(
        url, lat=lat, lon=lon, pincode=pincode, wait_ms=wait_ms
    )
    try:
        resolved_group_id = _group_id_from_url(capture.resolved_url or page.url)
        if resolved_group_id and not collection_meta.get("collection_group_id"):
            collection_meta["collection_group_id"] = resolved_group_id
        products, pages_fetched = _paginate_collection(page, capture, collection_meta)
    finally:
        _close_browser(playwright, browser)

    collection_meta["product_count"] = len(products)
    collection_meta["scraped_at"] = datetime.now(timezone.utc).isoformat()
    collection_meta["location"] = {
        "name": DEFAULT_LOCATION_NAME,
        "lat": lat,
        "lon": lon,
        "pincode": pincode,
    }
    return {
        **collection_meta,
        "products": products,
        "pages_fetched": pages_fetched,
    }


def _parse_skip_subcategory(value: str) -> tuple[str, str]:
    if "|" not in value:
        raise ValueError(f"Invalid --skip-subcategory {value!r}; use CATEGORY|Subcategory")
    category, subcategory = value.split("|", 1)
    category = category.strip()
    subcategory = subcategory.strip()
    if not category or not subcategory:
        raise ValueError(f"Invalid --skip-subcategory {value!r}; use CATEGORY|Subcategory")
    return category, subcategory


def run_batch(
    *,
    lat: float = DEFAULT_LAT,
    lon: float = DEFAULT_LON,
    pincode: str = DEFAULT_PINCODE,
    wait_ms: int = 8000,
    category_urls_path: Path = CATEGORY_URLS_PATH,
    output_root: Path = RAW_DIR,
    skip_categories: list[str] | None = None,
    skip_subcategories: list[str] | None = None,
) -> Path:
    entries = load_category_urls(category_urls_path)
    skip = set(skip_categories or [])
    skip_subs = {_parse_skip_subcategory(value) for value in (skip_subcategories or [])}
    if skip or skip_subs:
        entries = [
            entry
            for entry in entries
            if entry["category"] not in skip
            and (entry["category"], entry["subcategory"]) not in skip_subs
        ]

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    run_dir = output_root / stamp
    run_dir.mkdir(parents=True, exist_ok=True)

    manifest: dict[str, Any] = {
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "location": {
            "name": DEFAULT_LOCATION_NAME,
            "lat": lat,
            "lon": lon,
            "pincode": pincode,
        },
        "source": str(category_urls_path),
        "skipped_categories": sorted(skip),
        "skipped_subcategories": [
            {"category": category, "subcategory": subcategory}
            for category, subcategory in sorted(skip_subs)
        ],
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
                pincode=pincode,
                wait_ms=wait_ms,
                meta={
                    **parse_collection_url(url),
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
    parser.add_argument("--pincode", default=DEFAULT_PINCODE, help="Delivery pincode (default: Sarjapur service area)")
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
    parser.add_argument(
        "--skip-subcategory",
        action="append",
        default=[],
        metavar="CATEGORY|Subcategory",
        help="Skip one subcategory during --batch (repeatable)",
    )
    parser.add_argument(
        "--resolve-group-ids",
        action="store_true",
        help="Discover collection_group_id from tab bars and update data/category_urls.json",
    )
    args = parser.parse_args(argv)

    if args.resolve_group_ids:
        resolve_missing_group_ids(lat=args.lat, lon=args.lon)
        return 0

    if args.batch:
        run_batch(
            lat=args.lat,
            lon=args.lon,
            pincode=args.pincode,
            wait_ms=args.wait_ms,
            skip_categories=args.skip_category,
            skip_subcategories=args.skip_subcategory,
        )
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
