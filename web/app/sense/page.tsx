"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { CartPanel } from "@/components/CartPanel";
import { Header } from "@/components/Header";
import { OrderConfirmation } from "@/components/OrderConfirmation";
import { ScenarioSelector } from "@/components/ScenarioSelector";
import {
  SituationPanel,
  type SituationSubmitPayload,
} from "@/components/SituationPanel";
import { SuggestionsPanel } from "@/components/SuggestionsPanel";
import {
  fetchHouseholds,
  fetchProductDetails,
  fetchProductsBySkuIds,
  friendlyError,
  postNeeds,
  postSituations,
} from "@/lib/api";
import { mergeLinesIntoCart } from "@/lib/cart";
import {
  applySuggestionOption,
  canAdvanceOption,
  initialOptionIndex,
  suggestionRowKey,
} from "@/lib/suggestions";
import {
  catalogLocationFromAddress,
  confidenceThreshold,
  feeBreakdown,
  SCENARIO_PRESETS,
} from "@/lib/constants";
import type {
  CartLine,
  FlowPhase,
  Household,
  Product,
  ScenarioPreset,
  SelectedSuggestion,
  SituationsResponse,
} from "@/lib/types";

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function isLocationUnfamiliar(household: Household, location: string): boolean {
  return !household.known_addresses.includes(location);
}

function suggestionToProduct(s: SelectedSuggestion): Product {
  if (s.product) return s.product;
  return {
    id: s.item.resolved_sku,
    name: s.item.resolved_name,
    brand: "",
    category: s.item.category,
    price: s.item.price,
    mrp: s.item.price,
    unit: "",
    available_in: [],
  };
}

