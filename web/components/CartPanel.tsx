"use client";

import { ProductImage } from "./ProductImage";
import { feeBreakdown } from "@/lib/constants";
import type { CartLine } from "@/lib/types";

interface CartPanelProps {
  cart: CartLine[];
  onQtyChange: (skuId: string, qty: number) => void;
  onRemove: (skuId: string) => void;
}

export function CartPanel({ cart, onQtyChange, onRemove }: CartPanelProps) {
  const subtotal = cart.reduce((sum, line) => sum + line.product.price * line.qty, 0);
  const fees = feeBreakdown(subtotal);
  const total = subtotal + fees.totalFees;

  return (
    <section className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
      <h2 className="mb-3 text-lg font-semibold text-gray-900">Your cart</h2>

      {cart.length === 0 ? (
        <p className="py-6 text-center text-sm text-gray-500">
          Cart is empty — load a scenario below.
        </p>
      ) : (
        <ul className="divide-y divide-gray-100">
          {cart.map((line) => (
            <li key={line.sku_id} className="flex gap-3 py-3 first:pt-0 last:pb-0">
              <ProductImage product={line.product} size={72} />
              <div className="min-w-0 flex-1">
                <p className="line-clamp-2 text-sm font-medium text-gray-900">
                  {line.product.name}
                </p>
                <p className="text-xs text-gray-500">
                  {line.product.brand} · {line.product.unit}
                </p>
                <div className="mt-2 flex items-center justify-between gap-2">
                  <div className="flex items-center rounded-lg border border-gray-200">
                    <button
                      type="button"
                      disabled={line.qty <= 1}
                      onClick={() => onQtyChange(line.sku_id, line.qty - 1)}
                      className="px-2.5 py-1 text-lg text-gray-600 disabled:cursor-not-allowed disabled:opacity-30"
                      aria-label="Decrease quantity"
                    >
                      −
                    </button>
                    <span className="min-w-[2rem] text-center text-sm font-medium">
                      {line.qty}
                    </span>
                    <button
                      type="button"
                      disabled={line.qty >= 5}
                      onClick={() => onQtyChange(line.sku_id, line.qty + 1)}
                      className="px-2.5 py-1 text-lg text-gray-600 disabled:cursor-not-allowed disabled:opacity-30"
                      aria-label="Increase quantity"
                    >
                      +
                    </button>
                  </div>
                  <p className="text-sm font-semibold text-gray-900">
                    ₹{line.product.price * line.qty}
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => onRemove(line.sku_id)}
                className="self-start text-xs text-gray-400 hover:text-red-600"
                aria-label="Remove item"
              >
                Remove
              </button>
            </li>
          ))}
        </ul>
      )}

      <div className="mt-4 space-y-1 border-t border-gray-100 pt-3 text-sm text-gray-600">
        <div className="flex justify-between">
          <span>Subtotal</span>
          <span>₹{subtotal}</span>
        </div>
        <div className="flex justify-between">
          <span>Delivery</span>
          <span>₹{fees.delivery}</span>
        </div>
        <div className="flex justify-between">
          <span>Handling</span>
          <span>₹{fees.handling}</span>
        </div>
        {fees.smallCart > 0 && (
          <div className="flex justify-between text-orange-700">
            <span>Small-cart surcharge</span>
            <span>₹{fees.smallCart}</span>
          </div>
        )}
        <div className="flex justify-between pt-1 text-base font-semibold text-gray-900">
          <span>Total</span>
          <span>₹{total}</span>
        </div>
        {fees.gapToThreshold > 0 && (
          <p className="pt-2 text-xs text-orange-700">
            Add ₹{fees.gapToThreshold} more to reach ₹99 and waive the ₹20 small-cart
            charge.
          </p>
        )}
      </div>
    </section>
  );
}
