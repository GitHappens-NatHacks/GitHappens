import { Activity, Crosshair, History, SlidersHorizontal, Target, Wifi, WifiOff } from "lucide-react";
import type { ConnectionState } from "../hooks/useTelemetry";

export type AppView = "deck" | "playground" | "sensitivity" | "history";

interface TopBarProps {
  activeView: AppView;
  onNavigate: (view: AppView) => void;
  onStartCalibration: () => void;
  connectionState: ConnectionState;
  onReconnect: () => void;
}

const NAV_ITEMS: { id: AppView; label: string; icon: typeof Activity }[] = [
  { id: "deck", label: "Control Deck", icon: Activity },
  { id: "playground", label: "Appointment Lab", icon: Target },
  { id: "sensitivity", label: "Sensitivity & Filter", icon: SlidersHorizontal },
  { id: "history", label: "Session History", icon: History },
];

export function TopBar({
  activeView,
  onNavigate,
  onStartCalibration,
  connectionState,
  onReconnect,
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
    <header className="border-b-2 border-[var(--tc-border)] bg-[var(--tc-primary)] text-[var(--tc-on-primary)]">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-6 py-4">
        <div className="flex items-center gap-4">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-[var(--tc-surface)] text-[var(--tc-primary)]">
            <Crosshair className="h-7 w-7" aria-hidden="true" />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight text-white">
              TrueCursor
            </h1>
            <p className="text-sm text-[#DCEAE4]">
              Motor Stabilization &amp; Gaze Control
            </p>
          </div>
        </div>

        <nav aria-label="Primary sections" className="flex flex-wrap items-center gap-4">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const selected = activeView === item.id;
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => onNavigate(item.id)}
                aria-current={selected ? "page" : undefined}
                className={`inline-flex min-h-14 items-center gap-3 rounded-xl px-5 text-base font-semibold transition-colors ${
                  selected
                    ? "bg-[var(--tc-surface)] text-[var(--tc-primary)]"
                    : "border-2 border-[#4E8572] bg-transparent text-white hover:bg-[#0D5C45]"
                }`}
              >
                <Icon className="h-5 w-5 shrink-0" aria-hidden="true" />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>

        <div className="flex flex-wrap items-center gap-4">
          <button
            type="button"
            onClick={onStartCalibration}
            className="inline-flex min-h-14 items-center gap-3 rounded-xl border-2 border-white bg-[#013828] px-5 text-base font-semibold text-white hover:bg-[#01291D]"
          >
            <Crosshair className="h-5 w-5 shrink-0" aria-hidden="true" />
            <span>Guided Calibration</span>
          </button>

          <button
            type="button"
            onClick={onReconnect}
            title="Click to reconnect telemetry stream"
            aria-label={`WebSocket status: ${statusLabel}. Click to reconnect.`}
            className={`inline-flex min-h-14 items-center gap-2.5 rounded-xl px-4 text-sm font-semibold ${
              isConnected
                ? "bg-[var(--tc-mint)] text-[var(--tc-ink)]"
                : "bg-[var(--tc-alert-bg)] text-[var(--tc-alert)]"
            }`}
          >
            {isConnected ? (
              <Wifi className="h-5 w-5 shrink-0" aria-hidden="true" />
            ) : (
              <WifiOff className="h-5 w-5 shrink-0" aria-hidden="true" />
            )}
            <span>{statusLabel}</span>
          </button>
        </div>
      </div>
    </header>
  );
}
