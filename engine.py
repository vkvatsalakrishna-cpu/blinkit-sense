"""Deterministic resolver and household filter for Blinkit Sense."""

from __future__ import annotations

import math
import re
from typing import Any

from phases.phase_2_data.loader import (
    catalog_by_id,
    load_catalog,
    purchased_tiles,
)

STOPWORDS = frozenset({"and", "or", "the", "a", "for", "with"})
GENERIC_WORDS = frozenset(
    {
        "set",
        "pack",
        "box",
        "gift",
        "hamper",
        "kit",
        "combo",
        "assorted",
        "premium",
        "water",
        "mix",
        "plain",
        "small",
        "large",
    }
)
ACCESSORY_HINTS = frozenset({"scooper", "scoop", "tray", "brush", "spray", "refill"})
GAP_MESSAGE = "We don't stock this — you'll need it elsewhere."
SENSITIVE_CATEGORIES = frozenset({"Health & Pharma", "Baby Care"})
SENSITIVE_GUIDANCE = {
    "Health & Pharma": "Health & Pharma items need separate browsing — not auto-added.",
    "Baby Care": "Baby Care items need separate browsing — not auto-added.",
}
MAX_COMPOSED_ITEMS = 6
ROUTINE_OWNED_THRESHOLD = 1

FEE_DELIVERY = 30
FEE_HANDLING = 12
FEE_SMALL_CART = 20
THRESHOLD = 99

# Tiles that should not resolve needs for a given confirmed situation.
_SPECIALTY_STORES = frozenset(
    {
        "Pet Store",
        "Toy Store",
        "Spiritual Needs",
        "Book Store",
        "Jewellery Store",
        "E-Gifts Store",
        "Fashion Basics",
        "Sports Store",
        "Hobby Store",
        "Travel Store",
        "Pharma Store",
        "Ice Cream Store",
    }
)
_PERSONAL_SENSITIVE = frozenset(
    {
        "Paan Corner",
        "Feminine Hygiene",
        "Sexual Wellness",
        "Health & Pharma",
    }
)
_RAW_COOKING_STAPLES = frozenset(
    {
        "Vegetables & Fruits",
        "Atta, Rice & Dal",
        "Oil, Ghee & Masala",
        "Chicken, Meat & Fish",
    }
)
_JUNK_FOOD = frozenset(
    {"Sweets & Chocolates", "Ice Creams & More", "Chips & Namkeen"}
)

# Specialty / personal tiles vetoed for most situations (not in core catalog depth).
_SCENARIO_BASE_VETO = _SPECIALTY_STORES | _PERSONAL_SENSITIVE | frozenset({"Baby Care"})

