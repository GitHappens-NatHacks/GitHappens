import type {
  CalibrateRequest,
  CalibrateResponse,
  EngineToggleRequest,
  EngineToggleResponse,
  HealthResponse,
  SessionsResponse,
  SettingsPayload,
  SettingsUpdate,
} from "../types/telemetry";

const API_BASE =
  (import.meta.env.VITE_API_BASE as string | undefined)?.replace(/\/$/, "") ??
  "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${API_BASE}${path}`;
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
      "Could not reach the TrueCursor Python backend on port 8000. Verify uvicorn is running and retry."
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
): Promise<Record<string, unknown>> {
  return request<Record<string, unknown>>("/api/steadyhand/sample", {
    method: "POST",
    body: JSON.stringify({ x, y, pressed }),
  });
}
