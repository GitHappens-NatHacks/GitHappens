import { useEffect, useRef, useState } from "react";
import type { SettingsPayload, TelemetryFrame } from "../types/telemetry";

interface GazeCursorOverlayProps {
  frame: TelemetryFrame | null;
  settings: SettingsPayload;
}

const CLICK_COOLDOWN_MS = 750;
const RING_RADIUS = 22;
const RING_CIRCUMFERENCE = 2 * Math.PI * RING_RADIUS;

function findInteractiveTarget(x: number, y: number): HTMLElement | null {
  if (typeof document === "undefined" || typeof document.elementFromPoint !== "function") {
    return null;
  }
  const el = document.elementFromPoint(x, y);
  if (!el) {
    return null;
  }
  const interactive = el.closest<HTMLElement>(
    'button:not([disabled]), a[href], [role="button"], input:not([disabled]), select:not([disabled])'
  );
  if (!interactive) {
    return null;
  }
  return interactive;
}

export function GazeCursorOverlay({ frame, settings }: GazeCursorOverlayProps) {
  const gaze = frame?.gaze;
  const active = Boolean(gaze?.running && (settings.gaze_control || frame?.active_modes.gaze_control));

  const [domProgress, setDomProgress] = useState<number>(0);
  const [pulseClick, setPulseClick] = useState<boolean>(false);
  const [renderPos, setRenderPos] = useState<{ x: number; y: number } | null>(null);

  const hoverTargetRef = useRef<HTMLElement | null>(null);
  const hoverStartRef = useRef<number>(0);
  const lastClickAtRef = useRef<number>(0);
  const lastBlinkRef = useRef<boolean>(false);
  const renderPosRef = useRef<{ x: number; y: number } | null>(null);

  // Only show the head-controlled cursor after calibration is complete
  let vx: number | null = null;
  let vy: number | null = null;

  if (
    active &&
    gaze &&
    gaze.calibrated &&
    gaze.x !== null &&
    gaze.y !== null &&
    typeof window !== "undefined"
  ) {
    const sw = Math.max(1, settings.screen_width || 1440);
    const sh = Math.max(1, settings.screen_height || 900);
    vx = Math.min(window.innerWidth - 8, Math.max(8, (gaze.x / sw) * window.innerWidth));
    vy = Math.min(window.innerHeight - 8, Math.max(8, (gaze.y / sh) * window.innerHeight));
  }

  const posRef = useRef<{ x: number | null; y: number | null }>({ x: vx, y: vy });
  posRef.current = { x: vx, y: vy };

  const blinkNow = Boolean(gaze?.blink);
  const blinkJustFired = blinkNow && !lastBlinkRef.current;
  lastBlinkRef.current = blinkNow;

  useEffect(() => {
    if (!active) {
      hoverTargetRef.current = null;
      hoverStartRef.current = 0;
      renderPosRef.current = null;
      setRenderPos(null);
      setDomProgress(0);
      return;
    }

    let rafId = 0;
    const dwellMs = Math.max(300, settings.gaze_dwell_ms || 1100);

    const tick = (now: number) => {
      const { x, y } = posRef.current;
      if (x === null || y === null) {
        hoverTargetRef.current = null;
        hoverStartRef.current = 0;
        renderPosRef.current = null;
        setRenderPos(null);
        setDomProgress(0);
        rafId = window.requestAnimationFrame(tick);
        return;
      }

      // Smooth 60fps chase toward the latest 30Hz backend coordinate with zero CSS lag
      const prev = renderPosRef.current;
      let sx = x;
      let sy = y;
      if (prev && Math.hypot(x - prev.x, y - prev.y) < 320) {
        sx = prev.x + (x - prev.x) * 0.45;
        sy = prev.y + (y - prev.y) * 0.45;
      }
      renderPosRef.current = { x: sx, y: sy };
      setRenderPos({ x: sx, y: sy });

      const target = findInteractiveTarget(sx, sy);
      if (!target) {
        hoverTargetRef.current = null;
        hoverStartRef.current = 0;
        setDomProgress(0);
        rafId = window.requestAnimationFrame(tick);
        return;
      }

      if (hoverTargetRef.current !== target) {
        hoverTargetRef.current = target;
        hoverStartRef.current = now;
      }

      if (now - lastClickAtRef.current < CLICK_COOLDOWN_MS) {
        setDomProgress(0);
        rafId = window.requestAnimationFrame(tick);
        return;
      }

      const elapsed = now - hoverStartRef.current;
      const progress = Math.min(1, Math.max(0, elapsed / dwellMs));
      setDomProgress(progress);

      if (progress >= 1) {
        lastClickAtRef.current = now;
        hoverStartRef.current = now;
        setDomProgress(0);
        setPulseClick(true);
        window.setTimeout(() => setPulseClick(false), 260);
        target.click();
      }

      rafId = window.requestAnimationFrame(tick);
    };

    rafId = window.requestAnimationFrame(tick);
    return () => {
      window.cancelAnimationFrame(rafId);
    };
  }, [active, settings.gaze_dwell_ms]);

  useEffect(() => {
    if (!active || !settings.blink_select || !blinkJustFired) {
      return;
    }
    const target = hoverTargetRef.current;
    const now = performance.now();
    if (target && domProgress >= 0.2 && now - lastClickAtRef.current >= CLICK_COOLDOWN_MS) {
      lastClickAtRef.current = now;
      hoverStartRef.current = now;
      setDomProgress(0);
      setPulseClick(true);
      window.setTimeout(() => setPulseClick(false), 260);
      target.click();
    }
  }, [active, blinkJustFired, domProgress, settings.blink_select]);

  if (!active || vx === null || vy === null) {
    return null;
  }

  const displayX = renderPos?.x ?? vx;
  const displayY = renderPos?.y ?? vy;
  const effectiveProgress = Math.max(domProgress, gaze?.dwell_progress ?? 0);
  const dashOffset = RING_CIRCUMFERENCE * (1 - Math.min(1, Math.max(0, effectiveProgress)));

  return (
    <div
      aria-hidden="true"
      data-testid="gaze-cursor-overlay"
      className="pointer-events-none fixed inset-0 z-50 overflow-hidden"
    >
      <div
        style={{
          transform: `translate3d(${displayX}px, ${displayY}px, 0) translate(-50%, -50%)`,
        }}
        className="absolute left-0 top-0"
      >
        <div className="relative flex items-center justify-center">
          <svg
            width="56"
            height="56"
            viewBox="0 0 56 56"
            className="-rotate-90 drop-shadow-sm"
          >
            <circle
              cx="28"
              cy="28"
              r={RING_RADIUS}
              fill="none"
              stroke="rgba(15, 45, 89, 0.22)"
              strokeWidth="4"
            />
            {effectiveProgress > 0.01 && (
              <circle
                cx="28"
                cy="28"
                r={RING_RADIUS}
                fill="none"
                stroke="#1D4ED8"
                strokeWidth="4.5"
                strokeLinecap="round"
                strokeDasharray={RING_CIRCUMFERENCE}
                strokeDashoffset={dashOffset}
              />
            )}
          </svg>

          <span
            className={`absolute h-4 w-4 rounded-full border-2 border-white shadow-md transition-transform ${
              pulseClick
                ? "scale-150 bg-[#0F2D59]"
                : effectiveProgress > 0.05
                  ? "scale-110 bg-[#1D4ED8]"
                  : "bg-[#0F2D59]"
            }`}
          />
        </div>
      </div>
    </div>
  );
}
