"use client";

import { useCallback, useMemo } from "react";

export const BUDGET_CEILING = 5000;
const STEP = 50;

export function budgetFilterPayload(
  min: number,
  max: number,
): { min_price?: number; max_price?: number } {
  const payload: { min_price?: number; max_price?: number } = {};
  if (min > 0) payload.min_price = min;
  if (max < BUDGET_CEILING) payload.max_price = max;
  return payload;
}

function formatBudget(value: number, isMaxHandle: boolean): string {
  if (isMaxHandle && value >= BUDGET_CEILING) return "₹5,000+";
  return `₹${value.toLocaleString("en-IN")}`;
}

interface BudgetRangeSliderProps {
  min: number;
  max: number;
  onChange: (min: number, max: number) => void;
}

export function BudgetRangeSlider({ min, max, onChange }: BudgetRangeSliderProps) {
  const isFiltered = min > 0 || max < BUDGET_CEILING;

  const rangeLabel = useMemo(() => {
    if (!isFiltered) return "No filter";
    return `${formatBudget(min, false)} – ${formatBudget(max, true)}`;
  }, [isFiltered, min, max]);

  const handleMinChange = useCallback(
    (value: number) => {
      onChange(Math.min(value, max), max);
    },
    [max, onChange],
  );

  const handleMaxChange = useCallback(
    (value: number) => {
      onChange(min, Math.max(value, min));
    },
    [min, onChange],
  );

  const minPercent = (min / BUDGET_CEILING) * 100;
  const maxPercent = (max / BUDGET_CEILING) * 100;

  return (
    <div className="space-y-2 border-t border-amber-200/60 pt-3">
      <div className="flex items-baseline justify-between gap-2">
        <label className="text-xs font-medium text-gray-600">
          Budget per item (optional)
        </label>
        <span className="text-xs font-medium text-gray-800">{rangeLabel}</span>
      </div>

      <div className="relative mx-1 h-7">
        <div className="absolute top-1/2 h-1.5 w-full -translate-y-1/2 rounded-full bg-gray-200" />
        <div
          className="absolute top-1/2 h-1.5 -translate-y-1/2 rounded-full bg-blinkit-green/70"
          style={{
            left: `${minPercent}%`,
            width: `${Math.max(0, maxPercent - minPercent)}%`,
          }}
        />
        <input
          type="range"
          min={0}
          max={BUDGET_CEILING}
          step={STEP}
          value={min}
          onChange={(e) => handleMinChange(Number(e.target.value))}
          aria-label="Minimum budget per item"
          className="budget-range-input pointer-events-none absolute inset-x-0 top-0 h-7 w-full appearance-none bg-transparent"
        />
        <input
          type="range"
          min={0}
          max={BUDGET_CEILING}
          step={STEP}
          value={max}
          onChange={(e) => handleMaxChange(Number(e.target.value))}
          aria-label="Maximum budget per item"
          className="budget-range-input pointer-events-none absolute inset-x-0 top-0 h-7 w-full appearance-none bg-transparent"
        />
      </div>

      <div className="flex justify-between text-[10px] text-gray-400">
        <span>₹0</span>
        <span>₹5,000+</span>
      </div>
    </div>
  );
}