IMPLAUSIBLE_TILES: dict[str, frozenset[str]] = {
    "festival_gifting": frozenset(
        {
            # Routine staples and household — not gift shopping.
            "Vegetables & Fruits",
            "Atta, Rice & Dal",
            "Oil, Ghee & Masala",
            "Chicken, Meat & Fish",
            "Dairy, Bread & Eggs",
            "Cleaners & Repellents",
            "Paan Corner",
            "Feminine Hygiene",
            "Sexual Wellness",
            "Health & Pharma",
        }
    ),
    "hosting": _SPECIALTY_STORES | _PERSONAL_SENSITIVE | frozenset({"Baby Care"}),
    "moving_in": frozenset(
        {"Pet Store", "Toy Store", "Spiritual Needs", "Baby Care"}
    ),
    "new_pet": frozenset(
        {"Kitchenware & Appliances", "Home & Lifestyle", "Bath & Body"}
    ),
    "health": (_SPECIALTY_STORES - frozenset({"Sports Store"}))
    | (_PERSONAL_SENSITIVE - frozenset({"Health & Pharma"}))
    | _JUNK_FOOD
    | frozenset({"Cleaners & Repellents", "Home & Lifestyle"}),
    "cooking_project": _SPECIALTY_STORES
    | _PERSONAL_SENSITIVE
    | frozenset({"Baby Care", "Cleaners & Repellents", "Home & Lifestyle"}),
    "concert_night": _SPECIALTY_STORES
    | _PERSONAL_SENSITIVE
    | _RAW_COOKING_STAPLES
    | frozenset(
        {
            "Baby Care",
            "Cleaners & Repellents",
            "Kitchenware & Appliances",
            "Home & Lifestyle",
        }
    ),
    "road_trip": _SPECIALTY_STORES
    | _PERSONAL_SENSITIVE
    | _RAW_COOKING_STAPLES
    | frozenset(
        {
            "Baby Care",
            "Cleaners & Repellents",
            "Kitchenware & Appliances",
            "Home & Lifestyle",
        }
    ),
    "house_party": _SPECIALTY_STORES
    | _PERSONAL_SENSITIVE
    | _RAW_COOKING_STAPLES
    | frozenset({"Baby Care"}),
    "movie_night": _SPECIALTY_STORES
    | _PERSONAL_SENSITIVE
    | _RAW_COOKING_STAPLES
    | frozenset(
        {
            "Baby Care",
            "Cleaners & Repellents",
            "Kitchenware & Appliances",
        }
    ),
    "birthday": (_SPECIALTY_STORES - frozenset({"Toy Store"}))
    | _PERSONAL_SENSITIVE
    | _RAW_COOKING_STAPLES
    | frozenset({"Cleaners & Repellents"}),
    "hangover_recovery": _SPECIALTY_STORES
    | (_PERSONAL_SENSITIVE - frozenset({"Health & Pharma"}))
    | frozenset(
        {
            "Baby Care",
            "Cleaners & Repellents",
            "Kitchenware & Appliances",
            "Electronics",
            "Stationery & Games",
        }
    ),
    "fitness_restart": _SPECIALTY_STORES | _PERSONAL_SENSITIVE | _JUNK_FOOD | frozenset({"Baby Care"}),
    "sick_at_home": _SPECIALTY_STORES
    | _PERSONAL_SENSITIVE
    | _JUNK_FOOD
    | frozenset({"Electronics", "Stationery & Games"}),
    "new_baby": frozenset(
        {
            "Pet Store",
            "Spiritual Needs",
            "Book Store",
            "Jewellery Store",
            "E-Gifts Store",
            "Fashion Basics",
            "Sports Store",
            "Hobby Store",
            "Travel Store",
            "Pharma Store",
            "Ice Cream Store",
            "Paan Corner",
            "Feminine Hygiene",
            "Sexual Wellness",
            "Health & Pharma",
            "Cleaners & Repellents",
        }
    ),
    "new_flatmate": _SPECIALTY_STORES | _PERSONAL_SENSITIVE | frozenset({"Baby Care"}),
    "deadline_night": _SPECIALTY_STORES
    | _PERSONAL_SENSITIVE
    | _RAW_COOKING_STAPLES
    | frozenset(
        {
            "Baby Care",
            "Cleaners & Repellents",
            "Home & Lifestyle",
            "Kitchenware & Appliances",
        }
    ),
    "monsoon_prep": _SCENARIO_BASE_VETO,
    "picnic_day": _SPECIALTY_STORES
    | _PERSONAL_SENSITIVE
    | _RAW_COOKING_STAPLES
    | frozenset(
        {
            "Baby Care",
            "Cleaners & Repellents",
            "Kitchenware & Appliances",
            "Home & Lifestyle",
        }
    ),
    "deep_clean": _SCENARIO_BASE_VETO,
    "date_night": _SPECIALTY_STORES
    | _PERSONAL_SENSITIVE
    | _RAW_COOKING_STAPLES
    | frozenset({"Baby Care", "Cleaners & Repellents"}),
    "skincare_routine": _SPECIALTY_STORES
    | _PERSONAL_SENSITIVE
    | _RAW_COOKING_STAPLES
    | _JUNK_FOOD
    | frozenset(
        {
            "Baby Care",
            "Cleaners & Repellents",
            "Electronics",
            "Home & Lifestyle",
            "Kitchenware & Appliances",
            "Stationery & Games",
            "Dairy, Bread & Eggs",
            "Drinks & Juices",
            "Instant Food",
            "Sauces & Spreads",
            "Tea, Coffee & Milk Drinks",
            "Dry Fruits & Cereals",
            "Chicken, Meat & Fish",
            "Ice Creams & More",
        }
    ),
    "home_office": _SPECIALTY_STORES
    | _PERSONAL_SENSITIVE
    | _RAW_COOKING_STAPLES
    | _JUNK_FOOD
    | frozenset(
        {
            "Baby Care",
            "Bath & Body",
            "Beauty & Cosmetics",
            "Hair",
            "Skin & Face",
            "Cleaners & Repellents",
            "Kitchenware & Appliances",
            "Dairy, Bread & Eggs",
            "Bakery & Biscuits",
            "Dry Fruits & Cereals",
            "Chicken, Meat & Fish",
            "Chips & Namkeen",
            "Drinks & Juices",
            "Instant Food",
            "Sauces & Spreads",
            "Tea, Coffee & Milk Drinks",
            "Sweets & Chocolates",
            "Ice Creams & More",
            "Vegetables & Fruits",
            "Oil, Ghee & Masala",
        }
    ),
    "self_care_night": _SPECIALTY_STORES
    | _PERSONAL_SENSITIVE
    | _RAW_COOKING_STAPLES
    | frozenset(
        {
            "Baby Care",
            "Cleaners & Repellents",
            "Electronics",
            "Home & Lifestyle",
            "Kitchenware & Appliances",
            "Stationery & Games",
            "Chicken, Meat & Fish",
            "Instant Food",
            "Oil, Ghee & Masala",
            "Vegetables & Fruits",
            "Atta, Rice & Dal",
            "Chips & Namkeen",
            "Drinks & Juices",
            "Dairy, Bread & Eggs",
            "Dry Fruits & Cereals",
            "Sauces & Spreads",
        }
    ),
    "game_night": _SPECIALTY_STORES
    | _PERSONAL_SENSITIVE
    | _RAW_COOKING_STAPLES
    | frozenset(
        {
            "Baby Care",
            "Bath & Body",
            "Beauty & Cosmetics",
            "Hair",
            "Skin & Face",
            "Cleaners & Repellents",
            "Home & Lifestyle",
            "Kitchenware & Appliances",
            "Electronics",
            "Dairy, Bread & Eggs",
            "Bakery & Biscuits",
            "Dry Fruits & Cereals",
            "Chicken, Meat & Fish",
            "Oil, Ghee & Masala",
            "Sauces & Spreads",
            "Tea, Coffee & Milk Drinks",
            "Vegetables & Fruits",
            "Atta, Rice & Dal",
            "Sweets & Chocolates",
            "Ice Creams & More",
        }
    ),
    "baking_day": _SPECIALTY_STORES
    | _PERSONAL_SENSITIVE
    | frozenset(
        {
            "Baby Care",
            "Bath & Body",
            "Beauty & Cosmetics",
            "Hair",
            "Skin & Face",
            "Cleaners & Repellents",
            "Electronics",
            "Home & Lifestyle",
            "Stationery & Games",
            "Chicken, Meat & Fish",
            "Chips & Namkeen",
            "Drinks & Juices",
            "Instant Food",
            "Tea, Coffee & Milk Drinks",
            "Vegetables & Fruits",
            "Atta, Rice & Dal",
            "Dry Fruits & Cereals",
            "Sweets & Chocolates",
            "Ice Creams & More",
        }
    ),
    "kids_home": (_SPECIALTY_STORES - frozenset({"Toy Store"}))
    | _PERSONAL_SENSITIVE
    | _RAW_COOKING_STAPLES
    | frozenset(
        {
            "Cleaners & Repellents",
            "Electronics",
            "Home & Lifestyle",
            "Kitchenware & Appliances",
            "Beauty & Cosmetics",
            "Hair",
            "Skin & Face",
            "Bath & Body",
            "Oil, Ghee & Masala",
            "Chicken, Meat & Fish",
            "Tea, Coffee & Milk Drinks",
            "Sauces & Spreads",
            "Instant Food",
            "Drinks & Juices",
            "Dry Fruits & Cereals",
            "Dairy, Bread & Eggs",
            "Sweets & Chocolates",
            "Ice Creams & More",
            "Vegetables & Fruits",
            "Atta, Rice & Dal",
        }
    ),
    "hair_care": _SPECIALTY_STORES
    | _PERSONAL_SENSITIVE
    | _RAW_COOKING_STAPLES
    | _JUNK_FOOD
    | frozenset(
        {
            "Baby Care",
            "Beauty & Cosmetics",
            "Cleaners & Repellents",
            "Electronics",
            "Home & Lifestyle",
            "Kitchenware & Appliances",
            "Stationery & Games",
            "Dairy, Bread & Eggs",
            "Bakery & Biscuits",
            "Dry Fruits & Cereals",
            "Chicken, Meat & Fish",
            "Chips & Namkeen",
            "Drinks & Juices",
            "Instant Food",
            "Sauces & Spreads",
            "Tea, Coffee & Milk Drinks",
            "Sweets & Chocolates",
            "Ice Creams & More",
            "Vegetables & Fruits",
            "Oil, Ghee & Masala",
        }
    ),
    "care_package": (_SPECIALTY_STORES - frozenset({"E-Gifts Store"}))
    | _PERSONAL_SENSITIVE
    | _RAW_COOKING_STAPLES
    | frozenset(
        {
            "Baby Care",
            "Beauty & Cosmetics",
            "Hair",
            "Skin & Face",
            "Cleaners & Repellents",
            "Electronics",
            "Home & Lifestyle",
            "Kitchenware & Appliances",
            "Stationery & Games",
            "Pet Store",
            "Toy Store",
            "Chicken, Meat & Fish",
            "Chips & Namkeen",
            "Drinks & Juices",
            "Instant Food",
            "Tea, Coffee & Milk Drinks",
            "Vegetables & Fruits",
            "Atta, Rice & Dal",
            "Oil, Ghee & Masala",
            "Dairy, Bread & Eggs",
            "Bakery & Biscuits",
            "Ice Creams & More",
            "Sauces & Spreads",
        }
    ),
    "winter_care": _SPECIALTY_STORES
    | _PERSONAL_SENSITIVE
    | _RAW_COOKING_STAPLES
    | _JUNK_FOOD
    | frozenset(
        {
            "Baby Care",
            "Beauty & Cosmetics",
            "Cleaners & Repellents",
            "Electronics",
            "Home & Lifestyle",
            "Kitchenware & Appliances",
            "Stationery & Games",
            "Pet Store",
            "Toy Store",
            "Dairy, Bread & Eggs",
            "Bakery & Biscuits",
            "Dry Fruits & Cereals",
            "Chicken, Meat & Fish",
            "Chips & Namkeen",
            "Drinks & Juices",
            "Instant Food",
            "Sauces & Spreads",
            "Sweets & Chocolates",
            "Ice Creams & More",
            "Vegetables & Fruits",
            "Atta, Rice & Dal",
            "Oil, Ghee & Masala",
        }
    ),
}


