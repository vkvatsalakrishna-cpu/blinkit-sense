"use client";

import { useState } from "react";
import { CategoryBrowseModal } from "./CategoryBrowseModal";
import { ProductImage } from "./ProductImage";
import {
  canAdvanceOption,
  suggestionRowKey,
} from "@/lib/suggestions";
import type { Product, SelectedSuggestion } from "@/lib/types";

interface SuggestionsPanelProps {
  situationLabel: string;
  suggestions: SelectedSuggestion[];
  catalogLocation: string;
  onBack: () => void;
  onToggle: (rowKey: string) => void;
  onQtyChange: (rowKey: string, qty: number) => void;
  onAdvanceRow: (rowKey: string) => void;
  onShowOtherOptions: () => void;
  onAddAll: () => void;
  onAddProductToCart: (product: Product) => void;
  sensitiveGuidance: string[];
  newCategoryTiles: string[];
  hasReserve?: boolean;
}

export function SuggestionsPanel({
  situationLabel,
  suggestions,
  catalogLocation,
  onBack,
  onToggle,
  onQtyChange,
  onAdvanceRow,
  onShowOtherOptions,
  onAddAll,
  onAddProductToCart,
  sensitiveGuidance,
  newCategoryTiles,
  hasReserve = false,
}: SuggestionsPanelProps) {
  const [browseCategory, setBrowseCategory] = useState<string | null>(null);
  const visible = suggestions.filter((s) => !s.dismissed);
  const selected = visible.filter((s) => s.checked);
  const addTotal = selected.reduce(
    (sum, s) => sum + s.item.price * s.qty,
    0,
  );
  const anyCanAdvance = visible.some(canAdvanceOption);

  const backLink = (
    <button
      type="button"
      onClick={onBack}
      className="text-sm font-medium text-blinkit-green hover:underline"
    >
      ← Back
    </button>
  );

  if (visible.length === 0) {
    return (
      <section className="space-y-3">
        {backLink}
        <p className="font-caveat text-[20px] italic leading-tight text-blinkit-green">
          Suggested for you
        </p>
        <p className="text-sm text-gray-700">
          Nothing to add for this one — you&apos;re set.
        </p>
      </section>
    );
  }

  return (
    <section className="space-y-4">
      {backLink}
      <div>
        <p className="font-caveat text-[20px] italic leading-tight text-blinkit-green">
          Suggested for you
        </p>
        <h3 className="mt-1 text-lg font-semibold text-gray-900">{situationLabel}</h3>
      </div>

      <ul className="space-y-3">
        {visible.map((s) => {
          const rowKey = suggestionRowKey(s.item);
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

          const isNewCategory = s.item.flag === "new_category";

          return (
            <li
              key={rowKey}
              className="group overflow-hidden rounded-2xl border-l-[3px] border-l-blinkit-green bg-white shadow-sm transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md"
            >
              <div className="flex gap-3 p-3">
              <input
                type="checkbox"
                checked={s.checked}
                onChange={() => onToggle(rowKey)}
                className="mt-1 h-4 w-4 accent-blinkit-green"
                aria-label={`Select ${s.item.resolved_name}`}
              />
              <ProductImage product={product} size={56} />
              <div className="min-w-0 flex-1">
                <div className="mb-0.5 flex flex-wrap items-center gap-1.5">
                  <p className="text-xs text-gray-500">
                    {s.item.category} · {s.item.role}
                  </p>
                  {isNewCategory && (
                    <span className="rounded-full bg-blinkit-green/[0.08] px-2 py-0.5 text-[10px] font-medium text-blinkit-green">
                      New for you
                    </span>
                  )}
                </div>
                <p className="line-clamp-2 text-sm font-medium text-gray-900">
                  {s.item.resolved_name}
                </p>
                {s.item.quantity_reasoning ? (
                  <p className="mt-0.5 text-xs italic text-gray-500">
                    {s.item.quantity_reasoning}
                  </p>
                ) : null}
                <p className="mt-0.5 text-xs text-gray-500">
                  {product.brand}
                  {product.unit ? ` · ${product.unit}` : ""}
                </p>
                <button
                  type="button"
                  onClick={() => setBrowseCategory(s.item.category)}
                  className="mt-1 text-xs font-medium text-blinkit-green hover:underline"
                >
                  More from this category
                </button>
                <div className="mt-2 flex items-center justify-between">
                  <div className="flex items-center rounded-lg border border-gray-200">
                    <button
                      type="button"
                      disabled={s.qty <= 1}
                      onClick={() => onQtyChange(rowKey, s.qty - 1)}
                      className="px-2 py-0.5 text-gray-600 disabled:opacity-30"
                    >
                      −
                    </button>
                    <span className="min-w-[1.5rem] text-center text-sm">{s.qty}</span>
                    <button
                      type="button"
                      disabled={s.qty >= 5}
                      onClick={() => onQtyChange(rowKey, s.qty + 1)}
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
                onClick={() => onAdvanceRow(rowKey)}
                disabled={!canAdvanceOption(s)}
                className="self-start text-lg leading-none text-gray-300 hover:text-gray-600 disabled:cursor-default disabled:opacity-30"
                aria-label="Show another option for this item"
              >
                ×
              </button>
              </div>
            </li>
          );
        })}
      </ul>

      {anyCanAdvance || hasReserve ? (
        <button
          type="button"
          onClick={onShowOtherOptions}
          className="mt-4 w-full rounded-lg border border-gray-200 bg-white py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
        >
          Show other options
        </button>
      ) : (
        <p className="mt-4 text-center text-sm text-gray-500">
          That&apos;s everything I could think of for this.
        </p>
      )}

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

      {browseCategory && (
        <CategoryBrowseModal
          category={browseCategory}
          catalogLocation={catalogLocation}
          onClose={() => setBrowseCategory(null)}
          onAdd={onAddProductToCart}
        />
      )}
    </section>
  );
}
