"use client";

import { ProductImage } from "./ProductImage";
import type { SelectedSuggestion } from "@/lib/types";

interface SuggestionsPanelProps {
  situationLabel: string;
  suggestions: SelectedSuggestion[];
  onToggle: (skuId: string) => void;
  onQtyChange: (skuId: string, qty: number) => void;
  onDismiss: (skuId: string) => void;
  onAddAll: () => void;
  sensitiveGuidance: string[];
  newCategoryTiles: string[];
}

export function SuggestionsPanel({
  situationLabel,
  suggestions,
  onToggle,
  onQtyChange,
  onDismiss,
  onAddAll,
  sensitiveGuidance,
  newCategoryTiles,
}: SuggestionsPanelProps) {
  const visible = suggestions.filter((s) => !s.dismissed);
  const selected = visible.filter((s) => s.checked);
  const addTotal = selected.reduce(
    (sum, s) => sum + s.item.price * s.qty,
    0,
  );

  if (visible.length === 0) {
    return (
      <section className="rounded-xl border border-amber-200 bg-blinkit-cream p-4">
        <p className="text-sm text-gray-700">
          Nothing to add for this one — you&apos;re set.
        </p>
      </section>
    );
  }

  return (
    <section className="rounded-xl border border-amber-200 bg-blinkit-cream p-4 shadow-sm">
      <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-amber-800">
        Suggested for you
      </p>
      <h3 className="mb-4 text-lg font-semibold text-gray-900">{situationLabel}</h3>

      <ul className="space-y-3">
        {visible.map((s) => {
          const product = s.product ?? {
            id: s.item.resolved_sku,
            name: s.item.resolved_name,
            brand: "",
            category: s.item.category,
            price: s.item.price,
            mrp: s.item.price,
            unit: "",
            available_in: [],
          };

          return (
            <li
              key={s.item.resolved_sku}
              className="flex gap-3 rounded-lg border border-gray-200 bg-white p-3"
            >
              <input
                type="checkbox"
                checked={s.checked}
                onChange={() => onToggle(s.item.resolved_sku)}
                className="mt-1 h-4 w-4 accent-blinkit-green"
                aria-label={`Select ${s.item.resolved_name}`}
              />
              <ProductImage product={product} size={56} />
              <div className="min-w-0 flex-1">
                <p className="line-clamp-2 text-sm font-medium text-gray-900">
                  {s.item.resolved_name}
                </p>
                <p className="text-xs text-gray-500">
                  {product.brand}
                  {product.unit ? ` · ${product.unit}` : ""}
                </p>
                <p className="text-xs text-gray-400">{s.item.role}</p>
                <div className="mt-2 flex items-center justify-between">
                  <div className="flex items-center rounded-lg border border-gray-200">
                    <button
                      type="button"
                      disabled={s.qty <= 1}
                      onClick={() => onQtyChange(s.item.resolved_sku, s.qty - 1)}
                      className="px-2 py-0.5 text-gray-600 disabled:opacity-30"
                    >
                      −
                    </button>
                    <span className="min-w-[1.5rem] text-center text-sm">{s.qty}</span>
                    <button
                      type="button"
                      disabled={s.qty >= 5}
                      onClick={() => onQtyChange(s.item.resolved_sku, s.qty + 1)}
                      className="px-2 py-0.5 text-gray-600 disabled:opacity-30"
                    >
                      +
                    </button>
                  </div>
                  <span className="text-sm font-semibold">₹{s.item.price * s.qty}</span>
                </div>
              </div>
              <button
                type="button"
                onClick={() => onDismiss(s.item.resolved_sku)}
                className="self-start text-lg leading-none text-gray-300 hover:text-gray-600"
                aria-label="Dismiss suggestion"
              >
                ×
              </button>
            </li>
          );
        })}
      </ul>

      <button
        type="button"
        disabled={selected.length === 0}
        onClick={onAddAll}
        className="mt-4 w-full rounded-lg border border-blinkit-green bg-white py-2.5 text-sm font-semibold text-blinkit-green hover:bg-blinkit-green/5 disabled:opacity-50"
      >
        Add all {selected.length} · ₹{addTotal}
      </button>

      {newCategoryTiles.length > 0 && (
        <p className="mt-3 text-sm font-semibold text-blinkit-green">
          New for your household: {newCategoryTiles.join(", ")}
        </p>
      )}

      {sensitiveGuidance.map((line) => (
        <p key={line} className="mt-2 text-xs text-gray-500">
          {line}
        </p>
      ))}
    </section>
  );
}
