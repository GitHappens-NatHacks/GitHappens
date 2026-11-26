import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as client from "../api/client";
import { App } from "../App";
import { AppointmentPlayground } from "../components/AppointmentPlayground";
import { CalibrationWizard } from "../components/CalibrationWizard";
import { ControlDeck } from "../components/ControlDeck";
import { HomeOverview } from "../components/HomeOverview";
import { SensitivityPanel } from "../components/SensitivityPanel";
import { SessionHistory } from "../components/SessionHistory";
import type { SessionsResponse, SettingsPayload, TelemetryFrame } from "../types/telemetry";

const { mockPdfSave, mockPdfText, mockAutoTable } = vi.hoisted(() => ({
  mockPdfSave: vi.fn(),
  mockPdfText: vi.fn(),
  mockAutoTable: vi.fn((doc: { lastAutoTable?: { finalY: number } }) => {
    doc.lastAutoTable = { finalY: 200 };
  }),
}));

vi.mock("jspdf", () => {
  class MockJsPDF {
    setFontSize = vi.fn();
    setTextColor = vi.fn();
    setDrawColor = vi.fn();
    setFillColor = vi.fn();
    setLineWidth = vi.fn();
    rect = vi.fn();
    line = vi.fn();
    text = mockPdfText;
    addPage = vi.fn();
    save = mockPdfSave;
  }
  return { jsPDF: MockJsPDF };
});

vi.mock("jspdf-autotable", () => ({
  default: (doc: { lastAutoTable?: { finalY: number } }, opts: unknown) => {
    void opts;
    return mockAutoTable(doc);
  },
}));

