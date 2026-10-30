import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The dev proxy keeps the browser on one origin and forwards API traffic to
// the backend. VITE_API_BASE_URL can point elsewhere; no secrets live here.
const backend = "http://127.0.0.1:8090";

const proxy = {
  "/health": backend,
  "/topology": backend,
  "/experiments": backend,
  "/ws": {
    target: backend,
    ws: true,
  },
};

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy,
  },
  preview: {
    port: 5173,
    proxy,
  },
  build: {
    outDir: "dist",
    sourcemap: false,
    rollupOptions: {
      output: {
        manualChunks: {
          flow: ["@xyflow/react"],
          charts: ["recharts"],
        },
      },
    },
  },
});
