import { Play, RotateCcw, Waves } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { pushSteadyHandSample } from "../api/client";
import type { EngineToggleRequest, SettingsPayload } from "../types/telemetry";
import { SteppedControl } from "./SteppedControl";

type AssistMode = "baseline" | "smoothing" | "targets" | "full";
type StepId = "doctor" | "date" | "time" | "review" | "book";

interface TargetBox {
  id: StepId;
  label: string;
  x: number;
  y: number;
  width: number;
  height: number;
}

interface ModeMeta {
  id: AssistMode;
  title: string;
  subtitle: string;
  useSmoothing: boolean;
  useExtendedTargets: boolean;
}

const MODES: ModeMeta[] = [
  {
    id: "baseline",
    title: "Baseline",
    subtitle: "Raw cursor, standard button edges only.",
    useSmoothing: false,
    useExtendedTargets: false,
  },
  {
    id: "smoothing",
    title: "Smoothing Only",
    subtitle: "Filters 4-7 Hz tremor; standard edges.",
    useSmoothing: true,
    useExtendedTargets: false,
  },
  {
    id: "targets",
    title: "Larger Targets Only",
    subtitle: "Raw cursor + dashed extended hitboxes.",
    useSmoothing: false,
    useExtendedTargets: true,
  },
  {
    id: "full",
    title: "Full Assist",
    subtitle: "One Euro filter, anti-drag, and extended zones.",
    useSmoothing: true,
    useExtendedTargets: true,
  },
];

const SEQUENCE: StepId[] = [
  "doctor",
  "date",
  "time",
  "review",
  "book",
  "doctor",
  "date",
  "time",
  "review",
  "book",
];

const STEP_LABELS: Record<StepId, string> = {
  doctor: "1. Doctor",
  date: "2. Date",
  time: "3. Time",
  review: "4. Review",
  book: "5. Book",
};

const CANVAS_W = 880;
const CANVAS_H = 340;

function buildAppointmentTargets(): TargetBox[] {
  const keys: StepId[] = ["doctor", "date", "time", "review", "book"];
  const width = 136;
  const height = 56;
  const marginX = 44;
  const stepX = (CANVAS_W - 2 * marginX - width) / (keys.length - 1);
  return keys.map((id, idx) => ({
    id,
    label: STEP_LABELS[id],
    x: Math.round(marginX + idx * stepX),
    y: Math.round(138 + (idx % 2 === 0 ? -34 : 34)),
    width,
    height,
  }));
}

function pointInTarget(target: TargetBox, x: number, y: number, padding: number): boolean {
  return (
    target.x - padding <= x &&
    x <= target.x + target.width + padding &&
    target.y - padding <= y &&
    y <= target.y + target.height + padding
  );
}

function distanceToTarget(target: TargetBox, x: number, y: number): number {
  const dx = Math.max(target.x - x, 0, x - (target.x + target.width));
  const dy = Math.max(target.y - y, 0, y - (target.y + target.height));
  return Math.hypot(dx, dy);
}

function selectTarget(
  targets: TargetBox[],
  x: number,
  y: number,
  assisted: boolean,
  padding: number
): TargetBox | null {
  const direct = targets.filter((t) => pointInTarget(t, x, y, 0));
  if (direct.length > 0) {
    return direct[0];
  }
  if (!assisted || padding <= 0) {
    return null;
  }
  const extended = targets.filter((t) => pointInTarget(t, x, y, padding));
  if (extended.length === 0) {
    return null;
  }
  return extended.reduce((best, item) =>
    distanceToTarget(item, x, y) < distanceToTarget(best, x, y) ? item : best
  );
}

interface AppointmentPlaygroundProps {
  settings: SettingsPayload;
  toggling: boolean;
  onToggle: (payload: EngineToggleRequest) => Promise<void>;
}

