"use client";

import { DELIVERY_LOCATIONS } from "@/lib/constants";

interface HeaderProps {
  location: string;
  cartCount: number;
  onLocationChange: (address: string) => void;
  locationUnfamiliar: boolean;
}

export function Header({
  location,
  cartCount,
  onLocationChange,
  locationUnfamiliar,
}: HeaderProps) {
  return (
    <header className="sticky top-0 z-20 border-b border-gray-200 bg-white shadow-sm">
      <div className="mx-auto flex max-w-2xl items-center justify-between gap-3 px-4 py-3">
        <div className="flex min-w-0 items-center gap-2">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-blinkit-yellow text-lg font-black text-blinkit-green">
            b
          </div>
          <div className="min-w-0">
            <p className="text-xs font-semibold uppercase tracking-wide text-blinkit-green">
              Blinkit
            </p>
            <p className="truncate text-sm text-gray-600">
              Delivery in{" "}
              <span className="font-semibold text-gray-900">10 minutes</span>
            </p>
            <p className="truncate text-xs text-gray-500">
              {location}
              {locationUnfamiliar && (
                <span className="ml-1 font-medium text-orange-700">· new address</span>
              )}
            </p>
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-2">
          <select
            value={location}
            onChange={(e) => onLocationChange(e.target.value)}
            className="max-w-[9.5rem] truncate rounded-md border border-gray-200 bg-gray-50 px-2 py-1 text-xs text-gray-700"
            aria-label="Delivery address"
          >
            {DELIVERY_LOCATIONS.map((addr) => (
              <option key={addr} value={addr}>
                {addr}
              </option>
            ))}
          </select>
          <div className="relative flex h-10 w-10 items-center justify-center rounded-full bg-blinkit-green text-white">
            <svg
              className="h-5 w-5"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M3 3h2l.4 2M7 13h10l4-8H5.4M7 13L5.4 5M7 13l-2.293 2.293c-.63.63-.184 1.707.707 1.707H17m0 0a2 2 0 100 4 2 2 0 000-4zm-8 2a2 2 0 11-4 0 2 2 0 014 0z"
              />
            </svg>
            {cartCount > 0 && (
              <span className="absolute -right-1 -top-1 flex h-5 min-w-5 items-center justify-center rounded-full bg-blinkit-yellow px-1 text-xs font-bold text-gray-900">
                {cartCount}
              </span>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}
