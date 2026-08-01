#!/usr/bin/env python3
"""Blinkit Sense — checkout-time household intelligence (Streamlit UI)."""

from __future__ import annotations

import subprocess
import sys
from datetime import date
from pathlib import Path

import streamlit as st

from engine import apply_household_filter, fee_breakdown, resolve_needs
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
    font-size: 1.2rem;
    font-weight: 700;
    color: #111111;
    margin-top: 1.1rem;
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
    font-size: 1.08rem;
    font-weight: 700;
    color: #0d5c3d;
    margin: 1rem 0 0.5rem 0;
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


def _households_by_id() -> dict[str, dict]:
    return {household["id"]: household for household in load_households()}


def _scenarios_by_id() -> dict[str, dict]:
    return {scenario["id"]: scenario for scenario in load_scenarios()}


def _cart_lines(household: dict) -> list[dict]:
    by_id = catalog_by_id()
    lines = []
    for sku in household.get("current_cart", []):
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
        "prompt_context": f"The customer confirmed: {candidate['label']}. {candidate.get('reasoning', '')}",
    }


def _clear_composed(household_id: str) -> None:
    st.session_state.composed_by_household.pop(household_id, None)
    keys_to_drop = [key for key in st.session_state.item_selection if key.startswith(f"{household_id}:")]
    for key in keys_to_drop:
        st.session_state.item_selection.pop(key, None)


def _run_confirmation(
    household: dict,
    scenario: dict,
) -> dict | None:
    tiles = all_tiles()
    location = address_to_catalog_location(household["current_address"])
    with st.spinner("Planning what this situation needs..."):
        needs_result = plan_needs(
            situation_id=scenario["id"],
            situation_label=scenario["chip_label"],
            prompt_context=scenario["prompt_context"],
            tile_categories=tiles,
        )
    if needs_result is None:
        return None

    resolved = resolve_needs(
        needs_result["needs"],
        location,
        situation_id=scenario["id"],
    )
    filtered = apply_household_filter(resolved, household)
    filtered["situation_label"] = needs_result.get(
        "situation_label", scenario["chip_label"]
    )
    filtered["needs_result"] = needs_result
    return filtered


def _ensure_situation(household: dict, cart_lines: list[dict]) -> dict | None:
    household_id = household["id"]
    if household_id in st.session_state.dismissed_households:
        return None
    if household_id in st.session_state.situation_by_household:
        return st.session_state.situation_by_household[household_id]

    cart_payload = [
        {"name": line["name"], "category": line["category"]} for line in cart_lines
    ]
    with st.spinner("Reading your cart..."):
        result = read_situation(
            cart_items=cart_payload,
            delivery_location=household["current_address"],
            location_unfamiliar=is_location_unfamiliar(household),
            today=date.today().isoformat(),
        )
    st.session_state.situation_by_household[household_id] = result
    return result


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


def _render_chip_row(
    household: dict,
    situation: dict,
    show_picker: bool,
) -> None:
    top = situation["candidates"][0]
    st.markdown(
        f'<p class="strip-heading">We noticed: {top["reasoning"]}</p>',
        unsafe_allow_html=True,
    )

    if not show_picker and household["id"] in st.session_state.composed_by_household:
        return

    cols = st.columns(4)
    for index, candidate in enumerate(situation["candidates"]):
        with cols[index % 4]:
            if st.button(
                candidate["label"],
                key=f"chip_{household['id']}_{index}",
                use_container_width=True,
            ):
                scenario = _scenario_for_candidate(candidate)
                composed = _run_confirmation(household, scenario)
                if composed is None:
                    st.error("Could not plan needs for this situation.")
                else:
                    st.session_state.composed_by_household[household["id"]] = composed
                    st.session_state.show_chip_picker[household["id"]] = False
                st.rerun()

    tell_us = st.text_input(
        "Tell us",
        placeholder="Describe your situation in a few words",
        key=f"tell_us_{household['id']}",
    )
    action_cols = st.columns(3)
    with action_cols[0]:
        if st.button("Submit", key=f"tell_us_submit_{household['id']}"):
            text = tell_us.strip()
            if text:
                scenario = {
                    "id": "custom",
                    "chip_label": text,
                    "prompt_context": f"The customer described their situation as: {text}",
                }
                composed = _run_confirmation(household, scenario)
                if composed is None:
                    st.error("Could not plan needs for this situation.")
                else:
                    st.session_state.composed_by_household[household["id"]] = composed
                    st.session_state.show_chip_picker[household["id"]] = False
                st.rerun()
    with action_cols[1]:
        if st.button("Just stocking up", key=f"stocking_{household['id']}"):
            st.session_state.dismissed_households.add(household["id"])
            _clear_composed(household["id"])
            st.rerun()
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
    if household["id"] not in st.session_state.composed_by_household:
        if st.button(
            f"Add suggestions for \"{top['label']}\"",
            key=f"unamb_confirm_{household['id']}",
            type="primary",
        ):
            scenario = _scenario_for_candidate(top)
            composed = _run_confirmation(household, scenario)
            if composed is None:
                st.error("Could not plan needs for this situation.")
            else:
                st.session_state.composed_by_household[household["id"]] = composed
            st.rerun()
        if st.button("Dismiss", key=f"unamb_dismiss_{household['id']}"):
            st.session_state.dismissed_households.add(household["id"])
            st.rerun()


