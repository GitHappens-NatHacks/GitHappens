export type GazeSource = "head" | "eyes";

export interface SettingsPayload {
  profile: string;
  assistance_enabled: boolean;
  gaze_control: boolean;
  steady_hand: boolean;
  smart_interface: boolean;
  predictive_speech: boolean;
  blink_select: boolean;
  reduce_complexity: boolean;
  tremor_strength: number;
  tremor_intensity: number;
  one_euro_min_cutoff: number;
  one_euro_beta: number;
  simulate_tremor: boolean;
  anti_drag: boolean;
  anti_drag_threshold_px: number;
  anti_drag_hold_ms: number;
  click_freeze_ms: number;
  gravity_wells: boolean;
  gravity_strength: number;
  global_shortcut: string;
  system_mouse: boolean;
  gaze_source: GazeSource;
  gaze_dwell_ms: number;
  target_size_pct: number;
  font_size_pct: number;
  color_profile: string;
  letter_spacing_px: number;
  tint_color: string;
  tint_opacity: number;
  speech_rate: number;
  screen_width: number;
  screen_height: number;
}

export type SettingsUpdate = Partial<SettingsPayload>;

export interface GazeTelemetry {
  x: number | null;
  y: number | null;
  raw_feature: [number, number] | null;
  ear: number | null;
  face_detected: boolean;
  dwell_progress: number;
  blink: boolean;
  source: GazeSource;
  status: string;
  calibrated: boolean;
  target_id: string | null;
  running: boolean;
}

export interface SteadyHandTelemetry {
  raw_pos: [number, number];
  stable_pos: [number, number];
  strength: number;
  simulate_tremor: boolean;
  tremor_intensity: number;
  spastic_drags_prevented: number;
  slip_clicks_rescued: number;
  click_freeze_active: boolean;
  gravity_well_active: boolean;
  gravity_target_role: string | null;
  os_tap_mode: string;
  os_tap_error: string | null;
  system_mouse_enabled: boolean;
}

export interface SteadyHandSampleSnapshot {
  running: boolean;
  stabilization_active: boolean;
  strength: number;
  simulate_tremor: boolean;
  tremor_intensity: number;
  tremor_hz: number | null;
  tremor_index: number;
  medication_state_estimate: "ON" | "OFF" | null;
  stability_score: number;
  raw_pos: [number, number];
  stable_pos: [number, number];
  spastic_drags_prevented: number;
  slip_clicks_rescued: number;
}

export interface ActiveModes {
  profile: string;
  assistance_enabled: boolean;
  steady_hand: boolean;
  gaze_control: boolean;
  smart_interface: boolean;
  predictive_speech: boolean;
  simulate_tremor: boolean;
}

export interface TelemetryFrame {
  timestamp: number;
  session_id: string;
  tremor_hz: number | null;
  tremor_index: number;
  stabilization_active: boolean;
  stability_score: number;
  medication_state_estimate: "ON" | "OFF" | null;
  gaze: GazeTelemetry;
  steadyhand: SteadyHandTelemetry;
  active_modes: ActiveModes;
}

export interface EngineToggleRequest {
  assistance_enabled?: boolean;
  steady_hand?: boolean;
  gaze_control?: boolean;
  simulate_tremor?: boolean;
  system_mouse?: boolean;
  camera?: boolean;
  camera_index?: number;
}

export interface EngineToggleResponse {
  settings: SettingsPayload;
  camera_running: boolean;
  steadyhand_running: boolean;
}

export interface CalibrateRequest {
  mode: "dots" | "head";
  source: GazeSource;
  profile_name: string;
  features?: [number, number][];
  targets?: [number, number][];
  poses?: Record<string, [number, number]>;
  open_ears?: number[];
}

export interface CalibrateResponse {
  profile_id: number;
  source: string;
  error_px: number;
  calibrated: boolean;
}

export interface SessionSummary {
  session_id: string;
  started_at: number;
  ended_at: number;
  sample_count: number;
  avg_stability_score: number;
  avg_tremor_index: number;
  avg_tremor_hz: number | null;
  had_stabilization: boolean;
}

export interface DailyTrendPoint {
  date: string;
  sample_count: number;
  session_count: number;
  avg_stability_score: number;
  avg_tremor_index: number;
  avg_tremor_hz: number | null;
}

export interface CalibrationProfileSummary {
  id: number;
  name: string;
  source: string;
  error_px: number;
  is_active: boolean;
  created_at: number;
}

export interface SessionsResponse {
  active_session_id: string;
  sessions: SessionSummary[];
  daily_trends: DailyTrendPoint[];
  calibration_profiles: CalibrationProfileSummary[];
}

export interface HealthResponse {
  status: string;
  session_id: string;
  steadyhand_running: boolean;
  gaze_running: boolean;
  calibrated: boolean;
}
