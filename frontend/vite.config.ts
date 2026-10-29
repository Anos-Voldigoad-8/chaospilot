import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The dev proxy keeps the browser on one origin and forwards API traffic to
// the backend. VITE_API_BASE_URL can point elsewhere; no secrets live here.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8000",
      "/health": "http://127.0.0.1:8000",
    },
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
