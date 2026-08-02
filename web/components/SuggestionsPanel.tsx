"use client";

import { useState, type ReactNode } from "react";
import { CategoryBrowseModal } from "./CategoryBrowseModal";
import { ProductImage } from "./ProductImage";
import {
  canAdvanceOption,
  hasMultipleOptions,
  suggestionRowKey,
} from "@/lib/suggestions";
import type { CategoryBrowseFilter, Product, SelectedSuggestion } from "@/lib/types";

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

const FILTER_PILLS: {
  filter: CategoryBrowseFilter;
  label: string;
  icon: ReactNode;
}[] = [
  {
    filter: "budget",
    label: "Budget",
    icon: (
      <span className="text-[11px] font-semibold leading-none" aria-hidden>
        ₹
      </span>
    ),
  },
  {
    filter: "premium",
    label: "Premium",
    icon: (
      <svg className="h-3 w-3 shrink-0" viewBox="0 0 16 16" fill="currentColor" aria-hidden>
        <path d="M8 0.5L9.2 5.4L14 6.5L9.2 7.6L8 12.5L6.8 7.6L2 6.5L6.8 5.4L8 0.5Z" />
        <path
          d="M13 2.5L13.6 4.6L15.5 5.2L13.6 5.8L13 7.9L12.4 5.8L10.5 5.2L12.4 4.6L13 2.5Z"
          opacity="0.85"
        />
      </svg>
    ),
  },
  {
    filter: "popular",
    label: "Trending",
    icon: (
      <svg className="h-3 w-3 shrink-0" viewBox="0 0 12 12" fill="none" aria-hidden>
        <path
          d="M2.5 9.5L9.5 2.5M9.5 2.5H5.5M9.5 2.5V6.5"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    ),
  },
];

const filterPillClassName =
  "inline-flex items-center gap-1 rounded-full border border-[#0C831F]/25 bg-white px-2.5 py-1 text-xs font-medium text-blinkit-green transition-colors hover:border-blinkit-green hover:bg-blinkit-green/[0.08]";

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
  const [browse, setBrowse] = useState<{
    category: string;
    filter: CategoryBrowseFilter;
  } | null>(null);
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
          const canAdvance = canAdvanceOption(s);
          const multipleOptions = hasMultipleOptions(s);
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
                <div className="mt-2 flex flex-wrap items-center gap-1.5">
                  {FILTER_PILLS.map(({ filter, label, icon }) => (
                    <button
                      key={filter}
                      type="button"
                      onClick={() =>
                        setBrowse({ category: s.item.category, filter })
                      }
                      className={filterPillClassName}
                    >
                      {icon}
                      {label}
                    </button>
                  ))}
                </div>
                <p className="mt-1.5 text-xs text-gray-500">
                  {product.brand}
                  {product.unit ? ` · ${product.unit}` : ""}
                </p>
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
                disabled={!canAdvance}
                title={
                  !multipleOptions
                    ? "No other options for this item"
                    : canAdvance
                      ? "Show another option for this item"
                      : "Last option for this item"
                }
                className={`self-start text-lg leading-none disabled:cursor-not-allowed ${
                  canAdvance
                    ? "text-gray-300 hover:text-gray-600"
                    : multipleOptions
                      ? "text-gray-200 opacity-40"
                      : "text-gray-200/60 line-through decoration-gray-300/80"
                }`}
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
          className="mt-4 text-sm font-medium text-blinkit-green hover:underline"
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

      {browse && (
        <CategoryBrowseModal
          category={browse.category}
          filter={browse.filter}
          catalogLocation={catalogLocation}
          onClose={() => setBrowse(null)}
          onAdd={onAddProductToCart}
        />
      )}
    </section>
  );
}
