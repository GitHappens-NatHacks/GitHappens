import { Check, RotateCcw, Save } from "lucide-react";
import { useEffect, useState } from "react";
import type { SettingsPayload, SettingsUpdate } from "../types/telemetry";
import { SteppedControl } from "./SteppedControl";

interface SensitivityPanelProps {
  settings: SettingsPayload;
  saving: boolean;
  onSave: (updates: SettingsUpdate) => Promise<void>;
}

export function SensitivityPanel({
  settings,
  saving,
  onSave,
}: SensitivityPanelProps) {
  const [draft, setDraft] = useState<SettingsPayload>(settings);
  const [savedNotice, setSavedNotice] = useState<string | null>(null);

  useEffect(() => {
    setDraft(settings);
  }, [settings]);

  const updateField = <K extends keyof SettingsPayload>(
    key: K,
    value: SettingsPayload[K]
  ) => {
    setSavedNotice(null);
    setDraft((prev) => ({ ...prev, [key]: value }));
  };

  const handleSave = async () => {
    await onSave({
      profile: draft.profile,
      tremor_strength: draft.tremor_strength,
      one_euro_min_cutoff: draft.one_euro_min_cutoff,
      one_euro_beta: draft.one_euro_beta,
      anti_drag: draft.anti_drag,
      anti_drag_threshold_px: draft.anti_drag_threshold_px,
      anti_drag_hold_ms: draft.anti_drag_hold_ms,
      gaze_dwell_ms: draft.gaze_dwell_ms,
      blink_select: draft.blink_select,
      gaze_source: draft.gaze_source,
    });
    setSavedNotice("Settings saved to SQLite and applied to active engine workers.");
  };

  const applyPreset = (preset: "parkinsons" | "als" | "custom") => {
    setSavedNotice(null);
    if (preset === "parkinsons") {
      setDraft((prev) => ({
        ...prev,
        profile: "parkinsons",
        tremor_strength: 115,
        one_euro_min_cutoff: 0.45,
        one_euro_beta: 0.003,
        anti_drag: true,
        anti_drag_threshold_px: 10,
        anti_drag_hold_ms: 350,
      }));
    } else if (preset === "als") {
      setDraft((prev) => ({
        ...prev,
        profile: "als",
        gaze_dwell_ms: 1100,
        blink_select: true,
      }));
    } else {
      setDraft((prev) => ({
        ...prev,
        profile: "custom",
        tremor_strength: 95,
        one_euro_min_cutoff: 0.65,
        one_euro_beta: 0.004,
        anti_drag_threshold_px: 8,
        anti_drag_hold_ms: 300,
        gaze_dwell_ms: 1100,
      }));
    }
  };

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-[var(--tc-ink)]">
            Sensitivity &amp; Filter Tuning
          </h2>
          <p className="mt-1 text-base text-[var(--tc-ink-muted)]">
            Use the oversized minus and plus buttons to step each threshold safely without dragging sliders.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-4">
          <button
            type="button"
            aria-pressed={draft.profile === "parkinsons"}
            onClick={() => applyPreset("parkinsons")}
            className={`min-h-14 rounded-xl border-2 px-5 text-base font-bold ${
              draft.profile === "parkinsons"
                ? "border-[var(--tc-primary)] bg-[var(--tc-mint)] text-[var(--tc-primary)]"
                : "border-[var(--tc-border-strong)] bg-[var(--tc-surface)] text-[var(--tc-ink)] hover:bg-[var(--tc-surface-alt)]"
            }`}
          >
            Parkinson&apos;s Preset
          </button>
          <button
            type="button"
            aria-pressed={draft.profile === "als"}
            onClick={() => applyPreset("als")}
            className={`min-h-14 rounded-xl border-2 px-5 text-base font-bold ${
              draft.profile === "als"
                ? "border-[var(--tc-primary)] bg-[var(--tc-mint)] text-[var(--tc-primary)]"
                : "border-[var(--tc-border-strong)] bg-[var(--tc-surface)] text-[var(--tc-ink)] hover:bg-[var(--tc-surface-alt)]"
            }`}
          >
            Hands-Free Preset
          </button>
          <button
            type="button"
            onClick={() => applyPreset("custom")}
            className="inline-flex min-h-14 items-center gap-2 rounded-xl border-2 border-[var(--tc-border-strong)] bg-[var(--tc-surface)] px-5 text-base font-bold text-[var(--tc-ink)] hover:bg-[var(--tc-surface-alt)]"
          >
            <RotateCcw className="h-5 w-5" aria-hidden="true" />
            <span>Reset Defaults</span>
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <SteppedControl
          id="tremor-strength"
          label="Stabilization Strength"
          description="Overall One Euro dampening blend applied to pointer movement."
          value={draft.tremor_strength}
          min={0}
          max={200}
          step={5}
          unit="%"
          onChange={(v) => updateField("tremor_strength", v)}
        />

        <SteppedControl
          id="min-cutoff"
          label="One Euro Min Cutoff"
          description="Lower cutoff increases resting stillness against 4-7 Hz hand tremor."
          value={draft.one_euro_min_cutoff}
          min={0.05}
          max={2.0}
          step={0.05}
          decimals={2}
          unit="Hz"
          onChange={(v) => updateField("one_euro_min_cutoff", v)}
        />

        <SteppedControl
          id="one-euro-beta"
          label="One Euro Speed Coefficient (Beta)"
          description="Higher beta reduces lag during intentional fast pointer sweeps."
          value={draft.one_euro_beta}
          min={0.0}
          max={0.05}
          step={0.001}
          decimals={3}
          onChange={(v) => updateField("one_euro_beta", v)}
        />

        <SteppedControl
          id="dwell-ms"
          label="Gaze Dwell Click Timing"
          description="Time eyes or head pointer must hold on a button before clicking."
          value={draft.gaze_dwell_ms}
          min={600}
          max={2000}
          step={100}
          unit="ms"
          onChange={(v) => updateField("gaze_dwell_ms", v)}
        />

        <SteppedControl
          id="antidrag-px"
          label="Anti-Drag Slip Threshold"
          description="Minimum pixel excursion before accidental jitter counts as a drag attempt."
          value={draft.anti_drag_threshold_px}
          min={2}
          max={40}
          step={1}
          unit="px"
          onChange={(v) => updateField("anti_drag_threshold_px", v)}
        />

        <SteppedControl
          id="antidrag-hold"
          label="Intentional Hold Latch Time"
          description="Duration of steady coherent motion required to start a real drag."
          value={draft.anti_drag_hold_ms}
          min={100}
          max={1500}
          step={50}
          unit="ms"
          onChange={(v) => updateField("anti_drag_hold_ms", v)}
        />
      </div>

      {/* Binary Motor & Gaze Options */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <button
          type="button"
          aria-pressed={draft.anti_drag}
          onClick={() => updateField("anti_drag", !draft.anti_drag)}
          className={`flex min-h-16 items-center justify-between gap-4 rounded-2xl border-2 px-6 py-4 text-left text-base font-bold ${
            draft.anti_drag
              ? "border-[var(--tc-primary)] bg-[var(--tc-mint)] text-[var(--tc-ink)]"
              : "border-[var(--tc-border-strong)] bg-[var(--tc-surface)] text-[var(--tc-ink)]"
          }`}
        >
          <span>Anti-Drag Protection</span>
          <span>{draft.anti_drag ? "ON" : "OFF"}</span>
        </button>

        <button
          type="button"
          aria-pressed={draft.blink_select}
          onClick={() => updateField("blink_select", !draft.blink_select)}
          className={`flex min-h-16 items-center justify-between gap-4 rounded-2xl border-2 px-6 py-4 text-left text-base font-bold ${
            draft.blink_select
              ? "border-[var(--tc-primary)] bg-[var(--tc-mint)] text-[var(--tc-ink)]"
              : "border-[var(--tc-border-strong)] bg-[var(--tc-surface)] text-[var(--tc-ink)]"
          }`}
        >
          <span>Deliberate Blink Click</span>
          <span>{draft.blink_select ? "ON" : "OFF"}</span>
        </button>

        <button
          type="button"
          onClick={() =>
            updateField("gaze_source", draft.gaze_source === "head" ? "eyes" : "head")
          }
          className="flex min-h-16 items-center justify-between gap-4 rounded-2xl border-2 border-[var(--tc-border-strong)] bg-[var(--tc-surface)] px-6 py-4 text-left text-base font-bold text-[var(--tc-ink)] hover:bg-[var(--tc-surface-alt)]"
        >
          <span>Gaze Input Source</span>
          <span className="uppercase">{draft.gaze_source}</span>
        </button>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border-2 border-[var(--tc-border)] bg-[var(--tc-surface)] p-5">
        <div role="status" aria-live="polite" className="text-base font-semibold text-[var(--tc-primary)]">
          {savedNotice ? (
            <span className="inline-flex items-center gap-2">
              <Check className="h-5 w-5" aria-hidden="true" />
              {savedNotice}
            </span>
          ) : (
            <span className="text-[var(--tc-ink-muted)]">
              Changes take effect after clicking Save Settings.
            </span>
          )}
        </div>

        <button
          type="button"
          disabled={saving}
          onClick={() => void handleSave()}
          className="inline-flex min-h-14 items-center gap-3 rounded-xl bg-[var(--tc-primary)] px-8 text-lg font-bold text-white hover:bg-[var(--tc-primary-hover)] disabled:opacity-50"
        >
          <Save className="h-5 w-5" aria-hidden="true" />
          <span>{saving ? "Saving..." : "Save Settings"}</span>
        </button>
      </div>
    </div>
  );
}
