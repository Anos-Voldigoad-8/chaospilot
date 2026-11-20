import { useEffect, useRef } from "react";
import { useChaosStore } from "../../store/useChaosStore";

export function AuroraBackground() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const running = useChaosStore((state) => state.running);
  const activeScenario = useChaosStore((state) => {
    const id = state.selectedScenarioId;
    return id != null ? state.scenarios.find((s) => s.id === id) : null;
  });

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let animId: number;
    let width = (canvas.width = window.innerWidth);
    let height = (canvas.height = window.innerHeight);

    const handleResize = () => {
      if (!canvas) return;
      width = canvas.width = window.innerWidth;
      height = canvas.height = window.innerHeight;
    };
    window.addEventListener("resize", handleResize);

    // Atmospheric orbs in Cool Titanium space
    const orbs = [
      { x: width * 0.2, y: height * 0.25, radius: 360, vx: 0.25, vy: 0.18, color: "99, 102, 241" },  // Soft Ultraviolet (#6366F1)
      { x: width * 0.8, y: height * 0.35, radius: 420, vx: -0.22, vy: -0.2, color: "124, 58, 237" }, // Deep Ultraviolet (#7C3AED)
      { x: width * 0.45, y: height * 0.85, radius: 460, vx: 0.18, vy: -0.25, color: "148, 163, 184" }, // Titanium Slate (#94A3B8)
    ];

    let t = 0;
    const render = () => {
      t += 0.009;
      ctx.clearRect(0, 0, width, height);

      const isFault = running && activeScenario;

      orbs.forEach((orb, i) => {
        orb.x += orb.vx + Math.sin(t + i) * 0.35;
        orb.y += orb.vy + Math.cos(t + i) * 0.35;

        if (orb.x < -orb.radius) orb.x = width + orb.radius;
        if (orb.x > width + orb.radius) orb.x = -orb.radius;
        if (orb.y < -orb.radius) orb.y = height + orb.radius;
        if (orb.y > height + orb.radius) orb.y = -orb.radius;

        const gradient = ctx.createRadialGradient(
          orb.x,
          orb.y,
          0,
          orb.x,
          orb.y,
          orb.radius
        );

        if (isFault) {
          // Fault flare in Signal Red
          gradient.addColorStop(0, "rgba(239, 68, 68, 0.08)");
          gradient.addColorStop(0.5, "rgba(239, 68, 68, 0.025)");
          gradient.addColorStop(1, "transparent");
        } else {
          // Ambient soft ultraviolet glow in Cool Titanium
          gradient.addColorStop(0, `rgba(${orb.color}, 0.09)`);
          gradient.addColorStop(0.5, `rgba(${orb.color}, 0.02)`);
          gradient.addColorStop(1, "transparent");
        }

        ctx.fillStyle = gradient;
        ctx.beginPath();
        ctx.arc(orb.x, orb.y, orb.radius, 0, Math.PI * 2);
        ctx.fill();
      });

      animId = requestAnimationFrame(render);
    };

    animId = requestAnimationFrame(render);
    return () => {
      cancelAnimationFrame(animId);
      window.removeEventListener("resize", handleResize);
    };
  }, [running, activeScenario]);

  return (
    <canvas
      ref={canvasRef}
      className="pointer-events-none fixed inset-0 z-0 opacity-40"
      aria-hidden
    />
  );
}
