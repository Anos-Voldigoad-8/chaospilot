import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { useChaosStore } from "../store/useChaosStore";
import { STATUS_COLOR } from "../lib/theme";
import { formatLatency } from "../lib/stats";
import type { ServiceStatus } from "../types/chaos";
import { RotateCw, ZoomIn, ZoomOut, Eye, Sparkles } from "lucide-react";

interface Node3DData {
  id: string;
  label: string;
  role: string;
  port: number;
  mesh: THREE.Mesh;
  glowMesh: THREE.Mesh;
  haloMesh: THREE.LineSegments;
  angle: number;
  distance: number;
  height: number;
}

export function ChaosCore3D() {
  const containerRef = useRef<HTMLDivElement>(null);
  const topology = useChaosStore((state) => state.topology);
  const services = useChaosStore((state) => state.services);
  const running = useChaosStore((state) => state.running);
  const selectedScenarioId = useChaosStore((state) => state.selectedScenarioId);
  const scenarios = useChaosStore((state) => state.scenarios);

  const [hoveredNode, setHoveredNode] = useState<{
    id: string;
    label: string;
    role: string;
    port: number;
    status: ServiceStatus;
    latency: number;
    x: number;
    y: number;
  } | null>(null);

  const [autoRotate, setAutoRotate] = useState(true);

  const targetService = selectedScenarioId != null
    ? scenarios.find((s) => s.id === selectedScenarioId)?.target_service ?? null
    : null;

  // Refs for animation loop
  const sceneRef = useRef<THREE.Scene | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const coreMeshRef = useRef<THREE.Mesh | null>(null);
  const outerRing1Ref = useRef<THREE.Line | null>(null);
  const outerRing2Ref = useRef<THREE.Line | null>(null);
  const outerRing3Ref = useRef<THREE.Line | null>(null);
  const particleSystemRef = useRef<THREE.Points | null>(null);
  const nodes3DRef = useRef<Map<string, Node3DData>>(new Map());
  const edges3DRef = useRef<Map<string, { line: THREE.Line; source: string; target: string }>>(new Map());

  // Mouse interaction state
  const isDraggingRef = useRef(false);
  const previousMousePositionRef = useRef({ x: 0, y: 0 });
  const cameraOrbitRef = useRef({ radius: 26, theta: Math.PI / 4, phi: Math.PI / 3.5 });

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const width = container.clientWidth;
    const height = container.clientHeight;

    // 1. Scene & Camera in Void Pine atmosphere
    const scene = new THREE.Scene();
    sceneRef.current = scene;

    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000);
    cameraRef.current = camera;

    const updateCameraPos = () => {
      const { radius, theta, phi } = cameraOrbitRef.current;
      camera.position.x = radius * Math.sin(phi) * Math.cos(theta);
      camera.position.y = radius * Math.cos(phi);
      camera.position.z = radius * Math.sin(phi) * Math.sin(theta);
      camera.lookAt(0, 0, 0);
    };
    updateCameraPos();

    // 2. Renderer
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    rendererRef.current = renderer;
    container.innerHTML = "";
    container.appendChild(renderer.domElement);

    // 3. Central Soft Ultraviolet Chaos Core Orb
    const coreGeo = new THREE.IcosahedronGeometry(2.4, 2);
    const coreMat = new THREE.MeshBasicMaterial({
      color: 0x6366F1, // Soft Ultraviolet
      wireframe: true,
      transparent: true,
      opacity: 0.8,
    });
    const coreMesh = new THREE.Mesh(coreGeo, coreMat);
    scene.add(coreMesh);
    coreMeshRef.current = coreMesh;

    // Inner Deep Gunmetal core sphere
    const innerGeo = new THREE.SphereGeometry(1.6, 24, 24);
    const innerMat = new THREE.MeshBasicMaterial({
      color: 0x1E222B, // Deep Gunmetal
      transparent: true,
      opacity: 0.95,
    });
    const innerCore = new THREE.Mesh(innerGeo, innerMat);
    coreMesh.add(innerCore);

    // 4. Luminous Soft Ultraviolet Trajectory Rings
    const createRing = (radius: number, color: number, opacity = 0.4) => {
      const points = [];
      const segments = 64;
      for (let i = 0; i <= segments; i++) {
        const theta = (i / segments) * Math.PI * 2;
        points.push(new THREE.Vector3(Math.cos(theta) * radius, 0, Math.sin(theta) * radius));
      }
      const geo = new THREE.BufferGeometry().setFromPoints(points);
      const mat = new THREE.LineBasicMaterial({ color, transparent: true, opacity });
      return new THREE.Line(geo, mat);
    };

    const ring1 = createRing(5.5, 0x6366F1, 0.5);
    const ring2 = createRing(8.5, 0x818CF8, 0.4);
    const ring3 = createRing(11.5, 0xA5B4FC, 0.3);
    ring1.rotation.x = Math.PI / 6;
    ring2.rotation.z = Math.PI / 5;
    ring3.rotation.y = Math.PI / 4;
    scene.add(ring1, ring2, ring3);
    outerRing1Ref.current = ring1;
    outerRing2Ref.current = ring2;
    outerRing3Ref.current = ring3;

    // 5. Soft Ultraviolet Floating Telemetry Particles
    const particleCount = 550;
    const particleGeo = new THREE.BufferGeometry();
    const positions = new Float32Array(particleCount * 3);
    const colors = new Float32Array(particleCount * 3);

    for (let i = 0; i < particleCount; i++) {
      const pRadius = 6 + Math.random() * 18;
      const pTheta = Math.random() * Math.PI * 2;
      const pPhi = (Math.random() - 0.5) * Math.PI;

      positions[i * 3] = pRadius * Math.cos(pPhi) * Math.cos(pTheta);
      positions[i * 3 + 1] = pRadius * Math.sin(pPhi);
      positions[i * 3 + 2] = pRadius * Math.cos(pPhi) * Math.sin(pTheta);

      // Soft Ultraviolet particle glow (#6366F1 -> 0.39, 0.40, 0.95)
      colors[i * 3] = 0.39;
      colors[i * 3 + 1] = 0.40;
      colors[i * 3 + 2] = 0.95;
    }

    particleGeo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    particleGeo.setAttribute("color", new THREE.BufferAttribute(colors, 3));

    const particleMat = new THREE.PointsMaterial({
      size: 0.22,
      vertexColors: true,
      transparent: true,
      opacity: 0.65,
    });
    const particleSystem = new THREE.Points(particleGeo, particleMat);
    scene.add(particleSystem);
    particleSystemRef.current = particleSystem;

    // 6. 3D Service Satellite Nodes
    const orbitalLayout: Record<string, { distance: number; angle: number; height: number }> = {
      gateway:  { distance: 6.2, angle: 0, height: 1.2 },
      auth:     { distance: 9.2, angle: Math.PI / 3, height: -1.5 },
      orders:   { distance: 8.8, angle: (2 * Math.PI) / 3, height: 2.2 },
      payments: { distance: 11.5, angle: Math.PI, height: -1.0 },
      cache:    { distance: 10.5, angle: (4 * Math.PI) / 3, height: 1.8 },
      db:       { distance: 12.0, angle: (5 * Math.PI) / 3, height: -2.0 },
    };

    const nodeMap = new Map<string, Node3DData>();

    topology.nodes.forEach((node) => {
      const layout = orbitalLayout[node.id] || { distance: 9, angle: 0, height: 0 };
      const x = Math.cos(layout.angle) * layout.distance;
      const z = Math.sin(layout.angle) * layout.distance;
      const y = layout.height;

      // Solid sphere core
      const geo = new THREE.SphereGeometry(0.85, 16, 16);
      const mat = new THREE.MeshBasicMaterial({ color: 0x6366F1 });
      const mesh = new THREE.Mesh(geo, mat);
      mesh.position.set(x, y, z);
      (mesh as unknown as { serviceId: string }).serviceId = node.id;
      scene.add(mesh);

      // Wireframe halo in soft ultraviolet
      const haloGeo = new THREE.WireframeGeometry(new THREE.IcosahedronGeometry(1.2, 1));
      const haloMat = new THREE.LineBasicMaterial({ color: 0x818CF8, transparent: true, opacity: 0.6 });
      const haloMesh = new THREE.LineSegments(haloGeo, haloMat);
      mesh.add(haloMesh);

      // Outer glow shell
      const glowGeo = new THREE.SphereGeometry(1.35, 16, 16);
      const glowMat = new THREE.MeshBasicMaterial({
        color: 0x6366F1,
        transparent: true,
        opacity: 0.18,
      });
      const glowMesh = new THREE.Mesh(glowGeo, glowMat);
      mesh.add(glowMesh);

      nodeMap.set(node.id, {
        id: node.id,
        label: node.label,
        role: node.role,
        port: node.port,
        mesh,
        glowMesh,
        haloMesh,
        angle: layout.angle,
        distance: layout.distance,
        height: layout.height,
      });
    });
    nodes3DRef.current = nodeMap;

    // 7. Topology Connection Beams
    const edgeMap = new Map<string, { line: THREE.Line; source: string; target: string }>();
    topology.edges.forEach((edge) => {
      const srcNode = nodeMap.get(edge.source);
      const tgtNode = nodeMap.get(edge.target);
      if (!srcNode || !tgtNode) return;

      const points = [srcNode.mesh.position, tgtNode.mesh.position];
      const lineGeo = new THREE.BufferGeometry().setFromPoints(points);
      const lineMat = new THREE.LineBasicMaterial({
        color: 0x94A3B8,
        transparent: true,
        opacity: 0.5,
      });
      const line = new THREE.Line(lineGeo, lineMat);
      scene.add(line);
      edgeMap.set(edge.id, { line, source: edge.source, target: edge.target });
    });
    edges3DRef.current = edgeMap;

    // 8. Animation Loop
    let animId: number;
    let clock = new THREE.Clock();

    const animate = () => {
      animId = requestAnimationFrame(animate);
      const elapsedTime = clock.getElapsedTime();

      // Auto-rotation
      if (autoRotate && !isDraggingRef.current) {
        cameraOrbitRef.current.theta += 0.0035;
        updateCameraPos();
      }

      // Rotate central core
      if (coreMeshRef.current) {
        const isFaultActive = running;
        const spinSpeed = isFaultActive ? 0.03 : 0.008;
        coreMeshRef.current.rotation.y += spinSpeed;
        coreMeshRef.current.rotation.x += spinSpeed * 0.5;

        // Core breathing scale
        const scale = 1 + Math.sin(elapsedTime * (isFaultActive ? 5 : 2)) * (isFaultActive ? 0.1 : 0.04);
        coreMeshRef.current.scale.set(scale, scale, scale);
      }

      // Rotate orbital rings
      if (outerRing1Ref.current) outerRing1Ref.current.rotation.y += 0.005;
      if (outerRing2Ref.current) outerRing2Ref.current.rotation.y -= 0.004;
      if (outerRing3Ref.current) outerRing3Ref.current.rotation.x += 0.003;

      // Rotate particle cloud
      if (particleSystemRef.current) {
        particleSystemRef.current.rotation.y += 0.001;
      }

      // Pulse service halos
      nodeMap.forEach((node) => {
        node.haloMesh.rotation.y += 0.015;
      });

      renderer.render(scene, camera);
    };

    animate();

    // 9. Resize Listener
    const handleResize = () => {
      if (!container || !rendererRef.current || !cameraRef.current) return;
      const w = container.clientWidth;
      const h = container.clientHeight;
      cameraRef.current.aspect = w / h;
      cameraRef.current.updateProjectionMatrix();
      rendererRef.current.setSize(w, h);
    };
    window.addEventListener("resize", handleResize);

    // 10. Pointer Drag for Orbiting
    const onMouseDown = (e: MouseEvent) => {
      isDraggingRef.current = true;
      previousMousePositionRef.current = { x: e.clientX, y: e.clientY };
    };

    const onMouseMove = (e: MouseEvent) => {
      if (isDraggingRef.current) {
        const deltaX = e.clientX - previousMousePositionRef.current.x;
        const deltaY = e.clientY - previousMousePositionRef.current.y;

        cameraOrbitRef.current.theta -= deltaX * 0.008;
        cameraOrbitRef.current.phi = Math.max(
          0.15,
          Math.min(Math.PI - 0.15, cameraOrbitRef.current.phi - deltaY * 0.008)
        );

        updateCameraPos();
        previousMousePositionRef.current = { x: e.clientX, y: e.clientY };
      }

      // Raycasting for service hover inspection
      if (cameraRef.current && sceneRef.current) {
        const rect = container.getBoundingClientRect();
        const mouse = new THREE.Vector2(
          ((e.clientX - rect.left) / rect.width) * 2 - 1,
          -((e.clientY - rect.top) / rect.height) * 2 + 1
        );

        const raycaster = new THREE.Raycaster();
        raycaster.setFromCamera(mouse, cameraRef.current);

        const meshes = Array.from(nodeMap.values()).map((n) => n.mesh);
        const intersects = raycaster.intersectObjects(meshes);

        if (intersects.length > 0) {
          const hit = intersects[0].object as unknown as { serviceId: string };
          const sId = hit.serviceId;
          const nodeData = nodeMap.get(sId);
          const currentServices = useChaosStore.getState().services;
          const rt = currentServices[sId];

          if (nodeData) {
            setHoveredNode({
              id: sId,
              label: nodeData.label,
              role: nodeData.role,
              port: nodeData.port,
              status: rt?.status ?? "ok",
              latency: rt?.latency_ms ?? 0,
              x: e.clientX - rect.left,
              y: e.clientY - rect.top,
            });
          }
        } else {
          setHoveredNode(null);
        }
      }
    };

    const onMouseUp = () => {
      isDraggingRef.current = false;
    };

    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      cameraOrbitRef.current.radius = Math.max(
        12,
        Math.min(48, cameraOrbitRef.current.radius + e.deltaY * 0.02)
      );
      updateCameraPos();
    };

    container.addEventListener("mousedown", onMouseDown);
    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
    container.addEventListener("wheel", onWheel, { passive: false });

    return () => {
      cancelAnimationFrame(animId);
      window.removeEventListener("resize", handleResize);
      container.removeEventListener("mousedown", onMouseDown);
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", onMouseUp);
      container.removeEventListener("wheel", onWheel);
      renderer.dispose();
    };
  }, [topology]);

  // Reactive state updates for materials & colors
  useEffect(() => {
    const nodeMap = nodes3DRef.current;
    if (nodeMap.size === 0) return;

    let hasAnyBad = false;
    let hasAnyWarn = false;

    nodeMap.forEach((node) => {
      const rt = services[node.id];
      const status: ServiceStatus = rt?.status ?? "ok";
      if (status === "bad") hasAnyBad = true;
      if (status === "warn") hasAnyWarn = true;

      const isTarget = node.id === targetService;
      let hexColor = 0x6366F1; // Soft Ultraviolet (nominal)
      if (status === "bad" || (isTarget && running)) hexColor = 0xEF4444; // Signal Red
      else if (status === "warn") hexColor = 0xF59E0B; // Amber

      (node.mesh.material as THREE.MeshBasicMaterial).color.setHex(hexColor);
      (node.glowMesh.material as THREE.MeshBasicMaterial).color.setHex(hexColor);
      (node.haloMesh.material as THREE.LineBasicMaterial).color.setHex(hexColor);

      // Node scale pulsation if target
      if (isTarget && running) {
        node.mesh.scale.set(1.4, 1.4, 1.4);
      } else {
        node.mesh.scale.set(1.0, 1.0, 1.0);
      }
    });

    // Update core orb color
    if (coreMeshRef.current) {
      const coreMat = coreMeshRef.current.material as THREE.MeshBasicMaterial;
      if (hasAnyBad || running) {
        coreMat.color.setHex(0xEF4444); // Signal Red
      } else if (hasAnyWarn) {
        coreMat.color.setHex(0xF59E0B); // Amber
      } else {
        coreMat.color.setHex(0x6366F1); // Soft Ultraviolet
      }
    }

    // Update edge beam colors
    edges3DRef.current.forEach((edgeData) => {
      const srcStatus = services[edgeData.source]?.status;
      const tgtStatus = services[edgeData.target]?.status;
      let edgeColor = 0x94A3B8;
      if (tgtStatus === "bad" || srcStatus === "bad") edgeColor = 0xEF4444;
      else if (tgtStatus === "warn" || srcStatus === "warn") edgeColor = 0xF59E0B;
      else edgeColor = 0x6366F1;

      (edgeData.line.material as THREE.LineBasicMaterial).color.setHex(edgeColor);
      (edgeData.line.material as THREE.LineBasicMaterial).opacity = edgeColor === 0x6366F1 ? 0.6 : 0.85;
    });
  }, [services, running, targetService]);

  const zoomIn = () => {
    cameraOrbitRef.current.radius = Math.max(14, cameraOrbitRef.current.radius - 4);
    if (cameraRef.current) {
      const { radius, theta, phi } = cameraOrbitRef.current;
      cameraRef.current.position.x = radius * Math.sin(phi) * Math.cos(theta);
      cameraRef.current.position.y = radius * Math.cos(phi);
      cameraRef.current.position.z = radius * Math.sin(phi) * Math.sin(theta);
      cameraRef.current.lookAt(0, 0, 0);
    }
  };

  const zoomOut = () => {
    cameraOrbitRef.current.radius = Math.min(42, cameraOrbitRef.current.radius + 4);
    if (cameraRef.current) {
      const { radius, theta, phi } = cameraOrbitRef.current;
      cameraRef.current.position.x = radius * Math.sin(phi) * Math.cos(theta);
      cameraRef.current.position.y = radius * Math.cos(phi);
      cameraRef.current.position.z = radius * Math.sin(phi) * Math.sin(theta);
      cameraRef.current.lookAt(0, 0, 0);
    }
  };

  const resetView = () => {
    cameraOrbitRef.current = { radius: 26, theta: Math.PI / 4, phi: Math.PI / 3.5 };
    if (cameraRef.current) {
      const { radius, theta, phi } = cameraOrbitRef.current;
      cameraRef.current.position.x = radius * Math.sin(phi) * Math.cos(theta);
      cameraRef.current.position.y = radius * Math.cos(phi);
      cameraRef.current.position.z = radius * Math.sin(phi) * Math.sin(theta);
      cameraRef.current.lookAt(0, 0, 0);
    }
  };

  return (
    <div className="relative h-full w-full select-none overflow-hidden bg-titanium-200/50">
      {/* Three.js Container */}
      <div ref={containerRef} className="h-full w-full cursor-grab active:cursor-grabbing" />

      {/* Floating Tactical Controls in Cool Titanium / Deep Gunmetal */}
      <div className="absolute right-3.5 top-3.5 z-20 flex items-center gap-1.5 border border-[#DDE1EA] bg-[#F8F9FB]/95 p-1 shadow-card backdrop-blur-md">
        <button
          type="button"
          onClick={() => setAutoRotate(!autoRotate)}
          className={`flex h-6 w-6 items-center justify-center transition ${
            autoRotate ? "text-ultraviolet" : "text-gunmetal-500 hover:text-gunmetal-900"
          }`}
          title={autoRotate ? "Pause orbit" : "Resume auto-orbit"}
        >
          <RotateCw className={`h-3.5 w-3.5 ${autoRotate ? "animate-spin" : ""}`} style={{ animationDuration: "10s" }} />
        </button>
        <button
          type="button"
          onClick={zoomIn}
          className="flex h-6 w-6 items-center justify-center text-gunmetal-500 hover:text-ultraviolet"
          title="Zoom in"
        >
          <ZoomIn className="h-3.5 w-3.5" />
        </button>
        <button
          type="button"
          onClick={zoomOut}
          className="flex h-6 w-6 items-center justify-center text-gunmetal-500 hover:text-ultraviolet"
          title="Zoom out"
        >
          <ZoomOut className="h-3.5 w-3.5" />
        </button>
        <button
          type="button"
          onClick={resetView}
          className="flex h-6 w-6 items-center justify-center text-gunmetal-500 hover:text-ultraviolet"
          title="Reset camera angle"
        >
          <Eye className="h-3.5 w-3.5" />
        </button>
      </div>

      {/* Left Blueprint Telemetry Badge */}
      <div className="pointer-events-none absolute bottom-3.5 left-3.5 z-20 flex items-center gap-2 border border-[#DDE1EA] bg-[#F8F9FB]/95 px-3 py-1.5 shadow-card font-mono backdrop-blur-md">
        <Sparkles className="h-3.5 w-3.5 text-ultraviolet animate-pulse" />
        <div className="text-[9px] uppercase tracking-[0.16em]">
          <span className="text-gunmetal-500 font-semibold">METALLIC CORE // </span>
          <span className="text-ultraviolet font-bold">SOFT ULTRAVIOLET</span>
        </div>
      </div>

      {/* Hover Node Card */}
      {hoveredNode && (
        <div
          className="pointer-events-none absolute z-30 -translate-x-1/2 -translate-y-full border border-ultraviolet bg-[#F8F9FB] p-2.5 shadow-card font-mono backdrop-blur-md"
          style={{
            left: `${hoveredNode.x}px`,
            top: `${hoveredNode.y - 12}px`,
            minWidth: "160px",
          }}
        >
          <div className="flex items-start justify-between gap-2">
            <div>
              <div className="font-display text-[13px] font-bold uppercase tracking-wider text-gunmetal-900">
                {hoveredNode.label}
              </div>
              <div className="text-[8px] uppercase tracking-wider text-gunmetal-500 font-semibold">
                {hoveredNode.role}
              </div>
            </div>
            <span
              className="mt-1 h-2 w-2 rounded-full"
              style={{
                backgroundColor: STATUS_COLOR[hoveredNode.status],
                boxShadow: `0 0 8px ${STATUS_COLOR[hoveredNode.status]}`,
              }}
            />
          </div>
          <div className="mt-2 flex items-baseline justify-between border-t border-[#DDE1EA] pt-1.5">
            <span
              className="text-[16px] font-bold"
              style={{ color: STATUS_COLOR[hoveredNode.status] }}
            >
              {formatLatency(hoveredNode.latency)}
            </span>
            <span className="text-[8px] text-gunmetal-500 font-bold">
              PORT :{hoveredNode.port}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
