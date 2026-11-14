import { CheckCircle2, Crosshair, RotateCcw, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { submitCalibration } from "../api/client";
import type { CalibrateResponse, GazeSource, TelemetryFrame } from "../types/telemetry";

interface CalibrationWizardProps {
  initialSource: GazeSource;
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
}

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

export function CalibrationWizard({
  initialSource,
  screenWidth,
  screenHeight,
  frame,
  onClose,
  onCompleted,
}: CalibrationWizardProps) {
  const [pointCount, setPointCount] = useState<5 | 9>(5);
  const [source, setSource] = useState<GazeSource>(initialSource);
  const [stepIndex, setStepIndex] = useState<number>(0);
  const [capturedFeatures, setCapturedFeatures] = useState<[number, number][]>([]);
  const [capturedTargets, setCapturedTargets] = useState<[number, number][]>([]);
  const [capturedEars, setCapturedEars] = useState<number[]>([]);
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<CalibrateResponse | null>(null);
  const targetButtonRef = useRef<HTMLButtonElement | null>(null);

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

  const dots = useMemo(
    () => (pointCount === 5 ? FIVE_POINT_DOTS : NINE_POINT_DOTS),
    [pointCount]
  );

  const resetWizard = (nextCount?: 5 | 9, nextSource?: GazeSource) => {
    if (nextCount !== undefined) {
      setPointCount(nextCount);
    }
    if (nextSource !== undefined) {
      setSource(nextSource);
    }
    setStepIndex(0);
    setCapturedFeatures([]);
    setCapturedTargets([]);
    setCapturedEars([]);
    setError(null);
    setResult(null);
  };

  const handleCaptureDot = async (dot: TargetDot) => {
    if (submitting || result !== null) {
      return;
    }
    setError(null);

    const liveFeat =
      frame?.gaze.face_detected && frame.gaze.raw_feature
        ? frame.gaze.raw_feature
        : null;
    const feat: [number, number] = liveFeat ?? [dot.nx, dot.ny];
    const targetPx: [number, number] = [
      Math.round(dot.nx * screenWidth),
      Math.round(dot.ny * screenHeight),
    ];

    const nextFeatures = [...capturedFeatures, feat];
    const nextTargets = [...capturedTargets, targetPx];
    const nextEars =
      frame?.gaze.ear !== null && frame?.gaze.ear !== undefined
        ? [...capturedEars, frame.gaze.ear]
        : capturedEars;

    setCapturedFeatures(nextFeatures);
    setCapturedTargets(nextTargets);
    setCapturedEars(nextEars);

    if (stepIndex + 1 < dots.length) {
      setStepIndex(stepIndex + 1);
      return;
    }

    setSubmitting(true);
    try {
      const response = await submitCalibration({
        mode: "dots",
        source,
        profile_name: `${source}-${pointCount}pt`,
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
  };

  const activeDot = dots[stepIndex];
  const liveCameraReady = Boolean(frame?.gaze.running && frame?.gaze.face_detected);

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
                : `Look at and select target ${stepIndex + 1} of ${dots.length}: ${activeDot.label}. ${
                    liveCameraReady
                      ? "Capturing live webcam landmarks."
                      : "Camera standby: using interactive target positions."
                  }`}
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-4">
            <button
              type="button"
              aria-pressed={pointCount === 5}
              onClick={() => resetWizard(5, source)}
              disabled={submitting}
              className={`min-h-14 rounded-xl border-2 px-5 text-base font-bold ${
                pointCount === 5
                  ? "border-[var(--tc-primary)] bg-[var(--tc-mint)] text-[var(--tc-primary)]"
                  : "border-[var(--tc-border-strong)] bg-[var(--tc-surface)] text-[var(--tc-ink)]"
              }`}
            >
              5-Point Grid
            </button>
            <button
              type="button"
              aria-pressed={pointCount === 9}
              onClick={() => resetWizard(9, source)}
              disabled={submitting}
              className={`min-h-14 rounded-xl border-2 px-5 text-base font-bold ${
                pointCount === 9
                  ? "border-[var(--tc-primary)] bg-[var(--tc-mint)] text-[var(--tc-primary)]"
                  : "border-[var(--tc-border-strong)] bg-[var(--tc-surface)] text-[var(--tc-ink)]"
              }`}
            >
              9-Point Grid
            </button>
            <button
              type="button"
              onClick={() => resetWizard(pointCount, source === "head" ? "eyes" : "head")}
              disabled={submitting}
              className="min-h-14 rounded-xl border-2 border-[var(--tc-border-strong)] bg-[var(--tc-surface)] px-5 text-base font-bold text-[var(--tc-ink)] hover:bg-[var(--tc-surface-alt)]"
            >
              Source: {source === "head" ? "Head" : "Eyes"}
            </button>
            <button
              type="button"
              onClick={onClose}
              className="inline-flex min-h-14 items-center gap-2 rounded-xl border-2 border-[var(--tc-border-strong)] bg-[var(--tc-surface-alt)] px-5 text-base font-bold text-[var(--tc-ink)] hover:bg-[var(--tc-alert-bg)]"
            >
              <X className="h-5 w-5" aria-hidden="true" />
              <span>Exit Calibration</span>
            </button>
          </div>
        </div>
      </header>

      <div className="relative flex-1 overflow-hidden">
        {error && (
          <div
            role="alert"
            className="mx-auto mt-6 max-w-xl rounded-2xl border-2 border-[var(--tc-alert)] bg-[var(--tc-alert-bg)] p-5 text-center"
          >
            <p className="text-lg font-bold text-[var(--tc-alert)]">{error}</p>
            <button
              type="button"
              onClick={() => resetWizard()}
              className="mt-4 inline-flex min-h-14 items-center gap-2 rounded-xl bg-[var(--tc-primary)] px-6 text-base font-bold text-white"
            >
              <RotateCcw className="h-5 w-5" aria-hidden="true" />
              <span>Restart Grid</span>
            </button>
          </div>
        )}

        {result ? (
          <div className="flex h-full items-center justify-center p-6">
            <div className="w-full max-w-lg rounded-2xl border-2 border-[var(--tc-primary)] bg-[var(--tc-surface)] p-8 text-center">
              <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-[var(--tc-mint)] text-[var(--tc-primary)]">
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
                  className="inline-flex min-h-14 items-center gap-2 rounded-xl border-2 border-[var(--tc-border-strong)] bg-[var(--tc-surface-alt)] px-6 text-base font-bold text-[var(--tc-ink)]"
                >
                  <RotateCcw className="h-5 w-5" aria-hidden="true" />
                  <span>Calibrate Again</span>
                </button>
                <button
                  type="button"
                  onClick={onClose}
                  className="min-h-14 rounded-xl bg-[var(--tc-primary)] px-8 text-base font-bold text-white hover:bg-[var(--tc-primary-hover)]"
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
            className="absolute flex h-[92px] w-[92px] flex-col items-center justify-center rounded-full border-4 border-[var(--tc-focus)] bg-[var(--tc-primary)] text-white shadow-lg hover:bg-[var(--tc-primary-hover)]"
          >
            <Crosshair className="h-8 w-8" aria-hidden="true" />
            <span className="mt-1 text-sm font-bold tabular-nums">
              {stepIndex + 1}/{dots.length}
            </span>
          </button>
        )}
      </div>
    </div>
  );
}
