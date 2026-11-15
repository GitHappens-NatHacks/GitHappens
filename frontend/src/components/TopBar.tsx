import {
  Activity,
  Crosshair,
  History,
  Home,
  SlidersHorizontal,
  Square,
  Target,
  Wifi,
  WifiOff,
} from "lucide-react";
import type { ConnectionState } from "../hooks/useTelemetry";
import { BrandLogo } from "./BrandLogo";

export type AppView = "home" | "deck" | "playground" | "sensitivity" | "history";

interface TopBarProps {
  activeView: AppView;
  onNavigate: (view: AppView) => void;
  onStartCalibration: () => void;
  connectionState: ConnectionState;
  onReconnect: () => void;
  gazeActive?: boolean;
  onStopGaze?: () => void;
}

const NAV_ITEMS: { id: AppView; label: string; icon: typeof Activity }[] = [
  { id: "home", label: "Home", icon: Home },
  { id: "deck", label: "Control Deck", icon: Activity },
  { id: "playground", label: "Sandbox Lab", icon: Target },
  { id: "sensitivity", label: "Tuning", icon: SlidersHorizontal },
  { id: "history", label: "Clinician Report", icon: History },
];

export function TopBar({
  activeView,
  onNavigate,
  onStartCalibration,
  connectionState,
  onReconnect,
  gazeActive = false,
  onStopGaze,
}: TopBarProps) {
  const isConnected = connectionState === "connected";
  const statusLabel =
    connectionState === "connected"
      ? "Engine Connected"
      : connectionState === "reconnecting"
      ? "Reconnecting..."
      : connectionState === "connecting"
      ? "Connecting..."
      : "Engine Offline";

  return (
    <header className="sticky top-0 z-40 border-b border-[var(--tc-border)] bg-white/85 text-[var(--tc-ink)] backdrop-blur-xl">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-6 py-3.5">
        <div className="flex items-center gap-3.5">
          <BrandLogo className="h-12 w-12 shrink-0 rounded-xl shadow-sm" />
          <div>
            <h1 className="text-xl font-semibold tracking-tight text-[var(--tc-ink)]">
              TrueCursor
            </h1>
            <p className="text-sm font-medium text-[var(--tc-ink-muted)]">
              Steady Pointer &amp; Hands-Free Gaze
            </p>
          </div>
        </div>

        <nav aria-label="Primary sections" className="flex flex-wrap items-center gap-2 rounded-xl bg-[var(--tc-bg)] p-1.5">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const selected = activeView === item.id;
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => onNavigate(item.id)}
                aria-current={selected ? "page" : undefined}
                className={`inline-flex min-h-14 items-center gap-2.5 rounded-lg px-4 text-base font-semibold transition-all ${
                  selected
                    ? "bg-[var(--tc-primary)] text-white shadow-sm"
                    : "bg-transparent text-[var(--tc-ink)] hover:bg-white/80"
                }`}
              >
                <Icon className="h-5 w-5 shrink-0" aria-hidden="true" />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>

        <div className="flex flex-wrap items-center gap-3">
          {gazeActive && onStopGaze && (
            <button
              type="button"
              onClick={onStopGaze}
              className="inline-flex min-h-14 items-center gap-2 rounded-xl bg-[var(--tc-alert)] px-4 text-base font-bold text-white shadow-sm transition-colors hover:bg-[#7F1D1D]"
            >
              <Square className="h-4 w-4 fill-current" aria-hidden="true" />
              <span>Stop Gaze (Esc)</span>
            </button>
          )}

          <button
            type="button"
            onClick={onStartCalibration}
            className="inline-flex min-h-14 items-center gap-2.5 rounded-xl bg-[var(--tc-primary)] px-5 text-base font-semibold text-white shadow-sm transition-colors hover:bg-[var(--tc-primary-hover)]"
          >
            <Crosshair className="h-5 w-5 shrink-0" aria-hidden="true" />
            <span>Guided Calibration</span>
          </button>

          <button
            type="button"
            onClick={onReconnect}
            title="Click to reconnect telemetry stream"
            aria-label={`WebSocket status: ${statusLabel}. Click to reconnect.`}
            className={`inline-flex min-h-14 items-center gap-2 rounded-xl border px-4 text-sm font-semibold transition-colors ${
              isConnected
                ? "border-[var(--tc-border)] bg-[var(--tc-mint)] text-[var(--tc-primary)] hover:bg-[#DCE8FD]"
                : "border-[var(--tc-alert)]/30 bg-[var(--tc-alert-bg)] text-[var(--tc-alert)]"
            }`}
          >
            {isConnected ? (
              <Wifi className="h-4 w-4 shrink-0" aria-hidden="true" />
            ) : (
              <WifiOff className="h-4 w-4 shrink-0" aria-hidden="true" />
            )}
            <span>{statusLabel}</span>
          </button>
        </div>
      </div>
    </header>
  );
}
