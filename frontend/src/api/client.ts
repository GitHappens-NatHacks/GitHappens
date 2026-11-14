import type {
  CalibrateRequest,
  CalibrateResponse,
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
import { resolveApiBaseUrl } from "./runtime";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const apiBase = await resolveApiBaseUrl();
  const url = `${apiBase}${path}`;
  let response: Response;
  try {
    response = await fetch(url, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers ?? {}),
      },
    });
  } catch {
    throw new Error(
      `Could not reach the TrueCursor Python backend at ${apiBase}. Verify the local engine is running and retry.`
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
  limit = 30
): Promise<SessionsResponse> {
  return request<SessionsResponse>(
    `/api/sessions?days=${encodeURIComponent(days)}&limit=${encodeURIComponent(limit)}`
  );
}

export function pushSteadyHandSample(
  x: number,
  y: number,
  pressed?: boolean
): Promise<SteadyHandSampleSnapshot> {
  return request<SteadyHandSampleSnapshot>("/api/steadyhand/sample", {
    method: "POST",
    body: JSON.stringify({ x, y, pressed }),
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
