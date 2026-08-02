"""LLM calls for Blinkit Sense — situation reader (Call 1) and need planner (Call 2)."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI, RateLimitError

from engine import IMPLAUSIBLE_TILES
from phases.phase_2_data.loader import all_tiles

load_dotenv()

logger = logging.getLogger(__name__)

CACHE_ENABLED = True
_CACHE_DIR = Path(__file__).resolve().parent / "data" / "cache"
_CACHE_PATH = _CACHE_DIR / "llm_cache.json"

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
VALID_PLANNER_TILES = all_tiles()
_VALID_TILES_SET = frozenset(VALID_PLANNER_TILES)

SITUATION_READER_SYSTEM = """You are a checkout-time situation inference engine for an Indian quick-commerce grocery app.

You receive a JSON payload with:
- cart_items: product names with Blinkit tile categories
- delivery_location: where the order will be delivered
- location_unfamiliar: true if this address is new for the customer
- today: today's date (ISO)

Infer up to four plausible life situations that could explain this cart. Return JSON only matching this schema:
{
  "confidence": <float 0.0-1.0, must equal candidates[0].score>,
  "candidates": [
    {
      "id": "<scenario id, align with known ids where possible: festival_gifting, hosting, moving_in, new_pet, health, stocking, cooking_project>",
      "label": "<customer-facing chip text, max 4 words>",
      "reasoning": "<roughly 10 words or fewer>",
      "score": <float 0.0-1.0>
    }
  ]
}

Rules:
- Exactly 4 candidates, ordered by descending score.
- Each candidate must include a score between 0.0 and 1.0; confidence equals the top candidate's score.
- Candidate labels must be 4 words or fewer.
- reasoning: one short clause, roughly 10 words maximum — the UI truncates longer text.
- Calibrate scores: high confidence for strong situational items (cat food, bedsheet, dry fruits near festivals); low confidence (below 0.4) for staple-only carts (milk, bread, eggs).
- Unfamiliar delivery location and festival proximity raise confidence.
- Never reference or infer purchase history — it is not provided.
- Return raw JSON only. Do not wrap the response in markdown code fences. Do not use ```json or ``` blocks. No prose before or after the JSON."""


def _need_planner_system(valid_tiles: list[str]) -> str:
    tile_list = "\n".join(f"- {tile}" for tile in valid_tiles)
    return f"""You are a need planner for an Indian quick-commerce app. Given a confirmed life situation, decompose it into abstract household needs grouped by role.

You receive a JSON payload with:
- situation_id, situation_label, prompt_context: the confirmed situation
- tile_categories: Blinkit tile categories relevant to this situation (for domain awareness, not product retrieval)

Return JSON only matching this schema:
{{
  "situation_label": "<refined situation heading>",
  "needs": [
    {{
      "role": "<grouping label, e.g. Sleep, Bathroom, Cleaning>",
      "need": "<one product only — label wording as on Indian packs, singular>",
      "quantity_reasoning": "<why this quantity makes sense — logic only, no sizes>",
      "expected_tiles": ["<1-3 tile names from the valid list below>"]
    }}
  ],
  "unavailable": ["<needs Blinkit likely cannot cover, optional advisory>"]
}}

Valid tile names (expected_tiles must use only these, exact spelling):
{tile_list}

