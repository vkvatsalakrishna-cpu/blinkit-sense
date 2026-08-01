"use client";

import { useState } from "react";
import type { SituationCandidate } from "@/lib/types";

interface SituationPanelProps {
  top: SituationCandidate;
  others: SituationCandidate[];
  loading: boolean;
  onConfirm: (candidate: SituationCandidate) => void;
  onCustomSubmit: (text: string) => void;
  onStockingUp: () => void;
  onDismiss: () => void;
}

export function SituationPanel({
  top,
  others,
  loading,
  onConfirm,
  onCustomSubmit,
  onStockingUp,
  onDismiss,
}: SituationPanelProps) {
  const [showOthers, setShowOthers] = useState(false);
  const [customText, setCustomText] = useState("");

  return (
    <section className="rounded-xl border border-amber-200 bg-blinkit-cream p-4 shadow-sm">
      <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-amber-800">
        Blinkit Sense
      </p>
      <p className="mb-4 text-sm text-gray-700">{top.reasoning}</p>

      <div className="mb-4 rounded-lg border border-blinkit-green/30 bg-white p-4">
        <p className="text-xs text-gray-500">Most likely</p>
        <p className="text-lg font-semibold text-gray-900">{top.label}</p>
        <button
          type="button"
          disabled={loading}
          onClick={() => onConfirm(top)}
          className="mt-3 w-full rounded-lg bg-blinkit-green py-2.5 text-sm font-semibold text-white hover:bg-blinkit-green-dark disabled:opacity-50"
        >
          {loading ? "Planning…" : `Confirm · ${top.label}`}
        </button>
      </div>

      {!showOthers ? (
        <button
          type="button"
          onClick={() => setShowOthers(true)}
          className="mb-3 text-sm font-medium text-blinkit-green hover:underline"
        >
          Something else?
        </button>
      ) : (
        <div className="mb-4 space-y-2">
          <p className="text-xs font-medium text-gray-500">Other possibilities</p>
          {others.map((candidate) => (
            <button
              key={candidate.id + candidate.label}
              type="button"
              disabled={loading}
              onClick={() => onConfirm(candidate)}
              className="block w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-left text-sm hover:border-blinkit-green disabled:opacity-50"
            >
              <span className="font-medium">{candidate.label}</span>
              <span className="mt-0.5 block text-xs text-gray-500">
                {candidate.reasoning}
              </span>
            </button>
          ))}
        </div>
      )}

      <div className="space-y-2 border-t border-amber-200/60 pt-3">
        <label className="block text-xs font-medium text-gray-600">
          Or describe your situation
        </label>
        <div className="flex gap-2">
          <input
            type="text"
            value={customText}
            onChange={(e) => setCustomText(e.target.value)}
            placeholder="e.g. hosting friends this weekend"
            className="min-w-0 flex-1 rounded-lg border border-gray-200 px-3 py-2 text-sm"
          />
          <button
            type="button"
            disabled={loading || !customText.trim()}
            onClick={() => {
              onCustomSubmit(customText.trim());
              setCustomText("");
            }}
            className="shrink-0 rounded-lg bg-gray-800 px-3 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            Go
          </button>
        </div>
        <div className="flex gap-2 pt-1">
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
    </section>
  );
}
