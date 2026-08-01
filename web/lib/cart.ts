import type { CartLine } from "./types";

export function mergeLinesIntoCart(
  cart: CartLine[],
  additions: CartLine[],
): CartLine[] {
  const bySku = new Map(cart.map((line) => [line.sku_id, { ...line }]));

  for (const addition of additions) {
    const existing = bySku.get(addition.sku_id);
    if (existing) {
      existing.qty = Math.min(5, existing.qty + addition.qty);
    } else {
      bySku.set(addition.sku_id, { ...addition });
    }
  }

  return Array.from(bySku.values());
}
