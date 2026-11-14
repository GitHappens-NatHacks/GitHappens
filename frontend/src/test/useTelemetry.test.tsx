import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useTelemetry } from "../hooks/useTelemetry";
import type { TelemetryFrame } from "../types/telemetry";

class MockWebSocket {
  static instances: MockWebSocket[] = [];
  url: string;
  onopen: (() => void) | null = null;
  onmessage: ((event: MessageEvent<string>) => void) | null = null;
  onerror: (() => void) | null = null;
  onclose: (() => void) | null = null;
  close = vi.fn();

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
  }
}

function makeFrame(score: number, tremorIndex: number): TelemetryFrame {
  return {
    timestamp: 1700000000,
    session_id: "sess-1",
    tremor_hz: 5.2,
    tremor_index: tremorIndex,
    stabilization_active: true,
    stability_score: score,
    medication_state_estimate: "ON",
    gaze: {
      x: null,
      y: null,
      raw_feature: null,
      ear: null,
      face_detected: false,
      dwell_progress: 0,
      blink: false,
      source: "head",
      status: "Idle",
      calibrated: false,
      target_id: null,
      running: false,
    },
    steadyhand: {
      raw_pos: [100, 100],
      stable_pos: [100, 100],
      strength: 1.0,
      simulate_tremor: false,
      tremor_intensity: 55,
      spastic_drags_prevented: 1,
      slip_clicks_rescued: 2,
      click_freeze_active: false,
      gravity_well_active: false,
      gravity_target_role: null,
      os_tap_mode: "idle",
      os_tap_error: null,
      system_mouse_enabled: false,
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
}

describe("useTelemetry", () => {
  beforeEach(() => {
    MockWebSocket.instances = [];
    vi.useFakeTimers();
    vi.stubGlobal("WebSocket", MockWebSocket);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("connects, smooths valid telemetry frames, and guards malformed scores", async () => {
    const { result } = renderHook(() => useTelemetry());

    await act(async () => {
      await Promise.resolve();
    });

    expect(MockWebSocket.instances).toHaveLength(1);
    const ws = MockWebSocket.instances[0];

    act(() => {
      ws.onopen?.();
    });
    expect(result.current.connectionState).toBe("connected");
    expect(result.current.errorMessage).toBeNull();

    // Valid frame updates EMA score (100 -> 100 + 0.25*(80-100) = 95)
    act(() => {
      ws.onmessage?.(new MessageEvent("message", { data: JSON.stringify(makeFrame(80, 20)) }));
    });
    expect(result.current.smoothedScore).toBe(95);
    expect(result.current.smoothedTremorIndex).toBe(5);
    expect(result.current.history).toHaveLength(1);

    // Corrupted payload with NaN should be rejected cleanly without poisoning EMA
    act(() => {
      ws.onmessage?.(
        new MessageEvent("message", {
          data: JSON.stringify({ stability_score: null, tremor_index: "bad" }),
        })
      );
    });
    expect(result.current.smoothedScore).toBe(95);
    expect(result.current.errorMessage).toContain("incomplete telemetry payload");
  });

  it("reports resolved WebSocket URL on error and reconnects with backoff", async () => {
    const { result } = renderHook(() => useTelemetry());

    await act(async () => {
      await Promise.resolve();
    });

    const ws1 = MockWebSocket.instances[0];
    act(() => {
      ws1.onerror?.();
      ws1.onclose?.();
    });

    expect(result.current.connectionState).toBe("reconnecting");
    expect(result.current.errorMessage).toContain(ws1.url);

    await act(async () => {
      vi.advanceTimersByTime(1000);
      await Promise.resolve();
    });
    expect(MockWebSocket.instances).toHaveLength(2);
  });
});
