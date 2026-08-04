#!/usr/bin/env python3
"""Blinkit Sense — Phase 8 Streamlit UI (checkout-time household intelligence)."""

from __future__ import annotations

import subprocess
import sys
from datetime import date
from pathlib import Path

import streamlit as st

from engine import (
    FEE_SMALL_CART,
    GAP_MESSAGE,
    apply_household_filter,
    fee_breakdown,
    resolve_needs,
)
from llm import is_unambiguous, plan_needs, read_situation
from phases.phase_2_data.loader import (
    address_to_catalog_location,
    all_tiles,
    catalog_by_id,
    confidence_threshold,
    is_location_unfamiliar,
    load_catalog,
    load_households,
    load_scenarios,
)

ROOT = Path(__file__).resolve().parent

STRIP_CSS = """
<style>
.cart-panel {
    background: #ffffff;
    border: 1px solid #e6e6e6;
    border-radius: 8px;
    padding: 1.25rem 1.5rem;
}
.strip-panel {
    background: #f7f4eb;
    border: 1px solid #e8dfc8;
    border-radius: 8px;
    padding: 1.5rem;
    margin-top: 1.25rem;
}
.strip-heading {
    font-size: 1.05rem;
    font-weight: 600;
    color: #2b2b2b;
    margin-bottom: 0.75rem;
}
.role-heading {
    font-size: 1.25rem;
    font-weight: 700;
    color: #111111;
    margin-top: 1.15rem;
    margin-bottom: 0.35rem;
    letter-spacing: -0.01em;
}
.need-line {
    font-size: 0.95rem;
    color: #333333;
    margin-left: 0.25rem;
}
.qty-line {
    font-size: 0.82rem;
    color: #666666;
    margin-left: 0.25rem;
    margin-bottom: 0.5rem;
}
.new-category-line {
    font-size: 1.12rem;
    font-weight: 700;
    color: #0d5c3d;
    margin: 1.1rem 0 0.5rem 0;
    line-height: 1.4;
}
.gap-line {
    font-size: 0.92rem;
    color: #7c2d12;
    margin: 0.45rem 0;
}
.meta-line {
    font-size: 0.9rem;
    color: #555555;
    margin: 0.35rem 0;
}
.unfamiliar-flag {
    color: #9a3412;
    font-weight: 600;
}
</style>
"""


def _init_session() -> None:
    st.session_state.setdefault("dismissed_households", set())
    st.session_state.setdefault("situation_by_household", {})
    st.session_state.setdefault("composed_by_household", {})
    st.session_state.setdefault("item_selection", {})
    st.session_state.setdefault("show_chip_picker", {})
    st.session_state.setdefault("cart_skus_by_household", {})


def _households_by_id() -> dict[str, dict]:
    return {household["id"]: household for household in load_households()}


def _scenarios_by_id() -> dict[str, dict]:
    return {scenario["id"]: scenario for scenario in load_scenarios()}


def _effective_cart_skus(household: dict) -> list[str]:
    household_id = household["id"]
    if household_id not in st.session_state.cart_skus_by_household:
        st.session_state.cart_skus_by_household[household_id] = list(
            household.get("current_cart", [])
        )
    return st.session_state.cart_skus_by_household[household_id]


def _household_with_cart(household: dict) -> dict:
    return {**household, "current_cart": _effective_cart_skus(household)}


def _cart_lines(household: dict) -> list[dict]:
    by_id = catalog_by_id()
    lines = []
    for sku in _effective_cart_skus(household):
        product = by_id.get(sku)
        if product is None:
            continue
        lines.append(
            {
                "sku": sku,
                "name": product["name"],
                "price": product["price"],
                "category": product["category"],
            }
        )
    return lines


def _cart_subtotal(household: dict) -> int:
    return sum(line["price"] for line in _cart_lines(household))


def _cart_items_for_household(household: dict) -> tuple[list[dict], list[str]]:
    by_id = catalog_by_id()
    items: list[dict] = []
    sku_ids: list[str] = []
    for sku in _effective_cart_skus(household):
        product = by_id.get(sku)
        if product is None:
            continue
        items.append({"name": product["name"], "category": product["category"]})
        sku_ids.append(sku)
    return items, sorted(sku_ids)


def _catalog_fetched_at() -> str:
    catalog = load_catalog()
    if not catalog:
        return "unknown"
    return catalog[0].get("fetched_at", "unknown")


