"use client";

import { useState } from "react";
import type { SituationCandidate } from "@/lib/types";

export type SituationSelection =
  | { kind: "candidate"; candidate: SituationCandidate }
  | { kind: "custom"; text: string };

interface SituationPanelProps {
  candidates: SituationCandidate[];
  loading: boolean;
  onSubmit: (selection: SituationSelection) => void;
  onStockingUp: () => void;
  onDismiss: () => void;
}

export function SituationPanel({
  candidates,
  loading,
  onSubmit,
  onStockingUp,
  onDismiss,
}: SituationPanelProps) {
  const [selection, setSelection] = useState<SituationSelection>(() =>
    candidates.length > 0
      ? { kind: "candidate", candidate: candidates[0] }
      : { kind: "custom", text: "" },
  );
  const [customText, setCustomText] = useState("");

  const isSelected = (candidate: SituationCandidate) =>
    selection.kind === "candidate" && selection.candidate.id === candidate.id;

  const canSubmit =
    selection.kind === "candidate" ||
    (selection.kind === "custom" && customText.trim().length > 0);

  const handleSubmit = () => {
    if (selection.kind === "custom") {
      onSubmit({ kind: "custom", text: customText.trim() });
    } else {
      onSubmit(selection);
    }
  };

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <p className="text-xs font-medium text-gray-500">Pick what fits best</p>
        {candidates.map((candidate) => (
          <button
            key={candidate.id + candidate.label}
            type="button"
            disabled={loading}
            onClick={() => setSelection({ kind: "candidate", candidate })}
            className={`block w-full rounded-lg border px-3 py-2.5 text-left text-sm transition-colors disabled:opacity-50 ${
              isSelected(candidate)
                ? "border-blinkit-green bg-blinkit-green/5 ring-1 ring-blinkit-green"
                : "border-gray-200 bg-white hover:border-blinkit-green/50"
            }`}
          >
            <span className="font-medium text-gray-900">{candidate.label}</span>
            <span className="mt-0.5 block text-xs text-gray-500">{candidate.reasoning}</span>
          </button>
        ))}
      </div>

      <div className="space-y-2 border-t border-amber-200/60 pt-3">
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

      <button
        type="button"
        disabled={loading || !canSubmit}
        onClick={handleSubmit}
        className="w-full rounded-lg border border-blinkit-green bg-white py-2.5 text-sm font-semibold text-blinkit-green hover:bg-blinkit-green/5 disabled:opacity-50"
      >
        Submit
      </button>

      <div className="flex gap-2">
        <button
          type="button"
          disabled={loading}
          onClick={onStockingUp}
          className="flex-1 rounded-lg border border-gray-200 bg-white py-2 text-sm text-gray-700 hover:bg-gray-50 disabled:opacity-50"
        >
          Just stocking up
        </button>
        <button
          type="button"
          disabled={loading}
          onClick={onDismiss}
          className="flex-1 rounded-lg border border-gray-200 bg-white py-2 text-sm text-gray-500 hover:bg-gray-50 disabled:opacity-50"
        >
          Dismiss
        </button>
      </div>
    </div>
  );
}
