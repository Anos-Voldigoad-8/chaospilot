import { useEffect } from "react";
import { resolveWsUrl } from "../lib/api";
import { useChaosStore } from "../store/useChaosStore";
import type { WsEvent } from "../types/chaos";

const RETRY_BASE_MS = 1_000;
const RETRY_MAX_MS = 8_000;

let bootstrapped = false;

/**
 * Keeps one WebSocket open to the backend and feeds events into the store.
 * Reconnects with exponential backoff and never surfaces a fatal error: the
 * dashboard stays usable and shows the link as offline.
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
    let attempt = 0;
    let lastState: string = "connecting";
    let announcedDown = false;

    const announce = (state: "connecting" | "live" | "offline") => {
      if (lastState === state) return;
      lastState = state;
      setConnection(state);
    };

    const scheduleRetry = () => {
      const delay = Math.min(RETRY_BASE_MS * 2 ** attempt, RETRY_MAX_MS);
      attempt += 1;
      retryTimer = window.setTimeout(connect, delay);
    };

    const connect = () => {
      if (disposed) return;
      announce("connecting");

      const url = resolveWsUrl();
      try {
        socket = new WebSocket(url);
      } catch {
        announce("offline");
        scheduleRetry();
        return;
      }

      socket.onopen = () => {
        attempt = 0;
        announcedDown = false;
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
        announce("offline");
        if (!announcedDown) {
          announcedDown = true;
          ingest({
            type: "log",
            level: "warn",
            text:
              `link lost // backend unreachable at ${url} // ` +
              "start it with run_demo.ps1 or run_demo.sh; retrying",
          });
        }
        scheduleRetry();
      };
    };

    connect();

    return () => {
      disposed = true;
      if (retryTimer !== undefined) window.clearTimeout(retryTimer);
      socket?.close();
    };
  }, [mockMode, ingest, setConnection]);
}
