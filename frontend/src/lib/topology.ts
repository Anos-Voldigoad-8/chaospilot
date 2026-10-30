import type { Topology } from "../types/chaos";

/**
 * Mirrors `backend/topology.py`. Used as the first paint and as a fallback
 * when the API is unreachable, so the map is never blank.
 */
export const DEFAULT_TOPOLOGY: Topology = {
  nodes: [
    { id: "gateway", label: "gateway", port: 8000, role: "entry point", entry: true },
    { id: "auth", label: "auth", port: 8001, role: "session verification", entry: false },
    { id: "orders", label: "orders", port: 8002, role: "order orchestration", entry: false },
    { id: "cache", label: "cache", port: 8003, role: "session cache", entry: false },
    { id: "payments", label: "payments", port: 8004, role: "payment charges", entry: false },
    { id: "db", label: "db", port: 8005, role: "record store", entry: false },
  ],
  edges: [
    { id: "gateway->auth", source: "gateway", target: "auth" },
    { id: "gateway->orders", source: "gateway", target: "orders" },
    { id: "auth->cache", source: "auth", target: "cache" },
    { id: "orders->payments", source: "orders", target: "payments" },
    { id: "orders->db", source: "orders", target: "db" },
    { id: "payments->db", source: "payments", target: "db" },
  ],
};

/** Fixed, readable layout: callers on the left, callees on the right. */
export const NODE_POSITIONS: Record<string, { x: number; y: number }> = {
  gateway: { x: 0, y: 200 },
  auth: { x: 250, y: 60 },
  orders: { x: 250, y: 330 },
  cache: { x: 500, y: 60 },
  payments: { x: 500, y: 330 },
  db: { x: 750, y: 195 },
};

export function positionFor(id: string, index: number): { x: number; y: number } {
  return NODE_POSITIONS[id] ?? { x: (index % 3) * 240, y: Math.floor(index / 3) * 170 };
}

/** Direct callers of a service, derived from the edge list. */
export function callersOf(topology: Topology): Record<string, string[]> {
  const callers: Record<string, string[]> = {};
  for (const edge of topology.edges) {
    (callers[edge.target] ??= []).push(edge.source);
  }
  return callers;
}
