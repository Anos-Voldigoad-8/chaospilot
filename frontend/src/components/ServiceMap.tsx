import { useMemo } from "react";
import {
  Background,
  BackgroundVariant,
  Controls,
  Handle,
  MarkerType,
  Position,
  ReactFlow,
  type Edge,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import { useChaosStore } from "../store/useChaosStore";
import { formatLatency } from "../lib/stats";
import { positionFor } from "../lib/topology";
import { COLORS, STATUS_COLOR, STATUS_LABEL } from "../lib/theme";
import type { ServiceStatus } from "../types/chaos";
import { Panel } from "./Panel";

type ServiceNodeData = {
  label: string;
  role: string;
  port: number;
  status: ServiceStatus;
  latency: number;
  isTarget: boolean;
};

type ServiceNodeType = Node<ServiceNodeData, "service">;

function ServiceNode({ data }: NodeProps<ServiceNodeType>) {
  const color = STATUS_COLOR[data.status];

  return (
    <div className={`service-node service-node--${data.status}`}>
      <span className="service-node__aura" aria-hidden />
      <Handle type="target" position={Position.Left} />
      <Handle type="source" position={Position.Right} />

      {data.isTarget ? <span className="service-node__target">target</span> : null}

      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="truncate font-display text-[14px] font-semibold uppercase tracking-[0.18em] text-neon-ice">
            {data.label}
          </div>
          <div className="truncate text-[8px] uppercase tracking-[0.12em] text-slate-500">
            {data.role}
          </div>
        </div>
        <span className="service-node__dot mt-1 shrink-0" aria-hidden />
      </div>

      <div className="mt-2 flex items-end justify-between gap-2">
        <span
          className="hud-value text-[19px] font-medium leading-none"
          style={{ color }}
        >
          {formatLatency(data.latency)}
        </span>
        <span className="text-right leading-none">
          <span className="block text-[8px] uppercase tracking-[0.12em] text-slate-600">
            :{data.port}
          </span>
          <span
            className="mt-1 block text-[8px] uppercase tracking-[0.16em]"
            style={{ color }}
          >
            {STATUS_LABEL[data.status]}
          </span>
        </span>
      </div>
    </div>
  );
}

const NODE_TYPES = { service: ServiceNode };

function edgeStatus(
  source: ServiceStatus | undefined,
  target: ServiceStatus | undefined,
): ServiceStatus {
  if (target && target !== "ok") return target;
  if (source === "bad") return "warn";
  return "ok";
}

function Legend() {
  return (
    <div className="pointer-events-none absolute bottom-2 left-2 z-10 flex items-center gap-3 border border-neon-cyan/10 bg-void-950/80 px-2 py-1.5 backdrop-blur">
      {(["ok", "warn", "bad"] as const).map((status) => (
        <span
          key={status}
          className="flex items-center gap-1.5 text-[8px] uppercase tracking-[0.16em] text-slate-500"
        >
          <span
            className="h-1.5 w-1.5 rounded-full"
            style={{
              backgroundColor: STATUS_COLOR[status],
              boxShadow: `0 0 6px ${STATUS_COLOR[status]}`,
            }}
          />
          {STATUS_LABEL[status]}
        </span>
      ))}
    </div>
  );
}

export function ServiceMap() {
  const topology = useChaosStore((state) => state.topology);
  const services = useChaosStore((state) => state.services);
  const target = useChaosStore((state) => state.target);
  const connection = useChaosStore((state) => state.connection);
  const mockMode = useChaosStore((state) => state.mockMode);

  const nodes = useMemo<ServiceNodeType[]>(
    () =>
      topology.nodes.map((node, index) => {
        const runtime = services[node.id];
        return {
          id: node.id,
          type: "service",
          position: positionFor(node.id, index),
          draggable: false,
          selectable: false,
          data: {
            label: node.label,
            role: node.role,
            port: node.port,
            status: runtime?.status ?? "ok",
            latency: runtime?.latency_ms ?? 0,
            isTarget: node.id === target,
          },
        };
      }),
    [topology.nodes, services, target],
  );

  const edges = useMemo<Edge[]>(
    () =>
      topology.edges.map((edge) => {
        const status = edgeStatus(
          services[edge.source]?.status,
          services[edge.target]?.status,
        );
        const color =
          status === "ok" ? COLORS.cyanDim : STATUS_COLOR[status];

        return {
          id: edge.id,
          source: edge.source,
          target: edge.target,
          type: "default",
          animated: status !== "ok",
          style: {
            stroke: color,
            strokeWidth: status === "ok" ? 1 : 1.8,
            filter:
              status === "bad"
                ? "drop-shadow(0 0 4px rgba(255,61,85,0.7))"
                : status === "warn"
                  ? "drop-shadow(0 0 3px rgba(255,178,36,0.5))"
                  : undefined,
          },
          markerEnd: {
            type: MarkerType.ArrowClosed,
            color,
            width: 13,
            height: 13,
          },
        };
      }),
    [topology.edges, services],
  );

  return (
    <Panel
      title="Service map"
      code="live topology"
      bodyClassName="relative p-0"
      actions={
        <span className="hidden items-center gap-1.5 text-[8px] uppercase tracking-[0.16em] text-slate-600 sm:flex">
          <span className="h-1 w-1 rounded-full bg-neon-cyan/60" />
          edges follow the call path
        </span>
      }
    >
      <div className="relative h-[420px] sm:h-[470px] xl:h-[566px]">
        <div
          className="pointer-events-none absolute inset-0 z-[1]"
          style={{
            background:
              "radial-gradient(ellipse at 50% 45%, transparent 45%, rgba(4,7,10,0.55) 100%)",
          }}
          aria-hidden
        />
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={NODE_TYPES}
          fitView
          fitViewOptions={{ padding: 0.06 }}
          minZoom={0.4}
          maxZoom={1.6}
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable={false}
          panOnScroll
          zoomOnScroll={false}
          proOptions={{ hideAttribution: false }}
        >
          <Background
            variant={BackgroundVariant.Dots}
            gap={20}
            size={1}
            color="rgba(32,231,222,0.13)"
          />
          <Controls showInteractive={false} position="bottom-right" />
        </ReactFlow>

        <Legend />

        <div className="pointer-events-none absolute right-2 top-2 z-10 hidden border border-neon-cyan/10 bg-void-950/75 px-2 py-1 text-[8px] uppercase tracking-[0.16em] text-slate-600 sm:block">
          drag to pan
        </div>

        {connection === "offline" && !mockMode ? (
          <div className="pointer-events-none absolute inset-x-3 top-2 z-20 mx-auto w-fit max-w-full border border-neon-amber/30 bg-void-950/90 px-3 py-1.5 text-center text-[10px] uppercase tracking-[0.14em] text-neon-amber">
            no live link — retrying · append{" "}
            <span className="text-neon-ice">?mock=1</span> for a scripted demo
          </div>
        ) : null}
      </div>
    </Panel>
  );
}