def _implausible_tiles(situation_id: str | None) -> frozenset[str]:
    if not situation_id:
        return frozenset()
    return IMPLAUSIBLE_TILES.get(situation_id, frozenset())


def fee_breakdown(cart_subtotal: int) -> dict:
    small_cart = FEE_SMALL_CART if cart_subtotal < THRESHOLD else 0
    total_fees = FEE_DELIVERY + FEE_HANDLING + small_cart
    gap_to_threshold = max(0, THRESHOLD - cart_subtotal)
    return {
        "delivery": FEE_DELIVERY,
        "handling": FEE_HANDLING,
        "small_cart": small_cart,
        "total_fees": total_fees,
        "gap_to_threshold": gap_to_threshold,
    }


def _tokenize_need(need: str) -> list[str]:
    words = re.split(r"\s+", need.lower().strip())
    tokens = [re.sub(r"[^\w]", "", word) for word in words]
    return [token for token in tokens if token and token not in STOPWORDS]


def _need_variants(word: str) -> list[str]:
    variants = [word]
    if word.endswith("s") and len(word) > 3:
        variants.append(word[:-1])
    elif not word.endswith("s"):
        variants.append(f"{word}s")
    return variants


def _word_in_name(word: str, product_name: str) -> bool:
    name_lower = product_name.lower()
    for variant in _need_variants(word):
        if re.search(rf"(?<![a-z]){re.escape(variant)}(?![a-z])", name_lower):
            return True
    return False


