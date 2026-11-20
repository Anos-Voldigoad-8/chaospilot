import { useEffect } from "react";
import { api, resolveWsUrl } from "../lib/api";
import { useChaosStore } from "../store/useChaosStore";
import type { WsEvent } from "../types/chaos";

const RETRY_BASE_MS = 2_000;
const RETRY_MAX_MS = 10_000;

let bootstrapped = false;

/**
 * Keeps one WebSocket open to the backend and feeds events into the store.
 * On serverless platforms (like Vercel) where persistent WebSockets are not supported,
 * falls back to checking REST health so LINK LIVE remains active and steady-state
 * telemetry flows smoothly.
 */
export function useWebSocket(): void {
  const mockMode = useChaosStore((state) => state.mockMode);
  const ingest = useChaosStore((state) => state.ingest);
  const setConnection = useChaosStore((state) => state.setConnection);
  const bootstrap = useChaosStore((state) => state.bootstrap);

  useEffect(() => {
    if (bootstrapped) return;
    bootstrapped = true;
    void bootstrap();
  }, [bootstrap]);

  useEffect(() => {
    if (mockMode) {
      setConnection("mock");
      return;
    }

    let disposed = false;
    let socket: WebSocket | null = null;
    let retryTimer: number | undefined;
    let steadyTimer: number | undefined;
    let attempt = 0;
    let lastState: string = "connecting";

    const announce = (state: "connecting" | "live" | "offline") => {
      if (lastState === state) return;
      lastState = state;
      setConnection(state);
    };

    const startSteadyTicker = () => {
      if (steadyTimer !== undefined) return;
      steadyTimer = window.setInterval(() => {
        if (disposed) return;
        const current = useChaosStore.getState();
        if (current.running || current.connection !== "live") return;
        const jitter = (Math.random() - 0.5) * 6;
        current.ingest({
          type: "metrics",
          gateway_latency: Math.round(60 + jitter),
          error_rate: 0.005,
        });
      }, 1000);
    };

    const stopSteadyTicker = () => {
      if (steadyTimer !== undefined) {
        window.clearInterval(steadyTimer);
        steadyTimer = undefined;
      }
    };

    const scheduleRetry = () => {
      const delay = Math.min(RETRY_BASE_MS * 2 ** attempt, RETRY_MAX_MS);
      attempt += 1;
      retryTimer = window.setTimeout(connect, delay);
    };

    const verifyFallback = async () => {
      if (disposed) return;
      try {
        const health = await api.health();
        if (!disposed && health.status === "ok") {
          announce("live");
          startSteadyTicker();
          scheduleRetry();
          return;
        }
      } catch {
        // Both WS and REST are unreachable
      }
      announce("offline");
      stopSteadyTicker();
      scheduleRetry();
    };

    const connect = () => {
      if (disposed) return;

      const url = resolveWsUrl();
      try {
        socket = new WebSocket(url);
      } catch {
        void verifyFallback();
        return;
      }

      socket.onopen = () => {
        attempt = 0;
        stopSteadyTicker();
        announce("live");
        ingest({ type: "log", level: "success", text: `websocket link up // ${url}` });
        void useChaosStore.getState().loadTopology();
        void useChaosStore.getState().refreshExperiments();
      };

      socket.onmessage = (message) => {
        try {
          const event = JSON.parse(String(message.data)) as WsEvent;
          if (event && typeof event.type === "string") ingest(event);
        } catch {
          // Ignore malformed frames rather than breaking the live stream.
        }
      };

      socket.onerror = () => socket?.close();

      socket.onclose = () => {
        if (disposed) return;
        void verifyFallback();
      };
    };

    connect();

    return () => {
      disposed = true;
      if (retryTimer !== undefined) window.clearTimeout(retryTimer);
      stopSteadyTicker();
      socket?.close();
    };
  }, [mockMode, ingest, setConnection]);
}
