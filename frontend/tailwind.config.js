/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Primary (60%): Cool Titanium Silk
        titanium: {
          50: "#FFFFFF",
          100: "#F8F9FB", // Silk highlight
          highlight: "#F8F9FB",
          base: "#F1F3F6", // Base titanium
          200: "#F1F3F6",
          300: "#E8EBF1", // Silk fold
          fold: "#E8EBF1",
          400: "#DDE1EA", // Deep shadow fold
          shadow: "#DDE1EA",
          500: "#94A3B8",
          600: "#64748B",
        },
        // Secondary (30%): Deep Gunmetal
        gunmetal: {
          950: "#12151B",
          900: "#1E222B", // Deep Gunmetal primary
          DEFAULT: "#1E222B",
          850: "#252A35",
          800: "#2B303B", // Hover & raised dark surfaces
          hover: "#2B303B",
          raised: "#2B303B",
          700: "#3B4456",
          600: "#4D5566",
          500: "#5B6272", // Muted mono labels
          muted: "#5B6272",
          400: "#7C8599",
          300: "#A3ACBf",
        },
        // Accent (10%): Soft Ultraviolet
        ultraviolet: {
          DEFAULT: "#6366F1", // Soft Ultraviolet
          deep: "#7C3AED",
          bright: "#818CF8",
          light: "#A5B4FC",
          ice: "#EEF2FF",
          glow: "rgba(99, 102, 241, 0.14)", // Requested glow tint
          dim: "rgba(99, 102, 241, 0.14)",
          subtle: "rgba(99, 102, 241, 0.06)",
        },
        // Supporting signals
        signal: {
          green: "#10B981",
          greenLight: "rgba(16, 185, 129, 0.12)",
          amber: "#F59E0B",
          amberLight: "rgba(245, 158, 11, 0.12)",
          red: "#EF4444",
          redLight: "rgba(239, 68, 68, 0.12)",
        },
        // Semantic bridge aliases
        pine: {
          900: "#F1F3F6", // maps to titanium canvas
        },
        moss: {
          950: "#12151B",
          900: "#1E222B", // maps to gunmetal
          800: "#2B303B",
          700: "#3B4456",
          500: "#5B6272",
          400: "#7C8599",
        },
        celadon: {
          DEFAULT: "#6366F1", // maps to ultraviolet
          bright: "#818CF8",
          ice: "#1E222B",
          mist: "#5B6272",
          dim: "rgba(99, 102, 241, 0.14)",
        },
      },
      fontFamily: {
        display: ["Rajdhani", "system-ui", "-apple-system", "sans-serif"],
        mono: ["JetBrains Mono", "SF Mono", "Menlo", "monospace"],
      },
      boxShadow: {
        hud: "0 2px 10px rgba(30, 34, 43, 0.06)",
        glass: "0 8px 30px rgba(30, 34, 43, 0.08)",
        metal: "0 1px 3px rgba(30, 34, 43, 0.08), 0 1px 2px rgba(30, 34, 43, 0.05)",
        card: "0 4px 16px rgba(30, 34, 43, 0.06)",
        ultraviolet: "0 0 20px rgba(99, 102, 241, 0.28)",
        ultravioletSm: "0 0 10px rgba(99, 102, 241, 0.2)",
        glow: "0 0 24px rgba(99, 102, 241, 0.14)",
        red: "0 0 16px rgba(239, 68, 68, 0.25)",
        amber: "0 0 16px rgba(245, 158, 11, 0.25)",
        paper: "0 1px 2px rgba(30, 34, 43, 0.04)",
      },
      keyframes: {
        "node-breathe": {
          "0%, 100%": { opacity: "0.65", transform: "scale(1)" },
          "50%": { opacity: "1", transform: "scale(1.03)" },
        },
        "node-shake": {
          "0%, 100%": { transform: "translate(0, 0)" },
          "25%": { transform: "translate(-1.5px, 1px)" },
          "75%": { transform: "translate(1.5px, -1px)" },
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
        "node-breathe": "node-breathe 2.5s ease-in-out infinite",
        "node-shake": "node-shake 0.28s linear infinite",
        blink: "blink 1s step-end infinite",
        "fade-up": "fade-up 0.25s ease-out both",
      },
    },
  },
  plugins: [],
};
