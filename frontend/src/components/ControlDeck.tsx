import {
  Activity,
  Camera,
  CheckCircle2,
  Eye,
  Hand,
  Magnet,
  MousePointerClick,
  ShieldCheck,
  Waves,
} from "lucide-react";
import { useRef, useState } from "react";
import { Area, AreaChart, ResponsiveContainer, Tooltip, YAxis } from "recharts";
import { pushSteadyHandSample } from "../api/client";
import type { ConnectionState, TelemetryPoint } from "../hooks/useTelemetry";
import { CLINICAL_PRESETS, type ClinicalPreset } from "../presets";
import type {
  EngineToggleRequest,
  SettingsPayload,
  SettingsUpdate,
  TelemetryFrame,
} from "../types/telemetry";

interface ControlDeckProps {
  settings: SettingsPayload;
  frame: TelemetryFrame | null;
  smoothedScore: number;
  smoothedTremorIndex: number;
  history: TelemetryPoint[];
  connectionState: ConnectionState;
  toggling: boolean;
  onToggle: (payload: EngineToggleRequest) => Promise<void>;
  onApplyPreset: (updates: SettingsUpdate) => Promise<void>;
  onStartCalibration: () => void;
}

export function ControlDeck({
  settings,
  frame,
  smoothedScore,
  smoothedTremorIndex,
  history,
  connectionState,
  toggling,
  onToggle,
  onApplyPreset,
  onStartCalibration,
}: ControlDeckProps) {
  const [padCursor, setPadCursor] = useState<{ x: number; y: number } | null>(null);
  const lastSentAtRef = useRef<number>(0);

  const steadyActive =
    frame?.stabilization_active ?? (settings.assistance_enabled && settings.steady_hand);
  const gazeActive = frame?.active_modes.gaze_control ?? settings.gaze_control;
  const simActive = frame?.active_modes.simulate_tremor ?? settings.simulate_tremor;
  const cameraRunning = frame?.gaze.running ?? false;
  const sysMouseActive = frame?.steadyhand.system_mouse_enabled ?? settings.system_mouse;

  const tremorHz = frame?.tremor_hz ?? null;
  const inParkinsonBand = tremorHz !== null && tremorHz >= 4 && tremorHz <= 7;
  const dampeningPct = Math.round(
    (frame?.steadyhand.strength ?? settings.tremor_strength / 100) * 100
  );
  const dragsPrevented = frame?.steadyhand.spastic_drags_prevented ?? 0;
  const gravityActive = frame?.steadyhand.gravity_well_active ?? false;
  const tapMode = frame?.steadyhand.os_tap_mode ?? "idle";
  const tapError = frame?.steadyhand.os_tap_error ?? null;

  const handlePadPointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = Math.round(e.clientX - rect.left);
    const y = Math.round(e.clientY - rect.top);
    setPadCursor({ x, y });

    const now = performance.now();
    if (now - lastSentAtRef.current >= 32) {
      lastSentAtRef.current = now;
      void pushSteadyHandSample(x, y).catch(() => undefined);
    }
  };

  const handleSelectPreset = async (preset: ClinicalPreset) => {
    await onApplyPreset(preset.updates);
    if (preset.id === "hands_free") {
      await onToggle({ gaze_control: true, camera: true, steady_hand: false, assistance_enabled: true });
    } else {
      await onToggle({ steady_hand: true, gaze_control: false, camera: false, assistance_enabled: true });
    }
  };

  const chartData =
    history.length > 0
      ? history.map((pt, idx) => ({ idx, score: pt.stabilityScore }))
      : [{ idx: 0, score: 100 }];

  return (
    <div className="space-y-8">
      {/* Medication State Quick-Switch Presets */}
      <section aria-labelledby="medication-presets-heading">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-4">
          <div>
            <h2 id="medication-presets-heading" className="text-2xl font-bold text-[var(--tc-ink)]">
              Comfort &amp; Medication State Presets
            </h2>
            <p className="mt-1 text-base text-[var(--tc-ink-muted)]">
              Choose how much stabilization you want right now with one large tap. Shortcut:{" "}
              <span className="font-bold text-[var(--tc-ink)]">{settings.global_shortcut}</span>
            </p>
          </div>
          <button
            type="button"
            onClick={onStartCalibration}
            className="inline-flex min-h-14 items-center gap-3 rounded-xl border-2 border-[var(--tc-border-strong)] bg-[var(--tc-surface)] px-6 text-base font-bold text-[var(--tc-ink)] hover:bg-[var(--tc-mint)]"
          >
            <Eye className="h-5 w-5 shrink-0" aria-hidden="true" />
            <span>
              {frame?.gaze.calibrated ? "Recalibrate Gaze" : "Run Gaze Calibration"}
            </span>
          </button>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {CLINICAL_PRESETS.map((preset) => {
            const selected = settings.profile === preset.id;
            return (
              <button
                key={preset.id}
                type="button"
                disabled={toggling}
                aria-pressed={selected}
                onClick={() => void handleSelectPreset(preset)}
                className={`flex min-h-[116px] flex-col justify-between rounded-2xl border-2 p-5 text-left transition-colors ${
                  selected
                    ? "border-[var(--tc-primary)] bg-[var(--tc-mint)] text-[var(--tc-ink)]"
                    : "border-[var(--tc-border-strong)] bg-[var(--tc-surface)] text-[var(--tc-ink)] hover:bg-[var(--tc-surface-alt)]"
                }`}
              >
                <div>
                  <span className="block text-lg font-bold">{preset.label}</span>
                  <span className="mt-1.5 block text-sm text-[var(--tc-ink-muted)]">
                    {preset.tagline}
                  </span>
                </div>
                <span
                  className={`mt-3 inline-block self-start rounded-lg px-3 py-1 text-xs font-bold uppercase ${
                    selected
                      ? "bg-[var(--tc-primary)] text-white"
                      : "bg-[var(--tc-surface-alt)] text-[var(--tc-ink)]"
                  }`}
                >
                  {selected ? "Active Preset" : "Select"}
                </span>
              </button>
            );
          })}
        </div>
      </section>

      {/* Primary Assistance Toggles */}
      <section aria-labelledby="primary-modes-heading">
        <h2 id="primary-modes-heading" className="mb-4 text-2xl font-bold text-[var(--tc-ink)]">
          Active System Assistance
        </h2>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <button
            type="button"
            disabled={toggling}
            aria-pressed={steadyActive}
            onClick={() =>
              void onToggle({ steady_hand: !steadyActive, assistance_enabled: true })
            }
            className={`flex min-h-[112px] w-full items-center justify-between gap-6 rounded-2xl border-2 p-6 text-left transition-colors ${
              steadyActive
                ? "border-[var(--tc-primary)] bg-[var(--tc-mint)] text-[var(--tc-ink)]"
                : "border-[var(--tc-border-strong)] bg-[var(--tc-surface)] text-[var(--tc-ink)] hover:bg-[var(--tc-surface-alt)]"
            }`}
          >
            <div className="flex items-start gap-4">
              <div
                className={`flex h-14 w-14 shrink-0 items-center justify-center rounded-xl ${
                  steadyActive
                    ? "bg-[var(--tc-primary)] text-white"
                    : "bg-[var(--tc-surface-alt)] text-[var(--tc-ink)]"
                }`}
              >
                <Hand className="h-7 w-7" aria-hidden="true" />
              </div>
              <div>
                <span className="block text-xl font-bold">SteadyHand Stabilization</span>
                <span className="mt-1 block text-base text-[var(--tc-ink-muted)]">
                  Adaptive smoothing, 180ms click-freeze, and button magnetism.
                </span>
              </div>
            </div>
            <span
              className={`shrink-0 rounded-xl px-4 py-2 text-base font-bold ${
                steadyActive
                  ? "bg-[var(--tc-primary)] text-white"
                  : "border-2 border-[var(--tc-border-strong)] bg-[var(--tc-surface-alt)] text-[var(--tc-ink)]"
              }`}
            >
              {steadyActive ? "ACTIVE" : "OFF"}
            </span>
          </button>

          <button
            type="button"
            disabled={toggling}
            aria-pressed={gazeActive}
            onClick={() =>
              void onToggle({
                gaze_control: !gazeActive,
                camera: !gazeActive,
                assistance_enabled: true,
              })
            }
            className={`flex min-h-[112px] w-full items-center justify-between gap-6 rounded-2xl border-2 p-6 text-left transition-colors ${
              gazeActive
                ? "border-[var(--tc-primary)] bg-[var(--tc-mint)] text-[var(--tc-ink)]"
                : "border-[var(--tc-border-strong)] bg-[var(--tc-surface)] text-[var(--tc-ink)] hover:bg-[var(--tc-surface-alt)]"
            }`}
          >
            <div className="flex items-start gap-4">
              <div
                className={`flex h-14 w-14 shrink-0 items-center justify-center rounded-xl ${
                  gazeActive
                    ? "bg-[var(--tc-primary)] text-white"
                    : "bg-[var(--tc-surface-alt)] text-[var(--tc-ink)]"
                }`}
              >
                <Camera className="h-7 w-7" aria-hidden="true" />
              </div>
              <div>
                <span className="block text-xl font-bold">GazeControl Tracking</span>
                <span className="mt-1 block text-base text-[var(--tc-ink-muted)]">
                  Webcam head and iris pointing with dwell or blink click.
                </span>
              </div>
            </div>
            <span
              className={`shrink-0 rounded-xl px-4 py-2 text-base font-bold ${
                gazeActive
                  ? "bg-[var(--tc-primary)] text-white"
                  : "border-2 border-[var(--tc-border-strong)] bg-[var(--tc-surface-alt)] text-[var(--tc-ink)]"
              }`}
            >
              {gazeActive ? (cameraRunning ? "TRACKING" : "ON") : "OFF"}
            </span>
          </button>
        </div>

        {/* OS Tap + Secondary Toggles */}
        <div className="mt-4 flex flex-wrap items-center gap-4">
          <button
            type="button"
            disabled={toggling}
            aria-pressed={sysMouseActive}
            onClick={() => void onToggle({ system_mouse: !sysMouseActive })}
            className={`inline-flex min-h-14 items-center gap-3 rounded-xl border-2 px-5 text-base font-bold ${
              sysMouseActive
                ? "border-[var(--tc-primary)] bg-[var(--tc-mint)] text-[var(--tc-primary)]"
                : "border-[var(--tc-border-strong)] bg-[var(--tc-surface)] text-[var(--tc-ink)] hover:bg-[var(--tc-surface-alt)]"
            }`}
          >
            <MousePointerClick className="h-5 w-5 shrink-0" aria-hidden="true" />
            <span>
              System-Wide Cursor Intercept: {sysMouseActive ? "ON" : "OFF"}
            </span>
          </button>

          <button
            type="button"
            disabled={toggling}
            aria-pressed={simActive}
            onClick={() => void onToggle({ simulate_tremor: !simActive })}
            className={`inline-flex min-h-14 items-center gap-3 rounded-xl border-2 px-5 text-base font-bold ${
              simActive
                ? "border-[var(--tc-alert)] bg-[var(--tc-alert-bg)] text-[var(--tc-alert)]"
                : "border-[var(--tc-border-strong)] bg-[var(--tc-surface)] text-[var(--tc-ink)] hover:bg-[var(--tc-surface-alt)]"
            }`}
          >
            <Waves className="h-5 w-5 shrink-0" aria-hidden="true" />
            <span>4-7 Hz Tremor Simulation: {simActive ? "ON" : "OFF"}</span>
          </button>

          <div className="inline-flex min-h-14 items-center gap-2 rounded-xl border-2 border-[var(--tc-border)] bg-[var(--tc-surface)] px-4 text-sm font-semibold text-[var(--tc-ink)]">
            <Magnet className="h-5 w-5 text-[var(--tc-primary)]" aria-hidden="true" />
            <span>
              Gravity Wells:{" "}
              {settings.gravity_wells
                ? gravityActive
                  ? `Locked (${(frame?.steadyhand.gravity_target_role ?? "Control").replace(/^AX/, "")})`
                  : "Armed"
                : "Off"}
            </span>
          </div>
        </div>

        {tapError && sysMouseActive && (
          <div
            role="status"
            className="mt-4 rounded-xl border-2 border-[var(--tc-alert)] bg-[var(--tc-alert-bg)] p-4 text-sm font-semibold text-[var(--tc-alert)]"
          >
            OS Interception ({tapMode}): {tapError}
          </div>
        )}
      </section>

      {/* Live Telemetry & Stability Monitor */}
      <section aria-labelledby="telemetry-heading">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-4">
          <h2 id="telemetry-heading" className="text-2xl font-bold text-[var(--tc-ink)]">
            Live Stability Monitor
          </h2>
          <span className="text-sm font-semibold text-[var(--tc-ink-muted)]">
            Stream: {connectionState === "connected" ? "25 Hz live" : connectionState} | OS Hook: {tapMode}
          </span>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div className="rounded-2xl border-2 border-[var(--tc-border)] bg-[var(--tc-surface)] p-5">
            <div className="flex items-center justify-between text-sm font-semibold text-[var(--tc-ink-muted)]">
              <span>Stability Score</span>
              <ShieldCheck className="h-5 w-5 text-[var(--tc-primary)]" aria-hidden="true" />
            </div>
            <p className="mt-3 text-4xl font-bold text-[var(--tc-ink)] tabular-nums">
              {smoothedScore.toFixed(1)}
              <span className="ml-1 text-lg font-semibold text-[var(--tc-ink-muted)]">/ 100</span>
            </p>
            <p className="mt-2 text-sm text-[var(--tc-ink-muted)]">
              {steadyActive ? "Smoothing active" : "Raw unfiltered cursor"}
            </p>
          </div>

          <div
            className={`rounded-2xl border-2 p-5 ${
              inParkinsonBand
                ? "border-[var(--tc-alert)] bg-[var(--tc-alert-bg)]"
                : "border-[var(--tc-border)] bg-[var(--tc-surface)]"
            }`}
          >
            <div className="flex items-center justify-between text-sm font-semibold text-[var(--tc-ink-muted)]">
              <span>Tremor Frequency</span>
              <Activity
                className={`h-5 w-5 ${
                  inParkinsonBand ? "text-[var(--tc-alert)]" : "text-[var(--tc-primary)]"
                }`}
                aria-hidden="true"
              />
            </div>
            <p className="mt-3 text-4xl font-bold text-[var(--tc-ink)] tabular-nums">
              {tremorHz !== null ? tremorHz.toFixed(2) : "0.00"}
              <span className="ml-1.5 text-lg font-semibold text-[var(--tc-ink-muted)]">Hz</span>
            </p>
            <p
              className={`mt-2 text-sm font-semibold ${
                inParkinsonBand ? "text-[var(--tc-alert)]" : "text-[var(--tc-ink-muted)]"
              }`}
            >
              {inParkinsonBand
                ? `4-7 Hz Welch power: ${smoothedTremorIndex.toFixed(1)}%`
                : "No sustained 4-7 Hz tremor"}
            </p>
          </div>

          <div className="rounded-2xl border-2 border-[var(--tc-border)] bg-[var(--tc-surface)] p-5">
            <div className="flex items-center justify-between text-sm font-semibold text-[var(--tc-ink-muted)]">
              <span>Dampening &amp; Click-Freeze</span>
              <CheckCircle2 className="h-5 w-5 text-[var(--tc-primary)]" aria-hidden="true" />
            </div>
            <p className="mt-3 text-4xl font-bold text-[var(--tc-ink)] tabular-nums">
              {dampeningPct}
              <span className="ml-1 text-lg font-semibold text-[var(--tc-ink-muted)]">%</span>
            </p>
            <p className="mt-2 text-sm text-[var(--tc-ink-muted)]">
              Drags prevented: <span className="font-bold tabular-nums">{dragsPrevented}</span>
              {frame?.steadyhand.click_freeze_active ? " | Click-Freeze locked" : ""}
            </p>
          </div>

          <div className="rounded-2xl border-2 border-[var(--tc-border)] bg-[var(--tc-surface)] p-5">
            <div className="flex items-center justify-between text-sm font-semibold text-[var(--tc-ink-muted)]">
              <span>Gaze Pointer</span>
              <Eye className="h-5 w-5 text-[var(--tc-primary)]" aria-hidden="true" />
            </div>
            <p className="mt-3 text-2xl font-bold text-[var(--tc-ink)] tabular-nums">
              {frame?.gaze.x !== null && frame?.gaze.x !== undefined
                ? `${frame.gaze.x}, ${frame.gaze.y}`
                : "Standby"}
            </p>
            <p className="mt-3 text-sm text-[var(--tc-ink-muted)]">
              Source: <span className="font-semibold capitalize">{frame?.gaze.source ?? settings.gaze_source}</span>
              {" | "}
              {frame?.gaze.face_detected ? "Face locked" : frame?.gaze.status ?? "Idle"}
            </p>
          </div>
        </div>

        {/* Real-Time Recharts Trace + Practice Strip */}
        <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
          <div className="rounded-2xl border-2 border-[var(--tc-border)] bg-[var(--tc-surface)] p-5">
            <div className="mb-3 flex items-center justify-between">
              <h3 className="text-lg font-bold text-[var(--tc-ink)]">
                Real-Time Stability Score Trace
              </h3>
              <span className="text-sm font-semibold text-[var(--tc-ink-muted)] tabular-nums">
                Est. Med State: {frame?.medication_state_estimate ?? "N/A"}
              </span>
            </div>
            <div className="h-40 w-full rounded-xl border border-[var(--tc-border)] bg-[var(--tc-bg)] p-2">
              <ResponsiveContainer width="100%" height="100%" minWidth={0}>
                <AreaChart data={chartData}>
                  <YAxis domain={[0, 100]} width={32} stroke="#3D4C46" fontSize={12} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#FFFFFF",
                      border: "2px solid #014A35",
                      borderRadius: "12px",
                      color: "#16201C",
                      fontWeight: 600,
                    }}
                  />
                  <Area
                    type="monotone"
                    dataKey="score"
                    stroke="#014A35"
                    strokeWidth={3}
                    fill="#E3EFE9"
                    isAnimationActive={false}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="rounded-2xl border-2 border-[var(--tc-border)] bg-[var(--tc-surface)] p-5">
            <div className="mb-3 flex items-center justify-between">
              <h3 className="text-lg font-bold text-[var(--tc-ink)]">
                Live Pointer Practice Strip
              </h3>
              <span className="text-sm font-semibold text-[var(--tc-ink-muted)] tabular-nums">
                {padCursor ? `Input ${padCursor.x}, ${padCursor.y}` : "Move cursor inside"}
              </span>
            </div>
            <div
              onPointerMove={handlePadPointerMove}
              className="relative flex h-40 w-full items-center justify-center rounded-xl border-2 border-dashed border-[var(--tc-border-strong)] bg-[var(--tc-surface-alt)] px-4 text-center"
            >
              <p className="pointer-events-none text-base font-medium text-[var(--tc-ink-muted)]">
                Move your cursor across this area to sample live 4-7 Hz Welch tremor power and One Euro smoothing.
              </p>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