def _scenario_for_candidate(candidate: dict) -> dict:
    scenarios = _scenarios_by_id()
    if candidate["id"] in scenarios:
        return scenarios[candidate["id"]]
    return {
        "id": candidate["id"],
        "chip_label": candidate["label"],
        "prompt_context": (
            f"The customer confirmed: {candidate['label']}. "
            f"{candidate.get('reasoning', '')}"
        ),
    }


def _stocking_scenario() -> dict:
    scenarios = _scenarios_by_id()
    if "stocking" in scenarios:
        return scenarios["stocking"]
    return {
        "id": "stocking",
        "chip_label": "Just stocking up",
        "prompt_context": (
            "The customer is doing a routine restock with no special occasion. "
            "Suggest a mix of household staples they may be running low on, plus "
            "one or two adjacent products that complement what's already in the cart "
            "but come from a category they haven't bought from."
        ),
    }


def _clear_composed(household_id: str) -> None:
    st.session_state.composed_by_household.pop(household_id, None)
    prefix = f"{household_id}:"
    for key in list(st.session_state.item_selection):
        if key.startswith(prefix):
            st.session_state.item_selection.pop(key, None)


def _run_confirmation(household: dict, scenario: dict) -> dict | None:
    ctx = _household_with_cart(household)
    location = address_to_catalog_location(household["current_address"])
    cart_items, cart_skus = _cart_items_for_household(household)
    with st.spinner("Planning what this situation needs..."):
        needs_result = plan_needs(
            situation_id=scenario["id"],
            situation_label=scenario["chip_label"],
            prompt_context=scenario["prompt_context"],
            tile_categories=all_tiles(),
            household_id=household["id"],
            cart_items=cart_items,
            cart_skus=cart_skus,
        )
    if needs_result is None:
        return None

    resolved = resolve_needs(
        needs_result["needs"],
        location,
        situation_id=scenario["id"],
    )
    filtered = apply_household_filter(resolved, ctx)
    filtered["situation_label"] = needs_result.get(
        "situation_label", scenario["chip_label"]
    )
    filtered["needs_result"] = needs_result
    return filtered


def _ensure_situation(household: dict) -> dict | None:
    household_id = household["id"]
    if household_id in st.session_state.dismissed_households:
        return None
    if household_id in st.session_state.situation_by_household:
        return st.session_state.situation_by_household[household_id]

    cart_items, cart_skus = _cart_items_for_household(household)
    if not cart_items:
        return None

    with st.spinner("Reading your cart..."):
        result = read_situation(
            cart_items=cart_items,
            delivery_location=household["current_address"],
            location_unfamiliar=is_location_unfamiliar(household),
            today=date.today().isoformat(),
            household_id=household_id,
            cart_skus=cart_skus,
        )
    st.session_state.situation_by_household[household_id] = result
    return result


def _add_skus_to_cart(household_id: str, sku_ids: list[str]) -> None:
    cart = st.session_state.cart_skus_by_household.setdefault(household_id, [])
    for sku in sku_ids:
        if sku not in cart:
            cart.append(sku)


def _render_cart(household: dict) -> int:
    st.markdown('<div class="cart-panel">', unsafe_allow_html=True)
    st.subheader("Your cart")
    cart_lines = _cart_lines(household)
    if not cart_lines:
        st.write("Cart is empty.")
    else:
        for line in cart_lines:
            st.write(f"**{line['name']}**  \n₹{line['price']} · {line['category']}")

    subtotal = _cart_subtotal(household)
    fees = fee_breakdown(subtotal)
    st.markdown("---")
    st.write(f"Delivery · ₹{fees['delivery']}")
    st.write(f"Handling · ₹{fees['handling']}")
    if fees["small_cart"]:
        st.write(f"Small-cart surcharge · ₹{fees['small_cart']}")
    st.write(f"**Cart total · ₹{subtotal + fees['total_fees']}**")
    st.markdown("</div>", unsafe_allow_html=True)
    return subtotal


def _confirm_scenario(household: dict, scenario: dict) -> None:
    composed = _run_confirmation(household, scenario)
    if composed is None:
        st.error("Could not plan needs for this situation.")
    else:
        st.session_state.composed_by_household[household["id"]] = composed
        st.session_state.show_chip_picker[household["id"]] = False
    st.rerun()


