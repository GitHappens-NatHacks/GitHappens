interface TauriInternals {
  invoke<T>(cmd: string, args?: Record<string, unknown>): Promise<T>;
}

declare global {
  interface Window {
    __TAURI_INTERNALS__?: TauriInternals;
  }
}

let cachedPortPromise: Promise<number | null> | null = null;

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
  const tauriPort = await resolveTauriBackendPort();
  if (tauriPort !== null) {
    return `ws://127.0.0.1:${tauriPort}/ws/telemetry?hz=30`;
  }
  return "ws://localhost:8000/ws/telemetry?hz=30";
}
