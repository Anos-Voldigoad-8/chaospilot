import { useState, useMemo } from "react";
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
import { STATUS_COLOR, STATUS_LABEL } from "../lib/theme";
import type { ServiceStatus } from "../types/chaos";
import { Panel } from "./Panel";
import { ChaosCore3D } from "./ChaosCore3D";
import { Box, Network, Columns } from "lucide-react";
import { audioEngine } from "../lib/audio";

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
      <Handle type="target" position={Position.Left} />
      <Handle type="source" position={Position.Right} />

      {data.isTarget ? <span className="service-node__target">TARGET</span> : null}

      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="truncate font-display text-[14px] font-bold uppercase tracking-[0.1em] text-gunmetal-900">
            {data.label}
          </div>
          <div className="truncate font-mono text-[8.5px] uppercase tracking-[0.1em] text-gunmetal-500 font-semibold">
            {data.role}
          </div>
        </div>
        <span
          className="mt-1 h-2 w-2 rounded-full shrink-0"
          style={{ backgroundColor: color, boxShadow: `0 0 8px ${color}` }}
          aria-hidden
        />
      </div>

      <div className="mt-2.5 flex items-end justify-between gap-2 font-mono border-t border-[#DDE1EA] pt-1.5">
        <span
          className="text-[17px] font-bold leading-none text-gunmetal-900"
          style={{ color: data.status === "bad" ? "#EF4444" : "#1E222B" }}
        >
          {formatLatency(data.latency)}
        </span>
        <span className="text-right leading-none">
          <span className="block text-[8px] uppercase tracking-[0.1em] text-gunmetal-500 font-semibold">
            :{data.port}
          </span>
          <span
            className="mt-1 block text-[8px] uppercase tracking-[0.14em] font-bold"
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
    <div className="pointer-events-none absolute bottom-3 left-3 z-10 flex items-center gap-3 border border-[#DDE1EA] bg-[#F8F9FB]/95 px-2.5 py-1.5 shadow-card font-mono backdrop-blur-md">
      {(["ok", "warn", "bad"] as const).map((status) => (
        <span
          key={status}
          className="flex items-center gap-1.5 text-[8.5px] uppercase tracking-[0.14em] font-semibold text-gunmetal-500"
        >
          <span
            className="h-2 w-2 rounded-full"
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
  const [viewMode, setViewMode] = useState<"3d" | "2d" | "split">("3d");
  const topology = useChaosStore((state) => state.topology);
  const services = useChaosStore((state) => state.services);
  const selectedScenarioId = useChaosStore((state) => state.selectedScenarioId);
  const scenarios = useChaosStore((state) => state.scenarios);
  const connection = useChaosStore((state) => state.connection);
  const mockMode = useChaosStore((state) => state.mockMode);

  const targetService = selectedScenarioId != null
    ? scenarios.find((s) => s.id === selectedScenarioId)?.target_service ?? null
    : null;

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
            isTarget: node.id === targetService,
          },
        };
      }),
    [topology.nodes, services, targetService],
  );

  const edges = useMemo<Edge[]>(
    () =>
      topology.edges.map((edge) => {
        const status = edgeStatus(
          services[edge.source]?.status,
          services[edge.target]?.status,
        );
        const strokeColor = status !== "ok" ? "#EF4444" : "#6366F1";

        return {
          id: edge.id,
          source: edge.source,
          target: edge.target,
          type: "default",
          animated: status !== "ok",
          style: {
            stroke: strokeColor,
            strokeWidth: status === "ok" ? 1.5 : 2.5,
            filter: status !== "ok" ? `drop-shadow(0 0 4px ${strokeColor})` : undefined,
          },
          markerEnd: {
            type: MarkerType.ArrowClosed,
            color: strokeColor,
            width: 12,
            height: 12,
          },
        };
      }),
    [topology.edges, services],
  );

  const switchMode = (mode: "3d" | "2d" | "split") => {
    audioEngine.playClick();
    setViewMode(mode);
  };

  return (
    <Panel
      title="Architecture Blueprint & 3D Core"
      code={viewMode === "3d" ? "3D WEBGL VIEW" : viewMode === "2d" ? "CALL GRAPH" : "SPLIT DECK"}
      bodyClassName="relative p-0 overflow-hidden bg-titanium-200/50"
      actions={
        <div className="flex items-center gap-1 border border-[#DDE1EA] bg-[#F8F9FB] p-0.5 shadow-metal font-mono">
          <button
            type="button"
            onClick={() => switchMode("3d")}
            className={`flex items-center gap-1.5 px-2.5 py-1 text-[9px] font-bold uppercase tracking-wider transition ${
              viewMode === "3d"
                ? "bg-gradient-to-r from-ultraviolet to-ultraviolet-deep text-white shadow-ultravioletSm"
                : "text-gunmetal-500 hover:bg-gunmetal-800 hover:text-white"
            }`}
            title="3D Atmospheric Core View"
          >
            <Box className="h-3 w-3" />
            <span>3D CORE</span>
          </button>
          <button
            type="button"
            onClick={() => switchMode("2d")}
            className={`flex items-center gap-1.5 px-2.5 py-1 text-[9px] font-bold uppercase tracking-wider transition ${
              viewMode === "2d"
                ? "bg-gradient-to-r from-ultraviolet to-ultraviolet-deep text-white shadow-ultravioletSm"
                : "text-gunmetal-500 hover:bg-gunmetal-800 hover:text-white"
            }`}
            title="2D Flow Architecture Diagram"
          >
            <Network className="h-3 w-3" />
            <span>2D BLUEPRINT</span>
          </button>
          <button
            type="button"
            onClick={() => switchMode("split")}
            className={`hidden md:flex items-center gap-1.5 px-2.5 py-1 text-[9px] font-bold uppercase tracking-wider transition ${
              viewMode === "split"
                ? "bg-gradient-to-r from-ultraviolet to-ultraviolet-deep text-white shadow-ultravioletSm"
                : "text-gunmetal-500 hover:bg-gunmetal-800 hover:text-white"
            }`}
            title="Split Deck View"
          >
            <Columns className="h-3 w-3" />
            <span>SPLIT</span>
          </button>
        </div>
      }
    >
      <div className="relative h-[360px] sm:h-[400px] xl:h-[420px] w-full bg-titanium-200/50">
        {/* VIEW 1: 3D Holographic Core */}
        {viewMode === "3d" && (
          <div className="absolute inset-0">
            <ChaosCore3D />
          </div>
        )}

        {/* VIEW 2: 2D ReactFlow Diagram */}
        {viewMode === "2d" && (
          <div className="absolute inset-0">
            <ReactFlow
              nodes={nodes}
              edges={edges}
              nodeTypes={NODE_TYPES}
              fitView
              fitViewOptions={{ padding: 0.08 }}
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
                gap={24}
                size={1}
                color="rgba(99, 102, 241, 0.14)"
              />
              <Controls showInteractive={false} position="bottom-right" />
            </ReactFlow>
            <Legend />
            <div className="pointer-events-none absolute right-3 top-3 z-10 hidden border border-[#DDE1EA] bg-[#F8F9FB]/95 px-2 py-1 font-mono text-[8px] uppercase tracking-[0.16em] text-gunmetal-500 sm:block shadow-metal font-bold">
              DRAG TO PAN
            </div>
          </div>
        )}

        {/* VIEW 3: Split Deck View */}
        {viewMode === "split" && (
          <div className="grid grid-cols-2 h-full w-full divide-x divide-[#DDE1EA]">
            <div className="relative h-full">
              <ChaosCore3D />
            </div>
            <div className="relative h-full">
              <ReactFlow
                nodes={nodes}
                edges={edges}
                nodeTypes={NODE_TYPES}
                fitView
                fitViewOptions={{ padding: 0.14 }}
                minZoom={0.3}
                maxZoom={1.4}
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
                  color="rgba(99, 102, 241, 0.14)"
                />
              </ReactFlow>
              <Legend />
            </div>
          </div>
        )}

        {connection === "offline" && !mockMode ? (
          <div className="pointer-events-none absolute inset-x-3 top-3 z-20 mx-auto w-fit max-w-full border border-signal-red bg-signal-redLight px-3 py-1.5 text-center font-mono text-[10px] font-bold uppercase tracking-[0.14em] text-signal-red shadow-metal">
            LINK OFFLINE — RETRYING · APPEND <span className="underline">?mock=1</span> FOR SCRIPTED DEMO
          </div>
        ) : null}
      </div>
    </Panel>
  );
}