def _render_chip_row(household: dict, situation: dict) -> None:
    top = situation["candidates"][0]
    st.markdown(
        f'<p class="strip-heading">We noticed: {top["reasoning"]}</p>',
        unsafe_allow_html=True,
    )

    cols = st.columns(4)
    for index, candidate in enumerate(situation["candidates"]):
        with cols[index % 4]:
            if st.button(
                candidate["label"],
                key=f"chip_{household['id']}_{index}",
                use_container_width=True,
            ):
                _confirm_scenario(household, _scenario_for_candidate(candidate))

    tell_us = st.text_input(
        "Tell us",
        placeholder="Describe your situation in a few words",
        key=f"tell_us_{household['id']}",
    )
    action_cols = st.columns(3)
    with action_cols[0]:
        if st.button("Submit situation", key=f"tell_us_submit_{household['id']}"):
            text = tell_us.strip()
            if not text:
                st.warning("Enter a short description first.")
            else:
                _confirm_scenario(
                    household,
                    {
                        "id": "custom",
                        "chip_label": text,
                        "prompt_context": f"The customer described their situation as: {text}",
                    },
                )
    with action_cols[1]:
        if st.button("Just stocking up", key=f"stocking_{household['id']}"):
            _confirm_scenario(household, _stocking_scenario())
    with action_cols[2]:
        if st.button("Dismiss", key=f"dismiss_{household['id']}"):
            st.session_state.dismissed_households.add(household["id"])
            _clear_composed(household["id"])
            st.rerun()


def _render_unambiguous_confirm(household: dict, situation: dict) -> None:
    top = situation["candidates"][0]
    st.markdown(
        f'<p class="strip-heading">{top["label"]}: {top["reasoning"]}</p>',
        unsafe_allow_html=True,
    )
    if st.button(
        f'Add suggestions for "{top["label"]}"',
        key=f"unamb_confirm_{household['id']}",
        type="primary",
    ):
        _confirm_scenario(household, _scenario_for_candidate(top))
    if st.button("Dismiss", key=f"unamb_dismiss_{household['id']}"):
        st.session_state.dismissed_households.add(household["id"])
        _clear_composed(household["id"])
        st.rerun()


def _render_composed(household: dict, composed: dict, cart_subtotal: int) -> None:
    household_id = household["id"]
    items = composed["items"]

    if len(items) < 2:
        st.markdown(
            '<p class="strip-heading">Nothing to add for this one — you\'re set.</p>',
            unsafe_allow_html=True,
        )
        if composed.get("gaps"):
            for gap in composed["gaps"]:
                need = gap.get("need", "Item")
                message = gap.get("gap_message", GAP_MESSAGE)
                st.markdown(
                    f'<p class="gap-line">{need}: {message}</p>',
                    unsafe_allow_html=True,
                )
        return

    st.markdown(
        f'<p class="strip-heading">{composed["situation_label"]}</p>',
        unsafe_allow_html=True,
    )

    needs_by_text = {
        need.get("need"): need
        for need in composed.get("needs_result", {}).get("needs", [])
    }

    by_role: dict[str, list[dict]] = {}
    for item in items:
        by_role.setdefault(item.get("role", "Other"), []).append(item)

    by_id = catalog_by_id()
    for role, role_items in by_role.items():
        st.markdown(f'<p class="role-heading">{role}</p>', unsafe_allow_html=True)
        for item in role_items:
            need_meta = needs_by_text.get(item.get("need"), item)
            qty = need_meta.get(
                "quantity_reasoning", item.get("quantity_reasoning", "")
            )
            unit = by_id.get(item["resolved_sku"], {}).get("unit", "")
            unit_suffix = f" · {unit}" if unit else ""
            st.markdown(
                f'<p class="need-line">{item["need"]} · {item["resolved_name"]}'
                f"{unit_suffix} · ₹{item['price']}</p>",
                unsafe_allow_html=True,
            )
            if qty:
                st.markdown(f'<p class="qty-line">{qty}</p>', unsafe_allow_html=True)

    st.markdown("---")
    selected: list[dict] = []
    for item in items:
        sel_key = f"{household_id}:{item['resolved_sku']}"
        default = st.session_state.item_selection.get(sel_key, True)
        unit = by_id.get(item["resolved_sku"], {}).get("unit", "")
        unit_suffix = f" · {unit}" if unit else ""
        checked = st.checkbox(
            f"{item['resolved_name']}{unit_suffix} · ₹{item['price']}",
            value=default,
            key=f"toggle_{sel_key}",
        )
        st.session_state.item_selection[sel_key] = checked
        if checked:
            selected.append(item)

    selected_total = sum(item["price"] for item in selected)
    if st.button(
        f"Add all {len(selected)} · ₹{selected_total}",
        key=f"add_all_{household_id}",
        type="primary",
        disabled=len(selected) == 0,
    ):
        _add_skus_to_cart(household_id, [item["resolved_sku"] for item in selected])
        st.session_state.dismissed_households.add(household_id)
        _clear_composed(household_id)
        st.rerun()

    new_tiles = sorted(
        {item["category"] for item in items if item.get("flag") == "new_category"}
    )
    if new_tiles:
        st.markdown(
            f'<p class="new-category-line">New for your household: {", ".join(new_tiles)}</p>',
            unsafe_allow_html=True,
        )

    gaps = composed.get("gaps") or []
    for gap in gaps:
        need = gap.get("need", "Item")
        message = gap.get("gap_message", GAP_MESSAGE)
        st.markdown(
            f'<p class="gap-line">{need}: {message}</p>',
            unsafe_allow_html=True,
        )

    unavailable = composed.get("needs_result", {}).get("unavailable") or []
    for note in unavailable:
        st.markdown(f'<p class="gap-line">{note}</p>', unsafe_allow_html=True)

    if composed.get("sensitive_guidance"):
        for line in composed["sensitive_guidance"]:
            st.markdown(f'<p class="meta-line">{line}</p>', unsafe_allow_html=True)

    combined = cart_subtotal + selected_total
    threshold_fee = fee_breakdown(combined)
    gap = threshold_fee["gap_to_threshold"]
    if gap:
        st.markdown(
            f'<p class="meta-line">Add ₹{gap} more to waive the ₹{FEE_SMALL_CART} '
            f"small-cart charge.</p>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<p class="meta-line">Your cart clears the ₹99 small-cart threshold.</p>',
            unsafe_allow_html=True,
        )

    action_cols = st.columns(2)
    with action_cols[0]:
        if st.button("Show other options", key=f"other_{household_id}"):
            st.session_state.show_chip_picker[household_id] = True
            _clear_composed(household_id)
            st.rerun()
    with action_cols[1]:
        if st.button("No, I'm done", key=f"done_{household_id}"):
            st.session_state.dismissed_households.add(household_id)
            _clear_composed(household_id)
            st.rerun()


