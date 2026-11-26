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
import { Area, AreaChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, YAxis } from "recharts";
import { clearCalibration, pushSteadyHandSample } from "../api/client";
import type { ConnectionState, TelemetryPoint } from "../hooks/useTelemetry";
import { CLINICAL_PRESETS, type ClinicalPreset } from "../presets";
import type {
  EngineToggleRequest,
  SettingsPayload,
  SettingsUpdate,
  TelemetryFrame,
} from "../types/telemetry";
import { GazePreviewFeed } from "./GazePreviewFeed";

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
  const inTremorBand = tremorHz !== null && tremorHz >= 4 && tremorHz <= 12;
  const restingPct = frame?.resting_band_pct ?? 0;
  const actionPct = frame?.action_band_pct ?? 0;
  const rmsMm = frame?.rms_amplitude_mm ?? 0;
  const dampeningPct = Math.round(
    (frame?.steadyhand.strength ?? settings.tremor_strength / 100) * 100
  );
  const dragsPrevented = frame?.steadyhand.spastic_drags_prevented ?? 0;
  const clicksRescued = frame?.steadyhand.slip_clicks_rescued ?? 0;
  const bouncesBlocked = frame?.steadyhand.double_clicks_blocked ?? 0;
  const gravityActive = frame?.steadyhand.gravity_well_active ?? false;
  const bypassActive = frame?.steadyhand.bypass_active ?? false;
  const precisionActive = frame?.steadyhand.precision_active ?? false;
  const excludedApp = frame?.steadyhand.excluded_app_active ?? null;
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
      void pushSteadyHandSample(x, y, undefined, true).catch(() => undefined);
    }
  };

  const handleSelectPreset = async (preset: ClinicalPreset) => {
    await onApplyPreset(preset.updates);
    if (preset.id === "hands_free") {
      await onToggle({
        gaze_control: true,
        camera: true,
        steady_hand: false,
        assistance_enabled: true,
      });
    } else {
      await onToggle({
        steady_hand: true,
        gaze_control: false,
        camera: false,
        assistance_enabled: true,
      });
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
              Choose how much stabilization you want right now with one large tap. Toggle shortcut:{" "}
              <span className="font-bold text-[var(--tc-ink)]">{settings.global_shortcut}</span>
            </p>
          </div>
          <button
            type="button"
            onClick={onStartCalibration}
            className="inline-flex min-h-14 items-center gap-3 rounded-lg border-2 border-[var(--tc-border-strong)] bg-[var(--tc-surface)] px-6 text-base font-bold text-[var(--tc-ink)] hover:bg-[var(--tc-mint)]"
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
                className={`flex min-h-[116px] flex-col justify-between rounded-lg border-2 p-5 text-left transition-colors ${
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
                  className={`mt-3 inline-block self-start rounded-sm px-3 py-1 text-xs font-bold uppercase ${
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
            className={`flex min-h-[112px] w-full items-center justify-between gap-6 rounded-lg border-2 p-6 text-left transition-colors ${
              steadyActive
                ? "border-[var(--tc-primary)] bg-[var(--tc-mint)] text-[var(--tc-ink)]"
                : "border-[var(--tc-border-strong)] bg-[var(--tc-surface)] text-[var(--tc-ink)] hover:bg-[var(--tc-surface-alt)]"
            }`}
          >
            <div className="flex items-start gap-4">
              <div
                className={`flex h-14 w-14 shrink-0 items-center justify-center rounded-md ${
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
                  Delta-space smoothing, click-freeze, bounce guard, and button magnetism.
                </span>
              </div>
            </div>
            <span
              className={`shrink-0 rounded-sm px-4 py-2 text-base font-bold ${
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
              void onToggle(
                gazeActive
                  ? {
                      gaze_control: false,
                      camera: false,
                      system_mouse: false,
                      assistance_enabled: true,
                    }
                  : {
                      gaze_control: true,
                      camera: true,
                      assistance_enabled: true,
                    }
              )
            }
            className={`flex min-h-[112px] w-full items-center justify-between gap-6 rounded-lg border-2 p-6 text-left transition-colors ${
              gazeActive
                ? "border-[var(--tc-primary)] bg-[var(--tc-mint)] text-[var(--tc-ink)]"
                : "border-[var(--tc-border-strong)] bg-[var(--tc-surface)] text-[var(--tc-ink)] hover:bg-[var(--tc-surface-alt)]"
            }`}
          >
            <div className="flex items-start gap-4">
              <div
                className={`flex h-14 w-14 shrink-0 items-center justify-center rounded-md ${
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
              className={`shrink-0 rounded-sm px-4 py-2 text-base font-bold ${
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
            className={`inline-flex min-h-14 items-center gap-3 rounded-lg border-2 px-5 text-base font-bold ${
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
            className={`inline-flex min-h-14 items-center gap-3 rounded-lg border-2 px-5 text-base font-bold ${
              simActive
                ? "border-[var(--tc-alert)] bg-[var(--tc-alert-bg)] text-[var(--tc-alert)]"
                : "border-[var(--tc-border-strong)] bg-[var(--tc-surface)] text-[var(--tc-ink)] hover:bg-[var(--tc-surface-alt)]"
            }`}
          >
            <Waves className="h-5 w-5 shrink-0" aria-hidden="true" />
            <span>4-7 Hz Tremor Simulation: {simActive ? "ON" : "OFF"}</span>
          </button>

          <div className="inline-flex min-h-14 items-center gap-2 rounded-lg border-2 border-[var(--tc-border)] bg-[var(--tc-surface)] px-4 text-sm font-semibold text-[var(--tc-ink)]">
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

          {(bypassActive || precisionActive || excludedApp) && (
            <div className="inline-flex min-h-14 items-center gap-2 rounded-lg border-2 border-[var(--tc-warn)] bg-[var(--tc-warn-bg)] px-4 text-sm font-bold text-[var(--tc-warn)]">
              <span>
                {excludedApp
                  ? `Auto-Paused for ${excludedApp}`
                  : bypassActive
                    ? `Bypass Key Held (${settings.bypass_key.toUpperCase()})`
                    : `Precision Slow-Mode (${settings.precision_key.toUpperCase()})`}
              </span>
            </div>
          )}
        </div>

        {tapError && sysMouseActive && (
          <div
            role="status"
            className="mt-4 rounded-lg border-2 border-[var(--tc-alert)] bg-[var(--tc-alert-bg)] p-4 text-sm font-semibold text-[var(--tc-alert)]"
          >
            OS Interception ({tapMode}): {tapError}
          </div>
        )}
      </section>

      {/* Live Telemetry & Stability Monitor */}
      <section aria-labelledby="telemetry-heading" className="border-t-2 border-[var(--tc-border)] pt-8">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-4">
          <h2 id="telemetry-heading" className="text-2xl font-bold text-[var(--tc-ink)]">
            Live Stability Monitor
          </h2>
          <span className="text-sm font-semibold text-[var(--tc-ink-muted)]">
            Stream: {connectionState === "connected" ? "30 Hz live" : connectionState} | OS Hook: {tapMode}
          </span>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div className="rounded-lg border-2 border-[var(--tc-border)] bg-[var(--tc-surface)] p-5">
            <div className="flex items-center justify-between text-sm font-semibold text-[var(--tc-ink-muted)]">
              <span>Stability Score</span>
              <ShieldCheck className="h-5 w-5 text-[var(--tc-primary)]" aria-hidden="true" />
            </div>
            <p className="mt-3 text-4xl font-bold text-[var(--tc-ink)] tabular-nums">
              {smoothedScore.toFixed(1)}
              <span className="ml-1 text-lg font-semibold text-[var(--tc-ink-muted)]">/ 100</span>
            </p>
            <p className="mt-2 text-sm text-[var(--tc-ink-muted)]">
              {steadyActive ? `RMS jitter: ${rmsMm.toFixed(2)} mm` : "Raw unfiltered cursor"}
            </p>
          </div>

          <div
            className={`rounded-lg border-2 p-5 ${
              inTremorBand
                ? "border-[var(--tc-alert)] bg-[var(--tc-alert-bg)]"
                : "border-[var(--tc-border)] bg-[var(--tc-surface)]"
            }`}
          >
            <div className="flex items-center justify-between text-sm font-semibold text-[var(--tc-ink-muted)]">
              <span>Tremor Spectrum (4-12 Hz)</span>
              <Activity
                className={`h-5 w-5 ${
                  inTremorBand ? "text-[var(--tc-alert)]" : "text-[var(--tc-primary)]"
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
                inTremorBand ? "text-[var(--tc-alert)]" : "text-[var(--tc-ink-muted)]"
              }`}
            >
              {inTremorBand
                ? `Power ${smoothedTremorIndex.toFixed(0)}% (Rest ${restingPct.toFixed(0)}% | Act ${actionPct.toFixed(0)}%)`
                : "No sustained 4-12 Hz tremor"}
            </p>
          </div>

          <div className="rounded-lg border-2 border-[var(--tc-border)] bg-[var(--tc-surface)] p-5">
            <div className="flex items-center justify-between text-sm font-semibold text-[var(--tc-ink-muted)]">
              <span>Click &amp; Drag Protection</span>
              <CheckCircle2 className="h-5 w-5 text-[var(--tc-primary)]" aria-hidden="true" />
            </div>
            <p className="mt-3 text-4xl font-bold text-[var(--tc-ink)] tabular-nums">
              {dampeningPct}
              <span className="ml-1 text-lg font-semibold text-[var(--tc-ink-muted)]">%</span>
            </p>
            <p className="mt-2 text-sm text-[var(--tc-ink-muted)] tabular-nums">
              Rescued: <span className="font-bold">{clicksRescued}</span> | Drags:{" "}
              <span className="font-bold">{dragsPrevented}</span> | Bounces:{" "}
              <span className="font-bold">{bouncesBlocked}</span>
              {frame?.steadyhand.click_freeze_active ? " | Frozen" : ""}
            </p>
          </div>

          <div className="rounded-lg border-2 border-[var(--tc-border)] bg-[var(--tc-surface)] p-5">
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

        {gazeActive && (
          <div className="mt-6 grid grid-cols-1 items-start gap-6 rounded-xl border border-[var(--tc-border)] bg-[var(--tc-surface)] p-5 shadow-[var(--tc-shadow)] lg:grid-cols-12">
            <div className="lg:col-span-5">
              <GazePreviewFeed gaze={frame?.gaze} active={gazeActive} />
            </div>
            <div className="space-y-4 lg:col-span-7">
              <div>
                <h3 className="text-lg font-bold text-[var(--tc-ink)]">
                  GazeCam Quick Setup (3 Steps)
                </h3>
                <p className="mt-1 text-sm text-[var(--tc-ink-muted)]">
                  The head cursor only appears after you calibrate your center and edges.
                </p>
              </div>

              <ol className="space-y-2.5 text-sm">
                <li className="flex items-center justify-between gap-3 rounded-lg bg-[var(--tc-bg)] px-3.5 py-2.5">
                  <span className="font-semibold text-[var(--tc-ink)]">
                    1. Camera &amp; Face Lock
                  </span>
                  <span
                    className={`rounded-full px-2.5 py-0.5 text-xs font-bold ${
                      frame?.gaze.face_detected
                        ? "bg-[var(--tc-mint)] text-[var(--tc-primary)]"
                        : "bg-[var(--tc-alert-bg)] text-[var(--tc-alert)]"
                    }`}
                  >
                    {frame?.gaze.face_detected ? "Face Locked" : "Center Face in Preview"}
                  </span>
                </li>

                <li className="flex flex-wrap items-center justify-between gap-3 rounded-lg bg-[var(--tc-bg)] px-3.5 py-2.5">
                  <div>
                    <span className="font-semibold text-[var(--tc-ink)]">
                      2. Calibrate Center, Left, Right, Up &amp; Down
                    </span>
                    <span className="ml-2 text-xs font-semibold text-[var(--tc-ink-muted)]">
                      ({frame?.gaze.calibrated ? "Calibrated" : "Required first"})
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    {frame?.gaze.calibrated && (
                      <button
                        type="button"
                        onClick={() => void clearCalibration().catch(() => undefined)}
                        className="min-h-11 rounded-lg border border-[var(--tc-border-strong)] bg-[var(--tc-surface)] px-3 text-xs font-bold text-[var(--tc-ink)] hover:bg-[var(--tc-surface-alt)]"
                      >
                        Reset
                      </button>
                    )}
                    <button
                      type="button"
                      onClick={onStartCalibration}
                      className="min-h-11 rounded-lg bg-[var(--tc-primary)] px-4 text-sm font-semibold text-white hover:bg-[var(--tc-primary-hover)]"
                    >
                      {frame?.gaze.calibrated ? "Recalibrate" : "Calibrate Now"}
                    </button>
                  </div>
                </li>

                <li className="flex flex-wrap items-center justify-between gap-3 rounded-lg bg-[var(--tc-bg)] px-3.5 py-2.5">
                  <div>
                    <span className="font-semibold text-[var(--tc-ink)]">
                      3. Head Cursor &amp; Dwell Click
                    </span>
                    <span className="ml-2 text-xs font-semibold text-[var(--tc-ink-muted)]">
                      {frame?.gaze.calibrated
                        ? "Live in browser"
                        : "Waiting for Step 2"}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      disabled={toggling}
                      onClick={() => void onToggle({ system_mouse: !sysMouseActive })}
                      className={`min-h-11 rounded-lg border px-3.5 text-xs font-bold transition-colors ${
                        sysMouseActive
                          ? "border-[var(--tc-primary)] bg-[var(--tc-mint)] text-[var(--tc-primary)]"
                          : "border-[var(--tc-border-strong)] bg-[var(--tc-surface)] text-[var(--tc-ink)]"
                      }`}
                    >
                      Move System Cursor: {sysMouseActive ? "ON" : "OFF"}
                    </button>
                    <button
                      type="button"
                      disabled={toggling}
                      onClick={() =>
                        void onToggle({
                          gaze_control: false,
                          camera: false,
                          system_mouse: false,
                        })
                      }
                      className="min-h-11 rounded-lg bg-[var(--tc-alert)] px-3.5 text-xs font-bold text-white hover:bg-[#7F1D1D]"
                    >
                      Stop GazeCam
                    </button>
                  </div>
                </li>
              </ol>
            </div>
          </div>
        )}

        {/* Real-Time Recharts Trace + Practice Strip */}
        <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
          <div>
            <div className="mb-3 flex items-center justify-between">
              <h3 className="text-lg font-bold text-[var(--tc-ink)]">
                Real-Time Stability Score Trace
              </h3>
              <span className="text-sm font-semibold text-[var(--tc-ink-muted)] tabular-nums">
                Tremor Level: {frame?.tremor_severity ?? "minimal"}
              </span>
            </div>
            <div className="h-44 w-full rounded-xl border border-[var(--tc-border)] bg-[var(--tc-surface)] p-3.5 shadow-[var(--tc-shadow)]">
              <ResponsiveContainer width="100%" height="100%" minWidth={0}>
                <AreaChart data={chartData}>
                  <defs>
                    <linearGradient id="tcStabilityGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#1D4ED8" stopOpacity={0.28} />
                      <stop offset="95%" stopColor="#1D4ED8" stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke="#E2E8F0" strokeDasharray="3 3" vertical={false} />
                  <YAxis domain={[0, 100]} width={32} stroke="#42526E" fontSize={12} tickLine={false} axisLine={false} />
                  <ReferenceLine y={85} stroke="#0F2D59" strokeDasharray="4 4" strokeOpacity={0.45} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#0F2D59",
                      border: "1px solid #1E3A8A",
                      borderRadius: "10px",
                      color: "#FFFFFF",
                      fontSize: "13px",
                      fontWeight: 600,
                      boxShadow: "0 10px 25px rgba(11, 19, 36, 0.2)",
                    }}
                    itemStyle={{ color: "#DBEAFE" }}
                    labelStyle={{ color: "#93C5FD" }}
                  />
                  <Area
                    type="monotone"
                    dataKey="score"
                    stroke="#1D4ED8"
                    strokeWidth={2.75}
                    fill="url(#tcStabilityGrad)"
                    isAnimationActive={false}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div>
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
              className="relative flex h-44 w-full items-center justify-center rounded-lg border-2 border-dashed border-[var(--tc-border-strong)] bg-[var(--tc-surface-alt)] px-4 text-center"
            >
              <p className="pointer-events-none text-base font-medium text-[var(--tc-ink-muted)]">
                Move your cursor across this isolated practice area to test One Euro smoothing without affecting OS cursor logs.
              </p>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