export function AppointmentPlayground({
  settings,
  toggling,
  onToggle,
}: AppointmentPlaygroundProps) {
  const targets = useMemo(() => buildAppointmentTargets(), []);
  const [mode, setMode] = useState<AssistMode>("full");
  const [paddingPx, setPaddingPx] = useState<number>(18);
  const [trialStep, setTrialStep] = useState<number>(0);
  const [trialActive, setTrialActive] = useState<boolean>(true);
  const [hits, setHits] = useState<number>(0);
  const [misses, setMisses] = useState<number>(0);
  const [inside, setInside] = useState<boolean>(false);
  const [rawPos, setRawPos] = useState<[number, number]>([440, 170]);
  const [stablePos, setStablePos] = useState<[number, number]>([440, 170]);
  const [liveHz, setLiveHz] = useState<number | null>(null);
  const [lastFeedback, setLastFeedback] = useState<string>(
    "Click target 1 of 10: 1. Doctor"
  );

  const stageRef = useRef<HTMLDivElement | null>(null);
  const anchorPosRef = useRef<[number, number]>([440, 170]);
  const inFlightRef = useRef<boolean>(false);

  const activeMode = useMemo(
    () => MODES.find((m) => m.id === mode) ?? MODES[3],
    [mode]
  );

  const expectedId = trialStep < SEQUENCE.length ? SEQUENCE[trialStep] : null;
  const activeCursor = activeMode.useSmoothing ? stablePos : rawPos;
  const candidate = inside
    ? selectTarget(
        targets,
        activeCursor[0],
        activeCursor[1],
        activeMode.useExtendedTargets,
        paddingPx
      )
    : null;

  const sampleBackend = useCallback(async (x: number, y: number, pressed?: boolean) => {
    if (inFlightRef.current && pressed === undefined) {
      return;
    }
    inFlightRef.current = true;
    try {
      const snap = await pushSteadyHandSample(x, y, pressed);
      setRawPos(snap.raw_pos);
      setStablePos(snap.stable_pos);
      setLiveHz(snap.tremor_hz);
    } catch {
      // Fall back gracefully if backend is temporarily unreachable.
      setRawPos([x, y]);
      setStablePos([x, y]);
    } finally {
      inFlightRef.current = false;
    }
  }, []);

  // Poll at ~20 Hz while pointer is inside canvas or simulation is active so real-time
  // tremor oscillation and One Euro filtering stay visible even when mouse holds steady.
  useEffect(() => {
    if (!inside && !settings.simulate_tremor) {
      return;
    }
    const id = window.setInterval(() => {
      const [ax, ay] = anchorPosRef.current;
      void sampleBackend(ax, ay);
    }, 45);
    return () => window.clearInterval(id);
  }, [inside, sampleBackend, settings.simulate_tremor]);

  const toStageCoords = (clientX: number, clientY: number): [number, number] => {
    const el = stageRef.current;
    if (!el) {
      return [440, 170];
    }
    const rect = el.getBoundingClientRect();
    const nx = ((clientX - rect.left) / Math.max(1, rect.width)) * CANVAS_W;
    const ny = ((clientY - rect.top) / Math.max(1, rect.height)) * CANVAS_H;
    return [
      Math.max(0, Math.min(CANVAS_W, nx)),
      Math.max(0, Math.min(CANVAS_H, ny)),
    ];
  };

  const handleSelectMode = async (nextMode: ModeMeta) => {
    setMode(nextMode.id);
    await onToggle({
      steady_hand: nextMode.useSmoothing,
      assistance_enabled: true,
    });
  };

  const handleResetTrial = () => {
    setTrialStep(0);
    setTrialActive(true);
    setHits(0);
    setMisses(0);
    setLastFeedback("Trial started: click target 1 of 10 (1. Doctor).");
  };

  const handleCanvasPointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    const [x, y] = toStageCoords(e.clientX, e.clientY);
    anchorPosRef.current = [x, y];
    setInside(true);
    void sampleBackend(x, y);
  };

  const handleCanvasPointerDown = async (e: React.PointerEvent<HTMLDivElement>) => {
    const [x, y] = toStageCoords(e.clientX, e.clientY);
    anchorPosRef.current = [x, y];
    setInside(true);
    try {
      const snap = await pushSteadyHandSample(x, y, true);
      setRawPos(snap.raw_pos);
      setStablePos(snap.stable_pos);
      const clickPos = activeMode.useSmoothing ? snap.stable_pos : snap.raw_pos;
      const hitTarget = selectTarget(
        targets,
        clickPos[0],
        clickPos[1],
        activeMode.useExtendedTargets,
        paddingPx
      );
      void pushSteadyHandSample(x, y, false).catch(() => undefined);

      if (!trialActive || expectedId === null) {
        return;
      }
      if (hitTarget && hitTarget.id === expectedId) {
        const nextStep = trialStep + 1;
        setHits((h) => h + 1);
        setTrialStep(nextStep);
        if (nextStep >= SEQUENCE.length) {
          setTrialActive(false);
          setLastFeedback(
            `Completed all 10 appointment steps (${hits + 1} hits, ${misses} misses).`
          );
        } else {
          setLastFeedback(
            `Hit ${hitTarget.label}. Next target (${nextStep + 1}/10): ${STEP_LABELS[SEQUENCE[nextStep]]}`
          );
        }
      } else {
        setMisses((m) => m + 1);
        setLastFeedback(
          hitTarget
            ? `Clicked ${hitTarget.label}, but expected ${STEP_LABELS[expectedId]}.`
            : `Missed target boundary. Aim for ${STEP_LABELS[expectedId]}.`
        );
      }
    } catch {
      // Fall back locally when backend API is offline.
      const hitTarget = selectTarget(
        targets,
        x,
        y,
        activeMode.useExtendedTargets,
        paddingPx
      );
      if (trialActive && expectedId !== null && hitTarget?.id === expectedId) {
        const nextStep = trialStep + 1;
        setHits((h) => h + 1);
        setTrialStep(nextStep);
        if (nextStep >= SEQUENCE.length) {
          setTrialActive(false);
        }
      } else if (trialActive) {
        setMisses((m) => m + 1);
      }
    }
  };

  const totalAttempts = hits + misses;
  const accuracyPct = totalAttempts > 0 ? Math.round((hits / totalAttempts) * 100) : 100;

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-[var(--tc-ink)]">
            10-Step Appointment Tremor Playground
          </h2>
          <p className="mt-1 text-base text-[var(--tc-ink-muted)]">
            Compare raw shaky input against One Euro smoothing and dashed extended button boundaries across 10 simulated clinic booking steps.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-4">
          <button
            type="button"
            disabled={toggling}
            aria-pressed={settings.simulate_tremor}
            onClick={() =>
              void onToggle({
                simulate_tremor: !settings.simulate_tremor,
                assistance_enabled: true,
              })
            }
            className={`inline-flex min-h-14 items-center gap-3 rounded-xl border-2 px-5 text-base font-bold ${
              settings.simulate_tremor
                ? "border-[var(--tc-alert)] bg-[var(--tc-alert-bg)] text-[var(--tc-alert)]"
                : "border-[var(--tc-border-strong)] bg-[var(--tc-surface)] text-[var(--tc-ink)] hover:bg-[var(--tc-surface-alt)]"
            }`}
          >
            <Waves className="h-5 w-5 shrink-0" aria-hidden="true" />
            <span>
              Shaky Tremor Sim: {settings.simulate_tremor ? "ON (4-7 Hz)" : "OFF"}
            </span>
          </button>

          <button
            type="button"
            onClick={handleResetTrial}
            className="inline-flex min-h-14 items-center gap-3 rounded-xl bg-[var(--tc-primary)] px-6 text-base font-bold text-white hover:bg-[var(--tc-primary-hover)]"
          >
            {trialActive && trialStep > 0 ? (
              <RotateCcw className="h-5 w-5 shrink-0" aria-hidden="true" />
            ) : (
              <Play className="h-5 w-5 shrink-0" aria-hidden="true" />
            )}
            <span>{trialStep > 0 ? "Restart 10-Step Trial" : "Start 10-Step Trial"}</span>
          </button>
        </div>
      </div>

      {/* Mode Comparison Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {MODES.map((item) => {
          const selected = mode === item.id;
          return (
            <button
              key={item.id}
              type="button"
              aria-pressed={selected}
              onClick={() => void handleSelectMode(item)}
              className={`min-h-[84px] rounded-2xl border-2 p-4 text-left transition-colors ${
                selected
                  ? "border-[var(--tc-primary)] bg-[var(--tc-mint)] text-[var(--tc-ink)]"
                  : "border-[var(--tc-border-strong)] bg-[var(--tc-surface)] text-[var(--tc-ink)] hover:bg-[var(--tc-surface-alt)]"
              }`}
            >
              <span className="block text-lg font-bold">{item.title}</span>
              <span className="mt-1 block text-sm text-[var(--tc-ink-muted)]">
                {item.subtitle}
              </span>
            </button>
          );
        })}
      </div>

      {/* Interactive Appointment Trial Canvas */}
      <section className="rounded-2xl border-2 border-[var(--tc-border)] bg-[var(--tc-surface)] p-5">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-4">
          <div role="status" aria-live="polite" className="text-lg font-bold text-[var(--tc-ink)] tabular-nums">
            {expectedId !== null
              ? `Step ${trialStep + 1} of 10: Click ${STEP_LABELS[expectedId]}`
              : "10-Step Trial Complete"}
          </div>

          <div className="flex flex-wrap items-center gap-6 text-base font-bold text-[var(--tc-ink)] tabular-nums">
            <span>Hits: {hits}</span>
            <span>Misses: {misses}</span>
            <span className="text-[var(--tc-primary)]">Accuracy: {accuracyPct}%</span>
            <span className="text-[var(--tc-ink-muted)]">
              FFT: {liveHz !== null ? `${liveHz.toFixed(2)} Hz` : "Idle"}
            </span>
          </div>
        </div>

        <div
          ref={stageRef}
          onPointerMove={handleCanvasPointerMove}
          onPointerDown={(e) => void handleCanvasPointerDown(e)}
          onPointerLeave={() => setInside(false)}
          className="relative w-full cursor-crosshair select-none overflow-hidden rounded-2xl border-2 border-[var(--tc-border-strong)] bg-[var(--tc-bg)]"
          style={{ aspectRatio: `${CANVAS_W} / ${CANVAS_H}` }}
        >
          <svg
            viewBox={`0 0 ${CANVAS_W} ${CANVAS_H}`}
            role="img"
            aria-label="10-step appointment simulator showing button edges, extended dashed click boundaries, raw tremor ring, and smoothed pointer dot"
            className="h-full w-full"
          >
            {/* Subtle calibration dot matrix background */}
            <defs>
              <pattern
                id="tc-dot-grid"
                width="30"
                height="30"
                patternUnits="userSpaceOnUse"
              >
                <circle cx="15" cy="15" r="1.4" fill="#9EB0A6" opacity="0.45" />
              </pattern>
            </defs>
            <rect width={CANVAS_W} height={CANVAS_H} fill="url(#tc-dot-grid)" />

            {targets.map((target) => {
              const isExpected = target.id === expectedId;
              const isCandidate = candidate?.id === target.id;
              const showExtended = activeMode.useExtendedTargets && paddingPx > 0;
              return (
                <g key={target.id}>
                  {/* Extended Hitbox Boundary */}
                  {showExtended && (
                    <rect
                      x={target.x - paddingPx}
                      y={target.y - paddingPx}
                      width={target.width + paddingPx * 2}
                      height={target.height + paddingPx * 2}
                      rx={14}
                      fill={isCandidate ? "#CFE5DA" : "#E3EFE9"}
                      stroke={isExpected ? "#014A35" : "#3D4C46"}
                      strokeWidth={isCandidate ? 2.5 : 1.75}
                      strokeDasharray="7 5"
                    />
                  )}

                  {/* Standard Button Inner Boundary */}
                  <rect
                    x={target.x}
                    y={target.y}
                    width={target.width}
                    height={target.height}
                    rx={10}
                    fill={isExpected ? "#014A35" : "#FFFFFF"}
                    stroke={
                      isCandidate
                        ? "#01305A"
                        : isExpected
                        ? "#013828"
                        : "#5C6E66"
                    }
                    strokeWidth={isCandidate ? 3.5 : 2}
                  />

                  <text
                    x={target.x + target.width / 2}
                    y={target.y + target.height / 2 + 6}
                    textAnchor="middle"
                    fontSize="16"
                    fontWeight="700"
                    fill={isExpected ? "#FFFFFF" : "#16201C"}
                  >
                    {target.label}
                  </text>
                </g>
              );
            })}

            {/* Real-Time Cursors: Raw Tremor Ring vs One Euro Stabilized Dot */}
            {(inside || settings.simulate_tremor) && (
              <g>
                <line
                  x1={rawPos[0]}
                  y1={rawPos[1]}
                  x2={stablePos[0]}
                  y2={stablePos[1]}
                  stroke="#8C2113"
                  strokeWidth="1.5"
                  strokeDasharray="3 3"
                  opacity="0.7"
                />
                <circle
                  cx={rawPos[0]}
                  cy={rawPos[1]}
                  r="11"
                  fill="none"
                  stroke="#8C2113"
                  strokeWidth="3"
                />
                <circle
                  cx={stablePos[0]}
                  cy={stablePos[1]}
                  r="7"
                  fill="#014A35"
                  stroke="#FFFFFF"
                  strokeWidth="2.5"
                />
              </g>
            )}
          </svg>
        </div>

        <div className="mt-4 flex flex-wrap items-center justify-between gap-4 text-sm font-semibold text-[var(--tc-ink-muted)]">
          <span>
            Red ring: raw / 4-7 Hz shaky input | Solid green dot: One Euro smoothed pointer | Dashed box: extended boundary
          </span>
          <span className="text-[var(--tc-ink)]">{lastFeedback}</span>
        </div>
      </section>

      <SteppedControl
        id="extended-boundary-padding"
        label="Extended Click Boundary Padding"
        description="Expands forgiving target hitboxes around each appointment button for Larger Targets and Full Assist modes."
        value={paddingPx}
        min={0}
        max={36}
        step={4}
        unit="px"
        onChange={setPaddingPx}
      />
    </div>
  );
}
