import { Check, ChevronDown, ChevronUp, Monitor, Plus, RotateCcw, Save, X } from "lucide-react";
import { useEffect, useState } from "react";
import { fetchDisplays } from "../api/client";
import { CLINICAL_PRESETS, type ClinicalPreset } from "../presets";
import type {
  BypassKeyOption,
  DisplaysResponse,
  PrecisionKeyOption,
  SettingsPayload,
  SettingsUpdate,
} from "../types/telemetry";
import { SteppedControl } from "./SteppedControl";

interface SensitivityPanelProps {
  settings: SettingsPayload;
  saving: boolean;
  onSave: (updates: SettingsUpdate) => Promise<void>;
}

const SUGGESTED_EXCLUDED_APPS = ["Figma", "Photoshop", "Illustrator", "Blender", "Procreate"];
const BYPASS_OPTIONS: { value: BypassKeyOption; label: string }[] = [
  { value: "alt", label: "Alt / Option" },
  { value: "fn", label: "Fn (macOS)" },
  { value: "shift", label: "Shift" },
  { value: "ctrl", label: "Ctrl" },
  { value: "none", label: "Disabled" },
];
const PRECISION_OPTIONS: { value: PrecisionKeyOption; label: string }[] = [
  { value: "none", label: "Disabled" },
  { value: "shift", label: "Shift (0.35x speed)" },
  { value: "ctrl", label: "Ctrl (0.35x speed)" },
  { value: "alt", label: "Alt / Option (0.35x speed)" },
];

