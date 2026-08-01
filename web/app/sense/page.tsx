"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { CartPanel } from "@/components/CartPanel";
import { Header } from "@/components/Header";
import { ScenarioSelector } from "@/components/ScenarioSelector";
import { SituationPanel } from "@/components/SituationPanel";
import { SuggestionsPanel } from "@/components/SuggestionsPanel";
import {
  fetchHouseholds,
  fetchProductDetails,
  fetchProductsBySkuIds,
  friendlyError,
  postNeeds,
  postSituations,
} from "@/lib/api";
import {
  catalogLocationFromAddress,
  confidenceThreshold,
  SCENARIO_PRESETS,
} from "@/lib/constants";
import type {
  CartLine,
  FlowPhase,
  Household,
  ScenarioPreset,
  SelectedSuggestion,
  SituationCandidate,
  SituationsResponse,
} from "@/lib/types";

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function isLocationUnfamiliar(household: Household, location: string): boolean {
  return !household.known_addresses.includes(location);
}

export default function SensePage() {
  const [households, setHouseholds] = useState<Household[]>([]);
  const [householdId, setHouseholdId] = useState("h1");
  const [location, setLocation] = useState("Sarjapur, Bangalore");
  const [cart, setCart] = useState<CartLine[]>([]);
  const [activePresetId, setActivePresetId] = useState<string | null>(null);
  const [shuffleIndex, setShuffleIndex] = useState(0);
  const [presetLoading, setPresetLoading] = useState(false);
  const [initError, setInitError] = useState<string | null>(null);

  const [phase, setPhase] = useState<FlowPhase>("cart");
  const [flowError, setFlowError] = useState<string | null>(null);
  const [situations, setSituations] = useState<SituationsResponse | null>(null);
  const [suggestions, setSuggestions] = useState<SelectedSuggestion[]>([]);
  const [situationLabel, setSituationLabel] = useState("");
  const [sensitiveGuidance, setSensitiveGuidance] = useState<string[]>([]);

  const household = useMemo(
    () => households.find((h) => h.id === householdId) ?? null,
    [households, householdId],
  );

  const cartCount = useMemo(
    () => cart.reduce((sum, line) => sum + line.qty, 0),
    [cart],
  );

  useEffect(() => {
    fetchHouseholds()
      .then((list) => {
        setHouseholds(list);
        const h1 = list.find((h) => h.id === "h1");
        if (h1) {
          setLocation(h1.current_address);
        }
      })
      .catch((err) => setInitError(friendlyError(err)));
  }, []);

  const loadPresetCart = useCallback(
    async (preset: ScenarioPreset) => {
      setPresetLoading(true);
      setFlowError(null);
      setPhase("cart");
      setSituations(null);
      setSuggestions([]);
      setActivePresetId(preset.id);
      setHouseholdId(preset.householdId);

      const hh = households.find((h) => h.id === preset.householdId);
      const loc = hh?.current_address ?? location;

      try {
        const products = await fetchProductsBySkuIds(preset.skuIds, catalogLocationFromAddress(loc));
        const lines: CartLine[] = preset.skuIds
          .map((skuId) => {
            const product = products.get(skuId);
            if (!product) return null;
            return { sku_id: skuId, qty: 1, product };
          })
          .filter((line): line is CartLine => line !== null);

        if (lines.length === 0) {
          setFlowError("Could not load products for this scenario.");
          return;
        }

        setLocation(loc);
        setCart(lines);
      } catch (err) {
        setFlowError(friendlyError(err));
      } finally {
        setPresetLoading(false);
      }
    },
    [households, location],
  );

  useEffect(() => {
    if (households.length === 0) return;
    loadPresetCart(SCENARIO_PRESETS[0]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [households.length]);

  const handleHouseholdChange = (id: string) => {
    setHouseholdId(id);
    const hh = households.find((h) => h.id === id);
    if (hh) setLocation(hh.current_address);
    resetFlow();
  };

  const resetFlow = () => {
    setPhase("cart");
    setFlowError(null);
    setSituations(null);
    setSuggestions([]);
  };

  const handleShuffle = () => {
    const next = (shuffleIndex + 1) % SCENARIO_PRESETS.length;
    setShuffleIndex(next);
    loadPresetCart(SCENARIO_PRESETS[next]);
  };

  const handleQtyChange = (skuId: string, qty: number) => {
    setCart((prev) =>
      prev.map((line) =>
        line.sku_id === skuId ? { ...line, qty: Math.min(5, Math.max(1, qty)) } : line,
      ),
    );
    resetFlow();
  };

  const handleRemove = (skuId: string) => {
    setCart((prev) => prev.filter((line) => line.sku_id !== skuId));
    resetFlow();
  };

  const handleCheckout = async () => {
    if (cart.length === 0 || !household) return;
    setFlowError(null);
    setPhase("situations_loading");

    try {
      const result = await postSituations({
        household_id: householdId,
        cart: cart.map((l) => ({ sku_id: l.sku_id, qty: l.qty })),
        location,
        today: todayIso(),
      });

      const threshold = confidenceThreshold(household.orders_per_month);
      if (result.confidence < threshold) {
        setFlowError(
          "Your cart looks like a routine shop — no special situation detected.",
        );
        setPhase("cart");
        return;
      }

      setSituations(result);
      setPhase("situations");
    } catch (err) {
      setFlowError(friendlyError(err));
      setPhase("cart");
    }
  };

  const runNeeds = async (
    situationId: string,
    label: string,
    promptContext?: string,
  ) => {
    if (!household) return;
    setFlowError(null);
    setPhase("needs_loading");

    try {
      const result = await postNeeds({
        household_id: householdId,
        situation_id: situationId,
        cart: cart.map((l) => ({ sku_id: l.sku_id, qty: l.qty })),
        location,
        situation_label: situationId === "custom" ? label : undefined,
        prompt_context: promptContext,
      });

      const productMap = await Promise.all(
        result.items.map(async (item) => ({
          item,
          product: await fetchProductDetails(item.resolved_sku),
        })),
      );

      setSuggestions(
        productMap.map(({ item, product }) => ({
          item,
          product,
          qty: 1,
          checked: true,
          dismissed: false,
        })),
      );
      setSituationLabel(result.situation_label);
      setSensitiveGuidance(result.sensitive_guidance ?? []);
      setPhase("suggestions");
    } catch (err) {
      setFlowError(friendlyError(err));
      setPhase("situations");
    }
  };

  const handleConfirmCandidate = (candidate: SituationCandidate) => {
    runNeeds(candidate.id, candidate.label);
  };

  const handleCustomSubmit = (text: string) => {
    runNeeds(
      "custom",
      text,
      `The customer described their situation as: ${text}`,
    );
  };

  const handleStockingUp = () => {
    setPhase("dismissed");
    setSituations(null);
    setFlowError(null);
  };

  const handleDismiss = () => {
    setPhase("dismissed");
    setSituations(null);
    setFlowError(null);
  };

  const newCategoryTiles = useMemo(() => {
    const tiles = new Set<string>();
    suggestions.forEach((s) => {
      if (s.item.flag === "new_category") tiles.add(s.item.category);
    });
    return [...tiles].sort();
  }, [suggestions]);

  if (initError) {
    return (
      <div className="mx-auto max-w-2xl p-6">
        <p className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">
          {initError}
        </p>
      </div>
    );
  }

  return (
    <div className="min-h-screen pb-8">
      <Header
        location={location}
        cartCount={cartCount}
        households={households}
        selectedHouseholdId={householdId}
        onHouseholdChange={handleHouseholdChange}
        locationUnfamiliar={household ? isLocationUnfamiliar(household, location) : false}
      />

      <main className="mx-auto max-w-2xl space-y-4 px-4 pt-4">
        <CartPanel cart={cart} onQtyChange={handleQtyChange} onRemove={handleRemove} />

        <ScenarioSelector
          presets={SCENARIO_PRESETS}
          activePresetId={activePresetId}
          loading={presetLoading}
          onLoadPreset={loadPresetCart}
          onShuffle={handleShuffle}
        />

        {phase === "cart" && (
          <button
            type="button"
            disabled={cart.length === 0}
            onClick={handleCheckout}
            className="w-full rounded-lg bg-blinkit-green py-3.5 text-base font-semibold text-white shadow-sm hover:bg-blinkit-green-dark disabled:opacity-50"
          >
            Checkout
          </button>
        )}

        {phase === "situations_loading" && (
          <div className="rounded-xl border border-amber-200 bg-blinkit-cream p-6 text-center">
            <div className="mx-auto mb-3 h-8 w-8 animate-spin rounded-full border-2 border-blinkit-green border-t-transparent" />
            <p className="text-sm text-gray-700">Reading your cart…</p>
          </div>
        )}

        {phase === "situations" && situations && situations.candidates.length > 0 && (
          <SituationPanel
            top={situations.candidates[0]}
            others={situations.candidates.slice(1)}
            loading={false}
            onConfirm={handleConfirmCandidate}
            onCustomSubmit={handleCustomSubmit}
            onStockingUp={handleStockingUp}
            onDismiss={handleDismiss}
          />
        )}

        {phase === "needs_loading" && (
          <div className="rounded-xl border border-amber-200 bg-blinkit-cream p-6 text-center">
            <div className="mx-auto mb-3 h-8 w-8 animate-spin rounded-full border-2 border-blinkit-green border-t-transparent" />
            <p className="text-sm text-gray-700">Planning what you might need…</p>
          </div>
        )}

        {phase === "suggestions" && (
          <SuggestionsPanel
            situationLabel={situationLabel}
            suggestions={suggestions}
            onToggle={(skuId) =>
              setSuggestions((prev) =>
                prev.map((s) =>
                  s.item.resolved_sku === skuId ? { ...s, checked: !s.checked } : s,
                ),
              )
            }
            onQtyChange={(skuId, qty) =>
              setSuggestions((prev) =>
                prev.map((s) =>
                  s.item.resolved_sku === skuId
                    ? { ...s, qty: Math.min(5, Math.max(1, qty)) }
                    : s,
                ),
              )
            }
            onDismiss={(skuId) =>
              setSuggestions((prev) =>
                prev.map((s) =>
                  s.item.resolved_sku === skuId ? { ...s, dismissed: true } : s,
                ),
              )
            }
            sensitiveGuidance={sensitiveGuidance}
            newCategoryTiles={newCategoryTiles}
          />
        )}

        {phase === "dismissed" && (
          <p className="rounded-xl border border-gray-200 bg-white p-4 text-center text-sm text-gray-500">
            No suggestions this time. Adjust your cart or try another scenario.
          </p>
        )}

        {flowError && (
          <p className="rounded-lg border border-orange-200 bg-orange-50 p-3 text-sm text-orange-900">
            {flowError}
          </p>
        )}
      </main>
    </div>
  );
}
