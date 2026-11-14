import { useCallback, useEffect, useState } from "react";
import { fetchSettings, saveSettings, toggleEngine } from "./api/client";
import { AppointmentPlayground } from "./components/AppointmentPlayground";
import { CalibrationWizard } from "./components/CalibrationWizard";
import { ControlDeck } from "./components/ControlDeck";
import { HomeOverview } from "./components/HomeOverview";
import { SensitivityPanel } from "./components/SensitivityPanel";
import { SessionHistory } from "./components/SessionHistory";
import { type AppView, TopBar } from "./components/TopBar";
import { useTelemetry } from "./hooks/useTelemetry";
import type {
  CalibrateResponse,
  EngineToggleRequest,
  SettingsPayload,
  SettingsUpdate,
} from "./types/telemetry";

const DEFAULT_SETTINGS: SettingsPayload = {
  profile: "moderate",
  assistance_enabled: true,
  gaze_control: false,
  steady_hand: true,
  smart_interface: true,
  predictive_speech: false,
  blink_select: true,
  reduce_complexity: true,
  tremor_strength: 100,
  tremor_intensity: 55,
  one_euro_min_cutoff: 0.6,
  one_euro_beta: 0.004,
  simulate_tremor: false,
  anti_drag: true,
  anti_drag_threshold_px: 8.0,
  anti_drag_hold_ms: 300,
  click_freeze_ms: 180,
  gravity_wells: true,
  gravity_strength: 35,
  global_shortcut: "CommandOrControl+Shift+S",
  system_mouse: false,
  gaze_source: "head",
  gaze_dwell_ms: 1100,
  target_size_pct: 140,
  font_size_pct: 110,
  color_profile: "standard",
  letter_spacing_px: 0,
  tint_color: "warm",
  tint_opacity: 10,
  speech_rate: 160,
  screen_width: 1440,
  screen_height: 900,
};