export function SensitivityPanel({
  settings,
  saving,
  onSave,
}: SensitivityPanelProps) {
  const [draft, setDraft] = useState<SettingsPayload>(settings);
  const [savedNotice, setSavedNotice] = useState<string | null>(null);
  const [advancedOpen, setAdvancedOpen] = useState<boolean>(false);
  const [displaySummary, setDisplaySummary] = useState<DisplaysResponse | null>(null);
  const [newAppInput, setNewAppInput] = useState<string>("");

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

  const addExcludedApp = (appName: string) => {
    const trimmed = appName.trim();
    if (!trimmed) {
      return;
    }
    const exists = draft.excluded_apps.some(
      (item) => item.toLowerCase() === trimmed.toLowerCase()
    );
    if (!exists) {
      updateField("excluded_apps", [...draft.excluded_apps, trimmed]);
    }
    setNewAppInput("");
  };

  const removeExcludedApp = (appName: string) => {
    updateField(
      "excluded_apps",
      draft.excluded_apps.filter((item) => item !== appName)
    );
  };

  const handleSave = async () => {
    await onSave({
      profile: draft.profile,
      tremor_strength: draft.tremor_strength,
      one_euro_min_cutoff: draft.one_euro_min_cutoff,
      one_euro_beta: draft.one_euro_beta,
      adaptive_smoothing: draft.adaptive_smoothing,
      anti_drag: draft.anti_drag,
      anti_drag_threshold_px: draft.anti_drag_threshold_px,
      anti_drag_hold_ms: draft.anti_drag_hold_ms,
      click_freeze_ms: draft.click_freeze_ms,
      click_debounce_ms: draft.click_debounce_ms,
      right_click_guard: draft.right_click_guard,
      scroll_smoothing: draft.scroll_smoothing,
      gravity_wells: draft.gravity_wells,
      gravity_strength: draft.gravity_strength,
      bypass_key: draft.bypass_key,
      precision_key: draft.precision_key,
      excluded_apps: draft.excluded_apps,
      gaze_dwell_ms: draft.gaze_dwell_ms,
      blink_select: draft.blink_select,
      gaze_source: draft.gaze_source,
      global_shortcut: draft.global_shortcut,
      resume_stabilization_on_launch: draft.resume_stabilization_on_launch,
      minimize_to_tray: draft.minimize_to_tray,
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
      adaptive_smoothing: true,
      anti_drag: true,
      anti_drag_threshold_px: 8,
      anti_drag_hold_ms: 180,
      click_freeze_ms: 180,
      click_debounce_ms: 70,
      right_click_guard: true,
      scroll_smoothing: true,
      gravity_wells: true,
      gravity_strength: 35,
      bypass_key: "alt",
      precision_key: "none",
      excluded_apps: [],
      gaze_dwell_ms: 1100,
      global_shortcut: "CommandOrControl+Shift+S",
      resume_stabilization_on_launch: false,
      minimize_to_tray: true,
    }));
  };

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-[var(--tc-ink)]">
            Comfort Presets &amp; Everyday Tuning
          </h2>
          <p className="mt-1 text-base text-[var(--tc-ink-muted)]">
            Pick a preset matching how your hands feel right now, configure hold-to-bypass and excluded apps, or open Advanced Tuning.
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

        <button
          type="button"
          aria-pressed={draft.scroll_smoothing}
          onClick={() => updateField("scroll_smoothing", !draft.scroll_smoothing)}
          className={`flex min-h-16 items-center justify-between gap-4 rounded-lg border-2 px-6 py-4 text-left text-base font-bold ${
            draft.scroll_smoothing
              ? "border-[var(--tc-primary)] bg-[var(--tc-mint)] text-[var(--tc-ink)]"
              : "border-[var(--tc-border-strong)] bg-[var(--tc-surface)] text-[var(--tc-ink)]"
          }`}
        >
          <span>Scroll Jitter Guard</span>
          <span>{draft.scroll_smoothing ? "ON" : "OFF"}</span>
        </button>

        <button
          type="button"
          aria-pressed={draft.right_click_guard}
          onClick={() => updateField("right_click_guard", !draft.right_click_guard)}
          className={`flex min-h-16 items-center justify-between gap-4 rounded-lg border-2 px-6 py-4 text-left text-base font-bold ${
            draft.right_click_guard
              ? "border-[var(--tc-primary)] bg-[var(--tc-mint)] text-[var(--tc-ink)]"
              : "border-[var(--tc-border-strong)] bg-[var(--tc-surface)] text-[var(--tc-ink)]"
          }`}
        >
          <span>Right-Click Twitch Guard</span>
          <span>{draft.right_click_guard ? "ON" : "OFF"}</span>
        </button>

        <button
          type="button"
          aria-pressed={draft.adaptive_smoothing}
          onClick={() => updateField("adaptive_smoothing", !draft.adaptive_smoothing)}
          className={`flex min-h-16 items-center justify-between gap-4 rounded-lg border-2 px-6 py-4 text-left text-base font-bold ${
            draft.adaptive_smoothing
              ? "border-[var(--tc-primary)] bg-[var(--tc-mint)] text-[var(--tc-ink)]"
              : "border-[var(--tc-border-strong)] bg-[var(--tc-surface)] text-[var(--tc-ink)]"
          }`}
        >
          <span>Smooth Adaptive Ramping</span>
          <span>{draft.adaptive_smoothing ? "ON" : "OFF"}</span>
        </button>
      </div>

      {/* Everyday Workflow: Bypass Key, Precision Mode, Tray & Exclusions */}
      <section className="space-y-5 border-t-2 border-[var(--tc-border)] pt-6">
        <h3 className="text-xl font-bold text-[var(--tc-ink)]">
          Everyday Workflow, Hotkeys &amp; App Exclusions
        </h3>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <div className="rounded-lg border-2 border-[var(--tc-border)] bg-[var(--tc-surface)] p-4">
            <label htmlFor="bypass-key-select" className="block text-sm font-bold text-[var(--tc-ink)]">
              Hold-to-Bypass Key
            </label>
            <p className="mt-1 text-xs text-[var(--tc-ink-muted)]">
              Hold this modifier key to temporarily pause smoothing for freehand drawing.
            </p>
            <select
              id="bypass-key-select"
              value={draft.bypass_key}
              onChange={(e) => updateField("bypass_key", e.target.value as BypassKeyOption)}
              className="mt-3 min-h-12 w-full rounded-lg border-2 border-[var(--tc-border-strong)] bg-[var(--tc-bg)] px-3 text-base font-semibold text-[var(--tc-ink)]"
            >
              {BYPASS_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          <div className="rounded-lg border-2 border-[var(--tc-border)] bg-[var(--tc-surface)] p-4">
            <label htmlFor="precision-key-select" className="block text-sm font-bold text-[var(--tc-ink)]">
              Precision Slow-Mode Key
            </label>
            <p className="mt-1 text-xs text-[var(--tc-ink-muted)]">
              Hold to scale cursor speed down to 35% for fine-grained button targeting.
            </p>
            <select
              id="precision-key-select"
              value={draft.precision_key}
              onChange={(e) => updateField("precision_key", e.target.value as PrecisionKeyOption)}
              className="mt-3 min-h-12 w-full rounded-lg border-2 border-[var(--tc-border-strong)] bg-[var(--tc-bg)] px-3 text-base font-semibold text-[var(--tc-ink)]"
            >
              {PRECISION_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          <div className="rounded-lg border-2 border-[var(--tc-border)] bg-[var(--tc-surface)] p-4">
            <label htmlFor="global-shortcut-input" className="block text-sm font-bold text-[var(--tc-ink)]">
              Global Toggle Hotkey
            </label>
            <p className="mt-1 text-xs text-[var(--tc-ink-muted)]">
              Emergency Stop All is always bound to Command/Ctrl+Alt+Esc.
            </p>
            <input
              id="global-shortcut-input"
              type="text"
              value={draft.global_shortcut}
              onChange={(e) => updateField("global_shortcut", e.target.value)}
              className="mt-3 min-h-12 w-full rounded-lg border-2 border-[var(--tc-border-strong)] bg-[var(--tc-bg)] px-3 text-base font-semibold text-[var(--tc-ink)]"
            />
          </div>
        </div>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <button
            type="button"
            aria-pressed={draft.minimize_to_tray}
            onClick={() => updateField("minimize_to_tray", !draft.minimize_to_tray)}
            className={`flex min-h-16 items-center justify-between gap-4 rounded-lg border-2 px-6 py-4 text-left text-base font-bold ${
              draft.minimize_to_tray
                ? "border-[var(--tc-primary)] bg-[var(--tc-mint)] text-[var(--tc-ink)]"
                : "border-[var(--tc-border-strong)] bg-[var(--tc-surface)] text-[var(--tc-ink)]"
            }`}
          >
            <div>
              <span className="block">Keep Running in Tray on Window Close</span>
              <span className="text-xs font-normal text-[var(--tc-ink-muted)]">
                Closing the window hides to menu bar / tray so smoothing &amp; logging stay active.
              </span>
            </div>
            <span>{draft.minimize_to_tray ? "ON" : "OFF"}</span>
          </button>

          <button
            type="button"
            aria-pressed={draft.resume_stabilization_on_launch}
            onClick={() =>
              updateField("resume_stabilization_on_launch", !draft.resume_stabilization_on_launch)
            }
            className={`flex min-h-16 items-center justify-between gap-4 rounded-lg border-2 px-6 py-4 text-left text-base font-bold ${
              draft.resume_stabilization_on_launch
                ? "border-[var(--tc-primary)] bg-[var(--tc-mint)] text-[var(--tc-ink)]"
                : "border-[var(--tc-border-strong)] bg-[var(--tc-surface)] text-[var(--tc-ink)]"
            }`}
          >
            <div>
              <span className="block">Resume OS Smoothing on Launch</span>
              <span className="text-xs font-normal text-[var(--tc-ink-muted)]">
                Automatically re-arm system cursor interception when ClearCursor starts.
              </span>
            </div>
            <span>{draft.resume_stabilization_on_launch ? "ON" : "OFF"}</span>
          </button>
        </div>

        {/* Per-App Exclusions */}
        <div className="rounded-lg border-2 border-[var(--tc-border)] bg-[var(--tc-surface)] p-5">
          <h4 className="text-base font-bold text-[var(--tc-ink)]">
            Per-App Auto-Exclusions (Creative, Drawing &amp; Gaming Apps)
          </h4>
          <p className="mt-1 text-sm text-[var(--tc-ink-muted)]">
            ClearCursor automatically bypasses cursor interception whenever one of these apps is in focus.
          </p>

          <div className="mt-3 flex flex-wrap gap-2">
            {draft.excluded_apps.map((app) => (
              <span
                key={app}
                className="inline-flex items-center gap-2 rounded-full border border-[var(--tc-primary)] bg-[var(--tc-mint)] px-3.5 py-1.5 text-sm font-bold text-[var(--tc-primary)]"
              >
                <span>{app}</span>
                <button
                  type="button"
                  aria-label={`Remove excluded app ${app}`}
                  onClick={() => removeExcludedApp(app)}
                  className="rounded-full p-0.5 hover:bg-white"
                >
                  <X className="h-4 w-4" aria-hidden="true" />
                </button>
              </span>
            ))}
            {draft.excluded_apps.length === 0 && (
              <span className="text-sm text-[var(--tc-ink-muted)]">
                No excluded apps configured yet.
              </span>
            )}
          </div>

          <div className="mt-4 flex flex-wrap items-center gap-3">
            <input
              type="text"
              value={newAppInput}
              onChange={(e) => setNewAppInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  addExcludedApp(newAppInput);
                }
              }}
              placeholder="App name or bundle ID (e.g. Figma, Photoshop)"
              className="min-h-12 min-w-[260px] flex-1 rounded-lg border-2 border-[var(--tc-border-strong)] bg-[var(--tc-bg)] px-3.5 text-base text-[var(--tc-ink)]"
            />
            <button
              type="button"
              onClick={() => addExcludedApp(newAppInput)}
              className="inline-flex min-h-12 items-center gap-2 rounded-lg bg-[var(--tc-primary)] px-4 text-sm font-bold text-white hover:bg-[var(--tc-primary-hover)]"
            >
              <Plus className="h-4 w-4" aria-hidden="true" />
              <span>Add App</span>
            </button>
          </div>

          <div className="mt-3 flex flex-wrap items-center gap-2">
            <span className="text-xs font-semibold text-[var(--tc-ink-muted)]">Quick add:</span>
            {SUGGESTED_EXCLUDED_APPS.map((name) => (
              <button
                key={name}
                type="button"
                onClick={() => addExcludedApp(name)}
                className="rounded-md border border-[var(--tc-border-strong)] bg-[var(--tc-surface-alt)] px-2.5 py-1 text-xs font-semibold text-[var(--tc-ink)] hover:bg-[var(--tc-mint)]"
              >
                + {name}
              </button>
            ))}
          </div>
        </div>
      </section>

      {/* Expandable Advanced Tuning Section */}
      <section className="border-t-2 border-[var(--tc-border)] pt-6">
        <button
          type="button"
          aria-expanded={advancedOpen}
          onClick={() => setAdvancedOpen((prev) => !prev)}
          className="flex min-h-14 w-full items-center justify-between gap-4 rounded-lg border-2 border-[var(--tc-border-strong)] bg-[var(--tc-surface)] px-5 text-left text-lg font-bold text-[var(--tc-ink)] hover:bg-[var(--tc-mint)]"
        >
          <span>Advanced Tuning (One Euro, Click-Freeze, Bounce Guard, Gravity Wells &amp; Dwell)</span>
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
              id="click-debounce-ms"
              label="Double-Click Bounce Guard"
              description="Blocks involuntary repeat clicks faster than this interval after button release."
              value={draft.click_debounce_ms}
              min={0}
              max={250}
              step={10}
              unit="ms"
              onChange={(v) => updateField("click_debounce_ms", v)}
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
              description="Lower cutoff increases stillness against 4-12 Hz trembling."
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
              step={40}
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
