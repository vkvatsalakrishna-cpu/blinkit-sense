"use client";

import { ProductImage } from "./ProductImage";
import { feeBreakdown } from "@/lib/constants";
import type { CartLine } from "@/lib/types";

interface OrderConfirmationProps {
  cart: CartLine[];
  location: string;
}

export function OrderConfirmation({ cart, location }: OrderConfirmationProps) {
  const subtotal = cart.reduce((sum, line) => sum + line.product.price * line.qty, 0);
  const fees = feeBreakdown(subtotal);
  const total = subtotal + fees.totalFees;

  return (
    <section className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
      <div className="mb-6 text-center">
        <div className="mx-auto mb-3 flex h-14 w-14 items-center justify-center rounded-full bg-blinkit-green/10 text-2xl">
          ✓
        </div>
        <h2 className="text-xl font-bold text-gray-900">Your order is on its way</h2>
        <p className="mt-1 text-sm text-gray-600">Delivering to {location}</p>
      </div>

      <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-500">
        Order summary
      </h3>

      <ul className="divide-y divide-gray-100">
        {cart.map((line) => (
          <li key={line.sku_id} className="flex gap-3 py-3 first:pt-0">
            <ProductImage product={line.product} size={52} />
            <div className="min-w-0 flex-1">
              <p className="line-clamp-2 text-sm font-medium text-gray-900">
                {line.product.name}
              </p>
              <p className="text-xs text-gray-500">
                Qty {line.qty}
                {line.product.unit ? ` · ${line.product.unit}` : ""}
              </p>
            </div>
            <p className="shrink-0 text-sm font-semibold text-gray-900">
              ₹{line.product.price * line.qty}
            </p>
          </li>
        ))}
      </ul>

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
          <span>Total paid</span>
          <span>₹{total}</span>
        </div>
      </div>
    </section>
  );
}
