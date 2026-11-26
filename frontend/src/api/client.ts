import type {
  CalibrateRequest,
  CalibrateResponse,
  ClinicalEventCreateRequest,
  ClinicalEventRecord,
  DisplaysResponse,
  EngineToggleRequest,
  EngineToggleResponse,
  HealthResponse,
  SessionsResponse,
  SettingsPayload,
  SettingsUpdate,
  SteadyHandSampleSnapshot,
  SystemPermissionsResponse,
} from "../types/telemetry";
import { resolveApiBaseUrl, resolveTauriBackendToken } from "./runtime";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const [apiBase, token] = await Promise.all([
    resolveApiBaseUrl(),
    resolveTauriBackendToken(),
  ]);
  const url = `${apiBase}${path}`;
  let response: Response;
  try {
    response = await fetch(url, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(token ? { "X-ClearCursor-Token": token } : {}),
        ...(init?.headers ?? {}),
      },
    });
  } catch {
    throw new Error(
      `Could not reach the ClearCursor Python backend at ${apiBase}. Verify the local engine is running and retry.`
    );
  }

  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body?.detail) {
        detail = body.detail;
      }
    } catch {
      // keep HTTP status text
    }
    throw new Error(`Request failed (${detail}).`);
  }

  return (await response.json()) as T;
}

export function fetchHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/api/health");
}

export function fetchSettings(): Promise<SettingsPayload> {
  return request<SettingsPayload>("/api/settings");
}

export function saveSettings(updates: SettingsUpdate): Promise<SettingsPayload> {
  return request<SettingsPayload>("/api/settings", {
    method: "POST",
    body: JSON.stringify(updates),
  });
}

export function toggleEngine(
  payload: EngineToggleRequest
): Promise<EngineToggleResponse> {
  return request<EngineToggleResponse>("/api/engine/toggle", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function stopGazeEmergency(): Promise<EngineToggleResponse> {
  return request<EngineToggleResponse>("/api/gaze/stop", {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export function pauseGaze(paused: boolean): Promise<{ paused: boolean }> {
  return request<{ paused: boolean }>("/api/gaze/pause", {
    method: "POST",
    body: JSON.stringify({ paused }),
  });
}

export function clearCalibration(): Promise<{ calibrated: boolean; source: string }> {
  return request<{ calibrated: boolean; source: string }>("/api/gaze/clear-calibration", {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export function submitCalibration(
  payload: CalibrateRequest
): Promise<CalibrateResponse> {
  return request<CalibrateResponse>("/api/calibrate", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function fetchSessions(
  days = 14,
  limit = 30,
  includeSimulated = false
): Promise<SessionsResponse> {
  return request<SessionsResponse>(
    `/api/sessions?days=${encodeURIComponent(days)}&limit=${encodeURIComponent(limit)}&include_simulated=${includeSimulated ? "true" : "false"}`
  );
}

export function createClinicalEvent(
  payload: ClinicalEventCreateRequest
): Promise<ClinicalEventRecord> {
  return request<ClinicalEventRecord>("/api/events", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function deleteClinicalEvent(
  eventId: number
): Promise<{ deleted: boolean; id: number }> {
  return request<{ deleted: boolean; id: number }>(`/api/events/${encodeURIComponent(eventId)}`, {
    method: "DELETE",
  });
}

export function pushSteadyHandSample(
  x: number,
  y: number,
  pressed?: boolean,
  sandbox = false
): Promise<SteadyHandSampleSnapshot> {
  return request<SteadyHandSampleSnapshot>("/api/steadyhand/sample", {
    method: "POST",
    body: JSON.stringify({ x, y, pressed, sandbox }),
  });
}

export function fetchSystemPermissions(): Promise<SystemPermissionsResponse> {
  return request<SystemPermissionsResponse>("/api/system/permissions");
}

export function promptSystemPermissions(
  target: "accessibility" | "input_monitoring" | "camera" = "accessibility",
  openSettings = false
): Promise<SystemPermissionsResponse> {
  return request<SystemPermissionsResponse>("/api/system/permissions/prompt", {
    method: "POST",
    body: JSON.stringify({ target, open_settings: openSettings }),
  });
}

export function fetchDisplays(): Promise<DisplaysResponse> {
  return request<DisplaysResponse>("/api/system/displays");
}
