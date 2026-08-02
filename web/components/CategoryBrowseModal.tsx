"use client";

import { useEffect, useMemo, useState } from "react";
import { ProductImage } from "./ProductImage";
import { fetchCatalogByCategory, friendlyError } from "@/lib/api";
import type { CategoryBrowseFilter, Product } from "@/lib/types";

const FILTER_LABELS: Record<CategoryBrowseFilter, string> = {
  budget: "Budget",
  premium: "Premium",
  popular: "Trending",
};

interface CategoryBrowseModalProps {
  category: string;
  filter: CategoryBrowseFilter;
  catalogLocation: string;
  onClose: () => void;
  onAdd: (product: Product) => void;
}

export function CategoryBrowseModal({
  category,
  filter,
  catalogLocation,
  onClose,
  onAdd,
}: CategoryBrowseModalProps) {
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const query = useMemo(() => {
    const base = {
      limit: 24,
      sort: "popularity_rank" as const,
    };
    if (filter === "budget") {
      return { ...base, max_price: 249 };
    }
    if (filter === "premium") {
      return { ...base, min_price: 801 };
    }
    return base;
  }, [filter]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    fetchCatalogByCategory(category, catalogLocation, query)
      .then((items) => {
        if (!cancelled) setProducts(items);
      })
      .catch((err) => {
        if (!cancelled) setError(friendlyError(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [category, catalogLocation, query]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  const filterLabel = FILTER_LABELS[filter];

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 p-4 sm:items-center"
      role="dialog"
      aria-modal="true"
      aria-labelledby="category-browse-title"
      onClick={onClose}
    >
      <div
        className="flex max-h-[85vh] w-full max-w-lg flex-col rounded-xl bg-white shadow-xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-3 border-b border-gray-100 px-4 py-3">
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-gray-500">
              {filterLabel}
            </p>
            <h2 id="category-browse-title" className="text-lg font-semibold text-gray-900">
              {category}
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1 text-2xl leading-none text-gray-400 hover:bg-gray-100 hover:text-gray-700"
            aria-label="Close"
          >
            ×
          </button>
        </div>

        <div className="overflow-y-auto px-4 py-3">
          {loading && (
            <p className="py-8 text-center text-sm text-gray-500">Loading products…</p>
          )}
          {error && (
            <p className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">
              {error}
            </p>
          )}
          {!loading && !error && products.length === 0 && (
            <p className="py-8 text-center text-sm text-gray-500">
              No products found in this category at your location.
            </p>
          )}
          {!loading && !error && products.length > 0 && (
            <ul className="space-y-2">
              {products.map((product) => (
                <li
                  key={product.id}
                  className="flex items-center gap-3 rounded-lg border border-gray-100 bg-gray-50/50 p-2"
                >
                  <ProductImage product={product} size={48} />
                  <div className="min-w-0 flex-1">
                    <p className="line-clamp-2 text-sm font-medium text-gray-900">
                      {product.name}
                    </p>
                    <p className="text-sm font-semibold text-gray-800">₹{product.price}</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => onAdd(product)}
                    className="shrink-0 rounded-lg bg-blinkit-green px-3 py-1.5 text-xs font-semibold text-white hover:bg-blinkit-green/90"
                  >
                    Add
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
