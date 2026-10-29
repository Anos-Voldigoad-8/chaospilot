import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import type { Overview } from "../types/api";

interface DashboardState {
  data: Overview | null;
  error: string | null;
  loading: boolean;
  refresh: () => Promise<void>;
}

export function useDashboard(intervalMs = 5000): DashboardState {
  const [data, setData] = useState<Overview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const mounted = useRef(true);

  const refresh = useCallback(async () => {
    try {
      const overview = await api.overview();
      if (!mounted.current) return;
      setData(overview);
      setError(null);
    } catch (err) {
      if (!mounted.current) return;
      setError(err instanceof Error ? err.message : "Failed to reach the backend");
    } finally {
      if (mounted.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    mounted.current = true;
    void refresh();
    const timer = window.setInterval(() => void refresh(), intervalMs);
    return () => {
      mounted.current = false;
      window.clearInterval(timer);
    };
  }, [refresh, intervalMs]);

  return { data, error, loading, refresh };
}
