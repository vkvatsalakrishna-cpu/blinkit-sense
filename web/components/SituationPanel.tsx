"use client";

import { useState } from "react";
import type { SituationCandidate } from "@/lib/types";

export const BUDGET_CEILING = 5000;

export function budgetFilterPayload(
  min: number,
  max: number,
): { min_price?: number; max_price?: number } {
  const payload: { min_price?: number; max_price?: number } = {};
  if (min > 0) payload.min_price = min;
  if (max < BUDGET_CEILING) payload.max_price = max;
  return payload;
}

type BudgetChipId = "any" | "under300" | "mid" | "over1000";

const BUDGET_CHIPS: { id: BudgetChipId; label: string; min: number; max: number }[] = [
  { id: "any", label: "Any", min: 0, max: BUDGET_CEILING },
  { id: "under300", label: "Under ₹300", min: 0, max: 300 },
  { id: "mid", label: "₹300–1,000", min: 300, max: 1000 },
  { id: "over1000", label: "₹1,000+", min: 1000, max: BUDGET_CEILING },
];

function budgetChipFromMinMax(min: number, max: number): BudgetChipId {
  if (min === 0 && max >= BUDGET_CEILING) return "any";
  if (min === 0 && max === 300) return "under300";
  if (min === 300 && max === 1000) return "mid";
  if (min === 1000 && max >= BUDGET_CEILING) return "over1000";
  return "any";
}

export type SituationSelection =
  | { kind: "candidate"; candidate: SituationCandidate }
  | { kind: "custom"; text: string };

export type SituationSubmitPayload = {
  selection: SituationSelection;
  min_price?: number;
  max_price?: number;
};

export type SituationPanelInitialState = {
  selection: SituationSelection;
  customText: string;
  budgetMin: number;
  budgetMax: number;
};

interface SituationPanelProps {
  candidates: SituationCandidate[];
  loading: boolean;
  initialState?: SituationPanelInitialState;
  onSubmit: (payload: SituationSubmitPayload) => void;
  onStockingUp: () => void;
  onDismiss: () => void;
}

function SparkleIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 16 16"
      fill="currentColor"
      aria-hidden
    >
      <path d="M8 0.5L9.2 5.4L14 6.5L9.2 7.6L8 12.5L6.8 7.6L2 6.5L6.8 5.4L8 0.5Z" />
      <path
        d="M13 2.5L13.6 4.6L15.5 5.2L13.6 5.8L13 7.9L12.4 5.8L10.5 5.2L12.4 4.6L13 2.5Z"
        opacity="0.85"
      />
    </svg>
  );
}

export function SenseIntro() {
  return (
    <div>
      <p className="font-caveat text-[20px] italic leading-tight text-blinkit-green">
        Tell us the occasion
      </p>
      <p className="mt-1 text-sm text-gray-500">
        We&apos;ll work out what else you need
      </p>
    </div>
  );
}

function resolveInitialSelection(
  candidates: SituationCandidate[],
  initialState?: SituationPanelInitialState,
): SituationSelection {
  if (!initialState) {
    return candidates.length > 0
      ? { kind: "candidate", candidate: candidates[0] }
      : { kind: "custom", text: "" };
  }
  if (initialState.selection.kind === "custom") {
    return {
      kind: "custom",
      text: initialState.customText || initialState.selection.text,
    };
  }

  const savedCandidate = initialState.selection.candidate;
  const match = candidates.find((c) => c.id === savedCandidate.id);
  if (match) {
    return { kind: "candidate", candidate: match };
  }
  return candidates.length > 0
    ? { kind: "candidate", candidate: candidates[0] }
    : { kind: "candidate", candidate: savedCandidate };
}