def _matched_words(words: list[str], product_name: str) -> list[str]:
    return [word for word in words if _word_in_name(word, product_name)]


def _accessory_penalty(product_name: str, content_words: list[str]) -> int:
    name_tokens = set(_tokenize_need(product_name))
    need_set = set(content_words)
    extra = name_tokens - need_set
    penalty = 0
    for token in extra:
        if token not in ACCESSORY_HINTS:
            continue
        if any(word in token for word in content_words):
            continue
        penalty += 1
    return penalty


def _head_noun(content_words: list[str]) -> str:
    non_generic = [word for word in content_words if word not in GENERIC_WORDS]
    if non_generic:
        return non_generic[-1]
    return content_words[-1]


def _is_plural_pair(a: str, b: str) -> bool:
    if a == b:
        return True
    if not a.endswith("s") and a + "s" == b:
        return True
    if not b.endswith("s") and b + "s" == a:
        return True
    if a.endswith("s") and a[:-1] == b:
        return True
    if b.endswith("s") and b[:-1] == a:
        return True
    return False


def _exact_token_match(word: str, product_name: str) -> bool:
    for token in _tokenize_need(product_name):
        if _is_plural_pair(word, token):
            return True
    return False


def _qualifies_fallback_match(
    content_words: list[str], matched_words: list[str], product_name: str
) -> bool:
    if not _qualifies_match(content_words, matched_words):
        return False

    head = _head_noun(content_words)
    if head not in matched_words:
        return False

    tokens = _tokenize_need(product_name)
    if head not in tokens:
        return False

    head_idx = tokens.index(head)
    rightmost_match = -1
    for index, token in enumerate(tokens):
        if any(_is_plural_pair(word, token) for word in content_words):
            rightmost_match = index
    if head_idx != rightmost_match:
        return False

    if (
        len(content_words) == 1
        and head_idx == 0
        and len(tokens) > 1
        and not any(_is_plural_pair(word, tokens[1]) for word in content_words)
    ):
        return False

    if _word_in_name(head, product_name) and not _exact_token_match(head, product_name):
        return False

    return True


