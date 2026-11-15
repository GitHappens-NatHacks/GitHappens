import { Camera, SunMedium, UserCheck, UserX } from "lucide-react";
import { useEffect, useState } from "react";
import { resolveApiBaseUrl } from "../api/runtime";
import type { GazeTelemetry } from "../types/telemetry";

interface GazePreviewFeedProps {
  gaze: GazeTelemetry | null | undefined;
  active: boolean;
  compact?: boolean;
}

export function GazePreviewFeed({
  gaze,
  active,
  compact = false,
}: GazePreviewFeedProps) {
  const [apiBase, setApiBase] = useState<string>("");
  const [streamError, setStreamError] = useState<boolean>(false);
  const [streamNonce, setStreamNonce] = useState<number>(0);

  useEffect(() => {
    let mounted = true;
    void resolveApiBaseUrl().then((base) => {
      if (mounted) {
        setApiBase(base);
      }
    });
    return () => {
      mounted = false;
    };
  }, []);

  const isRunning = active && Boolean(gaze?.running);

  useEffect(() => {
    if (isRunning) {
      setStreamError(false);
      setStreamNonce((n) => n + 1);
    }
  }, [isRunning]);

  useEffect(() => {
    if (!isRunning || !streamError) {
      return;
    }
    const timer = window.setTimeout(() => {
      setStreamError(false);
      setStreamNonce((n) => n + 1);
    }, 650);
    return () => window.clearTimeout(timer);
  }, [isRunning, streamError]);

  const faceDetected = Boolean(gaze?.face_detected);
  const lighting = gaze?.lighting_quality ?? "ok";

  return (
    <div
      className={`overflow-hidden rounded-xl border border-[var(--tc-border)] bg-[var(--tc-surface)] shadow-[var(--tc-shadow)] ${
        compact ? "w-52 sm:w-60" : "w-full"
      }`}
    >
      <div className="relative aspect-video w-full bg-[#0B1324]">
        {isRunning && !streamError ? (
          <img
            src={`${apiBase}/api/gaze/preview?v=${streamNonce}`}
            alt="Live GazeCam webcam preview"
            onError={() => setStreamError(true)}
            className="h-full w-full object-cover"
          />
        ) : (
          <div className="flex h-full w-full flex-col items-center justify-center gap-2 px-4 text-center text-sm text-slate-300">
            <Camera className="h-7 w-7 text-slate-400" aria-hidden="true" />
            <span className="font-medium">
              {active
                ? streamError
                  ? "Camera stream unavailable. Check macOS Camera permission."
                  : "Starting camera stream..."
                : "Enable GazeControl Tracking to view live camera feed."}
            </span>
          </div>
        )}

        {isRunning && (
          <div className="pointer-events-none absolute inset-x-2.5 bottom-2.5 flex flex-wrap items-center justify-between gap-2">
            <span
              className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold backdrop-blur-md ${
                faceDetected
                  ? "bg-[#0F2D59]/85 text-white"
                  : "bg-[#9F1239]/90 text-white"
              }`}
            >
              {faceDetected ? (
                <UserCheck className="h-3.5 w-3.5" aria-hidden="true" />
              ) : (
                <UserX className="h-3.5 w-3.5" aria-hidden="true" />
              )}
              <span>{faceDetected ? "Face Locked" : "No Face"}</span>
            </span>

            {lighting !== "ok" && (
              <span className="inline-flex items-center gap-1 rounded-full bg-amber-900/90 px-2.5 py-1 text-xs font-semibold text-amber-100 backdrop-blur-md">
                <SunMedium className="h-3.5 w-3.5" aria-hidden="true" />
                <span>
                  {lighting === "low_light"
                    ? "Low Light"
                    : lighting === "backlit"
                      ? "Backlit"
                      : "Overexposed"}
                </span>
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