Rules:
- Return at most 7 needs — only what genuinely matters for the situation.
- Each need names exactly ONE product. Never combine items: not "mop and bucket", "plates and bowls", "pots and pans", "glasses and mugs". Split into separate needs.
- Each need is singular and catalogue-searchable: "bedsheet" not "bed sheets", "towel" not "shower towels", "pillow" not "pillows". Be specific where ambiguous: "refined oil" not "oil", "pet bowl" not "bowl" for a cat.
- Use the words Indian quick-commerce retailers print on product labels — not generic, Western, or textbook category names. Prefer the term on a Blinkit/Zepto/BigBasket pack over the polite English word. Examples: "dishwash gel" or "dish wash bar" not "dishwashing liquid"; "chopping board" not "cutting board"; "refined oil" or "sunflower oil" not "cooking oil"; "dustbin" not "trash bin"; "detergent powder" or "detergent liquid" not "laundry detergent".
- Write needs as a shopper would search on an Indian quick-commerce app — simple, common label words, one to three words when needed.
- expected_tiles: required on every need, 1 to 3 tiles from the valid list above where the product lives.
- quantity_reasoning: express only the logic for why one (or a few) is needed — never state a specific size, volume, weight, count, or pack detail. Pack size is unknown at this stage. Good: "One bucket covers most household cleaning tasks", "Enough towels to rotate while one dries". Bad: "One 5-liter bucket", "Two to three medium towels", "One set (fitted sheet + pillowcase)".
- Use world knowledge: moving in → bedsheet, pillow, towel, bucket, mug, mop, detergent powder, dustbin, dishwash gel; new cat → cat food, cat litter, litter tray, pet bowl, scoop.
- Gifting situations (situation_id festival_gifting, or when prompt_context describes buying gifts): name the gift-appropriate PRODUCT, not a stacked gift-form phrase. Use at most one qualifier when it disambiguates — never pile presentation words. Wrong: "bath and body hamper", "electronics gift set", "beauty cosmetics set", "chocolate gift box". Right: "gift chocolate", "dry fruits", "perfume", "earphones", "soft toy". Presentation (hamper, set, box, kit) is the retailer's job — the need must be findable as words on a product label in the catalogue. Prefer products people actually give (sweets, dry fruits, perfume, jewellery, gadgets, toys, books, candles, plants) over invented gift packaging names.
- For gifting, spread needs across categories — not only food. Draw across sweets and chocolates, dry fruits, perfume and bath products, beauty and cosmetics, jewellery, electronics, home décor, toys and books, stationery, e-gift vouchers, plants and flowers. The catalogue supports Bath & Body, E-Gifts Store, Sweets & Chocolates, Home & Lifestyle, Jewellery Store, Electronics, Toy Store, Book Store, and more.
- Needs must be generic nouns — never brand names or specific SKUs.
- Do not suggest Health & Pharma or Baby Care products for auto-composition — note them in unavailable or omit.
- Return raw JSON only. Do not wrap the response in markdown code fences. Do not use ```json or ``` blocks. No prose before or after the JSON."""


def _allowed_tiles(situation_id: str, tile_categories: list[str]) -> list[str]:
    vetoed = IMPLAUSIBLE_TILES.get(situation_id, frozenset())
    return [tile for tile in tile_categories if tile not in vetoed]


def _ensure_cache_dir() -> None:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _read_cache_file() -> dict[str, Any]:
    _ensure_cache_dir()
    if not _CACHE_PATH.exists():
        return {}
    try:
        with _CACHE_PATH.open(encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        logger.warning("LLM cache: could not read %s", _CACHE_PATH)
        return {}


def _write_cache_file(data: dict[str, Any]) -> None:
    _ensure_cache_dir()
    with _CACHE_PATH.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def _make_cache_key(func: str, **parts: Any) -> str:
    payload: dict[str, Any] = {"fn": func}
    for key, value in sorted(parts.items()):
        if value is None:
            continue
        payload[key] = value
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _resolve_cart_sku_ids(
    cart_items: list[dict],
    cart_skus: list[str] | None,
) -> list[str]:
    if cart_skus is not None:
        return sorted(cart_skus)
    skus = [
        item["sku"]
        for item in cart_items
        if isinstance(item, dict) and isinstance(item.get("sku"), str)
    ]
    if skus:
        return sorted(skus)
    return sorted(
        f"{item.get('name', '')}:{item.get('category', '')}"
        for item in cart_items
        if isinstance(item, dict)
    )


def _cache_get(key: str) -> dict | None:
    entry = _read_cache_file().get(key)
    return entry if isinstance(entry, dict) else None


def _cache_put(key: str, value: dict) -> None:
    cache = _read_cache_file()
    cache[key] = value
    _write_cache_file(cache)


def _env(name: str) -> str | None:
    value = os.getenv(name)
    return value.strip() if value else None


def _client() -> OpenAI | None:
    api_key = _env("GROQ_API_KEY")
    if not api_key:
        logger.error("GROQ_API_KEY not set")
        return None
    return OpenAI(api_key=api_key, base_url=GROQ_BASE_URL)


def _model() -> str | None:
    return _env("GROQ_MODEL")


def _clamp_score(value: Any) -> float | None:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return None
    return max(0.0, min(1.0, score))


def _extract_json(text: str) -> str | None:
    stripped = text.strip()
    if not stripped:
        return None
    if stripped.startswith("```"):
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", stripped, re.IGNORECASE)
        if match is None:
            return None
        return match.group(1).strip()
    return stripped


def _word_count(label: str) -> int:
    return len(label.split())


def _parse_situation_response(raw: str) -> dict | None:
    extracted = _extract_json(raw)
    if extracted is None:
        logger.warning("Situation reader: failed to extract JSON")
        return None

    try:
        data = json.loads(extracted)
    except json.JSONDecodeError:
        logger.warning("Situation reader: invalid JSON")
        return None

    if not isinstance(data, dict):
        return None

    confidence = _clamp_score(data.get("confidence"))
    candidates = data.get("candidates")
    if confidence is None or not isinstance(candidates, list) or len(candidates) != 4:
        logger.warning("Situation reader: schema validation failed")
        return None

    parsed_candidates: list[dict] = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            return None
        cand_id = candidate.get("id")
        label = candidate.get("label")
        reasoning = candidate.get("reasoning")
        score = _clamp_score(candidate.get("score"))
        if (
            not isinstance(cand_id, str)
            or not isinstance(label, str)
            or not isinstance(reasoning, str)
            or score is None
        ):
            return None
        if _word_count(label.strip()) > 4:
            logger.warning("Situation reader: label exceeds 4 words: %r", label)
            return None
        parsed_candidates.append(
            {
                "id": cand_id.strip(),
                "label": label.strip(),
                "reasoning": reasoning.strip(),
                "score": score,
            }
        )

    scores = [c["score"] for c in parsed_candidates]
    if scores != sorted(scores, reverse=True):
        logger.warning("Situation reader: candidates not in descending score order")
        return None

    if abs(confidence - parsed_candidates[0]["score"]) > 1e-9:
        logger.warning("Situation reader: confidence != top candidate score")
        return None

    return {"confidence": confidence, "candidates": parsed_candidates}


def _parse_expected_tiles(raw: Any, valid_tiles: frozenset[str] | None = None) -> list[str]:
    allowed = valid_tiles or _VALID_TILES_SET
    if raw is None:
        return []
    if not isinstance(raw, list):
        return []
    tiles: list[str] = []
    for entry in raw:
        if not isinstance(entry, str):
            continue
        tile = entry.strip()
        if tile in allowed and tile not in tiles:
            tiles.append(tile)
        if len(tiles) == 3:
            break
    return tiles


def _parse_needs_response(
    raw: str, valid_tiles: frozenset[str] | None = None
) -> dict | None:
    extracted = _extract_json(raw)
    if extracted is None:
        logger.warning("Need planner: failed to extract JSON")
        return None

    try:
        data = json.loads(extracted)
    except json.JSONDecodeError:
        logger.warning("Need planner: invalid JSON")
        return None

    if not isinstance(data, dict):
        return None

    situation_label = data.get("situation_label")
    needs = data.get("needs")
    unavailable = data.get("unavailable", [])
    if not isinstance(situation_label, str) or not isinstance(needs, list):
        logger.warning("Need planner: schema validation failed")
        return None
    if not isinstance(unavailable, list):
        return None

    parsed_needs: list[dict] = []
    for need in needs:
        if not isinstance(need, dict):
            return None
        role = need.get("role")
        need_text = need.get("need")
        quantity_reasoning = need.get("quantity_reasoning")
        if (
            not isinstance(role, str)
            or not isinstance(need_text, str)
            or not isinstance(quantity_reasoning, str)
        ):
            return None
        parsed_needs.append(
            {
                "role": role.strip(),
                "need": need_text.strip(),
                "quantity_reasoning": quantity_reasoning.strip(),
                "expected_tiles": _parse_expected_tiles(
                    need.get("expected_tiles"), valid_tiles
                ),
            }
        )

    parsed_unavailable = []
    for item in unavailable:
        if not isinstance(item, str):
            return None
        parsed_unavailable.append(item.strip())

    return {
        "situation_label": situation_label.strip(),
        "needs": parsed_needs,
        "unavailable": parsed_unavailable,
    }


def _chat(system: str, user_payload: dict) -> str | None:
    client = _client()
    model = _model()
    if client is None or not model:
        return None

    started = time.perf_counter()
    response = None
    try:
        for attempt in range(5):
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": json.dumps(user_payload)},
                    ],
                    temperature=0,
                    seed=42,
                )
                break
            except RateLimitError:
                print(
                    f"Rate limit hit on attempt {attempt + 1}/5, "
                    f"sleeping {2 ** attempt}s before retry"
                )
                if attempt == 4:
                    raise
                time.sleep(2**attempt)
    except RateLimitError:
        raise
    except Exception:
        logger.exception("LLM API error")
        return None
    finally:
        elapsed_ms = (time.perf_counter() - started) * 1000
        logger.info("LLM call completed in %.0f ms (model=%s)", elapsed_ms, model)

    if response.usage is not None:
        print(
            f"LLM usage: prompt_tokens={response.usage.prompt_tokens}, "
            f"completion_tokens={response.usage.completion_tokens}, "
            f"total_tokens={response.usage.total_tokens}"
        )

    if not response.choices:
        logger.error("LLM returned no choices")
        return None

    content = response.choices[0].message.content
    if not content:
        logger.error("LLM returned empty content")
        return None

    logger.debug("Raw LLM response: %s", content)
    return content


def read_situation(
    cart_items: list[dict],
    delivery_location: str,
    location_unfamiliar: bool,
    today: str,
    household_id: str | None = None,
    cart_skus: list[str] | None = None,
    free_text: str | None = None,
) -> dict | None:
    """Call 1 — infer up to four plausible situations from cart context."""
    key = _make_cache_key(
        "read_situation",
        household_id=household_id,
        cart_skus=_resolve_cart_sku_ids(cart_items, cart_skus),
        free_text=free_text,
    )
    if CACHE_ENABLED:
        cached = _cache_get(key)
        if cached is not None:
            print(f"cache hit: {key}")
            return cached
        print(f"cache miss: {key}")

    payload = {
        "cart_items": cart_items,
        "delivery_location": delivery_location,
        "location_unfamiliar": location_unfamiliar,
        "today": today,
    }
    raw = _chat(SITUATION_READER_SYSTEM, payload)
    if raw is None:
        return None
    result = _parse_situation_response(raw)
    if CACHE_ENABLED and result is not None:
        _cache_put(key, result)
    return result


def plan_needs(
    situation_id: str,
    situation_label: str,
    prompt_context: str,
    tile_categories: list[str],
    household_id: str | None = None,
    free_text: str | None = None,
) -> dict | None:
    """Call 2 — decompose a confirmed situation into role-grouped abstract needs."""
    key = _make_cache_key(
        "plan_needs",
        household_id=household_id,
        situation_id=situation_id,
        free_text=free_text,
    )
    if CACHE_ENABLED:
        cached = _cache_get(key)
        if cached is not None:
            print(f"cache hit: {key}")
            return cached
        print(f"cache miss: {key}")

    allowed = _allowed_tiles(situation_id, tile_categories)
    payload = {
        "situation_id": situation_id,
        "situation_label": situation_label,
        "prompt_context": prompt_context,
        "tile_categories": allowed,
    }
    system = _need_planner_system(allowed)
    raw = _chat(system, payload)
    if raw is None:
        return None
    result = _parse_needs_response(raw, frozenset(allowed))
    if CACHE_ENABLED and result is not None:
        _cache_put(key, result)
    return result


def is_unambiguous(response: dict) -> bool:
    """True when top score >= 0.75 and at least 0.3 above second."""
    top = response["candidates"][0]["score"]
    second = response["candidates"][1]["score"]
    return top >= 0.75 and (top - second) >= 0.3
