import { ArrowDown, ArrowLeft, ArrowRight, ArrowUp, CheckCircle2, Crosshair, RotateCcw, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { pauseGaze, submitCalibration } from "../api/client";
import type { CalibrateResponse, GazeSource, TelemetryFrame } from "../types/telemetry";
import { GazePreviewFeed } from "./GazePreviewFeed";

export type CalibrationGridMode = "5pt" | "9pt" | "head_poses";

interface CalibrationWizardProps {
  initialSource: GazeSource;
  initialMode?: CalibrationGridMode;
  screenWidth: number;
  screenHeight: number;
  frame: TelemetryFrame | null;
  onClose: () => void;
  onCompleted: (result: CalibrateResponse) => void;
}

interface TargetDot {
  label: string;
  nx: number;
  ny: number;
  poseKey?: "center" | "left" | "right" | "up" | "down";
  instruction?: string;
}

const HEAD_POSE_DOTS: TargetDot[] = [
  { label: "Center", nx: 0.5, ny: 0.5, poseKey: "center", instruction: "Look straight at the center of your monitor" },
  { label: "Left", nx: 0.14, ny: 0.5, poseKey: "left", instruction: "Turn your head slightly left toward this target" },
  { label: "Right", nx: 0.86, ny: 0.5, poseKey: "right", instruction: "Turn your head slightly right toward this target" },
  { label: "Up", nx: 0.5, ny: 0.18, poseKey: "up", instruction: "Tilt your head slightly up toward this target" },
  { label: "Down", nx: 0.5, ny: 0.82, poseKey: "down", instruction: "Tilt your head slightly down toward this target" },
];

const FIVE_POINT_DOTS: TargetDot[] = [
  { label: "Center", nx: 0.5, ny: 0.5 },
  { label: "Top Left", nx: 0.14, ny: 0.18 },
  { label: "Top Right", nx: 0.86, ny: 0.18 },
  { label: "Bottom Left", nx: 0.14, ny: 0.82 },
  { label: "Bottom Right", nx: 0.86, ny: 0.82 },
];

const NINE_POINT_DOTS: TargetDot[] = [
  { label: "Top Left", nx: 0.12, ny: 0.16 },
  { label: "Top Center", nx: 0.5, ny: 0.16 },
  { label: "Top Right", nx: 0.88, ny: 0.16 },
  { label: "Middle Left", nx: 0.12, ny: 0.5 },
  { label: "Center", nx: 0.5, ny: 0.5 },
  { label: "Middle Right", nx: 0.88, ny: 0.5 },
  { label: "Bottom Left", nx: 0.12, ny: 0.84 },
  { label: "Bottom Center", nx: 0.5, ny: 0.84 },
  { label: "Bottom Right", nx: 0.88, ny: 0.84 },
];

function medianValue(nums: number[]): number {
  const sorted = [...nums].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 1 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

const HEAD_SETTLE_MS = 550;
const HEAD_COLLECT_MS = 950;

export function CalibrationWizard({
  initialSource,
  initialMode = "5pt",
  screenWidth,
  screenHeight,
  frame,
  onClose,
  onCompleted,
}: CalibrationWizardProps) {
  const [gridMode, setGridMode] = useState<CalibrationGridMode>(initialMode);
  const [source, setSource] = useState<GazeSource>(
    initialMode === "head_poses" ? "head" : initialSource
  );
  const [stepIndex, setStepIndex] = useState<number>(0);
  const [capturedFeatures, setCapturedFeatures] = useState<[number, number][]>([]);
  const [capturedTargets, setCapturedTargets] = useState<[number, number][]>([]);
  const [capturedPoses, setCapturedPoses] = useState<Record<string, [number, number]>>({});
  const [capturedEars, setCapturedEars] = useState<number[]>([]);
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<CalibrateResponse | null>(null);
  const [holdProgress, setHoldProgress] = useState<number>(0);
  const targetButtonRef = useRef<HTMLButtonElement | null>(null);
  const stepStartAtRef = useRef<number>(performance.now());
  const samplesRef = useRef<[number, number][]>([]);
  const earsRef = useRef<number[]>([]);

  useEffect(() => {
    void pauseGaze(true).catch(() => undefined);
    return () => {
      void pauseGaze(false).catch(() => undefined);
    };
  }, []);

  useEffect(() => {
    stepStartAtRef.current = performance.now();
    samplesRef.current = [];
    earsRef.current = [];
    setHoldProgress(0);
  }, [stepIndex, gridMode]);

  useEffect(() => {
    targetButtonRef.current?.focus();
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  const dots = useMemo(() => {
    if (gridMode === "head_poses") {
      return HEAD_POSE_DOTS;
    }
    return gridMode === "5pt" ? FIVE_POINT_DOTS : NINE_POINT_DOTS;
  }, [gridMode]);

  const resetWizard = (
    nextMode?: CalibrationGridMode,
    nextSource?: GazeSource
  ) => {
    if (nextMode !== undefined) {
      setGridMode(nextMode);
    }
    if (nextSource !== undefined) {
      setSource(nextSource);
    }
    setStepIndex(0);
    setCapturedFeatures([]);
    setCapturedTargets([]);
    setCapturedPoses({});
    setCapturedEars([]);
    setError(null);
    setResult(null);
    setHoldProgress(0);
    samplesRef.current = [];
    earsRef.current = [];
  };

  const handleCaptureDot = useCallback(async (
    dot: TargetDot,
    overrideFeat?: [number, number],
    overrideEar?: number | null
  ) => {
    if (submitting || result !== null) {
      return;
    }
    setError(null);

    const liveFeat =
      overrideFeat ??
      (frame?.gaze.face_detected && frame.gaze.raw_feature
        ? frame.gaze.raw_feature
        : null);
    const feat: [number, number] = liveFeat ?? [dot.nx, dot.ny];
    const targetPx: [number, number] = [
      Math.round(dot.nx * screenWidth),
      Math.round(dot.ny * screenHeight),
    ];

    const nextFeatures = [...capturedFeatures.slice(0, stepIndex), feat];
    const nextTargets = [...capturedTargets.slice(0, stepIndex), targetPx];
    const nextPoses = dot.poseKey
      ? { ...capturedPoses, [dot.poseKey]: feat }
      : capturedPoses;
    const earVal = overrideEar !== undefined ? overrideEar : frame?.gaze.ear;
    const nextEars =
      earVal !== null && earVal !== undefined
        ? [...capturedEars.slice(0, stepIndex), earVal]
        : capturedEars.slice(0, stepIndex);

    setCapturedFeatures(nextFeatures);
    setCapturedTargets(nextTargets);
    setCapturedPoses(nextPoses);
    setCapturedEars(nextEars);

    if (stepIndex + 1 < dots.length) {
      setStepIndex(stepIndex + 1);
      return;
    }

    setSubmitting(true);
    try {
      const response =
        gridMode === "head_poses"
          ? await submitCalibration({
              mode: "head",
              source: "head",
              profile_name: "head-5pose",
              poses: nextPoses,
              open_ears: nextEars.length > 0 ? nextEars : undefined,
            })
          : await submitCalibration({
              mode: "dots",
              source,
              profile_name: `${source}-${gridMode === "5pt" ? 5 : 9}pt`,
              features: nextFeatures,
              targets: nextTargets,
              open_ears: nextEars.length > 0 ? nextEars : undefined,
            });
      setResult(response);
      onCompleted(response);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Calibration failed. Retry or verify backend connection."
      );
    } finally {
      setSubmitting(false);
    }
  }, [
    capturedEars,
    capturedFeatures,
    capturedPoses,
    capturedTargets,
    dots.length,
    frame?.gaze.ear,
    frame?.gaze.face_detected,
    frame?.gaze.raw_feature,
    gridMode,
    onCompleted,
    result,
    screenHeight,
    screenWidth,
    source,
    stepIndex,
    submitting,
  ]);

  const activeDot = dots[stepIndex];
  const liveCameraReady = Boolean(frame?.gaze.running && frame?.gaze.face_detected);

  // Automatic hands-free sample averaging for Head Pose mode while live camera sees your face
  useEffect(() => {
    if (
      gridMode !== "head_poses" ||
      !liveCameraReady ||
      submitting ||
      result !== null ||
      error !== null
    ) {
      return;
    }
    const elapsed = performance.now() - stepStartAtRef.current;
    if (elapsed < HEAD_SETTLE_MS) {
      setHoldProgress(0);
      return;
    }
    if (frame?.gaze.raw_feature) {
      samplesRef.current.push(frame.gaze.raw_feature);
      if (frame.gaze.ear !== null && frame.gaze.ear !== undefined) {
        earsRef.current.push(frame.gaze.ear);
      }
    }
    const progress = Math.min(1, (elapsed - HEAD_SETTLE_MS) / HEAD_COLLECT_MS);
    setHoldProgress(progress);

    if (progress >= 1 && samplesRef.current.length >= 3) {
      const xs = samplesRef.current.map((s) => s[0]);
      const ys = samplesRef.current.map((s) => s[1]);
      const medFeat: [number, number] = [medianValue(xs), medianValue(ys)];
      const medEar = earsRef.current.length > 0 ? medianValue(earsRef.current) : null;
      void handleCaptureDot(activeDot, medFeat, medEar);
    }
  }, [
    activeDot,
    error,
    frame,
    gridMode,
    handleCaptureDot,
    liveCameraReady,
    result,
    submitting,
  ]);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="calibration-title"
      className="fixed inset-0 z-50 flex flex-col bg-[var(--tc-bg)] text-[var(--tc-ink)]"
    >
      <header className="border-b-2 border-[var(--tc-border)] bg-[var(--tc-surface)] px-6 py-4">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4">
          <div>
            <h2 id="calibration-title" className="text-xl font-bold">
              Guided Gaze Calibration
            </h2>
            <p className="text-base text-[var(--tc-ink-muted)]">
              {result
                ? "Calibration saved to SQLite profile."
                : `${
                    activeDot.instruction ??
                    `Look at and select target ${stepIndex + 1} of ${dots.length}: ${activeDot.label}`
                  } (${stepIndex + 1}/${dots.length}). ${
                    liveCameraReady
                      ? "Capturing live webcam landmarks."
                      : "Camera standby: using interactive target positions."
                  }`}
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              aria-pressed={gridMode === "head_poses"}
              onClick={() => resetWizard("head_poses", "head")}
              disabled={submitting}
              className={`min-h-14 rounded-lg border-2 px-4 text-base font-bold ${
                gridMode === "head_poses"
                  ? "border-[var(--tc-primary)] bg-[var(--tc-mint)] text-[var(--tc-primary)]"
                  : "border-[var(--tc-border-strong)] bg-[var(--tc-surface)] text-[var(--tc-ink)]"
              }`}
            >
              Head Pose (Center/L/R/U/D)
            </button>
            <button
              type="button"
              aria-pressed={gridMode === "5pt"}
              onClick={() => resetWizard("5pt", source)}
              disabled={submitting}
              className={`min-h-14 rounded-lg border-2 px-4 text-base font-bold ${
                gridMode === "5pt"
                  ? "border-[var(--tc-primary)] bg-[var(--tc-mint)] text-[var(--tc-primary)]"
                  : "border-[var(--tc-border-strong)] bg-[var(--tc-surface)] text-[var(--tc-ink)]"
              }`}
            >
              5-Point Grid
            </button>
            <button
              type="button"
              aria-pressed={gridMode === "9pt"}
              onClick={() => resetWizard("9pt", source)}
              disabled={submitting}
              className={`min-h-14 rounded-lg border-2 px-4 text-base font-bold ${
                gridMode === "9pt"
                  ? "border-[var(--tc-primary)] bg-[var(--tc-mint)] text-[var(--tc-primary)]"
                  : "border-[var(--tc-border-strong)] bg-[var(--tc-surface)] text-[var(--tc-ink)]"
              }`}
            >
              9-Point Grid
            </button>
            <button
              type="button"
              onClick={() =>
                resetWizard(
                  gridMode === "head_poses" ? "5pt" : gridMode,
                  source === "head" ? "eyes" : "head"
                )
              }
              disabled={submitting}
              className="min-h-14 rounded-lg border-2 border-[var(--tc-border-strong)] bg-[var(--tc-surface)] px-4 text-base font-bold text-[var(--tc-ink)] hover:bg-[var(--tc-surface-alt)]"
            >
              Source: {source === "head" ? "Head" : "Eyes"}
            </button>
            <button
              type="button"
              onClick={onClose}
              className="inline-flex min-h-14 items-center gap-2 rounded-lg border-2 border-[var(--tc-border-strong)] bg-[var(--tc-surface-alt)] px-5 text-base font-bold text-[var(--tc-ink)] hover:bg-[var(--tc-alert-bg)]"
            >
              <X className="h-5 w-5" aria-hidden="true" />
              <span>Exit Calibration</span>
            </button>
          </div>
        </div>
      </header>

      <div className="relative flex-1 overflow-hidden">
        {!result && frame?.gaze.running && (
          <div className="pointer-events-none absolute bottom-4 left-1/2 z-10 -translate-x-1/2 opacity-90">
            <GazePreviewFeed gaze={frame.gaze} active={true} compact />
          </div>
        )}
        {error && (
          <div
            role="alert"
            className="mx-auto mt-6 max-w-xl rounded-lg border-2 border-[var(--tc-alert)] bg-[var(--tc-alert-bg)] p-5 text-center"
          >
            <p className="text-lg font-bold text-[var(--tc-alert)]">{error}</p>
            <button
              type="button"
              onClick={() => resetWizard()}
              className="mt-4 inline-flex min-h-14 items-center gap-2 rounded-lg bg-[var(--tc-primary)] px-6 text-base font-bold text-white"
            >
              <RotateCcw className="h-5 w-5" aria-hidden="true" />
              <span>Restart Grid</span>
            </button>
          </div>
        )}

        {result ? (
          <div className="flex h-full items-center justify-center p-6">
            <div className="w-full max-w-lg rounded-lg border-2 border-[var(--tc-primary)] bg-[var(--tc-surface)] p-8 text-center">
              <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-lg bg-[var(--tc-mint)] text-[var(--tc-primary)]">
                <CheckCircle2 className="h-9 w-9" aria-hidden="true" />
              </div>
              <h3 className="mt-4 text-2xl font-bold text-[var(--tc-ink)]">
                Calibration Complete
              </h3>
              <p className="mt-2 text-lg text-[var(--tc-ink-muted)] tabular-nums">
                Mean fit error: <strong className="text-[var(--tc-ink)]">{result.error_px.toFixed(1)} px</strong> (Profile #{result.profile_id})
              </p>
              <div className="mt-6 flex flex-wrap justify-center gap-4">
                <button
                  type="button"
                  onClick={() => resetWizard()}
                  className="inline-flex min-h-14 items-center gap-2 rounded-lg border-2 border-[var(--tc-border-strong)] bg-[var(--tc-surface-alt)] px-6 text-base font-bold text-[var(--tc-ink)]"
                >
                  <RotateCcw className="h-5 w-5" aria-hidden="true" />
                  <span>Calibrate Again</span>
                </button>
                <button
                  type="button"
                  onClick={onClose}
                  className="min-h-14 rounded-lg bg-[var(--tc-primary)] px-8 text-base font-bold text-white hover:bg-[var(--tc-primary-hover)]"
                >
                  Return to Control Deck
                </button>
              </div>
            </div>
          </div>
        ) : (
          <button
            ref={targetButtonRef}
            type="button"
            disabled={submitting}
            onClick={() => void handleCaptureDot(activeDot)}
            aria-label={`Calibration target ${stepIndex + 1} of ${dots.length}: ${activeDot.label}. Activate to capture.`}
            style={{
              left: `${activeDot.nx * 100}%`,
              top: `${activeDot.ny * 100}%`,
              transform: "translate(-50%, -50%)",
            }}
            className="absolute flex h-[104px] w-[104px] flex-col items-center justify-center rounded-full border-4 border-[var(--tc-focus)] bg-[var(--tc-primary)] text-white shadow-lg hover:bg-[var(--tc-primary-hover)]"
          >
            {gridMode === "head_poses" && liveCameraReady && holdProgress > 0 && (
              <svg
                width="104"
                height="104"
                viewBox="0 0 104 104"
                className="pointer-events-none absolute inset-0 -rotate-90"
                aria-hidden="true"
              >
                <circle
                  cx="52"
                  cy="52"
                  r="47"
                  fill="none"
                  stroke="#93C5FD"
                  strokeWidth="6"
                  strokeLinecap="round"
                  strokeDasharray={2 * Math.PI * 47}
                  strokeDashoffset={2 * Math.PI * 47 * (1 - holdProgress)}
                />
              </svg>
            )}
            {activeDot.poseKey === "left" ? (
              <ArrowLeft className="h-8 w-8" aria-hidden="true" />
            ) : activeDot.poseKey === "right" ? (
              <ArrowRight className="h-8 w-8" aria-hidden="true" />
            ) : activeDot.poseKey === "up" ? (
              <ArrowUp className="h-8 w-8" aria-hidden="true" />
            ) : activeDot.poseKey === "down" ? (
              <ArrowDown className="h-8 w-8" aria-hidden="true" />
            ) : (
              <Crosshair className="h-8 w-8" aria-hidden="true" />
            )}
            <span className="mt-1 text-sm font-bold tabular-nums">
              {stepIndex + 1}/{dots.length}
            </span>
          </button>
        )}
      </div>
    </div>
  );
}