export function App() {
  const [activeView, setActiveView] = useState<AppView>("home");
  const [settings, setSettings] = useState<SettingsPayload>(DEFAULT_SETTINGS);
  const [loadingSettings, setLoadingSettings] = useState<boolean>(true);
  const [busy, setBusy] = useState<boolean>(false);
  const [apiError, setApiError] = useState<string | null>(null);
  const [calibrating, setCalibrating] = useState<boolean>(false);

  const {
    frame,
    smoothedScore,
    smoothedTremorIndex,
    history,
    connectionState,
    errorMessage,
    reconnect,
  } = useTelemetry();

  const loadInitialSettings = useCallback(async () => {
    setLoadingSettings(true);
    setApiError(null);
    try {
      const loaded = await fetchSettings();
      setSettings(loaded);
    } catch (err) {
      setApiError(
        err instanceof Error
          ? err.message
          : "Unable to load initial backend settings."
      );
    } finally {
      setLoadingSettings(false);
    }
  }, []);

  useEffect(() => {
    void loadInitialSettings();
  }, [loadInitialSettings]);

  // Keep UI settings synchronized if the native tray menu or global hotkey toggles backend modes
  useEffect(() => {
    if (!frame) {
      return;
    }
    const nextSteady = frame.active_modes.steady_hand;
    const nextGaze = frame.active_modes.gaze_control;
    const nextSim = frame.active_modes.simulate_tremor;
    const nextSys = frame.steadyhand.system_mouse_enabled;
    const nextAssist = frame.stabilization_active || nextGaze;

    setSettings((prev) => {
      if (
        prev.steady_hand === nextSteady &&
        prev.gaze_control === nextGaze &&
        prev.simulate_tremor === nextSim &&
        prev.system_mouse === nextSys &&
        prev.assistance_enabled === nextAssist
      ) {
        return prev;
      }
      return {
        ...prev,
        steady_hand: nextSteady,
        gaze_control: nextGaze,
        simulate_tremor: nextSim,
        system_mouse: nextSys,
        assistance_enabled: nextAssist,
      };
    });
  }, [frame]);

  const handleToggle = async (payload: EngineToggleRequest) => {
    setBusy(true);
    setApiError(null);
    try {
      const response = await toggleEngine(payload);
      setSettings(response.settings);
    } catch (err) {
      setApiError(
        err instanceof Error ? err.message : "Failed to toggle engine mode."
      );
    } finally {
      setBusy(false);
    }
  };

  const handleSaveSettings = async (updates: SettingsUpdate) => {
    setBusy(true);
    setApiError(null);
    try {
      const updated = await saveSettings(updates);
      setSettings(updated);
    } catch (err) {
      setApiError(
        err instanceof Error ? err.message : "Failed to save settings."
      );
      throw err;
    } finally {
      setBusy(false);
    }
  };

  const handleCalibrationComplete = (_result: CalibrateResponse) => {
    void loadInitialSettings();
  };

  const handleStartStabilizing = async () => {
    if (!settings.steady_hand || !settings.assistance_enabled) {
      await handleToggle({ steady_hand: true, assistance_enabled: true });
    }
    setActiveView("deck");
  };

  return (
    <div className="min-h-screen bg-[var(--tc-bg)] text-[var(--tc-ink)]">
      <TopBar
        activeView={activeView}
        onNavigate={setActiveView}
        onStartCalibration={() => setCalibrating(true)}
        connectionState={connectionState}
        onReconnect={reconnect}
      />

      <main className="mx-auto max-w-6xl px-6 py-8">
        {(apiError || errorMessage) && (
          <div
            role="alert"
            className="mb-6 flex flex-wrap items-center justify-between gap-4 rounded-2xl border-2 border-[var(--tc-alert)] bg-[var(--tc-alert-bg)] p-5 text-[var(--tc-alert)]"
          >
            <p className="text-base font-bold">
              {apiError ?? errorMessage}
            </p>
            <button
              type="button"
              onClick={() => {
                setApiError(null);
                reconnect();
                void loadInitialSettings();
              }}
              className="min-h-14 rounded-xl bg-[var(--tc-alert)] px-5 text-base font-bold text-white"
            >
              Retry Connection
            </button>
          </div>
        )}

        {loadingSettings ? (
          <div className="rounded-2xl border-2 border-[var(--tc-border)] bg-[var(--tc-surface)] p-8 text-lg font-semibold text-[var(--tc-ink-muted)]">
            Connecting to TrueCursor backend...
          </div>
        ) : activeView === "home" ? (
          <HomeOverview
            stabilizationActive={Boolean(settings.assistance_enabled && settings.steady_hand)}
            onStartStabilizing={() => void handleStartStabilizing()}
            onOpenPlayground={() => setActiveView("playground")}
            onOpenControlDeck={() => setActiveView("deck")}
          />
        ) : activeView === "deck" ? (
          <ControlDeck
            settings={settings}
            frame={frame}
            smoothedScore={smoothedScore}
            smoothedTremorIndex={smoothedTremorIndex}
            history={history}
            connectionState={connectionState}
            toggling={busy}
            onToggle={handleToggle}
            onApplyPreset={handleSaveSettings}
            onStartCalibration={() => setCalibrating(true)}
          />
        ) : activeView === "playground" ? (
          <AppointmentPlayground
            settings={settings}
            toggling={busy}
            onToggle={handleToggle}
          />
        ) : activeView === "sensitivity" ? (
          <SensitivityPanel
            settings={settings}
            saving={busy}
            onSave={handleSaveSettings}
          />
        ) : (
          <SessionHistory />
        )}
      </main>

      {calibrating && (
        <CalibrationWizard
          initialSource={settings.gaze_source}
          screenWidth={settings.screen_width}
          screenHeight={settings.screen_height}
          frame={frame}
          onClose={() => setCalibrating(false)}
          onCompleted={handleCalibrationComplete}
        />
      )}
    </div>
  );
}

export default App;
