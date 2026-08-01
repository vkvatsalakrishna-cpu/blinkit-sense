"use client";

import type { ScenarioPreset } from "@/lib/types";

interface ScenarioSelectorProps {
  presets: ScenarioPreset[];
  activePresetId: string | null;
  loading: boolean;
  onLoadPreset: (preset: ScenarioPreset) => void;
  onShuffle: () => void;
}

export function ScenarioSelector({
  presets,
  activePresetId,
  loading,
  onLoadPreset,
  onShuffle,
}: ScenarioSelectorProps) {
  return (
    <section className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900">Scenario</h2>
        <button
          type="button"
          onClick={onShuffle}
          disabled={loading}
          className="rounded-lg border border-gray-200 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
        >
          Shuffle ↻
        </button>
      </div>
      <p className="mb-3 text-xs text-gray-500">
        Load a preset cart to try the Sense flow.
      </p>
      <div className="flex flex-wrap gap-2">
        {presets.map((preset) => (
          <button
            key={preset.id}
            type="button"
            disabled={loading}
            onClick={() => onLoadPreset(preset)}
            className={`rounded-full px-3 py-1.5 text-sm font-medium transition-colors disabled:opacity-50 ${
              activePresetId === preset.id
                ? "bg-blinkit-green text-white"
                : "bg-gray-100 text-gray-700 hover:bg-gray-200"
            }`}
          >
            {preset.label}
          </button>
        ))}
      </div>
    </section>
  );
}