export function SituationPanel({
  candidates,
  loading,
  initialState,
  onSubmit,
  onStockingUp,
  onDismiss,
}: SituationPanelProps) {
  const [selection, setSelection] = useState<SituationSelection>(() =>
    resolveInitialSelection(candidates, initialState),
  );
  const [customText, setCustomText] = useState(
    () => initialState?.customText ?? "",
  );
  const [budgetChip, setBudgetChip] = useState<BudgetChipId>(() =>
    budgetChipFromMinMax(
      initialState?.budgetMin ?? 0,
      initialState?.budgetMax ?? BUDGET_CEILING,
    ),
  );

  const isSelected = (candidate: SituationCandidate) =>
    selection.kind === "candidate" && selection.candidate.id === candidate.id;

  const canSubmit =
    selection.kind === "candidate" ||
    (selection.kind === "custom" && customText.trim().length > 0);

  const handleSubmit = () => {
    const chip = BUDGET_CHIPS.find((c) => c.id === budgetChip)!;
    const budget = budgetFilterPayload(chip.min, chip.max);
    if (selection.kind === "custom") {
      onSubmit({
        selection: { kind: "custom", text: customText.trim() },
        ...budget,
      });
    } else {
      onSubmit({ selection, ...budget });
    }
  };

  return (
    <div className="space-y-6">
      <SenseIntro />

      <div className="-mx-4 flex gap-4 overflow-x-auto px-4 pb-1 md:mx-0 md:flex-wrap md:overflow-visible md:px-0">
        {candidates.map((candidate) => {
          const selected = isSelected(candidate);
          return (
            <div
              key={candidate.id + candidate.label}
              className="w-[11.5rem] shrink-0 md:w-auto md:max-w-[13rem]"
            >
              <button
                type="button"
                disabled={loading}
                onClick={() => setSelection({ kind: "candidate", candidate })}
                className={`group flex w-full items-center gap-1.5 rounded-full px-3.5 py-2 text-left text-sm font-medium transition-colors disabled:opacity-50 ${
                  selected
                    ? "border border-blinkit-green bg-blinkit-green/10 text-gray-900"
                    : "border border-transparent bg-white text-gray-900 [background-clip:padding-box,border-box] [background-origin:border-box] [background-image:linear-gradient(white,white),linear-gradient(to_right,rgba(12,131,31,0.45),rgba(190,242,100,0.75))]"
                }`}
              >
                <SparkleIcon
                  className={`h-3.5 w-3.5 shrink-0 ${
                    selected ? "text-blinkit-green" : "text-blinkit-green"
                  }`}
                />
                <span className="leading-snug">{candidate.label}</span>
              </button>
              <p className="mt-1.5 px-1 text-xs leading-snug text-gray-500">
                {candidate.reasoning}
              </p>
            </div>
          );
        })}
      </div>

      <div className="space-y-2">
        <label className="block text-xs font-medium text-gray-600">
          Or describe your situation
        </label>
        <input
          type="text"
          value={customText}
          onChange={(e) => {
            setCustomText(e.target.value);
            if (e.target.value.trim()) {
              setSelection({ kind: "custom", text: e.target.value });
            }
          }}
          onFocus={() => {
            if (customText.trim()) {
              setSelection({ kind: "custom", text: customText });
            }
          }}
          placeholder="e.g. hosting friends this weekend"
          className={`w-full rounded-lg border px-3 py-2 text-sm ${
            selection.kind === "custom"
              ? "border-blinkit-green ring-1 ring-blinkit-green"
              : "border-gray-200"
          }`}
        />
      </div>

      <div className="space-y-2">
        <p className="text-xs font-medium text-gray-600">Budget</p>
        <div className="flex flex-wrap gap-2">
          {BUDGET_CHIPS.map((chip) => {
            const selected = budgetChip === chip.id;
            return (
              <button
                key={chip.id}
                type="button"
                disabled={loading}
                onClick={() => setBudgetChip(chip.id)}
                className={`rounded-full border px-3 py-1.5 text-xs font-medium transition-colors disabled:opacity-50 ${
                  selected
                    ? "border-blinkit-green bg-blinkit-green/10 text-blinkit-green"
                    : "border-blinkit-green/30 bg-white text-gray-600"
                }`}
              >
                {chip.label}
              </button>
            );
          })}
        </div>
      </div>

      <button
        type="button"
        disabled={loading || !canSubmit}
        onClick={handleSubmit}
        className="w-full rounded-xl bg-[#0C831F] py-3.5 text-sm font-semibold text-white shadow-[0_4px_14px_rgba(12,131,31,0.22)] transition-all hover:-translate-y-px hover:shadow-[0_6px_20px_rgba(12,131,31,0.32)] disabled:cursor-not-allowed disabled:opacity-50"
      >
        {canSubmit ? "Show me what I need" : "Submit"}
      </button>

      <div className="mt-4 flex items-center justify-between">
        <button
          type="button"
          disabled={loading}
          onClick={onStockingUp}
          className="inline-flex items-center gap-1.5 bg-transparent text-sm font-medium text-blinkit-green transition-colors hover:text-[#0A6E19] disabled:opacity-50"
        >
          <SparkleIcon className="h-3.5 w-3.5 shrink-0" />
          Just stocking up
        </button>
        <button
          type="button"
          disabled={loading}
          onClick={onDismiss}
          className="text-sm text-gray-500 transition-colors hover:text-gray-700 hover:underline disabled:opacity-50"
        >
          Dismiss
        </button>
      </div>
    </div>
  );
}
