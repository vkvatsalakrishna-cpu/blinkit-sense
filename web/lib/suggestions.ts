import type { Product, SelectedSuggestion, SuggestionItem } from "./types";

export function suggestionRowKey(item: SuggestionItem): string {
  return `${item.role}|${item.need}`;
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
  if (item.option_index != null) return item.option_index;
  const count = item.options?.length ?? 0;
  return count > 0 ? Math.floor((count - 1) / 2) : 0;
}