def _qualifies_match(content_words: list[str], matched_words: list[str]) -> bool:
    if not matched_words:
        return False
    min_required = max(1, math.ceil(len(content_words) / 2))
    if len(matched_words) < min_required:
        return False
    if not any(word not in GENERIC_WORDS for word in matched_words):
        return False
    non_generic = [word for word in content_words if word not in GENERIC_WORDS]
    if non_generic and not all(word in matched_words for word in non_generic):
        return False
    return True


def _match_key(
    content_words: list[str], matched_words: list[str], product_name: str, price: int
) -> tuple:
    score = len(matched_words)
    ratio = score / len(content_words)
    distinctive = sum(1 for word in matched_words if word not in GENERIC_WORDS)
    penalty = _accessory_penalty(product_name, content_words)
    return (score, ratio, distinctive, -penalty, price)


def cart_subtotal(household: dict, catalog: list[dict] | None = None) -> int:
    catalog = catalog or load_catalog()
    by_id = catalog_by_id(catalog)
    return sum(
        by_id[sku]["price"]
        for sku in household.get("current_cart", [])
        if sku in by_id
    )


def _has_image(item: dict) -> bool:
    image_url = item.get("image_url")
    return isinstance(image_url, str) and bool(image_url.strip())


def _match_quality(key: tuple) -> tuple:
    return key[:4]


