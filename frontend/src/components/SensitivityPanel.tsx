import { Check, ChevronDown, ChevronUp, Monitor, RotateCcw, Save } from "lucide-react";
import { useEffect, useState } from "react";
import { fetchDisplays } from "../api/client";
import { CLINICAL_PRESETS, type ClinicalPreset } from "../presets";
import type { DisplaysResponse, SettingsPayload, SettingsUpdate } from "../types/telemetry";
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
  const [advancedOpen, setAdvancedOpen] = useState<boolean>(false);
  const [displaySummary, setDisplaySummary] = useState<DisplaysResponse | null>(null);

  useEffect(() => {
    setDraft(settings);
  }, [settings]);

  useEffect(() => {
    let active = true;
    void fetchDisplays()
      .then((res) => {
        if (active) {
          setDisplaySummary(res);
        }
      })
      .catch(() => {
        // Ignore offline display lookup
      });
    return () => {
      active = false;
    };
  }, []);

  const updateField = <K extends keyof SettingsPayload>(
    key: K,
    value: SettingsPayload[K]
  ) => {
    setSavedNotice(null);
    setDraft((prev) => ({ ...prev, [key]: value }));
  };

  const handleApplyPreset = async (preset: ClinicalPreset) => {
    setSavedNotice(null);
    const merged = { ...draft, ...preset.updates };
    setDraft(merged);
    await onSave(preset.updates);
    setSavedNotice(`Applied "${preset.label}" and persisted settings.`);
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
      click_freeze_ms: draft.click_freeze_ms,
      gravity_wells: draft.gravity_wells,
      gravity_strength: draft.gravity_strength,
      gaze_dwell_ms: draft.gaze_dwell_ms,
      blink_select: draft.blink_select,
      gaze_source: draft.gaze_source,
      global_shortcut: draft.global_shortcut,
    });
    setSavedNotice("Settings saved to SQLite and applied to active engine workers.");
  };

  const resetDefaults = () => {
    setSavedNotice(null);
    setDraft((prev) => ({
      ...prev,
      profile: "moderate",
      tremor_strength: 100,
      one_euro_min_cutoff: 0.6,
      one_euro_beta: 0.004,
      anti_drag: true,
      anti_drag_threshold_px: 8,
      anti_drag_hold_ms: 300,
      click_freeze_ms: 180,
      gravity_wells: true,
      gravity_strength: 35,
      gaze_dwell_ms: 1100,
      global_shortcut: "CommandOrControl+Shift+S",
    }));
  };

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-[var(--tc-ink)]">
            Comfort Presets &amp; Advanced Tuning
          </h2>
          <p className="mt-1 text-base text-[var(--tc-ink-muted)]">
            Pick a preset matching how your hands feel right now, or open Advanced Tuning for manual filter adjustment.
          </p>
        </div>

        <button
          type="button"
          onClick={resetDefaults}
          className="inline-flex min-h-14 items-center gap-2 rounded-lg border-2 border-[var(--tc-border-strong)] bg-[var(--tc-surface)] px-5 text-base font-bold text-[var(--tc-ink)] hover:bg-[var(--tc-surface-alt)]"
        >
          <RotateCcw className="h-5 w-5" aria-hidden="true" />
          <span>Reset Defaults</span>
        </button>
      </div>

      {/* One-Tap Medication State Presets */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {CLINICAL_PRESETS.map((preset) => {
          const selected = draft.profile === preset.id;
          return (
            <button
              key={preset.id}
              type="button"
              disabled={saving}
              aria-pressed={selected}
              onClick={() => void handleApplyPreset(preset)}
              className={`min-h-[96px] rounded-lg border-2 p-5 text-left transition-colors ${
                selected
                  ? "border-[var(--tc-primary)] bg-[var(--tc-mint)] text-[var(--tc-ink)]"
                  : "border-[var(--tc-border-strong)] bg-[var(--tc-surface)] text-[var(--tc-ink)] hover:bg-[var(--tc-surface-alt)]"
              }`}
            >
              <div className="flex items-center justify-between gap-4">
                <span className="text-lg font-bold">{preset.label}</span>
                <span
                  className={`rounded-sm px-3 py-1 text-xs font-bold uppercase ${
                    selected
                      ? "bg-[var(--tc-primary)] text-white"
                      : "bg-[var(--tc-surface-alt)] text-[var(--tc-ink)]"
                  }`}
                >
                  {selected ? "Active" : "Apply"}
                </span>
              </div>
              <p className="mt-1.5 text-sm text-[var(--tc-ink-muted)]">{preset.clinicalNote}</p>
            </button>
          );
        })}
      </div>

      {/* Core Everyday Toggles */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <button
          type="button"
          aria-pressed={draft.gravity_wells}
          onClick={() => updateField("gravity_wells", !draft.gravity_wells)}
          className={`flex min-h-16 items-center justify-between gap-4 rounded-lg border-2 px-6 py-4 text-left text-base font-bold ${
            draft.gravity_wells
              ? "border-[var(--tc-primary)] bg-[var(--tc-mint)] text-[var(--tc-ink)]"
              : "border-[var(--tc-border-strong)] bg-[var(--tc-surface)] text-[var(--tc-ink)]"
          }`}
        >
          <span>Button Magnetism (Gravity Wells)</span>
          <span>{draft.gravity_wells ? "ON" : "OFF"}</span>
        </button>

        <button
          type="button"
          aria-pressed={draft.anti_drag}
          onClick={() => updateField("anti_drag", !draft.anti_drag)}
          className={`flex min-h-16 items-center justify-between gap-4 rounded-lg border-2 px-6 py-4 text-left text-base font-bold ${
            draft.anti_drag
              ? "border-[var(--tc-primary)] bg-[var(--tc-mint)] text-[var(--tc-ink)]"
              : "border-[var(--tc-border-strong)] bg-[var(--tc-surface)] text-[var(--tc-ink)]"
          }`}
        >
          <span>Click-Freeze &amp; Anti-Drag</span>
          <span>{draft.anti_drag ? "ON" : "OFF"}</span>
        </button>

        <button
          type="button"
          onClick={() =>
            updateField("gaze_source", draft.gaze_source === "head" ? "eyes" : "head")
          }
          className="flex min-h-16 items-center justify-between gap-4 rounded-lg border-2 border-[var(--tc-border-strong)] bg-[var(--tc-surface)] px-6 py-4 text-left text-base font-bold text-[var(--tc-ink)] hover:bg-[var(--tc-surface-alt)]"
        >
          <span>Gaze Input Source</span>
          <span className="uppercase">{draft.gaze_source}</span>
        </button>
      </div>

      {/* Expandable Advanced Tuning Section (Flattened without outer nested box) */}
      <section className="border-t-2 border-[var(--tc-border)] pt-6">
        <button
          type="button"
          aria-expanded={advancedOpen}
          onClick={() => setAdvancedOpen((prev) => !prev)}
          className="flex min-h-14 w-full items-center justify-between gap-4 rounded-lg border-2 border-[var(--tc-border-strong)] bg-[var(--tc-surface)] px-5 text-left text-lg font-bold text-[var(--tc-ink)] hover:bg-[var(--tc-mint)]"
        >
          <span>Advanced Tuning (One Euro, Click-Freeze, Gravity Wells &amp; Dwell)</span>
          {advancedOpen ? (
            <ChevronUp className="h-6 w-6 shrink-0" aria-hidden="true" />
          ) : (
            <ChevronDown className="h-6 w-6 shrink-0" aria-hidden="true" />
          )}
        </button>

        {advancedOpen && (
          <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
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
              id="click-freeze-ms"
              label="Click-Freeze Duration"
              description="Locks coordinates briefly on MouseDown to stop slip-drags while clicking."
              value={draft.click_freeze_ms}
              min={0}
              max={400}
              step={20}
              unit="ms"
              onChange={(v) => updateField("click_freeze_ms", v)}
            />

            <SteppedControl
              id="gravity-strength"
              label="Gravity Well Magnetism"
              description="Gentle pull toward nearby buttons when slowing down to click."
              value={draft.gravity_strength}
              min={0}
              max={80}
              step={5}
              unit="%"
              onChange={(v) => updateField("gravity_strength", v)}
            />

            <SteppedControl
              id="min-cutoff"
              label="One Euro Min Cutoff"
              description="Lower cutoff increases stillness against 4-7 Hz trembling."
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
              description="Higher beta reduces lag during intentional wide pointer sweeps."
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
              description="Duration eyes or head pointer hold on a control before clicking."
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
              description="Pixel excursion threshold before jitter counts as a drag attempt."
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
              description="Coherent sweep duration required before starting an intentional drag."
              value={draft.anti_drag_hold_ms}
              min={100}
              max={1500}
              step={50}
              unit="ms"
              onChange={(v) => updateField("anti_drag_hold_ms", v)}
            />

            {displaySummary && displaySummary.displays.length > 0 && (
              <div className="border-t-2 border-[var(--tc-border)] pt-5">
                <div className="mb-3 flex items-center gap-2 text-sm font-bold uppercase tracking-wider text-[var(--tc-primary)]">
                  <Monitor className="h-4 w-4" aria-hidden="true" />
                  <span>
                    Active Displays ({displaySummary.displays.length}) &amp; Virtual Bounds (
                    {displaySummary.virtual_rect.width}x{displaySummary.virtual_rect.height})
                  </span>
                </div>
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  {displaySummary.displays.map((disp, idx) => (
                    <div
                      key={disp.id}
                      className="rounded-md border-2 border-[var(--tc-border)] bg-[var(--tc-surface)] px-4 py-3 text-sm"
                    >
                      <p className="font-bold text-[var(--tc-ink)]">
                        Display {idx + 1} {disp.is_primary ? "(Primary)" : "(External)"}
                      </p>
                      <p className="mt-0.5 tabular-nums text-[var(--tc-ink-muted)]">
                        {disp.width}x{disp.height} at ({disp.left}, {disp.top}) | {disp.refresh_hz} Hz |{" "}
                        {disp.scale_factor}x DPI
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </section>

      <div className="flex flex-wrap items-center justify-between gap-4 rounded-lg border-2 border-[var(--tc-border)] bg-[var(--tc-surface)] p-5">
        <div role="status" aria-live="polite" className="text-base font-semibold text-[var(--tc-primary)]">
          {savedNotice ? (
            <span className="inline-flex items-center gap-2">
              <Check className="h-5 w-5" aria-hidden="true" />
              {savedNotice}
            </span>
          ) : (
            <span className="text-[var(--tc-ink-muted)]">
              One-tap presets save immediately. Manual tuning changes apply when you click Save Settings.
            </span>
          )}
        </div>

        <button
          type="button"
          disabled={saving}
          onClick={() => void handleSave()}
          className="inline-flex min-h-14 items-center gap-3 rounded-lg bg-[var(--tc-primary)] px-8 text-lg font-bold text-white hover:bg-[var(--tc-primary-hover)] disabled:opacity-50"
        >
          <Save className="h-5 w-5" aria-hidden="true" />
          <span>{saving ? "Saving..." : "Save Settings"}</span>
        </button>
      </div>
    </div>
  );
}