def _render_composed(household: dict, composed: dict, cart_subtotal: int) -> None:
    household_id = household["id"]
    items = composed["items"]

    if len(items) < 3:
        st.markdown(
            '<p class="strip-heading">Nothing to add for this one — you\'re set.</p>',
            unsafe_allow_html=True,
        )
        return

    st.markdown(
        f'<p class="strip-heading">{composed["situation_label"]}</p>',
        unsafe_allow_html=True,
    )

    needs_by_sku = {
        need.get("need"): need
        for need in composed.get("needs_result", {}).get("needs", [])
    }

    by_role: dict[str, list[dict]] = {}
    for item in items:
        by_role.setdefault(item["role"], []).append(item)

    by_id = catalog_by_id()

    for role, role_items in by_role.items():
        st.markdown(f'<p class="role-heading">{role}</p>', unsafe_allow_html=True)
        for item in role_items:
            need_meta = needs_by_sku.get(item["need"], item)
            qty = need_meta.get("quantity_reasoning", item.get("quantity_reasoning", ""))
            unit = by_id.get(item["resolved_sku"], {}).get("unit", "")
            unit_suffix = f" · {unit}" if unit else ""
            st.markdown(
                f'<p class="need-line">{item["need"]} · {item["resolved_name"]}{unit_suffix} · ₹{item["price"]}</p>',
                unsafe_allow_html=True,
            )
            if qty:
                st.markdown(f'<p class="qty-line">{qty}</p>', unsafe_allow_html=True)

    st.markdown("---")
    for item in items:
        sel_key = f"{household_id}:{item['resolved_sku']}"
        default = st.session_state.item_selection.get(sel_key, True)
        unit = by_id.get(item["resolved_sku"], {}).get("unit", "")
        unit_suffix = f" · {unit}" if unit else ""
        st.session_state.item_selection[sel_key] = st.checkbox(
            f"{item['resolved_name']}{unit_suffix} · ₹{item['price']}",
            value=default,
            key=sel_key,
        )

    selected = [
        item
        for item in items
        if st.session_state.item_selection.get(f"{household_id}:{item['resolved_sku']}", True)
    ]
    selected_total = sum(item["price"] for item in selected)
    st.button(
        f"Add all {len(selected)} · ₹{selected_total}",
        key=f"add_all_{household_id}",
        type="primary",
    )

    new_tiles = sorted({item["category"] for item in items if item.get("flag") == "new_category"})
    if new_tiles:
        tile_text = ", ".join(new_tiles)
        st.markdown(
            f'<p class="new-category-line">New for your household: {tile_text}</p>',
            unsafe_allow_html=True,
        )

    combined = cart_subtotal + selected_total
    threshold_fee = fee_breakdown(combined)
    gap = threshold_fee["gap_to_threshold"]
    if gap:
        st.markdown(
            f'<p class="meta-line">Add ₹{gap} more to waive the ₹{threshold_fee["small_cart"] or 20} small-cart charge.</p>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<p class="meta-line">Your cart clears the ₹99 small-cart threshold.</p>',
            unsafe_allow_html=True,
        )

    if composed.get("sensitive_guidance"):
        for line in composed["sensitive_guidance"]:
            st.markdown(f'<p class="meta-line">{line}</p>', unsafe_allow_html=True)

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
    cart_lines = _cart_lines(household)
    situation = _ensure_situation(household, cart_lines)
    if not situation:
        return

    threshold = confidence_threshold(household["orders_per_month"])
    if situation.get("confidence", 0) < threshold:
        return

    st.markdown('<div class="strip-panel">', unsafe_allow_html=True)

    if household_id in st.session_state.composed_by_household:
        _render_composed(household, st.session_state.composed_by_household[household_id], cart_subtotal)
    elif is_unambiguous(situation):
        _render_unambiguous_confirm(household, situation)
    else:
        show_picker = st.session_state.show_chip_picker.get(household_id, True)
        _render_chip_row(household, situation, show_picker)

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

    previous_id = st.session_state.get("active_household_id")
    selected_label = st.selectbox("Household", labels, key="household_select")
    selected_id = ids[labels.index(selected_label)]
    household = _households_by_id()[selected_id]

    if previous_id != selected_id:
        st.session_state.active_household_id = selected_id

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

    cart_subtotal = _render_cart(household)
    _render_strip(household, cart_subtotal)


if __name__ == "__main__":
    main()
