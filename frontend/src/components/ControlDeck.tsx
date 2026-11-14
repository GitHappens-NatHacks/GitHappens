import {
  Activity,
  Camera,
  CheckCircle2,
  Eye,
  Hand,
  MousePointerClick,
  ShieldCheck,
  Waves,
} from "lucide-react";
import { useRef, useState } from "react";
import { pushSteadyHandSample } from "../api/client";
import type { ConnectionState, TelemetryPoint } from "../hooks/useTelemetry";
import type { EngineToggleRequest, SettingsPayload, TelemetryFrame } from "../types/telemetry";

interface ControlDeckProps {
  settings: SettingsPayload;
  frame: TelemetryFrame | null;
  smoothedScore: number;
  smoothedTremorIndex: number;
  history: TelemetryPoint[];
  connectionState: ConnectionState;
  toggling: boolean;
  onToggle: (payload: EngineToggleRequest) => Promise<void>;
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
  onStartCalibration,
}: ControlDeckProps) {
  const [padCursor, setPadCursor] = useState<{ x: number; y: number } | null>(null);
  const lastSentAtRef = useRef<number>(0);

  const steadyActive = frame?.stabilization_active ?? (settings.assistance_enabled && settings.steady_hand);
  const gazeActive = frame?.active_modes.gaze_control ?? settings.gaze_control;
  const simActive = frame?.active_modes.simulate_tremor ?? settings.simulate_tremor;
  const cameraRunning = frame?.gaze.running ?? false;
  const sysMouseActive = frame?.steadyhand.system_mouse_enabled ?? settings.system_mouse;

  const tremorHz = frame?.tremor_hz ?? null;
  const inParkinsonBand = tremorHz !== null && tremorHz >= 4 && tremorHz <= 7;
  const dampeningPct = Math.round((frame?.steadyhand.strength ?? settings.tremor_strength / 100) * 100);
  const dragsPrevented = frame?.steadyhand.spastic_drags_prevented ?? 0;

  const handlePadPointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = Math.round(e.clientX - rect.left);
    const y = Math.round(e.clientY - rect.top);
    setPadCursor({ x, y });

    const now = performance.now();
    if (now - lastSentAtRef.current >= 32) {
      lastSentAtRef.current = now;
      void pushSteadyHandSample(x, y).catch(() => {
        // Ignore transient network errors during high-rate practice pointer streaming.
      });
    }
  };

  // Build SVG polyline for rolling stability score (0-100)
  const chartW = 560;
  const chartH = 128;
  const points = history.length > 1
    ? history
        .map((pt, idx) => {
          const px = (idx / (history.length - 1)) * chartW;
          const py = chartH - (Math.max(0, Math.min(100, pt.stabilityScore)) / 100) * (chartH - 16) - 8;
          return `${px.toFixed(1)},${py.toFixed(1)}`;
        })
        .join(" ")
    : `0,${(chartH / 2).toFixed(1)} ${chartW},${(chartH / 2).toFixed(1)}`;

  return (
    <div className="space-y-8">
      <section aria-labelledby="primary-modes-heading">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-4">
          <div>
            <h2 id="primary-modes-heading" className="text-2xl font-bold text-[var(--tc-ink)]">
              Assistance Modes
            </h2>
            <p className="mt-1 text-base text-[var(--tc-ink-muted)]">
              Large toggle controls for motor stabilization and hands-free gaze pointing.
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

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {/* SteadyHand Toggle Card */}
          <button
            type="button"
            disabled={toggling}
            aria-pressed={steadyActive}
            onClick={() => void onToggle({ steady_hand: !steadyActive, assistance_enabled: true })}
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
                  One Euro smoothing and anti-drag protection for hand tremors.
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

          {/* GazeControl Toggle Card */}
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
                  Webcam MediaPipe head and iris pointing with dwell or blink click.
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

        {/* Secondary Lab / OS Pointer Toggles */}
        <div className="mt-4 flex flex-wrap items-center gap-4">
          <button
            type="button"
            disabled={toggling}
            aria-pressed={simActive}
            onClick={() => void onToggle({ simulate_tremor: !simActive })}
            className={`inline-flex min-h-14 items-center gap-3 rounded-xl border-2 px-5 text-base font-semibold ${
              simActive
                ? "border-[var(--tc-alert)] bg-[var(--tc-alert-bg)] text-[var(--tc-alert)]"
                : "border-[var(--tc-border-strong)] bg-[var(--tc-surface)] text-[var(--tc-ink)] hover:bg-[var(--tc-surface-alt)]"
            }`}
          >
            <Waves className="h-5 w-5 shrink-0" aria-hidden="true" />
            <span>4-7 Hz Tremor Simulation: {simActive ? "ON" : "OFF"}</span>
          </button>

          <button
            type="button"
            disabled={toggling}
            aria-pressed={sysMouseActive}
            onClick={() => void onToggle({ system_mouse: !sysMouseActive })}
            className={`inline-flex min-h-14 items-center gap-3 rounded-xl border-2 px-5 text-base font-semibold ${
              sysMouseActive
                ? "border-[var(--tc-primary)] bg-[var(--tc-mint)] text-[var(--tc-primary)]"
                : "border-[var(--tc-border-strong)] bg-[var(--tc-surface)] text-[var(--tc-ink)] hover:bg-[var(--tc-surface-alt)]"
            }`}
          >
            <MousePointerClick className="h-5 w-5 shrink-0" aria-hidden="true" />
            <span>OS Pointer Control: {sysMouseActive ? "ON" : "OFF"}</span>
          </button>
        </div>
      </section>

      {/* Live Telemetry & Stability Monitor */}
      <section aria-labelledby="telemetry-heading">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-4">
          <h2 id="telemetry-heading" className="text-2xl font-bold text-[var(--tc-ink)]">
            Live Telemetry &amp; Stability Monitor
          </h2>
          <span className="text-sm font-semibold text-[var(--tc-ink-muted)]">
            Stream: {connectionState === "connected" ? "25 Hz live" : connectionState}
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
              {steadyActive ? "One Euro filter active" : "Raw unfiltered cursor"}
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
                ? `4-7 Hz band power: ${smoothedTremorIndex.toFixed(1)}%`
                : "No sustained 4-7 Hz oscillation"}
            </p>
          </div>

          <div className="rounded-2xl border-2 border-[var(--tc-border)] bg-[var(--tc-surface)] p-5">
            <div className="flex items-center justify-between text-sm font-semibold text-[var(--tc-ink-muted)]">
              <span>Dampening Intensity</span>
              <CheckCircle2 className="h-5 w-5 text-[var(--tc-primary)]" aria-hidden="true" />
            </div>
            <p className="mt-3 text-4xl font-bold text-[var(--tc-ink)] tabular-nums">
              {dampeningPct}
              <span className="ml-1 text-lg font-semibold text-[var(--tc-ink-muted)]">%</span>
            </p>
            <p className="mt-2 text-sm text-[var(--tc-ink-muted)]">
              Anti-drag rescues: <span className="font-bold tabular-nums">{dragsPrevented}</span>
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

        {/* Rolling Stability Trace + Practice Surface */}
        <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
          <div className="rounded-2xl border-2 border-[var(--tc-border)] bg-[var(--tc-surface)] p-5">
            <div className="mb-3 flex items-center justify-between">
              <h3 className="text-lg font-bold text-[var(--tc-ink)]">
                Real-Time Stability Score Trace
              </h3>
              <span className="text-sm font-semibold text-[var(--tc-ink-muted)] tabular-nums">
                Band: {frame?.medication_state_estimate ?? "N/A"}
              </span>
            </div>
            <svg
              viewBox={`0 0 ${chartW} ${chartH}`}
              role="img"
              aria-label="Live stability score waveform from 0 to 100"
              className="h-36 w-full rounded-xl border border-[var(--tc-border)] bg-[var(--tc-bg)]"
            >
              <line x1="0" y1={chartH * 0.25} x2={chartW} y2={chartH * 0.25} stroke="#D5DED8" strokeDasharray="4 4" />
              <line x1="0" y1={chartH * 0.5} x2={chartW} y2={chartH * 0.5} stroke="#D5DED8" strokeDasharray="4 4" />
              <line x1="0" y1={chartH * 0.75} x2={chartW} y2={chartH * 0.75} stroke="#D5DED8" strokeDasharray="4 4" />
              <polyline
                fill="none"
                stroke="#014A35"
                strokeWidth="3"
                strokeLinejoin="round"
                strokeLinecap="round"
                points={points}
              />
            </svg>
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
              className="relative flex h-36 w-full items-center justify-center rounded-xl border-2 border-dashed border-[var(--tc-border-strong)] bg-[var(--tc-surface-alt)] px-4 text-center"
            >
              <p className="pointer-events-none text-base font-medium text-[var(--tc-ink-muted)]">
                Move your cursor across this area to feed live coordinates into the FFT tremor detector.
              </p>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
