"use client";

import Image from "next/image";
import type { Product } from "@/lib/types";

const PLACEHOLDER =
  "data:image/svg+xml," +
  encodeURIComponent(
    `<svg xmlns="http://www.w3.org/2000/svg" width="80" height="80" viewBox="0 0 80 80"><rect fill="#f3f4f6" width="80" height="80" rx="8"/><text x="50%" y="52%" dominant-baseline="middle" text-anchor="middle" fill="#9ca3af" font-size="28">🛒</text></svg>`,
  );

export function ProductImage({
  product,
  size = 64,
  className = "",
}: {
  product: Product;
  size?: number;
  className?: string;
}) {
  const src = product.image_url || PLACEHOLDER;
  const isRemote = Boolean(product.image_url);

  return (
    <div
      className={`relative shrink-0 overflow-hidden rounded-lg bg-gray-100 ${className}`}
      style={{ width: size, height: size }}
    >
      {isRemote ? (
        <Image
          src={src}
          alt={product.name}
          fill
          className="object-contain p-1"
          sizes={`${size}px`}
        />
      ) : (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={src} alt={product.name} className="h-full w-full object-contain p-1" />
      )}
    </div>
  );
}