export default function SensePage() {
  const [households, setHouseholds] = useState<Household[]>([]);
  const [householdId, setHouseholdId] = useState("h1");
  const [location, setLocation] = useState("Sarjapur, Bangalore");
  const [cart, setCart] = useState<CartLine[]>([]);
  const [placedOrder, setPlacedOrder] = useState<CartLine[]>([]);
  const [activePresetId, setActivePresetId] = useState<string | null>(null);
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

  const cartSubtotal = useMemo(
    () => cart.reduce((sum, line) => sum + line.product.price * line.qty, 0),
    [cart],
  );

  const checkoutTotal = useMemo(() => {
    const fees = feeBreakdown(cartSubtotal);
    return cartSubtotal + fees.totalFees;
  }, [cartSubtotal]);

  useEffect(() => {
    fetchHouseholds()
      .then((list) => {
        setHouseholds(list);
        const h1 = list.find((h) => h.id === "h1");
        if (h1) setLocation(h1.current_address);
      })
      .catch((err) => setInitError(friendlyError(err)));
  }, []);

  const clearSensePanels = useCallback(() => {
    setSuggestions([]);
    setSituationLabel("");
    setSensitiveGuidance([]);
  }, []);

  const resetSenseFlow = useCallback(() => {
    setPhase("cart");
    setFlowError(null);
    setSituations(null);
    clearSensePanels();
  }, [clearSensePanels]);

  const loadPresetCart = useCallback(
    async (preset: ScenarioPreset) => {
      setPresetLoading(true);
      setFlowError(null);
      resetSenseFlow();
      setActivePresetId(preset.id);
      setHouseholdId(preset.householdId);

      const hh = households.find((h) => h.id === preset.householdId);
      const loc = hh?.current_address ?? location;

      try {
        const products = await fetchProductsBySkuIds(
          preset.skuIds,
          catalogLocationFromAddress(loc),
        );
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
    [households, location, resetSenseFlow],
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
    resetSenseFlow();
  };

  const handleShuffle = () => {
    if (SCENARIO_PRESETS.length === 0) return;
    const currentIdx = SCENARIO_PRESETS.findIndex((p) => p.id === activePresetId);
    let nextIdx = Math.floor(Math.random() * SCENARIO_PRESETS.length);
    while (nextIdx === currentIdx && SCENARIO_PRESETS.length > 1) {
      nextIdx = Math.floor(Math.random() * SCENARIO_PRESETS.length);
    }
    loadPresetCart(SCENARIO_PRESETS[nextIdx]);
  };

  const handleQtyChange = (skuId: string, qty: number) => {
    setCart((prev) =>
      prev.map((line) =>
        line.sku_id === skuId ? { ...line, qty: Math.min(5, Math.max(1, qty)) } : line,
      ),
    );
  };

  const handleRemove = (skuId: string) => {
    setCart((prev) => prev.filter((line) => line.sku_id !== skuId));
    resetSenseFlow();
  };

  const handleGetSuggestions = async () => {
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
      clearSensePanels();
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
    budget?: { min_price?: number; max_price?: number },
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
        min_price: budget?.min_price,
        max_price: budget?.max_price,
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
          optionIndex: initialOptionIndex(item),
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

  const handleSituationSubmit = ({ selection, min_price, max_price }: SituationSubmitPayload) => {
    const budget = { min_price, max_price };
    if (selection.kind === "custom") {
      runNeeds(
        "custom",
        selection.text,
        `The customer described their situation as: ${selection.text}`,
        budget,
      );
      return;
    }
    runNeeds(selection.candidate.id, selection.candidate.label, undefined, budget);
  };

  const handleStockingUp = () => {
    setSituations(null);
    clearSensePanels();
    setFlowError(null);
    setPhase("dismissed");
  };

  const handleDismissSense = () => {
    setSituations(null);
    clearSensePanels();
    setFlowError(null);
    setPhase("dismissed");
  };

  const handleAddAllSuggestions = () => {
    const selected = suggestions.filter((s) => s.checked && !s.dismissed);
    if (selected.length === 0) return;

    const additions: CartLine[] = selected.map((s) => ({
      sku_id: s.item.resolved_sku,
      qty: s.qty,
      product: suggestionToProduct(s),
    }));

    setCart((prev) => mergeLinesIntoCart(prev, additions));
    setSituations(null);
    clearSensePanels();
    setFlowError(null);
    setPhase("cart");
  };

  const handleAddProductToCart = useCallback((product: Product) => {
    setCart((prev) =>
      mergeLinesIntoCart(prev, [{ sku_id: product.id, qty: 1, product }]),
    );
  }, []);

  const refreshSuggestionProduct = useCallback((rowKey: string, skuId: string) => {
    void fetchProductDetails(skuId).then((product) => {
      setSuggestions((prev) =>
        prev.map((s) =>
          suggestionRowKey(s.item) === rowKey ? { ...s, product } : s,
        ),
      );
    });
  }, []);

  const handleAdvanceRow = useCallback(
    (rowKey: string) => {
      setSuggestions((prev) =>
        prev.map((s) => {
          if (suggestionRowKey(s.item) !== rowKey || !canAdvanceOption(s)) {
            return s;
          }
          const updated = applySuggestionOption(s, s.optionIndex + 1);
          refreshSuggestionProduct(rowKey, updated.item.resolved_sku);
          return updated;
        }),
      );
    },
    [refreshSuggestionProduct],
  );

  const handleShowOtherOptions = useCallback(() => {
    setSuggestions((prev) => {
      const advanced: { rowKey: string; skuId: string }[] = [];
      const next = prev.map((s) => {
        if (!canAdvanceOption(s)) return s;
        const updated = applySuggestionOption(s, s.optionIndex + 1);
        advanced.push({
          rowKey: suggestionRowKey(s.item),
          skuId: updated.item.resolved_sku,
        });
        return updated;
      });
      for (const { rowKey, skuId } of advanced) {
        refreshSuggestionProduct(rowKey, skuId);
      }
      return next;
    });
  }, [refreshSuggestionProduct]);

  const catalogLocation = useMemo(
    () => catalogLocationFromAddress(location),
    [location],
  );

  const handleCheckout = () => {
    if (cart.length === 0) return;
    setPlacedOrder(cart.map((line) => ({ ...line })));
    setPhase("order_confirmed");
  };

  const newCategoryTiles = useMemo(() => {
    const tiles = new Set<string>();
    suggestions.forEach((s) => {
      if (s.item.flag === "new_category") tiles.add(s.item.category);
    });
    return Array.from(tiles).sort();
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
        cartCount={phase === "order_confirmed" ? placedOrder.reduce((s, l) => s + l.qty, 0) : cartCount}
        households={households}
        selectedHouseholdId={householdId}
        onHouseholdChange={handleHouseholdChange}
        locationUnfamiliar={household ? isLocationUnfamiliar(household, location) : false}
      />

      <main className="mx-auto max-w-2xl space-y-4 px-4 pt-4">
        {phase === "order_confirmed" ? (
          <OrderConfirmation cart={placedOrder} location={location} />
        ) : (
          <>
            <CartPanel
              cart={cart}
              onQtyChange={handleQtyChange}
              onRemove={handleRemove}
            />

            <ScenarioSelector
              presets={SCENARIO_PRESETS}
              activePresetId={activePresetId}
              loading={presetLoading}
              onLoadPreset={loadPresetCart}
              onShuffle={handleShuffle}
            />

            <section className="rounded-xl border border-amber-200 bg-blinkit-cream p-4 shadow-sm">
              <div className="mb-3">
                <p className="text-xs font-semibold uppercase tracking-wide text-amber-800">
                  Blinkit Sense
                </p>
                <p className="mt-1 text-sm text-gray-600">
                  Optional — tell us your situation and we&apos;ll suggest items you
                  might need.
                </p>
              </div>

              {(phase === "cart" || phase === "dismissed") && (
                <div className="space-y-2">
                  <button
                    type="button"
                    disabled={cart.length === 0}
                    onClick={handleGetSuggestions}
                    className="w-full rounded-lg border border-amber-300 bg-white py-2.5 text-sm font-semibold text-amber-900 hover:bg-amber-50 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    Get suggestions
                  </button>
                  {cart.length === 0 && (
                    <p className="text-center text-sm text-gray-500">
                      Add something to your cart to get started.
                    </p>
                  )}
                </div>
              )}

              {phase === "situations_loading" && (
                <div className="py-4 text-center">
                  <div className="mx-auto mb-3 h-8 w-8 animate-spin rounded-full border-2 border-blinkit-green border-t-transparent" />
                  <p className="text-sm text-gray-700">Reading your cart…</p>
                </div>
              )}

              {phase === "situations" && situations && situations.candidates.length > 0 && (
                <SituationPanel
                  candidates={situations.candidates}
                  loading={false}
                  onSubmit={handleSituationSubmit}
                  onStockingUp={handleStockingUp}
                  onDismiss={handleDismissSense}
                />
              )}

              {phase === "needs_loading" && (
                <div className="py-4 text-center">
                  <div className="mx-auto mb-3 h-8 w-8 animate-spin rounded-full border-2 border-blinkit-green border-t-transparent" />
                  <p className="text-sm text-gray-700">Working out what you&apos;ll need…</p>
                </div>
              )}

              {phase === "suggestions" && (
                <SuggestionsPanel
                  situationLabel={situationLabel}
                  suggestions={suggestions}
                  catalogLocation={catalogLocation}
                  onToggle={(rowKey) =>
                    setSuggestions((prev) =>
                      prev.map((s) =>
                        suggestionRowKey(s.item) === rowKey
                          ? { ...s, checked: !s.checked }
                          : s,
                      ),
                    )
                  }
                  onQtyChange={(rowKey, qty) =>
                    setSuggestions((prev) =>
                      prev.map((s) =>
                        suggestionRowKey(s.item) === rowKey
                          ? { ...s, qty: Math.min(5, Math.max(1, qty)) }
                          : s,
                      ),
                    )
                  }
                  onAdvanceRow={handleAdvanceRow}
                  onShowOtherOptions={handleShowOtherOptions}
                  onAddAll={handleAddAllSuggestions}
                  onAddProductToCart={handleAddProductToCart}
                  sensitiveGuidance={sensitiveGuidance}
                  newCategoryTiles={newCategoryTiles}
                />
              )}

              {phase === "dismissed" && (
                <p className="text-center text-sm text-gray-600">
                  No suggestions this time. You can try again or checkout below.
                </p>
              )}
            </section>

            <button
              type="button"
              disabled={cart.length === 0}
              onClick={handleCheckout}
              className="w-full rounded-lg bg-blinkit-green py-4 text-base font-bold text-white shadow-md hover:bg-blinkit-green-dark disabled:opacity-50"
            >
              Checkout · ₹{checkoutTotal}
            </button>
          </>
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
