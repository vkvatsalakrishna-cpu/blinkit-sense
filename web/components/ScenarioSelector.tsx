"use client";

import type { ChangeEvent } from "react";
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
  const selectedId = activePresetId ?? presets[0]?.id ?? "";

  const handleChange = (event: ChangeEvent<HTMLSelectElement>) => {
    const preset = presets.find((p) => p.id === event.target.value);
    if (preset) onLoadPreset(preset);
  };

  return (
    <section className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h2 className="text-lg font-semibold text-gray-900">Scenario</h2>
        <button
          type="button"
          onClick={onShuffle}
          disabled={loading || presets.length === 0}
          className="shrink-0 rounded-lg border border-gray-200 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
        >
          Shuffle ↻
        </button>
      </div>
      <p className="mb-3 text-xs text-gray-500">
        Load a preset cart to try the Sense flow.
      </p>
      <select
        value={selectedId}
        disabled={loading || presets.length === 0}
        onChange={handleChange}
        className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2.5 text-sm text-gray-900 shadow-sm focus:border-blinkit-green focus:outline-none focus:ring-1 focus:ring-blinkit-green disabled:opacity-50"
        aria-label="Choose scenario"
      >
        {presets.map((preset) => (
          <option key={preset.id} value={preset.id}>
            {preset.label}
          </option>
        ))}
      </select>
    </section>
  );
}
