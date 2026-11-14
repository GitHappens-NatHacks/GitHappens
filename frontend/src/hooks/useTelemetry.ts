import { useEffect, useRef, useState } from "react";
import type { TelemetryFrame } from "../types/telemetry";

export type ConnectionState =
  | "connecting"
  | "connected"
  | "reconnecting"
  | "disconnected";

export interface TelemetryPoint {
  timestamp: number;
  tremorHz: number | null;
  tremorIndex: number;
  stabilityScore: number;
}

export interface UseTelemetryResult {
  frame: TelemetryFrame | null;
  smoothedScore: number;
  smoothedTremorIndex: number;
  history: TelemetryPoint[];
  connectionState: ConnectionState;
  errorMessage: string | null;
  reconnect: () => void;
}

const DEFAULT_WS_URL = "ws://localhost:8000/ws/telemetry?hz=25";
const MAX_HISTORY_POINTS = 75;
const EMA_ALPHA = 0.25;

function resolveWsUrl(): string {
  const configured = import.meta.env.VITE_WS_URL as string | undefined;
  if (configured && configured.trim().length > 0) {
    return configured.trim();
  }
  return DEFAULT_WS_URL;
}

export function useTelemetry(): UseTelemetryResult {
  const [frame, setFrame] = useState<TelemetryFrame | null>(null);
  const [smoothedScore, setSmoothedScore] = useState<number>(100);
  const [smoothedTremorIndex, setSmoothedTremorIndex] = useState<number>(0);
  const [history, setHistory] = useState<TelemetryPoint[]>([]);
  const [connectionState, setConnectionState] =
    useState<ConnectionState>("connecting");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [retryToken, setRetryToken] = useState<number>(0);

  const scoreRef = useRef<number>(100);
  const indexRef = useRef<number>(0);

  useEffect(() => {
    let active = true;
    let socket: WebSocket | null = null;
    let reconnectTimer: number | null = null;
    let attempt = 0;

    const connect = () => {
      if (!active) {
        return;
      }
      setConnectionState(attempt === 0 ? "connecting" : "reconnecting");
      const url = resolveWsUrl();

      try {
        socket = new WebSocket(url);
      } catch {
        setConnectionState("disconnected");
        setErrorMessage("Invalid WebSocket endpoint configuration.");
        return;
      }

      socket.onopen = () => {
        if (!active) {
          return;
        }
        attempt = 0;
        setConnectionState("connected");
        setErrorMessage(null);
      };

      socket.onmessage = (event: MessageEvent<string>) => {
        if (!active) {
          return;
        }
        try {
          const parsed = JSON.parse(event.data) as TelemetryFrame;
          scoreRef.current =
            scoreRef.current + EMA_ALPHA * (parsed.stability_score - scoreRef.current);
          indexRef.current =
            indexRef.current + EMA_ALPHA * (parsed.tremor_index - indexRef.current);

          setFrame(parsed);
          setSmoothedScore(Math.round(scoreRef.current * 10) / 10);
          setSmoothedTremorIndex(Math.round(indexRef.current * 10) / 10);
          setHistory((prev) => {
            const next: TelemetryPoint = {
              timestamp: parsed.timestamp,
              tremorHz: parsed.tremor_hz,
              tremorIndex: parsed.tremor_index,
              stabilityScore: parsed.stability_score,
            };
            const merged = [...prev, next];
            return merged.length > MAX_HISTORY_POINTS
              ? merged.slice(merged.length - MAX_HISTORY_POINTS)
              : merged;
          });
        } catch {
          setErrorMessage("Received malformed telemetry payload.");
        }
      };

      socket.onerror = () => {
        if (!active) {
          return;
        }
        setErrorMessage(
          "WebSocket connection interrupted. Retrying connection to ws://localhost:8000/ws/telemetry."
        );
      };

      socket.onclose = () => {
        if (!active) {
          return;
        }
        attempt += 1;
        const delayMs = Math.min(8000, 1000 * Math.pow(2, Math.min(attempt - 1, 3)));
        setConnectionState("reconnecting");
        reconnectTimer = window.setTimeout(connect, delayMs);
      };
    };

    connect();

    return () => {
      active = false;
      if (reconnectTimer !== null) {
        window.clearTimeout(reconnectTimer);
      }
      if (socket !== null) {
        socket.close();
      }
    };
  }, [retryToken]);

  const reconnect = () => {
    setRetryToken((prev) => prev + 1);
  };

  return {
    frame,
    smoothedScore,
    smoothedTremorIndex,
    history,
    connectionState,
    errorMessage,
    reconnect,
  };
}