def _render_strip(household: dict, cart_subtotal: int) -> None:
    household_id = household["id"]
    if household_id in st.session_state.dismissed_households:
        return

    situation = _ensure_situation(household)
    if not situation:
        return

    threshold = confidence_threshold(household["orders_per_month"])
    if situation.get("confidence", 0) < threshold:
        return

    st.markdown('<div class="strip-panel">', unsafe_allow_html=True)

    if household_id in st.session_state.composed_by_household:
        _render_composed(
            household,
            st.session_state.composed_by_household[household_id],
            cart_subtotal,
        )
    elif is_unambiguous(situation):
        _render_unambiguous_confirm(household, situation)
    else:
        _render_chip_row(household, situation)

    st.markdown("</div>", unsafe_allow_html=True)


def _render_sidebar() -> None:
    st.sidebar.header("Catalogue")
    st.sidebar.caption(f"Last fetched: {_catalog_fetched_at()}")
    if st.sidebar.button("Refresh catalogue"):
        with st.spinner("Rebuilding catalogue..."):
            result = subprocess.run(
                [sys.executable, "-m", "phases.phase_1_scraper.build_catalog"],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
        if result.returncode == 0:
            st.sidebar.success("Catalogue refreshed.")
            st.session_state.situation_by_household.clear()
            st.session_state.composed_by_household.clear()
            st.session_state.cart_skus_by_household.clear()
        else:
            st.sidebar.error("Catalogue refresh failed.")
            if result.stderr:
                st.sidebar.code(result.stderr[:500])


def main() -> None:
    st.set_page_config(page_title="Blinkit Sense", layout="wide")
    st.markdown(STRIP_CSS, unsafe_allow_html=True)
    _init_session()
    _render_sidebar()

    st.title("Blinkit Sense")
    st.caption("Checkout-time household intelligence")

    households = load_households()
    labels = [f"{household['name']} ({household['id']})" for household in households]
    ids = [household["id"] for household in households]

    selected_label = st.selectbox("Household", labels, key="household_select")
    selected_id = ids[labels.index(selected_label)]
    household = _households_by_id()[selected_id]

    unfamiliar = is_location_unfamiliar(household)
    location_text = household["current_address"]
    if unfamiliar:
        st.markdown(
            f'Delivery to **{location_text}** '
            f'<span class="unfamiliar-flag">(new address)</span>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(f"Delivery to **{location_text}**")

    left_col, _right_col = st.columns([2, 3])
    with left_col:
        cart_subtotal = _render_cart(household)
        _render_strip(household, cart_subtotal)


if __name__ == "__main__":
    main()