const BASE_SETTINGS: SettingsPayload = {
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
  adaptive_smoothing: true,
  simulate_tremor: false,
  anti_drag: true,
  anti_drag_threshold_px: 8,
  anti_drag_hold_ms: 180,
  click_freeze_ms: 180,
  click_debounce_ms: 70,
  right_click_guard: true,
  scroll_smoothing: true,
  gravity_wells: true,
  gravity_strength: 35,
  bypass_key: "alt",
  precision_key: "none",
  excluded_apps: [],
  global_shortcut: "CommandOrControl+Shift+S",
  resume_stabilization_on_launch: false,
  minimize_to_tray: true,
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

const BASE_FRAME: TelemetryFrame = {
  timestamp: 1700000100,
  session_id: "sess-ui",
  tremor_hz: 5.4,
  tremor_index: 32,
  resting_band_pct: 22.0,
  action_band_pct: 10.0,
  rms_amplitude_px: 4.5,
  rms_amplitude_mm: 1.19,
  tremor_severity: "moderate",
  stabilization_active: true,
  stability_score: 88.5,
  medication_state_estimate: "ON",
  gaze: {
    x: 720,
    y: 450,
    raw_feature: [0.5, 0.5],
    ear: 0.28,
    face_detected: true,
    dwell_progress: 0.3,
    blink: false,
    source: "head",
    status: "Tracking",
    calibrated: true,
    target_id: null,
    running: true,
  },
  steadyhand: {
    raw_pos: [120, 140],
    stable_pos: [118, 139],
    strength: 1.0,
    simulate_tremor: false,
    tremor_intensity: 55,
    spastic_drags_prevented: 4,
    slip_clicks_rescued: 2,
    double_clicks_blocked: 1,
    scroll_jitters_filtered: 3,
    click_freeze_active: true,
    gravity_well_active: true,
    gravity_target_role: "AXButton",
    bypass_active: false,
    precision_active: false,
    excluded_app_active: null,
    os_tap_mode: "quartz_cgeventtap",
    os_tap_error: null,
    system_mouse_enabled: true,
  },
  active_modes: {
    profile: "moderate",
    assistance_enabled: true,
    steady_hand: true,
    gaze_control: false,
    smart_interface: true,
    predictive_speech: false,
    simulate_tremor: false,
  },
};

describe("ClearCursor Frontend Suite", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders HomeOverview offline editorial illustrations cleanly and triggers navigation", () => {
    const onStart = vi.fn();
    const onPlay = vi.fn();
    const onDeck = vi.fn();
    const { container } = render(
      <HomeOverview
        stabilizationActive={false}
        onStartStabilizing={onStart}
        onOpenPlayground={onPlay}
        onOpenControlDeck={onDeck}
      />
    );

    expect(container.textContent).not.toContain("\u2014");
    expect(screen.getByText("Calm Everyday Desktop Control")).toBeInTheDocument();
    expect(screen.getByText(/ClearCursor Assistive Desktop/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Start Stabilizing/i }));
    expect(onStart).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole("button", { name: /Try Sandbox Playground/i }));
    expect(onPlay).toHaveBeenCalledTimes(1);
  });

  it("handles ControlDeck medication presets and displays Gravity Well + click protection telemetry", async () => {
    const onToggle = vi.fn().mockResolvedValue(undefined);
    const onApplyPreset = vi.fn().mockResolvedValue(undefined);
    const onCal = vi.fn();

    render(
      <ControlDeck
        settings={BASE_SETTINGS}
        frame={BASE_FRAME}
        smoothedScore={88.5}
        smoothedTremorIndex={32.0}
        history={[{ timestamp: 1, tremorHz: 5.4, tremorIndex: 32, stabilityScore: 88.5 }]}
        connectionState="connected"
        toggling={false}
        onToggle={onToggle}
        onApplyPreset={onApplyPreset}
        onStartCalibration={onCal}
      />
    );

    expect(screen.getByText(/Gravity Wells: Locked \(Button\)/i)).toBeInTheDocument();
    expect(screen.getByText(/Frozen/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Hands-Free \(Gaze Mode\)/i }));
    await waitFor(() => {
      expect(onApplyPreset).toHaveBeenCalledTimes(1);
      expect(onToggle).toHaveBeenCalledWith({
        gaze_control: true,
        camera: true,
        steady_hand: false,
        assistance_enabled: true,
      });
    });
  });

  it("opens Advanced Tuning and Per-App Exclusions in SensitivityPanel and persists to SQLite", async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    render(<SensitivityPanel settings={BASE_SETTINGS} saving={false} onSave={onSave} />);

    // Add excluded app quick button
    fireEvent.click(screen.getByRole("button", { name: /\+ Figma/i }));
    expect(screen.getByText("Figma")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Advanced Tuning/i }));
    const incFreeze = screen.getByRole("button", { name: /Increase Click-Freeze Duration by 20 ms/i });
    fireEvent.click(incFreeze);

    fireEvent.click(screen.getByRole("button", { name: /Save Settings/i }));
    await waitFor(() => {
      expect(onSave).toHaveBeenCalledWith(
        expect.objectContaining({
          click_freeze_ms: 200,
          excluded_apps: ["Figma"],
        })
      );
    });
    expect(screen.getByText(/Settings saved to SQLite/i)).toBeInTheDocument();
  });

  it("scores 10-step target hits/misses in sandbox mode and everyday controls in AppointmentPlayground", async () => {
    const sampleSpy = vi.spyOn(client, "pushSteadyHandSample").mockResolvedValue({
      running: true,
      stabilization_active: true,
      strength: 1.0,
      simulate_tremor: false,
      tremor_intensity: 55,
      tremor_hz: 5.0,
      tremor_index: 12.0,
      medication_state_estimate: "ON",
      stability_score: 94.0,
      raw_pos: [112, 132],
      stable_pos: [112, 132],
      spastic_drags_prevented: 0,
      slip_clicks_rescued: 0,
    });
    const onToggle = vi.fn().mockResolvedValue(undefined);

    const { container } = render(
      <AppointmentPlayground settings={BASE_SETTINGS} toggling={false} onToggle={onToggle} />
    );
    const canvas = container.querySelector("canvas")!;
    canvas.getBoundingClientRect = () =>
      ({ left: 0, top: 0, width: 880, height: 340, right: 880, bottom: 340 } as DOMRect);

    // Hit Target 1 ("1. Doctor" center ~ (112, 132)) with sandbox=true
    fireEvent.pointerDown(canvas, { clientX: 112, clientY: 132 });
    await waitFor(() => expect(screen.getByText("Hits: 1")).toBeInTheDocument());
    expect(sampleSpy).toHaveBeenCalledWith(expect.any(Number), expect.any(Number), true, true);

    // Miss intentionally outside any target box
    fireEvent.pointerDown(canvas, { clientX: 5, clientY: 5 });
    await waitFor(() => expect(screen.getByText("Misses: 1")).toBeInTheDocument());

    const tapBtn = screen.getByRole("button", { name: /Tap Cleanly to Test Click-Freeze/i });
    fireEvent.click(tapBtn);
    expect(screen.getByText("1 clicks")).toBeInTheDocument();
  });

  it("exports formula-safe CSV, vector PDF report, and supports Clinical Event Diary in SessionHistory", async () => {
    const payload: SessionsResponse = {
      active_session_id: "s1",
      sessions: [
        {
          session_id: "s1",
          started_at: 1700000000,
          ended_at: 1700000500,
          sample_count: 12,
          avg_stability_score: 91.4,
          avg_tremor_index: 18.2,
          avg_resting_band_pct: 12.1,
          avg_action_band_pct: 6.1,
          avg_rms_amplitude_px: 3.4,
          avg_rms_amplitude_mm: 0.9,
          avg_tremor_hz: 5.3,
          had_stabilization: true,
          click_rescues: 5,
          drags_prevented: 3,
          bounces_blocked: 2,
        },
      ],
      daily_trends: [
        {
          date: "2026-11-14",
          sample_count: 12,
          session_count: 1,
          avg_stability_score: 91.4,
          avg_tremor_index: 18.2,
          avg_resting_band_pct: 12.1,
          avg_action_band_pct: 6.1,
          avg_rms_amplitude_mm: 0.9,
          avg_tremor_hz: 5.3,
        },
      ],
      hourly_profile: [
        {
          hour: 9,
          label: "09:00",
          sample_count: 12,
          avg_stability_score: 91.4,
          avg_tremor_index: 18.2,
          avg_resting_band_pct: 12.1,
          avg_action_band_pct: 6.1,
          avg_rms_amplitude_mm: 0.9,
        },
      ],
      functional_summary: {
        total_samples: 12,
        total_sessions: 1,
        total_click_rescues: 5,
        total_drags_prevented: 3,
        total_bounces_blocked: 2,
        avg_rms_amplitude_mm: 0.9,
        avg_resting_band_pct: 12.1,
        avg_action_band_pct: 6.1,
      },
      clinical_events: [
        {
          id: 1,
          timestamp: 1700000100,
          event_type: "medication",
          label: "Levodopa Dose",
          dosage: "100mg",
          severity: null,
          notes: "Morning dose",
        },
      ],
      simulated_sample_count: 4,
      calibration_profiles: [
        {
          id: 7,
          name: "=CMD('calc')",
          source: "head",
          error_px: 31.2,
          is_active: true,
          created_at: 1700000010,
        },
      ],
    };
    const fetchSpy = vi.spyOn(client, "fetchSessions").mockResolvedValue(payload);
    const createEventSpy = vi.spyOn(client, "createClinicalEvent").mockResolvedValue({
      id: 2,
      timestamp: 1700000200,
      event_type: "medication",
      label: "Medication Dose Taken",
      dosage: "",
      severity: null,
      notes: "",
    });

    let capturedCsv = "";
    const originalBlob = globalThis.Blob;
    vi.stubGlobal(
      "Blob",
      class extends originalBlob {
        constructor(parts?: BlobPart[], options?: BlobPropertyBag) {
          super(parts, options);
          if (parts && typeof parts[0] === "string") {
            capturedCsv = parts[0];
          }
        }
      }
    );
    URL.createObjectURL = vi.fn(() => "blob:mock-url");
    URL.revokeObjectURL = vi.fn();
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});

    render(<SessionHistory />);
    await waitFor(() => expect(screen.getByText("=CMD('calc')")).toBeInTheDocument());
    expect(screen.getByText(/How to Read This Clinical Motor Data/i)).toBeInTheDocument();
    expect(screen.getByText(/4 demo windows excluded/i)).toBeInTheDocument();
    expect(screen.getByText("Levodopa Dose")).toBeInTheDocument();

    // Quick diary log button
    fireEvent.click(screen.getByRole("button", { name: /\+ Medication Taken/i }));
    await waitFor(() => expect(createEventSpy).toHaveBeenCalledTimes(1));

    // Date range switch
    fireEvent.click(screen.getByRole("button", { name: "30 Days" }));
    await waitFor(() => expect(fetchSpy).toHaveBeenCalledWith(30, 50, false));

    fireEvent.click(screen.getByRole("button", { name: /Export CSV Data/i }));
    expect(capturedCsv).toContain("\"'=CMD('calc')\"");
    expect(capturedCsv).toContain("Levodopa Dose");

    fireEvent.click(screen.getByRole("button", { name: /Export Clinician Report \(PDF\)/i }));
    expect(mockPdfText).toHaveBeenCalledWith(
      "ClearCursor Clinician Motor Telemetry Report",
      expect.any(Number),
      expect.any(Number)
    );
    expect(mockPdfText).toHaveBeenCalledWith(
      "How to Read This Clinical Motor Report",
      expect.any(Number),
      expect.any(Number)
    );
    expect(mockPdfSave).toHaveBeenCalledTimes(1);
    vi.unstubAllGlobals();
  });

  it("handles transient failure on final CalibrationWizard dot without exceeding 5 points", async () => {
    const spy = vi
      .spyOn(client, "submitCalibration")
      .mockRejectedValueOnce(new Error("Temporary timeout"))
      .mockResolvedValueOnce({
        profile_id: 9,
        source: "head",
        error_px: 28.4,
        calibrated: true,
      });
    const onCompleted = vi.fn();

    render(
      <CalibrationWizard
        initialSource="head"
        screenWidth={1440}
        screenHeight={900}
        frame={BASE_FRAME}
        onClose={vi.fn()}
        onCompleted={onCompleted}
      />
    );

    for (let i = 0; i < 5; i += 1) {
      fireEvent.click(screen.getByRole("button", { name: /Calibration target/i }));
    }
    await waitFor(() => expect(screen.getByText("Temporary timeout")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: /Calibration target/i }));
    await waitFor(() => expect(screen.getByText("Calibration Complete")).toBeInTheDocument());
    expect(spy.mock.calls[1][0].features).toHaveLength(5);
    expect(onCompleted).toHaveBeenCalledTimes(1);
  });

  it("shows macOS Accessibility prompt banner and triggers prompt endpoint on click", async () => {
    vi.spyOn(client, "fetchSettings").mockResolvedValueOnce(BASE_SETTINGS);
    vi.spyOn(client, "fetchSystemPermissions").mockResolvedValueOnce({
      platform: "macos",
      accessibility_trusted: false,
      input_monitoring_trusted: true,
      needs_prompt: true,
      message: "macOS Accessibility permission is needed.",
    });
    const promptSpy = vi.spyOn(client, "promptSystemPermissions").mockResolvedValueOnce({
      platform: "macos",
      accessibility_trusted: true,
      input_monitoring_trusted: true,
      needs_prompt: false,
      message: null,
    });

    render(<App />);
    await waitFor(() =>
      expect(screen.getByText("System Pointer Permission Needed")).toBeInTheDocument()
    );
    fireEvent.click(screen.getByRole("button", { name: /Prompt Permission/i }));
    await waitFor(() =>
      expect(promptSpy).toHaveBeenCalledWith("accessibility", false)
    );
  });
});
