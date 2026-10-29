import { useEffect, useState } from "react";
import { api } from "../lib/api";
import type { MetricPoint } from "../types/api";

interface MetricsState {
  points: MetricPoint[];
  loading: boolean;
  error: string | null;
}

export function useMetrics(serviceId: string, minutes = 15, intervalMs = 5000): MetricsState {
  const [points, setPoints] = useState<MetricPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);

    const load = async () => {
      try {
        const response = await api.metrics(serviceId, minutes);
        if (!active) return;
        setPoints(response.points);
        setError(null);
      } catch (err) {
        if (!active) return;
        setError(err instanceof Error ? err.message : "Failed to load metrics");
      } finally {
        if (active) setLoading(false);
      }
    };

    void load();
    const timer = window.setInterval(() => void load(), intervalMs);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [serviceId, minutes, intervalMs]);

  return { points, loading, error };
}
