import { CheckSquare, Play, RotateCcw, Square, Waves } from "lucide-react";
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
    subtitle: "One Euro filter, 180ms click-freeze, and extended zones.",
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
const MAX_TRAIL_POINTS = 64;

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

function drawRoundedRect(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  r: number
) {
  ctx.beginPath();
  ctx.roundRect(x, y, w, h, r);
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
  const [liveHz, setLiveHz] = useState<number | null>(null);
  const [lastFeedback, setLastFeedback] = useState<string>(
    "Move across the dual-trace canvas and click target 1 of 10: 1. Doctor"
  );

  // Interactive sandbox controls for testing everyday clicks & forms
  const [sandboxChecks, setSandboxChecks] = useState<boolean[]>([true, false, false]);
  const [sandboxNote, setSandboxNote] = useState<string>("");
  const [sandboxClickCount, setSandboxClickCount] = useState<number>(0);

  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const anchorPosRef = useRef<[number, number]>([440, 170]);
  const rawPosRef = useRef<[number, number]>([440, 170]);
  const stablePosRef = useRef<[number, number]>([440, 170]);
  const rawTrailRef = useRef<[number, number][]>([]);
  const stableTrailRef = useRef<[number, number][]>([]);
  const inFlightRef = useRef<boolean>(false);

  const activeMode = useMemo(
    () => MODES.find((m) => m.id === mode) ?? MODES[3],
    [mode]
  );

  const expectedId = trialStep < SEQUENCE.length ? SEQUENCE[trialStep] : null;

  const paintCanvas = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) {
      return;
    }
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const backingW = Math.round(CANVAS_W * dpr);
    const backingH = Math.round(CANVAS_H * dpr);
    if (canvas.width !== backingW || canvas.height !== backingH) {
      canvas.width = backingW;
      canvas.height = backingH;
    }

    const ctx = canvas.getContext("2d");
    if (!ctx) {
      return;
    }

    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, CANVAS_W, CANVAS_H);
    ctx.fillStyle = "#FAF7F0";
    ctx.fillRect(0, 0, CANVAS_W, CANVAS_H);

    // Subtle calibration dot matrix background
    ctx.fillStyle = "rgba(92, 110, 102, 0.3)";
    for (let gx = 20; gx < CANVAS_W; gx += 30) {
      for (let gy = 20; gy < CANVAS_H; gy += 30) {
        ctx.beginPath();
        ctx.arc(gx, gy, 1.3, 0, Math.PI * 2);
        ctx.fill();
      }
    }

    const activeCursor = activeMode.useSmoothing ? stablePosRef.current : rawPosRef.current;
    const candidate = inside
      ? selectTarget(
          targets,
          activeCursor[0],
          activeCursor[1],
          activeMode.useExtendedTargets,
          paddingPx
        )
      : null;

    // Render targets and extended hitbox halos
    for (const target of targets) {
      const isExpected = target.id === expectedId;
      const isCandidate = candidate?.id === target.id;
      if (activeMode.useExtendedTargets && paddingPx > 0) {
        ctx.save();
        drawRoundedRect(
          ctx,
          target.x - paddingPx,
          target.y - paddingPx,
          target.width + paddingPx * 2,
          target.height + paddingPx * 2,
          8
        );
        ctx.fillStyle = isCandidate ? "#CFE5DA" : "#E3EFE9";
        ctx.fill();
        ctx.setLineDash([7, 5]);
        ctx.strokeStyle = isExpected ? "#014A35" : "#3D4C46";
        ctx.lineWidth = isCandidate ? 2.5 : 1.75;
        ctx.stroke();
        ctx.restore();
      }

      drawRoundedRect(ctx, target.x, target.y, target.width, target.height, 6);
      ctx.fillStyle = isExpected ? "#014A35" : "#FFFFFF";
      ctx.fill();
      ctx.strokeStyle = isCandidate ? "#01305A" : isExpected ? "#013828" : "#5C6E66";
      ctx.lineWidth = isCandidate ? 3.5 : 2;
      ctx.stroke();

      ctx.fillStyle = isExpected ? "#FFFFFF" : "#16201C";
      ctx.font = "bold 16px -apple-system, BlinkMacSystemFont, sans-serif";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(target.label, target.x + target.width / 2, target.y + target.height / 2);
    }

    // Draw dual-trace history ribbons (Raw shaky trail in crimson vs Smoothed trail in forest green)
    const drawTrail = (pts: [number, number][], color: string, width: number, dashed: boolean) => {
      if (pts.length < 2) {
        return;
      }
      ctx.save();
      ctx.beginPath();
      ctx.moveTo(pts[0][0], pts[0][1]);
      for (let i = 1; i < pts.length; i += 1) {
        ctx.lineTo(pts[i][0], pts[i][1]);
      }
      if (dashed) {
        ctx.setLineDash([4, 3]);
      }
      ctx.strokeStyle = color;
      ctx.lineWidth = width;
      ctx.lineJoin = "round";
      ctx.lineCap = "round";
      ctx.stroke();
      ctx.restore();
    };

    drawTrail(rawTrailRef.current, "rgba(140, 33, 19, 0.55)", 2, true);
    drawTrail(stableTrailRef.current, "rgba(1, 74, 53, 0.9)", 3.5, false);

    // Draw live raw tremor ring and stabilized pointer dot
    if (inside || settings.simulate_tremor) {
      const [rx, ry] = rawPosRef.current;
      const [sx, sy] = stablePosRef.current;

      ctx.save();
      ctx.beginPath();
      ctx.setLineDash([3, 3]);
      ctx.moveTo(rx, ry);
      ctx.lineTo(sx, sy);
      ctx.strokeStyle = "rgba(140, 33, 19, 0.7)";
      ctx.lineWidth = 1.5;
      ctx.stroke();
      ctx.restore();

      ctx.beginPath();
      ctx.arc(rx, ry, 10, 0, Math.PI * 2);
      ctx.strokeStyle = "#8C2113";
      ctx.lineWidth = 3;
      ctx.stroke();

      ctx.beginPath();
      ctx.arc(sx, sy, 7, 0, Math.PI * 2);
      ctx.fillStyle = "#014A35";
      ctx.fill();
      ctx.strokeStyle = "#FFFFFF";
      ctx.lineWidth = 2.5;
      ctx.stroke();
    }
  }, [activeMode, expectedId, inside, paddingPx, settings.simulate_tremor, targets]);

  useEffect(() => {
    paintCanvas();
  }, [paintCanvas]);

  const recordTrail = (raw: [number, number], stable: [number, number]) => {
    rawPosRef.current = raw;
    stablePosRef.current = stable;
    rawTrailRef.current = [...rawTrailRef.current, raw].slice(-MAX_TRAIL_POINTS);
    stableTrailRef.current = [...stableTrailRef.current, stable].slice(-MAX_TRAIL_POINTS);
    paintCanvas();
  };

  const sampleBackend = useCallback(
    async (x: number, y: number, pressed?: boolean) => {
      if (inFlightRef.current && pressed === undefined) {
        return;
      }
      inFlightRef.current = true;
      try {
        const snap = await pushSteadyHandSample(x, y, pressed);
        recordTrail(snap.raw_pos, snap.stable_pos);
        setLiveHz(snap.tremor_hz);
      } catch {
        recordTrail([x, y], [x, y]);
      } finally {
        inFlightRef.current = false;
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [paintCanvas]
  );

  useEffect(() => {
    if (!inside && !settings.simulate_tremor) {
      return;
    }
    const id = window.setInterval(() => {
      const [ax, ay] = anchorPosRef.current;
      void sampleBackend(ax, ay);
    }, 35);
    return () => window.clearInterval(id);
  }, [inside, sampleBackend, settings.simulate_tremor]);

  const toStageCoords = (clientX: number, clientY: number): [number, number] => {
    const el = canvasRef.current;
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
    rawTrailRef.current = [];
    stableTrailRef.current = [];
    paintCanvas();
    setLastFeedback("Trial started: click target 1 of 10 (1. Doctor).");
  };

  const handleCanvasPointerMove = (e: React.PointerEvent<HTMLCanvasElement>) => {
    const [x, y] = toStageCoords(e.clientX, e.clientY);
    anchorPosRef.current = [x, y];
    setInside(true);
    void sampleBackend(x, y);
  };

  const handleCanvasPointerDown = async (e: React.PointerEvent<HTMLCanvasElement>) => {
    const [x, y] = toStageCoords(e.clientX, e.clientY);
    anchorPosRef.current = [x, y];
    setInside(true);
    try {
      const snap = await pushSteadyHandSample(x, y, true);
      recordTrail(snap.raw_pos, snap.stable_pos);
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
            ? `Clicked ${hitTarget.label}, expected ${STEP_LABELS[expectedId]}.`
            : `Missed target boundary. Aim for ${STEP_LABELS[expectedId]}.`
        );
      }
    } catch {
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
            Sandbox Test Playground &amp; 10-Step Appointment Trial
          </h2>
          <p className="mt-1 text-base text-[var(--tc-ink-muted)]">
            Watch the dashed red shaky input path compared against the solid green One Euro stabilized path across target buttons, extended hitboxes, and practice controls.
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
            className={`inline-flex min-h-14 items-center gap-3 rounded-lg border-2 px-5 text-base font-bold ${
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
            className="inline-flex min-h-14 items-center gap-3 rounded-lg bg-[var(--tc-primary)] px-6 text-base font-bold text-white hover:bg-[var(--tc-primary-hover)]"
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
              className={`min-h-[84px] rounded-lg border-2 p-4 text-left transition-colors ${
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

      {/* Dual-Trace Real-Time HTML5 Canvas */}
      <section className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-4">
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

        <canvas
          ref={canvasRef}
          width={CANVAS_W}
          height={CANVAS_H}
          style={{ aspectRatio: `${CANVAS_W} / ${CANVAS_H}` }}
          onPointerMove={handleCanvasPointerMove}
          onPointerDown={(e) => void handleCanvasPointerDown(e)}
          onPointerLeave={() => setInside(false)}
          aria-label="Dual-trace HTML5 canvas showing raw tremor trail, stabilized pointer trail, and 5 appointment targets with extended boundaries"
          className="w-full cursor-crosshair select-none rounded-lg border-2 border-[var(--tc-border-strong)] bg-[var(--tc-bg)]"
        />

        <div className="flex flex-wrap items-center justify-between gap-4 text-sm font-semibold text-[var(--tc-ink-muted)]">
          <span>
            Dashed red ring &amp; trail: raw shaky input | Solid green dot &amp; trail: One Euro stabilized path | Dashed green box: extended boundary
          </span>
          <span className="text-[var(--tc-ink)]">{lastFeedback}</span>
        </div>
      </section>

      <SteppedControl
        id="extended-boundary-padding"
        label="Extended Click Boundary Padding"
        description="Expands forgiving hitboxes around the 5 clinic booking targets for Larger Targets and Full Assist modes."
        value={paddingPx}
        min={0}
        max={36}
        step={4}
        unit="px"
        onChange={setPaddingPx}
      />

      {/* Everyday UI Target Sandbox (Flattened section, no outer wrapper card) */}
      <section className="border-t-2 border-[var(--tc-border)] pt-6">
        <h3 className="text-xl font-bold text-[var(--tc-ink)]">
          Everyday Control Practice Area
        </h3>
        <p className="mt-1 text-base text-[var(--tc-ink-muted)]">
          Try clicking checkboxes, confirmation buttons, and typing notes while OS pointer interception or tremor simulation is active.
        </p>

        <div className="mt-5 grid grid-cols-1 gap-6 lg:grid-cols-3">
          <div className="space-y-4">
            {[
              "Confirm morning appointment",
              "Bring medication schedule list",
              "Send copy to caregiver",
            ].map((labelText, idx) => (
              <button
                key={labelText}
                type="button"
                role="checkbox"
                aria-checked={sandboxChecks[idx]}
                onClick={() =>
                  setSandboxChecks((prev) =>
                    prev.map((v, i) => (i === idx ? !v : v))
                  )
                }
                className={`flex min-h-14 w-full items-center gap-3 rounded-lg border-2 px-4 text-left text-base font-semibold ${
                  sandboxChecks[idx]
                    ? "border-[var(--tc-primary)] bg-[var(--tc-mint)] text-[var(--tc-ink)]"
                    : "border-[var(--tc-border-strong)] bg-[var(--tc-surface)] text-[var(--tc-ink)]"
                }`}
              >
                {sandboxChecks[idx] ? (
                  <CheckSquare className="h-6 w-6 shrink-0 text-[var(--tc-primary)]" aria-hidden="true" />
                ) : (
                  <Square className="h-6 w-6 shrink-0 text-[var(--tc-ink-muted)]" aria-hidden="true" />
                )}
                <span>{labelText}</span>
              </button>
            ))}
          </div>

          <div className="space-y-4">
            <label
              htmlFor="sandbox-note-input"
              className="block text-base font-bold text-[var(--tc-ink)]"
            >
              Visit Note Practice Input
            </label>
            <input
              id="sandbox-note-input"
              type="text"
              value={sandboxNote}
              onChange={(e) => setSandboxNote(e.target.value)}
              placeholder="Click inside and type a short test note..."
              className="min-h-14 w-full rounded-lg border-2 border-[var(--tc-border-strong)] bg-[var(--tc-surface)] px-4 text-base text-[var(--tc-ink)]"
            />
            <button
              type="button"
              onClick={() => setSandboxNote("")}
              className="inline-flex min-h-14 items-center rounded-lg border-2 border-[var(--tc-border-strong)] bg-[var(--tc-surface-alt)] px-5 text-base font-bold text-[var(--tc-ink)] hover:bg-[var(--tc-mint)]"
            >
              Clear Note
            </button>
          </div>

          <div className="flex flex-col justify-between rounded-lg border-2 border-[var(--tc-border)] bg-[var(--tc-surface)] p-5">
            <div>
              <p className="text-base font-bold text-[var(--tc-ink)]">
                Quick Target Tap Counter
              </p>
              <p className="mt-1 text-3xl font-bold text-[var(--tc-primary)] tabular-nums">
                {sandboxClickCount} clicks
              </p>
            </div>
            <button
              type="button"
              onClick={() => setSandboxClickCount((c) => c + 1)}
              className="mt-4 min-h-14 w-full rounded-lg bg-[var(--tc-primary)] px-5 text-base font-bold text-white hover:bg-[var(--tc-primary-hover)]"
            >
              Tap Cleanly to Test Click-Freeze
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}
