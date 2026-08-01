"""FastAPI HTTP layer for Blinkit Sense."""

from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from openai import RateLimitError
from pydantic import BaseModel, Field

from engine import apply_household_filter, resolve_needs
from llm import plan_needs, read_situation
from phases.phase_2_data.loader import (
    address_to_catalog_location,
    all_tiles,
    catalog_by_id,
    is_location_unfamiliar,
    load_catalog,
    load_households,
    load_json,
    load_scenarios,
)

load_dotenv()

app = FastAPI(title="Blinkit Sense API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_origin_regex=r"https?://[\w-]+\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class CartLine(BaseModel):
    sku_id: str
    qty: int = Field(default=1, ge=1)


class SituationsRequest(BaseModel):
    household_id: str
    cart: list[CartLine]
    location: str
    today: str


class NeedsRequest(BaseModel):
    household_id: str
    situation_id: str
    cart: list[CartLine]
    location: str
    situation_label: str | None = None
    prompt_context: str | None = None


def _llm_configured() -> bool:
    return bool(os.getenv("GROQ_API_KEY", "").strip())


def _llm_unavailable() -> HTTPException:
    if not _llm_configured():
        return HTTPException(
            status_code=503,
            detail={
                "error": "llm_unconfigured",
                "message": "GROQ_API_KEY is not set in the environment.",
            },
        )
    return HTTPException(
        status_code=503,
        detail={
            "error": "llm_unavailable",
            "message": "The LLM call failed or returned an invalid response.",
        },
    )


def _llm_rate_limited() -> HTTPException:
    return HTTPException(
        status_code=503,
        detail={
            "error": "llm_rate_limited",
            "message": "The LLM provider rate limit was exceeded. Try again shortly.",
        },
    )


def _household_by_id(household_id: str) -> dict[str, Any]:
    for household in load_households():
        if household["id"] == household_id:
            return household
    raise HTTPException(
        status_code=404,
        detail={
            "error": "household_not_found",
            "message": f"No household with id {household_id!r}.",
        },
    )


def _scenario_by_id(situation_id: str) -> dict[str, Any]:
    for scenario in load_scenarios():
        if scenario["id"] == situation_id:
            return scenario
    raise HTTPException(
        status_code=404,
        detail={
            "error": "situation_not_found",
            "message": f"No situation with id {situation_id!r}.",
        },
    )


def _resolve_scenario(body: NeedsRequest) -> dict[str, Any]:
    if body.situation_id == "custom":
        label = (body.situation_label or "Custom").strip()
        context = body.prompt_context or f"The customer described their situation as: {label}"
        return {
            "id": "custom",
            "chip_label": label,
            "prompt_context": context,
        }
    scenario = _scenario_by_id(body.situation_id)
    if body.situation_label:
        scenario = {**scenario, "chip_label": body.situation_label}
    if body.prompt_context:
        scenario = {**scenario, "prompt_context": body.prompt_context}
    return scenario


def _household_with_request_context(
    household: dict[str, Any],
    cart: list[CartLine],
    location: str,
) -> dict[str, Any]:
    return {
        **household,
        "current_cart": [line.sku_id for line in cart],
        "current_address": location,
    }


def _cart_items(cart: list[CartLine]) -> tuple[list[dict[str, str]], list[str]]:
    by_id = catalog_by_id()
    items: list[dict[str, str]] = []
    sku_ids: list[str] = []
    for line in cart:
        product = by_id.get(line.sku_id)
        if product is None:
            continue
        items.append({"name": product["name"], "category": product["category"]})
        sku_ids.append(line.sku_id)
    return items, sorted(sku_ids)


@app.exception_handler(Exception)
async def unhandled_exception_handler(_request: Any, exc: Exception) -> JSONResponse:
    if isinstance(exc, HTTPException):
        raise exc
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_error",
            "message": "An unexpected error occurred.",
        },
    )


@app.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}


@app.get("/categories")
def categories() -> dict[str, Any]:
    return load_json("categories.json")


@app.get("/households")
def households() -> dict[str, Any]:
    return load_json("households.json")


@app.get("/catalog")
def catalog(
    category: str | None = Query(default=None),
    q: str | None = Query(default=None),
    location: str | None = Query(default=None),
    sku_id: str | None = Query(default=None),
) -> list[dict[str, Any]]:
    items = load_catalog()
    if sku_id:
        items = [item for item in items if item.get("id") == sku_id]
    if category:
        items = [item for item in items if item.get("category") == category]
    if location:
        items = [item for item in items if location in item.get("available_in", [])]
    if q:
        needle = q.casefold()
        items = [item for item in items if needle in item.get("name", "").casefold()]
    return items[:50]


@app.post("/situations")
def situations(body: SituationsRequest) -> dict[str, Any]:
    if not _llm_configured():
        raise _llm_unavailable()

    household = _household_by_id(body.household_id)
    ctx = _household_with_request_context(household, body.cart, body.location)
    cart_items, cart_skus = _cart_items(body.cart)

    try:
        result = read_situation(
            cart_items=cart_items,
            delivery_location=body.location,
            location_unfamiliar=is_location_unfamiliar(ctx),
            today=body.today,
            household_id=body.household_id,
            cart_skus=cart_skus,
        )
    except RateLimitError:
        raise _llm_rate_limited() from None

    if result is None:
        raise _llm_unavailable()
    return result


@app.post("/needs")
def needs(body: NeedsRequest) -> dict[str, Any]:
    if not _llm_configured():
        raise _llm_unavailable()

    household = _household_by_id(body.household_id)
    scenario = _resolve_scenario(body)
    ctx = _household_with_request_context(household, body.cart, body.location)
    catalog_location = address_to_catalog_location(body.location)

    try:
        needs_result = plan_needs(
            situation_id=scenario["id"],
            situation_label=scenario["chip_label"],
            prompt_context=scenario["prompt_context"],
            tile_categories=all_tiles(),
            household_id=body.household_id,
        )
    except RateLimitError:
        raise _llm_rate_limited() from None

    if needs_result is None:
        raise _llm_unavailable()

    resolved = resolve_needs(
        needs_result["needs"],
        catalog_location,
        situation_id=scenario["id"],
    )
    filtered = apply_household_filter(resolved, ctx)
    return {
        "situation_label": needs_result.get(
            "situation_label", scenario["chip_label"]
        ),
        "unavailable": needs_result.get("unavailable", []),
        **filtered,
    }