def _median_priced(
    rows: list[tuple[dict, list[str], tuple]],
) -> tuple[dict, list[str], tuple]:
    sorted_rows = sorted(rows, key=lambda row: row[0]["price"])
    return sorted_rows[(len(sorted_rows) - 1) // 2]


def _catalog_option(item: dict) -> dict[str, Any]:
    return {
        "resolved_sku": item["id"],
        "resolved_name": item["name"],
        "price": item["price"],
        "category": item["category"],
        "image_url": item.get("image_url"),
    }


def _qualified_candidates(
    content_words: list[str],
    available: list[dict],
    implausible: frozenset[str],
    allowed_categories: frozenset[str] | None = None,
    *,
    strict: bool = False,
) -> list[tuple[dict, list[str], tuple]]:
    qualified: list[tuple[dict, list[str], tuple]] = []

    for item in available:
        if item["category"] in implausible:
            continue
        if allowed_categories is not None and item["category"] not in allowed_categories:
            continue
        matched = _matched_words(content_words, item["name"])
        qualifies = (
            _qualifies_fallback_match(content_words, matched, item["name"])
            if strict
            else _qualifies_match(content_words, matched)
        )
        if not qualifies:
            continue
        key = _match_key(content_words, matched, item["name"], item["price"])
        qualified.append((item, matched, key))

    return qualified


def _ranked_options(
    qualified: list[tuple[dict, list[str], tuple]],
    budget_min: int | None = None,
    budget_max: int | None = None,
) -> list[tuple[dict, list[str], tuple]]:
    if not qualified:
        return []

    best_quality = max(_match_quality(key) for _, _, key in qualified)
    top_tier = [row for row in qualified if _match_quality(row[2]) == best_quality]

    pool = top_tier
    if budget_min is not None:
        pool = [row for row in pool if row[0]["price"] >= budget_min]
    if budget_max is not None:
        pool = [row for row in pool if row[0]["price"] <= budget_max]

    with_image = [row for row in pool if _has_image(row[0])]
    return sorted(with_image, key=lambda row: row[0]["price"])


def _pick_winning_candidate(
    qualified: list[tuple[dict, list[str], tuple]],
    budget_min: int | None = None,
    budget_max: int | None = None,
) -> tuple[dict | None, list[str], tuple, list[dict[str, Any]]]:
    ranked = _ranked_options(qualified, budget_min, budget_max)
    if not ranked:
        return None, [], (0, 0, 0, 0, 0), []

    item, matched, key = _median_priced(ranked)
    options = [_catalog_option(row[0]) for row in ranked]
    return item, matched, key, options


def _search_candidates(
    content_words: list[str],
    available: list[dict],
    implausible: frozenset[str],
    allowed_categories: frozenset[str] | None = None,
    *,
    strict: bool = False,
    budget_min: int | None = None,
    budget_max: int | None = None,
) -> tuple[dict | None, list[str], tuple, list[dict[str, Any]]]:
    qualified = _qualified_candidates(
        content_words,
        available,
        implausible,
        allowed_categories,
        strict=strict,
    )
    return _pick_winning_candidate(qualified, budget_min, budget_max)


def _best_candidate(
    content_words: list[str],
    available: list[dict],
    situation_id: str | None = None,
    expected_tiles: list[str] | None = None,
    budget_min: int | None = None,
    budget_max: int | None = None,
) -> tuple[dict | None, list[str], tuple, list[dict[str, Any]]]:
    implausible = _implausible_tiles(situation_id)

    if expected_tiles:
        best = _search_candidates(
            content_words,
            available,
            implausible,
            frozenset(expected_tiles),
            budget_min=budget_min,
            budget_max=budget_max,
        )
        if best[0] is not None:
            return best

    return _search_candidates(
        content_words,
        available,
        implausible,
        strict=True,
        budget_min=budget_min,
        budget_max=budget_max,
    )


def _owned_skus(household: dict) -> dict[str, int]:
    return {
        entry["sku"]: entry["orders_per_month"]
        for entry in household.get("order_history", [])
        if "sku" in entry
    }


def _gap_entry(need: dict, message: str = GAP_MESSAGE) -> dict:
    return {
        "role": need.get("role", ""),
        "need": need.get("need", ""),
        "status": "gap",
        "gap_message": message,
    }


def gap_tile_coverage(
    need_text: str,
    location_name: str,
    catalog: list[dict] | None = None,
) -> dict[str, Any]:
    """Infer the most likely tile for a gap need and report catalogue coverage."""
    catalog = catalog or load_catalog()
    content_words = _tokenize_need(need_text)
    at_location = [
        item for item in catalog if location_name in item.get("available_in", [])
    ]

    overlap_by_tile: dict[str, int] = {}
    for item in at_location:
        matched = _matched_words(content_words, item["name"])
        if not matched:
            continue
        tile = item["category"]
        overlap_by_tile[tile] = overlap_by_tile.get(tile, 0) + 1

    if overlap_by_tile:
        inferred_tile = max(overlap_by_tile, key=overlap_by_tile.get)
    else:
        inferred_tile = None

    tile_total = 0
    if inferred_tile:
        tile_total = sum(1 for item in at_location if item["category"] == inferred_tile)

    return {
        "inferred_tile": inferred_tile,
        "tile_total_at_location": tile_total,
        "name_overlap_count": overlap_by_tile.get(inferred_tile, 0) if inferred_tile else 0,
    }


def resolve_needs(
    needs: list[dict],
    location_name: str,
    situation_id: str | None = None,
    catalog: list[dict] | None = None,
    budget_min: int | None = None,
    budget_max: int | None = None,
) -> list[dict]:
    """Map abstract needs to catalog SKUs for the given location."""
    catalog = catalog or load_catalog()
    available = [
        item for item in catalog if location_name in item.get("available_in", [])
    ]

    candidates: list[dict] = []
    for index, need in enumerate(needs):
        content_words = _tokenize_need(need.get("need", ""))
        if not content_words:
            candidates.append(
                {
                    "index": index,
                    "need": need,
                    "item": None,
                    "matched_words": [],
                    "match_key": (0, 0, 0, 0, 0),
                }
            )
            continue

        item, matched_words, match_key, options = _best_candidate(
            content_words,
            available,
            situation_id,
            need.get("expected_tiles") or None,
            budget_min=budget_min,
            budget_max=budget_max,
        )
        candidates.append(
            {
                "index": index,
                "need": need,
                "item": item,
                "matched_words": matched_words,
                "match_key": match_key,
                "options": options,
            }
        )

    # Assign SKUs in match-strength order so the best claim wins (fixes litter dedup starvation).
    used_skus: set[str] = set()
    assignment: dict[int, dict | None] = {}

    for candidate in sorted(candidates, key=lambda row: row["match_key"], reverse=True):
        index = candidate["index"]
        item = candidate["item"]
        if item is None:
            assignment[index] = None
            continue
        sku_id = item["id"]
        if sku_id in used_skus:
            assignment[index] = None
            continue
        used_skus.add(sku_id)
        assignment[index] = candidate

    resolved: list[dict] = []
    for index, need in enumerate(needs):
        assigned = assignment.get(index)
        if not assigned or assigned["item"] is None:
            resolved.append(_gap_entry(need))
            continue

        item = assigned["item"]
        content_words = _tokenize_need(need.get("need", ""))
        score = len(assigned["matched_words"])
        options = assigned.get("options") or []
        option_index = (len(options) - 1) // 2 if options else 0
        resolved.append(
            {
                "role": need.get("role", ""),
                "need": need.get("need", ""),
                "why": need.get("why", ""),
                "quantity_reasoning": need.get("quantity_reasoning", ""),
                "expected_tiles": need.get("expected_tiles", []),
                "resolved_sku": item["id"],
                "resolved_name": item["name"],
                "price": item["price"],
                "category": item["category"],
                "status": "matched",
                "match_score": score,
                "match_ratio": score / len(content_words),
                "matched_words": assigned["matched_words"],
                "options": options,
                "option_index": option_index,
            }
        )

    return resolved


def apply_household_filter(
    resolved: list[dict],
    household: dict,
    catalog: list[dict] | None = None,
) -> dict[str, Any]:
    """Apply owned drop, flags, sensitive veto, cap, cart dedup, and fee maths."""
    catalog = catalog or load_catalog()
    by_id = catalog_by_id(catalog)
    owned = _owned_skus(household)
    cart_skus = set(household.get("current_cart", []))
    tiles_bought = purchased_tiles(household, catalog)

    cart_subtotal = sum(
        by_id[sku]["price"] for sku in household.get("current_cart", []) if sku in by_id
    )

    items: list[dict] = []
    gaps: list[dict] = []
    sensitive_guidance: list[str] = []

    for entry in resolved:
        if entry.get("status") != "matched":
            gaps.append(entry)
            continue

        sku_id = entry["resolved_sku"]
        if owned.get(sku_id, 0) >= ROUTINE_OWNED_THRESHOLD:
            continue

        category = entry["category"]
        if category in SENSITIVE_CATEGORIES:
            guidance = SENSITIVE_GUIDANCE[category]
            if guidance not in sensitive_guidance:
                sensitive_guidance.append(guidance)
            continue

        flagged = dict(entry)
        flagged["flag"] = (
            "new_category" if category not in tiles_bought else "deepening"
        )
        items.append(flagged)

    items.sort(key=lambda item: item.get("match_score", 0), reverse=True)
    if len(items) > MAX_COMPOSED_ITEMS:
        items = items[:MAX_COMPOSED_ITEMS]

    items = [item for item in items if item["resolved_sku"] not in cart_skus]

    suggested_total = sum(item["price"] for item in items)
    combined_subtotal = cart_subtotal + suggested_total

    return {
        "items": items,
        "gaps": gaps,
        "sensitive_guidance": sensitive_guidance,
        "cart_subtotal": cart_subtotal,
        "suggested_total": suggested_total,
        "fee": fee_breakdown(combined_subtotal),
    }
