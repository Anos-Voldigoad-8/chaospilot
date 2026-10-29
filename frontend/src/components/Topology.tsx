import { useMemo } from "react";
import {
  Background,
  BackgroundVariant,
  Controls,
  Handle,
  MiniMap,
  Position,
  ReactFlow,
  type Edge,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import { Boxes, CircleAlert, CircleCheck, CircleDot } from "lucide-react";
import type { Service, ServiceStatus } from "../types/api";
import { formatNumber } from "../lib/format";

type ServiceNodeData = Record<string, unknown> & {
  service: Service;
  selected: boolean;
};

type ServiceNode = Node<ServiceNodeData, "service">;

const STATUS_STYLES: Record<
  ServiceStatus,
  { border: string; text: string; icon: typeof CircleCheck }
> = {
  healthy: { border: "border-emerald-400/40", text: "text-emerald-300", icon: CircleCheck },
  degraded: { border: "border-amber-400/50", text: "text-amber-300", icon: CircleAlert },
  down: { border: "border-rose-400/60", text: "text-rose-300", icon: CircleAlert },
  unknown: { border: "border-slate-500/40", text: "text-slate-400", icon: CircleDot },
};

const POSITIONS: Record<string, { x: number; y: number }> = {
  catalog: { x: 0, y: 0 },
  cart: { x: 0, y: 150 },
  checkout: { x: 240, y: 75 },
  payments: { x: 490, y: 0 },
  notifications: { x: 490, y: 150 },
};

function ServiceNodeComponent({ data }: NodeProps<ServiceNode>) {
  const { service, selected } = data;
  const styles = STATUS_STYLES[service.status];
  const StatusIcon = styles.icon;

  return (
    <div
      className={`w-48 rounded-lg border ${styles.border} bg-ink-800/95 px-3 py-2.5 shadow-lg backdrop-blur transition ${
        selected ? "ring-2 ring-cyan-400/50" : ""
      }`}
    >
      <Handle type="target" position={Position.Top} className="!bg-cyan-400/60" />
      <div className="flex items-center justify-between">
        <span className="flex items-center gap-1.5 text-sm font-medium text-white">
          <Boxes className="h-3.5 w-3.5 text-slate-400" aria-hidden />
          {service.name}
        </span>
        <StatusIcon className={`h-3.5 w-3.5 ${styles.text}`} aria-hidden />
      </div>
      <div className="mt-1 flex items-center justify-between font-mono text-[10px] text-slate-500">
        <span>{service.latest ? `${formatNumber(service.latest.latency_ms, 0)} ms` : "no data"}</span>
        <span>:{service.port}</span>
      </div>
      {service.active_faults > 0 ? (
        <div className="mt-1.5 rounded bg-amber-500/10 px-1.5 py-0.5 text-[10px] text-amber-300">
          {service.active_faults} active fault{service.active_faults > 1 ? "s" : ""}
        </div>
      ) : null}
      <Handle type="source" position={Position.Bottom} className="!bg-cyan-400/60" />
    </div>
  );
}

const nodeTypes = { service: ServiceNodeComponent };

interface TopologyProps {
  services: Service[];
  selectedService: string;
  onSelect: (serviceId: string) => void;
}

export function Topology({ services, selectedService, onSelect }: TopologyProps) {
  const nodes = useMemo<ServiceNode[]>(
    () =>
      services.map((service, index) => ({
        id: service.id,
        type: "service",
        position: POSITIONS[service.id] ?? { x: 120 * index, y: 0 },
        data: { service, selected: service.id === selectedService },
        draggable: false,
      })),
    [services, selectedService],
  );

  const edges = useMemo<Edge[]>(() => {
    const byId = new Map(services.map((service) => [service.id, service]));
    return services.flatMap((service) =>
      service.dependencies
        .filter((dependency) => byId.has(dependency))
        .map((dependency) => {
          const source = byId.get(service.id);
          const target = byId.get(dependency);
          const unhealthy = source?.status !== "healthy" || target?.status !== "healthy";
          return {
            id: `${service.id}-${dependency}`,
            source: service.id,
            target: dependency,
            animated: Boolean(unhealthy),
            style: {
              stroke: unhealthy ? "#fbbf24" : "#334155",
              strokeWidth: unhealthy ? 2 : 1.5,
            },
          };
        }),
    );
  }, [services]);

  return (
    <div className="h-[360px] overflow-hidden rounded-lg border border-white/5 bg-ink-950/60">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        minZoom={0.5}
        maxZoom={1.4}
        nodesDraggable={false}
        nodesConnectable={false}
        onNodeClick={(_, node) => onSelect(node.id)}
        proOptions={{ hideAttribution: true }}
      >
        <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="#1e293b" />
        <Controls showInteractive={false} className="!border-white/10 !bg-ink-800" />
        <MiniMap
          pannable
          zoomable
          maskColor="rgba(5, 8, 16, 0.75)"
          nodeColor="#22d3ee"
          className="!border !border-white/10 !bg-ink-900"
        />
      </ReactFlow>
    </div>
  );
}
