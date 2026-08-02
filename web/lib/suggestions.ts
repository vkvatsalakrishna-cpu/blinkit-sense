import type { Product, SelectedSuggestion, SuggestionItem } from "./types";

export function suggestionRowKey(item: SuggestionItem): string {
  return `${item.role}|${item.need}`;
}

export function optionCount(s: SelectedSuggestion): number {
  return s.item.options?.length ?? 0;
}

export function hasMultipleOptions(s: SelectedSuggestion): boolean {
  return optionCount(s) > 1;
}

export function canAdvanceOption(s: SelectedSuggestion): boolean {
  const opts = s.item.options ?? [];
  return s.optionIndex < opts.length - 1;
}

export function applySuggestionOption(
  s: SelectedSuggestion,
  nextIndex: number,
): SelectedSuggestion {
  const opts = s.item.options ?? [];
  const opt = opts[nextIndex];
  if (!opt) return s;

  const product: Product = {
    id: opt.resolved_sku,
    name: opt.resolved_name,
    brand: s.product?.brand ?? "",
    category: opt.category,
    price: opt.price,
    mrp: opt.price,
    unit: s.product?.unit ?? "",
    available_in: s.product?.available_in ?? [],
    image_url: opt.image_url ?? s.product?.image_url,
  };

  return {
    ...s,
    optionIndex: nextIndex,
    item: {
      ...s.item,
      resolved_sku: opt.resolved_sku,
      resolved_name: opt.resolved_name,
      price: opt.price,
      category: opt.category,
    },
    product,
  };
}

export function initialOptionIndex(item: SuggestionItem): number {
  const count = item.options?.length ?? 0;
  if (count === 0) return 0;
  if (item.option_index != null) {
    return Math.min(Math.max(0, item.option_index), count - 1);
  }
  return Math.floor((count - 1) / 2);
}
