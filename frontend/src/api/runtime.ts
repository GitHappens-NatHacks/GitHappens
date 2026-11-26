interface TauriInternals {
  invoke<T>(cmd: string, args?: Record<string, unknown>): Promise<T>;
}

declare global {
  interface Window {
    __TAURI_INTERNALS__?: TauriInternals;
  }
}

let cachedPortPromise: Promise<number | null> | null = null;
let cachedTokenPromise: Promise<string | null> | null = null;

export function isTauriRuntime(): boolean {
  return typeof window !== "undefined" && Boolean(window.__TAURI_INTERNALS__);
}

export function resolveTauriBackendPort(): Promise<number | null> {
  if (!isTauriRuntime()) {
    return Promise.resolve(null);
  }
  if (cachedPortPromise === null) {
    cachedPortPromise = window.__TAURI_INTERNALS__!
      .invoke<number>("get_backend_port")
      .then((port) => (Number.isFinite(port) && port > 0 ? port : 8000))
      .catch(() => 8000);
  }
  return cachedPortPromise;
}

export function resolveTauriBackendToken(): Promise<string | null> {
  if (!isTauriRuntime()) {
    return Promise.resolve(null);
  }
  if (cachedTokenPromise === null) {
    cachedTokenPromise = window.__TAURI_INTERNALS__!
      .invoke<string>("get_backend_token")
      .then((token) => (token && token.trim().length > 0 ? token.trim() : null))
      .catch(() => null);
  }
  return cachedTokenPromise;
}

export async function syncTauriTrayState(
  active: boolean,
  statusText?: string,
  minimizeToTray?: boolean
): Promise<void> {
  if (!isTauriRuntime()) {
    return;
  }
  await window.__TAURI_INTERNALS__!
    .invoke<void>("sync_tray_state", {
      active,
      statusText: statusText ?? null,
      minimizeToTray: minimizeToTray ?? null,
    })
    .catch(() => undefined);
}

export async function updateTauriGlobalShortcut(shortcut: string): Promise<boolean> {
  if (!isTauriRuntime()) {
    return false;
  }
  return window.__TAURI_INTERNALS__!
    .invoke<boolean>("update_global_shortcut", { shortcut })
    .catch(() => false);
}

export async function resolveApiBaseUrl(): Promise<string> {
  const configured = (import.meta.env.VITE_API_BASE as string | undefined)?.replace(/\/$/, "");
  if (configured && configured.length > 0) {
    return configured;
  }
  const tauriPort = await resolveTauriBackendPort();
  if (tauriPort !== null) {
    return `http://127.0.0.1:${tauriPort}`;
  }
  return "";
}

export async function resolveTelemetryWsUrl(): Promise<string> {
  const configured = (import.meta.env.VITE_WS_URL as string | undefined)?.trim();
  if (configured && configured.length > 0) {
    return configured;
  }
  const [tauriPort, token] = await Promise.all([
    resolveTauriBackendPort(),
    resolveTauriBackendToken(),
  ]);
  const tokenQuery = token ? `&token=${encodeURIComponent(token)}` : "";
  if (tauriPort !== null) {
    return `ws://127.0.0.1:${tauriPort}/ws/telemetry?hz=30${tokenQuery}`;
  }
  return `ws://localhost:8000/ws/telemetry?hz=30${tokenQuery}`;
}
