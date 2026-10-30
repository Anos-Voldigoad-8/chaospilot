/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        void: {
          950: "#04070a",
          900: "#070c12",
          850: "#0a1219",
          800: "#0e1720",
          700: "#16232e",
        },
        neon: {
          cyan: "#20e7de",
          mint: "#41f2a6",
          amber: "#ffb224",
          red: "#ff3d55",
          ice: "#9fe8ef",
          dim: "#3f6b72",
        },
      },
      fontFamily: {
        display: ["Rajdhani", "Segoe UI", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "Cascadia Code", "Consolas", "monospace"],
      },
      boxShadow: {
        hud: "inset 0 0 40px rgba(0, 0, 0, 0.55)",
        cyan: "0 0 18px rgba(32, 231, 222, 0.22)",
        red: "0 0 22px rgba(255, 61, 85, 0.28)",
      },
      keyframes: {
        "node-breathe": {
          "0%, 100%": { opacity: "0.55", transform: "scale(1)" },
          "50%": { opacity: "1", transform: "scale(1.04)" },
        },
        "node-shake": {
          "0%, 100%": { transform: "translate(0, 0)" },
          "20%": { transform: "translate(-1.5px, 1px)" },
          "40%": { transform: "translate(1.5px, -1px)" },
          "60%": { transform: "translate(-1px, -1px)" },
          "80%": { transform: "translate(1px, 1px)" },
        },
        "node-flash": {
          "0%, 100%": { backgroundColor: "rgba(255, 61, 85, 0.05)" },
          "50%": { backgroundColor: "rgba(255, 61, 85, 0.18)" },
        },
        "hud-sweep": {
          "0%": { transform: "translateY(-10%)", opacity: "0" },
          "10%": { opacity: "1" },
          "90%": { opacity: "1" },
          "100%": { transform: "translateY(100vh)", opacity: "0" },
        },
        blink: {
          "0%, 49%": { opacity: "1" },
          "50%, 100%": { opacity: "0" },
        },
        "fade-up": {
          "0%": { opacity: "0", transform: "translateY(4px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        "node-breathe": "node-breathe 2.6s ease-in-out infinite",
        "node-shake": "node-shake 0.28s linear infinite",
        "node-flash": "node-flash 1.1s ease-in-out infinite",
        "hud-sweep": "hud-sweep 7s linear infinite",
        blink: "blink 1s step-end infinite",
        "fade-up": "fade-up 0.3s ease-out both",
      },
    },
  },
  plugins: [],
};
